"""Explicit demo approval must not bypass evidence, review, replay or cost gates."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import Config
from demo_analyst import DemoAnalyst
from lab import LabError
from server import make_server


class DemoAnalystChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.sdk = patch('google.genai.Client.__init__', side_effect=AssertionError('No paid calls'))
        self.sdk.start()
        self.server = make_server(0, Path(self.temp.name)/'demo.db', Config(live=False), seed_history=False)
        self.demo, self.lab, self.desk = self.server.world_demo, self.server.lab, self.server.fraud_desk
        self.actor = self.desk.demo_analyst
        self.run = self.demo.start(0, fresh=True, background=False, mode='simulation')['run_id']

    def tearDown(self):
        self.server.server_close(); self.lab.db.close(); self.sdk.stop(); self.temp.cleanup()

    def wait(self):
        deadline = time.monotonic()+10
        while self.server.fraud_runner.pending and time.monotonic()<deadline:
            time.sleep(.02)
        self.assertFalse(self.server.fraud_runner.pending)

    def case(self):
        self.demo.incident(self.run, 'phishing'); self.wait()
        return self.desk.detail(self.demo.status()['incidents'][0]['report_id'])

    def approve(self, report):
        return self.actor.approve(self.run, report['id'], report['investigation']['id'])

    def test_review_learn_activate_and_changed_recipient_hold_with_one_click(self):
        report = self.case()
        self.assertTrue(report['demo_analyst']['eligible'])
        before = self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0]
        self.approve(report); self.wait()
        result = self.desk.detail(report['id'])
        self.assertEqual(result['demo_analyst']['status'], 'activated')
        self.assertTrue(result['demo_analyst']['assumption'])
        self.assertEqual(result['prevention']['rule']['status'], 'active')
        self.assertIn('DEMO ASSUMPTION', result['reviews'][0]['note'])
        calls = self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0]
        self.assertEqual(calls, before+1)
        self.assertLessEqual(calls, 6)
        self.approve(report); self.actor.finish(report['id'])
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_reviews').fetchone()[0], 1)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0], calls)
        balances = self.lab.rows("SELECT id,balance_minor FROM accounts WHERE id LIKE 'C%' ORDER BY id")
        self.demo.incident(self.run, 'phishing', repeat=True)
        held = self.demo.status()['incidents'][0]
        self.assertEqual(held['status'], 'blocked')
        self.assertIn('variant', held['id'])
        self.assertEqual(balances, self.lab.rows("SELECT id,balance_minor FROM accounts WHERE id LIKE 'C%' ORDER BY id"))
        self.assertEqual(self.server.world.payment('normal-payment', 'C002', 'm1', 5000, 'device-C002'), 'settled')

    def test_blocked_evidence_submitted_reports_and_stale_run_are_rejected(self):
        with patch.object(self.demo, 'prepare'):
            self.demo.incident(self.run, 'phishing')
        report_id = self.demo.status()['incidents'][0]['report_id']
        self.desk.prepare(report_id, 'blocked', 'preparation', 'Daily publication limit reached.')
        with self.assertRaisesRegex(LabError, 'Evidence is blocked'):
            self.actor.approve(self.run, report_id, 'missing')
        report = self.desk.detail(report_id)
        submitted = self.desk.create('C001', report['story'], report['message'], [report['transactions'][0]['id']], 'user-submission')
        with self.assertRaisesRegex(LabError, 'current simulation'):
            self.actor.approve(self.run, submitted['id'], 'missing')
        with self.assertRaisesRegex(LabError, 'simulation changed'):
            self.actor.approve(self.run-1, report_id, 'missing')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_reviews').fetchone()[0], 0)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0], 0)

    def test_evidence_change_still_hits_the_normal_review_gate(self):
        report = self.case()
        with self.lab.db:
            self.lab.db.execute('UPDATE financial_events SET amount_minor=amount_minor+100 WHERE id=?', (report['transactions'][0]['id'],))
        with self.assertRaises(LabError):self.approve(report)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_reviews').fetchone()[0], 0)

    def test_rejected_candidate_is_never_activated_or_retried(self):
        report = self.case()
        proposal=('propose_playbook', {'name':'Demo candidate', 'signals':['safe_account_request','secrecy_request'],
            'explanation':'Test a source-supported pair.', 'purpose':'Check a candidate.',
            'investigation_tip':'Verify the request through an independently obtained contact.',
            'recommended_models':['message_intent_v1'],'verification_question':'Did you independently contact the bank?',
            'counterexample':'An independently initiated savings transfer may be legitimate.'})
        with patch('prevention.fake_choice', return_value=proposal), patch('prevention.replay', return_value={'passed':False,'feature_schema_version':'prepayment-signals-v1','false_flags':1}):
            self.approve(report); self.wait()
        result = self.desk.detail(report['id'])
        self.assertEqual(result['prevention']['rule']['status'], 'rejected')
        self.assertEqual(result['demo_analyst']['status'], 'attention')
        before = self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0]
        self.approve(report)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0], before)

    def test_budget_failure_and_restart_preserve_review_without_retry(self):
        report = self.case()
        self.server.agents.config.daily_calls = report['investigation']['budget']['case_calls']
        self.approve(report); self.wait()
        result = self.desk.detail(report['id'])
        self.assertEqual(result['status'], 'resolved')
        self.assertEqual(result['demo_analyst']['status'], 'attention')
        self.assertFalse(self.server.fraud_runner.prevention.active())
        before = self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0]
        with self.lab.db:self.lab.db.execute("UPDATE demo_analyst_approvals SET status='learning'")
        DemoAnalyst(self.demo)
        self.assertEqual(self.desk.detail(report['id'])['demo_analyst']['status'], 'attention')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0], before)


if __name__ == '__main__':unittest.main()
