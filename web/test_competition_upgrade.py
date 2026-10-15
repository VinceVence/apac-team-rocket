"""Offline regression checks for evidence references, SQL lineage and learned tools."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

from agents import Config
from case_features import reference,sql
from cloud_data import CloudData
from fraud_adk import FakeInvestigator,tools_for
from fraud_models import manifests,predict
from google.adk.tools.function_tool import FunctionTool
from lab import LabError,now
from policy_replay import compare
from server import make_server
from test_cloud_data import Response
from test_warehouse import QueryCloud


class CompetitionUpgradeChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.server=make_server(0,Path(self.tmp.name)/'case.db',Config(live=False),seed_history=False)
    def tearDown(self):self.server.server_close();self.server.lab.db.close();self.tmp.cleanup()

    def case(self):
        d=self.server.world_demo;s=d.start(0,background=False,fresh=True,mode='demo')
        for _ in range(6):d.tick(s['run_id'])
        return self.server.fraud_desk.detail(d.status()['focus_report_id'])

    def test_transaction_schema_cannot_confuse_snapshot_and_transaction_ids(self):
        report=self.case();agent=self.server.fraud_agent;run=agent.start(report['id'])
        aliases=agent.harness.event_aliases(run);allowed=[aliases[e] for e in report['event_ids']]
        tool=next(t for t in tools_for(agent,run['id']) if t.__name__=='submit_case_resolution')
        declaration=FunctionTool(tool)._get_declaration().model_dump(exclude_none=True)['parameters_json_schema']
        items=declaration['properties']['evidence_ids']['items']
        self.assertEqual(items.get('enum',[items.get('const')]),allowed)
        self.assertNotIn(run['context']['snapshot_id'],allowed)
        run=agent.step(run['id'],run['step']);run=agent.step(run['id'],run['step'])
        from fraud_harness_fixtures import choose
        def wrong(packet):
            _,args=choose({**packet,'delegation_used':True});args['evidence_ids']=[packet['evidence_snapshot']['id']]
            return 'submit_case_resolution',args
        agent.model_factory=lambda:FakeInvestigator(chooser=wrong)
        run=agent.step(run['id'],run['step'])
        self.assertEqual(run['status'],'failed');self.assertIn('cite every',run['context']['stop_reason'])
        self.assertFalse(self.server.fraud_desk.memories())

    def test_model_disagreement_is_visible_and_single_arm_cannot_delegate(self):
        report=self.case();agent=self.server.fraud_agent;run=agent.start(report['id'],experiment_arm='single')
        for _ in range(2):run=agent.step(run['id'],run['step'])
        decision=run['context']['decision_context']
        self.assertTrue(decision['open_questions']);self.assertIn('different questions',decision['observations'][0])
        from fraud_adk import available_tools
        self.assertNotIn('delegate_question',available_tools(agent.packet(run)))
        self.assertEqual(agent.start(report['id'])['context']['experiment_arm'],'single')
        with self.assertRaisesRegex(LabError,'pinned'):agent.start(report['id'],experiment_arm='selective')

    def test_trained_predictor_is_real_advisory_and_never_reads_truth_labels(self):
        report=self.case();agent=self.server.fraud_agent;run=agent.start(report['id']);snapshot=agent.snapshot(run['context']['snapshot_id'])
        result=predict(['synthetic_triage_v1'],[],snapshot,manifests(),report['customer_id'])[0]
        self.assertEqual(result['status'],'scored');self.assertEqual(result['score_kind'],'uncalibrated_model_score')
        self.assertFalse(result['calibrated']);self.assertEqual(result['manifest']['allowed_use'],'investigation_only')
        self.assertGreater(result['prediction']['signal_score'],0)
        changed=copy.deepcopy(snapshot)
        for t in changed['data']['transactions']:t['metadata'].update(is_fraud=False,risk_score=-999,scam_type='legitimate',age_band='anything')
        other=predict(['synthetic_triage_v1'],[],changed,manifests(),report['customer_id'])[0]
        self.assertEqual(other['input_hash'],result['input_hash']);self.assertEqual(other['prediction'],result['prediction'])
        changed['data']['transactions'][0]['metadata'].pop('risk_features')
        unavailable=predict(['synthetic_triage_v1'],[],changed,manifests(),report['customer_id'])[0]
        self.assertEqual(unavailable['status'],'not_available');self.assertIsNone(unavailable['prediction']['signal_score'])

    def test_paired_replay_uses_real_context_and_keeps_legitimate_controls(self):
        source={'requests':[{'payee':'old','amount_minor':90000,'occurred_at':'2026-10-06T14:00:00Z',
            'history':[{'to_account':'known','amount_minor':10000,'occurred_at':'2026-10-05T13:00:00Z'}],
            'metadata':{'device_known':True,'authorization_verified':True,'payment_context':{'before_payment':True,'kind':'payment_request','message':'Move to a safe account immediately. Keep it secret.'}}}],
            'baseline_recipients':['old'],'baseline_rules':[]}
        result=compare(['safe_account_request','secrecy_request'],source)
        self.assertTrue(result['passed']);self.assertEqual(result['before_stopped'],0);self.assertEqual(result['newly_stopped'],3)
        self.assertEqual(result['after_false_holds'],0);self.assertGreater(result['rejected_baseline']['false_holds'],0)
        broad=compare(['safe_account_request','urgent_request'],source)
        self.assertFalse(broad['passed']);self.assertGreater(broad['new_false_holds'],0)
        overly_large=compare(['safe_account_request','secrecy_request','large_amount'],source)
        self.assertFalse(overly_large['passed']);self.assertLess(overly_large['after_stopped'],overly_large['scam_variants'])

    def test_evaluation_arms_share_evidence_without_recreating_transactions(self):
        from evaluate_upgrade import stage_case
        desk=self.server.fraud_desk
        first,created=stage_case(desk,'phishing','pair-single','test-pair-phishing','single')
        count=desk.lab.db.execute('SELECT count(*) FROM financial_events').fetchone()[0]
        second,created=stage_case(desk,'phishing','pair-selective','test-pair-phishing','selective')
        self.assertTrue(created);self.assertNotEqual(first['id'],second['id'])
        self.assertEqual(first['transactions'],second['transactions'])
        self.assertEqual(count,desk.lab.db.execute('SELECT count(*) FROM financial_events').fetchone()[0])
        again,created=stage_case(desk,'phishing','pair-selective','test-pair-phishing','selective')
        self.assertFalse(created);self.assertEqual(again['id'],second['id'])
        with self.assertRaisesRegex(LabError,'another fixture'):stage_case(desk,'payment_burst','pair-wrong','test-pair-phishing','single')

    def test_json_predictors_match_fitted_estimators_and_ablation_ignores_test_labels(self):
        from risk_models import train,synthetic_examples
        from trained_models import score
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import GradientBoostingClassifier
        captured=[]
        def record(original):
            def wrapped(model,x,*args,**kwargs):
                predictions=original(model,x,*args,**kwargs);captured.append(predictions[:,1].tolist());return predictions
            return wrapped
        rows=synthetic_examples(['C%03d'%n for n in range(1,101)])
        with patch.object(LogisticRegression,'predict_proba',record(LogisticRegression.predict_proba)),patch.object(GradientBoostingClassifier,'predict_proba',record(GradientBoostingClassifier.predict_proba)):
            candidates=train({'rows':rows,'plan':{'recipes':['logistic','boosted_tree'],'feature_groups':['transaction','request']}})
        for index,candidate in enumerate(candidates[1:]):
            for offset,split in enumerate(('validation','test')):
                deployed=[score(candidate['artifact'],r['features']) for r in rows if r['split']==split]
                self.assertLess(max(abs(a-b) for a,b in zip(deployed,captured[2*index+offset])),1e-7)
        plan={'recipes':['logistic'],'feature_groups':['transaction','request'],'ablation_group':'request'}
        first=train({'rows':rows,'plan':plan})
        for row in rows:
            if row['split']=='test':row['label']=1-row['label']
        second=train({'rows':rows,'plan':plan})
        self.assertEqual(len(first),4) # One rule reference and three CPU fits.
        self.assertEqual([(c['recipe'],c['preselected'],c['validation']) for c in first],[(c['recipe'],c['preselected'],c['validation']) for c in second])
        self.assertIn('ablation',first[2]);self.assertNotEqual(first[2]['test'],second[2]['test'])


class FeatureQueryChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.remote=QueryCloud();self.cloud=CloudData('test-project','test-state','demo',session=self.remote)
        with patch.dict(os.environ,{'PALLET_WAREHOUSE_ENABLED':'1','MINTTOWN_CLOUD_LIVE':'0'}):self.server=make_server(0,Path(self.tmp.name)/'sql.db',cloud=self.cloud,seed_history=False)
        self.s=self.server;d=self.s.world_demo;state=d.start(0,background=False,fresh=True,mode='demo')
        for _ in range(6):d.tick(state['run_id'])
        self.report=self.s.fraud_desk.report(d.status()['focus_report_id']);self.service=self.s.warehouse.case_features
        class Publisher:
            def status(inner):return {'latest':{'id':'completed-batch','status':'completed','created_at':now(),'completed_at':now()}}
        self.service.publisher=Publisher()
        with self.s.lab.db:self.s.lab.db.execute('INSERT INTO environment_feature_coverage VALUES(?,?)',
            ('completed-batch',json.dumps([r['transaction_id'] for r in self.service.basis(self.report)['records']])))
    def tearDown(self):self.s.server_close();self.s.lab.db.close();self.tmp.cleanup()
    def test_real_sql_contract_and_cached_receipt_are_case_bound(self):
        basis=self.service.basis(self.report);query=self.s.warehouse.query
        def scoped(statement,params,location=None):
            self.assertEqual(location,'US');self.assertNotIn(params['customer'],statement)
            self.assertEqual(params['cutoff'],basis['cutoff']);self.assertEqual(params['since'],basis['since'])
            for forbidden in ('risk_score','risk_factors','is_fraud','scam_type','trust_score','risk_tier','current_balance'):self.assertNotIn(forbidden,statement)
            self.assertEqual(statement.count('minttown_world.'),4)
            return [{'features':copy.deepcopy(basis['features']),'records':copy.deepcopy(basis['records']),'record_count':len(basis['records'])}],{'provider':'BigQuery','job_id':'verified-query','snapshot_id':params['snapshot'],'bytes_billed':1024}
        with patch.object(self.s.warehouse,'query',side_effect=scoped) as called:
            result=self.service.prepare(self.report);again=self.service.prepare(self.report)
            self.assertEqual(called.call_count,1);self.assertEqual(result,again)
        self.assertEqual(result['source']['provider'],'BigQuery');self.assertIn('available_at',result['source'])
        run=self.s.fraud_agent.start(self.report['id']);frozen=self.s.fraud_agent.snapshot(run['context']['snapshot_id'])['data']['customer_features']
        self.assertEqual(frozen['source']['job_id'],'verified-query')
    def test_stale_rows_are_withheld_without_repeating_the_query(self):
        with patch.object(self.s.warehouse,'query',return_value=([{'features':{},'records':[],'record_count':0}],{})) as called:
            self.assertIsNone(self.service.prepare(self.report));self.assertIsNone(self.service.prepare(self.report));self.assertEqual(called.call_count,1)
        run=self.s.fraud_agent.start(self.report['id']);data=self.s.fraud_agent.snapshot(run['context']['snapshot_id'])['data']
        self.assertEqual(data['customer_features']['source']['provider'],'Simulation ledger')

    def test_unpublished_records_do_not_consume_queries(self):
        with self.s.lab.db:self.s.lab.db.execute('DELETE FROM environment_feature_coverage')
        with patch.object(self.s.warehouse,'query',side_effect=AssertionError('No query for unpublished records')):
            self.assertIsNone(self.service.prepare(self.report))


if __name__=='__main__':unittest.main()
