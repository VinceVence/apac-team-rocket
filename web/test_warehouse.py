"""Typed warehouse, scoped queries, model constraints and durable allowances."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import Config
from evaluate_cases import fixture_chooser
from fraud_adk import FakeInvestigator
from cloud_data import CloudData
from lab import LabError
from server import make_server
from test_cloud_data import FakeCloud, Response
from warehouse import Warehouse, MAX_QUERY_BYTES, MODEL_FEATURES, fit_behavior


class QueryCloud(FakeCloud):
    def __init__(self):super().__init__();self.query_config=None;self.result_customer='C001'
    def request(self,method,url,**kwargs):
        if 'bigquery.googleapis.com' in url:
            if method=='POST' and 'query' in kwargs.get('json',{}).get('configuration',{}):
                self.query_config=kwargs['json']['configuration']['query']
            if '/queries/' in url:
                row={k:1 for k in MODEL_FEATURES};row.update(customer_id=self.result_customer,baseline_days=28,prior_daily_payment_count=2,prior_daily_spend_php=300)
                return Response(data={'jobComplete':True,'rows':[{'f':[{'v':json.dumps(row)}]}]})
        return super().request(method,url,**kwargs)


class WarehouseChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.server=make_server(0,Path(self.temp.name)/'test.db',Config(live=False))
        self.lab=self.server.lab;self.remote=QueryCloud();self.cloud=CloudData('test-project','test-state','demo',session=self.remote)
        self.cloud.initialize(self.lab);self.warehouse=Warehouse(self.lab,self.cloud)
    def tearDown(self):self.server.server_close();self.lab.db.close();self.temp.cleanup()

    def test_typed_snapshot_and_publication_replay_use_one_allowance(self):
        case=self.server.fraud_desk.demo('payment_burst','warehouse-burst')
        tables=self.warehouse.tables();customers={r['customer_id'] for r in tables['pallet_customers']}
        self.assertEqual(len(customers),100);self.assertEqual(len(tables),7)
        self.assertTrue(all(t['customer_id'] in customers for t in tables['pallet_transactions']))
        feature=next(r for r in tables['pallet_customer_daily'] if r['customer_id']=='C004' and r['event_date']==self.lab.clock_day)
        self.assertGreaterEqual(feature['max_burst_minute'],3);self.assertEqual(feature['unknown_device_count'],3)
        self.assertTrue(set(case['event_ids'])<={r['event_id'] for r in tables['pallet_transactions']})
        snapshot=self.warehouse.publish();jobs=len(self.remote.jobs)
        self.assertEqual(snapshot,self.warehouse.publish());self.assertEqual(jobs,len(self.remote.jobs))
        self.assertEqual(self.cloud.daily_exports(self.lab),1)
        self.assertLessEqual(self.warehouse.latest()['row_count'],20000)

    def test_publication_failure_retains_allowance_and_never_resubmits(self):
        self.remote.fail_jobs=True
        with self.assertRaisesRegex(LabError,'publication stopped'):self.warehouse.publish()
        count=len(self.remote.jobs)
        with self.assertRaisesRegex(LabError,'operator reconciliation'):self.warehouse.publish()
        self.assertEqual(len(self.remote.jobs),count);self.assertEqual(self.cloud.daily_exports(self.lab),1)

    def test_queries_are_parameterized_scoped_and_capped_before_submission(self):
        result=self.warehouse.customer_features('C001','snapshot-test',self.lab.clock_day)
        config=self.remote.query_config
        self.assertEqual(config['maximumBytesBilled'],str(MAX_QUERY_BYTES))
        self.assertNotIn('C001',config['query'])
        self.assertEqual(next(x['parameterValue']['value'] for x in config['queryParameters'] if x['name']=='customer'),'C001')
        self.assertEqual(result['source']['provider'],'BigQuery')
        self.remote.result_customer='C099'
        with self.assertRaisesRegex(LabError,'outside this case'):self.warehouse.customer_features('C001','snapshot-test',self.lab.clock_day)
        with patch('warehouse.DAILY_QUERIES',2),self.assertRaisesRegex(LabError,'allowance'):self.warehouse.customer_features('C001','snapshot-test',self.lab.clock_day)
        self.assertEqual(len(self.remote.jobs),2)

    def test_behavior_model_is_real_bounded_and_has_no_fraud_accuracy_claim(self):
        rows=[{'customer_id':'C%03d'%i,**{k:(i%7+1)*(j+1) for j,k in enumerate(MODEL_FEATURES)}} for i in range(1,101)]
        model,report=fit_behavior(rows)
        self.assertEqual(len(model['centers']),3)
        self.assertGreaterEqual(report['holdout_customers'],3)
        self.assertIsNone(report['labelled_fraud_accuracy'])
        self.assertNotIn('age_band',model['features'])

    def test_adk_can_use_warehouse_guidance_and_model_tools_inside_case_envelope(self):
        desk=self.server.fraud_desk;case=desk.demo('phishing','all-tools')
        self.warehouse.publish();agent=self.server.fraud_agent;agent.warehouse=self.warehouse
        agent.harness_enabled=False  # Retained single-agent baseline; mesh cases do not expose training.
        def choose(packet):
            seen={o['tool'] for o in packet['observations']}
            for tool in ('get_customer_features','get_complaint_guidance','train_behavior_model'):
                if tool not in seen:return tool,{'purpose':'Inspect this bounded evidence source for the current case.'}
            return fixture_chooser('phishing',False)(packet)
        agent.model_factory=lambda:FakeInvestigator(chooser=choose)
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No paid client')):
            run=agent.start(case['id'])
            for _ in range(7):
                if run['status']!='running':break
                run=agent.step(run['id'],run['step'])
        self.assertEqual(run['status'],'awaiting_review',run['context'].get('stop_reason'))
        self.assertEqual(run['budget']['case_calls'],6)
        self.assertEqual(run['context']['warehouse_features']['source']['provider'],'BigQuery')


if __name__=='__main__':unittest.main()
