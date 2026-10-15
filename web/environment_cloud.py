"""Bounded AE-schema mirror in a dedicated, app-owned BigQuery dataset.

Six loads are not a cross-table transaction. Consumers must require a completed
receipt and use its immutable GCS batch for reproducible training/evaluation.
"""
import datetime as dt
import gzip
import hashlib
import json
import time

from cloud_data import DAILY_EXPORTS, MAX_EXPORT_BYTES, MAX_EXPORT_ROWS, wait_job
from environment_data import COLUMNS, CONTRACT_VERSION, schema
from lab import AS_OF, LabError, encoded, now

DATASET='minttown_world'
LOCATION='US'
RETENTION_MS=7*86400*1000
LABELS={'app':'minttown','purpose':'simulator_mirror','contract':'gab_f03a384_v1'}


def initialize(lab):
    lab.db.execute('''CREATE TABLE IF NOT EXISTS environment_publications(
        id TEXT PRIMARY KEY,created_at TEXT NOT NULL,status TEXT NOT NULL,
        row_count INTEGER NOT NULL,size_bytes INTEGER NOT NULL,counts TEXT NOT NULL,
        jobs TEXT NOT NULL,completed_at TEXT)''')
    lab.db.execute('''CREATE TABLE IF NOT EXISTS environment_feature_coverage(
        publication_id TEXT PRIMARY KEY,transaction_ids TEXT NOT NULL)''')
    lab.db.commit()


class EnvironmentPublisher:
    def __init__(self,data,cloud,dataset=DATASET):
        if dataset!=DATASET:raise ValueError('Only the isolated minttown_world dataset is writable.')
        self.data,self.lab,self.cloud,self.dataset=data,data.lab,cloud,dataset
        self.base=f'https://bigquery.googleapis.com/bigquery/v2/projects/{cloud.project}/datasets'

    def view_sql(self,day):
        end=dt.date.fromisoformat(day)+dt.timedelta(days=1);start=end-dt.timedelta(days=29)
        table=lambda name:f'`{self.cloud.project}.{self.dataset}.{name}`'
        return f'''SELECT t.transaction_id,t.timestamp,t.amount,t.transaction_type,
            t.risk_score,t.risk_factors,t.is_fraud,t.scam_type,
            t.sender_wallet_id,s.full_name AS sender_name,s.kyc_status AS sender_kyc,
            s.risk_tier AS sender_risk_tier,t.receiver_wallet_id,r.full_name AS receiver_name,
            t.device_id,d.device_model,d.ip_address,d.trust_score
            FROM {table('wallet_transactions')} t
            JOIN {table('wallets')} sw ON t.sender_wallet_id=sw.wallet_id
            JOIN {table('customers')} s ON sw.customer_id=s.customer_id
            JOIN {table('wallets')} rw ON t.receiver_wallet_id=rw.wallet_id
            JOIN {table('customers')} r ON rw.customer_id=r.customer_id
            JOIN {table('devices')} d ON t.device_id=d.device_id
            WHERE t.timestamp>=TIMESTAMP('{start}') AND t.timestamp<TIMESTAMP('{end}')'''

    def provision(self,day=AS_OF):
        """Metadata only. Never adopt an unowned dataset/table or change AE data."""
        url=self.base+'/'+self.dataset
        response=self.cloud.request('GET',url)
        if response.status_code==404:
            response=self.cloud.request('POST',self.base,json={
                'datasetReference':{'projectId':self.cloud.project,'datasetId':self.dataset},
                'location':LOCATION,'defaultTableExpirationMs':str(RETENTION_MS),'labels':LABELS,
                'description':'Disposable simulator mirror of Gab f03a384 schemas; not the AE training dataset.'})
        response.raise_for_status();dataset=response.json()
        if dataset.get('labels',{}).get('purpose')!=LABELS['purpose'] or dataset.get('location','').upper()!=LOCATION:
            raise LabError('Simulator destination ownership or location differs; no table was written.',409)
        if int(dataset.get('defaultTableExpirationMs',0))!=RETENTION_MS:
            raise LabError('Simulator dataset retention differs; operator review required.',409)
        expiry=str(int(time.time()*1000)+RETENTION_MS)
        for name in (*COLUMNS,'v_agent_ledger'):
            target=url+'/tables/'+name
            response=self.cloud.request('GET',target)
            spec={'tableReference':{'projectId':self.cloud.project,'datasetId':self.dataset,'tableId':name},
                'labels':LABELS,'expirationTime':expiry}
            if name=='v_agent_ledger':spec['view']={'query':self.view_sql(day),'useLegacySql':False}
            else:
                spec['schema']={'fields':schema(name)}
                if name=='wallet_transactions':spec.update(timePartitioning={'type':'DAY','field':'timestamp'},
                    requirePartitionFilter=True,clustering={'fields':['sender_wallet_id','receiver_wallet_id']})
            if response.status_code==404:
                response=self.cloud.request('POST',url+'/tables',json=spec)
                response.raise_for_status();actual=response.json()
            else:
                response.raise_for_status();actual=response.json()
                if actual.get('labels',{}).get('purpose')!=LABELS['purpose']:
                    raise LabError('An unowned simulator table exists; overwrite refused.',409)
                if name in COLUMNS:
                    fields=[{k:f.get(k,'NULLABLE' if k=='mode' else None) for k in ('name','type','mode')}
                        for f in actual.get('schema',{}).get('fields',[])]
                    if fields!=schema(name):raise LabError('Simulator schema drift; load refused for '+name,409)
                if name=='wallet_transactions' and (actual.get('timePartitioning',{}).get('field')!='timestamp'
                        or actual.get('timePartitioning',{}).get('expirationMs') or not actual.get('requirePartitionFilter')):
                    raise LabError('Simulator partition controls differ; load refused.',409)
                patch={}
                if int(actual.get('expirationTime',0))<int(expiry)-86400*1000:patch['expirationTime']=expiry
                if name=='v_agent_ledger' and actual.get('view',{}).get('query')!=spec['view']['query']:patch['view']=spec['view']
                if patch:self.cloud.request('PATCH',target,json=patch).raise_for_status()

    def status(self):
        with self.lab.lock:
            row=self.lab.db.execute('SELECT * FROM environment_publications ORDER BY rowid DESC LIMIT 1').fetchone()
            latest=dict(row) if row else None
            if latest:
                latest['counts']=json.loads(latest['counts']);latest['jobs']=json.loads(latest['jobs'])
                latest['archive_prefix']=f'gs://{self.cloud.bucket}/exports/environment/{latest["id"]}/'
        return {'enabled':True,'project':self.cloud.project,'dataset':self.dataset,'location':LOCATION,
            'retention_days':7,'latest':latest,'daily_publication_limit':DAILY_EXPORTS}

    def publish(self):
        with self.lab.lock:
            if not self.cloud.healthy:raise LabError('Cloud state is unavailable.',503)
            # A partial mirror must never be reported as complete or overwritten by a fresh scene.
            if self.lab.db.execute("SELECT 1 FROM environment_publications WHERE status!='completed'").fetchone():
                raise LabError('Simulator publication needs operator reconciliation; no load was retried.',409)
            tables=self.data.tables();self.data.validate(tables)
            bodies={name:''.join(encoded(row)+'\n' for row in rows).encode() for name,rows in tables.items()}
            fingerprint=hashlib.sha256(encoded([CONTRACT_VERSION,tables]).encode()).hexdigest()
            prior=self.lab.db.execute('SELECT * FROM environment_publications WHERE id=?',(fingerprint,)).fetchone()
            if prior:return dict(prior)|{'replayed':True}
            count=sum(map(len,tables.values()));size=sum(map(len,bodies.values()))
            if count>MAX_EXPORT_ROWS or size>MAX_EXPORT_BYTES:raise LabError('Simulator publication exceeds its row or byte cap.',413)
            if DAILY_EXPORTS is not None and self.cloud.daily_exports(self.lab)>=DAILY_EXPORTS:raise LabError('Daily BigQuery publication limit reached.',429)
            jobs={name:'mint_env_'+fingerprint[:32]+'_'+name for name in COLUMNS}
            counts={name:len(rows) for name,rows in tables.items()};day=self.lab.clock_day
            with self.lab.db:self.lab.db.execute('INSERT INTO environment_publications VALUES(?,?,?,?,?,?,?,NULL)',
                (fingerprint,now(),'reserved',count,size,encoded(counts),encoded(jobs)))
            self.cloud.save(self.lab)  # Shared allowance is durable before any external job.
        try:
            self.provision(day)
            prefix=f'exports/environment/{fingerprint}/'
            for name,body in bodies.items():
                path=prefix+name+'.jsonl.gz';self.cloud.upload(path,gzip.compress(body,mtime=0),'0')
                load={'sourceUris':[f'gs://{self.cloud.bucket}/{path}'],
                    'destinationTable':{'projectId':self.cloud.project,'datasetId':self.dataset,'tableId':name},
                    'createDisposition':'CREATE_NEVER','writeDisposition':'WRITE_TRUNCATE',
                    'sourceFormat':'NEWLINE_DELIMITED_JSON','schema':{'fields':schema(name)},'maxBadRecords':0}
                if name=='wallet_transactions':load.update(timePartitioning={'type':'DAY','field':'timestamp'},
                    clustering={'fields':['sender_wallet_id','receiver_wallet_id']})
                response=self.cloud.request('POST',self.cloud.job_url(),json={
                    'jobReference':{'projectId':self.cloud.project,'jobId':jobs[name],'location':LOCATION},
                    'configuration':{'jobTimeoutMs':'15000','load':load}})
                response.raise_for_status();wait_job(self.cloud,jobs[name],response.json(),location=LOCATION)
            manifest={'contract':CONTRACT_VERSION,'batch_id':fingerprint,'counts':counts,'jobs':jobs,
                'private_evaluation_labels':True,'completed_at':now()}
            self.cloud.upload(prefix+'manifest.json.gz',gzip.compress(encoded(manifest).encode(),mtime=0),'0')
            with self.lab.lock,self.lab.db:
                self.lab.db.execute("UPDATE environment_publications SET status='completed',completed_at=? WHERE id=?",(manifest['completed_at'],fingerprint))
                # Only the current mirror can answer queries. Retain one bounded index,
                # so reports with newer, unpublished payments do not waste BQ queries.
                self.lab.db.execute('DELETE FROM environment_feature_coverage')
                self.lab.db.execute('INSERT INTO environment_feature_coverage VALUES(?,?)',
                    (fingerprint,encoded(sorted(r['transaction_id'] for r in tables['wallet_transactions']))))
        except Exception:
            with self.lab.lock,self.lab.db:self.lab.db.execute("UPDATE environment_publications SET status='uncertain' WHERE id=?",(fingerprint,))
            self.cloud.save(self.lab)
            raise LabError('Simulator publication stopped; its allowance is retained. No automatic retry.',503) from None
        self.cloud.save(self.lab)
        return self.status()['latest']|{'replayed':False}
