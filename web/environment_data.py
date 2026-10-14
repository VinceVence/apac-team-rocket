"""AE dictionary projection of the real simulation ledger; no cloud/model calls.

Raw evaluation labels exist only in operator exports. Agent-facing projections
exclude them and heuristic scores. Amounts remain exact decimal strings.
"""
import datetime as dt
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from lab import AS_OF, LabError, encoded
from settings import MAX_CUSTOMERS
from cloud_data import MAX_EXPORT_BYTES, MAX_EXPORT_ROWS

CONTRACT_VERSION='gab-f03a384-v1'
COLUMNS={
 'customers':'customer_id:STRING! full_name:STRING kyc_status:STRING creation_date:TIMESTAMP risk_tier:STRING',
 'wallets':'wallet_id:STRING! customer_id:STRING! wallet_type:STRING current_balance:NUMERIC daily_spent:NUMERIC wallet_status:STRING',
 'devices':'device_id:STRING! customer_id:STRING! device_model:STRING ip_address:STRING trust_score:FLOAT',
 'wallet_transactions':'transaction_id:STRING! sender_wallet_id:STRING! receiver_wallet_id:STRING! amount:NUMERIC! timestamp:TIMESTAMP! transaction_type:STRING channel:STRING device_id:STRING risk_score:FLOAT risk_factors:STRING is_fraud:BOOLEAN! scam_type:STRING',
 'scam_knowledge':'scam_id:STRING! scam_category:STRING! scam_name:STRING! typology_description:STRING key_red_flags:STRING* base_impact:INTEGER',
 'scam_memory':'case_id:STRING! incident_timestamp:TIMESTAMP! scam_category:STRING victim_id:STRING fraudster_id:STRING evidence_summary:STRING investigation_outcome:STRING approved_by_analyst:STRING learned_pattern_rule:STRING',
}
PAYMENT_TYPES=('P2P_TRANSFER','MERCHANT_QR','CASH_OUT_AGENT','CASH_IN_AGENT')
DEVICE_MODELS=('iPhone 14','iPhone 15','Samsung S23','Xiaomi Redmi','Pixel 8')
PRIVATE_FIELDS=frozenset(('is_fraud','scam_type','risk_score','risk_factors'))
TYPOLOGIES=(
 ('PHISHING_APP','Authorized Push Payment','Safe-account impersonation','A victim is pressured to approve a transfer to a supposed safe account.',('Safe-account request','Secrecy','Unverified caller'),45),
 ('ATO_DRAIN','Account Takeover','Account takeover','An unauthorized actor accesses a wallet and drains funds.',('Unrecognized device','Unverified authorization','Rapid transfers'),50),
 ('VISHING','Social Engineering','Voice impersonation','A caller impersonates a trusted organization to obtain money or access.',('Urgent caller','Requests an OTP','Independent callback discouraged'),45),
 ('FAKE_MERCHANT_QR','Merchant Fraud','Tampered merchant QR','A payment request substitutes a different recipient for the intended merchant.',('Unexpected payee','Recipient not independently verified'),43),
 ('PIG_BUTCHERING','Long-Term Scam','Relationship investment scam','A relationship is used to encourage deposits into a fraudulent investment scheme.',('Guaranteed returns','Withdrawal fees','Repeated deposits'),48),
 ('AGENT_FRAUD','Agent Fraud','Cash agent impersonation','A fake cash agent asks for a wallet transfer without delivering the promised cash service.',('Unverified agent','Unexpected destination'),42),
 ('TASK_SCAM','Employment Scam','Paid-task scam','A supposed employer requires deposits to release earnings.',('Deposit to unlock earnings','Urgency'),44),
 ('SUBSIDY_PHISHING','Phishing & Smishing','Subsidy phishing','An impostor asks for a fee or credentials to release a supposed subsidy.',('Processing fee','Unverified subsidy message'),40),
 ('PREDATORY_LENDING','Predatory Lending','Predatory lending impersonation','An unverified lender demands unexpected payments or access.',('Unexpected deductions','Unverified lender'),41),
 ('REFUND_SCAM','Refund Scam','Refund impersonation','A fake refund requires a new payment or disclosure of credentials.',('Payment to receive refund','Credential request'),39),
)
SCENARIO_TYPES={'phishing':'PHISHING_APP','payment_burst':'ATO_DRAIN','task_scam':'TASK_SCAM','investment_scam':'PIG_BUTCHERING'}


def schema(table):
    fields=[]
    for item in COLUMNS[table].split():
        name,kind=item.split(':');mode='REQUIRED' if kind.endswith('!') else 'REPEATED' if kind.endswith('*') else 'NULLABLE'
        fields.append({'name':name,'type':kind.rstrip('!*'),'mode':mode})
    return fields


def money(minor):return format(Decimal(minor)/100,'.2f')

def timestamp(value):
    value=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if value.tzinfo is None:value=value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')


def digest_id(prefix,scene,key):
    # Sixteen hex digits reduce the collisions seen with the original 8-digit IDs.
    return prefix+'_'+hashlib.sha256((scene+'|'+prefix+'|'+key).encode()).hexdigest()[:16].upper()


class EnvironmentData:
    def __init__(self,lab,world,desk):
        self.lab,self.world,self.desk=lab,world,desk
        self._key=None;self._tables_cache=None

    def tables(self):
        with self.lab.lock:
            key=(self.lab.db.total_changes,self.lab.clock_day,self.world.state()['tick'])
            if key!=self._key:
                self._tables_cache=self._tables();self._key=key
            return self._tables_cache

    def _tables(self):
        scene=self.lab.db.execute('SELECT scene_id FROM demo_scene WHERE id=1').fetchone()[0]
        ids=lambda prefix,key:digest_id(prefix,scene,key)
        people=self.lab.rows('SELECT * FROM customers ORDER BY id LIMIT ?', (MAX_CUSTOMERS,))
        people_by_id={p['id']:p for p in people}
        if not people:return {name:[] for name in COLUMNS}
        # Business/agent wallets belong to existing residents, not invented FK rows.
        owners=[p['id'] for p in people]
        merchant_owners={f'm{i+1}':owners[-1-i%len(owners)] for i in range(3)}
        agent_owner=owners[-min(4,len(owners))]
        accounts={a['id']:a for a in self.lab.rows('SELECT * FROM accounts')}
        start=(dt.date.fromisoformat(self.lab.clock_day)-dt.timedelta(days=28)).isoformat()
        as_of=timestamp(self.lab.clock_day+'T%02d:59:59Z'%self.world.status()['hour'])
        candidates=self.lab.rows("SELECT * FROM financial_events WHERE status='settled' AND kind IN ('payment','payroll') AND occurred_at>=? AND occurred_at<=? ORDER BY occurred_at,id",(start,as_of))
        events=[e for e in candidates if e['customer_id'] in people_by_id and e['from_account'] and e['to_account'] and e['from_account']!=e['to_account']]
        account_ids={p['id']+':wallet' for p in people}|set(merchant_owners)
        for e in events:account_ids.update((e['from_account'],e['to_account']))
        ownership={}
        for aid in sorted(account_ids):
            a=accounts[aid]
            owner=a['customer_id'] if a.get('customer_id') in people_by_id else merchant_owners.get(aid,agent_owner)
            if a['kind']=='counterparty':
                payers={e['customer_id'] for e in events if e['to_account']==aid}
                available=[cid for cid in owners if cid not in payers] or owners
                owner=available[int(hashlib.sha256(aid.encode()).hexdigest()[:8],16)%len(available)]
            if a.get('customer_id') and a['customer_id'] not in people_by_id:
                raise LabError('Environment export exceeds the active customer boundary.',413)
            ownership[aid]=owner
        tables={name:[] for name in COLUMNS}
        created=timestamp((dt.date.fromisoformat(AS_OF)-dt.timedelta(days=365)).isoformat())
        for i,p in enumerate(people):
            kyc='BASIC' if i%5==0 else 'FULLY_VERIFIED'
            tables['customers'].append({'customer_id':ids('CUST',p['id']),'full_name':p['name'],'kyc_status':kyc,
                'creation_date':created,'risk_tier':'MEDIUM' if kyc=='BASIC' else 'LOW'})
        devices={};daily=Counter();history=defaultdict(list)
        for i,p in enumerate(people):
            key=(p['id'],'device-'+p['id'])
            devices[key]={'device_id':ids('DEV','|'.join(key)),'customer_id':ids('CUST',p['id']),
                'device_model':DEVICE_MODELS[i%len(DEVICE_MODELS)],'ip_address':'192.0.2.'+str(i%254+1),'trust_score':.9}
        # Oracle labels are derived from controlled fixtures, never complaint wording.
        oracle={}
        for report in self.lab.rows('SELECT request_json,event_ids FROM fraud_reports'):
            scenario=json.loads(report['request_json']).get('scenario')
            if scenario:
                control=scenario.endswith('.control');kind=scenario.removesuffix('.control')
                if kind in ('phishing','payment_burst','invoice_redirect','task_scam','investment_scam'):
                    for eid in json.loads(report['event_ids']):oracle[eid]=(not control,'LEGITIMATE' if control else SCENARIO_TYPES.get(kind))
        elapsed=lambda stamp:dt.datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp()
        now_seconds=elapsed(as_of)
        for e in events:
            meta=json.loads(e['metadata']);source,target=e['from_account'],e['to_account'];owner=ownership[source]
            stamp=timestamp(e['occurred_at']);at=elapsed(stamp)
            raw_device=meta.get('device_id','device-'+owner)
            key=(owner,raw_device)
            if key not in devices:
                devices[key]={'device_id':ids('DEV','|'.join(key)),'customer_id':ids('CUST',owner),
                    'device_model':DEVICE_MODELS[int(hashlib.sha256(raw_device.encode()).hexdigest()[:4],16)%len(DEVICE_MODELS)],
                    'ip_address':'198.51.100.'+str(len(devices)%254+1),'trust_score':.4 if meta.get('device_known') is False else .8}
            prior=history[source];flags=[]
            if meta.get('device_known') is False:flags.append('NOVEL_IP')
            precise='T' in e['occurred_at']
            if precise and sum(known and 0<=at-t<=60 for t,_,known in prior)>=2:flags.append('VELOCITY_SPIKE')
            if not any(dest==target for _,dest,_ in prior):flags.append('NEW_RECIPIENT')
            if meta.get('limit_hit') is True:flags.append('MAX_LIMIT_HIT')
            if meta.get('otp_triggered') is True:flags.append('OTP_TRIGGERED')
            kind=meta.get('transaction_type')
            if kind not in PAYMENT_TYPES:
                kind='CASH_IN_AGENT' if e['kind']=='payroll' else 'MERCHANT_QR' if accounts[target]['kind']=='merchant' else 'P2P_TRANSFER'
            channel=meta.get('channel','MOBILE_APP')
            if channel not in ('MOBILE_APP','WEB_PORTAL'):raise LabError('Unsupported environment payment channel.',422)
            fraud,label=oracle.get(e['id'],(bool(meta.get('scenario')),SCENARIO_TYPES.get(meta.get('scenario')) if meta.get('scenario') else 'LEGITIMATE'))
            tables['wallet_transactions'].append({'transaction_id':ids('TXN',e['id']),'sender_wallet_id':ids('WAL',source),
                'receiver_wallet_id':ids('WAL',target),'amount':money(e['amount_minor']),'timestamp':stamp,'transaction_type':kind,
                'channel':channel,'device_id':devices[key]['device_id'],'risk_score':float(min(100,len(flags)*20)),
                'risk_factors':encoded(flags),'is_fraud':fraud,'scam_type':label})
            if 0<=now_seconds-at<86400:daily[source]+=e['amount_minor']
            prior.append((at,target,precise))
        tables['devices']=list(devices.values())
        for aid,owner in ownership.items():
            a=accounts[aid];kind='MERCHANT' if a['kind']=='merchant' else 'AGENT_WALLET' if a['kind']=='treasury' or owner==agent_owner else 'PERSONAL_PRIMARY'
            tables['wallets'].append({'wallet_id':ids('WAL',aid),'customer_id':ids('CUST',owner),'wallet_type':kind,
                'current_balance':money(a['balance_minor']),'daily_spent':money(daily[aid]),'wallet_status':'ACTIVE'})
        for i,(label,category,name,description,flags,impact) in enumerate(TYPOLOGIES,1):
            tables['scam_knowledge'].append({'scam_id':f'KNOW_REF_{i:03d}','scam_category':category,'scam_name':name,
                'typology_description':description,'key_red_flags':list(flags),'base_impact':impact})
        categories={label:category for label,category,*_ in TYPOLOGIES}
        for m in self.desk.memories():
            report=self.lab.db.execute('SELECT * FROM fraud_reports WHERE id=?',(m['source_report_id'],)).fetchone()
            review=self.lab.db.execute('SELECT * FROM fraud_reviews WHERE id=?',(m['review_id'],)).fetchone()
            if not report or not review or review['disposition']!='confirmed_scam' or report['customer_id'] not in people_by_id:continue
            event_ids=json.loads(report['event_ids']);first=next((e for e in events if e['id'] in event_ids),None)
            if not first:continue
            meta=json.loads(first['metadata']);label=oracle.get(first['id'],(None,SCENARIO_TYPES.get(meta.get('scenario'))))[1]
            # A recall request is not a completed refund/freeze. Nullable outcome avoids fabricating one.
            outcome={'TASK_SCAM':'CONFIRMED_TASK_SCAM','FAKE_MERCHANT_QR':'CONFIRMED_QR_SPOOFING','SUBSIDY_PHISHING':'CONFIRMED_SUBSIDY_PHISHING'}.get(label)
            tables['scam_memory'].append({'case_id':'CASE_'+self.lab.clock_day[:4]+'_'+ids('CASE',m['id']).split('_')[1],
                'incident_timestamp':timestamp(review['created_at']),'scam_category':categories.get(label),
                'victim_id':ids('WAL',first['from_account']),'fraudster_id':ids('WAL',first['to_account']),
                'evidence_summary':review['note'],'investigation_outcome':outcome,'approved_by_analyst':'ANALYST_DEMO',
                'learned_pattern_rule':m['lesson']})
        self.validate(tables)
        return tables

    @staticmethod
    def validate(tables):
        primary={'customers':'customer_id','wallets':'wallet_id','devices':'device_id','wallet_transactions':'transaction_id','scam_knowledge':'scam_id','scam_memory':'case_id'}
        keys={}
        for name,rows in tables.items():
            fields=schema(name);names={f['name'] for f in fields};keys[name]={r[primary[name]] for r in rows}
            if len(keys[name])!=len(rows):raise LabError('Generated identifier collision; export refused.',409)
            for row in rows:
                if set(row)!=names:raise LabError('Generated record differs from the AE dictionary.',422)
                if any(row[f['name']] is None for f in fields if f['mode']=='REQUIRED'):raise LabError('A required AE field is missing.',422)
                for field in fields:
                    value=row[field['name']]
                    if value is None:continue
                    kind=field['type']
                    if field['mode']=='REPEATED':valid=isinstance(value,list) and all(isinstance(v,str) for v in value)
                    elif kind=='STRING':valid=isinstance(value,str)
                    elif kind=='BOOLEAN':valid=type(value) is bool
                    elif kind=='INTEGER':valid=type(value) is int
                    elif kind=='FLOAT':valid=type(value) in (int,float) and math.isfinite(value)
                    elif kind=='NUMERIC':valid=isinstance(value,str) and bool(re.fullmatch(r'\d+\.\d{2}',value))
                    elif kind=='TIMESTAMP':
                        try:valid=isinstance(value,str) and value.endswith('Z') and timestamp(value)==value
                        except (ValueError,TypeError):valid=False
                    else:valid=False
                    if not valid:raise LabError('Invalid AE field type: '+name+'.'+field['name'],422)
        if len(keys['customers'])>MAX_CUSTOMERS:raise LabError('Too many active customers.',413)
        wallets={r['wallet_id']:r for r in tables['wallets']};devices={r['device_id']:r for r in tables['devices']}
        customers={r['customer_id']:r for r in tables['customers']}
        if any(r['customer_id'] not in keys['customers'] for rows in (tables['wallets'],tables['devices']) for r in rows):raise LabError('Broken customer reference.',422)
        for r in tables['wallet_transactions']:
            if r['sender_wallet_id'] not in wallets or r['receiver_wallet_id'] not in wallets or r['device_id'] not in devices:raise LabError('Broken transaction reference.',422)
            if devices[r['device_id']]['customer_id']!=wallets[r['sender_wallet_id']]['customer_id']:raise LabError('Device owner differs from sender.',422)
            if r['timestamp']<customers[wallets[r['sender_wallet_id']]['customer_id']]['creation_date']:raise LabError('Payment predates its customer.',422)
            if r['transaction_type'] not in PAYMENT_TYPES or r['channel'] not in ('MOBILE_APP','WEB_PORTAL'):raise LabError('Invalid payment category.',422)
            if Decimal(r['amount'])<=0 or not 0<=r['risk_score']<=100:raise LabError('Invalid payment amount or score.',422)
            if r['scam_type'] not in (None,'LEGITIMATE',*(x[0] for x in TYPOLOGIES)):raise LabError('Invalid scam label.',422)
            if not isinstance(json.loads(r['risk_factors']),list):raise LabError('Risk factors must encode a JSON array.',422)
        if any(not 0<=r['trust_score']<=1 for r in devices.values()):raise LabError('Invalid device trust.',422)
        for r in tables['scam_memory']:
            if r['victim_id'] not in wallets or r['fraudster_id'] not in wallets:raise LabError('Broken memory wallet reference.',422)

    def summary(self):
        tables=self.tables()
        return {'contract':CONTRACT_VERSION,'table_count':len(tables),'counts':{k:len(v) for k,v in tables.items()},
            'transaction_types':dict(Counter(r['transaction_type'] for r in tables['wallet_transactions']))}

    def ledger(self,include_truth=False):
        tables=self.tables();customers={r['customer_id']:r for r in tables['customers']}
        wallets={r['wallet_id']:r for r in tables['wallets']};devices={r['device_id']:r for r in tables['devices']}
        result=[]
        for t in tables['wallet_transactions']:
            sender=customers[wallets[t['sender_wallet_id']]['customer_id']];receiver=customers[wallets[t['receiver_wallet_id']]['customer_id']]
            device=devices[t['device_id']]
            row={k:t[k] for k in ('transaction_id','timestamp','amount','transaction_type','risk_score','risk_factors','is_fraud','scam_type','sender_wallet_id','receiver_wallet_id','device_id')}
            row.update(sender_name=sender['full_name'],sender_kyc=sender['kyc_status'],sender_risk_tier=sender['risk_tier'],
                receiver_name=receiver['full_name'],device_model=device['device_model'],ip_address=device['ip_address'],trust_score=device['trust_score'])
            result.append(row if include_truth else {k:v for k,v in row.items() if k not in PRIVATE_FIELDS})
        return result

    def preview(self):
        tables=self.tables()
        return {'contract':CONTRACT_VERSION,'dictionary':'data/DATA_DICTIONARY.md','customer_limit':MAX_CUSTOMERS,
            'as_of':self.lab.clock_day,'tables':[{'name':name,'rows':len(rows),'fields':[f['name'] for f in schema(name)]} for name,rows in tables.items()],
            'transaction_types':dict(Counter(r['transaction_type'] for r in tables['wallet_transactions'])),
            'memory_policy':'Only cases approved in this scene; seeded rules do not activate prevention.',
            'risk_scores':'Observed heuristic flags, not trained fraud probabilities.',
            'view':{'name':'v_agent_ledger','rows':len(tables['wallet_transactions']),'preview':self.ledger()[:2]},
            'previews':{name:[{k:v for k,v in r.items() if k not in PRIVATE_FIELDS} for r in rows[:2]] for name,rows in tables.items()}}

    def export(self,directory):
        tables=self.tables()
        bodies={name:''.join(encoded(r)+'\n' for r in rows) for name,rows in tables.items()}
        if sum(map(len,tables.values()))>MAX_EXPORT_ROWS or sum(len(s.encode()) for s in bodies.values())>MAX_EXPORT_BYTES:
            raise LabError('Environment export exceeds its row or byte allowance.',413)
        target=Path(directory);target.mkdir(parents=True,exist_ok=True)
        for name,rows in tables.items():
            (target/(name+'.jsonl')).write_text(bodies[name])
            (target/(name+'.schema.json')).write_text(json.dumps(schema(name),indent=2)+'\n')
        (target/'v_agent_ledger.jsonl').write_text(''.join(encoded(r)+'\n' for r in self.ledger(include_truth=True)))
        manifest={'contract':CONTRACT_VERSION,'scene':self.lab.db.execute('SELECT scene_id FROM demo_scene WHERE id=1').fetchone()[0],
            'counts':{name:len(rows) for name,rows in tables.items()},'private_evaluation_labels':True}
        (target/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        return manifest
