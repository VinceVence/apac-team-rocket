"""Bounded demo persistence and batch analytics on Google Cloud.

One writer checkpoints SQLite to a generation-checked GCS object. This is a small
demo store, not a distributed SQL database. A conflict or ambiguous write fails
closed; Cloud Run's liveness probe replaces the instance and reloads the object.
"""
import gzip
import hashlib
import io
import json
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import quote, urlencode

from lab import LabError, encoded, now
from settings import DAILY_PUBLICATIONS

MAX_STATE_BYTES = 64 * 1024 * 1024
MAX_EXPORT_BYTES = 16 * 1024 * 1024
MAX_EXPORT_ROWS = 20000
DAILY_EXPORTS = DAILY_PUBLICATIONS


class CloudData:
    def __init__(self, project, bucket, dataset, location='us-central1', session=None):
        self.project, self.bucket, self.dataset, self.location = project, bucket, dataset, location
        if not all((project, bucket, dataset)): raise ValueError('Cloud project, state bucket and BigQuery dataset are required.')
        self.checkpoint_interval=1.1 if session is None else 0.0
        self.next_checkpoint_at=0.0
        if session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            session = AuthorizedSession(credentials)
        self.session = session
        self.generation, self.last_hash, self.healthy = '0', None, True
        self.state_object = 'state/minttown.sqlite3.gz'

    @classmethod
    def environment(cls):
        return cls(os.environ['GOOGLE_CLOUD_PROJECT'], os.environ['MINTTOWN_STATE_BUCKET'],
                   os.environ['MINTTOWN_BQ_DATASET'], os.getenv('MINTTOWN_DATA_LOCATION', 'us-central1'))

    def object_url(self, name):
        return 'https://storage.googleapis.com/storage/v1/b/%s/o/%s' % (quote(self.bucket, safe=''), quote(name, safe=''))

    def request(self, method, url, **kwargs):
        response = self.session.request(method, url, timeout=kwargs.pop('timeout',20), **kwargs)
        return response

    def upload(self, name, body, generation):
        query = urlencode({'uploadType':'media', 'name':name, 'ifGenerationMatch':generation})
        url = 'https://storage.googleapis.com/upload/storage/v1/b/%s/o?%s' % (quote(self.bucket, safe=''), query)
        response = self.request('POST', url, data=body, headers={'Content-Type':'application/gzip'})
        response.raise_for_status()
        return response.json()['generation']

    def restore(self, path):
        meta = self.request('GET', self.object_url(self.state_object))
        if meta.status_code == 404: return
        meta.raise_for_status(); self.generation = meta.json()['generation']
        response = self.request('GET', self.object_url(self.state_object), params={'alt':'media','generation':self.generation})
        response.raise_for_status()
        with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as archive: data = archive.read(MAX_STATE_BYTES + 1)
        if len(data) > MAX_STATE_BYTES or not data.startswith(b'SQLite format 3\x00'):
            raise ValueError('The saved demo database is invalid or exceeds its size cap.')
        Path(path).write_bytes(data); self.last_hash = hashlib.sha256(data).hexdigest()

    def initialize(self, lab):
        self.initialize_schema(lab)
        self.save(lab)

    @staticmethod
    def initialize_schema(lab):
        with lab.lock, lab.db:
            lab.db.execute('''CREATE TABLE IF NOT EXISTS cloud_exports(
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL,
                row_count INTEGER NOT NULL, size_bytes INTEGER NOT NULL, job_id TEXT NOT NULL)''')
            columns = {row['name'] for row in lab.db.execute('PRAGMA table_info(cloud_exports)')}
            for name, definition in {'request_id':'TEXT', 'event_start':'INTEGER NOT NULL DEFAULT 0',
                                     'event_end':'INTEGER NOT NULL DEFAULT 0', 'event_count':'INTEGER NOT NULL DEFAULT 0',
                                     'profile_hash':"TEXT NOT NULL DEFAULT ''"}.items():
                if name not in columns: lab.db.execute('ALTER TABLE cloud_exports ADD COLUMN ' + name + ' ' + definition)
            lab.db.execute('CREATE UNIQUE INDEX IF NOT EXISTS cloud_export_request ON cloud_exports(request_id)')
            lab.db.execute('CREATE INDEX IF NOT EXISTS ledger_event ON ledger_entries(event_id)')

    def save(self, lab):
        with lab.lock:
            if not self.healthy: raise LabError('Cloud state is unavailable. Retry after this instance restarts.', 503)
            if lab.db.in_transaction: raise RuntimeError('Checkpoint only after committing the local transaction.')
            data = lab.db.serialize()
            if len(data) > MAX_STATE_BYTES:
                self.healthy = False
                raise LabError('The hosted demo reached its database size cap. Export and archive data before continuing.', 507)
            digest = hashlib.sha256(data).hexdigest()
            if digest == self.last_hash: return
            try:
                # Serialize bursts of writes to this single GCS object, without
                # retrying uncertain writes or skipping durable reservations.
                delay=self.next_checkpoint_at-time.monotonic()
                if delay>0:time.sleep(delay)
                self.generation = self.upload(self.state_object, gzip.compress(data, compresslevel=1, mtime=0), self.generation)
                self.next_checkpoint_at=time.monotonic()+self.checkpoint_interval
            except Exception:
                self.healthy = False
                logging.getLogger(__name__).exception('Canonical cloud checkpoint failed; writer fenced')
                raise LabError('Cloud checkpoint could not be confirmed. This instance stopped accepting changes; no overwrite or retry was attempted.', 503) from None
            self.last_hash = digest

    def status(self, lab):
        with lab.lock:
            exports = lab.rows('SELECT * FROM cloud_exports WHERE row_count>0 ORDER BY rowid DESC LIMIT 5')
            today = self.daily_exports(lab)
            cursor = self.cursor(lab)
            pending = lab.db.execute('SELECT count(*) FROM financial_events WHERE rowid>?', (cursor,)).fetchone()[0]
        return {'enabled':True, 'healthy':self.healthy, 'project':self.project, 'dataset':self.dataset,
                'table':'simulation_records', 'daily_exports':today, 'daily_export_limit':DAILY_EXPORTS,
                'pending_events':pending, 'exports':exports, 'gemini':'disabled in the hosted demo'}

    def daily_exports(self, lab):
        count=lab.db.execute('SELECT count(*) FROM cloud_exports WHERE row_count>0 AND substr(created_at,1,10)=?', (now()[:10],)).fetchone()[0]
        if lab.db.execute("SELECT 1 FROM sqlite_master WHERE name='warehouse_snapshots'").fetchone():
            count+=lab.db.execute('SELECT count(*) FROM warehouse_snapshots WHERE substr(created_at,1,10)=?',(now()[:10],)).fetchone()[0]
        if lab.db.execute("SELECT 1 FROM sqlite_master WHERE name='demo_usage_archive'").fetchone():
            count+=lab.db.execute('SELECT coalesce(sum(publications),0) FROM demo_usage_archive WHERE day=?',(now()[:10],)).fetchone()[0]
        return count

    def cursor(self, lab):
        return lab.db.execute("SELECT coalesce(max(event_end),0) FROM cloud_exports WHERE status='completed'").fetchone()[0]

    def reconcile(self, lab):
        # Unknown submissions keep their allowance. Only a terminal job receipt can release the cursor.
        for row in lab.rows("SELECT * FROM cloud_exports WHERE status IN ('reserved','submitted','uncertain')"):
            try:
                response = self.request('GET', self.job_url() + '/' + row['job_id'], params={'location':self.location})
                response.raise_for_status(); job = response.json()
                if job.get('status', {}).get('state') != 'DONE': continue
                state = 'failed' if job['status'].get('errorResult') else 'completed'
            except Exception: continue
            with lab.db: lab.db.execute('UPDATE cloud_exports SET status=? WHERE id=?', (state,row['id']))
            self.save(lab)

    def job_url(self):
        return 'https://bigquery.googleapis.com/bigquery/v2/projects/%s/jobs' % quote(self.project, safe='')

    def receipt(self, lab, batch_id, replayed):
        row = dict(lab.db.execute('SELECT * FROM cloud_exports WHERE id=?', (batch_id,)).fetchone())
        remaining = lab.db.execute('SELECT count(*) FROM financial_events WHERE rowid>?', (row['event_end'],)).fetchone()[0]
        return row | {'replayed':replayed, 'remaining_events':remaining}

    def export(self, lab, request_id):
        if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', request_id):
            raise LabError('A valid export request ID is required.')
        with lab.lock:
            if not self.healthy: raise LabError('Cloud state is unavailable.', 503)
            self.reconcile(lab)
            prior = lab.db.execute('SELECT id FROM cloud_exports WHERE request_id=?', (request_id,)).fetchone()
            if prior: return self.receipt(lab, prior['id'], True)
            if lab.db.execute("SELECT 1 FROM cloud_exports WHERE status IN ('reserved','submitted','uncertain')").fetchone():
                raise LabError('The previous export is still unconfirmed. Retry its request ID; no new batch was submitted.', 409)
            start = end = self.cursor(lab)
            stamp = now(); event_count = size = 0
            records = []
            def record(table, row):
                return {'source_table':table, 'record_id':str(row['id']),
                        'customer_id':row.get('customer_id') or (row['id'] if table=='customers' else None), 'payload':row}
            def bytes_used(rows):
                return sum(len(encoded(dict(r, batch_id='0'*64, exported_at=stamp)).encode()) + 1 for r in rows)
            for table in ('customers','accounts'):
                for row in lab.rows('SELECT * FROM ' + table + ' ORDER BY id LIMIT ?', (MAX_EXPORT_ROWS + 1,)):
                    records.append(record(table, row))
                    if len(records)>MAX_EXPORT_ROWS: raise LabError('Customer/account snapshots exceed the export row cap.', 413)
            size = bytes_used(records)
            if size>MAX_EXPORT_BYTES: raise LabError('Customer/account snapshots exceed the 16 MiB payload cap.', 413)
            profile_hash = hashlib.sha256(encoded(records).encode()).hexdigest()
            # ponytail: one bounded SQLite snapshot under the lab lock; use CDC before scaling this demo.
            for row in lab.rows('SELECT rowid AS cursor,* FROM financial_events WHERE rowid>? ORDER BY rowid LIMIT ?', (start,MAX_EXPORT_ROWS+1)):
                event_end = row.pop('cursor')
                legs = lab.rows('SELECT * FROM ledger_entries WHERE event_id=? ORDER BY id LIMIT ?', (row['id'],MAX_EXPORT_ROWS+1))
                group = [record('financial_events',row)] + [record('ledger_entries',leg) for leg in legs]
                group_size = bytes_used(group)
                if len(records)+len(group)>MAX_EXPORT_ROWS or size+group_size>MAX_EXPORT_BYTES:
                    if not event_count: raise LabError('One complete transaction exceeds the export row cap or 16 MiB payload cap.', 413)
                    break
                records.extend(group); size += group_size; end = event_end; event_count += 1
            latest = lab.db.execute("SELECT profile_hash FROM cloud_exports WHERE status='completed' ORDER BY rowid DESC LIMIT 1").fetchone()
            if not event_count and latest and latest['profile_hash']==profile_hash:
                records=[]  # Persist an idempotent no-op receipt without consuming a load-job allowance.
            if records and self.daily_exports(lab)>=DAILY_EXPORTS:
                raise LabError('Daily BigQuery export limit reached.', 429)
            batch_id = hashlib.sha256(encoded([request_id,start,end,records]).encode()).hexdigest()
            job_id = 'minttown_' + batch_id if records else ''
            body = '\n'.join(encoded(dict(r, batch_id=batch_id, exported_at=stamp)) for r in records).encode()
            with lab.db:
                lab.db.execute('''INSERT INTO cloud_exports(id,created_at,status,row_count,size_bytes,job_id,
                    request_id,event_start,event_end,event_count,profile_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                    (batch_id,stamp,'reserved' if records else 'completed',len(records),len(body),job_id,request_id,start,end,event_count,profile_hash))
            self.save(lab)  # Reserve the daily allowance before any external batch job.
            if not records: return self.receipt(lab,batch_id,False)
        try:
            object_name = 'exports/' + batch_id + '.jsonl.gz'
            self.upload(object_name, gzip.compress(body, mtime=0), '0')
            job_url = self.job_url()
            response = self.request('POST', job_url, json={
                'jobReference':{'projectId':self.project,'jobId':job_id,'location':self.location},
                'configuration':{'load':{'sourceUris':['gs://' + self.bucket + '/' + object_name],
                    'destinationTable':{'projectId':self.project,'datasetId':self.dataset,'tableId':'simulation_records'},
                    'createDisposition':'CREATE_NEVER','writeDisposition':'WRITE_APPEND','sourceFormat':'NEWLINE_DELIMITED_JSON'}}})
            response.raise_for_status(); job = response.json()
            for _ in range(8):
                if job.get('status', {}).get('state') == 'DONE': break
                time.sleep(.25)
                response = self.request('GET', job_url + '/' + job_id, params={'location':self.location})
                response.raise_for_status(); job = response.json()
            state = 'failed' if job.get('status', {}).get('errorResult') else 'completed' if job.get('status', {}).get('state') == 'DONE' else 'submitted'
        except Exception:
            state = 'uncertain'  # Keep the reservation and deterministic job ID; never blindly resubmit.
        with lab.lock, lab.db:
            lab.db.execute('UPDATE cloud_exports SET status=? WHERE id=?', (state, batch_id))
        self.save(lab)
        with lab.lock: return self.receipt(lab,batch_id,False)
