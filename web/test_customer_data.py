"""Customer pipeline, model lineage, agent tool choices and randomized pilots."""
import json
import tempfile
import unittest
from pathlib import Path

from adk_mesh import dispatch
from agents import Config
from customer_data import FEATURES, MODEL_SPECS, ordinal
from lab import LabError, encoded
from mesh import CUSTOMER_ROLE_IDS
from server import make_server


class CustomerIntelligenceChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.server=make_server(0,Path(self.temp.name)/'customer.db',Config())
        self.lab=self.server.lab;self.data=self.server.customer_data;self.mesh=self.server.mesh

    def tearDown(self):
        self.server.server_close();self.lab.db.close();self.temp.cleanup()

    def finish(self,run,adk=False):
        for _ in range(13):
            if run['status']!='running':return run
            run=dispatch(self.mesh,run['id'],run['step']) if adk else self.mesh.step(run['id'],run['step'])
        self.fail('Unbounded agent loop')

    def test_pk_sort_key_dedup_quarantine_and_gold_grain(self):
        with self.lab.db:
            self.assertTrue(self.data.record('C001','same-time-a',self.lab.clock_day,'app_open'))
            self.assertTrue(self.data.record('C001','same-time-b',self.lab.clock_day,'product_view',product='qr'))
            self.assertFalse(self.data.record('C001','same-time-a',self.lab.clock_day,'app_open'))
            with self.assertRaises(LabError):self.data.record('C001','same-time-a',self.lab.clock_day,'campaign_click')
            self.data.record('UNKNOWN','bad-profile',self.lab.clock_day,'app_open')
        report=self.data.build_layers()
        self.assertEqual(report['rejected_rows'],1);self.assertEqual(report['gold_customers'],240)
        self.assertTrue(self.data.build_layers()['cached'])
        self.assertEqual(self.lab.db.execute("SELECT count(*) FROM silver_interactions WHERE customer_id='UNKNOWN'").fetchone()[0],0)
        keys=self.lab.rows("SELECT event_key FROM bronze_interactions WHERE event_key LIKE '%same-time-%'")
        self.assertEqual(len(keys),2);self.assertTrue(all('#same-time-' in r['event_key'] for r in keys))
        self.assertEqual(self.lab.db.execute('SELECT count(DISTINCT customer_id) FROM gold_customer_features').fetchone()[0],240)

    def test_features_use_past_available_data_and_exclude_demographics(self):
        profile=self.data.profiles()['C001'];cutoff=ordinal(self.lab.clock_day)
        record={'day':cutoff-2,'available':cutoff-2,'kind':'app_open','value_minor':0,'product':None}
        base=self.data.features([record],cutoff,profile)
        self.assertEqual(base,self.data.features([record,{**record,'day':cutoff+1,'available':cutoff+1},{**record,'available':cutoff+1}],cutoff,profile))
        changed={**profile,'age_band':'60+','region':'Changed','occupation':'Changed','household_size':9}
        self.assertEqual(base,self.data.features([record],cutoff,changed))
        self.assertFalse({'age_band','region','occupation','household_size'}&set(FEATURES))
        with self.assertRaises(LabError):self.data.fit_models(feature_names=['age_band','region','occupation','household_size'])

    def test_eight_models_real_artifacts_lineage_and_withheld_columns(self):
        batch=self.data.fit_models();self.assertEqual(batch['model_tasks'],8);self.assertEqual(batch['trained_models'],8)
        self.assertGreaterEqual(batch['eligible_models'],5)
        for row in self.lab.rows('SELECT * FROM customer_dna_models'):
            report=json.loads(row['report']);self.assertFalse(set(report['train_customer_ids'])&set(report['holdout_customer_ids']))
            self.assertLessEqual(report['training_label_end'],report['holdout_label_start'])
            self.assertTrue(json.loads(row['artifact']))
        release=self.data.publish_dna(batch);self.assertTrue(release['approved'])
        self.assertEqual(len(self.data.dna(1000)),240)
        for target in release['held_models']:
            column=MODEL_SPECS[target]['column']
            self.assertEqual(self.lab.db.execute('SELECT count(*) FROM gold_customer_dna WHERE '+column+' IS NOT NULL').fetchone()[0],0)
        row=self.lab.db.execute("SELECT id,artifact FROM customer_dna_models WHERE target='churn'").fetchone()
        artifact=json.loads(row['artifact']);artifact['weights'][0]+=1
        with self.lab.db:self.lab.db.execute('UPDATE customer_dna_models SET artifact=? WHERE id=?',(encoded(artifact),row['id']))
        with self.assertRaisesRegex(LabError,'integrity'):self.data.publish_dna(batch)

    def test_pilot_has_controls_consent_delayed_labels_and_feedback(self):
        run=self.finish(self.mesh.start('customer-growth','baseline','pilot-loop'),adk=True)
        self.assertEqual(run['status'],'completed');self.assertEqual({t['from_role'] for t in run['turns']},set(CUSTOMER_ROLE_IDS))
        tools=[t['decision']['tool'] for t in run['turns']]
        self.assertLess(tools.index('preview_personalized_campaign'),tools.index('launch_personalized_campaign'))
        c=self.data.dashboard()['campaigns'][0];self.assertEqual(c['status'],'running')
        self.assertEqual(sum(a['arm']=='message' for a in c['assignments']),sum(a['arm']=='control' for a in c['assignments']))
        self.assertTrue(all(a['outcome'] is None for a in c['assignments']))
        self.assertTrue(all(self.data.profiles()[a['customer_id']]['marketing_consent'] for a in c['assignments']))
        self.assertTrue(all(not a['message'] for a in c['assignments'] if a['arm']=='control'))
        monitor=self.finish(self.mesh.start('customer-growth','baseline','monitor-only'))
        self.assertIn('monitor_campaigns',[t['decision']['tool'] for t in monitor['turns']])
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM marketing_campaigns').fetchone()[0],1)
        for _ in range(168):self.server.world.advance(self.server.world.state()['tick'],1)
        matured=self.data.campaign(c['id']);self.assertEqual(matured['status'],'completed')
        self.assertTrue(all(a['outcome'] in (0,1) for a in matured['assignments']))
        self.assertTrue(matured['report']['approximate_95pct_interval'][0]<matured['report']['approximate_95pct_interval'][1])
        rebuilt=self.data.build_layers();self.assertNotEqual(rebuilt['source_hash'],c['config']['source_hash'])
        observed=self.lab.db.execute('SELECT count(*) FROM silver_interactions WHERE campaign_id=? AND kind=?',(c['id'],'product_activated')).fetchone()[0]
        self.assertEqual(observed,sum(a['outcome'] for a in matured['assignments']))
        self.assertEqual(self.server.agents.budget()['calls_today'],0);self.assertTrue(self.lab.integrity())

    def test_non_linear_agent_decisions_use_cohort_and_custom_feature_tools(self):
        self.server.agents.config=Config(api_key='test-only',live=True,daily_calls=10)
        run_id=[];investigated=[]
        def fake(config,packet):
            run=self.mesh.run(run_id[0]);answer=self.mesh.baseline(run)
            if packet['role']=='scientist' and not investigated:
                investigated.append(True);answer.update(tool='analyze_customer_cohorts',args={'group_by':'goal'},to_role='scientist',message='Compare declared-goal cohorts before deciding which features and targets to fit.')
            elif packet['role']=='scientist':
                answer.update(tool='run_model_experiment',args={'targets':','.join(MODEL_SPECS),'features':','.join(FEATURES)},message='Use observed behavior and declared preferences for this experiment. Demographic columns are excluded.')
            return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(answer)}]}}],
                    'usageMetadata':{'promptTokenCount':1000,'candidatesTokenCount':150}}
        self.server.agents.transport=fake
        run=self.mesh.start('customer-growth','gemini','adaptive-contract',objective='Test useful product experiences while avoiding unsupported targeting and measuring outcomes.');run_id.append(run['id'])
        run=self.finish(run,adk=True)
        self.assertEqual(run['status'],'completed')
        self.assertTrue(any(t['from_role']=='scientist' and t['to_role']=='scientist' for t in run['turns']))
        self.assertIn('run_model_experiment',[t['decision']['tool'] for t in run['turns']])
        self.assertEqual(run['playbook']['objective'],'Test useful product experiences while avoiding unsupported targeting and measuring outcomes.')
        # Fake transport tests the contract only; no actual Gemini endpoint is called.


if __name__=='__main__':unittest.main(verbosity=2)
