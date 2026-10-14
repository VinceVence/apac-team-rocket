import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from agents import Config
from server import make_server
from fraud_models import manifests,predict
from lab import LabError

class ModelContractChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.server=make_server(0,Path(self.tmp.name)/'test.db',Config(live=False))
        self.report=self.server.fraud_desk.demo('phishing','models');self.run=self.server.fraud_agent.start(self.report['id'])
        self.snapshot=self.server.fraud_agent.snapshot(self.run['context']['snapshot_id'])
    def tearDown(self):self.server.server_close();self.server.lab.db.close();self.tmp.cleanup()
    def test_receipt_is_scoped_versioned_and_not_a_probability(self):
        result=predict(['device_integrity_v1'],self.report['event_ids'],self.snapshot,manifests(),self.report['customer_id'])[0]
        self.assertEqual(result['score_kind'],'rule_signal');self.assertFalse(result['calibrated']);self.assertEqual(result['status'],'scored')
        self.assertEqual(result['snapshot_hash'],self.snapshot['evidence_hash']);self.assertEqual(len(result['input_hash']),64)
        changed=copy.deepcopy(self.snapshot)
        for t in changed['data']['transactions']:t['metadata'].update(is_fraud=True,scam_type='anything',risk_score=100,risk_factors=['cheat'])
        other=predict(['device_integrity_v1'],[],changed,manifests(),self.report['customer_id'])[0]
        self.assertEqual(other['input_hash'],result['input_hash']);self.assertEqual(other['prediction'],result['prediction'])
        with self.assertRaises(LabError):predict(['device_integrity_v1'],['foreign-event'],self.snapshot,manifests(),self.report['customer_id'])
        with self.assertRaises(LabError):predict(['untrusted-model'],[],self.snapshot,manifests(),self.report['customer_id'])
    def test_missing_and_stale_inputs_do_not_become_zero_risk(self):
        snapshot=copy.deepcopy(self.snapshot)
        for t in snapshot['data']['transactions']:t['metadata'].pop('device_known',None)
        result=predict(['device_integrity_v1'],[],snapshot,manifests(),self.report['customer_id'])[0]
        self.assertEqual(result['status'],'not_available');self.assertIsNone(result['prediction']['signal_score']);self.assertTrue(result['missing_inputs'])
        pinned=manifests();pinned['device_integrity_v1']['version']='old'
        result=predict(['device_integrity_v1'],[],self.snapshot,pinned,self.report['customer_id'])[0]
        self.assertEqual(result['status'],'not_available');self.assertIsNone(result['prediction'])

    def test_malformed_features_and_future_transactions_fail_closed(self):
        snapshot=copy.deepcopy(self.snapshot)
        for t in snapshot['data']['transactions']:
            t['metadata'].update(prevention_schema_version='prepayment-signals-v1',prevention_features={'unknown_device':None,'unverified_authorization':False})
        result=predict(['device_integrity_v1'],[],snapshot,manifests(),self.report['customer_id'])[0]
        self.assertEqual(result['status'],'not_available');self.assertIsNone(result['prediction']['signal_score'])
        snapshot['data']['transactions'][0]['occurred_at']='2099-01-01T00:00:00Z'
        with self.assertRaisesRegex(LabError,'cutoff'):predict(['device_integrity_v1'],[],snapshot,manifests(),self.report['customer_id'])

if __name__=='__main__':unittest.main()
