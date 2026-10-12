"""Run the actual hosted API with a short-lived IAP JWT; never enables Gemini.

The caller supplies an already-authorized service account. This script grants no
permissions, creates no keys, resets no budgets, and retries no mutation.
Reuse --run-id after interruption to resume the same reports.
"""
import argparse
import json
import time
from pathlib import Path

import google.auth
import requests
from google.auth.transport.requests import AuthorizedSession

from fraud_desk import LESSON, QUESTION

BASE = 'https://minttown-1040017899050.us-central1.run.app'
PROJECT = 'minttown-apac-2026'


def iap_token(service_account):
    if not service_account.endswith('@'+PROJECT+'.iam.gserviceaccount.com'):
        raise ValueError('Use a dedicated MintTown service account.')
    session = AuthorizedSession(google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])[0])
    stamp = int(time.time())
    claims = {'iss':service_account,'sub':service_account,'aud':BASE+'/*','iat':stamp,'exp':stamp+900}
    response = session.post('https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/'+service_account+':signJwt',
                            json={'payload':json.dumps(claims)}, timeout=30)
    response.raise_for_status()
    return response.json()['signedJwt']


def rehearse(call, run_id, save):
    initial = call('/api/state'); dashboard = call('/api/fraud-desk')
    assert not initial['budget']['live_enabled'] and not dashboard['agent_runtime']['live_enabled']
    before_live = initial['budget']['calls_today']
    result = {'host':BASE,'run_id':run_id,'mode':'ADK with fake model; no live reasoning evaluation',
              'initial_memory_ids':[m['id'] for m in dashboard['memories']]}

    def checkpoint(key, value):
        result[key]=value;save(result);return value

    def settled(report_id):
        # Read-only polling backs off and stops. The server owns every model turn.
        deadline = time.monotonic()+180; delay = 1
        while time.monotonic()<deadline:
            detail = call('/api/fraud-desk/reports/'+report_id)
            run = detail['investigation']
            if run and run['context'].get('execution',{}).get('status') not in ('queued','running'):
                return detail
            time.sleep(delay);delay=min(5,delay*1.5)
        raise TimeoutError('Hosted investigation did not finish within 180 seconds; no retry was submitted.')

    first = call('/api/fraud-desk/demo',{'scenario':'first','request_id':run_id+'-first'})
    if not first.get('reviews'):
        call('/api/fraud-agent/start',{'report_id':first['id'],'mode':'fake'})
        first = checkpoint('first_before_review',settled(first['id']))
        assert first['investigation']['status']=='awaiting_review', first['investigation']['context'].get('stop_reason')
    review = {'report_id':first['id'],'investigation_id':first['investigation']['id'],
              'disposition':'confirmed_scam','action':'request_recall',
              'note':'Programmatic demo analyst verified the synthetic impersonation report and recorded transfer.',
              'publish_memory':True,'lesson':LESSON,'next_question':QUESTION}
    approved = checkpoint('first_approved',call('/api/fraud-desk/review',review))
    assert approved['status']=='resolved' and approved['reviews'][0]['resolution']['simulated']
    # Verify exact review replay cannot publish another memory or another receipt.
    replay = call('/api/fraud-desk/review',review)
    assert replay['reviews']==approved['reviews']
    memory = next(m for m in call('/api/fraud-desk')['memories'] if m['source_report_id']==first['id'])
    checkpoint('approved_memory',memory)

    second = call('/api/fraud-desk/demo',{'scenario':'repeat','request_id':run_id+'-second'})
    if not second['investigation']:
        call('/api/fraud-agent/start',{'report_id':second['id'],'mode':'fake'})
    second = settled(second['id'])
    if second['investigation']['status']=='awaiting_customer':
        checkpoint('second_before_reply',second)
        assert second['investigation']['context']['pending_question']==QUESTION
        call('/api/fraud-desk/reply',{'report_id':second['id'],'expected_revision':second['revision'],
            'answer':'Yes. The caller said to keep this secret from bank staff.'})
        second = settled(second['id'])
    checkpoint('second_after_reply',second)
    run = second['investigation']; trail = second['decision_trail']
    assert run['status']=='awaiting_review',run['context'].get('stop_reason')
    assert memory['id'] in run['recommendation']['memory_ids']
    assert any(t['tool']=='ask_customer' and QUESTION==t['result'].get('question') for t in trail)
    assert all(t['provider']=='fake' and t['provenance']['snapshot_id'] for t in trail)
    assert len(trail)==run['budget']['case_calls']<=6
    duplicate = call('/api/fraud-agent/start',{'report_id':second['id'],'mode':'fake'})
    assert duplicate['id']==run['id'] and duplicate['budget']['case_calls']==run['budget']['case_calls']
    final = call('/api/state')
    assert not final['budget']['live_enabled'] and final['budget']['calls_today']==before_live
    assert final['ledger_balanced'] and run['budget']['daily_calls']<=10
    checkpoint('summary',{'first_report_id':first['id'],'second_report_id':second['id'],'memory_id':memory['id'],
        'first_tools':[t['tool'] for t in approved['decision_trail']],
        'second_tools':[t['tool'] for t in trail],'question':QUESTION,'second_status':run['status'],
        'fake_daily_calls':run['budget']['daily_calls'],'daily_call_limit':run['budget']['daily_call_limit'],
        'live_gemini_calls_added':final['budget']['calls_today']-before_live,'real_model_cost_usd':0,
        'ledger_balanced':True,'review_replay_idempotent':True,'duplicate_start_idempotent':True})
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--service-account',required=True)
    parser.add_argument('--run-id',required=True,help='Stable request prefix; reuse it after an interruption.')
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'reports'/'hosted-investigation.json')
    args=parser.parse_args()
    if not 1<=len(args.run_id)<=70 or not all(c.isalnum() or c in '-_' for c in args.run_id):
        parser.error('Use a 1–70 character alphanumeric run ID with optional hyphens/underscores.')
    session=requests.Session();session.headers['Authorization']='Bearer '+iap_token(args.service_account)
    counts={'GET':0,'POST':0}
    def call(path,body=None):
        method='GET' if body is None else 'POST';counts[method]+=1
        response=session.request(method,BASE+path,json=body,timeout=60,allow_redirects=False)
        if response.status_code>=300:
            raise RuntimeError('%s %s: HTTP %s; stopped without automatic retry.'%(method,path,response.status_code))
        result=response.json()
        if path=='/api/state':session.headers['X-MintTown-Token']=result['csrf_token']
        return result
    def save(result):
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(dict(result,http_requests=counts),indent=2)+'\n')
    try:
        result=rehearse(call,args.run_id,save)
        print(json.dumps(result['summary']|{'http_requests':counts,'report':str(args.output)},indent=2))
    finally:session.close()


if __name__=='__main__':main()
