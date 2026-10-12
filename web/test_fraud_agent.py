"""Real ADK runners with fake responses: branching, questions, scope and durable spending."""
import logging
import os
import tempfile
import threading
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from agents import Agents, Config
from fraud_adk import FakeInvestigator, fixture_choice
from fraud_agent import FraudAgent, RESERVE_MICROUSD
from fraud_desk import FraudDesk, LESSON, QUESTION
from lab import Lab, LabError
from world import World

logging.getLogger('google.adk').setLevel(logging.CRITICAL)
warnings.filterwarnings('ignore', message='.*EXPERIMENTAL.*')


class AgentChecks(unittest.TestCase):
    def setUp(self):
        previous_logging = logging.root.manager.disable
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, previous_logging)
        warnings.filterwarnings('ignore', message='.*EXPERIMENTAL.*')
        self.temp = tempfile.TemporaryDirectory(); self.path = Path(self.temp.name) / 'agent.db'
        self.lab = Lab(self.path); self.world = World(self.lab); self.desk = FraudDesk(self.lab, self.world)
        self.agents = Agents(self.lab, Config(daily_calls=100, live=False))
        self.agent = FraudAgent(self.desk, self.agents)

    def tearDown(self):
        self.lab.db.close(); self.temp.cleanup()

    def start(self, flavor='first', request=None):
        report = self.desk.demo(flavor, request or 'case-' + str(self.lab.db.execute('SELECT count(*) FROM fraud_reports').fetchone()[0]))
        return report, self.agent.start(report['id'])

    def finish(self, run):
        for _ in range(7):
            if run['status'] != 'running': return run
            run = self.agent.step(run['id'], run['step'])
        self.fail('Unbounded ADK loop')

    def approve(self, report, run):
        return self.desk.review(report['id'], run['id'], 'confirmed_scam', 'request_recall',
            'The analyst verified the reported impersonation and transfer.', True, LESSON, QUESTION)

    def test_native_tool_choice_differs_and_uses_actual_results(self):
        first, run = self.start(); run = self.finish(run)
        self.assertEqual(run['status'], 'awaiting_review')
        self.assertEqual([r['tool'] for r in run['trace']], ['get_transactions','search_reviewed_cases','compare_behavior','trace_recipient','submit_for_review'])
        self.assertTrue(run['context']['adk_trace'][-1]['function_responses'])
        benign, clean = self.start('benign'); clean = self.finish(clean)
        self.assertEqual(clean['status'], 'awaiting_review'); self.assertEqual(clean['step'], 2)
        self.assertEqual(clean['recommendation']['disposition'], 'likely_legitimate')
        observed = []
        def alternative(packet):
            observed.append(packet)
            if not packet['observations']: return 'compare_behavior', {'window_days':7,'purpose':'Inspect seven days before selecting the next check.'}
            return fixture_choice(packet)
        self.agent.model_factory = lambda: FakeInvestigator(chooser=alternative)
        _, alternative_run = self.start('benign'); alternative_run = self.finish(alternative_run)
        self.assertEqual(alternative_run['status'], 'awaiting_review')
        self.assertEqual(alternative_run['trace'][0]['tool'], 'compare_behavior')
        self.assertEqual(observed[1]['observations'][0]['result']['window_days'], 7)
        self.assertEqual(self.agents.budget()['calls_today'], 0); self.assertTrue(self.lab.integrity())

    def test_approved_memory_question_pause_resume_and_case_budget_survive_restart(self):
        report, run = self.start(); run = self.finish(run)
        self.assertFalse(self.desk.memories()); self.approve(report, run)
        second, run = self.start('repeat'); run = self.finish(run)
        self.assertEqual(run['status'], 'awaiting_customer'); self.assertEqual(run['step'], 3)
        self.assertEqual(run['trace'][0]['tool'], 'search_reviewed_cases')
        self.assertEqual(run['context']['pending_question'], QUESTION)
        self.assertEqual(run['context']['memories'][0]['source_report_id'], report['id'])
        calls = run['budget']['case_calls']; old_id = run['id']
        self.lab.db.close(); self.lab = Lab(self.path); self.world = World(self.lab); self.desk = FraudDesk(self.lab, self.world)
        self.agents = Agents(self.lab, Config(daily_calls=100)); self.agent = FraudAgent(self.desk, self.agents)
        self.desk.answer(second['id'], 'Yes. The caller told me to keep it secret from bank staff.', second['revision'])
        resumed = self.agent.start(second['id'])
        self.assertNotEqual(resumed['id'], old_id); self.assertEqual(resumed['budget']['case_calls'], calls)
        self.assertEqual(len(resumed['context']['answers']), 1)
        resumed = self.finish(resumed)
        self.assertEqual(resumed['status'], 'awaiting_review'); self.assertEqual(resumed['budget']['case_calls'], 5)
        self.assertTrue(resumed['recommendation']['memory_ids'])
        self.assertEqual(resumed['budget']['actual_usd'], 0)

    def test_model_can_choose_a_different_question_and_resume_from_answer(self):
        question = 'Did anyone promise to return a larger amount after this transfer?'
        def choose(packet):
            if not packet['customer_replies']: return 'ask_customer', {'question':question,'purpose':'Establish whether a return was promised before reading spending patterns.'}
            return fixture_choice(packet)
        self.agent.model_factory = lambda: FakeInvestigator(chooser=choose)
        report, run = self.start('benign'); run = self.finish(run)
        self.assertEqual(run['step'], 1); self.assertEqual(run['context']['pending_question'], question)
        self.assertFalse(run['recommendation']); self.assertFalse(self.desk.memories())
        self.desk.answer(report['id'], 'No. I recognized the merchant and received my items.', report['revision'])
        resumed = self.finish(self.agent.start(report['id']))
        self.assertEqual(resumed['status'], 'awaiting_review'); self.assertEqual(resumed['budget']['case_calls'], 3)

    def test_live_gate_prevents_client_creation(self):
        report = self.desk.demo('first','live-off')
        with patch.dict(os.environ, {'MINTTOWN_FRAUD_LIVE':'1','GOOGLE_CLOUD_PROJECT':'fake-project'}), patch('google.genai.Client.__init__', side_effect=AssertionError('No live client')) as client:
            with self.assertRaisesRegex(LabError, 'Live Gemini is off'): self.agent.start(report['id'], 'gemini')
            self.finish(self.agent.start(report['id'], 'fake'))
            client.assert_not_called()
        self.assertEqual(self.agents.budget()['calls_today'], 0)

    def test_daily_call_cap_lifetime_cap_and_provider_pin(self):
        self.agents.config = Config(daily_calls=1)
        _, run = self.start(); run = self.finish(run)
        self.assertEqual(run['status'], 'budget_exhausted'); self.assertIn('Daily model-call', run['context']['stop_reason'])
        self.agents.config = Config(daily_calls=100, total_usd=.01)
        self.agent.model_factory = self.expensive_model
        _, run = self.start(); run = self.finish(run)
        self.assertEqual(run['status'], 'budget_exhausted'); self.assertIn('Lifetime', run['context']['stop_reason'])
        self.agents.config = Config(live=True, daily_calls=100)
        with patch.dict(os.environ, {'MINTTOWN_FRAUD_LIVE':'1','GOOGLE_CLOUD_PROJECT':'test-only'}):
            with self.assertRaisesRegex(LabError, 'provider is pinned'): self.agent.start(run['report_id'], 'gemini')

    def test_scope_invalid_tool_and_fabricated_citation_are_rejected(self):
        choices = [
            lambda p: ('approve_case', {'report_id':p['report_id']}),
            lambda p: ('get_transactions', {'event_ids':['somebody-elses-payment'],'purpose':'Read an unrelated transaction.'}),
            lambda p: ('trace_recipient', {'recipient_id':'treasury','purpose':'Read an account unrelated to this report.'}),
        ]
        for choice in choices:
            self.agent.model_factory = lambda choice=choice: FakeInvestigator(chooser=choice)
            _, run = self.start(); result = self.finish(run)
            self.assertEqual(result['status'], 'failed'); self.assertFalse(result['recommendation'])
        def fabricated(packet):
            name, args = fixture_choice(packet)
            if name == 'submit_for_review': args['memory_ids'] = ['MEM-not-retrieved']
            return name, args
        self.agent.model_factory = lambda: FakeInvestigator(chooser=fabricated)
        _, run = self.start('benign'); result = self.finish(run)
        self.assertEqual(result['status'], 'failed'); self.assertIn('not retrieved', result['context']['stop_reason'])
        self.assertFalse(self.desk.memories()); self.assertTrue(self.lab.integrity())

    def expensive_model(self):
        def choose(packet):
            return 'compare_behavior', {'window_days':len(packet['observations'])+1, 'purpose':'Inspect a different bounded time window.'}
        return FakeInvestigator(chooser=choose, input_tokens=16000, output_tokens=512)

    def test_per_case_cost_limit_stops_before_next_model_call_and_allows_human_handoff(self):
        self.agent.model_factory = self.expensive_model
        report, run = self.start(); run = self.finish(run)
        self.assertEqual(run['status'], 'budget_exhausted'); self.assertEqual(run['step'], 2)
        self.assertIn('Per-case cost', run['context']['stop_reason'])
        self.assertEqual(run['budget']['case_committed_microusd'], 12160)
        self.assertLessEqual(run['budget']['case_committed_microusd'], 20000)
        handed = self.agent.handoff(run['id'])
        self.assertEqual(handed['status'], 'awaiting_review'); self.assertTrue(handed['investigation']['context']['manual_handoff'])
        self.assertEqual(handed['investigation']['budget']['case_calls'], 2)
        self.assertFalse(self.desk.memories()); self.assertTrue(self.lab.integrity())

    def test_daily_limit_is_shared_across_cases_and_resets_on_utc_day(self):
        self.agents.config = Config(daily_calls=100, daily_usd=.015)
        date = ['2026-10-12T23:59:00+00:00']; self.agent.clock = lambda: date[0]
        self.agent.model_factory = self.expensive_model
        _, one = self.start(); one = self.agent.step(one['id'], 0)
        _, two = self.start(); two = self.agent.step(two['id'], 0)
        self.assertEqual(two['status'], 'budget_exhausted'); self.assertIn('Daily cost', two['context']['stop_reason'])
        self.assertEqual(two['budget']['daily_calls'], 1)
        date[0] = '2026-10-13T00:01:00+00:00'
        one = self.agent.step(one['id'], one['step'])
        self.assertEqual(one['status'], 'running'); self.assertEqual(one['budget']['case_calls'], 2)
        one = self.agent.step(one['id'], one['step'])
        self.assertEqual(one['status'], 'budget_exhausted'); self.assertIn('Per-case cost', one['context']['stop_reason'])

    def test_generation_limit_and_identical_retry_are_bounded(self):
        self.agent.model_factory = lambda: FakeInvestigator(chooser=lambda p: ('compare_behavior', {'window_days':len(p['observations'])+1,'purpose':'Choose another bounded window.'}))
        _, run = self.start(); first = self.agent.step(run['id'], 0)
        self.assertEqual(self.agent.step(run['id'], 0), first)
        run = self.finish(first)
        self.assertEqual(run['status'], 'budget_exhausted'); self.assertEqual(run['budget']['case_calls'], 6)
        self.assertIn('generation limit', run['context']['stop_reason'])

    def test_repeated_tool_ignores_cosmetic_purpose_changes(self):
        self.agent.model_factory = lambda: FakeInvestigator(chooser=lambda p: ('compare_behavior', {'window_days':7,'purpose':'Inspect this window again '+str(len(p['observations']))}))
        _, run = self.start(); result = self.finish(run)
        self.assertEqual(result['status'], 'failed'); self.assertIn('Repeated tool', result['context']['stop_reason'])
        self.assertEqual(result['budget']['case_calls'], 2)

    def test_failure_reservations_and_global_gemini_accounting(self):
        def broken(packet): raise TimeoutError('Simulated transport interruption')
        self.agent.model_factory = lambda: FakeInvestigator(chooser=broken)
        report, run = self.start(); result = self.finish(run)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['budget']['case_committed_microusd'], RESERVE_MICROUSD)
        # A synthetic ledger row verifies cross-feature accounting; no Gemini client runs.
        with self.lab.db: self.lab.db.execute("UPDATE fraud_agent_turns SET provider='gemini' WHERE run_id=?", (run['id'],))
        self.assertEqual(self.agents.budget()['committed_microusd_today'], RESERVE_MICROUSD)
        self.assertEqual(self.agents.budget()['calls_today'], 1)

    def test_parallel_requests_reserve_before_calling_the_model(self):
        entered, release = threading.Event(), threading.Event()
        def slow(packet):
            entered.set()
            if not release.wait(5): raise TimeoutError('Test synchronization failed')
            return fixture_choice(packet)
        self.agents.config = Config(daily_calls=100, daily_usd=.015)
        self.agent.model_factory = lambda: FakeInvestigator(chooser=slow)
        _, first = self.start('benign'); _, second = self.start('benign'); outcomes = []
        worker = threading.Thread(target=lambda: outcomes.append(self.agent.step(first['id'],0)))
        worker.start()
        try:
            self.assertTrue(entered.wait(5))
            with self.assertRaisesRegex(LabError, 'already running'): self.agent.step(first['id'],0)
            stopped = self.agent.step(second['id'],0)
            self.assertEqual(stopped['status'], 'budget_exhausted'); self.assertEqual(stopped['budget']['daily_calls'],1)
        finally: release.set(); worker.join(8)
        self.assertFalse(worker.is_alive()); self.assertEqual(outcomes[0]['status'],'running')

    def test_context_and_stale_evidence_stop_without_unsafe_actions(self):
        report, run = self.start('benign'); run = self.agent.step(run['id'],0)
        with self.lab.db: self.lab.db.execute("UPDATE financial_events SET metadata='{}' WHERE id=?", (report['event_ids'][0],))
        run = self.finish(run)
        self.assertEqual(run['status'],'failed'); self.assertIn('evidence changed',run['context']['stop_reason'])
        huge = self.desk.create('C003','界'*4000,'界'*2000,report['event_ids'],'large-context')
        run = self.finish(self.agent.start(huge['id']))
        self.assertEqual(run['budget']['case_calls'],0); self.assertIn('context limit',run['context']['stop_reason'])


if __name__ == '__main__': unittest.main(verbosity=2)
