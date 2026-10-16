"""One read-only BigQuery export, capped before submission; uncertain jobs are never retried."""
import argparse
import csv
import hashlib
import json
import time
import uuid
from pathlib import Path
from cloud_data import CloudData

MAX_BYTES = 50*1024*1024
MAX_ROWS = 20000
PROJECT = 'minttown-apac-2026'


def export(destination):
    receipt_path = destination.with_suffix('.receipt.json')
    if receipt_path.exists() or destination.exists():
        raise ValueError('An export already exists. Inspect its receipt; do not resubmit an uncertain job.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    query = (Path(__file__).resolve().parents[1]/'sql/ledger_fraud_export_simulated_env.sql').read_text()
    cloud = CloudData(PROJECT, PROJECT+'-demo-state', 'minttown_simulated_env', location='US')
    base = f'https://bigquery.googleapis.com/bigquery/v2/projects/{PROJECT}'
    config = {'query':query,'useLegacySql':False,'maximumBytesBilled':str(MAX_BYTES),'useQueryCache':True}
    response = cloud.request('POST',base+'/jobs',json={'configuration':{'dryRun':True,'query':config},'jobReference':{'projectId':PROJECT,'location':'US'}},timeout=25)
    response.raise_for_status(); dry = response.json()
    if dry.get('status',{}).get('errorResult'):
        raise ValueError(dry['status']['errorResult'])
    estimated = int(dry.get('statistics',{}).get('query',{}).get('totalBytesProcessed',dry.get('statistics',{}).get('totalBytesProcessed',0)))
    if estimated > MAX_BYTES:
        raise ValueError(f'Export exceeds {MAX_BYTES} byte cap: {estimated}')
    job = 'minttown_ledger_'+uuid.uuid4().hex
    receipt = {'job_id':job,'location':'US','sql_sha256':hashlib.sha256(query.encode()).hexdigest(),
               'estimated_bytes':estimated,'maximum_bytes_billed':MAX_BYTES,'max_rows':MAX_ROWS,'status':'submission_uncertain'}
    def save():receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
    save()
    response = cloud.request('POST',base+'/jobs',json={'configuration':{'query':config,'jobTimeoutMs':'60000'},'jobReference':{'projectId':PROJECT,'location':'US','jobId':job},'labels':{'app':'minttown','purpose':'ledger-training'}},timeout=25)
    response.raise_for_status(); result = response.json()
    deadline = time.monotonic()+90
    while result.get('status',{}).get('state') != 'DONE':
        if time.monotonic() > deadline:
            raise TimeoutError('Export observer timed out; inspect the saved job ID. No retry.')
        time.sleep(1)
        response = cloud.request('GET',base+'/jobs/'+job,params={'location':'US'},timeout=15)
        response.raise_for_status(); result=response.json()
    if result.get('status',{}).get('errorResult'):
        receipt.update(status='failed',error=result['status']['errorResult']);save();raise ValueError(receipt['error'])
    stats=result.get('statistics',{}).get('query',{})
    receipt.update(status='completed',bytes_processed=stats.get('totalBytesProcessed'),bytes_billed=stats.get('totalBytesBilled'),cache_hit=stats.get('cacheHit',False));save()
    output=[];token=None;fields=None
    for _ in range(4):
        params={'location':'US','maxResults':10000}
        if token:params['pageToken']=token
        response=cloud.request('GET',base+'/queries/'+job,params=params,timeout=20);response.raise_for_status();page=response.json()
        if int(page.get('totalRows',0)) > MAX_ROWS:
            raise ValueError('Export row cap exceeded; no artifact will be trained.')
        fields=[f['name'] for f in page['schema']['fields']]
        output.extend([[v['v'] for v in r['f']] for r in page.get('rows',[])])
        token=page.get('pageToken')
        if not token:break
    if token or len(output)>MAX_ROWS:
        raise ValueError('Incomplete or oversized export.')
    # BigQuery REST serializes TIMESTAMP as epoch seconds; retain an explicit UTC cutoff.
    import datetime as dt
    idx=fields.index('event_timestamp')
    for row in output:row[idx]=dt.datetime.fromtimestamp(float(row[idx]),dt.timezone.utc).isoformat().replace('+00:00','Z')
    with destination.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.writer(handle);writer.writerow(fields);writer.writerows(output)
    receipt.update(rows=len(output),csv_sha256=hashlib.sha256(destination.read_bytes()).hexdigest());save()
    print(json.dumps(receipt,indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    export(parser.parse_args().output)
