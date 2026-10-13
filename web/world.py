"""Persistent hourly town events and a scoped, simulated payment-service gateway."""
import datetime as dt
import json
import random
import hashlib
from lab import AS_OF, LabError, encoded, now
from settings import MAX_CUSTOMERS


class World:
    def __init__(self, lab):
        self.lab=lab;self.macro=None;self.customer_data=None;self.fraud_desk=None;self.prevention=None
        lab.db.executescript('''
        CREATE TABLE IF NOT EXISTS simulation_state(
          id INTEGER PRIMARY KEY CHECK(id=1), tick INTEGER NOT NULL DEFAULT 0,
          last_alert INTEGER NOT NULL DEFAULT -24, shock_until INTEGER NOT NULL DEFAULT 0);
        INSERT OR IGNORE INTO simulation_state(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS service_actions(
          id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), run_id TEXT NOT NULL REFERENCES agent_runs(id),
          customer_id TEXT NOT NULL, device_id TEXT NOT NULL, service TEXT NOT NULL,
          action TEXT NOT NULL, created_at TEXT NOT NULL,
          UNIQUE(customer_id,device_id,action));
        ''')
        lab.clock_day=self.day(self.state()['tick'])

    def state(self):
        return dict(self.lab.db.execute('SELECT * FROM simulation_state WHERE id=1').fetchone())

    @staticmethod
    def day(tick):
        return (dt.date.fromisoformat(AS_OF)+dt.timedelta(days=(tick+9)//24)).isoformat()

    def status(self):
        result=self.state(); result['day']=self.day(result['tick']);result['hour']=(result['tick']+9)%24
        result['service_actions']=self.lab.rows('SELECT * FROM service_actions ORDER BY rowid DESC LIMIT 8')
        result['open_cases']=self.lab.db.execute("SELECT count(*) FROM cases WHERE status='open' AND id LIKE 'W%'").fetchone()[0]
        return result

    def payment_flags(self,cid,merchant,amount,metadata,stamp):
        flags=self.fraud_desk.screen(cid,merchant) if self.fraud_desk else []
        values={}
        if self.prevention:
            values,learned=self.prevention.assess(cid,merchant,amount,metadata,stamp);flags+=learned
        return values,flags

    def payment(self, eid, cid, merchant, amount, device, metadata=None, occurred_at=None):
        stamp=occurred_at or self.lab.clock_day+'T%02d:00:%02dZ'%((self.state()['tick']+9)%24,int(hashlib.sha256(eid.encode()).hexdigest()[:8],16)%60)
        blocked=self.lab.db.execute("SELECT 1 FROM service_actions WHERE customer_id=? AND device_id=? AND action='block_device'",(cid,device)).fetchone()
        meta={'device_id':device,'category':'discretionary',**(metadata or {})}
        values,flags=self.payment_flags(cid,merchant,amount,meta,stamp)
        meta.pop('review_flags',None)
        if self.prevention:
            from prevention import FEATURE_SCHEMA_VERSION
            meta['prevention_features']=values;meta['prevention_schema_version']=FEATURE_SCHEMA_VERSION
        if flags:meta['review_flags']=flags
        if meta.get('review_flags'):
            blocked=True
            meta['prevention_tool']='payments.hold_transfer'
            learned=[f for f in flags if f.get('rule_id')]
            meta['prevention_action']='verify' if learned else 'hold'
            meta['prevention_rule_ids']=[f['rule_id'] for f in learned]
            meta['prevention_reason']='Approved signals matched before debit. Verify the request independently.' if learned else 'Exact recipient matched an analyst-approved scam. Simulated transfer held for review.'
        if blocked:
            self.lab.event(eid,cid,'payment_blocked',amount,stamp,'blocked',cid+':wallet',merchant,meta)
            return 'blocked'
        try:
            if self.macro and merchant in ('m1','m2','m3'):self.macro.purchase(eid,cid,merchant,amount,meta,occurred_at=stamp)
            else:self.lab.post(eid,cid,'payment',amount,stamp,cid+':wallet',merchant,meta)
            return 'settled'
        except LabError:
            self.lab.event(eid,cid,'payment_declined',amount,stamp,'declined',cid+':wallet',merchant,meta)
            return 'declined'

    def fraud_case(self, tick, rng, forced=None):
        cid='C%03d' % rng.randint(1,24); case_id='WF%06d' % tick;device='unseen-'+case_id
        flavor=forced or rng.choice(('mismatch','mismatch','authorized','unknown'))
        ids=[]
        for j in range(4):
            eid=case_id+'-'+str(j+1);ids.append(eid)
            self.lab.event(eid,cid,'payment_request',240000,self.lab.clock_day+'T%02d:00:%02dZ' % ((tick+9)%24,j*10),
                           'held',cid+':wallet','m3',{'device_id':device,'device_known':flavor=='authorized',
                            'authorization_verified':flavor!='unknown','invoice_payee':'m2' if flavor=='mismatch' else 'm3' if flavor=='authorized' else None,
                            'authorized_payee':'m3' if flavor=='authorized' else 'm2' if flavor=='mismatch' else None,
                            'authorized_amount_minor':240000 if flavor!='unknown' else None,
                            'fee_minor':(240000*self.macro.policy()['fee_bps']+5000)//10000 if self.macro else 0})
        self.lab.db.execute('INSERT INTO cases(id,kind,customer_id,title,description,event_ids) VALUES(?,?,?,?,?,?)',
                            (case_id,'fraud',cid,'A QR burst needs a closer look.','Four requests in 30 seconds triggered the router. The investigator must check the authorization and payee records.',encoded(ids)))
        return case_id

    def daily_cashflows(self, tick, rng):
        customers=self.lab.rows('SELECT * FROM customers ORDER BY id LIMIT ?', (MAX_CUSTOMERS,))
        profiles=self.customer_data.profiles() if self.customer_data else {}
        for p in customers:
            cid=p['id'];wallet=cid+':wallet';day=self.lab.clock_day
            active=not self.customer_data or self.customer_data.active(cid,day)
            if ((tick+9)//24)%7==0:
                amount=p['weekly_income_minor']//(2 if tick<self.state()['shock_until'] else 1)
                treasury='treasury' if int(cid[1:])<=24 else 'cohort-treasury'
                if self.lab.db.execute('SELECT balance_minor FROM accounts WHERE id=?',(treasury,)).fetchone()[0]>=amount:
                    self.lab.post('wage-%s-%d'%(cid,tick),cid,'payroll',amount,day,treasury,wallet)
            balance=self.lab.db.execute('SELECT balance_minor FROM accounts WHERE id=?',(wallet,)).fetchone()[0]
            if balance>=15000 and active:
                if self.macro:self.payment('essentials-%s-%d'%(cid,tick),cid,'m2',15000,'device-'+cid,{'category':'essential'})
                else:self.lab.post('essentials-%s-%d'%(cid,tick),cid,'payment',15000,day,wallet,'m2',{'category':'essential','device_id':'device-'+cid})
            savings_chance=min(.6,.10+self.macro.policy()['loan_bps']/10000) if self.macro else .2
            if cid in profiles:savings_chance=min(.6,.04+.28*(profiles[cid]['goal']=='savings')+savings_chance*.3)
            if balance>900000 and rng.random()<savings_chance:
                self.lab.post('save-%s-%d'%(cid,tick),cid,'savings_deposit',25000,day,wallet,cid+':savings')
            if active and int(cid[1:])>24 and rng.random()<.55:
                self.payment('cohort-%s-%d'%(cid,tick),cid,'m1',rng.randint(40,160)*100,'device-'+cid)
        # Existing bills settle once; failures are retained for the analyst rather than repeated each hour.
        due=self.lab.rows("SELECT e.* FROM financial_events e WHERE e.kind='scheduled_expense' AND e.status='scheduled' AND e.occurred_at<=? AND NOT EXISTS(SELECT 1 FROM financial_events p WHERE p.kind='bill_payment' AND json_extract(p.metadata,'$.bill_id')=e.id)",(self.lab.clock_day,))
        for event in due:
            cid=event['customer_id'];amount=event['amount_minor']
            try:self.lab.post('paid-'+event['id'],cid,'bill_payment',amount,self.lab.clock_day,cid+':wallet','m2',{'bill_id':event['id']})
            except LabError:self.lab.event('missed-'+event['id']+'-'+self.lab.clock_day,cid,'bill_missed',amount,self.lab.clock_day,'declined',metadata={'bill_id':event['id']})

    def advance(self, expected_tick, activity=2, scenario='none'):
        if type(expected_tick) is not int or type(activity) is not int or activity not in range(1,5) or scenario not in ('none','fraud','income','demand','supply'):
            raise LabError('Invalid simulation controls.')
        with self.lab.lock,self.lab.db:
            current=self.state()
            if expected_tick!=current['tick']:
                return {'replayed':True,'tick':current['tick'],'motions':[],'alerts':[]}
            tick=current['tick']+1;day=self.day(tick);rng=random.Random(42+tick*761)
            previous_day=self.lab.clock_day;self.lab.clock_day=day
            self.lab.db.execute('UPDATE simulation_state SET tick=? WHERE id=1',(tick,))
            if previous_day!=day:
                self.daily_cashflows(tick,rng)
                if self.macro:self.macro.daily(tick)
            motions=[];alerts=[]
            profiles=self.customer_data.profiles() if self.customer_data else {}
            candidates=[cid for cid in sorted(profiles)[:MAX_CUSTOMERS] if self.customer_data.active(cid,day)] if profiles else []
            purchases=max(1,round(activity*self.macro.demand_factor(tick))) if self.macro else activity
            for i in range(purchases):
                cid='C%03d'%rng.randint(1,24);merchant='m%d'%rng.randint(1,3);amount=rng.randint(40,280)*100
                if candidates:
                    cid=rng.choices(candidates,weights=[profiles[c]['activity_rate'] for c in candidates])[0]
                    merchant=rng.choices(['m1','m2','m3'],weights=profiles[cid]['merchant_weights'])[0]
                    amount=max(100,round(profiles[cid]['typical_spend_minor']*rng.uniform(.5,1.5)/100)*100)
                if self.macro and rng.random()<max(.03,.24-self.macro.policy()['loan_bps']/10000):
                    try:self.macro._loan(cid,200000,'auto-loan-%s-%d'%(cid,tick))
                    except LabError:pass
                rail=profiles[cid]['preferred_rail'] if cid in profiles and rng.random()<.8 else rng.choice(('QR','Card','Wallet'))
                outcome=self.payment('world-%d-%d'%(tick,i),cid,merchant,amount,'device-'+cid,{'rail':rail})
                if self.macro and outcome=='settled':amount=self.lab.db.execute('SELECT amount_minor FROM financial_events WHERE id=?',('world-%d-%d'%(tick,i),)).fetchone()[0]
                motions.append({'customer_id':cid,'merchant':merchant,'amount_minor':amount,'status':outcome})
            # A blocked device retries periodically. The gateway denies it before settlement or another agent call.
            if tick%5==0:
                block=self.lab.db.execute('SELECT * FROM service_actions ORDER BY rowid DESC LIMIT 1').fetchone()
                if block:
                    outcome=self.payment('retry-%d'%tick,block['customer_id'],'m3',240000,block['device_id'])
                    motions.append({'customer_id':block['customer_id'],'merchant':'m3','amount_minor':240000,'status':outcome})
            if scenario=='income':
                self.lab.db.execute('UPDATE simulation_state SET shock_until=? WHERE id=1',(tick+14*24,))
                case_id='WI%06d'%tick
                self.lab.event(case_id+'-shock','C004','income_shock',0,day,'scheduled',metadata={'duration_days':14,'wage_multiplier':.5})
                bill_id=case_id+'-bill';self.lab.event(bill_id,'C004','scheduled_expense',180000,(dt.date.fromisoformat(day)+dt.timedelta(days=2)).isoformat(),'scheduled',metadata={'category':'essentials'})
                self.lab.db.execute('INSERT INTO cases(id,kind,customer_id,title,description,event_ids) VALUES(?,?,?,?,?,?)',
                                    (case_id,'cashflow','C004','Income slowed. Bills did not.','The cash-flow specialist checks the recorded wallet, obligations and spending after an income shock.',encoded([bill_id])))
                alerts.append(case_id)
            elif scenario=='fraud' or (not self.customer_data and tick-current['last_alert']>=18 and rng.random()<.14):
                alerts.append(self.fraud_case(tick,rng,'mismatch' if scenario=='fraud' else None));self.lab.db.execute('UPDATE simulation_state SET last_alert=? WHERE id=1',(tick,))
            if self.macro:self.macro.on_tick(tick,scenario)
            if self.customer_data and previous_day!=day:self.customer_data.advance_day(day)
            return {'replayed':False,'tick':tick,'motions':motions,'alerts':alerts,'day_closed':previous_day!=day,
                    'macro_due':self.macro.due() if self.macro else False}

    def block_device(self, case_id, run_id):
        # Real service boundary: caller supplies only a reviewed case/run, never an arbitrary customer/device.
        with self.lab.lock,self.lab.db:
            case=self.lab.case(case_id)
            run=self.lab.db.execute("SELECT * FROM agent_runs WHERE id=? AND case_id=? AND status='completed'",(run_id,case_id)).fetchone()
            if not run or json.loads(run['decision'])['action']!='reject':
                raise LabError('A validated rejection is required to block this device.',409)
            if case['applied_run_id'] and case['applied_run_id']!=run_id:raise LabError('A different decision was already applied.',409)
            packet=json.loads(run['evidence']);self.lab.validate(packet,json.loads(run['decision']))
            requests=[e['data'] for e in packet['evidence'] if e['type']=='event']
            devices={r['metadata'].get('device_id') for r in requests}
            if len(devices)!=1 or None in devices:raise LabError('The case must identify one device.',409)
            device=devices.pop()
            existing=self.lab.db.execute("SELECT id FROM service_actions WHERE customer_id=? AND device_id=? AND action='block_device'",(case['customer_id'],device)).fetchone()
            if existing:return {'replayed':True,'service':'payments.block_device','receipt_id':existing[0],'device_id':device}
            self.lab._apply_decision(case_id,run_id)
            receipt='service-'+case_id
            self.lab.db.execute('INSERT INTO service_actions VALUES(?,?,?,?,?,?,?,?)',
                                (receipt,case_id,run_id,case['customer_id'],device,'payments','block_device',now()))
            self.lab.event(receipt,case['customer_id'],'device_blocked',0,self.lab.clock_day,'blocked',metadata={'service':'payments.block_device','device_id':device,'run_id':run_id})
            return {'replayed':False,'service':'payments.block_device','receipt_id':receipt,'device_id':device}
