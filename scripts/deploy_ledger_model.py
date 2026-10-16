"""One bounded build and single-writer rollout of the existing Mint Town service.

Preserves IAM, credentials, budgets and ledgers. No uncertain build/deploy is resubmitted.
"""
import copy
import hashlib
import io
import json
import sys
import tarfile
import time
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'web'))
from cloud_data import CloudData
from fraud_models import manifests

PROJECT='minttown-apac-2026'
REGION='us-central1'
URL='https://minttown-1040017899050.us-central1.run.app'
SERVICE=f'https://run.googleapis.com/v2/projects/{PROJECT}/locations/{REGION}/services/minttown'
BUCKET=PROJECT+'_cloudbuild'


def main():
    assert manifests()['ledger_transaction_v1']['available'], 'Model contract is unavailable.'
    cloud=CloudData(PROJECT,BUCKET,'minttown_demo')
    def request(method,url,**kwargs):
        response=cloud.request(method,url,**kwargs);response.raise_for_status();return response.json()
    def service():return request('GET',SERVICE)
    before=service()
    if before.get('scaling',{}).get('scalingMode')!='AUTOMATIC':
        raise ValueError('Service is already stopped. Do not override an owner/cost shutdown.')
    env={v['name']:v.get('value') for v in before['template']['containers'][0]['env']}
    headers={'X-MintTown-Operator':env['MINTTOWN_RISK_OPERATOR_TOKEN']}
    def state():
        response=requests.get(URL+'/api/state',headers=headers,timeout=30);response.raise_for_status();return response.json()
    def idle():
        data=state()
        if data['demo']['running'] or data['demo']['agent_busy'] or data['demo']['restart_blocked']:
            raise ValueError('Pause the simulation and let admitted work finish before deploying.')
        assert data['budget']['daily_usd_limit']==2 and data['budget']['total_usd_limit']==8
        return data
    initial=idle()
    files=[ROOT/p for p in ('Dockerfile','.dockerignore','pyproject.toml','uv.lock')]
    files+=sorted((ROOT/'web').glob('*.py'))
    files+=sorted(p for p in (ROOT/'web/dist').rglob('*') if p.is_file())
    files+=sorted((ROOT/'web/model_artifacts').glob('*.json'))
    digest=hashlib.sha256()
    for p in files:digest.update(str(p.relative_to(ROOT)).encode()+b'\0'+p.read_bytes())
    tag='ledger-'+digest.hexdigest()[:12]
    receipt_path=ROOT/'output/ledger-training'/f'{tag}-deployment.json'
    if receipt_path.exists():
        raise ValueError('This release was already attempted; inspect its receipt, never rebuild/retry blindly.')
    image=f'{REGION}-docker.pkg.dev/{PROJECT}/minttown/minttown:{tag}'
    receipt={'tag':tag,'image':image,'previous_revision':before['latestReadyRevision'],'status':'prepared'}
    def save():receipt_path.parent.mkdir(parents=True,exist_ok=True);receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
    def wait(operation,timeout=600):
        deadline=time.monotonic()+timeout
        while not operation.get('done'):
            if time.monotonic()>deadline:raise TimeoutError('Operation still pending; inspect receipt. No retry.')
            time.sleep(4)
            operation=request('GET','https://run.googleapis.com/v2/'+operation['name'])
        if operation.get('error'):raise ValueError(operation['error'])
        return operation
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode='w:gz') as out:
        for p in files:out.add(p,arcname=str(p.relative_to(ROOT)),recursive=False)
    body=archive.getvalue();assert len(body)<8*1024*1024
    source='source/'+tag+'.tar.gz';save()
    generation=cloud.upload(source,body,'0')
    receipt.update(status='build_submission_uncertain',source_bytes=len(body));save()
    previous=before['template']['containers'][0]['image']
    op=request('POST',f'https://cloudbuild.googleapis.com/v1/projects/{PROJECT}/builds',json={
        'source':{'storageSource':{'bucket':BUCKET,'object':source,'generation':generation}},
        'steps':[{'name':'gcr.io/cloud-builders/docker','args':['pull',previous]},
                 {'name':'gcr.io/cloud-builders/docker','args':['build','--cache-from',previous,'-t',image,'.']}],
        'images':[image],'timeout':'600s','options':{'machineType':'E2_MEDIUM','logging':'CLOUD_LOGGING_ONLY'},
        'serviceAccount':f'projects/{PROJECT}/serviceAccounts/minttown-builder@{PROJECT}.iam.gserviceaccount.com'},timeout=30)
    receipt.update(status='building',build_operation=op['name'],build_id=op['metadata']['build']['id']);save()
    print(json.dumps({'status':'building','build_id':receipt['build_id'],'image':image}),flush=True)
    deadline=time.monotonic()+660
    while True:
        build=request('GET',f'https://cloudbuild.googleapis.com/v1/projects/{PROJECT}/builds/'+receipt['build_id'])
        if build['status'] not in ('QUEUED','WORKING','PENDING'):break
        if time.monotonic()>deadline:raise TimeoutError('Build still pending; inspect saved ID. No retry.')
        time.sleep(5)
    receipt['build_status']=build['status'];save()
    if build['status']!='SUCCESS':raise ValueError('Build did not succeed: '+build['status'])
    idle();current=service()
    if current['etag']!=before['etag']:raise ValueError('Service changed during build; preserve the other deployment.')
    receipt['status']='pause_submission_uncertain';save()
    op=request('PATCH',SERVICE,params={'updateMask':'scaling'},json={'name':current['name'],'etag':current['etag'],'scaling':{'scalingMode':'MANUAL','manualInstanceCount':0,'maxInstanceCount':1}},timeout=30)
    receipt['pause_operation']=op['name'];save();wait(op,240)
    time.sleep(10) # Cloud Run gives the previous process a bounded shutdown grace period.
    current=service();assert current['scaling']['scalingMode']=='MANUAL'
    containers=copy.deepcopy(current['template']['containers']);containers[0]['image']=image
    # Background world/investigation threads need CPU between HTTP requests.
    containers[0]['resources']['cpuIdle']=False
    receipt['status']='deploy_submission_uncertain';save()
    op=request('PATCH',SERVICE,params={'updateMask':'template.containers,template.scaling,scaling,traffic'},json={
        'name':current['name'],'etag':current['etag'],'template':{'containers':containers,'scaling':{'minInstanceCount':0,'maxInstanceCount':1}},
        'scaling':{'scalingMode':'AUTOMATIC','minInstanceCount':0,'maxInstanceCount':1},
        'traffic':[{'type':'TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST','percent':100}]},timeout=30)
    receipt['deploy_operation']=op['name'];save();wait(op,300)
    deployed=service();final=state()
    assert final['budget']['committed_microusd_total']>=initial['budget']['committed_microusd_total']
    assert deployed['template']['containers'][0]['image']==image
    assert deployed['scaling'].get('minInstanceCount',0)==0 and deployed['scaling']['maxInstanceCount']==1
    receipt.update(status='deployed',revision=deployed['latestReadyRevision'],scaling=deployed['scaling'],
                   spend_preserved=True,models_usd=final['budget']['committed_usd_total'],url=URL)
    save();print(json.dumps(receipt,indent=2),flush=True)


if __name__=='__main__':main()
