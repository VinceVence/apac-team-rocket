"""Cloud-boundary tests: exact schemas, independent dataset, durable caps, no retries."""
import copy
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from agents import Config
from cloud_data import CloudData
DAILY_EXPORTS=25  # Explicit saturation test, not a production daily quota.
from environment_cloud import DATASET, LABELS, RETENTION_MS
from environment_data import COLUMNS, schema
from lab import LabError, now
from server import make_server
from test_cloud_data import FakeCloud, Response


class EnvironmentCloud(FakeCloud):
    def __init__(self):
        super().__init__();self.resources={};self.fail_table=None
    def request(self,method,url,**kwargs):
        path=urlsplit(url).path
        if '/datasets' in path:
            if method=='GET':return Response(data=copy.deepcopy(self.resources[path])) if path in self.resources else Response(404)
            body=copy.deepcopy(kwargs['json'])
            if method=='POST':
                ref=body.get('tableReference',body.get('datasetReference'))
                path+='/'+ref.get('tableId',ref['datasetId'])
                self.resources[path]=body
            elif method=='PATCH':self.resources[path].update(body)
            return Response(data=copy.deepcopy(self.resources[path]))
        if '/jobs' in path and method=='POST':
            name=kwargs['json']['configuration']['load']['destinationTable']['tableId']
            if name==self.fail_table:
                self.jobs.append(kwargs['json']);raise TimeoutError('Unknown load outcome')
        return super().request(method,url,**kwargs)


class EnvironmentCloudChecks(unittest.TestCase):
    def setUp(self):
        limit=patch('environment_cloud.DAILY_EXPORTS',DAILY_EXPORTS);limit.start();self.addCleanup(limit.stop)
        self.tmp=tempfile.TemporaryDirectory();self.remote=EnvironmentCloud()
        self.cloud=CloudData('test-project','test-bucket','simulation',session=self.remote)
        self.env=patch.dict('os.environ',{'MINTTOWN_ENV_DATASET':DATASET,'MINTTOWN_LIVE':'0','MINTTOWN_FRAUD_LIVE':'0','PALLET_WAREHOUSE_ENABLED':'0'})
        self.env.start()
        self.server=make_server(0,Path(self.tmp.name)/'world.db',Config(live=False),cloud=self.cloud)
        self.lab=self.server.lab;self.publisher=self.server.environment_publisher
    def tearDown(self):
        self.server.server_close();self.lab.db.close();self.env.stop();self.tmp.cleanup()

    def test_six_typed_loads_are_bounded_idempotent_and_private(self):
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No paid model')):
            for tick in range(4):self.server.world.advance(tick,4)
            receipt=self.publisher.publish()
        self.assertEqual(receipt['status'],'completed');self.assertEqual(len(self.remote.jobs),6)
        self.assertEqual(self.cloud.daily_exports(self.lab),1)
        self.assertLessEqual(receipt['row_count'],20000);self.assertLessEqual(receipt['size_bytes'],16*1024*1024)
        for job in self.remote.jobs:
            load=job['configuration']['load'];table=load['destinationTable']['tableId']
            self.assertEqual(load['destinationTable']['datasetId'],DATASET)
            self.assertEqual(job['jobReference']['location'],'US')
            self.assertEqual(load['schema']['fields'],schema(table))
            self.assertEqual(load['createDisposition'],'CREATE_NEVER');self.assertEqual(load['writeDisposition'],'WRITE_TRUNCATE')
            self.assertNotIn('query',job['configuration'])
        prefix='exports/environment/'+receipt['id']+'/'
        records={table:[json.loads(line) for line in gzip.decompress(self.remote.objects[prefix+table+'.jsonl.gz'][1]).splitlines()] for table in COLUMNS}
        self.server.environment_data.validate(records)
        self.assertEqual(records['scam_memory'],[])
        self.assertTrue(self.publisher.publish()['replayed']);self.assertEqual(len(self.remote.jobs),6)
        dataset=self.remote.resources['/bigquery/v2/projects/test-project/datasets/'+DATASET]
        self.assertEqual(dataset['defaultTableExpirationMs'],str(RETENTION_MS))
        self.assertTrue(all('minttown_simulated_env' not in path for path in self.remote.resources))

    def test_shared_allowance_survives_reset_and_cannot_be_bypassed(self):
        self.publisher.publish()
        with self.lab.db:self.lab.db.execute('INSERT OR REPLACE INTO demo_usage_archive VALUES(?,?,0,0)',(now()[:10],DAILY_EXPORTS-1))
        self.server.world.advance(0,4)
        with self.assertRaisesRegex(LabError,'limit reached'):self.publisher.publish()
        count=self.cloud.daily_exports(self.lab);before=self.server.agents.budget()['committed_microusd_total']
        state=self.server.world_demo.start(0,background=False,fresh=True);self.server.world_demo.stop(state['run_id'])
        self.assertEqual(self.cloud.daily_exports(self.lab),count)
        self.assertEqual(self.server.agents.budget()['committed_microusd_total'],before)
        with self.assertRaisesRegex(LabError,'limit reached'):self.publisher.publish()
        self.assertEqual(len(self.remote.jobs),6)

    def test_partial_submission_blocks_retry_and_fresh_reset(self):
        self.remote.fail_table='devices'
        with self.assertRaisesRegex(LabError,'No automatic retry'):self.publisher.publish()
        self.assertEqual(self.publisher.status()['latest']['status'],'uncertain')
        self.assertEqual(len(self.remote.jobs),3);self.assertEqual(self.cloud.daily_exports(self.lab),1)
        with self.assertRaisesRegex(LabError,'reconciliation'):self.publisher.publish()
        with self.assertRaisesRegex(LabError,'reconciliation'):self.server.world_demo.start(0,background=False,fresh=True)
        self.assertEqual(len(self.remote.jobs),3)

    def test_unowned_or_schema_drifted_destination_is_not_overwritten(self):
        path='/bigquery/v2/projects/test-project/datasets/'+DATASET
        self.remote.resources[path]={'labels':{},'location':'US','defaultTableExpirationMs':str(RETENTION_MS)}
        with self.assertRaisesRegex(LabError,'ownership'):self.publisher.provision()
        self.assertEqual(len(self.remote.resources),1);self.assertEqual(self.remote.jobs,[])
        self.remote.resources[path]['labels']=LABELS.copy();self.publisher.provision()
        self.remote.resources[path+'/tables/wallets']['schema']['fields'][3]['type']='FLOAT'
        with self.assertRaisesRegex(LabError,'schema drift'):self.publisher.provision()
        self.assertEqual(self.remote.jobs,[])

    def test_row_limit_is_checked_before_reserving_or_uploading(self):
        previous=dict(self.remote.objects)
        with patch('environment_cloud.MAX_EXPORT_ROWS',1),self.assertRaisesRegex(LabError,'row or byte cap'):self.publisher.publish()
        self.assertEqual(self.remote.objects,previous);self.assertEqual(self.remote.jobs,[])
        self.assertEqual(self.cloud.daily_exports(self.lab),0)


if __name__=='__main__':unittest.main()
