"""Bounded typed BigQuery snapshots and parameterized, case-scoped feature tools."""
import datetime as dt
import gzip
import hashlib
import json
import math
import time
import uuid
from collections import Counter, defaultdict

from cloud_data import DAILY_EXPORTS, MAX_EXPORT_BYTES, MAX_EXPORT_ROWS
from lab import LabError, encoded, now
from settings import MAX_CUSTOMERS, DAILY_WAREHOUSE_QUERIES

MAX_QUERY_BYTES=50*1024*1024
DAILY_QUERIES=DAILY_WAREHOUSE_QUERIES
SCHEMAS={
 'pallet_customers':'customer_id:STRING name:STRING age_band:STRING region:STRING occupation:STRING weekly_income_minor:INTEGER',
 'pallet_merchants':'merchant_id:STRING name:STRING kind:STRING',
 'pallet_transactions':'event_id:STRING customer_id:STRING occurred_at:TIMESTAMP kind:STRING status:STRING amount_minor:INTEGER currency:STRING from_account:STRING to_account:STRING merchant_id:STRING rail:STRING device_known:BOOLEAN authorization_verified:BOOLEAN',
 'pallet_customer_daily':'customer_id:STRING payment_count:INTEGER spend_minor:INTEGER average_payment_minor:FLOAT max_payment_minor:INTEGER merchant_count:INTEGER unknown_device_count:INTEGER max_burst_minute:INTEGER income_minor:INTEGER',
 'pallet_complaints':'report_id:STRING customer_id:STRING story:STRING message:STRING event_ids:JSON status:STRING',
 'pallet_reviews':'review_id:STRING report_id:STRING customer_id:STRING disposition:STRING note:STRING',
 'pallet_memories':'memory_id:STRING report_id:STRING lesson:STRING next_question:STRING pattern:JSON validation:JSON',
}
MODEL_FEATURES=('payment_count','spend_php','average_payment_php','merchant_count')
MODEL_RECIPE='daily-behavior-kmeans-v2'


class Warehouse:
    def __init__(self,lab,cloud):
        self.lab,self.cloud=lab,cloud
        lab.db.executescript('''
        CREATE TABLE IF NOT EXISTS warehouse_snapshots(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,
          as_of TEXT NOT NULL,status TEXT NOT NULL,row_count INTEGER NOT NULL,jobs TEXT NOT NULL,counts TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS warehouse_queries(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,
          status TEXT NOT NULL,bytes_billed INTEGER NOT NULL DEFAULT 0,result TEXT NOT NULL DEFAULT '[]');
        CREATE TABLE IF NOT EXISTS behavior_models(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,
          artifact TEXT NOT NULL,report TEXT NOT NULL);
        ''')

    def provision(self):
        """Seven-day table TTL; historical event-date partitions must not expire at ingestion."""
        base=f'https://bigquery.googleapis.com/bigquery/v2/projects/{self.cloud.project}/datasets/{self.cloud.dataset}/tables'
        for name,columns in SCHEMAS.items():
            response=self.cloud.request('GET',base+'/'+name)
            if response.status_code==404:
                fields=[{'name':'snapshot_id','type':'STRING','mode':'REQUIRED'},{'name':'event_date','type':'DATE','mode':'REQUIRED'}]
                fields += [{'name':item.split(':')[0],'type':item.split(':')[1]} for item in columns.split()]
                response=self.cloud.request('POST',base,json={'tableReference':{'projectId':self.cloud.project,'datasetId':self.cloud.dataset,'tableId':name},
                    'schema':{'fields':fields},'timePartitioning':{'type':'DAY','field':'event_date'},
                    'requirePartitionFilter':True,'clustering':{'fields':['snapshot_id']},
                    'expirationTime':str(int((time.time()+7*86400)*1000))})
            response.raise_for_status();table=response.json()
            if table.get('timePartitioning',{}).get('expirationMs'):
                response=self.cloud.request('PATCH',base+'/'+name,json={'timePartitioning':{'type':'DAY','field':'event_date','expirationMs':None}})
                response.raise_for_status();table=response.json()
            if table.get('timePartitioning',{}).get('expirationMs') or not table.get('expirationTime') or not table.get('requirePartitionFilter'):
                raise ValueError('Warehouse retention or partition controls were not applied: '+name)

    def tables(self):
        day=self.lab.clock_day;start=(dt.date.fromisoformat(day)-dt.timedelta(days=28)).isoformat()
        people=self.lab.rows('SELECT * FROM customers ORDER BY id LIMIT ?', (MAX_CUSTOMERS,));ids={p['id'] for p in people}
        profiles={r['customer_id']:json.loads(r['profile']) for r in self.lab.rows('SELECT * FROM customer_profiles') if r['customer_id'] in ids}
        events=[r for r in self.lab.rows('SELECT * FROM financial_events WHERE occurred_at>=? AND occurred_at<? ORDER BY rowid',(start,day+'T24')) if r['customer_id'] in ids]
        accounts={r['id']:r for r in self.lab.rows('SELECT * FROM accounts')};tables={k:[] for k in SCHEMAS}
        for p in people:
            profile=profiles.get(p['id'],{})
            tables['pallet_customers'].append({'event_date':day,'customer_id':p['id'],'name':p['name'],
                'age_band':profile.get('age_band'),'region':profile.get('region'),'occupation':profile.get('occupation'),
                'weekly_income_minor':p['weekly_income_minor']})
        grouped=defaultdict(list);merchant_ids=set()
        for event in events:
            meta=json.loads(event['metadata']);payee=event['to_account'];account=accounts.get(payee,{})
            merchant=payee if account.get('kind') in ('merchant','counterparty') else None
            if merchant:merchant_ids.add(merchant)
            event_day=event['occurred_at'][:10];grouped[(event['customer_id'],event_day)].append(event)
            tables['pallet_transactions'].append({'event_date':event_day,'event_id':event['id'],'customer_id':event['customer_id'],
                'occurred_at':event['occurred_at'] if 'T' in event['occurred_at'] else event_day+'T00:00:00Z',
                'kind':event['kind'],'status':event['status'],'amount_minor':event['amount_minor'],'currency':'PHP',
                'from_account':event['from_account'],'to_account':payee,'merchant_id':merchant,'rail':meta.get('rail'),
                'device_known':meta.get('device_known'),'authorization_verified':meta.get('authorization_verified')})
        for mid in sorted(merchant_ids):tables['pallet_merchants'].append({'event_date':day,'merchant_id':mid,'name':accounts[mid]['label'],'kind':accounts[mid]['kind']})
        for cid in sorted(ids):
            for offset in range(29):
                event_day=(dt.date.fromisoformat(start)+dt.timedelta(days=offset)).isoformat()
                rows=grouped[(cid,event_day)];payments=[r for r in rows if r['kind']=='payment' and r['status']=='settled']
                amounts=[r['amount_minor'] for r in payments];minutes=Counter(r['occurred_at'][:16] for r in payments if 'T' in r['occurred_at'])
                tables['pallet_customer_daily'].append({'event_date':event_day,'customer_id':cid,'payment_count':len(payments),
                    'spend_minor':sum(amounts),'average_payment_minor':sum(amounts)/len(amounts) if amounts else 0,
                    'max_payment_minor':max(amounts,default=0),'merchant_count':len({r['to_account'] for r in payments}),
                    'unknown_device_count':sum(json.loads(r['metadata']).get('device_known') is False for r in payments),
                    'max_burst_minute':max(minutes.values(),default=0),
                    'income_minor':sum(r['amount_minor'] for r in rows if r['kind']=='payroll' and r['status']=='settled')})
        for r in self.lab.rows('SELECT * FROM fraud_reports ORDER BY rowid'):
            if r['customer_id'] in ids:tables['pallet_complaints'].append({'event_date':r['created_at'][:10],'report_id':r['id'],
                'customer_id':r['customer_id'],'story':r['story'],'message':r['message'],'event_ids':json.loads(r['event_ids']),'status':r['status']})
        for r in self.lab.rows('SELECT v.*,r.customer_id FROM fraud_reviews v JOIN fraud_reports r ON r.id=v.report_id'):
            if r['customer_id'] in ids:tables['pallet_reviews'].append({'event_date':r['created_at'][:10],'review_id':r['id'],
                'report_id':r['report_id'],'customer_id':r['customer_id'],'disposition':r['disposition'],'note':r['note']})
        for r in self.lab.rows('SELECT * FROM scam_memories'):tables['pallet_memories'].append({'event_date':r['created_at'][:10],
            'memory_id':r['id'],'report_id':r['source_report_id'],'lesson':r['lesson'],'next_question':r['next_question'],
            'pattern':json.loads(r['pattern']),'validation':json.loads(r['validation'])})
        return tables

    def latest(self):
        row=self.lab.db.execute("SELECT * FROM warehouse_snapshots WHERE status='completed' ORDER BY rowid DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def status(self):
        latest=self.latest()
        return {'enabled':True,'table_count':len(SCHEMAS),'tables':list(SCHEMAS),'customer_limit':MAX_CUSTOMERS,
                'latest_snapshot':None if not latest else {**latest,'counts':json.loads(latest['counts']),'jobs':json.loads(latest['jobs'])},
                'query_limit_per_day':DAILY_QUERIES,'max_bytes_per_query':MAX_QUERY_BYTES}

    def wait_job(self,job_id,job=None):
        deadline=time.monotonic()+12
        for _ in range(20):
            if job and job.get('status',{}).get('state')=='DONE':
                if job['status'].get('errorResult'):raise LabError('BigQuery job failed: '+job['status']['errorResult'].get('message','Unknown failure'),502)
                return job
            if time.monotonic()>=deadline:break
            response=self.cloud.request('GET',self.cloud.job_url()+'/'+job_id,params={'location':self.cloud.location},timeout=5)
            response.raise_for_status();job=response.json()
            if job.get('status',{}).get('state')!='DONE':time.sleep(.25)
        raise LabError('BigQuery job is still pending. No job was resubmitted.',503)

    def publish(self):
        with self.lab.lock:
            tables=self.tables()
            # Workflow status changes do not make a new financial feature snapshot.
            identity={k:rows if k!='pallet_complaints' else [{a:b for a,b in r.items() if a!='status'} for r in rows] for k,rows in tables.items()}
            snapshot=self.lab.fingerprint(identity)
            prior=self.lab.db.execute('SELECT * FROM warehouse_snapshots WHERE id=?',(snapshot,)).fetchone()
            if prior:
                if prior['status']=='completed':return snapshot
                raise LabError('An earlier warehouse publication needs operator reconciliation. No load was retried.',409)
            count=sum(map(len,tables.values()));size=sum(len(encoded(r).encode())+90 for rows in tables.values() for r in rows)
            if count>MAX_EXPORT_ROWS or size>MAX_EXPORT_BYTES:raise LabError('Warehouse snapshot exceeds its row or byte cap.',413)
            if self.cloud.daily_exports(self.lab)>=DAILY_EXPORTS:raise LabError('Daily BigQuery publication limit reached.',429)
            jobs={name:'pallet_load_'+snapshot[:32]+'_'+name for name,rows in tables.items() if rows}
            with self.lab.db:self.lab.db.execute('INSERT INTO warehouse_snapshots VALUES(?,?,?,?,?,?,?)',
                (snapshot,now(),self.lab.clock_day,'reserved',count,encoded(jobs),encoded({k:len(v) for k,v in tables.items()})))
            self.cloud.save(self.lab)
        try:
            for name,job_id in jobs.items():
                body='\n'.join(encoded({'snapshot_id':snapshot,**r}) for r in tables[name]).encode()
                object_name=f'exports/{snapshot}/{name}.jsonl.gz';self.cloud.upload(object_name,gzip.compress(body,mtime=0),'0')
                response=self.cloud.request('POST',self.cloud.job_url(),json={
                    'jobReference':{'projectId':self.cloud.project,'jobId':job_id,'location':self.cloud.location},
                    'configuration':{'jobTimeoutMs':'15000','load':{'sourceUris':[f'gs://{self.cloud.bucket}/{object_name}'],
                        'destinationTable':{'projectId':self.cloud.project,'datasetId':self.cloud.dataset,'tableId':name},
                        'createDisposition':'CREATE_NEVER','writeDisposition':'WRITE_APPEND','sourceFormat':'NEWLINE_DELIMITED_JSON'}}})
                response.raise_for_status();self.wait_job(job_id,response.json())
            status='completed'
        except Exception:
            with self.lab.lock,self.lab.db:self.lab.db.execute("UPDATE warehouse_snapshots SET status='uncertain' WHERE id=?",(snapshot,))
            self.cloud.save(self.lab);raise LabError('Warehouse publication stopped. Its allowance is retained; no automatic retry.',503) from None
        with self.lab.lock,self.lab.db:self.lab.db.execute('UPDATE warehouse_snapshots SET status=? WHERE id=?',(status,snapshot))
        self.cloud.save(self.lab);return snapshot

    def query(self,sql,parameters):
        identifier='pallet_query_'+uuid.uuid4().hex
        params=[{'name':k,'parameterType':{'type':'DATE' if k in ('day','since') else 'STRING'},'parameterValue':{'value':v}} for k,v in parameters.items()]
        with self.lab.lock,self.lab.db:
            used=self.lab.db.execute('SELECT count(*) FROM warehouse_queries WHERE substr(created_at,1,10)=?',(now()[:10],)).fetchone()[0]
            if used>=DAILY_QUERIES:raise LabError('Daily BigQuery query allowance reached.',429)
            self.lab.db.execute('INSERT INTO warehouse_queries(id,created_at,status) VALUES(?,?,?)',(identifier,now(),'reserved'))
        self.cloud.save(self.lab)
        try:
            response=self.cloud.request('POST',self.cloud.job_url(),json={'jobReference':{'projectId':self.cloud.project,'jobId':identifier,'location':self.cloud.location},
                'configuration':{'jobTimeoutMs':'15000','query':{'query':sql,'useLegacySql':False,'maximumBytesBilled':str(MAX_QUERY_BYTES),
                    'parameterMode':'NAMED','queryParameters':params}}})
            response.raise_for_status();job=self.wait_job(identifier,response.json())
            url=f'https://bigquery.googleapis.com/bigquery/v2/projects/{self.cloud.project}/queries/{identifier}'
            response=self.cloud.request('GET',url,params={'location':self.cloud.location,'maxResults':100});response.raise_for_status();result=response.json()
            if not result.get('jobComplete') or result.get('pageToken'):raise LabError('BigQuery result exceeds the bounded result envelope.',413)
            rows=[json.loads(r['f'][0]['v']) for r in result.get('rows',[])]
            billed=int(job.get('statistics',{}).get('query',{}).get('totalBytesBilled',0))
            with self.lab.lock,self.lab.db:self.lab.db.execute("UPDATE warehouse_queries SET status='completed',bytes_billed=?,result=? WHERE id=?",(billed,encoded(rows),identifier))
            self.cloud.save(self.lab)
            return rows,{'provider':'BigQuery','job_id':identifier,'bytes_billed':billed,'snapshot_id':parameters['snapshot']}
        except Exception:
            with self.lab.lock,self.lab.db:self.lab.db.execute("UPDATE warehouse_queries SET status='uncertain' WHERE id=?",(identifier,))
            self.cloud.save(self.lab);raise

    def parameters(self,snapshot,day):
        return {'snapshot':snapshot,'day':day,'since':(dt.date.fromisoformat(day)-dt.timedelta(days=28)).isoformat()}

    def customer_features(self,cid,snapshot,day):
        table=f'`{self.cloud.project}.{self.cloud.dataset}.pallet_customer_daily`'
        sql=f'''SELECT TO_JSON_STRING(STRUCT(customer_id,
            SUM(IF(event_date=@day,payment_count,0)) AS payment_count,
            SUM(IF(event_date=@day,spend_minor,0))/100.0 AS spend_php,
            SUM(IF(event_date=@day,average_payment_minor,0))/100.0 AS average_payment_php,
            SUM(IF(event_date=@day,merchant_count,0)) AS merchant_count,
            SUM(IF(event_date=@day,unknown_device_count,0)) AS unknown_device_count,
            MAX(IF(event_date=@day,max_burst_minute,0)) AS max_burst_minute,
            AVG(IF(event_date<@day,payment_count,NULL)) AS prior_daily_payment_count,
            AVG(IF(event_date<@day,spend_minor/100.0,NULL)) AS prior_daily_spend_php,
            COUNTIF(event_date<@day) AS baseline_days)) AS data
            FROM {table} WHERE snapshot_id=@snapshot AND customer_id=@customer
            AND event_date BETWEEN @since AND @day GROUP BY customer_id'''
        rows,source=self.query(sql,{**self.parameters(snapshot,day),'customer':cid})
        if not rows or rows[0].get('customer_id')!=cid:raise LabError('The pinned BigQuery customer snapshot is unavailable or outside this case.',409)
        return {'features':rows[0],'source':source,'currency':'PHP',
                'scope':'Behavioral features only. Demographics are stored separately and excluded from risk scoring.'}

    def train_behavior_model(self,cid,snapshot,day,current):
        table=f'`{self.cloud.project}.{self.cloud.dataset}.pallet_customer_daily`'
        sql=f'''SELECT TO_JSON_STRING(STRUCT(customer_id,ARRAY_AGG(STRUCT(event_date,payment_count,
            spend_minor/100.0 AS spend_php,average_payment_minor/100.0 AS average_payment_php,
            merchant_count) ORDER BY event_date LIMIT 28) AS days)) AS data FROM {table}
            WHERE snapshot_id=@snapshot AND event_date>=@since AND event_date<@day
            GROUP BY customer_id ORDER BY customer_id LIMIT 100'''
        rows,source=self.query(sql,self.parameters(snapshot,day))
        if len(rows)<20:return {'status':'not_trained','reason':'Need at least 20 customer histories. Continue descriptive analysis.','source':source}
        identifier='behavior-'+self.lab.fingerprint({'recipe':MODEL_RECIPE,'rows':rows})[:20]
        with self.lab.lock:
            saved=self.lab.db.execute('SELECT * FROM behavior_models WHERE id=?',(identifier,)).fetchone()
            if saved:artifact=json.loads(saved['artifact']);report=json.loads(saved['report'])
            else:
                if self.lab.db.execute('SELECT count(*) FROM behavior_models WHERE substr(created_at,1,10)=?',(now()[:10],)).fetchone()[0]>=2:
                    return {'status':'not_trained','reason':'Two local model builds already used today.','source':source}
                artifact,report=fit_behavior(rows)
                with self.lab.db:self.lab.db.execute('INSERT INTO behavior_models VALUES(?,?,?,?)',(identifier,now(),encoded(artifact),encoded(report)))
                self.cloud.save(self.lab)
        vector=[float(current[k]) for k in MODEL_FEATURES]
        distance=behavior_distance(artifact,vector)
        return {'status':'cached' if saved else 'trained','model_id':identifier,'report':report,'source':source,
            'customer_id':cid,'distance':round(distance,4),'unusual':distance>artifact['threshold'],
            'restriction':'Unsupervised behavior anomaly, not probability or proof of fraud. Never activates a payment block.'}


def behavior_distance(model,values):
    vector=[(v-m)/s for v,m,s in zip(values,model['means'],model['scales'])]
    return min(sum((a-b)**2 for a,b in zip(vector,c)) for c in model['centers'])


def fit_behavior(rows):
    training=[r for r in rows if int(hashlib.sha256(r['customer_id'].encode()).hexdigest()[:8],16)%5]
    holdout=[r for r in rows if r not in training]
    if len(training)<10 or len(holdout)<3:raise LabError('Insufficient independent customers for behavior-model validation.',409)
    training_days=[point for row in training for point in row.get('days',[row])]
    holdout_days=[point for row in holdout for point in row.get('days',[row])]
    values=[[float(r[k]) for k in MODEL_FEATURES] for r in training_days];n=len(values);width=len(MODEL_FEATURES)
    means=[sum(r[j] for r in values)/n for j in range(width)]
    scales=[max(.01,math.sqrt(sum((r[j]-means[j])**2 for r in values)/n)) for j in range(width)]
    vectors=[[(v-m)/s for v,m,s in zip(row,means,scales)] for row in values]
    centers=[vectors[0]]
    for _ in range(2):centers.append(max(vectors,key=lambda v:min(sum((a-b)**2 for a,b in zip(v,c)) for c in centers)))
    for _ in range(25):
        groups=[[],[],[]]
        for vector in vectors:groups[min(range(3),key=lambda j:sum((a-b)**2 for a,b in zip(vector,centers[j])))].append(vector)
        centers=[[sum(v[j] for v in group)/len(group) for j in range(width)] if group else center for group,center in zip(groups,centers)]
    model={'features':MODEL_FEATURES,'means':means,'scales':scales,'centers':centers}
    distances=sorted(behavior_distance(model,v) for v in values);model['threshold']=max(.01,distances[min(n-1,int(.95*n))])
    report={'algorithm':'Three-cluster k-means, 25 iterations, local CPU','training_customers':len(training),'holdout_customers':len(holdout),
        'training_rows':len(training_days),'holdout_rows':len(holdout_days),
        'holdout_unusual_fraction':sum(behavior_distance(model,[float(r[k]) for k in MODEL_FEATURES])>model['threshold'] for r in holdout_days)/len(holdout_days),
        'recipe':MODEL_RECIPE,'features':MODEL_FEATURES,'labelled_fraud_accuracy':None,
        'limitations':'Synthetic daily observations and unlabeled holdout. Advisory only. Demographics and incompletely recorded historical device/minute signals are excluded.'}
    return model,report
