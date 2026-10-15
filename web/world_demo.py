"""Bounded background town: payments -> scam report -> ADK -> reviewed prevention."""
import random
import threading

from lab import LabError, encoded, now
from fraud_scenarios import SCENARIOS as SCAMS

RUN_STEPS = 24


class WorldDemo:
    def __init__(self, world, desk, runner, checkpoint=None, guard=None, warehouse=None):
        self.world,self.lab,self.desk,self.runner=world,world.lab,desk,runner
        self.checkpoint=checkpoint or (lambda:None);self.guard=guard
        self.warehouse=warehouse;self.environment_publisher=None
        self.thread=None;self.stopping=threading.Event();self.closed=False;self.resetter=None
        self.lab.db.executescript('''
        CREATE TABLE IF NOT EXISTS world_demo_state(
          id INTEGER PRIMARY KEY CHECK(id=1), run_id INTEGER NOT NULL DEFAULT 0,
          running INTEGER NOT NULL DEFAULT 0, steps INTEGER NOT NULL DEFAULT 0,
          activity INTEGER NOT NULL DEFAULT 2, speed INTEGER NOT NULL DEFAULT 1,
          note TEXT NOT NULL DEFAULT 'Ready');
        INSERT OR IGNORE INTO world_demo_state(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS world_incidents(
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL,
          customer_id TEXT NOT NULL, report_id TEXT, memory_ids TEXT NOT NULL,
          event_ids TEXT NOT NULL, amount_minor INTEGER NOT NULL, tick INTEGER NOT NULL,
          created_at TEXT NOT NULL);
        ''')
        with self.lab.db:
            columns={r['name'] for r in self.lab.rows('PRAGMA table_info(world_demo_state)')}
            for name,definition in {'guided':'INTEGER NOT NULL DEFAULT 0','focus_report_id':'TEXT','event_start':'INTEGER NOT NULL DEFAULT 0'}.items():
                if name not in columns:self.lab.db.execute('ALTER TABLE world_demo_state ADD COLUMN '+name+' '+definition)
            self.lab.db.execute("UPDATE world_demo_state SET running=0,note='Paused after server restart' WHERE running=1")

    def status(self):
        with self.lab.lock:
            state=dict(self.lab.db.execute('SELECT * FROM world_demo_state WHERE id=1').fetchone())
            incidents=self.lab.rows('''SELECT w.*,r.status AS report_status FROM world_incidents w
                LEFT JOIN fraud_reports r ON r.id=w.report_id ORDER BY w.rowid DESC LIMIT 20''')
            provider='gemini' if self.runner.agent.live_enabled() else 'fake'
            budget=self.runner.agent.budget('',provider)
            blocked=self.lab.db.execute("SELECT count(*) FROM financial_events WHERE kind='payment_blocked' AND json_extract(metadata,'$.prevention_tool')='payments.hold_transfer'").fetchone()[0]
            phase='world';focus=None
            if state['guided'] and state['focus_report_id']:
                focus=self.desk.detail(state['focus_report_id']);job=focus.get('prevention');rule=job.get('rule') if job else None
                phase='complaint' if focus['status']=='reported' else 'investigation' if focus['status']=='investigating' else 'review' if focus['status']=='awaiting_review' else 'followup' if focus['status']=='awaiting_customer' else 'attention'
                if focus['status']=='resolved':
                    phase='prevention' if not job or job['status'] in ('ready','queued','running') else 'activate' if rule and rule['status']=='proposed' else 'ready' if rule and rule['status']=='active' else 'attention'
                if any(i['id']=='world-proof-'+str(state['run_id']) and i['status']=='passed' for i in incidents):phase='protected'
            scene=self.lab.db.execute('SELECT scene_id FROM demo_scene WHERE id=1').fetchone()[0] if self.resetter else 'legacy'
            restart_blocked=bool(self.runner.pending or self.lab.db.execute("SELECT 1 FROM fraud_agent_turns WHERE status IN ('reserved','responded') LIMIT 1").fetchone())
            if self.environment_publisher and self.lab.db.execute("SELECT 1 FROM environment_publications WHERE status!='completed' LIMIT 1").fetchone():restart_blocked=True
            return {**state,'max_steps':RUN_STEPS,'provider':provider,'incidents':incidents,'blocked_payments':blocked,
                    'knowledge_count':len(self.desk.memories()),'calls_remaining':max(0,budget['daily_call_limit']-budget['daily_calls']),
                    'phase':phase,'scene_id':scene,'focus_customer_id':focus['customer_id'] if focus else None,
                    'restart_blocked':restart_blocked,'agent_busy':bool(self.runner.pending)}

    def start(self, expected_run, activity=2, speed=1, background=True, fresh=False):
        if type(expected_run) is not int or type(activity) is not int or activity not in range(1,5) or type(speed) is not int or speed not in (1,2,4):
            raise LabError('Invalid world controls.')
        with self.lab.lock:
            current=self.status()
            if self.closed:raise LabError('The world is stopping.',503)
            if current['running'] or expected_run!=current['run_id']:return current
            if self.thread and self.thread.is_alive():raise LabError('The previous world run is stopping.',409)
            if type(fresh) is not bool:raise LabError('Fresh must be true or false.')
            if fresh:
                if not self.resetter:raise LabError('Fresh demo reset is unavailable.',409)
                self.resetter.reset(current['run_id']+1)
            with self.lab.db:
                self.lab.db.execute("UPDATE world_demo_state SET run_id=?,running=1,steps=0,activity=?,speed=?,note='Running' WHERE id=1",(current['run_id']+1,activity,speed))
            self.checkpoint();self.stopping.clear();run_id=current['run_id']+1
            if background:
                self.thread=threading.Thread(target=self.work,args=(run_id,),daemon=True,name='town-world');self.thread.start()
            return self.status()

    def stop(self, expected_run):
        with self.lab.lock,self.lab.db:
            if type(expected_run) is not int:raise LabError('Use the current world run.')
            if expected_run!=self.status()['run_id']:return self.status()
            self.stopping.set()
            self.lab.db.execute("UPDATE world_demo_state SET running=0,note='Paused' WHERE id=1")
        self.checkpoint();return self.status()

    def incident(self, run_id, kind, repeat=False):
        """A scoped simulator event; observed payments are the investigator's evidence."""
        spec=dict(SCAMS[kind])
        learned=bool(repeat and self.world.prevention and any(r['family']==kind for r in self.world.prevention.active()))
        if learned:spec['payee']='external:variant-'+str(run_id)+'-'+kind
        identifier='world-scam-%s-%s-%s'%(run_id,kind,'variant' if learned else 'repeat' if repeat else 'first')
        with self.lab.lock:
            if self.lab.db.execute('SELECT 1 FROM world_incidents WHERE id=?',(identifier,)).fetchone():return None
            cid='C002' if repeat and kind=='phishing' else 'C005' if repeat else spec['customer']
            metadata={'rail':'Wallet','device_known':spec['device_known'],'authorization_verified':spec['authorization_verified'],
                'authorized_payee':spec['payee'],'scenario':kind,'source':'world_demo',
                'guided_demo':bool(self.lab.db.execute('SELECT guided FROM world_demo_state WHERE id=1').fetchone()[0]),
                'payment_context':{'before_payment':True,'kind':'payment_request','message':spec['message']}}
            at=self.lab.clock_day+'T%02d:00:00Z'%self.world.status()['hour']
            opening=self.lab.db.execute('SELECT balance_minor FROM accounts WHERE id=?',(cid+':wallet',)).fetchone()[0]
            first_amount=min(spec.get('amounts',(spec['amount'],))[0],opening//spec['count'])
            _,flags=self.world.payment_flags(cid,spec['payee'],first_amount,metadata,at)
            if repeat and not flags and not learned and kind in ('phishing','payment_burst'):
                for memory in self.desk.memories():
                    pattern=memory['pattern']
                    matching_shape=(len(pattern['evidence_ids'])==1 if kind=='phishing' else len(pattern['evidence_ids'])>1)
                    if memory['validation']['passed'] and matching_shape and pattern['recipient_accounts']:
                        spec['payee']=pattern['recipient_accounts'][0]
                        flags=self.desk.screen(cid,spec['payee']);break
            if repeat and not flags:return None
            status='blocked' if flags else 'investigating';report_id=None;events=[];settled=[];total=0;memory_ids={f['memory_id'] for f in flags}
            provider='gemini' if self.runner.agent.live_enabled() else 'fake'
            if not flags:
                budget=self.runner.agent.budget('',provider)
                if (budget['daily_calls']>=budget['daily_call_limit'] or
                    budget['daily_committed_microusd']+10000>budget['daily_limit_microusd'] or
                    budget['total_committed_microusd']+10000>budget['total_limit_microusd'] or
                    (provider=='gemini' and self.runner.agent.runtime()['live_circuit_open'])):
                    status='budget_limited'
                if status!='budget_limited' and self.guard:
                    try:self.guard.allow('POST','/api/fraud-desk/report',{'request_id':identifier})
                    except LabError:status='budget_limited'
            if status!='budget_limited':
                with self.lab.db:
                    self.lab.db.execute('INSERT OR IGNORE INTO accounts(id,label,kind,opening_minor,balance_minor) VALUES(?,?,?,0,0)',
                                        (spec['payee'],'Synthetic scam recipient','counterparty'))
                    for n in range(spec['count']):
                        balance=self.lab.db.execute('SELECT balance_minor FROM accounts WHERE id=?',(cid+':wallet',)).fetchone()[0]
                        amount=min(spec.get('amounts',(spec['amount'],)*spec['count'])[n],balance//(spec['count']-n))
                        if amount<100:break
                        eid=identifier+'-'+str(n)
                        at=self.lab.clock_day+'T%02d:00:%02dZ'%(self.world.status()['hour'],n*4)
                        device=('device-' if spec['device_known'] else 'unrecognized-')+cid
                        outcome=self.world.payment(eid,cid,spec['payee'],amount,device,
                            {**metadata,'authorized_payee':spec['payee']},occurred_at=at)
                        if outcome=='declined':continue
                        events.append(eid);total+=amount
                        if outcome=='settled':settled.append(eid)
                        else:
                            import json
                            receipt=json.loads(self.lab.db.execute('SELECT metadata FROM financial_events WHERE id=?',(eid,)).fetchone()[0])
                            memory_ids.update(f['memory_id'] for f in receipt.get('review_flags',[]) if f.get('memory_id'))
                            break  # A verification hold pauses the remaining payment batch.
                    if settled and flags and self.guard:
                        # A policy can expire between preview and execution. Still require
                        # case admission if an actual transfer settled in that interval.
                        try:self.guard.allow('POST','/api/fraud-desk/report',{'request_id':identifier})
                        except LabError:status='needs_review';settled=[]
                    if settled:
                        report=self.desk.create(cid,spec['story'],spec['message'],settled,identifier);report_id=report['id']
                        if metadata['guided_demo'] and not repeat:
                            self.lab.db.execute("UPDATE world_demo_state SET focus_report_id=?,running=0,note='Customer filed a scam report. Follow the investigation.' WHERE id=1",(report_id,))
                    elif events and status!='needs_review':status='blocked'
                    elif not events:status='no_funds'
            with self.lab.db:
                self.lab.db.execute('INSERT INTO world_incidents VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (identifier,kind,spec['title']+(' · changed recipient' if learned else ''),status,cid,report_id,encoded(sorted(memory_ids)),
                     encoded(events),total,self.world.state()['tick'],now()))
            self.checkpoint()
        if report_id:
            try:
                if self.environment_publisher:self.environment_publisher.publish()
                if self.warehouse:self.warehouse.publish()
                self.runner.start(report_id,provider)
            except LabError as exc:
                with self.lab.lock,self.lab.db:
                    self.lab.db.execute("UPDATE world_incidents SET status='needs_review' WHERE id=?",(identifier,))
                    self.lab.db.execute('UPDATE world_demo_state SET note=? WHERE id=1',(str(exc),))
                self.checkpoint()
        return identifier

    def tick(self, run_id):
        with self.lab.lock:
            state=self.status()
            if not state['running'] or run_id!=state['run_id']:return state
            # This tick is local-only. Persist its allowance and resulting ledger together,
            # before any publication or model call, instead of uploading the full DB twice.
            if self.guard:self.guard.allow('POST','/api/world/step',{},checkpoint=False)
            self.world.advance(self.world.state()['tick'],state['activity'],'none')
            step=state['steps']+1
            with self.lab.db:self.lab.db.execute('UPDATE world_demo_state SET steps=? WHERE id=1',(step,))
            self.checkpoint()
        rng=random.Random(run_id)
        first_at=rng.randint(4,6);burst_at=rng.randint(12,14)
        if state['guided']:
            if step==first_at:self.incident(run_id,'phishing')
            return self.status()
        kinds=tuple(SCAMS);first=kinds[((run_id-1)*2)%len(kinds)];second=kinds[((run_id-1)*2+1)%len(kinds)]
        if step==first_at:self.incident(run_id,first)
        if step==burst_at:self.incident(run_id,second)
        if step>=first_at+4:
            for kind in SCAMS:self.incident(run_id,kind,repeat=True)
        # Only the simulator's own customers answer. Never invent answers for submitted user reports.
        with self.lab.lock:
            waiting=self.lab.rows("""SELECT r.id,r.revision,w.kind FROM world_incidents w JOIN fraud_reports r
                ON r.id=w.report_id WHERE w.id LIKE ? AND r.status='awaiting_customer' AND r.answers='[]' LIMIT 2""",('world-scam-'+str(run_id)+'-%',))
        for report in waiting:
            answer=SCAMS[report['kind']]['reply']
            try:
                if self.guard:self.guard.allow('POST','/api/fraud-desk/reply',{})
                self.runner.reply(report_id=report['id'],answer=answer,expected_revision=report['revision'])
            except LabError:pass
        with self.lab.lock,self.lab.db:
            if step>=RUN_STEPS:self.lab.db.execute("UPDATE world_demo_state SET running=0,note='24-hour episode complete' WHERE id=1")
        self.checkpoint();return self.status()

    def prove(self,expected_run):
        with self.lab.lock:
            state=self.status()
            if type(expected_run) is not int or state['run_id']!=expected_run:raise LabError('The demo changed. Refresh its state.',409)
            if state['phase']=='protected':return state
            if state['phase']!='ready':raise LabError('Activate the reviewed prevention safeguard before testing it.',409)
            self.incident(expected_run,'phishing',repeat=True)
            held=self.lab.db.execute("SELECT id FROM world_incidents WHERE id=? AND status='blocked'",('world-scam-'+str(expected_run)+'-phishing-variant',)).fetchone()
            if not held:raise LabError('This safeguard did not match the changed-recipient request. Review its replay.',409)
            with self.lab.db:
                eid='world-proof-payment-'+str(expected_run)
                result=self.world.payment(eid,'C002','m1',5000,'device-C002',{'device_known':True,'authorization_verified':True,
                    'payment_context':{'before_payment':True,'kind':'payment_request','message':'I am paying for groceries I ordered.'}})
                if result!='settled':raise LabError('The legitimate control did not settle. Review the safeguards.',409)
                self.lab.db.execute('INSERT INTO world_incidents VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    ('world-proof-'+str(expected_run),'control','Legitimate payment','passed','C002',None,'[]',encoded([eid]),5000,self.world.state()['tick'],now()))
                self.lab.db.execute("UPDATE world_demo_state SET note='Similar scam held before debit. Legitimate payment passed.' WHERE id=1")
            self.checkpoint();return self.status()

    def work(self, run_id):
        try:
            for _ in range(RUN_STEPS):
                state=self.status()
                if not state['running'] or state['run_id']!=run_id:break
                if self.stopping.wait(max(1.1,3/state['speed'])):break
                if not self.tick(run_id)['running']:break
        except Exception as exc:
            with self.lab.lock,self.lab.db:
                self.lab.db.execute('UPDATE world_demo_state SET running=0,note=? WHERE id=1',
                                    (str(exc) if isinstance(exc,LabError) else 'World paused after an error. No automatic retry.',))
            try:self.checkpoint()
            except LabError:pass

    def close(self):
        self.closed=True;self.stopping.set()
        if self.thread:self.thread.join()
        with self.lab.lock,self.lab.db:self.lab.db.execute("UPDATE world_demo_state SET running=0,note='Paused' WHERE running=1")
        try:self.checkpoint()
        except LabError:pass
