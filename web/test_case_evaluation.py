"""Scenario contracts and local-live admission, without paid model calls."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import Agents, Config
from evaluate_cases import fake_evaluation, live_evaluation
from fraud_agent import FraudAgent
from fraud_desk import FraudDesk
from fraud_scenarios import SCENARIOS
from lab import Lab
from local_vertex import require_paused
from world import World


class CaseEvaluationChecks(unittest.TestCase):
    def test_all_five_pairs_reach_review_with_scoped_evidence(self):
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No paid client')) as client:
            result=fake_evaluation();client.assert_not_called()
        self.assertEqual(len(result['cases']),10)
        self.assertEqual(result['actual_model_cost_usd'],0)
        for case in result['cases']:
            self.assertTrue(case['completed'],case)
            self.assertTrue(case['assessment_matches_expected'],case)
            self.assertTrue(case['safety_passed'],case)
        self.assertTrue(any(c['questions'] for c in result['cases']))

    def test_fixture_replay_is_idempotent_and_hides_expected_outcome(self):
        with tempfile.TemporaryDirectory() as folder:
            lab=Lab(Path(folder)/'test.db');desk=FraudDesk(lab,World(lab));agent=FraudAgent(desk,Agents(lab,Config()))
            try:
                for key in SCENARIOS:
                    case=desk.demo(key,'case-'+key);count=lab.db.execute('SELECT count(*) FROM financial_events').fetchone()[0]
                    self.assertEqual(case['id'],desk.demo(key,'case-'+key)['id'])
                    self.assertEqual(count,lab.db.execute('SELECT count(*) FROM financial_events').fetchone()[0])
                    packet=agent.packet(agent.start(case['id']))
                    self.assertNotIn('scenario',packet);self.assertNotIn('expected_assessment',packet)
                    self.assertTrue(all('scam' not in t['to_account'] for t in case['transactions']))
                self.assertTrue(lab.integrity())
            finally:lab.db.close()

    def test_local_vertex_refuses_active_or_tagged_cloud_writers(self):
        require_paused({'scaling':{'scalingMode':'MANUAL','manualInstanceCount':0}})
        for service in ({},{'scaling':{'scalingMode':'AUTOMATIC'}},
            {'scaling':{'scalingMode':'MANUAL','manualInstanceCount':1}},
            {'scaling':{'scalingMode':'MANUAL'},'reconciling':True},
            {'scaling':{'scalingMode':'MANUAL'},'trafficStatuses':[{'tag':'old'}]}):
            with self.assertRaises(ValueError):require_paused(service)

    def test_currency_units_are_checked_against_evidence(self):
        context={'transactions':[{'amount_minor':90000}], 'warehouse_features':{'features':{'prior_daily_spend_php':275.123}}}
        self.assertTrue(FraudAgent.amount_warnings({'summary':'The transfer was 90,000 PHP.','customer_message':''},context))
        self.assertTrue(FraudAgent.amount_warnings({'summary':'A USD 900 transfer.','customer_message':''},context))
        self.assertFalse(FraudAgent.amount_warnings({'summary':'The transfer was ₱900, versus PHP 275.12 average spending.','customer_message':''},context))

    def test_live_evaluation_never_creates_a_case_when_daily_calls_are_used(self):
        class Response:
            def __init__(self,data):self.data=data
            def raise_for_status(self):pass
            def json(self):return self.data
        class Session:
            def __init__(self):self.headers={};self.posts=0
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def request(self,method,url,**kwargs):
                self.posts+=method=='POST'
                if url.endswith('/api/cloud'):return Response({'execution':'local'})
                if url.endswith('/api/fraud-desk'):return Response({'agent_runtime':{'live_enabled':True,'max_case_calls':6,'live_circuit_open':False}})
                return Response({'csrf_token':'test','budget':{'live_enabled':True,'daily_usd_limit':.1,'total_usd_limit':1,
                    'calls_today':30,'daily_call_limit':30,'committed_usd_today':.01,'committed_usd_total':.02}})
        session=Session()
        with patch('requests.Session',return_value=session):result=live_evaluation('http://127.0.0.1:3000','no-spend',lambda _:None)
        self.assertEqual(session.posts,0);self.assertEqual(result['calls_added'],0)
        self.assertEqual(len(result['not_run']),5)


if __name__=='__main__':unittest.main()
