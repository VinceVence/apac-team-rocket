"""Exercise cloud persistence/export contracts without Google credentials or network."""
import gzip
import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from unittest.mock import patch

from agents import Agents, Config
from cloud_data import CloudData, MAX_EXPORT_BYTES, MAX_EXPORT_ROWS
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
    def __init__(self): self.objects={}; self.jobs=[]; self.fail_jobs=False; self.fail_lookup=False; self.job_error=False
    def request(self, method, url, **kwargs):
        parts=urlsplit(url)
        if parts.netloc=='bigquery.googleapis.com':
            if method=='POST':
                self.jobs.append(kwargs['json'])
                if self.fail_jobs: raise TimeoutError('Ambiguous batch submission')
            elif self.fail_lookup: return Response(503)
            status={'state':'DONE'}
            if self.job_error:status['errorResult']={'reason':'invalid','message':'Test load failure'}
            return Response(data={'status':status})
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
        result=self.cloud.export(self.lab,'first-batch')
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
        replay=self.cloud.export(self.lab,'first-batch')
        self.assertTrue(replay['replayed']);self.assertEqual(len(self.remote.jobs),1)
        noop=self.cloud.export(self.lab,'unchanged')
        self.assertEqual(noop['row_count'],0);self.assertEqual(len(self.remote.jobs),1)
        with self.lab.db:self.lab.event('new-event','C001','test',0,self.lab.clock_day)
        self.assertEqual(self.cloud.export(self.lab,'unchanged')['row_count'],0)
        self.assertEqual(self.cloud.status(self.lab)['daily_exports'],1)

    @patch('cloud_data.MAX_EXPORT_ROWS',10000)
    def test_full_hosted_economy_exports_in_complete_bounded_batches(self):
        from server import make_server
        remote=FakeCloud(); cloud=CloudData('test-project','full-seed','simulation',session=remote)
        server=make_server(0,self.root/'full-seed.db',cloud=cloud)
        try:
            lab=server.lab
            self.assertEqual(lab.db.execute('SELECT count(*) FROM customers').fetchone()[0],100)
            expected={r['id'] for r in lab.rows('SELECT id FROM financial_events')}
            self.assertGreater(sum(lab.db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('customers','accounts','financial_events','ledger_entries')),10000)
            seen=set(); leg_ids=set()
            for n in range(2):
                result=cloud.export(lab,'full-batch-'+str(n))
                self.assertEqual(result['status'],'completed')
                self.assertLessEqual(result['row_count'],10000)
                self.assertLessEqual(result['size_bytes'],MAX_EXPORT_BYTES)
                self.assertEqual(cloud.export(lab,'full-batch-'+str(n))['id'],result['id'])
                records=[json.loads(line) for line in gzip.decompress(remote.objects['exports/'+result['id']+'.jsonl.gz'][1]).splitlines()]
                events={r['record_id'] for r in records if r['source_table']=='financial_events'}
                self.assertFalse(seen & events);seen.update(events)
                legs=[r['payload'] for r in records if r['source_table']=='ledger_entries']
                self.assertTrue(all(leg['event_id'] in events for leg in legs))
                for event_id in events:
                    expected_legs={r['id'] for r in lab.rows('SELECT id FROM ledger_entries WHERE event_id=?',(event_id,))}
                    actual={leg['id'] for leg in legs if leg['event_id']==event_id}
                    self.assertEqual(expected_legs,actual)
                    self.assertEqual(sum(leg['delta_minor'] for leg in legs if leg['event_id']==event_id),0)
                leg_ids.update(leg['id'] for leg in legs)
            self.assertEqual(seen,expected)
            self.assertEqual(len(leg_ids),lab.db.execute('SELECT count(*) FROM ledger_entries').fetchone()[0])
            self.assertEqual(result['remaining_events'],0)
            self.assertEqual(len(remote.jobs),2)
            self.assertEqual(cloud.status(lab)['pending_events'],0)
        finally:server.server_close();server.lab.db.close()

    def test_uncertain_export_blocks_new_batch_until_job_is_confirmed(self):
        self.remote.fail_jobs=self.remote.fail_lookup=True
        first=self.cloud.export(self.lab,'uncertain-job')
        self.assertEqual(first['status'],'uncertain')
        with self.lab.db:self.lab.event('after-export','C001','test',0,self.lab.clock_day)
        self.assertEqual(self.cloud.export(self.lab,'uncertain-job')['id'],first['id'])
        with self.assertRaisesRegex(LabError,'still unconfirmed'):self.cloud.export(self.lab,'next-job')
        self.assertEqual(len(self.remote.jobs),1)
        self.remote.fail_jobs=self.remote.fail_lookup=False
        self.assertEqual(self.cloud.export(self.lab,'uncertain-job')['status'],'completed')
        following=self.cloud.export(self.lab,'next-job')
        self.assertEqual(following['event_count'],1)
        self.assertEqual(following['event_start'],first['event_end'])
        self.assertEqual(len(self.remote.jobs),2)

    def test_failed_exports_retain_allowance_and_daily_and_size_caps_apply(self):
        with patch('cloud_data.MAX_EXPORT_ROWS',2),self.assertRaisesRegex(LabError,'row cap'):self.cloud.export(self.lab,'row-limit')
        with patch('cloud_data.MAX_EXPORT_BYTES',32),self.assertRaisesRegex(LabError,'payload cap'):self.cloud.export(self.lab,'byte-limit')
        self.assertEqual(len(self.remote.jobs),0)
        self.remote.job_error=True
        with patch('cloud_data.DAILY_EXPORTS',3):
            for n in range(3):
                with self.lab.db:self.lab.event('batch-change-'+str(n),'C001','test',0,self.lab.clock_day)
                result=self.cloud.export(self.lab,'failed-'+str(n));self.assertEqual(result['status'],'failed')
                self.assertTrue(self.cloud.export(self.lab,'failed-'+str(n))['replayed'])
            with self.lab.db:self.lab.event('over-budget','C001','test',0,self.lab.clock_day)
            with self.assertRaisesRegex(LabError,'Daily BigQuery export'):self.cloud.export(self.lab,'over-budget')
        self.assertEqual(len(self.remote.jobs),3)

    def test_restore_and_save_have_a_database_size_cap(self):
        with patch('cloud_data.MAX_STATE_BYTES',16),self.assertRaisesRegex(LabError,'database size cap'):self.cloud.save(self.lab)
        self.assertFalse(self.cloud.healthy)
        restored=CloudData('test-project','test-bucket','simulation',session=self.remote)
        with patch('cloud_data.MAX_STATE_BYTES',16),self.assertRaisesRegex(ValueError,'size cap'):restored.restore(self.root/'oversized.db')

    def test_hosted_server_ignores_live_flags_and_paid_configuration(self):
        from server import make_server
        cloud=CloudData('test-project','other-bucket','simulation',session=FakeCloud())
        with patch.dict(os.environ,{'MINTTOWN_LIVE':'1','MINTTOWN_FRAUD_LIVE':'1','MINTTOWN_CLOUD_LIVE':'0',
             'MINTTOWN_CLOUD_LIVE_CANARY':'1','GOOGLE_CLOUD_PROJECT':'test-project'}),patch('google.genai.Client.__init__',side_effect=AssertionError('Hosted Gemini is forbidden')) as client:
            server=make_server(0,self.root/'hosted.db',config=Config(live=True,api_key='never-use'),cloud=cloud,public_host='demo.run.app')
            try:
                self.assertFalse(server.agents.config.live)
                self.assertFalse(server.fraud_agent.live_enabled())
                report=server.fraud_desk.demo('benign','hosted-gate')
                with self.assertRaisesRegex(LabError,'Live Gemini is off'):server.fraud_runner.start(report['id'],'gemini')
                client.assert_not_called()
            finally:server.server_close();server.lab.db.close()

    def test_private_live_mode_needs_explicit_gate_and_keeps_fixed_caps(self):
        from server import make_server
        cloud=CloudData('minttown-apac-2026','live-bucket','simulation',session=FakeCloud())
        with patch.dict(os.environ,{'MINTTOWN_LIVE':'1','MINTTOWN_FRAUD_LIVE':'1','MINTTOWN_CLOUD_LIVE':'1',
             'GOOGLE_CLOUD_PROJECT':'minttown-apac-2026','MINTTOWN_DAILY_USD':'999'}),patch('google.genai.Client.__init__',side_effect=AssertionError('Startup must not call Gemini')) as client:
            server=make_server(0,self.root/'hosted-live.db',cloud=cloud)
            try:
                self.assertTrue(server.fraud_agent.live_enabled())
                self.assertTrue(server.agents.budget()['live_enabled'])
                self.assertIn('Vertex AI',server.agents.budget()['mode'])
                self.assertEqual(server.agents.config.api_key,'')
                self.assertEqual(server.fraud_agent.max_case_calls,6)
                self.assertEqual(server.agents.config.daily_usd,2)
                self.assertEqual(server.agents.config.total_usd,8)
                self.assertEqual(server.agents.config.daily_calls,100)
                self.assertEqual(server.fraud_agent.case_limit,50000)
                self.assertTrue(server.demo_guard.live_enabled);client.assert_not_called()
            finally:server.server_close();server.lab.db.close()

    def test_world_tick_checkpoints_its_allowance_with_the_ledger_once(self):
        from server import make_server
        remote=FakeCloud();cloud=CloudData('test-project','world-checkpoint','simulation',session=remote)
        server=make_server(0,self.root/'tick.db',cloud=cloud)
        try:
            state=server.world_demo.start(0,background=False);before=int(cloud.generation)
            server.world_demo.tick(state['run_id'])
            self.assertEqual(int(cloud.generation)-before,1)
            self.assertEqual(server.demo_guard.status()['used']['world_steps'],1)
            restored=CloudData('test-project','world-checkpoint','simulation',session=remote)
            restored.restore(self.root/'tick-restored.db');lab=Lab(self.root/'tick-restored.db')
            try:
                self.assertEqual(lab.db.execute('SELECT world_steps FROM demo_daily_usage').fetchone()[0],1)
                self.assertEqual(lab.db.execute('SELECT tick FROM simulation_state').fetchone()[0],1)
                self.assertTrue(lab.integrity())
            finally:lab.db.close()
        finally:server.server_close();server.lab.db.close()


if __name__=='__main__':unittest.main(verbosity=2)
