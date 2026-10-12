"""Programmatic playbook/Google-routing checks. All Gemini responses are fake."""
import json
import tempfile
import unittest
from pathlib import Path

from adk_mesh import dispatch, runtime
from agents import Config
from lab import LabError
from mesh import Mesh, ROLES, LEGACY_ROLE_IDS
from server import make_server


class MeshChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = make_server(0, Path(self.temp.name) / 'test.db', Config())
        self.mesh, self.lab = self.server.mesh, self.server.lab

    def tearDown(self):
        self.server.server_close(); self.lab.db.close(); self.temp.cleanup()

    def finish(self, run, use_adk=False):
        for _ in range(13):
            if run['status'] != 'running': return run
            run = dispatch(self.mesh, run['id'], run['step']) if use_adk else self.mesh.step(run['id'], run['step'])
        self.fail('The bounded run did not stop.')

    def test_five_role_financial_service_receipts_and_adk_trace(self):
        run = self.mesh.start('fraud-response', 'baseline', 'fraud-run', 'F001')
        same = self.mesh.start('fraud-response', 'baseline', 'fraud-run', 'F001')
        self.assertEqual(run['id'], same['id'])
        run = self.finish(run, use_adk=True)
        self.assertEqual(run['status'], 'completed')
        self.assertEqual({t['from_role'] for t in run['turns']}, set(LEGACY_ROLE_IDS))
        self.assertTrue(run['context']['verified']); self.assertTrue(self.lab.integrity())
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM service_actions').fetchone()[0], 1)
        self.assertEqual(self.mesh.step(run['id'], 0)['step'], 7)
        self.assertEqual(self.server.agents.budget()['calls_today'], 0)
        if runtime()['engine'] == 'google-adk':
            self.assertTrue(all(t['router_trace'] for t in run['turns']))
            self.assertTrue(any(e['route'] == 'scientist' for t in run['turns'] for e in t['router_trace']))
        # Reconstruct the runtime and ensure conversation, prompts and receipts remain.
        restored = Mesh(self.lab, self.server.world, self.server.macro, self.server.science_team, self.server.agents)
        self.assertEqual(restored.run(run['id'])['turns'], run['turns'])

    def test_domain_playbooks_share_roles_and_pin_edited_prompts(self):
        old = self.mesh.start('savings-science', 'baseline', 'old-prompt')
        p = self.mesh.playbook('savings-science')
        prompts = dict(p['prompts']); prompts['scientist'] = 'Investigate the policy context and seek evidence of changing savings behavior.'
        updated = self.mesh.save(p['id'], p['revision'], p['objective'], prompts, 8)
        fresh = self.mesh.start('savings-science', 'baseline', 'new-prompt')
        self.assertEqual(updated['revision'], 2)
        self.assertEqual(old['playbook']['revision'], self.mesh.run(old['id'])['playbook']['revision'])
        self.assertNotEqual(old['playbook']['prompts']['scientist'], fresh['playbook']['prompts']['scientist'])
        self.assertEqual(set(fresh['playbook']['prompts']), set(LEGACY_ROLE_IDS))
        with self.assertRaises(LabError): self.mesh.save(p['id'], 1, p['objective'], prompts, 8)
        with self.assertRaises(LabError): self.mesh.start('cashflow-care', 'baseline', 'wrong-case', 'F001')

    def test_weak_model_is_withheld_and_macro_uses_actual_bank_gate(self):
        run = self.finish(self.mesh.start('savings-science', 'baseline', 'weak-candidate'))
        self.assertEqual(run['status'], 'withheld'); self.assertIsNone(self.server.science_team.active('propensity'))
        self.assertNotIn('execute_plan', [t['decision']['tool'] for t in run['turns']])
        self.assertTrue(any(t['artifact']['data'].get('routing_gate') for t in run['turns']))
        for tick in range(6): self.server.world.advance(tick, 3, 'demand' if tick == 0 else 'none')
        before = self.server.macro.policy()['loan_bps']
        run = self.finish(self.mesh.start('macro-policy', 'baseline', 'macro-run'))
        self.assertEqual(run['status'], 'completed')
        self.assertEqual(self.server.macro.policy()['loan_bps'], before + 100)
        self.assertTrue(self.lab.integrity())

    def test_gemini_contract_can_handoff_back_and_uses_shared_budget(self):
        self.server.agents.config = Config(api_key='test-only', live=True, daily_calls=10)
        run_id = []; challenged = []; packets = []
        def fake(config, packet):
            packets.append(packet)
            run = self.mesh.run(run_id[0]); decision = self.mesh.baseline(run)
            if packet['role'] == 'verifier' and not challenged:
                challenged.append(True)
                decision.update(tool='handoff', args={}, to_role='scientist', message='Please recheck the source authorization before I approve the proposed action.')
            return {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(decision)}]}}],
                    'usageMetadata': {'promptTokenCount': 1000, 'candidatesTokenCount': 120}}
        self.server.agents.transport = fake
        run = self.mesh.start('fraud-response', 'gemini', 'fake-gemini', 'F001'); run_id.append(run['id'])
        run = self.finish(run, use_adk=True)
        self.assertEqual(run['status'], 'completed'); self.assertEqual(run['step'], 10)
        self.assertTrue(any(t['from_role'] == 'verifier' and t['to_role'] == 'scientist' for t in run['turns']))
        self.assertTrue(all(p['role_prompt'] == run['playbook']['prompts'][p['role']] for p in packets))
        self.assertEqual(self.server.agents.budget()['calls_today'], 10)
        with self.assertRaises(LabError) as error: self.server.agents.analyze('F003', 'gemini')
        self.assertEqual(error.exception.status, 429)

    def test_route_permissions_and_budget_stop_before_another_call(self):
        calls = []; self.server.agents.config = Config(api_key='test-only', live=True, daily_calls=1)
        def fake(config, packet):
            calls.append(packet)
            decision = {'outcome': 'route', 'to_role': 'scientist', 'tool': 'inspect_context', 'args': {},
                        'message': 'Inspect the recorded financial evidence before proposing an intervention.', 'evidence_ids': []}
            return {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': json.dumps(decision)}]}}],
                    'usageMetadata': {'promptTokenCount': 100, 'candidatesTokenCount': 100}}
        self.server.agents.transport = fake
        run = self.mesh.start('fraud-response', 'gemini', 'budget-stop', 'F001')
        run = self.mesh.step(run['id'], 0); run = self.mesh.step(run['id'], 1)
        self.assertEqual(run['status'], 'budget_exhausted'); self.assertEqual(len(calls), 1)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM service_actions').fetchone()[0], 0)
        offline = self.mesh.start('fraud-response', 'baseline', 'invalid-route', 'F001')
        wrong = self.mesh.baseline(offline); wrong.update(to_role='engineer', tool='execute_plan', args={'artifact_id': 'invented'})
        with self.assertRaises(LabError): self.mesh.validate(offline, wrong)
        wrong = self.mesh.baseline(offline); wrong['evidence_ids'] = ['made-up-evidence']
        with self.assertRaises(LabError): self.mesh.validate(offline, wrong)

    def test_stale_approval_cannot_execute(self):
        run = self.mesh.start('fraud-response', 'baseline', 'stale-approval', 'F001')
        for _ in range(4): run = self.mesh.step(run['id'], run['step'])
        self.assertEqual(run['active_role'], 'engineer')
        self.server.world.advance(0, 1)
        with self.assertRaisesRegex(LabError, 'world changed'): self.mesh.step(run['id'], run['step'])
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM service_actions').fetchone()[0], 0)
        self.assertEqual(self.mesh.run(run['id'])['status'], 'failed')
        self.assertTrue(self.lab.integrity())

    def test_small_turn_budget_cannot_spend_the_verification_steps(self):
        p = self.mesh.playbook('fraud-response')
        self.mesh.save(p['id'], p['revision'], p['objective'], p['prompts'], 5)
        run = self.mesh.start('fraud-response', 'baseline', 'short-run', 'F001')
        for _ in range(4): run = self.mesh.step(run['id'], run['step'])
        with self.assertRaisesRegex(LabError, 'three turns'): self.mesh.step(run['id'], run['step'])
        self.assertEqual(self.mesh.run(run['id'])['status'], 'budget_exhausted')
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM service_actions').fetchone()[0], 0)


if __name__ == '__main__': unittest.main(verbosity=2)
