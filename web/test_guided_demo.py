"""Competition story and reset invariants; no paid model or cloud requests."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from cloud_data import CloudData
from fraud_desk import LESSON,QUESTION
from lab import LabError,now
from server import make_server
from test_warehouse import QueryCloud
from fraud_detectors import predict_case


class GuidedDemoChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.remote=QueryCloud();self.cloud=CloudData('test-project','test-state','demo',session=self.remote)
        with patch.dict(os.environ,{'PALLET_WAREHOUSE_ENABLED':'1','MINTTOWN_CLOUD_LIVE':'0'}):
            self.server=make_server(0,Path(self.tmp.name)/'demo.db',cloud=self.cloud)
        self.lab=self.server.lab
    def tearDown(self):self.server.server_close();self.lab.db.close();self.tmp.cleanup()
    def wait(self,report_id,prevention=False):
        limit=time.monotonic()+20
        while time.monotonic()<limit:
            case=self.server.fraud_desk.detail(report_id)
            item=case.get('prevention') if prevention else case['investigation']
            if item and item['status'] not in ('queued','running','stepping'):return case
            time.sleep(.02)
        self.fail('Worker did not settle')

    def test_fresh_world_routes_detectors_review_learning_and_local_prevention(self):
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No paid SDK client')) as client:
            demo=self.server.world_demo;before=demo.status()['run_id']
            state=demo.start(before,background=False,fresh=True)
            self.assertTrue(state['guided']);self.assertEqual(self.server.world.state()['tick'],0)
            self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_reports').fetchone()[0],0)
            for _ in range(6):demo.tick(state['run_id'])
            state=demo.status();self.assertFalse(state['running']);self.assertTrue(state['focus_report_id'])
            case=self.wait(state['focus_report_id']);self.assertEqual(case['investigation']['status'],'awaiting_review',case['investigation']['context'].get('stop_reason'))
            self.assertEqual(demo.status()['phase'],'review')
            models=case['investigation']['context']['detector_results']['detectors']
            self.assertEqual(models[0]['signal_score'],0);self.assertEqual(models[1]['signal_score'],1)
            self.assertEqual(case['investigation']['budget']['case_calls'],5)
            desk=self.server.fraud_desk
            desk.review(case['id'],case['investigation']['id'],'confirmed_scam','request_recall',
                'Verified the synthetic complaint and its prepayment message.',True,LESSON,QUESTION)
            self.server.fraud_runner.learn(case['id'],'fake')
            case=self.wait(case['id'],True);job=case['prevention']
            self.assertEqual(job['status'],'awaiting_activation',job.get('error'))
            self.assertEqual(job['budget']['case_calls'],6)
            with self.assertRaisesRegex(LabError,'Activate'):demo.prove(state['run_id'])
            self.server.prevention.activate(job['rule']['id'],True)
            paid=self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0]
            result=demo.prove(state['run_id']);self.assertEqual(result['phase'],'protected')
            self.assertTrue(any(i['status']=='blocked' and 'variant' in i['id'] for i in result['incidents']))
            self.assertTrue(any(i['status']=='passed' for i in result['incidents']))
            self.assertEqual(demo.prove(state['run_id'])['phase'],'protected')
            self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0],paid)
            self.assertTrue(self.lab.integrity());client.assert_not_called()

    def test_fresh_reset_preserves_money_calls_admission_queries_and_circuit(self):
        day=now()[:10]
        with self.lab.db:
            self.lab.db.execute('INSERT INTO model_usage_archive VALUES(?,?,?,?,?,?)',('historic','gemini','old-case','resolution',now(),23000))
            self.lab.db.execute('INSERT INTO demo_usage_archive VALUES(?,?,?,?)',(day,3,4,1))
            self.lab.db.execute("UPDATE demo_daily_usage SET writes=12,reports=5,world_steps=24,starts=2 WHERE day=?",(day,))
            self.lab.db.execute("UPDATE fraud_live_control SET next_call_at=9999999999,blocked_reason='Retain this circuit' WHERE id=1")
        before=self.server.agents.budget();self.cloud.save(self.lab)
        demo=self.server.world_demo
        for _ in range(2):
            state=demo.start(demo.status()['run_id'],background=False,fresh=True);demo.stop(state['run_id'])
            after=self.server.agents.budget()
            self.assertEqual(after['committed_microusd_total'],before['committed_microusd_total']);self.assertEqual(after['calls_today'],before['calls_today'])
            self.assertEqual(self.cloud.daily_exports(self.lab),3)
            self.assertEqual(self.server.demo_guard.status()['used']['reports'],5)
            self.assertEqual(self.server.demo_guard.status()['used']['starts'],2)
            self.assertEqual(self.lab.db.execute('SELECT queries FROM demo_usage_archive WHERE day=?',(day,)).fetchone()[0],4)
            self.assertEqual(self.lab.db.execute('SELECT blocked_reason FROM fraud_live_control').fetchone()[0],'Retain this circuit')
            self.assertTrue(self.lab.integrity())
        self.assertEqual(len([k for k in self.remote.objects if k.startswith('archives/')]),2)
        restored_cloud=CloudData('test-project','test-state','demo',session=self.remote)
        path=Path(self.tmp.name)/'restored.db';restored_cloud.restore(path)
        with patch.dict(os.environ,{'PALLET_WAREHOUSE_ENABLED':'1','MINTTOWN_CLOUD_LIVE':'0'}):
            restored=make_server(0,path,cloud=restored_cloud)
        try:
            self.assertEqual(restored.agents.budget()['committed_microusd_total'],before['committed_microusd_total'])
            self.assertEqual(restored.agents.budget()['calls_today'],before['calls_today'])
            self.assertEqual(restored.demo_guard.status()['used']['reports'],5)
            self.assertEqual(restored_cloud.daily_exports(restored.lab),3)
        finally:restored.server_close();restored.lab.db.close()

    def test_detector_registry_rejects_unknown_models_and_does_not_read_complaints(self):
        tx={'id':'tx','to_account':'new','amount_minor':90000,'occurred_at':now(),'metadata':{'device_known':True,'authorization_verified':True,'scenario':'phishing','story':'safe account keep it secret'}}
        with self.assertRaisesRegex(LabError,'Unknown detector'):predict_case(['arbitrary-cloud-model'],[tx])
        result=predict_case(['device_integrity_v1','message_intent_v1'],[tx])
        self.assertEqual(result['detectors'][0]['signal_score'],0)
        self.assertFalse(result['detectors'][1]['available']);self.assertIsNone(result['detectors'][1]['calibrated_fraud_probability'])


if __name__=='__main__':unittest.main()
