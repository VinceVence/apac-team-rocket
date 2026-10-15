"""The local financial lab. Six durable tables; no model has a database handle."""
import datetime as dt
import hashlib
import json
import random
import sqlite3
import threading
import uuid
from pathlib import Path

AS_OF = '2026-10-06'
TABLES = ('customers', 'accounts', 'financial_events', 'ledger_entries', 'cases', 'agent_runs')


def resident_name(index):
    """Numbered synthetic residents; never rewrite saved case evidence."""
    return 'Resident '+str(index)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


class LabError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


class Lab:
    def __init__(self, path, seed_history=True):
        self.lock = threading.RLock()
        self.clock_day = AS_OF
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.seed_history=seed_history
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE name='simulation_state'").fetchone():
            if 'history_seeded' in {r['name'] for r in self.db.execute('PRAGMA table_info(simulation_state)')}:
                self.seed_history=bool(self.db.execute('SELECT history_seeded FROM simulation_state WHERE id=1').fetchone()[0])
        self.db.executescript('''
        PRAGMA foreign_keys=ON;
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS customers(
          id TEXT PRIMARY KEY, name TEXT NOT NULL, weekly_income_minor INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS accounts(
          id TEXT PRIMARY KEY, customer_id TEXT REFERENCES customers(id), label TEXT NOT NULL,
          kind TEXT NOT NULL, opening_minor INTEGER NOT NULL CHECK(opening_minor>=0),
          balance_minor INTEGER NOT NULL CHECK(balance_minor>=0), version INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS financial_events(
          id TEXT PRIMARY KEY, customer_id TEXT REFERENCES customers(id), kind TEXT NOT NULL,
          amount_minor INTEGER NOT NULL CHECK(amount_minor>=0), occurred_at TEXT NOT NULL,
          status TEXT NOT NULL, from_account TEXT REFERENCES accounts(id),
          to_account TEXT REFERENCES accounts(id), metadata TEXT NOT NULL DEFAULT '{}');
        CREATE TABLE IF NOT EXISTS ledger_entries(
          id INTEGER PRIMARY KEY, event_id TEXT NOT NULL REFERENCES financial_events(id),
          account_id TEXT NOT NULL REFERENCES accounts(id), delta_minor INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS cases(
          id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('fraud','cashflow')),
          customer_id TEXT NOT NULL REFERENCES customers(id), title TEXT NOT NULL,
          description TEXT NOT NULL, event_ids TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
          status TEXT NOT NULL DEFAULT 'open', applied_run_id TEXT, applied_at TEXT);
        CREATE TABLE IF NOT EXISTS agent_runs(
          id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id), evidence_hash TEXT NOT NULL,
          case_version INTEGER NOT NULL, prompt_version TEXT NOT NULL, provider TEXT NOT NULL,
          model TEXT NOT NULL, status TEXT NOT NULL, evidence TEXT NOT NULL,
          decision TEXT, error TEXT, input_tokens INTEGER NOT NULL DEFAULT 0,
          output_tokens INTEGER NOT NULL DEFAULT 0, reserved_usd REAL NOT NULL DEFAULT 0,
          cost_usd REAL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS events_customer_time ON financial_events(customer_id,occurred_at);
        CREATE UNIQUE INDEX IF NOT EXISTS active_run ON agent_runs(case_id,evidence_hash,provider,model,prompt_version)
          WHERE status='running';
        ''')
        with self.db:
            # A request lost during process shutdown may have reached the provider. Keep its reservation.
            self.db.execute("UPDATE agent_runs SET status='uncertain',error='Server restarted during this request; its cost reservation was retained.' WHERE status='running'")
        if not self.db.execute('SELECT 1 FROM customers LIMIT 1').fetchone():
            self.seed()

    def rows(self, query, args=()):
        return [dict(row) for row in self.db.execute(query, args)]

    def event(self, event_id, customer, kind, amount, day, status='settled', source=None, target=None, metadata=None):
        self.db.execute('INSERT INTO financial_events VALUES(?,?,?,?,?,?,?,?,?)',
                        (event_id, customer, kind, amount, day, status, source, target, encoded(metadata or {})))

    def post(self, event_id, customer, kind, amount, day, source, target, metadata=None):
        return self.post_legs(event_id,customer,kind,amount,day,[(source,target,amount)],metadata)

    def post_legs(self, event_id, customer, kind, amount, day, legs, metadata=None):
        deltas={}
        if type(amount) is not int or amount<=0 or not legs:raise LabError('Invalid posting.')
        for source,target,value in legs:
            if type(value) is not int or value<=0 or source==target:raise LabError('Invalid posting.')
            deltas[source]=deltas.get(source,0)-value;deltas[target]=deltas.get(target,0)+value
        for account,delta in deltas.items():
            row=self.db.execute('SELECT balance_minor FROM accounts WHERE id=?',(account,)).fetchone()
            if not row or row[0]+delta<0:raise LabError('Insufficient available funds. No money moved.',409)
        self.event(event_id,customer,kind,amount,day,source=legs[0][0],target=legs[0][1],metadata=metadata)
        for account, delta in deltas.items():
            self.db.execute('UPDATE accounts SET balance_minor=balance_minor+?,version=version+1 WHERE id=?', (delta, account))
            self.db.execute('INSERT INTO ledger_entries(event_id,account_id,delta_minor) VALUES(?,?,?)', (event_id, account, delta))

    def seed(self):
        rng = random.Random(42)
        with self.lock, self.db:
            def account(identifier, customer, label, kind, amount):
                self.db.execute('INSERT INTO accounts(id,customer_id,label,kind,opening_minor,balance_minor) VALUES(?,?,?,?,?,?)',
                                (identifier, customer, label, kind, amount, amount))
            account('treasury', None, 'Town treasury', 'treasury', 100000000)
            for i, name in enumerate(('Kape café','Sari-sari','Mercado'), 1):
                account('m%d' % i, None, name, 'merchant', 2000000)
            for i in range(1,25):
                name=resident_name(i)
                cid = 'C%03d' % i
                self.db.execute('INSERT INTO customers VALUES(?,?,?)', (cid, resident_name(i), 350000+i*9000))
                account(cid+':wallet', cid, name+' · wallet', 'wallet', 1500000)
                account(cid+':savings', cid, name+' · savings', 'savings', 200000)
                if not self.seed_history:continue
                for day_index in range(28):
                    day = (dt.date.fromisoformat(AS_OF)-dt.timedelta(days=28-day_index)).isoformat()
                    if day_index % 7 == 0:
                        self.post('payroll-%s-%s' % (cid, day), cid, 'payroll', 350000+i*9000, day+'T08:00:00Z', 'treasury', cid+':wallet')
                    for j in range(2):
                        merchant = 'm%d' % rng.randint(1, 3)
                        self.post('purchase-%s-%s-%d' % (cid, day, j), cid, 'payment', rng.randint(40,180)*100,
                                  day+'T%02d:00:00Z'%(10+j*8), cid+':wallet', merchant,
                                  {'category':'essential' if j == 0 else 'discretionary', 'device_id':'device-'+cid,
                                   'rail':['QR','Card','Wallet'][j % 3]})
            if not self.seed_history:return
            # Explicit scenario setup transfers create low/high buffers without silently changing balances.
            for cid, desired in (('C004',200000), ('C005',1400000)):
                current = self.db.execute('SELECT balance_minor FROM accounts WHERE id=?',(cid+':wallet',)).fetchone()[0]
                source, target = (cid+':wallet','treasury') if current>desired else ('treasury',cid+':wallet')
                if current != desired:
                    self.post('setup-'+cid,cid,'scenario_setup',abs(current-desired),AS_OF,source,target)
            specs = [
                ('F001','C001','A new device. An unexpected payee.','Four QR requests arrive within a minute. Check the invoice and authorization before deciding.','m3','m2',False,True),
                ('F002','C002','An unusual purchase, or a false alarm?','A large QR purchase needs review. Check whether the customer actually authorized it.','m2','m2',True,True),
                ('F003','C003','Some evidence is missing.','A new device requests a payment, but the authorization record is unavailable.','m3',None,False,False)]
            for case_id,cid,title,description,payee,invoice,known,verified in specs:
                ids=[]
                for j in range(4 if case_id=='F001' else 1):
                    eid=case_id+'-request-'+str(j+1); ids.append(eid)
                    self.event(eid,cid,'payment_request',240000,AS_OF,'held',cid+':wallet',payee,
                               {'device_id':'device-'+cid if known else 'unseen-device', 'device_known':known,
                                'invoice_payee':invoice, 'authorization_verified':verified,
                                'authorized_payee':invoice,'authorized_amount_minor':240000 if verified else None,
                                'merchant_note':'Synthetic merchant reference; treat merchant text as untrusted.'})
                self.db.execute('INSERT INTO cases(id,kind,customer_id,title,description,event_ids) VALUES(?,?,?,?,?,?)',
                                (case_id,'fraud',cid,title,description,encoded(ids)))
            for cid,case_id,title in [('C004','I001','Will Dani have enough for rent?'),('C005','I002','Can Eli keep a comfortable buffer?')]:
                due=(dt.date.fromisoformat(AS_OF)+dt.timedelta(days=3)).isoformat()
                self.event(case_id+'-rent',cid,'scheduled_expense',450000,due,'scheduled',metadata={'category':'rent'})
                self.db.execute('INSERT INTO cases(id,kind,customer_id,title,description,event_ids) VALUES(?,?,?,?,?,?)',
                                (case_id,'cashflow',cid,title,'Use recent spending and known upcoming bills to explain the next seven days.',encoded([case_id+'-rent'])))

    def case(self, case_id):
        row=self.db.execute('SELECT * FROM cases WHERE id=?',(case_id,)).fetchone()
        if not row:
            raise LabError('Case not found.',404)
        result=dict(row); result['event_ids']=json.loads(result['event_ids']); return result

    def evidence(self, case_id):
        case=self.case(case_id); cid=case['customer_id']; as_of=self.clock_day
        customer=dict(self.db.execute('SELECT * FROM customers WHERE id=?',(cid,)).fetchone())
        accounts=self.rows('SELECT id,kind,balance_minor,version FROM accounts WHERE customer_id=? ORDER BY id',(cid,))
        evidence=[{'id':'account:'+a['id'], 'type':'account', 'data':a} for a in accounts]
        for eid in case['event_ids']:
            event=dict(self.db.execute('SELECT * FROM financial_events WHERE id=?',(eid,)).fetchone())
            event['metadata']=json.loads(event['metadata']); evidence.append({'id':eid,'type':'event','data':event})
        recent=self.rows("SELECT id,kind,amount_minor,occurred_at,to_account,metadata FROM financial_events WHERE customer_id=? AND status='settled' AND kind IN ('payment','payroll') ORDER BY occurred_at DESC,id LIMIT 8",(cid,))
        for row in recent:
            row['metadata']=json.loads(row['metadata']); evidence.append({'id':row['id'],'type':'history','data':row})
        if case['kind']=='cashflow':
            start=(dt.date.fromisoformat(as_of)-dt.timedelta(days=14)).isoformat()
            end=(dt.date.fromisoformat(as_of)+dt.timedelta(days=7)).isoformat()
            expenses=self.rows("SELECT id,amount_minor FROM financial_events WHERE customer_id=? AND kind='payment' AND status='settled' AND occurred_at>=? AND occurred_at<?",(cid,start,as_of))
            future=self.rows("""SELECT e.id,e.kind,e.amount_minor FROM financial_events e WHERE e.customer_id=? AND e.status='scheduled'
              AND e.occurred_at<=? AND ((e.kind='scheduled_income' AND e.occurred_at>=?) OR
              (e.kind='scheduled_expense' AND NOT EXISTS(SELECT 1 FROM financial_events p WHERE p.kind='bill_payment' AND json_extract(p.metadata,'$.bill_id')=e.id)))""",(cid,end,as_of))
            wallet=next(a['balance_minor'] for a in accounts if a['kind']=='wallet')
            recent_spend=sum(e['amount_minor'] for e in expenses)
            expected=(recent_spend+1)//2
            bills=sum(e['amount_minor'] for e in future if e['kind']=='scheduled_expense')
            income=sum(e['amount_minor'] for e in future if e['kind']=='scheduled_income')
            projected=wallet+income-bills-expected
            evidence.append({'id':'forecast:'+cid,'type':'calculation','data':{
                'wallet_minor':wallet,'scheduled_income_minor':income,'bills_minor':bills,
                'recent_14_day_spend_minor':recent_spend,'estimated_7_day_spend_minor':expected,
                'projected_wallet_minor':projected,'shortfall_minor':max(0,-projected),
                'method':'Next 7 days: wallet + scheduled income - scheduled bills - half of the previous 14 days of settled purchases. Spending is an estimate; savings are excluded.',
                'source_ids':[e['id'] for e in expenses+future]}})
        return {'case_id':case_id,'case_version':case['version'],'kind':case['kind'],
                'as_of':as_of,'customer':customer,'evidence':evidence}

    def fingerprint(self, packet):
        return hashlib.sha256(encoded(packet).encode()).hexdigest()

    @staticmethod
    def permitted(packet):
        if packet['kind']=='cashflow':
            return {'insight'}
        requests=[e['data'] for e in packet['evidence'] if e['type']=='event' and e['data']['kind']=='payment_request']
        if not requests:
            return {'review'}
        mismatch=all(r['metadata'].get('authorization_verified') and r['metadata'].get('invoice_payee')
                     and r['to_account']!=r['metadata']['invoice_payee'] for r in requests)
        authorized=all(r['metadata'].get('authorization_verified') and r['metadata'].get('device_known')
                       and r['metadata'].get('authorized_payee')==r['to_account']
                       and r['metadata'].get('authorized_amount_minor')==r['amount_minor'] for r in requests)
        return {'review','reject'} if mismatch else {'review','release'} if authorized else {'review'}

    def validate(self, packet, decision):
        if not isinstance(decision,dict) or set(decision)!={'action','summary','evidence_ids','uncertainties'}:
            raise LabError('The response did not match the decision schema.',422)
        if decision['action'] not in self.permitted(packet):
            raise LabError('The proposed action is not supported by the policy checks.',422)
        if not isinstance(decision['summary'],str) or not 10<=len(decision['summary'])<=1400:
            raise LabError('The response needs a bounded explanation.',422)
        refs=decision['evidence_ids']; allowed={e['id'] for e in packet['evidence']}
        if not isinstance(refs,list) or not 1<=len(refs)<=12 or any(not isinstance(x,str) or x not in allowed for x in refs):
            raise LabError('The response cited missing or invalid evidence.',422)
        required={e['id'] for e in packet['evidence'] if e['type']==('calculation' if packet['kind']=='cashflow' else 'event')}
        if not required.issubset(refs):
            raise LabError('The response must cite the decisive records.',422)
        if not isinstance(decision['uncertainties'],list) or len(decision['uncertainties'])>5 or any(not isinstance(x,str) or len(x)>250 for x in decision['uncertainties']):
            raise LabError('Invalid uncertainty list.',422)
        return decision

    def baseline(self, packet):
        options=self.permitted(packet); refs=[e['id'] for e in packet['evidence'] if e['type'] in ('event','calculation')]
        if 'reject' in options:
            action,summary='reject','The requested payee differs from the verified invoice payee. Reject these requests and keep the rest of the account usable.'
        elif 'release' in options:
            action,summary='release','The known device, verified authorization, payee and amount agree. Release this payment if the wallet still has enough funds.'
        elif 'insight' in options:
            forecast=next(e['data'] for e in packet['evidence'] if e['type']=='calculation')
            action='insight'
            summary='The projected wallet falls below zero. Protect the rent money and review discretionary purchases before the due date.' if forecast['shortfall_minor'] else 'The projected wallet covers known bills and estimated spending. Preserve the bill buffer before making an optional savings transfer.'
        else:
            action,summary='review','Authorization is incomplete. Keep the requests on hold and request confirmation; a new device alone is not enough to reject a payment.'
        return self.validate(packet,{'action':action,'summary':summary,'evidence_ids':refs,
                                     'uncertainties':['Future spending is estimated; only scheduled income is counted.'] if action=='insight' else ['Authorization unavailable.'] if action=='review' else []})

    def apply_decision(self, case_id, run_id):
        with self.lock, self.db:
            return self._apply_decision(case_id, run_id)

    def _apply_decision(self, case_id, run_id):
        case=self.case(case_id)
        if case['applied_run_id']:
            if case['applied_run_id']!=run_id: raise LabError('This case already has an applied decision.',409)
            return {'status':case['status'],'replayed':True}
        row=self.db.execute("SELECT * FROM agent_runs WHERE id=? AND case_id=? AND status='completed'",(run_id,case_id)).fetchone()
        if not row: raise LabError('Choose a completed investigation for this case.',409)
        packet=self.evidence(case_id)
        if self.fingerprint(packet)!=row['evidence_hash']: raise LabError('The evidence changed. Run a fresh investigation.',409)
        decision=self.validate(packet,json.loads(row['decision'])); action=decision['action']
        if action in ('release','reject'):
            for eid in case['event_ids']:
                event=dict(self.db.execute('SELECT * FROM financial_events WHERE id=?',(eid,)).fetchone())
                metadata={'request_id':eid,'run_id':run_id,'action':action}
                if action=='release':
                    fee=json.loads(event['metadata']).get('fee_minor',0)
                    legs=[(event['from_account'],event['to_account'],event['amount_minor'])]
                    if fee:legs.append((event['from_account'],'payment-fees',fee));metadata['fee_minor']=fee
                    self.post_legs('resolution-'+eid,case['customer_id'],'payment',event['amount_minor'],self.clock_day,legs,metadata)
                else:
                    self.event('resolution-'+eid,case['customer_id'],'payment_rejected',event['amount_minor'],self.clock_day,'rejected',metadata=metadata)
        self.db.execute('UPDATE cases SET status=?,applied_run_id=?,applied_at=?,version=version+1 WHERE id=?',
                        ('review' if action=='review' else 'resolved',run_id,now(),case_id))
        return {'status':'review' if action=='review' else 'resolved','replayed':False}


    def integrity(self):
        total=self.db.execute('SELECT sum(balance_minor)=sum(opening_minor) FROM accounts').fetchone()[0]
        bad_journal=self.db.execute('SELECT event_id FROM ledger_entries GROUP BY event_id HAVING sum(delta_minor)!=0 LIMIT 1').fetchone()
        bad_account=self.db.execute('SELECT a.id FROM accounts a LEFT JOIN ledger_entries l ON a.id=l.account_id GROUP BY a.id HAVING a.balance_minor!=a.opening_minor+coalesce(sum(l.delta_minor),0) LIMIT 1').fetchone()
        return bool(total and not bad_journal and not bad_account)

    def snapshot(self):
        with self.lock:
            cases=self.rows('SELECT * FROM cases ORDER BY id')
            for case in cases: case['event_ids']=json.loads(case['event_ids'])
            runs=self.rows('SELECT id,case_id,evidence_hash,provider,model,status,decision,error,input_tokens,output_tokens,cost_usd,reserved_usd,created_at FROM agent_runs ORDER BY created_at DESC LIMIT 30')
            for run in runs: run['decision']=json.loads(run['decision']) if run['decision'] else None
            return {'as_of':self.clock_day,'customers':self.rows('SELECT * FROM customers ORDER BY id'),'cases':cases,'runs':runs,
                    'tables':{table:self.db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in TABLES},
                    'ledger_balanced':self.integrity(),
                    'events':self.rows('SELECT id,customer_id,kind,amount_minor,status,occurred_at FROM financial_events ORDER BY rowid DESC LIMIT 20')}
