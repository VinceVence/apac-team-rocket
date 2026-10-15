"""Headless world -> ADK -> analyst -> KB -> pre-settlement hold."""
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from agents import Config
from fraud_adk import FakeInvestigator
from fraud_desk import LESSON, QUESTION
from server import make_server
from world_demo import RUN_STEPS, SCAMS, WorldDemo


class WorldDemoChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.server=make_server(0,Path(self.temp.name)/'world.db',Config(live=False))
        self.demo=self.server.world_demo;self.lab=self.server.lab
    def tearDown(self):self.server.server_close();self.lab.db.close();self.temp.cleanup()
    def wait(self,report_id,timeout=10):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            detail=self.server.fraud_desk.detail(report_id);run=detail['investigation']
            if run and run['context'].get('execution',{}).get('status') not in ('queued','running'):return detail
            time.sleep(.02)
        self.fail('Investigation did not stop')

    def test_world_opens_case_and_approved_knowledge_prevents_related_transfer(self):
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No live client')) as client:
            state=self.demo.start(0,background=False)
            for _ in range(6):self.demo.tick(state['run_id'])
            incident=next(x for x in self.demo.status()['incidents'] if x['kind']=='phishing')
            self.assertEqual(incident['status'],'investigating')
            first=self.wait(incident['report_id']);run=first['investigation']
            self.assertEqual(run['status'],'awaiting_review');self.assertEqual(run['budget']['case_calls'],5)
            self.server.fraud_desk.review(first['id'],run['id'],'confirmed_scam','request_recall',
                'Verified this synthetic phishing report and its ledger evidence.',True,LESSON,QUESTION)
            before=self.lab.rows('SELECT id,balance_minor FROM accounts ORDER BY id')
            self.demo.incident(state['run_id'],'phishing',repeat=True)
            blocked=self.demo.status()['incidents'][0]
            self.assertEqual(blocked['status'],'blocked');self.assertIsNone(blocked['report_id'])
            self.assertEqual(self.demo.status()['blocked_payments'],1)
            self.assertEqual(before,self.lab.rows('SELECT id,balance_minor FROM accounts ORDER BY id'))
            self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0],5)
            with self.lab.db:ordinary=self.server.world.payment('legitimate-control','C002','m1',5000,'device-C002')
            self.assertEqual(ordinary,'settled');self.assertTrue(self.lab.integrity());client.assert_not_called()

    def test_payment_burst_is_real_evidence_and_customer_reply_is_bounded(self):
        state=self.demo.start(0,background=False)
        self.demo.incident(state['run_id'],'payment_burst')
        incident=self.demo.status()['incidents'][0];case=self.wait(incident['report_id'])
        self.assertEqual(len(case['transactions']),3)
        self.assertEqual({t['to_account'] for t in case['transactions']},{SCAMS['payment_burst']['payee']})
        self.assertEqual([t['occurred_at'][-3:-1] for t in case['transactions']],['00','04','08'])
        self.assertEqual(case['investigation']['status'],'awaiting_review')
        self.assertTrue(self.lab.integrity())

    def test_hosted_world_investigates_two_live_cases_with_mocked_vertex(self):
        from cloud_data import CloudData
        from test_cloud_data import FakeCloud
        self.server.server_close();self.lab.db.close()
        model_options=[]
        class FakeVertex(FakeInvestigator):
            def __init__(self,**kwargs):
                model_options.append(kwargs)
                super().__init__()
        with patch.dict(os.environ,{'MINTTOWN_LIVE':'1','MINTTOWN_FRAUD_LIVE':'1','MINTTOWN_CLOUD_LIVE':'1',
             'GOOGLE_CLOUD_PROJECT':'minttown-apac-2026'}),patch('fraud_agent.LIVE_INTERVAL_SECONDS',0),\
             patch('google.genai.Client') as client,patch('google.adk.models.google_llm.Gemini',FakeVertex):
            client.return_value.aio.aclose=AsyncMock()
            cloud=CloudData('minttown-apac-2026','test-state','simulation',session=FakeCloud())
            self.server=make_server(0,Path(self.temp.name)/'hosted.db',cloud=cloud)
            self.demo=self.server.world_demo;self.lab=self.server.lab
            self.server.agents.config.daily_calls=10  # Lower boundary for this two-case gate check.
            with self.server:
                state=self.demo.start(0,background=False)
                for kind in ('phishing','payment_burst'):
                    self.demo.incident(state['run_id'],kind)
                    incident=self.demo.status()['incidents'][0]
                    self.assertEqual(incident['status'],'investigating')
                    case=self.wait(incident['report_id'],timeout=40);run=case['investigation']
                    self.assertEqual(run['context']['provider'],'gemini')
                    self.assertEqual(run['status'],'awaiting_review',run['context'].get('stop_reason'))
                    self.assertEqual(run['budget']['case_calls'],5)
                self.assertEqual(self.server.agents.budget()['calls_today'],10)
                self.assertLess(self.server.agents.budget()['committed_usd_today'],.1)
                self.assertEqual(self.server.demo_guard.status()['used']['reports'],2)
                self.demo.stop(state['run_id']);state=self.demo.start(state['run_id'],background=False)
                self.demo.incident(state['run_id'],'phishing')
                self.assertEqual(self.demo.status()['incidents'][0]['status'],'budget_limited')
                self.assertEqual(client.call_count,10);self.assertEqual(len(model_options),10)
                for call in client.call_args_list:
                    self.assertTrue(call.kwargs['vertexai'])
                    self.assertEqual(call.kwargs['http_options'].retry_options.attempts,1)
                for options in model_options:self.assertEqual(options['retry_options'].attempts,1)
                self.assertTrue(self.lab.integrity())

    def test_existing_approved_cases_protect_the_new_world_without_model_calls(self):
        desk=self.server.fraud_desk;report=desk.demo('first','legacy-known-scam')
        self.server.fraud_runner.start(report['id'])
        case=self.wait(report['id'])
        desk.review(report['id'],case['investigation']['id'],'confirmed_scam','request_recall',
            'Verified the synthetic report and exact recipient.',True,LESSON,QUESTION)
        calls=self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0]
        before=self.lab.rows('SELECT id,balance_minor FROM accounts ORDER BY id')
        state=self.demo.start(0,background=False);self.demo.incident(state['run_id'],'phishing',repeat=True)
        self.assertEqual(self.demo.status()['incidents'][0]['status'],'blocked')
        self.assertEqual(before,self.lab.rows('SELECT id,balance_minor FROM accounts ORDER BY id'))
        self.assertEqual(calls,self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0])
        protection=self.demo.status()['protection']
        self.assertEqual(protection['count'],1)
        self.assertEqual(protection['recent'][0]['source_report_id'],report['id'])
        self.assertGreater(protection['amount_minor'],0)

    def test_continuous_world_keeps_paying_during_intake_and_resumes_same_scene(self):
        entered=threading.Event();release=threading.Event()
        class Publisher:
            def publish(inner):
                entered.set()
                if not release.wait(10):raise RuntimeError('Test intake timed out')
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No paid client')) as client:
            state=self.demo.start(0,background=False,fresh=True,mode='simulation');self.demo.environment_publisher=Publisher()
            self.assertFalse(state['guided']);self.assertTrue(state['continuous'])
            self.assertEqual(self.lab.db.execute('SELECT count(*) FROM financial_events').fetchone()[0],0)
            try:
                for _ in range(6):self.demo.tick(state['run_id'])
                self.assertTrue(entered.wait(2));self.assertTrue(self.demo.status()['running'])
                report_id=self.demo.status()['incidents'][0]['report_id']
                self.assertIsNone(self.server.fraud_desk.detail(report_id)['investigation'])
                before=self.lab.db.execute('SELECT count(*) FROM financial_events').fetchone()[0]
                for _ in range(RUN_STEPS):self.demo.tick(state['run_id'])
                current=self.demo.status();self.assertGreater(current['steps'],RUN_STEPS);self.assertTrue(current['running'])
                self.assertGreater(self.lab.db.execute('SELECT count(*) FROM financial_events').fetchone()[0],before)
                self.assertEqual(len([i for i in current['incidents'] if i['report_id']]),1)
                self.demo.stop(state['run_id']);resumed=self.demo.start(state['run_id'],background=False,mode='simulation')
                self.assertEqual(resumed['scene_id'],state['scene_id']);self.assertEqual(resumed['run_id'],state['run_id']);self.assertEqual(resumed['steps'],current['steps'])
                from lab import LabError
                self.demo.stop(state['run_id'])
                with self.assertRaises(LabError):self.demo.start(state['run_id'],background=False,fresh=True,mode='demo')
            finally:release.set();self.demo.intake.join(10)
            case=self.wait(report_id);self.assertEqual(case['status'],'awaiting_review');client.assert_not_called()

    def test_continuous_world_retains_the_hosted_step_limit(self):
        from demo_guard import DemoGuard
        from lab import LabError
        self.demo.guard=DemoGuard(self.lab,lambda:None)
        state=self.demo.start(0,background=False,fresh=True,mode='simulation')
        with patch('demo_guard.DAILY_WORLD_STEPS',2):
            for _ in range(2):self.demo.tick(state['run_id'])
            with self.assertRaisesRegex(LabError,'world-step'):self.demo.tick(state['run_id'])
        self.assertEqual(self.demo.status()['steps'],2)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0],0)

    def test_episode_is_idempotent_bounded_and_does_not_resume_after_restart(self):
        self.server.fraud_agent.agents.config=Config(daily_calls=1)
        state=self.demo.start(0,background=False)
        self.assertEqual(self.demo.start(0,background=False)['run_id'],state['run_id'])
        for _ in range(RUN_STEPS+2):self.demo.tick(state['run_id'])
        self.assertEqual(self.demo.status()['steps'],RUN_STEPS);self.assertFalse(self.demo.status()['running'])
        newer=self.demo.start(state['run_id'],background=False)
        self.assertTrue(newer['running'])
        self.assertTrue(self.demo.stop(state['run_id'])['running'])
        restored=WorldDemo(self.server.world,self.server.fraud_desk,self.server.fraud_runner)
        self.assertFalse(restored.status()['running']);restored.close()


if __name__=='__main__':unittest.main()
