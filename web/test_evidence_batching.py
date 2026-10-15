"""Publication saturation must not strand valid, durable simulation evidence."""
import datetime as dt
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from cloud_data import CloudData
DAILY_EXPORTS=25  # Explicitly exercise saturation; production uses spend/size gates.
from lab import LabError, now
from server import make_server
from test_environment_cloud import EnvironmentCloud


class EvidenceBatchChecks(unittest.TestCase):
    def setUp(self):
        for module in ('cloud_data','environment_cloud','warehouse','world_demo'):
            limit=patch(module+'.DAILY_EXPORTS',DAILY_EXPORTS);limit.start();self.addCleanup(limit.stop)
        self.tmp=tempfile.TemporaryDirectory();self.remote=EnvironmentCloud()
        self.cloud=CloudData('test-project','test-state','demo',session=self.remote)
        self.env=patch.dict('os.environ',{'MINTTOWN_ENV_DATASET':'minttown_world','PALLET_WAREHOUSE_ENABLED':'1',
            'MINTTOWN_LIVE':'0','MINTTOWN_FRAUD_LIVE':'0','MINTTOWN_CLOUD_LIVE':'0'})
        self.env.start();self.sdk=patch('google.genai.Client.__init__',side_effect=AssertionError('No paid model'))
        self.sdk.start();self.server=make_server(0,Path(self.tmp.name)/'test.db',cloud=self.cloud,seed_history=False)
        self.demo,self.lab,self.desk=self.server.world_demo,self.server.lab,self.server.fraud_desk
        self.run=self.demo.start(0,fresh=True,background=False,mode='simulation')['run_id']

    def tearDown(self):
        self.server.server_close();self.lab.db.close();self.sdk.stop();self.env.stop();self.tmp.cleanup()

    def wait(self,rid):
        deadline=time.monotonic()+10
        while self.server.fraud_runner.pending and time.monotonic()<deadline:time.sleep(.02)
        self.assertFalse(self.server.fraud_runner.pending)
        return self.desk.detail(rid)

    def incident(self,kind,cycle=0):
        identifier=self.demo.incident(self.run,kind,cycle=cycle)
        rid=self.lab.db.execute('SELECT report_id FROM world_incidents WHERE id=?',(identifier,)).fetchone()[0]
        return identifier,rid

    def exhaust(self):
        with self.lab.db:self.lab.db.execute('INSERT OR REPLACE INTO demo_usage_archive VALUES(?,?,0,0)',
            (now()[:10],DAILY_EXPORTS-self.cloud.daily_exports(self.lab)))

    def test_six_stranded_cases_finish_with_no_new_bigquery_writes_or_queries(self):
        self.exhaust();saved=[]
        with patch.object(self.demo,'prepare'):
            for n,kind in enumerate(('phishing','payment_burst','invoice_redirect','task_scam','investment_scam','phishing')):
                identifier,rid=self.incident(kind,n)
                self.desk.prepare(rid,'blocked','preparation','Daily BigQuery publication limit reached.')
                saved.append((identifier,rid))
        for identifier,rid in saved:
            self.demo.prepare(rid,identifier,'fake');case=self.wait(rid)
            self.assertEqual(case['status'],'awaiting_review',case['investigation']['context'].get('stop_reason'))
            self.assertEqual(case['preparation']['status'],'completed')
            features=case['investigation']['context']['warehouse_features']
            self.assertEqual(features['source']['provider'],'Simulation ledger')
            self.assertEqual(features['features']['customer_id'],case['customer_id'])
            self.assertLessEqual(case['investigation']['budget']['case_calls'],6)
        self.assertEqual(len(self.remote.jobs),0)
        self.assertEqual(self.cloud.daily_exports(self.lab),DAILY_EXPORTS)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0],30)
        self.assertTrue(self.lab.integrity())

    def test_six_reports_use_two_shared_batches_instead_of_six(self):
        for n,kind in enumerate(('phishing','payment_burst','invoice_redirect','task_scam','investment_scam','phishing')):
            _,rid=self.incident(kind,n);self.wait(rid)
            self.assertEqual(self.cloud.daily_exports(self.lab),2 if n<5 else 4)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM warehouse_snapshots').fetchone()[0],2)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM environment_publications').fetchone()[0],2)
        # Only reports whose records are in the two completed batches query BQ.
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM warehouse_queries').fetchone()[0],2)
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM environment_feature_coverage').fetchone()[0],1)

    def test_exact_completed_snapshot_reuses_at_cap_but_stale_uncertain_and_expired_do_not(self):
        _,rid=self.incident('phishing');self.wait(rid)
        warehouse=self.server.warehouse;matching=warehouse.matching_snapshot()
        self.assertIsNotNone(matching);self.exhaust();jobs=len(self.remote.jobs)
        self.assertIn('Reusing',self.demo.sync_analytics());self.assertEqual(len(self.remote.jobs),jobs)
        with self.lab.db:self.lab.db.execute("UPDATE warehouse_snapshots SET status='uncertain'")
        self.assertIsNone(warehouse.matching_snapshot());self.demo.sync_analytics()
        self.assertEqual(len(self.remote.jobs),jobs)
        with self.lab.db:self.lab.db.execute("UPDATE warehouse_snapshots SET status='completed',created_at=?",
            ((dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=8)).isoformat(),))
        self.assertIsNone(warehouse.matching_snapshot())
        with self.lab.db:self.lab.db.execute('UPDATE warehouse_snapshots SET created_at=?',(now(),))
        self.server.world.advance(self.server.world.state()['tick'],4)
        self.assertIsNone(warehouse.matching_snapshot())

    def test_case_features_stop_at_report_time_and_keep_labels_out(self):
        self.exhaust();_,rid=self.incident('phishing');case=self.wait(rid)
        snap=self.server.fraud_agent.snapshot(case['investigation']['context']['snapshot_id'])
        before=snap['data']['customer_features'];cutoff=before['source']['cutoff']
        self.server.world.payment('later-payment','C001','m1',100,'device-C001',
            {'device_known':False,'is_fraud':True,'risk_score':1,'scam_type':'secret'},occurred_at=cutoff[:10]+'T23:00:00Z')
        after=self.server.warehouse.frozen_features('C001',cutoff)
        self.assertEqual(before,after);self.assertNotIn('is_fraud',json.dumps(after))
        self.assertEqual(after['features']['payment_count'],1)
        self.assertEqual(after['features']['baseline_days'],0)
        with self.assertRaises(LabError):self.server.warehouse.frozen_features('C999',cutoff)
        with self.lab.db:self.lab.db.execute("UPDATE fraud_reports SET event_ids='[]' WHERE id=?",(rid,))
        with self.assertRaises(LabError):self.demo.prepare_evidence(rid)

    def test_fenced_checkpoint_still_blocks_work_and_partial_batch_is_not_retried(self):
        self.remote.fail_table='devices'
        _,rid=self.incident('phishing');case=self.wait(rid)
        self.assertEqual(case['status'],'awaiting_review')
        self.assertEqual(self.server.environment_publisher.status()['latest']['status'],'uncertain')
        jobs=len(self.remote.jobs);self.server.world.advance(self.server.world.state()['tick'],1)
        self.demo.sync_analytics();self.assertEqual(len(self.remote.jobs),jobs)
        self.cloud.healthy=False
        with self.assertRaisesRegex(LabError,'Cloud state'):self.demo.sync_analytics()
        self.cloud.healthy=True


if __name__=='__main__':unittest.main()
