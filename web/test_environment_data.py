"""AE contract and real ledger/approval behavior, with no paid clients."""
import copy
import datetime as dt
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from agents import Config
from environment_data import EnvironmentData, COLUMNS, PAYMENT_TYPES, PRIVATE_FIELDS, schema
from fraud_desk import LESSON, QUESTION
from lab import LabError
from server import make_server


class EnvironmentDataChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.server=make_server(0,Path(self.tmp.name)/'world.db',Config(live=False))
        self.data=self.server.environment_data;self.lab=self.server.lab
    def tearDown(self):
        self.server.server_close();self.lab.db.close();self.tmp.cleanup()

    def test_generated_tables_match_dictionary_and_all_four_payment_types_settle(self):
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No paid model')):
            before=self.lab.db.execute('SELECT sum(balance_minor) FROM accounts').fetchone()[0]
            for tick in range(4):self.server.world.advance(tick,activity=4)
            tables=self.data.tables()
            self.assertEqual(set(tables),set(COLUMNS));self.assertEqual(len(tables['customers']),100)
            self.assertEqual({t['transaction_type'] for t in tables['wallet_transactions']},set(PAYMENT_TYPES))
            EnvironmentData.validate(tables)
            self.assertEqual(self.lab.db.execute('SELECT sum(balance_minor) FROM accounts').fetchone()[0],before)
            self.assertTrue(self.lab.integrity())
            self.assertEqual(len(self.data.ledger()),len(tables['wallet_transactions']))
            self.assertTrue(all(not(PRIVATE_FIELDS&row.keys()) for row in self.data.ledger()))

    def test_decimal_balances_and_rolling_daily_spend_are_exact(self):
        self.server.world.advance(0,activity=4)
        tables=self.data.tables();cutoff=dt.datetime.fromisoformat(self.lab.clock_day+'T10:59:59+00:00')
        for wallet in tables['wallets']:
            expected=sum((Decimal(t['amount']) for t in tables['wallet_transactions']
                if t['sender_wallet_id']==wallet['wallet_id'] and 0<=(cutoff-dt.datetime.fromisoformat(t['timestamp'].replace('Z','+00:00'))).total_seconds()<86400),Decimal(0))
            self.assertEqual(Decimal(wallet['daily_spent']),expected)
        self.assertEqual(schema('wallets')[3]['type'],'NUMERIC')
        self.assertEqual(schema('customers')[3]['type'],'TIMESTAMP')

    def test_burst_uses_real_timing_and_private_labels_never_enter_preview(self):
        report=self.server.fraud_desk.demo('payment_burst','ae-burst')
        rows=[r for r in self.data.tables()['wallet_transactions'] if r['is_fraud']]
        self.assertEqual(len(rows),3)
        self.assertEqual({r['scam_type'] for r in rows},{'ATO_DRAIN'})
        stamps=sorted(r['timestamp'] for r in rows)
        self.assertEqual([s[-3:-1] for s in stamps],['00','04','08'])
        self.assertTrue(any('VELOCITY_SPIKE' in json.loads(r['risk_factors']) for r in rows))
        for samples in self.data.preview()['previews'].values():
            self.assertTrue(all(not(PRIVATE_FIELDS&row.keys()) for row in samples))
        devices={d['device_id']:d for d in self.data.tables()['devices']}
        self.assertTrue(all(devices[r['device_id']]['trust_score']<.9 for r in rows))
        EnvironmentData.validate(self.data.tables())

    def test_memory_requires_actual_review_and_does_not_fabricate_refund(self):
        desk=self.server.fraud_desk;agent=self.server.fraud_agent
        case=desk.demo('phishing','ae-review')
        self.assertEqual(self.data.tables()['scam_memory'],[])
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No paid model')):
            run=agent.start(case['id'])
            for _ in range(6):
                if run['status']!='running':break
                run=agent.step(run['id'],run['step'])
            self.assertEqual(run['status'],'awaiting_review')
            self.assertEqual(self.data.tables()['scam_memory'],[])
            desk.review(case['id'],run['id'],'confirmed_scam','request_recall','Checked the controlled report and transaction evidence.',True,LESSON,QUESTION)
            rows=self.data.tables()['scam_memory'];self.assertEqual(len(rows),1)
            self.assertIsNone(rows[0]['investigation_outcome'])
            self.assertEqual(rows[0]['approved_by_analyst'],'ANALYST_DEMO')
            before=len(self.data.tables()['wallet_transactions'])
            with self.lab.db:result=self.server.world.payment('ae-held','C002',case['transactions'][0]['to_account'],5000,'device-C002')
            self.assertEqual(result,'blocked')
            self.assertEqual(len(self.data.tables()['wallet_transactions']),before)
            self.assertTrue(self.lab.integrity())

    def test_bad_types_and_broken_ownership_are_rejected(self):
        tables=copy.deepcopy(self.data.tables())
        tables['wallets'][0]['current_balance']=12.5
        with self.assertRaisesRegex(LabError,'Invalid AE field type'):EnvironmentData.validate(tables)
        tables=copy.deepcopy(self.data.tables());tx=tables['wallet_transactions'][0]
        device=next(d for d in tables['devices'] if d['device_id']==tx['device_id'])
        device['customer_id']=next(c['customer_id'] for c in tables['customers'] if c['customer_id']!=device['customer_id'])
        with self.assertRaisesRegex(LabError,'Device owner'):EnvironmentData.validate(tables)

    def test_export_is_typed_and_scene_reset_preserves_spend(self):
        initial={c['customer_id'] for c in self.data.tables()['customers']}
        before=self.server.agents.budget()
        state=self.server.world_demo.start(0,background=False,fresh=True);self.server.world_demo.stop(state['run_id'])
        after={c['customer_id'] for c in self.data.tables()['customers']}
        self.assertFalse(initial&after)
        self.assertEqual(self.server.agents.budget()['committed_microusd_total'],before['committed_microusd_total'])
        out=Path(self.tmp.name)/'export';manifest=self.data.export(out)
        self.assertEqual(manifest['counts']['customers'],100)
        for table in COLUMNS:
            self.assertEqual(json.loads((out/(table+'.schema.json')).read_text()),schema(table))
            self.assertEqual(len((out/(table+'.jsonl')).read_text().splitlines()),manifest['counts'][table])
        self.assertTrue((out/'v_agent_ledger.jsonl').exists())


if __name__=='__main__':unittest.main()
