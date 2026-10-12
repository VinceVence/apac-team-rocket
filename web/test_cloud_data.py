"""Exercise cloud persistence/export contracts without Google credentials or network."""
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from unittest.mock import patch

from agents import Agents, Config
from cloud_data import CloudData
from fraud_agent import FraudAgent
from fraud_desk import FraudDesk
from lab import Lab, LabError
from world import World


class Response:
    def __init__(self, status=200, data=None, content=b''):
        self.status_code, self.data, self.content = status, data or {}, content
    def json(self): return self.data
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError('Fake HTTP %d' % self.status_code)


class FakeCloud:
    def __init__(self): self.objects={}; self.jobs=[]; self.fail_jobs=False
    def request(self, method, url, **kwargs):
        parts=urlsplit(url)
        if parts.netloc=='bigquery.googleapis.com':
            if method=='POST':
                self.jobs.append(kwargs['json'])
                if self.fail_jobs: raise TimeoutError('Ambiguous batch submission')
            return Response(data={'status':{'state':'DONE'}})
        if method=='POST':
            query=parse_qs(parts.query); name=query['name'][0]; wanted=query['ifGenerationMatch'][0]
            current=self.objects.get(name,('0',b''))
            if wanted!=current[0]:return Response(412)
            generation=str(int(current[0])+1)
            self.objects[name]=(generation,kwargs['data'])
            return Response(data={'generation':generation})
        name=unquote(parts.path.rsplit('/o/',1)[1])
        if name not in self.objects:return Response(404)
        generation,body=self.objects[name]
        if kwargs.get('params',{}).get('alt')=='media':return Response(content=body)
        return Response(data={'generation':generation})


class CloudChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        self.lab=Lab(self.root/'live.db'); self.world=World(self.lab)
        self.desk=FraudDesk(self.lab,self.world); self.agents=Agents(self.lab,Config(live=False))
        self.remote=FakeCloud(); self.cloud=CloudData('test-project','test-bucket','simulation',session=self.remote)
        self.agent=FraudAgent(self.desk,self.agents,checkpoint=lambda:self.cloud.save(self.lab))
        self.cloud.initialize(self.lab)
    def tearDown(self):self.lab.db.close();self.temp.cleanup()

    def test_checkpoint_restores_cases_evidence_and_spending(self):
        report=self.desk.demo('benign','cloud-case'); run=self.agent.start(report['id'])
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No model client')) as client:
            run=self.agent.step(run['id'],0)
            client.assert_not_called()
        self.cloud.save(self.lab)
        copy=CloudData('test-project','test-bucket','simulation',session=self.remote)
        copy.restore(self.root/'restored.db')
        restored=Lab(self.root/'restored.db')
        try:
            desk=FraudDesk(restored,World(restored)); agents=Agents(restored,Config(live=False)); agent=FraudAgent(desk,agents)
            saved=desk.run(run['id'])
            self.assertEqual(saved['snapshot'],run['snapshot'])
            self.assertEqual(saved['budget']['case_calls'],1)
            self.assertEqual(saved['budget']['case_committed_microusd'],run['budget']['case_committed_microusd'])
            self.assertEqual(desk.detail(report['id'])['decision_trail'][0]['finding'],self.desk.detail(report['id'])['decision_trail'][0]['finding'])
            self.assertTrue(restored.integrity())
        finally:restored.db.close()

    def test_generation_conflict_fails_closed_and_does_not_overwrite(self):
        old=CloudData('test-project','test-bucket','simulation',session=self.remote)
        old.restore(self.root/'old.db')
        self.desk.demo('benign','newer-case'); self.cloud.save(self.lab)
        latest=self.remote.objects[self.cloud.state_object]
        stale=Lab(self.root/'old.db')
        try:
            with stale.db:stale.event('old-writer-change','C001','test',0,stale.clock_day)
            with self.assertRaisesRegex(LabError,'checkpoint could not be confirmed'):old.save(stale)
            self.assertFalse(old.healthy)
            self.assertEqual(self.remote.objects[self.cloud.state_object],latest)
            with self.assertRaisesRegex(LabError,'state is unavailable'):old.save(stale)
        finally:stale.db.close()

    def test_checkpoint_failure_prevents_model_execution(self):
        report=self.desk.demo('benign','checkpoint-failure'); run=self.agent.start(report['id'])
        self.cloud.healthy=False
        with patch('fraud_adk.FakeInvestigator.generate_content_async',side_effect=AssertionError('Must reserve durably first')) as generate:
            result=self.agent.step(run['id'],0)
        self.assertEqual(result['status'],'failed');generate.assert_not_called()
        self.assertEqual(result['budget']['case_committed_microusd'],10000)

    def test_export_is_one_idempotent_batch_with_partitionable_records(self):
        result=self.cloud.export(self.lab)
        self.assertEqual(result['status'],'completed');self.assertEqual(len(self.remote.jobs),1)
        job=self.remote.jobs[0]
        self.assertNotIn('query',job['configuration'])
        self.assertEqual(job['configuration']['load']['createDisposition'],'CREATE_NEVER')
        self.assertEqual(job['configuration']['load']['destinationTable']['datasetId'],'simulation')
        raw=self.remote.objects['exports/'+result['id']+'.jsonl.gz'][1]
        records=[json.loads(line) for line in gzip.decompress(raw).splitlines()]
        self.assertEqual(len(records),result['row_count'])
        self.assertEqual({r['source_table'] for r in records},{'customers','accounts','financial_events','ledger_entries'})
        self.assertTrue(all(r['batch_id']==result['id'] and r['exported_at'] and isinstance(r['payload'],dict) for r in records))
        replay=self.cloud.export(self.lab)
        self.assertTrue(replay['replayed']);self.assertEqual(len(self.remote.jobs),1)

    def test_failed_exports_retain_allowance_and_daily_and_size_caps_apply(self):
        self.remote.fail_jobs=True
        for n in range(3):
            with self.lab.db:self.lab.event('batch-change-'+str(n),'C001','test',0,self.lab.clock_day)
            result=self.cloud.export(self.lab);self.assertEqual(result['status'],'uncertain')
            self.assertTrue(self.cloud.export(self.lab)['replayed'])
        with self.lab.db:self.lab.event('over-budget','C001','test',0,self.lab.clock_day)
        with self.assertRaisesRegex(LabError,'Daily BigQuery export'):self.cloud.export(self.lab)
        self.assertEqual(len(self.remote.jobs),3)
        with patch('cloud_data.MAX_EXPORT_ROWS',2),self.assertRaisesRegex(LabError,'row cap'):self.cloud.export(self.lab)

    def test_restore_and_save_have_a_database_size_cap(self):
        with patch('cloud_data.MAX_STATE_BYTES',16),self.assertRaisesRegex(LabError,'database size cap'):self.cloud.save(self.lab)
        self.assertFalse(self.cloud.healthy)
        restored=CloudData('test-project','test-bucket','simulation',session=self.remote)
        with patch('cloud_data.MAX_STATE_BYTES',16),self.assertRaisesRegex(ValueError,'size cap'):restored.restore(self.root/'oversized.db')


if __name__=='__main__':unittest.main(verbosity=2)
