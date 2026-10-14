"""Harness behavior and final state, not a claimed Gemini accuracy benchmark."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from agents import Config
from fraud_adk import FakeInvestigator
from fraud_harness_fixtures import choose
from fraud_desk import LESSON,QUESTION
from lab import LabError,encoded
from server import make_server

class HarnessChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'case.db'
        self.server=make_server(0,self.path,Config(live=False));self.agent=self.server.fraud_agent;self.desk=self.server.fraud_desk
        self.no_paid=patch('google.genai.Client.__init__',side_effect=AssertionError('No paid clients'));self.no_paid.start()
    def tearDown(self):self.server.server_close();self.server.lab.db.close();self.no_paid.stop();self.tmp.cleanup()
    def case(self,name='phishing'):
        report=self.desk.demo(name,'harness-'+str(self.server.lab.db.total_changes));return report,self.agent.start(report['id'])
    def finish(self,run):
        for _ in range(7):
            if run['status']!='running':break
            run=self.agent.step(run['id'],run['step'])
        return run
    def test_selective_roles_use_shared_budget_and_judges(self):
        for role in ('transaction_specialist','device_specialist','scam_specialist','resolution_critic'):
            def policy(packet):
                name,args=choose(packet)
                if name=='delegate_question':args['role']=role
                return name,args
            self.agent.model_factory=lambda:FakeInvestigator(chooser=policy)
            report,run=self.case();run=self.finish(run)
            self.assertEqual(run['status'],'awaiting_review',run['context'].get('stop_reason'))
            self.assertEqual(run['budget']['case_calls'],5)
            data=self.desk.detail(report['id'])['harness'];self.assertEqual(data['tasks'][0]['role'],role)
            self.assertTrue(data['checks'][0]['passed']);self.assertEqual(len(data['checks'][0]['judges']),3)
            self.assertEqual([r['role'] for r in self.desk.detail(report['id'])['decision_trail']],['resolution']*3+[role,'resolution'])
            self.assertFalse(self.desk.detail(report['id'])['reviews']);self.assertEqual(self.desk.memories(),[])
    def test_judges_reject_unsupported_resolution_and_prevent_approval(self):
        def bad(packet):
            name,args=choose(packet)
            if name=='submit_case_resolution':args['customer_message']='We have refunded your money. Recovery is guaranteed.'
            return name,args
        self.agent.model_factory=lambda:FakeInvestigator(chooser=bad)
        report,run=self.case();run=self.finish(run)
        self.assertEqual(run['status'],'budget_exhausted');self.assertIsNone(run['recommendation'])
        checks=self.desk.detail(report['id'])['harness']['checks'];self.assertTrue(any(not c['passed'] for c in checks))
        self.assertIn('Unsupported completed bank action',json.dumps(checks))
        with self.assertRaises(LabError):self.desk.review(report['id'],run['id'],'confirmed_scam','request_recall','I checked the case.',True,LESSON,QUESTION)
        self.assertEqual(self.desk.memories(),[])
    def test_foreign_receipt_cannot_be_used_by_specialist(self):
        def bad(packet):
            name,args=choose(packet)
            if name=='return_finding':args['receipt_ids']=['PRED-foreign']
            return name,args
        self.agent.model_factory=lambda:FakeInvestigator(chooser=bad)
        report,run=self.case();run=self.finish(run)
        self.assertEqual(run['status'],'failed');self.assertIn('outside its delegated scope',run['context']['stop_reason'])
        self.assertEqual(run['budget']['case_calls'],4);self.assertFalse(self.desk.detail(report['id'])['harness']['checks'][0]['passed'])
    def test_completed_parent_resumes_child_without_repeating_paid_step(self):
        report,run=self.case()
        for _ in range(3):run=self.agent.step(run['id'],run['step'])
        self.assertEqual(self.agent.harness.task(run['context'])['status'],'queued')
        context=run['context'];context['execution']={'status':'running','mode':'automatic'}
        with self.server.lab.db:self.server.lab.db.execute('UPDATE fraud_investigations SET context=? WHERE id=?',(encoded(context),run['id']))
        self.server.server_close();self.server.lab.db.close()
        self.server=make_server(0,self.path,Config(live=False));self.agent=self.server.fraud_agent;self.desk=self.server.fraud_desk
        paused=self.desk.run(run['id']);self.assertEqual(paused['status'],'interrupted');self.assertTrue(self.desk.detail(report['id'])['harness']['can_resume'])
        resumed=self.agent.start(report['id']);done=self.finish(resumed)
        self.assertEqual(done['status'],'awaiting_review');self.assertEqual(done['budget']['case_calls'],5)
        self.assertEqual(len(self.desk.detail(report['id'])['harness']['tasks']),1)
    def test_stale_model_and_post_submission_draft_changes_block_review(self):
        report,run=self.case();run=self.finish(run)
        from fraud_models import manifests
        drift=manifests();drift['device_integrity_v1']['version']='2.0'
        with patch('fraud_harness.manifests',return_value=drift),self.assertRaisesRegex(LabError,'implementation changed'):
            self.desk.review(report['id'],run['id'],'confirmed_scam','request_recall','Verified the case records.',True,LESSON,QUESTION)
        changed=copy.deepcopy(run['recommendation']);changed['customer_message']='You are liable for this transfer.'
        with self.server.lab.db:self.server.lab.db.execute('UPDATE fraud_investigations SET recommendation=? WHERE id=?',(encoded(changed),run['id']))
        with self.assertRaisesRegex(LabError,'liability'):
            self.desk.review(report['id'],run['id'],'confirmed_scam','request_recall','Verified the case records.',True,LESSON,QUESTION)
    def test_legitimate_case_can_skip_specialist(self):
        report,run=self.case('benign');run=self.finish(run)
        self.assertEqual(run['status'],'awaiting_review',run['context'].get('stop_reason'))
        self.assertEqual(run['budget']['case_calls'],3);self.assertEqual(self.desk.detail(report['id'])['harness']['tasks'],[])

    def test_customer_reply_keeps_model_receipts_and_budget(self):
        def policy(packet):
            name,args=choose(packet)
            if name=='delegate_question':
                if not packet['customer_replies']:return 'ask_customer',{'question':'Did you independently verify the caller through the official channel?','purpose':'Resolve the caller verification gap with the customer.'}
                # A reply replaces delegation so final review still fits the same case allowance.
                packet={**packet,'delegation_used':True};return choose(packet)
            return name,args
        self.agent.model_factory=lambda:FakeInvestigator(chooser=policy)
        report,run=self.case();run=self.finish(run);self.assertEqual(run['status'],'awaiting_customer')
        before=self.agent.harness.receipts(run['id'])
        self.desk.answer(report['id'],'I did not verify the caller with the bank.',report['revision'])
        resumed=self.agent.start(report['id']);done=self.finish(resumed)
        self.assertEqual(done['status'],'awaiting_review',done['context'].get('stop_reason'))
        self.assertEqual(done['budget']['case_calls'],4)
        self.assertEqual([r['receipt_id'] for r in self.agent.harness.receipts(done['id'])],[r['receipt_id'] for r in before])
    def test_revocation_removes_knowledge_and_blocks_its_safeguards(self):
        report,run=self.case();run=self.finish(run)
        self.desk.review(report['id'],run['id'],'confirmed_scam','request_recall','Verified the synthetic evidence.',True,LESSON,QUESTION)
        memory=self.desk.memories()[0]
        self.assertTrue(memory['lifecycle']['counterexamples']);self.assertTrue(memory['lifecycle']['source_receipts'])
        prevention=self.server.prevention;job=prevention.start(report['id'],'fake')
        with self.server.lab.db:self.server.lab.db.execute("UPDATE prevention_jobs SET status='running' WHERE id=?",(job['id'],))
        job=prevention.step(job['id']);self.assertEqual(job['status'],'awaiting_activation',job.get('error'))
        prevention.activate(job['rule']['id'],True)
        self.assertEqual(len(prevention.active()),1)
        self.desk.revoke_memory(memory['id'],'Analyst found this lesson should be re-verified.')
        self.assertEqual(self.desk.memories(),[]);self.assertEqual(prevention.active(),[])
        with self.assertRaises(LabError):prevention.activate(job['rule']['id'],True)
        self.assertTrue(self.desk.memories(include_inactive=True)[0]['lifecycle']['revoked_at'])
    def test_case_tool_cannot_request_otp_or_approve_itself(self):
        self.agent.model_factory=lambda:FakeInvestigator(chooser=lambda packet:('ask_customer',{'question':'Please share your OTP so I can check the case.','purpose':'Request authentication data for the case.'}))
        report,run=self.case();run=self.finish(run)
        self.assertEqual(run['status'],'failed');self.assertIn('authentication secrets',run['context']['stop_reason'])
        self.assertEqual(self.desk.report(report['id'])['status'],'needs_review')
        self.assertEqual(self.desk.detail(report['id'])['reviews'],[])

    def test_uncertain_child_is_not_retried_and_can_be_handed_to_a_human(self):
        report,run=self.case()
        for _ in range(3):run=self.agent.step(run['id'],run['step'])
        before=copy.deepcopy(run);task=self.agent.harness.task(run['context'])
        child=self.agent.step(run['id'],run['step'])
        with self.server.lab.db:
            self.server.lab.db.execute("UPDATE fraud_agent_turns SET status='reserved',cost_microusd=NULL WHERE job_id=?",(task['id'],))
            self.server.lab.db.execute("UPDATE fraud_delegations SET status='running',finding=NULL WHERE id=?",(task['id'],))
            self.server.lab.db.execute("UPDATE fraud_investigations SET status='stepping',step=?,context=? WHERE id=?",(before['step'],encoded(before['context']),run['id']))
        self.server.server_close();self.server.lab.db.close()
        self.server=make_server(0,self.path,Config(live=False));self.agent=self.server.fraud_agent;self.desk=self.server.fraud_desk
        saved=self.agent.start(report['id']);self.assertEqual(saved['status'],'interrupted')
        self.assertFalse(self.desk.detail(report['id'])['harness']['can_resume'])
        self.assertEqual(saved['budget']['case_calls'],4)
        manual=self.agent.handoff(saved['id'])
        self.assertEqual(manual['investigation']['status'],'awaiting_review')
        self.assertEqual(manual['harness']['checks'][0]['mode'],'manual_handoff_checks')
        self.assertTrue(manual['harness']['checks'][0]['passed'])
        self.assertEqual(manual['harness']['active_role'],'risk_analyst')
        self.desk.review(report['id'],saved['id'],'needs_information','support_followup','Human analyst is verifying the missing information.',False,'','')
        self.assertEqual(self.agent.budget(report['id'],'fake')['case_calls'],4)
    def test_model_prompts_hide_simulator_event_labels(self):
        report,run=self.case();raw_id=report['event_ids'][0]
        packets=[]
        def policy(packet):packets.append(packet);return choose(packet)
        self.agent.model_factory=lambda:FakeInvestigator(chooser=policy)
        done=self.finish(run);self.assertEqual(done['status'],'awaiting_review')
        self.assertTrue(packets)
        for packet in packets:
            self.assertNotIn(raw_id,json.dumps(packet));self.assertNotIn('guided_demo',packet)
            self.assertTrue(all(e.startswith('EVT-') for e in packet['event_ids']))
        self.assertEqual(done['recommendation']['evidence_ids'],report['event_ids'])
    def test_expired_knowledge_cannot_screen_or_be_retrieved(self):
        report,run=self.case();run=self.finish(run)
        self.desk.review(report['id'],run['id'],'confirmed_scam','request_recall','Verified the synthetic evidence.',True,LESSON,QUESTION)
        memory=self.desk.memories()[0]
        with self.server.lab.db:self.server.lab.db.execute("UPDATE fraud_lesson_controls SET expires_at='2000-01-01T00:00:00+00:00' WHERE memory_id=?",(memory['id'],))
        self.assertEqual(self.desk.memories(),[])
        self.assertEqual(self.desk.screen('C002',report['transactions'][0]['to_account']),[])

if __name__=='__main__':unittest.main()
