"""ACE lifecycle and MLE refinement contracts through real local tools; no paid SDK."""
import copy,json,sqlite3,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch

from agents import Config
from fraud_adk import FakeInvestigator
from fraud_agent import FraudAgent
from fraud_desk import LESSON,QUESTION
from fraud_harness_fixtures import choose
from fraud_models import manifests,predict
from fraud_playbook import for_memory
from lab import LabError
from request_corpus import examples
from request_models import fit,finalize,validate_artifact
from risk_search import fake_choice,register
from server import make_server


class LearningLoopChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.sdk=patch('google.genai.Client.__init__',side_effect=AssertionError('Paid SDK forbidden'));self.sdk.start()
        self.s=make_server(0,Path(self.tmp.name)/'loops.db',Config(live=False),seed_history=False)
    def tearDown(self):self.s.server_close();self.s.lab.db.close();self.sdk.stop();self.tmp.cleanup()
    def finish(self,rid,chooser=choose):
        agent=self.s.fraud_agent;agent.model_factory=lambda:FakeInvestigator(chooser=chooser)
        run=agent.start(rid,experiment_arm='single')
        for _ in range(6):
            if run['status']!='running':break
            run=agent.step(run['id'],run['step'])
        self.assertEqual(run['status'],'awaiting_review',run['context'].get('stop_reason'));return run
    def wait(self):
        deadline=time.monotonic()+40
        while self.s.fraud_runner.pending and time.monotonic()<deadline:time.sleep(.03)
        self.assertFalse(self.s.fraud_runner.pending)

    def test_playbook_requires_review_then_retrieves_pinned_delta_and_revokes(self):
        desk=self.s.fraud_desk;case=desk.demo('phishing','ace-source');run=self.finish(case['id'])
        desk.review(case['id'],run['id'],'confirmed_scam','request_recall','Reviewed synthetic evidence for this source case.',True,LESSON,QUESTION)
        job=self.s.fraud_runner.learn(case['id'],'fake');self.wait();job=self.s.prevention.job(job['id'])
        self.assertEqual(job['trace'][1]['tool'],'propose_playbook');self.assertEqual(job['playbook']['status'],'candidate')
        memory=job['source']['memory_id'];self.assertIsNone(for_memory(self.s.lab,memory))
        self.s.prevention.activate(job['rule']['id'],True);entry=for_memory(self.s.lab,memory)
        self.assertEqual(self.s.prevention.activate(job['rule']['id'],True)['playbook']['id'],entry['id'])
        with self.assertRaises(sqlite3.IntegrityError),self.s.lab.db:self.s.lab.db.execute("UPDATE fraud_playbook_entries SET payload='{}'")
        later=desk.demo('phishing','ace-later')
        def with_memory(packet):
            observed={o['tool']:o['result'] for o in packet['observations']}
            if 'get_case_evidence' in observed and 'search_reviewed_cases' not in observed:
                return 'search_reviewed_cases',{'query':'safe account secrecy','purpose':'Retrieve a reviewed strategy for this independently investigated request.'}
            return choose(packet)
        follow=self.finish(later['id'],with_memory)
        self.assertEqual(follow['context']['memories'][0]['playbook']['fingerprint'],entry['fingerprint'])
        desk.review(later['id'],follow['id'],'confirmed_scam','request_recall','Independently reviewed the later synthetic case.',False,'','')
        self.assertEqual(for_memory(self.s.lab,memory)['feedback']['helpful'],1)
        desk.revoke_memory(memory,'Withdraw the synthetic lesson for an explicit source recheck.')
        self.assertIsNone(for_memory(self.s.lab,memory));self.assertFalse(self.s.prevention.active())

    def test_three_role_search_hides_test_then_registers_only_an_advisory_tool(self):
        team=self.s.risk_lab;seen=[]
        def traced(packet):seen.append(packet);return fake_choice(packet)
        for role in ('scientist','refiner','validator'):team.model_factories[role]=lambda:FakeInvestigator(chooser=traced)
        self.assertTrue(team.seed('request_benchmark')['dataset']['eligible'])
        job=team.start('mle-integrated-check','request_benchmark','fake');self.wait();result=team.study(job['id'])
        self.assertEqual(result['status'],'rejected',result['error']);self.assertEqual(result['budget']['case_calls'],3)
        self.assertEqual([p['role'] for p in seen],['scientist','refiner','validator'])
        self.assertNotIn('scams',seen[0]['dataset']['splits']['test'])
        for c in seen[1]['candidates']:self.assertNotIn('test',c);self.assertNotIn('artifact',c)
        self.assertLess([t['tool'] for t in result['trace']].index('seal_nomination'),[t['tool'] for t in result['trace']].index('sealed_test'))
        nominee=next(c for c in result['candidates'] if c['preselected'])
        card=register(team,job['id'],nominee['id'],'Reviewed limitations: advisory investigations only; payment release is not approved.')
        self.assertEqual(register(team,job['id'],nominee['id'],'Repeated human review of the same advisory artifact.')['model_id'],card['model_id'])
        self.assertFalse(self.s.prevention.active())
        case=self.s.fraud_desk.demo('phishing','use-trained-artifact');run=self.s.fraud_agent.start(case['id'])
        snap=self.s.fraud_agent.snapshot(run['context']['snapshot_id']);models=manifests(self.s.lab)
        receipt=predict([card['model_id']],[],snap,models,case['customer_id'],self.s.lab)[0]
        self.assertEqual(receipt['status'],'scored');self.assertFalse(receipt['calibrated'])
        self.assertEqual(receipt['manifest']['allowed_use'],'investigation_only')
        altered=copy.deepcopy(snap);altered['data']['transactions'][0]['metadata'].update(is_fraud=False,scam_type='not a scam',risk_score=999)
        self.assertEqual(receipt['input_hash'],predict([card['model_id']],[],altered,models,case['customer_id'],self.s.lab)[0]['input_hash'])
        altered['data']['transactions'][0]['metadata'].pop('payment_context')
        self.assertEqual(predict([card['model_id']],[],altered,models,case['customer_id'],self.s.lab)[0]['status'],'not_available')
        # Research and reviewed artifacts outlive a disposable scene.
        with self.s.lab.db:self.s.fraud_agent.stop(run['id'],'interrupted','Test ends this unstarted case without a model call.')
        self.s.world_demo.start(0,mode='demo',fresh=True,background=False)
        self.assertIn(card['model_id'],manifests(self.s.lab))

    def test_final_labels_do_not_choose_a_candidate_or_threshold(self):
        rows=examples(['C%03d'%n for n in range(1,101)])
        candidates=[fit(rows,'transaction'),fit(rows,'word')]
        first=finalize(rows,copy.deepcopy(candidates))
        for row in rows:
            if row['split']=='test':row['label']=1-row['label']
        second=finalize(rows,copy.deepcopy(candidates))
        self.assertEqual([(c['recipe'],c['preselected'],c['artifact']['threshold']) for c in first],[(c['recipe'],c['preselected'],c['artifact']['threshold']) for c in second])
        self.assertNotEqual(first[-1]['test'],second[-1]['test'])
        bad=copy.deepcopy(first[-1]['artifact']);bad['blocks']=['run_arbitrary_code']
        with self.assertRaises(ValueError):validate_artifact(bad)

    def test_known_case_rejection_and_uncertain_provider_failure_have_different_scope(self):
        known={'cost_microusd':1425,'input_tokens':2465,'output_tokens':274}
        self.assertTrue(FraudAgent.accounted_rejection(LabError('Bad transaction citation.',422),known))
        self.assertFalse(FraudAgent.accounted_rejection(TimeoutError(),known))
        self.assertFalse(FraudAgent.accounted_rejection(LabError('Missing usage.',502),{**known,'cost_microusd':None}))
        self.assertFalse(FraudAgent.accounted_rejection(LabError('Invalid call.',422),{**known,'cost_microusd':20000}))

    def test_shared_connection_reads_do_not_mix_parameters_or_drop_aggregate_rows(self):
        from concurrent.futures import ThreadPoolExecutor
        def reader(n):
            for _ in range(30):
                row=self.s.lab.db.execute('SELECT ? AS marker,count(*) AS n FROM customers',(n,)).fetchone()
                self.assertIsNotNone(row);self.assertEqual(row['marker'],n);self.assertEqual(row['n'],100)
        with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(reader,range(8)))

    def test_last_investigation_call_can_finish_instead_of_starting_an_unfinishable_branch(self):
        from fraud_adk import available_tools
        packet={'harness_version':'current','remaining_generations':2,'observations':[{'tool':'get_case_evidence','result':{}}]}
        self.assertEqual(available_tools(packet),('submit_case_resolution',))

    def test_native_citations_allow_only_retrieved_memories_and_recorded_receipts(self):
        from google.adk.tools import FunctionTool
        from fraud_adk import tools_for
        case=self.s.fraud_desk.demo('phishing','citation-boundaries');agent=self.s.fraud_agent
        run=agent.start(case['id'],experiment_arm='single')
        def schema():
            fn=next(f for f in tools_for(agent,run['id']) if f.__name__=='submit_case_resolution')
            return FunctionTool(fn)._get_declaration().parameters_json_schema['properties']
        for field in ('memory_ids','receipt_ids'):self.assertEqual(schema()[field]['maxItems'],0)
        run['context']['memories']=[{'id':'MEM-retrieved'}]
        with self.s.lab.db:self.s.lab.db.execute('UPDATE fraud_investigations SET context=? WHERE id=?',(json.dumps(run['context']),run['id']))
        memory=schema()['memory_ids']['items']
        self.assertEqual(memory.get('const') or memory.get('enum'), 'MEM-retrieved' if 'const' in memory else ['MEM-retrieved'])
        self.assertEqual(agent.packet(self.s.fraud_desk.run(run['id']))['citation_contract']['retrieved_memory_ids'],['MEM-retrieved'])

    def test_withheld_knowledge_cannot_leak_through_recipient_alerts(self):
        desk=self.s.fraud_desk;case=desk.demo('phishing','withheld-alert')
        row=self.s.lab.db.execute('SELECT request_json FROM fraud_reports WHERE id=?',(case['id'],)).fetchone()
        request=json.loads(row[0]);request['evaluation']={'knowledge_mode':'withheld'}
        transaction=desk.transactions(case)[0];transaction['metadata']['review_flags']=[{'memory_id':'MEM-alert-only'}]
        with self.s.lab.db:
            self.s.lab.db.execute('UPDATE fraud_reports SET request_json=? WHERE id=?',(json.dumps(request),case['id']))
            self.s.lab.db.execute('UPDATE financial_events SET metadata=? WHERE id=?',(json.dumps(transaction['metadata']),transaction['id']))
        run=self.s.fraud_agent.start(case['id']);packet=self.s.fraud_agent.packet(run)
        self.assertEqual(packet['ingestion_flags'],[]);self.assertEqual(packet['reviewed_memory_count'],0)
        self.assertNotIn('MEM-alert-only',json.dumps(packet))

if __name__=='__main__':unittest.main()
