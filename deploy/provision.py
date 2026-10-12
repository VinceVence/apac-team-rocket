"""Apply the approved MintTown demo resources. No build, deployment or model calls.

Run from the repository root with local ADC configured. Without --apply, this
prints the plan only. Existing IAM bindings are preserved using their etags.
"""
import argparse
import json
import time
from pathlib import Path

import google.auth
from google.auth.transport.requests import AuthorizedSession


class Provisioner:
    def __init__(self, plan):
        self.plan = plan
        self.project, self.region = plan['project'], plan['region']
        credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        self.http = AuthorizedSession(credentials)
        project = self.call('GET', 'https://cloudresourcemanager.googleapis.com/v1/projects/' + self.project)
        self.number = project['projectNumber']
        self.receipt = {'project': self.project, 'project_number': self.number}

    def call(self, method, url, body=None, allow_missing=False, **kwargs):
        response = self.http.request(method, url, json=body, timeout=30, **kwargs)
        if response.status_code == 404 and allow_missing: return None
        if not response.ok:
            raise RuntimeError('%s %s: %s %s' % (method, url, response.status_code, response.text[:1200]))
        return response.json() if response.content else {}

    def wait(self, host, operation):
        for _ in range(30):
            if operation.get('done'):
                if operation.get('error'): raise RuntimeError(str(operation['error']))
                return operation.get('response', {})
            time.sleep(1)
            operation = self.call('GET', host + '/' + operation['name'])
        raise RuntimeError('Operation still pending: ' + operation['name'])

    def bind(self, get_url, set_url, role, member, method='POST', wrapped=True, get_method=None):
        read_method = get_method or ('GET' if method == 'PUT' else 'POST')
        policy = self.call(read_method, get_url, None if read_method=='GET' else {})
        bindings = policy.setdefault('bindings', [])
        binding = next((b for b in bindings if b['role']==role and not b.get('condition')), None)
        if binding is None: binding={'role':role,'members':[]}; bindings.append(binding)
        if member in binding['members']: return
        binding['members'].append(member)
        self.call(method, set_url, {'policy':policy} if wrapped else policy)

    def controls(self):
        billing = self.call('GET', 'https://cloudbilling.googleapis.com/v1/projects/' + self.project + '/billingInfo')
        if not billing.get('billingEnabled'): raise RuntimeError('Project billing is not enabled.')
        url = 'https://billingbudgets.googleapis.com/v1/' + billing['billingAccountName'] + '/budgets'
        existing = self.call('GET', url).get('budgets', [])
        for title, amount, service in [('MintTown Cloud Run - USD 1 monthly cap', 1, '152E-C115-5142'),
                                       ('MintTown whole project - USD 5 alert', 5, None)]:
            desired = {'displayName':title,'budgetFilter':{'projects':['projects/'+self.number],
                'calendarPeriod':'MONTH','creditTypesTreatment':'EXCLUDE_ALL_CREDITS'},
                'amount':{'specifiedAmount':{'currencyCode':'USD','units':str(amount)}},
                'thresholdRules':[{'thresholdPercent':p} for p in (.5,.8,1)],
                'notificationsRule':{'enableProjectLevelRecipients':True}}
            if service:
                desired['budgetFilter']['services']=['services/'+service]
                desired['spendCap']={'inputState':'CONFIGURED'}
            found=next((b for b in existing if b['displayName']==title),None)
            if found is None: found=self.call('POST',url,desired)
            found=self.call('GET','https://billingbudgets.googleapis.com/v1/'+found['name'])
            if found['budgetFilter']['projects'] not in (['projects/'+self.number],['projects/'+self.project]): raise RuntimeError('Budget project mismatch.')
            if int(found['amount']['specifiedAmount'].get('units',0))!=amount:raise RuntimeError('Existing budget amount differs; not changing it silently.')
            if service and (found.get('spendCap',{}).get('outputState')!='CONFIGURED' or found['budgetFilter'].get('services')!=['services/'+service]):raise RuntimeError('Cloud Run cap is not configured for the expected service.')
            self.receipt['cloud_run_budget' if service else 'project_alert']={'name':found['name'],'usd':amount,'state':found.get('spendCap',{}).get('outputState','ALERT_ONLY')}
            print(title + ': verified', flush=True)
        quota_base='https://serviceusage.googleapis.com/v1beta1/projects/'+self.number+'/services/bigquery.googleapis.com/consumerQuotaMetrics'
        metrics=self.call('GET',quota_base,params={'view':'FULL','pageSize':200})
        metric=next(m for m in metrics['metrics'] if m['metric']=='bigquery.googleapis.com/quota/query/usage')
        if metric['unit']!='MiBy':raise RuntimeError('Unexpected BigQuery quota unit; refusing an unverified limit.')
        limit=next(l for l in metric['consumerQuotaLimits'] if l['unit']=='1/d/{project}')
        bucket=next(b for b in limit['quotaBuckets'] if not b.get('dimensions'))
        override=bucket.get('consumerOverride')
        if int(bucket['effectiveLimit'])>1024:
            if override:
                operation=self.call('PATCH','https://serviceusage.googleapis.com/v1beta1/'+override['name'],{'overrideValue':'1024'},params={'force':'true'})
            else:
                operation=self.call('POST','https://serviceusage.googleapis.com/v1beta1/'+limit['name']+'/consumerOverrides',{'overrideValue':'1024'},params={'force':'true'})
            self.wait('https://serviceusage.googleapis.com/v1beta1',operation)
        verified=self.call('GET','https://serviceusage.googleapis.com/v1beta1/'+metric['name'],params={'view':'FULL'})
        daily=next(l for l in verified['consumerQuotaLimits'] if l['unit']=='1/d/{project}')
        effective=int(next(b for b in daily['quotaBuckets'] if not b.get('dimensions'))['effectiveLimit'])
        if effective>1024:raise RuntimeError('BigQuery daily quota was not applied.')
        self.receipt['bigquery_query_mib_per_day']=effective
        print('BigQuery query quota: %d MiB/day verified' % effective,flush=True)

    def resources(self):
        accounts={}
        for key in ('runtime_service_account','build_service_account'):
            account_id=self.plan[key]; email=account_id+'@'+self.project+'.iam.gserviceaccount.com'
            url='https://iam.googleapis.com/v1/projects/'+self.project+'/serviceAccounts/'+email
            if self.call('GET',url,allow_missing=True) is None:
                self.call('POST','https://iam.googleapis.com/v1/projects/'+self.project+'/serviceAccounts',{'accountId':account_id,'serviceAccount':{'displayName':account_id}})
            accounts[key]=email
        runtime,builder=accounts['runtime_service_account'],accounts['build_service_account']
        self.receipt.update(accounts)
        bucket=self.plan['state_bucket']; bucket_url='https://storage.googleapis.com/storage/v1/b/'+bucket
        if self.call('GET',bucket_url,allow_missing=True) is None:
            self.call('POST','https://storage.googleapis.com/storage/v1/b',{
                'name':bucket,'location':self.region,'storageClass':'STANDARD','versioning':{'enabled':False},
                'softDeletePolicy':{'retentionDurationSeconds':'0'},
                'iamConfiguration':{'uniformBucketLevelAccess':{'enabled':True},'publicAccessPrevention':'enforced'},
                'lifecycle':{'rule':[{'action':{'type':'Delete'},'condition':{'age':1,'matchesPrefix':['build/']}},
                                     {'action':{'type':'Delete'},'condition':{'age':7,'matchesPrefix':['exports/']}}]}},params={'project':self.project})
        saved=self.call('GET',bucket_url)
        if saved.get('versioning',{}).get('enabled') or int(saved.get('softDeletePolicy',{}).get('retentionDurationSeconds',0))!=0:raise RuntimeError('Bucket retention does not match the bounded-storage plan.')
        for email,role in ((runtime,'roles/storage.objectAdmin'),(builder,'roles/storage.objectViewer')):
            self.bind(bucket_url+'/iam',bucket_url+'/iam',role,'serviceAccount:'+email,method='PUT',wrapped=False)
        project_url='https://cloudresourcemanager.googleapis.com/v1/projects/'+self.project
        for email,role in ((runtime,'roles/bigquery.jobUser'),(builder,'roles/logging.logWriter')):
            self.bind(project_url+':getIamPolicy',project_url+':setIamPolicy',role,'serviceAccount:'+email)
        dataset=self.plan['bigquery_dataset']; bq='https://bigquery.googleapis.com/bigquery/v2/projects/'+self.project+'/datasets'
        if self.call('GET',bq+'/'+dataset,allow_missing=True) is None:
            self.call('POST',bq,{'datasetReference':{'projectId':self.project,'datasetId':dataset},'location':self.region,
                'maxTimeTravelHours':'48','defaultPartitionExpirationMs':'604800000',
                'access':[{'role':'OWNER','specialGroup':'projectOwners'},{'role':'WRITER','userByEmail':runtime}]})
        tables=bq+'/'+dataset+'/tables'
        if self.call('GET',tables+'/simulation_records',allow_missing=True) is None:
            self.call('POST',tables,{'tableReference':{'projectId':self.project,'datasetId':dataset,'tableId':'simulation_records'},
                'schema':{'fields':[{'name':name,'type':typ,'mode':mode} for name,typ,mode in (
                    ('batch_id','STRING','REQUIRED'),('exported_at','TIMESTAMP','REQUIRED'),('source_table','STRING','REQUIRED'),
                    ('record_id','STRING','REQUIRED'),('customer_id','STRING','NULLABLE'),('payload','JSON','REQUIRED'))]},
                'timePartitioning':{'type':'DAY','field':'exported_at','expirationMs':'604800000'},
                'requirePartitionFilter':True,'clustering':{'fields':['source_table','customer_id']}})
        repo_id=self.plan['artifact_repository']
        repos='https://artifactregistry.googleapis.com/v1/projects/'+self.project+'/locations/'+self.region+'/repositories'
        repo=repos+'/'+repo_id
        if self.call('GET',repo,allow_missing=True) is None:
            operation=self.call('POST',repos,{'format':'DOCKER','description':'MintTown bounded team demo',
                'cleanupPolicyDryRun':False,'cleanupPolicies':{
                    'keep-recent':{'id':'keep-recent','action':'KEEP','mostRecentVersions':{'keepCount':2}},
                    'remove-old':{'id':'remove-old','action':'DELETE','condition':{'olderThan':'86400s','tagState':'ANY'}}}},params={'repositoryId':repo_id})
            self.wait('https://artifactregistry.googleapis.com/v1',operation)
        self.bind(repo+':getIamPolicy',repo+':setIamPolicy','roles/artifactregistry.writer','serviceAccount:'+builder,get_method='GET')
        policy=self.call('POST',project_url+':getIamPolicy',{})
        roles=[b['role'] for b in policy.get('bindings',[]) if 'serviceAccount:'+runtime in b.get('members',[])]
        if roles!=['roles/bigquery.jobUser']:raise RuntimeError('Unexpected project-level runtime roles: '+str(roles))
        self.receipt.update(state_bucket=bucket,bigquery_dataset=dataset,artifact_repository=repo_id,runtime_project_roles=roles)
        print('Storage, BigQuery, repository and scoped service accounts: ready',flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    plan=json.loads(Path('deploy/plan.json').read_text())
    if not args.apply: print(json.dumps(plan,indent=2));return
    provision=Provisioner(plan)
    provision.controls()
    provision.resources()
    target=Path('output/google-cloud/provisioned-resources.json');target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(provision.receipt,indent=2)+'\n')
    print(json.dumps(provision.receipt,indent=2))


if __name__=='__main__':main()
