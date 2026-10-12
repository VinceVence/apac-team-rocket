"""Bounded background town: payments -> scam report -> ADK -> reviewed prevention."""
import random
import threading

from lab import LabError, encoded, now

RUN_STEPS = 24
SCAMS = {
    'phishing': {'title':'Phishing attempt','payee':'external:phishing-link','customer':'C001','count':1,'amount':90000,
        'story':'A bank support text linked to a verification page. The caller told me to move money to a safe account immediately. I entered my PIN and now the caller has disappeared.',
        'message':'Bank security: urgently verify your wallet at bank-check.example.invalid and move funds to the safe account.'},
    'payment_burst': {'title':'Payment burst','payee':'external:burst-network','customer':'C004','count':3,'amount':14000,
        'story':'Three unrecognized payments left my wallet in a few seconds. A caller claiming to be bank support said these urgent transfers were needed to protect my money. I did not intend to pay this recipient.',
        'message':'Bank support: approve these transfers immediately to protect your money.'}}


class WorldDemo:
    def __init__(self, world, desk, runner, checkpoint=None, guard=None):
        self.world,self.lab,self.desk,self.runner=world,world.lab,desk,runner
        self.checkpoint=checkpoint or (lambda:None);self.guard=guard
        self.thread=None;self.stopping=threading.Event();self.closed=False
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
            self.lab.db.execute("UPDATE world_demo_state SET running=0,note='Paused after server restart' WHERE running=1")

    def status(self):
        with self.lab.lock:
            state=dict(self.lab.db.execute('SELECT * FROM world_demo_state WHERE id=1').fetchone())
            incidents=self.lab.rows('''SELECT w.*,r.status AS report_status FROM world_incidents w
                LEFT JOIN fraud_reports r ON r.id=w.report_id ORDER BY w.rowid DESC LIMIT 20''')
            provider='gemini' if self.runner.agent.live_enabled() else 'fake'
            budget=self.runner.agent.budget('',provider)
            blocked=self.lab.db.execute("SELECT count(*) FROM financial_events WHERE kind='payment_blocked' AND json_extract(metadata,'$.prevention_tool')='payments.hold_transfer'").fetchone()[0]
            return {**state,'max_steps':RUN_STEPS,'provider':provider,'incidents':incidents,'blocked_payments':blocked,
                    'knowledge_count':len(self.desk.memories()),'calls_remaining':max(0,budget['daily_call_limit']-budget['daily_calls'])}

    def start(self, expected_run, activity=2, speed=1, background=True):
        if type(expected_run) is not int or type(activity) is not int or activity not in range(1,5) or type(speed) is not int or speed not in (1,2,4):
            raise LabError('Invalid world controls.')
        with self.lab.lock:
            current=self.status()
            if self.closed:raise LabError('The world is stopping.',503)
            if current['running'] or expected_run!=current['run_id']:return current
            if self.thread and self.thread.is_alive():raise LabError('The previous world run is stopping.',409)
            with self.lab.db:
                self.lab.db.execute("UPDATE world_demo_state SET run_id=run_id+1,running=1,steps=0,activity=?,speed=?,note='Running' WHERE id=1",(activity,speed))
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
        spec=SCAMS[kind];identifier='world-scam-%s-%s-%s'%(run_id,kind,'repeat' if repeat else 'first')
        with self.lab.lock:
            if self.lab.db.execute('SELECT 1 FROM world_incidents WHERE id=?',(identifier,)).fetchone():return None
            cid='C002' if repeat and kind=='phishing' else 'C005' if repeat else spec['customer']
            flags=self.desk.screen(cid,spec['payee'])
            if repeat and not flags:return None  # Wait for analyst approval; do not manufacture another loss.
            status='blocked' if flags else 'investigating';report_id=None;events=[];total=0
            provider='gemini' if self.runner.agent.live_enabled() else 'fake'
            if not flags:
                if self.runner.agent.budget('',provider)['daily_calls']>=self.runner.agent.agents.config.daily_calls:
                    status='budget_limited'
                elif provider=='gemini':
                    try:self.runner.agent.check_live_case('new-world-case')
                    except LabError:status='budget_limited'
                if status!='budget_limited' and self.guard:
                    try:self.guard.allow('POST','/api/fraud-desk/report',{'request_id':identifier})
                    except LabError:status='budget_limited'
            if status!='budget_limited':
                with self.lab.db:
                    self.lab.db.execute('INSERT OR IGNORE INTO accounts(id,label,kind,opening_minor,balance_minor) VALUES(?,?,?,0,0)',
                                        (spec['payee'],'Synthetic scam recipient','counterparty'))
                    for n in range(spec['count']):
                        balance=self.lab.db.execute('SELECT balance_minor FROM accounts WHERE id=?',(cid+':wallet',)).fetchone()[0]
                        amount=min(spec['amount'],balance//(spec['count']-n))
                        if amount<100:break
                        eid=identifier+'-'+str(n)
                        outcome=self.world.payment(eid,cid,spec['payee'],amount,'device-'+cid,
                            {'rail':'Wallet','device_known':kind=='phishing','authorization_verified':kind=='phishing',
                             'authorized_payee':spec['payee'],'scenario':kind,'source':'world_demo'})
                        if outcome=='declined':continue
                        if kind=='payment_burst':
                            self.lab.db.execute('UPDATE financial_events SET occurred_at=? WHERE id=?',
                                (self.lab.clock_day+'T%02d:00:%02dZ'%(self.world.status()['hour'],n*4),eid))
                        events.append(eid);total+=amount
                    if not flags and events:
                        report=self.desk.create(cid,spec['story'],spec['message'],events,identifier);report_id=report['id']
                    elif not events:status='no_funds'
            with self.lab.db:
                self.lab.db.execute('INSERT INTO world_incidents VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (identifier,kind,spec['title'],status,cid,report_id,encoded([f['memory_id'] for f in flags]),
                     encoded(events),total,self.world.state()['tick'],now()))
            self.checkpoint()
        if report_id:
            try:self.runner.start(report_id,provider)
            except LabError:
                with self.lab.lock,self.lab.db:self.lab.db.execute("UPDATE world_incidents SET status='needs_review' WHERE id=?",(identifier,))
                self.checkpoint()
        return identifier

    def tick(self, run_id):
        with self.lab.lock:
            state=self.status()
            if not state['running'] or run_id!=state['run_id']:return state
            if self.guard:self.guard.allow('POST','/api/world/step',{})
            self.world.advance(self.world.state()['tick'],state['activity'],'none')
            step=state['steps']+1
            with self.lab.db:self.lab.db.execute('UPDATE world_demo_state SET steps=? WHERE id=1',(step,))
            self.checkpoint()
        rng=random.Random(run_id)
        first_at=rng.randint(4,6);burst_at=rng.randint(12,14)
        if step==first_at:self.incident(run_id,'phishing')
        if step==burst_at:self.incident(run_id,'payment_burst')
        if step>=first_at+4:self.incident(run_id,'phishing',repeat=True)
        if step>=burst_at+4:self.incident(run_id,'payment_burst',repeat=True)
        # Only the simulator's own customers answer. Never invent answers for submitted user reports.
        with self.lab.lock:
            waiting=self.lab.rows("""SELECT r.id,r.revision,w.kind FROM world_incidents w JOIN fraud_reports r
                ON r.id=w.report_id WHERE w.id LIKE ? AND r.status='awaiting_customer' AND r.answers='[]' LIMIT 2""",('world-scam-'+str(run_id)+'-%',))
        for report in waiting:
            answer=('Yes. The caller said to use a safe account and keep it secret from bank staff.' if report['kind']=='phishing'
                    else 'No. I did not intend to approve these payments. The caller claimed they would protect my wallet.')
            try:
                if self.guard:self.guard.allow('POST','/api/fraud-desk/reply',{})
                self.runner.reply(report_id=report['id'],answer=answer,expected_revision=report['revision'])
            except LabError:pass
        with self.lab.lock,self.lab.db:
            if step>=RUN_STEPS:self.lab.db.execute("UPDATE world_demo_state SET running=0,note='24-hour episode complete' WHERE id=1")
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
