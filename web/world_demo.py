"""Bounded background town: payments -> scam report -> ADK -> reviewed prevention."""
import json
import random
import threading

from lab import LabError, encoded, now
from fraud_scenarios import SCENARIOS as SCAMS
from fraud_desk import LESSON, QUESTION
from cloud_data import DAILY_EXPORTS

RUN_STEPS = 24
REPORTS_PER_ANALYTICS_BATCH = 5


class WorldDemo:
    def __init__(self, world, desk, runner, checkpoint=None, guard=None, warehouse=None):
        self.world,self.lab,self.desk,self.runner=world,world.lab,desk,runner
        self.checkpoint=checkpoint or (lambda:None);self.guard=guard
        self.warehouse=warehouse;self.environment_publisher=None
        self.thread=None;self.intake=None;self.stopping=threading.Event();self.closed=False;self.resetter=None
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
        CREATE TABLE IF NOT EXISTS world_demo_actions(
          run_id INTEGER NOT NULL,report_id TEXT NOT NULL,action TEXT NOT NULL,
          receipt TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(run_id,action));
        ''')
        with self.lab.db:
            columns={r['name'] for r in self.lab.rows('PRAGMA table_info(world_demo_state)')}
            for name,definition in {'guided':'INTEGER NOT NULL DEFAULT 0','continuous':'INTEGER NOT NULL DEFAULT 0','focus_report_id':'TEXT','event_start':'INTEGER NOT NULL DEFAULT 0','report_reserved':'INTEGER NOT NULL DEFAULT 0'}.items():
                if name not in columns:self.lab.db.execute('ALTER TABLE world_demo_state ADD COLUMN '+name+' '+definition)
            self.lab.db.execute("UPDATE world_demo_state SET running=0,note='Paused after server restart' WHERE running=1")

    def status(self):
        with self.lab.lock:
            state=dict(self.lab.db.execute('SELECT * FROM world_demo_state WHERE id=1').fetchone())
            incidents=self.lab.rows('''SELECT w.*,r.status AS report_status FROM world_incidents w
                LEFT JOIN fraud_reports r ON r.id=w.report_id ORDER BY w.rowid DESC LIMIT 20''')
            provider='gemini' if self.runner.agent.live_enabled() else 'fake'
            budget=self.runner.agent.budget('',provider)
            condition="kind='payment_blocked' AND json_extract(metadata,'$.prevention_tool')='payments.hold_transfer'"
            totals=self.lab.db.execute('SELECT count(*),coalesce(sum(amount_minor),0) FROM financial_events WHERE '+condition).fetchone()
            protected=self.lab.rows('SELECT id,customer_id,amount_minor,occurred_at,metadata FROM financial_events WHERE '+condition+' ORDER BY rowid DESC LIMIT 6')
            for item in protected:
                metadata=json.loads(item.pop('metadata'));flags=metadata.get('review_flags',[])
                memory_ids=[f['memory_id'] for f in flags if f.get('memory_id')]
                lesson=self.lab.db.execute('SELECT source_report_id FROM scam_memories WHERE id=?',(memory_ids[0],)).fetchone() if memory_ids else None
                item.update(source_report_id=lesson[0] if lesson else None,reason=metadata.get('prevention_reason'),
                    rule_ids=metadata.get('prevention_rule_ids',[]),memory_ids=memory_ids,created_at=metadata.get('risk_recorded_at',item['occurred_at']))
            phase='world';focus=None
            if state['guided'] and state['focus_report_id']:
                focus=self.desk.detail(state['focus_report_id']);job=focus.get('prevention');rule=job.get('rule') if job else None
                phase='complaint' if focus['status']=='reported' else 'investigation' if focus['status']=='investigating' else 'review' if focus['status']=='awaiting_review' else 'followup' if focus['status']=='awaiting_customer' else 'attention'
                if focus['status']=='reported' and (focus.get('preparation',{} ) or {}).get('status') in ('blocked','interrupted'):phase='attention'
                if focus['status']=='resolved':
                    phase='prevention' if not job or job['status'] in ('ready','queued','running') else 'activate' if rule and rule['status']=='proposed' else 'ready' if rule and rule['status']=='active' else 'attention'
                if any(i['id']=='world-proof-'+str(state['run_id']) and i['status']=='passed' for i in incidents):phase='protected'
            scene=self.lab.db.execute('SELECT scene_id FROM demo_scene WHERE id=1').fetchone()[0] if self.resetter else 'legacy'
            restart_blocked=bool(self.runner.pending or self.lab.db.execute("SELECT 1 FROM fraud_agent_turns WHERE status IN ('reserved','responded') LIMIT 1").fetchone())
            if self.lab.db.execute("SELECT 1 FROM fraud_case_preparation WHERE status='running' LIMIT 1").fetchone():restart_blocked=True
            if self.environment_publisher and self.lab.db.execute("SELECT 1 FROM environment_publications WHERE status!='completed' LIMIT 1").fetchone():restart_blocked=True
            allowance=self.guard.status() if self.guard else None
            start_blocked='Live world allowance reached. The recorded Gemini demo remains available.' if allowance and allowance['used']['world_steps']>=allowance['limits']['world_steps_per_day'] else None
            failed_scene=bool(state['guided'] and not state['focus_report_id'] and any(i['id'].startswith('world-scam-'+str(state['run_id'])+'-') and i['status'] in ('budget_limited','no_funds') for i in incidents))
            scene_blocked=(start_blocked or (state['note'] if state['note'] not in ('Paused','Running','Ready') else 'The scam report was not created. No investigation ran.')) if failed_scene or (state['guided'] and not state['focus_report_id'] and not state['running'] and state['steps']) else None
            return {**state,'mode':'simulation' if state['continuous'] else 'demo' if state['guided'] else 'episode',
                    'max_steps':None if state['continuous'] else RUN_STEPS,'provider':provider,'incidents':incidents,'blocked_payments':totals[0],
                    'protection':{'count':totals[0],'amount_minor':totals[1],'recent':protected},
                    'presentation_actions':{r['action']:json.loads(r['receipt']) for r in self.lab.rows('SELECT action,receipt FROM world_demo_actions WHERE run_id=?',(state['run_id'],))},
                    'knowledge_count':len(self.desk.memories()),'calls_remaining':max(0,budget['daily_call_limit']-budget['daily_calls']),
                    'phase':phase,'scene_id':scene,'focus_customer_id':focus['customer_id'] if focus else None,
                    'restart_blocked':restart_blocked,'start_blocked_reason':start_blocked,'scene_blocked_reason':scene_blocked,
                    'agent_busy':bool(self.runner.pending or (self.intake and self.intake.is_alive()))}

    def start(self, expected_run, activity=2, speed=1, background=True, fresh=False, mode=None):
        if type(expected_run) is not int or type(activity) is not int or activity not in range(1,5) or type(speed) is not int or speed not in (1,2,4):
            raise LabError('Invalid world controls.')
        with self.lab.lock:
            current=self.status()
            if self.closed:raise LabError('The world is stopping.',503)
            if current['running'] or expected_run!=current['run_id']:return current
            if self.thread and self.thread.is_alive():raise LabError('The previous world run is stopping.',409)
            if type(fresh) is not bool:raise LabError('Fresh must be true or false.')
            if mode is not None and mode not in ('demo','simulation'):raise LabError('Choose demo or simulation.')
            resume=mode=='simulation' and current['continuous'] and not fresh
            run_id=current['run_id'] if resume else current['run_id']+1
            guided=mode=='demo' or mode is None and (fresh or current['guided'])
            # A server-created guided complaint is local data, not a paid call.
            # Only continuous/user-submitted reports consume report admission.
            report_reserved=int(guided)
            if fresh:
                if not self.resetter:raise LabError('Fresh demo reset is unavailable.',409)
                self.resetter.reset(current['run_id']+1)
            with self.lab.db:
                self.lab.db.execute("UPDATE world_demo_state SET run_id=?,running=1,steps=?,activity=?,speed=?,report_reserved=?,note='Running' WHERE id=1",(run_id,current['steps'] if resume else 0,activity,speed,report_reserved))
                if mode:self.lab.db.execute('UPDATE world_demo_state SET guided=?,continuous=?,focus_report_id=CASE WHEN ? THEN focus_report_id ELSE NULL END WHERE id=1',(int(mode=='demo'),int(mode=='simulation'),int(mode=='demo')))
            self.checkpoint();self.stopping.clear()
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

    def restart(self,expected_run,activity=2,speed=1,background=True):
        """Archive this scene and start empty; accounting and limits survive."""
        if type(expected_run) is not int or type(activity) is not int or activity not in range(1,5) or type(speed) is not int or speed not in (1,2,4):
            raise LabError('Invalid restart controls.')
        with self.lab.lock:
            state=self.status()
            if expected_run!=state['run_id']:return state
            if state['restart_blocked']:raise LabError('Wait for the current agent or evidence work to finish before restarting.',409)
            previous=self.thread
            self.stop(expected_run)
        if previous:
            previous.join(timeout=5)
            if previous.is_alive():raise LabError('The previous simulation is still stopping. Its saved scene is unchanged.',409)
        return self.start(expected_run,activity,speed,background=background,fresh=True,mode='simulation')

    def incident(self, run_id, kind, repeat=False, cycle=0, background=False):
        """A scoped simulator event; observed payments are the investigator's evidence."""
        spec=dict(SCAMS[kind])
        learned=bool(repeat and self.world.prevention and any(r['family']==kind for r in self.world.prevention.active()))
        if learned:spec['payee']='external:variant-'+str(run_id)+'-'+kind
        identifier='world-scam-%s-%s-%s'%(run_id,kind,'variant' if learned else 'repeat' if repeat else 'first')+('-cycle'+str(cycle) if cycle else '')
        with self.lab.lock:
            # One intake and one existing model worker; never accumulate an unbounded queue.
            if background and not repeat and (self.runner.pending or (self.intake and self.intake.is_alive())):return None
            if self.lab.db.execute('SELECT 1 FROM world_incidents WHERE id=?',(identifier,)).fetchone():return None
            scene=self.lab.db.execute('SELECT run_id,guided,report_reserved FROM world_demo_state WHERE id=1').fetchone()
            reserved=bool(scene['run_id']==run_id and scene['guided'] and scene['report_reserved'] and kind=='phishing' and not repeat and not cycle)
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
            status='blocked' if flags else 'investigating';report_id=None;events=[];settled=[];total=0;memory_ids={f['memory_id'] for f in flags};manual_only=False;admission_error=None
            provider='gemini' if self.runner.agent.live_enabled() else 'fake'
            if not flags:
                budget=self.runner.agent.budget('',provider)
                if (budget['daily_calls']>=budget['daily_call_limit'] or
                    budget['daily_committed_microusd']+10000>budget['daily_limit_microusd'] or
                    budget['total_committed_microusd']+10000>budget['total_limit_microusd'] or
                    (provider=='gemini' and self.runner.agent.runtime()['live_circuit_open'])):
                    status='budget_limited'
                if status=='budget_limited' and metadata['guided_demo']:
                    manual_only=True;status='needs_review'
                if status!='budget_limited' and self.guard and not reserved:
                    try:self.guard.allow('POST','/api/fraud-desk/report',{'request_id':identifier})
                    except LabError as exc:status='budget_limited';admission_error=str(exc)
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
                    if settled and flags and self.guard and not reserved:
                        # A policy can expire between preview and execution. Still require
                        # case admission if an actual transfer settled in that interval.
                        try:self.guard.allow('POST','/api/fraud-desk/report',{'request_id':identifier})
                        except LabError:status='needs_review';settled=[]
                    if settled:
                        report=self.desk.create(cid,spec['story'],spec['message'],settled,identifier);report_id=report['id']
                        self.desk.prepare(report_id,'running','report','The customer report is saved. Preparing its recorded evidence.')
                        if metadata['guided_demo'] and not repeat:
                            self.lab.db.execute("UPDATE world_demo_state SET focus_report_id=?,running=0,note='Customer filed a scam report. Follow the investigation.' WHERE id=1",(report_id,))
                    elif events and status!='needs_review':status='blocked'
                    elif not events:status='no_funds'
            with self.lab.db:
                self.lab.db.execute('INSERT INTO world_incidents VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (identifier,kind,spec['title']+(' · changed recipient' if learned else ''),status,cid,report_id,encoded(sorted(memory_ids)),
                     encoded(events),total,self.world.state()['tick'],now()))
                if metadata['guided_demo'] and not repeat and not report_id:
                    self.lab.db.execute('UPDATE world_demo_state SET running=0,note=? WHERE id=1',
                        (admission_error or 'The scam report was not created. No investigation ran.',))
            self.checkpoint()
        if report_id:
            if manual_only:
                self.desk.prepare(report_id,'blocked','admission','Live investigation is unavailable. The demo can continue with an assumed analyst review of the recorded payment; no model request was made.');self.checkpoint()
            elif metadata['guided_demo'] and not repeat:
                self.desk.prepare(report_id,'waiting','demo_investigation','Ready. Next starts the resolution agent while you watch its decisions.');self.checkpoint()
            elif background:
                self.intake=threading.Thread(target=self.prepare,args=(report_id,identifier,provider),daemon=True,name='case-intake');self.intake.start()
            else:self.prepare(report_id,identifier,provider)
        return identifier

    def sync_analytics(self):
        """Coalesce reports; never make an analytics quota the case-evidence gate."""
        cloud=self.warehouse.cloud if self.warehouse else self.environment_publisher.cloud if self.environment_publisher else None
        if not cloud:return 'Local ledger evidence is ready.'
        with self.lab.lock:
            if not cloud.healthy:raise LabError('Cloud state is unavailable.',503)
            if self.warehouse and self.warehouse.matching_snapshot():
                return 'Reusing the matching completed publication; no new BigQuery write.'
            latest=self.warehouse.latest() if self.warehouse else None
            published_reports=json.loads(latest['counts']).get('pallet_complaints',0) if latest else 0
            reports=self.lab.db.execute('SELECT count(*) FROM fraud_reports').fetchone()[0]
            if latest and reports-published_reports<REPORTS_PER_ANALYTICS_BATCH:
                return 'Fresh ledger evidence is ready. Analytics sync waits for the shared five-report batch.'
            for table in ('warehouse_snapshots','environment_publications'):
                if self.lab.db.execute("SELECT 1 FROM sqlite_master WHERE name=?",(table,)).fetchone() and self.lab.db.execute("SELECT 1 FROM "+table+" WHERE status!='completed'").fetchone():
                    return 'Fresh ledger evidence is ready. An uncertain analytics publication needs reconciliation; no load was retried.'
            needed=int(self.warehouse is not None)+int(self.environment_publisher is not None)
            if cloud.daily_exports(self.lab)+needed>DAILY_EXPORTS:
                return 'Fresh ledger evidence is ready. BigQuery sync is deferred until publication allowance is available.'
        try:
            # Each existing publisher retains its own durable allowance and job receipts.
            if self.warehouse:self.warehouse.publish()
            if self.environment_publisher:self.environment_publisher.publish()
            return 'The shared analytics batch is saved. Case evidence is ready.'
        except LabError:
            if not cloud.healthy:raise
            return 'Fresh ledger evidence is ready. Analytics sync stopped; no load was retried.'

    def prepare_evidence(self,report_id):
        report=self.desk.report(report_id)
        if not self.desk.transactions(report):raise LabError('The reported payment evidence is missing.',409)
        self.desk.prepare(report_id,'running','ledger_snapshot','Freezing the recorded payments and case-time behavior.')
        notice=self.sync_analytics()
        self.desk.prepare(report_id,'running','dispatch',notice)
        return notice

    def prepare(self,report_id,identifier,provider):
        try:
            notice=self.prepare_evidence(report_id)
            self.desk.prepare(report_id,'running','dispatch','Handing the saved evidence to the resolution agent.')
            self.runner.start(report_id,provider)
            self.desk.prepare(report_id,'completed','dispatched',notice)
        except LabError as exc:
            self.desk.prepare(report_id,'blocked','preparation',str(exc))
            with self.lab.lock,self.lab.db:
                self.lab.db.execute("UPDATE world_incidents SET status='needs_review' WHERE id=?",(identifier,))
                self.lab.db.execute('UPDATE world_demo_state SET note=? WHERE id=1',(str(exc),))
            self.checkpoint()
        except Exception:
            self.desk.prepare(report_id,'blocked','preparation','Evidence preparation failed. The case is saved; no task was retried.')
            with self.lab.lock,self.lab.db:self.lab.db.execute("UPDATE world_incidents SET status='needs_review' WHERE id=?",(identifier,))
            self.checkpoint()

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
            if step>=RUN_STEPS:
                with self.lab.db:self.lab.db.execute("UPDATE world_demo_state SET running=0,note='Demo finished without an admitted report.' WHERE id=1")
                self.checkpoint()
            return self.status()
        cycle=(step-1)//RUN_STEPS if state['continuous'] else 0;episode=(step-1)%RUN_STEPS+1 if state['continuous'] else step
        kinds=tuple(SCAMS);first=kinds[((run_id-1+cycle)*2)%len(kinds)];second=kinds[((run_id-1+cycle)*2+1)%len(kinds)]
        if episode==first_at:self.incident(run_id,first,cycle=cycle,background=bool(state['continuous']))
        if episode==burst_at:self.incident(run_id,second,cycle=cycle,background=bool(state['continuous']))
        if episode>=first_at+4:
            for kind in SCAMS:self.incident(run_id,kind,repeat=True,cycle=cycle)
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
            if step>=RUN_STEPS and not state['continuous']:self.lab.db.execute("UPDATE world_demo_state SET running=0,note='24-hour episode complete' WHERE id=1")
        self.checkpoint();return self.status()

    def demo_action(self,expected_run,report_id,action):
        """Viewer-authorized demo assumptions, scoped to the current synthetic scene.

        Never exposed as a model tool. Normal simulation keeps explicit review and
        activation. Failed models stay failed; the reviewed recipient watch is
        the honest, local fallback when a broader candidate cannot be activated.
        """
        if action not in ('investigate','answer','review','learn','activate','prove'):raise LabError('Unknown demo action.')
        with self.lab.lock:
            state=self.status()
            if type(expected_run) is not int or expected_run!=state['run_id'] or not state['guided'] or report_id!=state['focus_report_id']:
                raise LabError('This action belongs only to the current guided demo.',409)
            report=self.desk.detail(report_id);tx=report['transactions']
            if not tx or any(t['metadata'].get('source')!='world_demo' or not t['metadata'].get('guided_demo') for t in tx):
                raise LabError('Demo assumptions cannot be used for submitted customer reports.',403)
            prior=self.lab.db.execute('SELECT receipt FROM world_demo_actions WHERE run_id=? AND action=?',(expected_run,action)).fetchone()
            if prior:return {'demo':state,'report':report,'receipt':json.loads(prior[0]),'replayed':True}
            run=report['investigation']
            if action!='investigate' and ((run and run['status'] in ('running','stepping')) or (report.get('preparation') or {}).get('status')=='running'):raise LabError('The current check is still being recorded.',409)
            receipt={'actor':'simulated_analyst','assumption':True,'action':action,'report_id':report_id}
            intake=None
            if action=='investigate':
                if run:raise LabError('This case already has an investigation. Follow its saved receipts; no request was retried.',409)
                if (report.get('preparation') or {}).get('status')!='waiting':raise LabError('The case is not waiting for the demo investigation step.',409)
                if self.intake and self.intake.is_alive():raise LabError('An evidence handoff is already running.',409)
                identifier=self.lab.db.execute('SELECT id FROM world_incidents WHERE report_id=?',(report_id,)).fetchone()[0]
                self.desk.prepare(report_id,'running','queued','The viewer started the resolution agent. Preparing its case evidence.')
                intake=threading.Thread(target=self.prepare,args=(report_id,identifier,'gemini' if self.runner.agent.live_enabled() else 'fake'),daemon=True,name='demo-case-intake')
                self.intake=intake;receipt.update(actor='viewer',assumption=False,status='investigation_requested')
            elif action=='answer':
                if report['status']!='awaiting_customer':raise LabError('No customer reply is pending.',409)
                self.runner.reply(report_id=report_id,answer=SCAMS['phishing']['reply'],expected_revision=report['revision'])
                receipt['actor']='simulated_customer'
            elif action=='review':
                if report['status']!='resolved':
                    if not run and (report.get('preparation') or {}).get('status')=='waiting':
                        raise LabError('Start the resolution agent with Next before the demo review.',409)
                    # This scripted review is permitted only for the demonstrated
                    # impersonation evidence, never from a synthetic truth label.
                    observed=[t['metadata'].get('prevention_features',{}) for t in tx]
                    if not any(v.get('safe_account_request') and v.get('secrecy_request') for v in observed):
                        raise LabError('The demo review requires the recorded impersonation and secrecy signals.',409)
                    if not run:
                        run=self.desk.start(report_id)
                        for _ in range(5):run=self.desk.step(run['id'],run['step'])
                        receipt['fallback']='Local evidence review; no model investigation was completed.'
                    elif run['status'] in ('failed','budget_exhausted','interrupted'):
                        receipt['fallback']='Investigation stopped: '+run['context'].get('stop_reason','No further request was made.')
                        self.runner.agent.handoff(run['id']);run=self.desk.detail(report_id)['investigation']
                    if run['status']!='awaiting_review':raise LabError('Wait for the current investigation result.',409)
                    self.desk.review(report_id,run['id'],'confirmed_scam','request_recall',
                        'DEMO ASSUMPTION: the simulated risk analyst verified this synthetic transfer and its recorded impersonation request. No real customer decision.',
                        True,LESSON,QUESTION)
                receipt['review_id']=self.desk.detail(report_id)['reviews'][-1]['id']
                receipt['memory_id']=self.world.prevention.basis(report_id)['memory']['id']
            else:
                basis=self.world.prevention.basis(report_id)
                receipt['memory_id']=basis['memory']['id']
                job=self.world.prevention.for_report(report_id)
                if action=='learn':
                    if not job and not self.runner.agent.runtime()['live_circuit_open']:
                        try:job=self.runner.learn(report_id,'gemini' if self.runner.agent.live_enabled() else 'fake')
                        except LabError as exc:receipt['fallback']=str(exc)
                    elif not job:receipt['fallback']='The model circuit is paused. The approved recipient watch remains available; no model request was retried.'
                    receipt.update(actor='prevention',mode='candidate' if job else 'reviewed_recipient',job_id=job['id'] if job else None)
                elif action=='activate':
                    if not self.lab.db.execute("SELECT 1 FROM world_demo_actions WHERE run_id=? AND action='learn'",(expected_run,)).fetchone():raise LabError('Load the reviewed lesson first.',409)
                    rule=job.get('rule') if job else None
                    if job and job['status'] in ('ready','queued','running'):raise LabError('The prevention check is still running.',409)
                    if rule and rule['replay']['passed']:
                        self.world.prevention.activate(rule['id'],True);receipt.update(mode='behavioral_safeguard',rule_id=rule['id'])
                    else:receipt.update(mode='reviewed_recipient',fallback='The broader candidate is inactive. Only the analyst-approved recipient watch is used.')
                else:
                    if not self.lab.db.execute("SELECT 1 FROM world_demo_actions WHERE run_id=? AND action='activate'",(expected_run,)).fetchone():raise LabError('Confirm the demo protection step first.',409)
                    self.prove(expected_run,allow_watch=True)
                    receipt.update(actor='payment_gateway',blocked=True,legitimate_payment_passed=True)
            with self.lab.db:self.lab.db.execute('INSERT INTO world_demo_actions VALUES(?,?,?,?,?)',(expected_run,report_id,action,encoded(receipt),now()))
            self.checkpoint()
            if intake:intake.start()
            return {'demo':self.status(),'report':self.desk.detail(report_id),'receipt':receipt,'replayed':False}

    def prove(self,expected_run,allow_watch=False):
        with self.lab.lock:
            state=self.status()
            if type(expected_run) is not int or state['run_id']!=expected_run:raise LabError('The demo changed. Refresh its state.',409)
            if state['phase']=='protected':return state
            if state['phase']!='ready':
                if not allow_watch:raise LabError('Activate the reviewed prevention safeguard before testing it.',409)
                self.world.prevention.basis(state['focus_report_id'])
            self.incident(expected_run,'phishing',repeat=True)
            suffix='variant' if any(r['family']=='phishing' for r in self.world.prevention.active()) else 'repeat'
            if suffix=='repeat' and not allow_watch:raise LabError('The reviewed behavioral safeguard is no longer active.',409)
            held=self.lab.db.execute("SELECT id FROM world_incidents WHERE id=? AND status='blocked'",('world-scam-'+str(expected_run)+'-phishing-'+suffix,)).fetchone()
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
            while not self.closed:
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
        if self.intake:self.intake.join()
        with self.lab.lock,self.lab.db:self.lab.db.execute("UPDATE world_demo_state SET running=0,note='Paused' WHERE running=1")
        try:self.checkpoint()
        except LabError:pass
