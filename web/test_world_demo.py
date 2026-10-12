"""Headless world -> ADK -> analyst -> KB -> pre-settlement hold."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import Config
from fraud_desk import LESSON, QUESTION
from server import make_server
from world_demo import RUN_STEPS, SCAMS, WorldDemo


class WorldDemoChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.server=make_server(0,Path(self.temp.name)/'world.db',Config(live=False))
        self.demo=self.server.world_demo;self.lab=self.server.lab
    def tearDown(self):self.server.server_close();self.lab.db.close();self.temp.cleanup()
    def wait(self,report_id):
        deadline=time.monotonic()+10
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
