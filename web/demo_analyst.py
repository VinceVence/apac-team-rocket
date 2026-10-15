"""Explicit, per-case demo consent; reuses review and replay gates without an LLM."""
import logging

from lab import LabError, now


class DemoAnalyst:
    def __init__(self, world_demo):
        self.world_demo = world_demo
        self.lab, self.desk, self.runner = world_demo.lab, world_demo.desk, world_demo.runner
        self.lab.db.execute('''CREATE TABLE IF NOT EXISTS demo_analyst_approvals(
            report_id TEXT PRIMARY KEY, run_id INTEGER NOT NULL, investigation_id TEXT NOT NULL,
            review_id TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL, updated_at TEXT NOT NULL)''')
        with self.lab.db:
            self.lab.db.execute("UPDATE demo_analyst_approvals SET status='attention',detail='Demo approval stopped on restart. Review the saved lesson and safeguard manually.' WHERE status='learning'")
        self.desk.demo_analyst = self
        self.runner.on_learning_complete = self.finish

    def status(self, report):
        row = self.lab.db.execute('SELECT * FROM demo_analyst_approvals WHERE report_id=?', (report['id'],)).fetchone()
        if row:
            return {**dict(row), 'eligible': False, 'assumption': True, 'actor': 'demo_fraud_analyst'}
        state = self.lab.db.execute('SELECT run_id FROM world_demo_state WHERE id=1').fetchone()
        incident = self.lab.db.execute('SELECT id FROM world_incidents WHERE report_id=?', (report['id'],)).fetchone()
        tx = report['transactions']
        synthetic = bool(incident and incident['id'].startswith('world-scam-'+str(state['run_id'])+'-') and tx
                         and all(t['metadata'].get('source') == 'world_demo' for t in tx))
        run = report['investigation']
        reason = 'Available only for a case created by the current simulation.'
        if synthetic:
            prep = report.get('preparation') or {}
            if prep.get('status') in ('blocked', 'interrupted'):
                reason = 'Evidence is blocked. Auto-approval cannot replace the missing investigation.'
            elif not run or report['status'] != 'awaiting_review' or run['status'] != 'awaiting_review' or run['id'] in self.runner.pending:
                reason = 'Available when the agent finishes its investigation.'
            elif run['context'].get('controller') != 'adk' or run['context'].get('manual_handoff') or not run.get('snapshot'):
                reason = 'This case requires manual review of the saved evidence.'
            elif report.get('validation_warnings') or run['recommendation']['disposition'] not in ('suspected_scam', 'likely_legitimate'):
                reason = 'Resolve the missing evidence or validation warnings manually.'
            else:
                return {'eligible': True, 'status': 'ready', 'detail': 'Ready for demo approval.'}
        return {'eligible': False, 'status': 'unavailable', 'detail': reason}

    def approve(self, expected_run, report_id, investigation_id):
        with self.lab.lock:
            current = self.lab.db.execute('SELECT run_id FROM world_demo_state WHERE id=1').fetchone()[0]
            if type(expected_run) is not int or expected_run != current:
                raise LabError('The simulation changed. Open its current case.', 409)
            report = self.desk.detail(report_id)
            state = self.status(report)
            if state.get('investigation_id') == investigation_id:
                return report  # Repeated clicks cannot create another review or generation.
            if not state['eligible']:
                raise LabError(state['detail'], 409)
            run = report['investigation']
            if run['id'] != investigation_id:
                raise LabError('The investigation changed. Refresh the case.', 409)
            proposal = run['recommendation']
            scam = proposal['disposition'] == 'suspected_scam'
            with self.lab.db:
                reviewed = self.desk.review(report_id, investigation_id,
                    'confirmed_scam' if scam else 'not_scam', proposal['suggested_action'] if scam else 'support_followup',
                    'DEMO ASSUMPTION: the viewer requested simulated Fraud Analyst approval of this completed investigation. Not a real human review.',
                    scam, proposal['suggested_lesson'], proposal['suggested_question'])
                self.lab.db.execute('INSERT INTO demo_analyst_approvals VALUES(?,?,?,?,?,?,?)',
                    (report_id, current, investigation_id, reviewed['reviews'][0]['id'], 'learning' if scam else 'reviewed',
                     'Demo review saved. Prevention will test the lesson.' if scam else 'Demo review saved. No scam lesson or safeguard was created.', now()))
            self.world_demo.checkpoint()  # Persist consent and the review before any learning call.
            if scam:
                try:
                    self.runner.learn(report_id, run['context']['provider'])
                except LabError as exc:
                    self.record(report_id, 'attention', 'Lesson saved; prevention was not started. '+str(exc))
            self.world_demo.checkpoint()
            return self.desk.detail(report_id)

    def record(self, report_id, status, detail):
        with self.lab.db:
            self.lab.db.execute('UPDATE demo_analyst_approvals SET status=?,detail=?,updated_at=? WHERE report_id=?',
                                (status, detail, now(), report_id))

    def finish(self, report_id):
        """Called after the one existing prevention worker finishes; never retries."""
        with self.lab.lock:
            consent = self.lab.db.execute("SELECT * FROM demo_analyst_approvals WHERE report_id=? AND status='learning'", (report_id,)).fetchone()
            if not consent:
                return
            try:
                current = self.lab.db.execute('SELECT run_id FROM world_demo_state WHERE id=1').fetchone()[0]
                if current != consent['run_id']:
                    raise LabError('The simulation changed; manual activation is required.')
                job = self.runner.prevention.for_report(report_id)
                rule = job.get('rule') if job else None
                if not job or job['status'] != 'awaiting_activation' or not rule or not rule['replay']['passed']:
                    raise LabError('The prevention candidate did not pass. The lesson is saved; no broader safeguard was activated.')
                self.runner.prevention.activate(rule['id'], True)
                self.record(report_id, 'activated', 'Demo Fraud Analyst approved the resolution and activated the replay-passed safeguard.')
            except LabError as exc:
                self.record(report_id, 'attention', str(exc))
            except Exception:
                logging.getLogger(__name__).exception('Demo activation stopped for %s', report_id)
                self.record(report_id, 'attention', 'Demo activation stopped. Review the saved safeguard manually; no retry was made.')
