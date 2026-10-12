"""The reviewed-memory loop, review boundaries and zero-money resolution semantics."""
import tempfile
import unittest
from pathlib import Path

from fraud_desk import FraudDesk, LESSON, QUESTION
from lab import Lab, LabError
from world import World


class FraudDeskChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'fraud.db'
        self.lab = Lab(self.path); self.world = World(self.lab)
        self.desk = FraudDesk(self.lab, self.world); self.world.fraud_desk = self.desk

    def tearDown(self):
        self.lab.db.close(); self.temp.cleanup()

    def investigate(self, report):
        run = self.desk.start(report['id'])
        for _ in range(5): run = self.desk.step(run['id'], run['step'])
        self.assertEqual(run['status'], 'awaiting_review')
        return run

    def command(self, report, run, **changes):
        return dict(report_id=report['id'], investigation_id=run['id'], disposition='confirmed_scam',
                    action='request_recall', note='The customer confirmed the impersonation story during analyst review.',
                    publish_memory=True, lesson=LESSON, next_question=QUESTION, **changes)

    def test_first_case_review_repeat_retrieval_and_restart(self):
        first = self.desk.demo('first', 'first-case')
        balances = self.lab.rows('SELECT id,balance_minor FROM accounts ORDER BY id')
        run = self.investigate(first)
        self.assertEqual(run['context']['memories'], [])
        self.assertEqual(run['trace'][3]['tool'], 'request_missing_context')
        self.assertEqual(self.desk.memories(), [])
        command = self.command(first, run)
        command['next_question'] = 'Did the caller ask you to keep the transfer secret from bank staff?'
        reviewed = self.desk.review(**command)
        self.assertEqual(reviewed['status'], 'resolved')
        self.assertEqual(reviewed['reviews'][0]['resolution']['money_recovered_minor'], 0)
        self.assertEqual(balances, self.lab.rows('SELECT id,balance_minor FROM accounts ORDER BY id'))
        self.assertEqual(self.desk.review(**command)['reviews'], reviewed['reviews'])
        self.assertEqual(len(self.desk.memories()), 1)
        with self.assertRaises(LabError): self.desk.review(**{**command, 'note': 'A conflicting second review must not silently overwrite the first.'})
        # Reopen the DB to demonstrate persistent knowledge, not a transient UI message.
        self.lab.db.close(); self.lab = Lab(self.path); self.world = World(self.lab)
        self.desk = FraudDesk(self.lab, self.world); self.world.fraud_desk = self.desk
        second = self.desk.demo('repeat', 'second-case')
        self.assertEqual(second['transactions'][0]['metadata']['review_flags'][0]['source_report_id'], first['id'])
        second_run = self.investigate(second)
        self.assertEqual(second_run['trace'][3]['tool'], 'compare_reviewed_pattern')
        memory = second_run['context']['memories'][0]
        self.assertEqual(memory['source_report_id'], first['id'])
        self.assertEqual(second_run['recommendation']['questions'], [command['next_question']])
        self.assertEqual(second_run['recommendation']['memory_ids'], [memory['id']])
        self.assertEqual(second_run['gemini_calls'], 0); self.assertTrue(self.lab.integrity())

    def test_review_cannot_be_skipped_or_publish_unconfirmed_claims(self):
        report = self.desk.demo('first', 'review-gate'); run = self.desk.start(report['id'])
        with self.assertRaisesRegex(LabError, 'Complete'): self.desk.review(**self.command(report, run))
        run = self.investigate(report)
        request = {**self.command(report, run), 'disposition': 'needs_information', 'action': 'support_followup'}
        with self.assertRaisesRegex(LabError, 'Only analyst-confirmed'): self.desk.review(**request)
        reviewed = self.desk.review(**{**request, 'publish_memory': False})
        self.assertEqual(reviewed['status'], 'awaiting_customer'); self.assertEqual(self.desk.memories(), [])
        updated = self.desk.answer(report['id'], 'The caller asked me to keep it secret and claimed to be bank support.', report['revision'])
        with self.assertRaises(LabError): self.desk.answer(report['id'], 'A duplicate reply must not be applied.', report['revision'])
        next_run = self.investigate(updated)
        self.assertNotEqual(next_run['id'], run['id'])
        self.assertEqual(len(next_run['context']['answers']), 1)
        self.assertEqual(next_run['context']['memories'], [])

    def test_idempotence_scope_and_benign_non_match(self):
        first = self.desk.demo('first', 'replay')
        self.assertEqual(self.desk.demo('first', 'replay')['event_ids'], first['event_ids'])
        with self.assertRaises(LabError): self.desk.demo('repeat', 'replay')
        with self.assertRaises(LabError): self.desk.create('C002', first['story'], '', first['event_ids'], 'wrong-customer')
        run = self.desk.start(first['id']); step = self.desk.step(run['id'], 0)
        self.assertEqual(self.desk.step(run['id'], 0), step)
        with self.assertRaises(LabError): self.desk.step(run['id'], 8)
        run = self.investigate(first); self.desk.review(**self.command(first, run))
        benign = self.desk.demo('benign', 'benign-case'); clean = self.investigate(benign)
        self.assertEqual(clean['context']['memories'], [])
        self.assertFalse(benign['transactions'][0]['metadata']['review_flags'])
        self.assertEqual(clean['recommendation']['disposition'], 'needs_information')
        self.assertEqual(self.desk.screen('C001', 'm1'), [])
        with self.lab.db: self.world.payment('watch-test', 'C002', 'm1', 100, 'device-C002')
        self.assertTrue(self.lab.integrity())

    def test_stale_or_mismatched_evidence_cannot_be_approved(self):
        first = self.desk.demo('first', 'stale'); run = self.investigate(first)
        second = self.desk.demo('repeat', 'other')
        with self.assertRaisesRegex(LabError, 'different report'):
            self.desk.review(**{**self.command(first, run), 'report_id': second['id']})
        with self.lab.db: self.lab.db.execute("UPDATE financial_events SET metadata='{}' WHERE id=?", (first['event_ids'][0],))
        with self.assertRaisesRegex(LabError, 'evidence changed'): self.desk.review(**self.command(first, run))
        self.assertFalse(self.desk.memories())
        refreshed = self.investigate(first)
        self.assertNotEqual(refreshed['id'], run['id'])
        self.assertEqual(self.desk.run(run['id'])['status'], 'superseded')
        self.assertFalse(refreshed['context']['signals']['authorization_recorded'])


if __name__ == '__main__': unittest.main(verbosity=2)
