"""Offline regressions for the imported AE tools and their write boundaries."""
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]


def module(path):
    spec=importlib.util.spec_from_file_location(Path(path).stem,ROOT/path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


generator=module('data/generator/generate_minttown_data.py')
loader=module('data/ingestion/load_to_bq.py')


class DataToolsTests(unittest.TestCase):
    def test_repeatable_bounded_numbered_residents_and_owned_devices(self):
        a=generator.generate(20,100,42)
        self.assertEqual(a,generator.generate(20,100,42))
        self.assertEqual(a['customers'][0]['full_name'],'Resident 1')
        for tx in a['wallet_transactions']:
            self.assertEqual(tx['device_id'][4:],tx['sender_wallet_id'][4:])
        for size in (1,101):
            with self.assertRaises(ValueError):generator.generate(size,100)
        with self.assertRaises(ValueError):generator.generate(100,10001)

    def test_csv_roundtrip_money_and_zero_transactions(self):
        for count in (0,100):
            with tempfile.TemporaryDirectory() as folder:
                generator.write_csv(generator.generate(20,count),folder)
                rows=loader.read_tables(folder)
                self.assertEqual(len(rows['wallet_transactions']),count)
                self.assertIsInstance(rows['wallets'][0]['current_balance'],str)
                with self.assertRaises(ValueError):generator.write_csv(generator.generate(),folder)

    def test_invalid_references_and_nan_are_rejected(self):
        for field,value in [('device_id','DEV_9999'),('amount','NaN'),('timestamp','2020-01-01T00:00:00Z')]:
            with tempfile.TemporaryDirectory() as folder:
                rows=generator.generate(5,5);rows['wallet_transactions'][0][field]=value
                generator.write_csv(rows,folder)
                with self.assertRaises(ValueError):loader.read_tables(folder)

    def test_source_dataset_and_running_world_are_refused_before_sdk(self):
        client=Mock()
        for dataset,stopped in [('minttown_simulated_env',True),('minttown_world',False)]:
            with self.assertRaises(ValueError):loader.apply({},'test-project',dataset,'unused-receipt',stopped,client)
        oversized={name:[] for name in generator.TABLES};oversized['customers']=[{}]*101
        with self.assertRaises(ValueError):loader.apply(oversized,'test-project','minttown_world','unused-receipt',True,client)
        self.assertEqual(client.mock_calls,[])

    def client(self,occupied=False):
        client=Mock();client.get_dataset.return_value=SimpleNamespace(labels={'purpose':'simulator_mirror'},location='US')
        def table(name,**kwargs):
            name=name.rsplit('.',1)[-1]
            return SimpleNamespace(labels={'purpose':'simulator_mirror'},num_rows=int(occupied),streaming_buffer=None,
                schema=[SimpleNamespace(name=f['name'],field_type=f['type'],mode=f['mode']) for f in loader.schema(name)])
        client.get_table.side_effect=table
        return client

    def test_nonempty_destination_is_never_loaded(self):
        with tempfile.TemporaryDirectory() as folder:
            client=self.client(occupied=True)
            with self.assertRaises(ValueError):loader.apply(generator.generate(5,10),'test-project','minttown_world',Path(folder)/'receipt',True,client)
            client.load_table_from_json.assert_not_called()

    def test_explicit_load_is_empty_only_and_receipt_blocks_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            client=self.client();receipt=Path(folder)/'receipt';rows=generator.generate(5,10)
            self.assertEqual(loader.apply(rows,'test-project','minttown_world',receipt,True,client)['status'],'complete')
            self.assertEqual(client.load_table_from_json.call_count,4)
            for call in client.load_table_from_json.call_args_list:
                self.assertEqual(call.kwargs['job_config'].write_disposition,'WRITE_EMPTY')
                self.assertEqual(call.kwargs['job_config'].create_disposition,'CREATE_NEVER')
                self.assertEqual(call.kwargs['num_retries'],0)
            with self.assertRaises(ValueError):loader.apply(rows,'test-project','minttown_world',receipt,True,client)
            self.assertEqual(client.load_table_from_json.call_count,4)


if __name__=='__main__':unittest.main()
