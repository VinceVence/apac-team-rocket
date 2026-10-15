"""Competition story and reset invariants; no paid model or cloud requests."""
import json
import os
import tempfile
import threading
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
from fraud_adk import available_tools


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
            residents=self.lab.rows('SELECT id,name FROM customers ORDER BY id')
            self.assertEqual(len(residents),100);self.assertEqual(len({r['name'] for r in residents}),100)
            self.assertEqual([r['name'] for r in residents],['Resident '+str(i) for i in range(1,101)])
            for table in ('financial_events','ledger_entries','bronze_interactions','model_runs'):
                self.assertEqual(self.lab.db.execute('SELECT count(*) FROM '+table).fetchone()[0],0,table)
            self.assertEqual(self.server.environment_data.tables()['wallet_transactions'],[])
            daily=self.server.warehouse.tables()['pallet_customer_daily']
            self.assertEqual(len(daily),100);self.assertEqual({r['event_date'] for r in daily},{self.lab.clock_day})
            self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_reports').fetchone()[0],0)
            demo.tick(state['run_id'])
            self.assertGreater(len(self.server.environment_data.tables()['wallet_transactions']),0)
            self.assertFalse(demo.status()['incidents'])
            self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0],0)
            for _ in range(5):demo.tick(state['run_id'])
            state=demo.status();self.assertFalse(state['running']);self.assertTrue(state['focus_report_id'])
            case=self.wait(state['focus_report_id']);self.assertEqual(case['investigation']['status'],'awaiting_review',case['investigation']['context'].get('stop_reason'))
            self.assertEqual(demo.status()['phase'],'review')
            models=case['investigation']['context']['detector_results']['detectors']
            self.assertEqual(models[0]['signal_score'],0);self.assertEqual(models[1]['signal_score'],1)
            self.assertEqual(case['investigation']['budget']['case_calls'],5)
            packet=self.server.fraud_agent.packet(case['investigation'])
            self.assertNotIn('search_reviewed_cases',available_tools(packet))
            with self.assertRaisesRegex(LabError,'reserved for prevention'):
                self.server.fraud_agent.reserve(case['investigation']['id'],None)
            self.assertEqual(self.server.fraud_agent.budget(case['id'],'fake')['case_calls'],5)
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

    def test_next_only_review_learning_activation_and_payment_proof(self):
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No paid SDK')):
            demo=self.server.world_demo;state=demo.start(0,background=False,fresh=True,mode='demo')
            for _ in range(6):demo.tick(state['run_id'])
            case=self.wait(demo.status()['focus_report_id']);rid=case['id']
            reviewed=demo.demo_action(state['run_id'],rid,'review')
            self.assertEqual(reviewed['report']['status'],'resolved');self.assertTrue(reviewed['receipt']['assumption'])
            self.assertTrue(demo.demo_action(state['run_id'],rid,'review')['replayed'])
            demo.demo_action(state['run_id'],rid,'learn');self.wait(rid,True)
            activated=demo.demo_action(state['run_id'],rid,'activate');self.assertEqual(activated['receipt']['mode'],'behavioral_safeguard')
            count=self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0]
            proof=demo.demo_action(state['run_id'],rid,'prove');self.assertEqual(proof['demo']['phase'],'protected')
            self.assertTrue(demo.demo_action(state['run_id'],rid,'prove')['replayed'])
            self.assertEqual(count,self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0]);self.assertLessEqual(count,6)
            self.assertEqual(len(self.server.fraud_desk.memories()),1);self.assertTrue(self.lab.integrity())

    def test_failed_agent_can_finish_demo_without_retrying_or_activating_rejected_rule(self):
        from fraud_adk import FakeInvestigator
        self.server.fraud_agent.model_factory=lambda:FakeInvestigator(chooser=lambda p:('not_a_tool',{}))
        demo=self.server.world_demo;state=demo.start(0,background=False,fresh=True,mode='demo')
        for _ in range(6):demo.tick(state['run_id'])
        rid=demo.status()['focus_report_id'];case=self.wait(rid);self.assertEqual(case['investigation']['status'],'failed')
        count=self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0]
        demo.demo_action(state['run_id'],rid,'review')
        with self.lab.db:self.lab.db.execute("UPDATE fraud_live_control SET blocked_reason='Offline test fence' WHERE id=1")
        learned=demo.demo_action(state['run_id'],rid,'learn');self.assertEqual(learned['receipt']['mode'],'reviewed_recipient')
        demo.demo_action(state['run_id'],rid,'activate');result=demo.demo_action(state['run_id'],rid,'prove')
        self.assertEqual(result['demo']['phase'],'protected');self.assertFalse(self.server.prevention.active())
        self.assertEqual(count,self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0]);self.assertTrue(self.lab.integrity())
        with self.assertRaises(LabError):demo.demo_action(state['run_id']+1,rid,'review')
        with self.assertRaises(LabError):demo.demo_action(state['run_id'],'another-case','review')

    def test_rejected_prevention_candidate_stays_rejected_in_the_demo(self):
        from fraud_adk import FakeInvestigator
        self.server.prevention.model_factory=lambda:FakeInvestigator(chooser=lambda p:('propose_prevention_rule',{'name':'Too broad urgency rule','signals':['urgent_request'],'explanation':'Deliberately invalid single-signal rule for this offline check.','purpose':'Verify that failed validation cannot become active.'}))
        demo=self.server.world_demo;state=demo.start(0,background=False,fresh=True,mode='demo')
        for _ in range(6):demo.tick(state['run_id'])
        rid=demo.status()['focus_report_id'];self.wait(rid)
        demo.demo_action(state['run_id'],rid,'review');demo.demo_action(state['run_id'],rid,'learn')
        job=self.wait(rid,True)['prevention'];self.assertEqual(job['status'],'rejected')
        activation=demo.demo_action(state['run_id'],rid,'activate');self.assertEqual(activation['receipt']['mode'],'reviewed_recipient')
        self.assertFalse(self.server.prevention.active())
        demo.demo_action(state['run_id'],rid,'prove')
        self.assertEqual(self.server.prevention.for_report(rid)['status'],'rejected')
        self.assertEqual(demo.status()['phase'],'protected')

    def test_demo_fence_still_allows_scoped_local_story_but_not_model_calls(self):
        demo=self.server.world_demo;state=demo.start(0,background=False,fresh=True,mode='demo')
        self.server.fraud_agent.agents.config.daily_calls=0
        for _ in range(6):demo.tick(state['run_id'])
        rid=demo.status()['focus_report_id'];self.assertTrue(rid)
        for action in ('review','learn','activate','prove'):
            # Keep learning local as well: no paid or fake model generation.
            with self.lab.db:self.lab.db.execute("UPDATE fraud_live_control SET blocked_reason='Test allowance exhausted' WHERE id=1")
            demo.demo_action(state['run_id'],rid,action)
        self.assertEqual(demo.status()['phase'],'protected')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0],0)
        with self.lab.db:self.lab.db.execute('UPDATE world_demo_state SET guided=0 WHERE id=1')
        with self.assertRaisesRegex(LabError,'guided demo'):demo.demo_action(state['run_id'],rid,'review')

    def test_empty_scene_stays_empty_after_restart_without_backfilling_history(self):
        state=self.server.world_demo.start(0,background=False,fresh=True);self.server.world_demo.stop(state['run_id'])
        self.server.server_close();self.lab.db.close()
        with patch.dict(os.environ,{'PALLET_WAREHOUSE_ENABLED':'1','MINTTOWN_CLOUD_LIVE':'0'}):
            self.server=make_server(0,Path(self.tmp.name)/'demo.db',cloud=self.cloud)
        self.lab=self.server.lab
        self.assertFalse(self.lab.seed_history)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM financial_events').fetchone()[0],0)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM bronze_interactions').fetchone()[0],0)
        self.assertEqual(self.server.environment_data.tables()['wallet_transactions'],[])
        self.assertTrue(self.lab.integrity())

    def test_preparation_is_observable_before_agent_creation_and_dispatches_once(self):
        entered,released=threading.Event(),threading.Event()
        class Publisher:
            calls=0
            def publish(inner):
                inner.calls+=1;entered.set()
                if not released.wait(10):raise LabError('Test publication timed out.')
        publisher=Publisher();demo=self.server.world_demo
        state=demo.start(0,background=False,fresh=True);demo.environment_publisher=publisher
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No paid client')):
            thread=threading.Thread(target=lambda:demo.incident(state['run_id'],'phishing'));thread.start()
            try:
                self.assertTrue(entered.wait(5));rid=demo.status()['focus_report_id'];case=self.server.fraud_desk.detail(rid)
                self.assertIsNone(case['investigation']);self.assertEqual(case['preparation']['stage'],'simulation_data')
                self.assertEqual(case['preparation']['status'],'running');self.assertTrue(demo.status()['restart_blocked'])
                self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0],0)
            finally:released.set();thread.join(10)
            self.assertFalse(thread.is_alive());case=self.wait(rid)
            self.assertEqual(case['preparation']['status'],'completed');self.assertEqual(case['status'],'awaiting_review')
            self.assertEqual(publisher.calls,1);self.assertEqual(case['investigation']['budget']['case_calls'],5)

    def test_preparation_failure_is_a_visible_blocker_without_model_calls_or_retries(self):
        class Publisher:
            calls=0
            def publish(inner):inner.calls+=1;raise LabError('Snapshot needs operator review.',503)
        publisher=Publisher();demo=self.server.world_demo
        state=demo.start(0,background=False,fresh=True);demo.environment_publisher=publisher
        demo.incident(state['run_id'],'phishing');rid=demo.status()['focus_report_id'];case=self.server.fraud_desk.detail(rid)
        self.assertEqual(case['preparation']['status'],'blocked');self.assertIsNone(case['investigation'])
        self.assertEqual(demo.status()['phase'],'attention')
        demo.incident(state['run_id'],'phishing');self.assertEqual(publisher.calls,1)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0],0)

    def test_restart_marks_unfinished_preparation_interrupted_without_restarting_it(self):
        report=self.server.fraud_desk.demo('phishing','unfinished-preparation')
        self.server.fraud_desk.prepare(report['id'],'running','evidence_snapshot','Preparing evidence.')
        self.server.server_close();self.lab.db.close()
        with patch.dict(os.environ,{'PALLET_WAREHOUSE_ENABLED':'1','MINTTOWN_CLOUD_LIVE':'0'}):
            self.server=make_server(0,Path(self.tmp.name)/'demo.db',cloud=self.cloud)
        self.lab=self.server.lab;case=self.server.fraud_desk.detail(report['id'])
        self.assertEqual(case['preparation']['status'],'interrupted');self.assertIsNone(case['investigation'])
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0],0)

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
