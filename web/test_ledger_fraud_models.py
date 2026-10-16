import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fraud_adk import FakeInvestigator
from fraud_harness_fixtures import choose
from ledger_fraud_features import FEATURES, snapshot_records

from agents import Config
from fraud_models import manifests, predict
from lab import LabError
from server import make_server


class LedgerClassifierChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = make_server(0, Path(self.tmp.name) / 'test.db', Config(live=False))
        self.report = self.server.fraud_desk.demo('phishing', 'ledger-model-test')
        self.run = self.server.fraud_agent.start(self.report['id'])
        self.snapshot = self.server.fraud_agent.snapshot(self.run['context']['snapshot_id'])
        self.model_id = 'ledger_transaction_v1'

    def tearDown(self):
        self.server.server_close()
        self.server.lab.db.close()
        self.tmp.cleanup()

    def test_manifest_registers_without_bigquery_ml(self):
        card = manifests(self.server.lab)[self.model_id]
        self.assertTrue(card['available'])
        self.assertEqual(card['feature_version'], 'ledger-features-v2')
        self.assertEqual(card['score_kind'], 'uncalibrated_model_score')

    def test_scoped_score_ignores_hidden_labels(self):
        baseline = predict([self.model_id], self.report['event_ids'], self.snapshot, manifests(self.server.lab), self.report['customer_id'], self.server.lab)[0]
        self.assertIn(baseline['status'], ('scored', 'partial'))
        changed = copy.deepcopy(self.snapshot)
        for tx in changed['data']['transactions']:
            tx['metadata'].update(is_fraud=True, scam_type='anything', risk_score=100, risk_factors=['cheat'])
        other = predict([self.model_id], self.report['event_ids'], changed, manifests(self.server.lab), self.report['customer_id'], self.server.lab)[0]
        self.assertEqual(baseline['input_hash'], other['input_hash'])
        self.assertEqual(baseline['prediction']['signal_score'], other['prediction']['signal_score'])

    def test_missing_projection_fails_closed(self):
        changed = copy.deepcopy(self.snapshot)
        changed['data'].pop('ledger_features', None)
        result = predict([self.model_id], self.report['event_ids'], changed, manifests(self.server.lab), self.report['customer_id'], self.server.lab)[0]
        self.assertEqual(result['status'], 'not_available')
        self.assertIsNone(result['prediction']['signal_score'])

    def test_foreign_event_rejected(self):
        with self.assertRaises(LabError):
            predict([self.model_id], ['foreign-event'], self.snapshot, manifests(self.server.lab), self.report['customer_id'], self.server.lab)

    def test_score_survives_later_wallet_state_and_excludes_label_proxies(self):
        pinned = manifests(self.server.lab)
        before = predict([self.model_id], self.report['event_ids'], self.snapshot, pinned, self.report['customer_id'], self.server.lab)[0]
        with self.server.lab.db:
            self.server.lab.db.execute('UPDATE accounts SET balance_minor=balance_minor+999999')
        after = predict([self.model_id], self.report['event_ids'], self.snapshot, pinned, self.report['customer_id'], self.server.lab)[0]
        self.assertEqual(before['input_hash'], after['input_hash'])
        self.assertEqual(before['prediction'], after['prediction'])
        self.assertFalse(set(FEATURES) & {'risk_score','risk_factors','is_fraud','scam_type','current_balance','wallet_status','trust_score','risk_tier'})

    def test_temporal_inputs_and_model_version_fail_closed(self):
        changed = copy.deepcopy(self.snapshot)
        for record in changed['data']['ledger_features'].values():record['available_at']='2099-01-01T00:00:00Z'
        result = predict([self.model_id], self.report['event_ids'], changed, manifests(self.server.lab), self.report['customer_id'], self.server.lab)[0]
        self.assertEqual(result['status'], 'not_available')
        pinned = manifests(self.server.lab);pinned[self.model_id]['version']='stale'
        result = predict([self.model_id], self.report['event_ids'], self.snapshot, pinned, self.report['customer_id'], self.server.lab)[0]
        self.assertEqual(result['status'], 'not_available')
        self.assertIsNone(result['prediction'])

    def test_below_threshold_claim_is_blocked_before_analyst_approval(self):
        from fraud_harness import FraudHarness
        agent=self.server.fraud_agent
        snapshot=self.snapshot
        run=agent.step(self.run['id'],self.run['step'])
        scored=agent.harness.score(run,self.report,snapshot,{'model_ids':[self.model_id],'event_ids':self.report['event_ids']})
        receipt=scored['receipts'][0]
        # Use a captured below-threshold result to isolate the semantic guard.
        receipt=copy.deepcopy(receipt);receipt['prediction'].update(available=True,signal_score=.58,threshold=.7,result='no elevated learned signal')
        self.assertFalse(FraudHarness.compact_receipt(receipt)['prediction']['signal_elevated'])
        draft={'summary':'Models note elevated risk signals.','customer_message':'An analyst will review the report.',
               'evidence_ids':self.report['event_ids'],'memory_ids':[],'uncertainties':['Identity is unverified.']}
        with patch.object(agent.harness,'receipts',return_value=[receipt]):
            checked=agent.harness.check(run,draft,[receipt['receipt_id']],record=False)
        self.assertFalse(checked['passed'])
        self.assertIn('operating threshold',' '.join(checked['judges'][1]['blockers']))
        draft['summary']='The models report no elevated signal; the complaint still warrants investigation.'
        with patch.object(agent.harness,'receipts',return_value=[receipt]):
            checked=agent.harness.check(run,draft,[receipt['receipt_id']],record=False)
        self.assertTrue(checked['passed'],checked)

    def test_real_harness_uses_model_receipt_and_requires_review(self):
        def policy(packet):
            tool,args=choose(packet)
            if tool=='score_models':args['model_ids']=[self.model_id,'message_intent_v1']
            return tool,args
        agent=self.server.fraud_agent;agent.model_factory=lambda:FakeInvestigator(chooser=policy)
        run=self.run
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No paid calls')):
            for _ in range(6):
                if run['status']!='running':break
                run=agent.step(run['id'],run['step'])
        self.assertEqual(run['status'],'awaiting_review',run['context'].get('stop_reason'))
        receipts=agent.harness.receipts(run['id'])
        ledger=next(r for r in receipts if r['model_id']==self.model_id)
        self.assertEqual(ledger['status'],'scored')
        checks=self.server.fraud_desk.detail(self.report['id'])['harness']['checks']
        self.assertIn(ledger['receipt_id'],checks[0]['receipt_ids'])
        self.assertTrue(checks[0]['passed'])
        self.assertFalse(self.server.fraud_desk.detail(self.report['id'])['reviews'])


if __name__ == '__main__':
    unittest.main()

