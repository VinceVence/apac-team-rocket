"""Bounded, fake-only team demo persistence and batch analytics on Google Cloud.

One writer checkpoints SQLite to a generation-checked GCS object. This is a small
demo store, not a distributed SQL database. A conflict or ambiguous write fails
closed; Cloud Run's liveness probe replaces the instance and reloads the object.
"""
import gzip
import hashlib
import io
import json
import os
import time
from pathlib import Path
from urllib.parse import quote, urlencode

from lab import LabError, encoded, now

MAX_STATE_BYTES = 64 * 1024 * 1024
MAX_EXPORT_BYTES = 16 * 1024 * 1024
MAX_EXPORT_ROWS = 20000
DAILY_EXPORTS = 3
SOURCE_TABLES = ('customers', 'accounts', 'financial_events', 'ledger_entries')


class CloudData:
    def __init__(self, project, bucket, dataset, location='us-central1', session=None):
        self.project, self.bucket, self.dataset, self.location = project, bucket, dataset, location
        if not all((project, bucket, dataset)): raise ValueError('Cloud project, state bucket and BigQuery dataset are required.')
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
        response = self.session.request(method, url, timeout=20, **kwargs)
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
        with lab.lock, lab.db:
            lab.db.execute('''CREATE TABLE IF NOT EXISTS cloud_exports(
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL,
                row_count INTEGER NOT NULL, size_bytes INTEGER NOT NULL, job_id TEXT NOT NULL)''')
        self.save(lab)

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
                self.generation = self.upload(self.state_object, gzip.compress(data, mtime=0), self.generation)
            except Exception:
                self.healthy = False
                raise LabError('Cloud checkpoint could not be confirmed. This instance stopped accepting changes; no overwrite or retry was attempted.', 503) from None
            self.last_hash = digest

    def status(self, lab):
        with lab.lock:
            exports = lab.rows('SELECT * FROM cloud_exports ORDER BY created_at DESC LIMIT 5')
            today = lab.db.execute('SELECT count(*) FROM cloud_exports WHERE substr(created_at,1,10)=?', (now()[:10],)).fetchone()[0]
        return {'enabled':True, 'healthy':self.healthy, 'project':self.project, 'dataset':self.dataset,
                'table':'simulation_records', 'daily_exports':today, 'daily_export_limit':DAILY_EXPORTS,
                'exports':exports, 'gemini':'disabled in the hosted demo'}

    def export(self, lab):
        with lab.lock:
            if not self.healthy: raise LabError('Cloud state is unavailable.', 503)
            records = []
            for table in SOURCE_TABLES:
                for row in lab.rows('SELECT * FROM ' + table + ' ORDER BY id LIMIT ?', (MAX_EXPORT_ROWS + 1,)):
                    records.append({'source_table':table, 'record_id':str(row['id']),
                                    'customer_id':row.get('customer_id') or (row['id'] if table=='customers' else None), 'payload':row})
                    if len(records) > MAX_EXPORT_ROWS: raise LabError('Export row cap reached. This demo exports at most 20,000 records.', 413)
            batch_id = hashlib.sha256(encoded(records).encode()).hexdigest()
            prior = lab.db.execute('SELECT * FROM cloud_exports WHERE id=?', (batch_id,)).fetchone()
            if prior: return dict(prior) | {'replayed':True}
            if lab.db.execute('SELECT count(*) FROM cloud_exports WHERE substr(created_at,1,10)=?', (now()[:10],)).fetchone()[0] >= DAILY_EXPORTS:
                raise LabError('Daily BigQuery export limit reached.', 429)
            stamp = now(); job_id = 'minttown_' + batch_id
            body = '\n'.join(encoded(dict(r, batch_id=batch_id, exported_at=stamp)) for r in records).encode()
            if len(body) > MAX_EXPORT_BYTES: raise LabError('Export exceeds the 16 MiB payload cap.', 413)
            with lab.db:
                lab.db.execute('INSERT INTO cloud_exports VALUES(?,?,?,?,?,?)', (batch_id, stamp, 'reserved', len(records), len(body), job_id))
            self.save(lab)  # Reserve the daily allowance before any external batch job.
        try:
            object_name = 'exports/' + batch_id + '.jsonl.gz'
            self.upload(object_name, gzip.compress(body, mtime=0), '0')
            job_url = 'https://bigquery.googleapis.com/bigquery/v2/projects/%s/jobs' % quote(self.project, safe='')
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
        return {'id':batch_id,'status':state,'row_count':len(records),'size_bytes':len(body),'job_id':job_id,'replayed':False}
