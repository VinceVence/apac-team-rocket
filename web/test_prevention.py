"""Reviewed learning, changed-recipient holds and shared cost boundaries."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from agents import Config
from fraud_desk import LESSON, QUESTION
from lab import LabError
from server import make_server
from prevention import features
from fraud_scenarios import SCENARIOS


class PreventionChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.server=make_server(0,Path(self.tmp.name)/'test.db',Config(live=False))
        self.lab=self.server.lab;self.desk=self.server.fraud_desk;self.agent=self.server.prevention
    def tearDown(self):self.server.server_close();self.lab.db.close();self.tmp.cleanup()
    def reviewed(self):
        world=self.server.world_demo
        world.incident(1,'phishing')
        report_id=world.status()['incidents'][0]['report_id']
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            case=self.desk.detail(report_id)
            if case['investigation'] and case['investigation']['status']=='awaiting_review':break
            time.sleep(.02)
        self.assertEqual(case['investigation']['status'],'awaiting_review')
        self.desk.review(report_id,case['investigation']['id'],'confirmed_scam','request_recall',
            'Verified the simulated caller message and disputed transfer.',True,LESSON,QUESTION)
        return report_id
    def learned(self,report_id):
        job=self.server.fraud_runner.learn(report_id,'fake');deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            job=self.agent.job(job['id'])
            if job['status'] not in ('queued','running'):return job
            time.sleep(.02)
        self.fail('Prevention learner did not stop')
    def metadata(self):
        return {'device_known':True,'authorization_verified':True,
                'payment_context':{'kind':'payment_request','before_payment':True,'message':SCENARIOS['phishing']['message']}}

    def test_review_learning_activation_and_changed_recipient_hold_without_model_calls(self):
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No paid client')) as client:
            rid=self.reviewed();job=self.learned(rid)
            self.assertEqual(job['status'],'awaiting_activation',job.get('error'))
            self.assertEqual(job['model_calls'],1);self.assertEqual(job['budget']['case_calls'],6)
            self.assertEqual(job['rule']['replay']['false_flags'],0)
            self.assertFalse(self.agent.assess('C002','external:unseen',90000,self.metadata(),self.lab.clock_day+'T18:00:00Z')[1])
            self.agent.activate(job['rule']['id'],True)
            with self.lab.db:self.lab.db.execute("INSERT INTO accounts(id,label,kind,opening_minor,balance_minor) VALUES('external:unseen','Unseen recipient','counterparty',0,0)")
            before=self.lab.rows('SELECT id,balance_minor FROM accounts ORDER BY id')
            calls=self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0]
            with self.lab.db:result=self.server.world.payment('new-recipient','C002','external:unseen',90000,'device-C002',self.metadata())
            self.assertEqual(result,'blocked');self.assertEqual(before,self.lab.rows('SELECT id,balance_minor FROM accounts ORDER BY id'))
            meta=json.loads(self.lab.db.execute("SELECT metadata FROM financial_events WHERE id='new-recipient'").fetchone()[0])
            self.assertEqual(meta['prevention_action'],'verify');self.assertIn(job['rule']['id'],meta['prevention_rule_ids'])
            with self.lab.db:legit=self.server.world.payment('legit-after-rule','C002','m1',500,'device-C002',{'device_known':True,'authorization_verified':True,'scenario':'phishing'})
            self.assertEqual(legit,'settled');self.assertTrue(self.lab.integrity())
            self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0],calls)
            self.assertEqual(self.server.fraud_runner.learn(rid,'fake')['model_calls'],1)
            self.assertEqual(len(self.desk.detail(rid)['decision_trail']),5)
            self.agent.activate(job['rule']['id'],False)
            self.assertFalse(self.agent.assess('C002','external:another',90000,self.metadata(),self.lab.clock_day+'T18:00:00Z')[1])
            client.assert_not_called()

    def test_unapproved_or_changed_source_cannot_activate(self):
        report=self.desk.demo('phishing','unapproved')
        with self.assertRaisesRegex(LabError,'analyst-confirmed'):self.agent.start(report['id'],'fake')
        rid=self.reviewed();job=self.learned(rid)
        with self.lab.db:self.lab.db.execute("UPDATE fraud_reports SET message='Changed after review' WHERE id=?",(rid,))
        with self.assertRaisesRegex(LabError,'source changed'):self.agent.activate(job['rule']['id'],True)

    def test_missing_context_and_security_advice_are_not_scam_signals(self):
        at='2026-10-13T12:00:00Z';meta=self.metadata()
        for m in ({'scenario':'phishing','story':SCENARIOS['phishing']['story']},
                  {**meta,'payment_context':{**meta['payment_context'],'before_payment':False}},
                  {**meta,'payment_context':{**meta['payment_context'],'message':'Never transfer money to a safe account. Keep it secret is a scam warning.'}}):
            result=features('new',90000,m,at,[])
            self.assertFalse(result['safe_account_request']);self.assertFalse(result['secrecy_request'])

    def test_learner_uses_the_existing_case_cap(self):
        rid=self.reviewed();self.server.fraud_agent.max_case_calls=5
        with patch('google.genai.Client.__init__',side_effect=AssertionError('No client')):
            job=self.learned(rid)
        self.assertEqual(job['status'],'budget_exhausted',job.get('error'))
        self.assertEqual(job['model_calls'],0);self.assertEqual(job['budget']['case_calls'],5)
        self.assertIsNone(job['rule']);self.assertTrue(self.desk.memories())

    def test_running_world_replays_a_changed_recipient_after_activation(self):
        rid=self.reviewed();job=self.learned(rid);self.agent.activate(job['rule']['id'],True)
        calls=self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0]
        self.server.world_demo.incident(2,'phishing',repeat=True)
        incident=self.server.world_demo.status()['incidents'][0]
        self.assertIn('variant',incident['id']);self.assertEqual(incident['status'],'blocked');self.assertIsNone(incident['report_id'])
        tx=self.lab.db.execute('SELECT to_account,metadata FROM financial_events WHERE id=?',(json.loads(incident['event_ids'])[0],)).fetchone()
        self.assertNotEqual(tx['to_account'],SCENARIOS['phishing']['payee'])
        self.assertIn(job['rule']['id'],json.loads(tx['metadata'])['prevention_rule_ids'])
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0],calls)


if __name__=='__main__':unittest.main()
