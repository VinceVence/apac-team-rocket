import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        self.assertEqual(card['feature_version'], 'ledger-features-v1')
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
        with patch.object(self.server.lab, 'environment_data', None):
            result = predict([self.model_id], self.report['event_ids'], self.snapshot, manifests(self.server.lab), self.report['customer_id'], self.server.lab)[0]
        self.assertEqual(result['status'], 'not_available')
        self.assertIsNone(result['prediction']['signal_score'])

    def test_foreign_event_rejected(self):
        with self.assertRaises(LabError):
            predict([self.model_id], ['foreign-event'], self.snapshot, manifests(self.server.lab), self.report['customer_id'], self.server.lab)


if __name__ == '__main__':
    unittest.main()
