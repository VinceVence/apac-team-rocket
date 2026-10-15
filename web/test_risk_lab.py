"""Research roles, real CPU fits, data lineage and costs; no paid provider calls."""
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from agents import Config
from cloud_data import CloudData
from fraud_adk import FakeInvestigator
from fraud_desk import LESSON,QUESTION
from lab import LabError,now
from risk_lab import StudyRole,fake_choice
from risk_models import VERSION,ALLOWED,synthetic_examples,train
from server import make_server
from test_cloud_data import FakeCloud

TOKEN='test-only-operator-token-1234567890'

class RiskChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        with patch.dict(os.environ,{'MINTTOWN_RISK_OPERATOR_TOKEN':TOKEN}):
            self.server=make_server(0,Path(self.tmp.name)/'risk.db',Config(live=False))
        self.lab=self.server.lab;self.team=self.server.risk_lab
    def tearDown(self):self.server.server_close();self.lab.db.close();self.tmp.cleanup()
    def settle(self,job):
        deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            result=self.team.study(job['id'])
            if result['status'] not in ('queued','scientist','planned','training','validator'):return result
            time.sleep(.03)
        self.fail('Study did not stop')
    def test_real_models_rejections_and_separate_agent_tool_choices(self):
        calls=[]
        def chooser(packet):calls.append(packet);return fake_choice(packet)
        self.team.model_factories={role:lambda:FakeInvestigator(chooser=chooser) for role in ('scientist','validator')}
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No paid SDK')) as sdk:
            self.assertEqual(self.team.seed()['added'],1000)
            self.assertEqual(self.team.seed()['added'],0)
            state=self.team.dataset('benchmark')[1]
            self.assertEqual(state['customers'],100);self.assertTrue(state['eligible'],state['problems'])
            run=self.settle(self.team.start('risk-real-models','benchmark','fake'))
            self.assertEqual(run['status'],'rejected',run['error'])
            self.assertEqual(run['budget']['case_calls'],2)
            self.assertEqual([x['role'] for x in run['trace']],['scientist','training_tool','validator'])
            by={x['recipe']:x for x in run['candidates']}
            self.assertEqual(by['amount_baseline']['status'],'rejected')
            self.assertLess(by['amount_baseline']['test']['recall'],.8)
            self.assertTrue(any(x['gate_passed'] for x in run['candidates']))
            self.assertEqual([x['recipe'] for x in run['candidates'] if x['preselected']],['logistic'])
            self.assertEqual(self.team.start('new-id-same-cohort','benchmark','fake')['id'],run['id'])
            self.assertNotIn('scams',calls[0]['dataset']['splits']['test']);self.assertNotIn('rows',calls[0])
            self.assertNotIn('dataset_json',run);self.assertNotIn('artifact',run['candidates'][0])
            self.assertFalse(run['verdict']['serving_changed']);self.assertEqual(self.server.agents.budget()['calls_today'],0)
            self.assertEqual(self.lab.db.execute('SELECT count(*) FROM prevention_rules').fetchone()[0],0)
            sdk.assert_not_called()
    def test_validator_cannot_override_a_failed_gate(self):
        self.team.seed()
        def bad(packet):
            c=next(x for x in packet['candidates'] if x['recipe']=='amount_baseline')
            return 'recommend_candidate',{'candidate_id':c['id'],'summary':'Approve despite the measured failure.','risks':['Synthetic example'],'purpose':'Test whether a model can override the gate.'}
        self.team.model_factories['validator']=lambda:FakeInvestigator(chooser=bad)
        result=self.settle(self.team.start('risk-bad-validator','benchmark','fake'))
        self.assertEqual(result['status'],'failed');self.assertIn('cannot approve',result['error']);self.assertEqual(result['budget']['case_calls'],2)
        self.assertEqual(self.team.start('same-failed-study','benchmark','fake')['id'],result['id'])
        candidate=next(x for x in result['candidates'] if x['recipe']=='amount_baseline')
        with self.lab.db:
            self.lab.db.execute("UPDATE risk_studies SET status='validator' WHERE id=?",(result['id'],))
            data=json.loads(self.lab.db.execute('SELECT data_json FROM risk_candidates WHERE id=?',(candidate['id'],)).fetchone()[0])
            data['gate_passed']=True
            self.lab.db.execute('UPDATE risk_candidates SET data_json=? WHERE id=?',(json.dumps(data),candidate['id']))
        with self.assertRaisesRegex(LabError,'non-preselected'):
            self.team.decide(result['id'],'validator','recommend_candidate',{'candidate_id':candidate['id'],'summary':'Cannot choose another model after seeing final test results.','risks':['Synthetic data'],'purpose':'Check the preselection constraint.'})

    def test_scientist_ablation_runs_through_the_same_bounded_validator(self):
        self.team.seed()
        def ablation(packet):
            return 'design_ablation',{'hypothesis':'Request context should improve detection compared with transaction features alone.',
                'recipe':'logistic','feature_groups':['transaction','request'],'remove_group':'request',
                'purpose':'Measure the contribution of request features with one paired ablation.'}
        self.team.model_factories['scientist']=lambda:FakeInvestigator(chooser=ablation)
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No paid SDK')):
            result=self.settle(self.team.start('risk-ablation','benchmark','fake'))
        self.assertEqual(result['status'],'rejected',result['error']);self.assertEqual(result['budget']['case_calls'],2)
        self.assertEqual(result['trace'][0]['tool'],'design_ablation');self.assertEqual(len(result['candidates']),4)
        full=next(c for c in result['candidates'] if c['recipe']=='logistic')
        self.assertEqual(full['ablation']['removed_group'],'request');self.assertTrue(full['preselected'])
        self.assertFalse(result['verdict']['serving_changed'])
    def test_final_test_labels_cannot_change_selection_or_threshold(self):
        rows=synthetic_examples(['C'+str(n).zfill(3) for n in range(1,101)])
        payload={'rows':rows,'plan':{'recipes':['logistic','boosted_tree'],'feature_groups':['transaction','request']}}
        first=train(payload)
        for row in rows:
            if row['split']=='test':row['label']=1-row['label']
        changed=train(payload)
        self.assertEqual([(x['recipe'],x['preselected'],x['validation']['threshold']) for x in first],[(x['recipe'],x['preselected'],x['validation']['threshold']) for x in changed])
        self.assertNotEqual(first[-1]['test']['recall'],changed[-1]['test']['recall'])
    def test_scientist_can_request_labels_without_fitting(self):
        self.team.seed();self.team.model_factories['scientist']=lambda:FakeInvestigator(chooser=lambda p:('request_labels',{'reason':'Need more independent reviewed examples for the desired target.','purpose':'Decline an unsupported experiment.'}))
        with patch('risk_lab.subprocess.run',side_effect=AssertionError('No fitting')):
            result=self.settle(self.team.start('risk-request-data','benchmark','fake'))
        self.assertEqual(result['status'],'needs_data');self.assertEqual(result['budget']['case_calls'],1);self.assertFalse(result['candidates'])
    def test_insufficient_data_makes_no_model_calls(self):
        result=self.team.start('risk-no-labels','reviewed','fake')
        self.assertEqual(result['status'],'needs_data');self.assertEqual(result['budget']['case_calls'],0)
    def test_leakage_and_invalid_features_are_excluded(self):
        rows=synthetic_examples(['C001','C002','C003'])[:3]
        rows[0]['available_at']='2030-01-01T00:00:00+00:00'
        rows[1]['features']['future_review']=1
        rows[2]['features']['amount_ratio']=float('nan')
        # JSON rejects non-finite data before it can enter the corpus.
        with self.assertRaises(ValueError):self.team.add_examples(rows)
        rows[2]['features']['amount_ratio']=20
        self.team.add_examples(rows)
        _,manifest=self.team.dataset('benchmark')
        self.assertEqual(manifest['excluded_count'],3);self.assertFalse(manifest['eligible'])
    def test_operator_curation_is_separate_from_public_review(self):
        world=self.server.world
        with self.lab.db:self.lab.db.execute("INSERT INTO accounts(id,label,kind,opening_minor,balance_minor) VALUES('external:risk-test','Counterparty','counterparty',0,0)")
        world.payment('risk-source-payment','C001','external:risk-test',90000,'device-C001',{'device_known':True,'authorization_verified':True,'payment_context':{'before_payment':True,'kind':'payment_request','message':'Move to a safe account. Keep it secret.'}})
        case=self.server.fraud_desk.create('C001','A caller induced this transfer to a safe account and then disappeared.','Move to a safe account. Keep it secret.',['risk-source-payment'],'risk-case-source')
        self.assertEqual(self.team.dataset('reviewed')[1]['rows'],0)
        with self.assertRaises(LabError):self.team.curate(case['id'],1,'Verified the generated case independently.')
        run=self.server.fraud_agent.start(case['id'])
        for _ in range(6):
            if run['status']!='running':break
            run=self.server.fraud_agent.step(run['id'],run['step'])
        self.assertEqual(run['status'],'awaiting_review')
        self.server.fraud_desk.review(case['id'],run['id'],'confirmed_scam','support_followup','Verified the synthetic source transfer and request.',False,LESSON,QUESTION)
        self.assertEqual(self.team.dataset('reviewed')[1]['rows'],0)
        with self.assertRaises(LabError):self.team.curate(case['id'],0,'Trying to flip a reviewed scam label to legitimate.')
        result=self.team.curate(case['id'],1,'Verified the synthetic transfer and its prepayment evidence.')
        self.assertEqual(result['added'],1);self.assertEqual(result['dataset']['eligible_rows'],1)
        self.assertEqual(self.team.curate(case['id'],1,'Verified the synthetic transfer and its prepayment evidence.')['added'],0)
        row=self.lab.db.execute('SELECT data_json FROM risk_examples').fetchone()[0]
        with self.assertRaises(sqlite3.IntegrityError):
            with self.lab.db:self.lab.db.execute('UPDATE risk_examples SET data_json=?',(row,))
    def test_public_cannot_mutate_research_or_obtain_token(self):
        thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(self.server.server_port)
        try:
            state=json.load(urllib.request.urlopen(base+'/api/state'));headers={'Content-Type':'application/json','X-MintTown-Token':state['csrf_token']}
            r=urllib.request.Request(base+'/api/risk-lab/seed',data=b'{}',headers=headers)
            with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(r)
            self.assertEqual(caught.exception.code,403)
            r=urllib.request.Request(base+'/api/risk-lab/evaluate-case',data=b'{}',headers=headers)
            with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(r)
            self.assertEqual(caught.exception.code,403)
            self.assertNotIn(TOKEN,urllib.request.urlopen(base+'/api/risk-lab').read().decode())
            self.assertIn('showEvaluation',urllib.request.urlopen(base+'/evaluation-ui.js').read().decode())
            self.assertEqual(json.load(urllib.request.urlopen(base+'/evaluation-summary.json'))['paid_model_calls'],0)
            headers['X-MintTown-Operator']=TOKEN
            result=json.load(urllib.request.urlopen(urllib.request.Request(base+'/api/risk-lab/seed',data=b'{}',headers=headers)))
            self.assertEqual(result['added'],1000)
        finally:self.server.shutdown();thread.join()
    def test_shared_global_spend_case_ceiling_and_research_limits(self):
        job=self.team.start('risk-ledger-check','reviewed','fake')
        with self.lab.db:self.lab.db.execute("UPDATE risk_studies SET provider='gemini',status='scientist' WHERE id=?",(job['id'],))
        self.server.agents.config=Config(live=True,daily_usd=.015,total_usd=.02)
        with patch.dict(os.environ,{'MINTTOWN_FRAUD_LIVE':'1','GOOGLE_CLOUD_PROJECT':'minttown-apac-2026'}):
            role=StudyRole(self.team,job['id'],'scientist');request=SimpleNamespace(model_dump=lambda **kwargs:{'contents':[]})
            first=role.reserve(job['id'],request)
            self.assertEqual(self.server.agents.budget()['committed_microusd_total'],10000)
            with self.assertRaisesRegex(LabError,'already used'):role.reserve(job['id'],request)
            with self.lab.db:
                self.lab.db.execute("UPDATE risk_agent_turns SET status='completed' WHERE id=?",(first,))
                self.lab.db.execute("UPDATE risk_studies SET status='validator' WHERE id=?",(job['id'],))
                self.lab.db.execute('UPDATE fraud_live_control SET next_call_at=0')
            with self.assertRaisesRegex(LabError,'Daily cost'):StudyRole(self.team,job['id'],'validator').reserve(job['id'],request)
        self.assertEqual(self.server.fraud_agent.max_case_calls,6)
    def test_dataset_and_research_usage_survive_scene_reset_and_cloud_restore(self):
        self.team.seed();job=self.team.start('risk-persist-labels','reviewed','fake')
        with self.lab.db:self.lab.db.execute("INSERT INTO risk_agent_turns(id,report_id,run_id,seq,provider,model,status,reserved_microusd,cost_microusd,created_at,role) VALUES(?,?,?,0,'gemini','meter-test','completed',10000,800,?,'scientist')",(job['id']+':0',job['id'],job['id'],now()))
        before=self.server.agents.budget()
        state=self.server.world_demo.start(self.server.world_demo.status()['run_id'],background=False,fresh=True)
        self.server.world_demo.stop(state['run_id'])
        self.assertEqual(self.team.dataset('benchmark')[1]['rows'],1000)
        self.assertEqual(self.server.agents.budget()['committed_microusd_total'],before['committed_microusd_total'])
        remote=FakeCloud();cloud=CloudData('test-project','test-bucket','simulation',session=remote);cloud.save(self.lab)
        path=Path(self.tmp.name)/'restored.db';cloud.restore(path);db=sqlite3.connect(path)
        self.assertEqual(db.execute('SELECT count(*) FROM risk_examples').fetchone()[0],1000)
        self.assertEqual(db.execute('SELECT sum(cost_microusd) FROM risk_agent_turns').fetchone()[0],800);db.close()
    def test_study_timeouts_do_not_retry_or_change_serving(self):
        self.team.seed()
        import subprocess
        with patch('risk_lab.subprocess.run',side_effect=subprocess.TimeoutExpired('trusted recipes',25)) as tool:
            result=self.settle(self.team.start('risk-timeout','benchmark','fake'))
        self.assertEqual(result['status'],'failed');self.assertEqual(tool.call_count,1)
        self.assertEqual(result['budget']['case_calls'],1);self.assertEqual(self.lab.db.execute('SELECT count(*) FROM prevention_rules').fetchone()[0],0)

if __name__=='__main__':unittest.main()
