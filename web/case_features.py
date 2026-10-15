"""Case-scoped SQL features from the AE contract; verified against canonical rows.

Runs during intake, outside model/ledger transactions. Missing or stale mirrors
retain the existing local evidence path with explicit provenance, never fake BQ.
"""
import datetime as dt
import json
import math
from collections import Counter
from decimal import Decimal

from environment_data import digest_id,timestamp
from lab import AS_OF,LabError,encoded,now

VERSION='ae-case-features-v1'
MAX_CASE_ROWS=1000


def reference(data,cid,cutoff,event_ids):
    tables=data.tables();scene=data.lab.db.execute('SELECT scene_id FROM demo_scene WHERE id=1').fetchone()[0]
    customer=digest_id('CUST',scene,cid);wallets={r['wallet_id']:r for r in tables['wallets']};devices={r['device_id']:r for r in tables['devices']}
    day=dt.date.fromisoformat(cutoff[:10]);since=day-dt.timedelta(days=28)
    if not data.lab.seed_history:since=max(since,dt.date.fromisoformat(AS_OF))
    cutoff=timestamp(cutoff);rows=[]
    for r in tables['wallet_transactions']:
        if wallets[r['sender_wallet_id']]['customer_id']!=customer or not str(since)<=r['timestamp']<=cutoff:continue
        rows.append({'transaction_id':r['transaction_id'],'timestamp':r['timestamp'],'amount_php':float(Decimal(r['amount'])),
            'recipient_wallet':r['receiver_wallet_id'],'sender_customer':customer,'device_customer':devices[r['device_id']]['customer_id']})
    rows.sort(key=lambda r:(r['timestamp'],r['transaction_id']))
    if len(rows)>MAX_CASE_ROWS:raise LabError('AE feature history exceeds its bounded case window.',413)
    required={digest_id('TXN',scene,e) for e in event_ids}
    if not required<=set(r['transaction_id'] for r in rows):raise LabError('The AE projection does not contain all reported outgoing payments.',409)
    today=[r for r in rows if r['timestamp'][:10]==str(day)];prior=[r for r in rows if r['timestamp'][:10]<str(day)];days=(day-since).days
    spend=sum(r['amount_php'] for r in today)
    values={'customer_id':customer,'payment_count':len(today),'spend_php':spend,'average_payment_php':spend/len(today) if today else 0,
        'merchant_count':len({r['recipient_wallet'] for r in today}),'unknown_device_count':None,
        'max_burst_minute':max(Counter(r['timestamp'][:16] for r in today).values(),default=0),
        'prior_daily_payment_count':len(prior)/days if days else None,
        'prior_daily_spend_php':sum(r['amount_php'] for r in prior)/days if days else None,'baseline_days':days,
        'device_ownership_mismatches':sum(r['device_customer']!=customer for r in rows)}
    return {'customer':customer,'day':str(day),'since':str(since),'cutoff':cutoff,'records':rows,'features':values,
        'reported_transaction_ids':sorted(required),'scene_id':scene}


def sql(project):
    table=lambda name:f'`{project}.minttown_world.{name}`'
    return f'''WITH scoped AS (
        SELECT t.transaction_id,t.timestamp,CAST(t.amount AS FLOAT64) amount_php,
               t.receiver_wallet_id recipient_wallet,w.customer_id sender_customer,d.customer_id device_customer
        FROM {table('wallet_transactions')} t
        JOIN {table('wallets')} w ON w.wallet_id=t.sender_wallet_id
        JOIN {table('customers')} c ON c.customer_id=w.customer_id
        LEFT JOIN {table('devices')} d ON d.device_id=t.device_id
        WHERE w.customer_id=@customer AND t.timestamp>=TIMESTAMP(@since)
          AND t.timestamp<=TIMESTAMP(@cutoff) AND DATE(t.timestamp) BETWEEN @since AND @day
          AND c.creation_date<=t.timestamp
    ), totals AS (
        SELECT COUNT(*) record_count,COUNTIF(DATE(timestamp)=@day) payment_count,
          COALESCE(SUM(IF(DATE(timestamp)=@day,amount_php,0)),0) spend_php,
          COUNT(DISTINCT IF(DATE(timestamp)=@day,recipient_wallet,NULL)) merchant_count,
          COUNTIF(DATE(timestamp)<@day) prior_count,COALESCE(SUM(IF(DATE(timestamp)<@day,amount_php,0)),0) prior_spend,
          COUNTIF(device_customer IS NULL OR device_customer!=sender_customer) device_ownership_mismatches FROM scoped
    ), bursts AS (
        SELECT COUNT(*) n FROM scoped WHERE DATE(timestamp)=@day GROUP BY TIMESTAMP_TRUNC(timestamp,MINUTE)
    ) SELECT TO_JSON_STRING(STRUCT(
      STRUCT(@customer AS customer_id,payment_count,spend_php,COALESCE(SAFE_DIVIDE(spend_php,payment_count),0) AS average_payment_php,
        merchant_count,CAST(NULL AS INT64) AS unknown_device_count,(SELECT COALESCE(MAX(n),0) FROM bursts) AS max_burst_minute,
        SAFE_DIVIDE(prior_count,DATE_DIFF(@day,@since,DAY)) AS prior_daily_payment_count,
        SAFE_DIVIDE(prior_spend,DATE_DIFF(@day,@since,DAY)) AS prior_daily_spend_php,
        DATE_DIFF(@day,@since,DAY) AS baseline_days,device_ownership_mismatches) AS features,
      record_count,ARRAY(SELECT AS STRUCT transaction_id,FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ',timestamp,'UTC') AS timestamp,
        amount_php,recipient_wallet,sender_customer,device_customer FROM scoped ORDER BY timestamp,transaction_id LIMIT {MAX_CASE_ROWS+1}) AS records
    )) AS data FROM totals'''


def same_values(actual,expected):
    if type(actual) is dict:return set(actual)==set(expected) and all(same_values(actual[k],expected[k]) for k in actual)
    if type(actual) is list:return len(actual)==len(expected) and all(same_values(a,b) for a,b in zip(actual,expected))
    if isinstance(actual,(int,float)) and isinstance(expected,(int,float)):return math.isfinite(actual) and math.isclose(actual,expected,rel_tol=1e-9,abs_tol=1e-6)
    return actual==expected


class CaseFeatures:
    def __init__(self,warehouse):
        self.warehouse,self.lab=warehouse,warehouse.lab;self.data=None;self.publisher=None
        self.lab.db.execute('''CREATE TABLE IF NOT EXISTS case_feature_queries(
          id TEXT PRIMARY KEY,report_id TEXT NOT NULL,basis_hash TEXT NOT NULL,publication_id TEXT NOT NULL,
          status TEXT NOT NULL,result TEXT,error TEXT,created_at TEXT NOT NULL)''');self.lab.db.commit()

    def basis(self,report):
        tx=self.lab.rows('SELECT * FROM financial_events WHERE id IN ('+','.join('?' for _ in report['event_ids'])+')',tuple(report['event_ids']))
        if not tx or any(t['customer_id']!=report['customer_id'] for t in tx):raise LabError('Case features require owned payment evidence.',403)
        return reference(self.data,report['customer_id'],max(t['occurred_at'] for t in tx),report['event_ids'])

    def prepare(self,report):
        if not self.data or not self.publisher:return None
        with self.lab.lock:
            source=self.publisher.status()['latest']
            if not source or source['status']!='completed' or not self.warehouse.fresh(source):return None
            try:basis=self.basis(report)
            except LabError:return None
            coverage=self.lab.db.execute('SELECT transaction_ids FROM environment_feature_coverage WHERE publication_id=?',(source['id'],)).fetchone()
            if not coverage or not {r['transaction_id'] for r in basis['records']}<=set(json.loads(coverage['transaction_ids'])):return None
            basis_hash=self.lab.fingerprint([VERSION,basis]);key=self.lab.fingerprint([report['id'],basis_hash,source['id']])
            old=self.lab.db.execute('SELECT status,result FROM case_feature_queries WHERE id=?',(key,)).fetchone()
            if old:return json.loads(old['result']) if old['status']=='completed' else None
            with self.lab.db:self.lab.db.execute('INSERT INTO case_feature_queries VALUES(?,?,?,?,?,NULL,NULL,?)',(key,report['id'],basis_hash,source['id'],'reserved',now()))
        self.warehouse.cloud.save(self.lab)
        try:
            rows,receipt=self.warehouse.query(sql(self.warehouse.cloud.project),
                {k:basis[k] for k in ('customer','day','since','cutoff')}|{'snapshot':source['id']},location='US')
            result=rows[0] if len(rows)==1 else {}
            current=self.publisher.status()['latest']
            if not current or current['id']!=source['id'] or current['status']!='completed':raise LabError('The AE mirror changed during the feature query.',409)
            if result.get('record_count')!=len(basis['records']) or not same_values(result.get('records',[]),basis['records']) or not same_values(result.get('features',{}),basis['features']):
                raise LabError('BigQuery records differ from the frozen case projection. Stale or incomplete features were withheld.',409)
            values=result['features'];values['customer_id']=report['customer_id']
            output={'available':True,'features':values,'currency':'PHP','missing_inputs':['AE dictionary has no device-recognition or authorization status; use the pinned payment facts.'],
                'source':{**receipt,'feature_version':VERSION,'evidence_hash':basis_hash,'cutoff':basis['cutoff'],'record_count':len(basis['records']),
                    'published_at':source['completed_at'],'available_at':now(),'analytics_sync':'queried_completed_publication',
                    'dataset':'minttown_world','tables':['customers','wallets','devices','wallet_transactions'],
                    'computation':'Parameterized BigQuery aggregation over four AE tables; source rows checked against the scoped canonical projection.'},
                'scope':'Investigation-time outgoing payments. Historical aggregates are not retrospective proof of what the prepayment gateway knew.'}
            with self.lab.lock,self.lab.db:self.lab.db.execute("UPDATE case_feature_queries SET status='completed',result=? WHERE id=?",(encoded(output),key))
        except Exception as exc:
            with self.lab.lock,self.lab.db:self.lab.db.execute("UPDATE case_feature_queries SET status='unavailable',error=? WHERE id=?",(str(exc)[:500],key))
            if not self.warehouse.cloud.healthy:raise
            output=None
        self.warehouse.cloud.save(self.lab);return output

    def cached(self,report):
        if not self.data or not self.publisher:return None
        try:basis_hash=self.lab.fingerprint([VERSION,self.basis(report)])
        except LabError:return None
        row=self.lab.db.execute("SELECT result,created_at FROM case_feature_queries WHERE report_id=? AND basis_hash=? AND status='completed' ORDER BY rowid DESC LIMIT 1",(report['id'],basis_hash)).fetchone()
        return json.loads(row['result']) if row and self.warehouse.fresh(row) else None
