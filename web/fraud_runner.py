"""One local worker; every generation still passes through FraudAgent's durable gates."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time

from fraud_agent import TURN_TIMEOUT_SECONDS
from lab import LabError, encoded, now

RUN_TIMEOUT_SECONDS = 180
MAX_PENDING = 2

class InvestigationRunner:
    def __init__(self, agent):
        self.agent, self.lab, self.desk = agent, agent.lab, agent.desk
        # ponytail: one process owns SQLite; use database job leases before scaling out.
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='investigation')
        self.pending = set()
        self.closed = False
        self.stopping = threading.Event()

    def execution(self, run_id, status):
        run = self.desk.run(run_id)
        run['context']['execution'] = {'mode': 'automatic', 'status': status, 'updated_at': now()}
        self.lab.db.execute('UPDATE fraud_investigations SET context=? WHERE id=?', (encoded(run['context']), run_id))

    def start(self, report_id, mode='fake'):
        with self.lab.lock:
            if self.closed: raise LabError('The investigation worker is stopping.', 503)
            run = self.agent.start(report_id, mode)
            if run['status'] != 'running' or run['id'] in self.pending: return run
            if len(self.pending) >= MAX_PENDING: raise LabError('The investigation queue is full. Retry starting this saved report shortly.', 429)
            with self.lab.db: self.execution(run['id'], 'queued')
            self.agent.checkpoint()
            self.pending.add(run['id'])
            self.pool.submit(self.work, run['id'])
            return self.desk.run(run['id'])

    def work(self, run_id):
        deadline=time.monotonic()+RUN_TIMEOUT_SECONDS
        try:
            with self.lab.lock, self.lab.db: self.execution(run_id, 'running')
            # The extra iteration lets the admission gate record a clean limit stop.
            for _ in range(self.agent.max_case_calls + 1):
                with self.lab.lock:
                    if self.closed: break
                    run = self.desk.run(run_id)
                if run['status'] != 'running': break
                delay=self.agent.live_delay(run)
                if self.stopping.wait(min(delay,max(0,deadline-time.monotonic()))):break
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    with self.lab.lock,self.lab.db:self.agent.stop(run_id,'interrupted','Investigation time limit reached. No additional model request was made.')
                    break
                self.agent.step(run_id, run['step'], automatic=True,timeout=min(TURN_TIMEOUT_SECONDS,remaining))
                self.agent.checkpoint()
        except Exception:
            with self.lab.lock, self.lab.db:
                self.agent.stop(run_id, 'failed', 'The background investigation stopped. Review the saved evidence; no automatic retry was made.')
        finally:
            with self.lab.lock, self.lab.db:
                run = self.desk.run(run_id)
                if run['status'] in ('running', 'stepping'):
                    self.agent.stop(run_id, 'interrupted', 'The worker stopped. Saved evidence and cost reservations were retained.')
                    run = self.desk.run(run_id)
                self.execution(run_id, run['status'])
                self.pending.discard(run_id)
            self.agent.checkpoint()

    def reply(self, **command):
        with self.lab.lock:
            old = self.desk.detail(command['report_id'])['investigation']
            updated = self.desk.answer(**command)
            if old and old['context'].get('execution', {}).get('mode') == 'automatic':
                try: self.start(updated['id'], old['context']['provider'])
                except LabError as exc:
                    updated['auto_resume_error'] = 'Reply saved. ' + str(exc)
                    return updated
                return self.desk.detail(updated['id'])
            return updated

    def close(self):
        with self.lab.lock: self.closed = True; self.stopping.set()
        self.pool.shutdown(wait=True, cancel_futures=True)
        with self.lab.lock, self.lab.db:
            for run_id in self.pending:
                self.agent.stop(run_id, 'interrupted', 'The queued investigation stopped with the server. No request was retried.')
                self.execution(run_id, 'interrupted')
            self.pending.clear()
        try: self.agent.checkpoint()
        except LabError: pass  # A failed cloud checkpoint already fenced this instance.
