"""Release/serving acceptance tests; provider calls are fake and use no API credits."""
import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from agents import Agents, Config
from lab import Lab, LabError, encoded
from science import Science, predict
from science_ops import ScienceTeam
from server import make_server


class ScienceOperationsChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'science.db'
        self.lab=Lab(self.path);self.science=Science(self.lab);self.agents=Agents(self.lab,Config())
        self.team=ScienceTeam(self.lab,self.science,self.agents)

    def tearDown(self):self.lab.db.close();self.temp.cleanup()

    def test_pipeline_deploys_serves_and_survives_restart(self):
        result=self.team.run_pipeline();active=self.team.active('churn')
        self.assertEqual(result['pipeline']['status'],'completed');self.assertEqual(len(result['pipeline']['stages']),6)
        self.assertIsNotNone(active);self.assertEqual(result['pipeline']['report']['batch_scored']['churn'],24)
        response=self.team.serve('churn','C001');self.assertEqual(response['model_id'],active['model_id'])
        model=self.team.model(active['model_id'])
        # Use the recorded model and its recorded feature vector to verify the endpoint's score.
        expected=predict(model['artifact'],list(response['features'].values()))
        self.assertAlmostEqual(response['probability'],expected,places=6)
        count=self.lab.db.execute('SELECT count(*) FROM prediction_logs').fetchone()[0]
        self.assertTrue(self.team.serve('churn','C001')['cached'])
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM prediction_logs').fetchone()[0],count)
        self.assertTrue(self.team.run_pipeline()['cached'])
        self.lab.db.close();self.lab=Lab(self.path);self.science=Science(self.lab)
        self.team=ScienceTeam(self.lab,self.science,Agents(self.lab,Config()))
        self.assertEqual(self.team.active('churn')['id'],active['id'])
        self.assertEqual(self.team.serve('churn','C001')['prediction_id'],response['prediction_id'])

    def test_failed_candidate_cannot_replace_serving_version(self):
        self.team.run_pipeline();active=self.team.active('churn')
        self.assertIsNone(self.team.active('propensity'))
        with self.assertRaises(LabError):self.team.promote('propensity-2026-10-06',None)
        self.lab.clock_day='2026-10-07';report=self.team.run_pipeline()
        self.assertEqual(self.team.active('churn')['id'],active['id'])
        self.assertTrue(any(r['status']=='kept_current' for r in report['pipeline']['report']['releases']))

    def test_rollback_and_integrity_quarantine(self):
        self.team.run_pipeline();first=self.team.active('churn')
        self.lab.clock_day='2026-10-07';self.science.train();candidate='churn-2026-10-07'
        self.assertTrue(self.team.gate(self.team.model(candidate))['eligible'])
        with self.assertRaises(LabError):self.team.promote(candidate,'stale-release-id')
        # Isolate the atomic release/rollback path; measured champion rejection is tested above.
        with patch.object(self.team,'compare_champion',return_value={'passed':True,'reason':'Test comparison fixture'}):
            second=self.team.promote(candidate,first['id'])
        self.assertEqual(second['previous_id'],first['id'])
        altered=self.team.model(candidate)['artifact'];altered['weights'][0]+=1
        with self.lab.db:self.lab.db.execute('UPDATE model_runs SET artifact=? WHERE id=?',(encoded(altered),candidate))
        with self.assertRaisesRegex(LabError,'integrity'):self.team.serve('churn','C001')
        self.assertIsNone(self.team.active('churn'))
        restored=self.team.rollback('churn',second['id']);self.assertEqual(restored['id'],first['id'])
        self.assertFalse(self.team.gate(self.team.model(candidate))['eligible'])
        self.assertEqual(self.team.serve('churn','C001')['model_id'],first['model_id'])

    def test_quality_failure_blocks_training_and_serving(self):
        self.team.run_pipeline();count=self.lab.db.execute('SELECT count(*) FROM model_runs').fetchone()[0]
        with self.lab.db:self.lab.event('unposted','C001','payment',100,'2026-10-01','settled')
        with self.assertRaisesRegex(LabError,'quality'):self.team.run_pipeline()
        self.assertEqual(self.lab.db.execute('SELECT count(*) FROM model_runs').fetchone()[0],count)
        with self.assertRaisesRegex(LabError,'quality'):self.team.serve('churn','C001')
        self.assertEqual(self.team.dashboard()['pipeline']['status'],'failed')
        self.assertEqual(self.team.dashboard()['pipeline']['stages'][1]['status'],'skipped')

    def test_monitor_waits_for_mature_labels_and_runs_once_per_day(self):
        self.team.run_pipeline();report=self.team.monitor()[0]
        self.assertEqual(report['mature_predictions'],0);self.assertFalse(report['performance_evaluable'])
        self.assertIsNone(self.team.autorun())
        self.lab.clock_day='2026-10-13';report=self.team.monitor()[0]
        self.assertEqual(report['mature_predictions'],24);self.assertFalse(report['performance_evaluable'])
        self.assertIsNotNone(self.team.autorun());self.assertIsNone(self.team.autorun())

    def test_scientist_uses_shared_budget_and_rejects_unregistered_recipes(self):
        calls=[]
        def fake(config,packet):
            calls.append(packet['kind']);answer=self.team.baseline(packet)
            return {'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(answer)}]}}],
                    'usageMetadata':{'promptTokenCount':2000,'candidatesTokenCount':400}}
        self.agents=Agents(self.lab,Config(api_key='test-only',live=True,daily_calls=1),fake);self.team.agents=self.agents
        self.team.run_pipeline('gemini');self.assertEqual(calls,['data_science'])
        self.assertTrue(self.team.run_pipeline('gemini')['cached'])
        with self.assertRaises(LabError) as exc:self.agents.analyze('F001','gemini')
        self.assertEqual(exc.exception.status,429)
        packet,_,_=self.team.snapshot();answer=self.team.baseline(packet);answer['model_kinds']=['execute arbitrary Python']
        with self.assertRaises(LabError):self.team.validate_review(packet,answer)

    def test_local_prediction_http_endpoint_and_day_close_handoff(self):
        server=make_server(0,Path(self.temp.name)/'http.db',Config())
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with urllib.request.urlopen(base+'/api/state') as response:state=json.load(response)
            def post(path,body):
                request=urllib.request.Request(base+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-MintTown-Token':state['csrf_token']})
                with urllib.request.urlopen(request) as response:return json.load(response)
            prediction=post('/api/models/churn/predict',{'customer_id':'C001'})
            self.assertEqual(prediction['mode'],'local advisory');self.assertTrue(0<=prediction['probability']<=1)
            self.assertTrue(prediction['model_id'].startswith('churn-'))
            for tick in range(15):result=post('/api/world/step',{'expected_tick':tick,'activity':1,'scenario':'none'})
            self.assertTrue(result['day_closed']);self.assertIn('science_handoff',result)
            self.assertEqual(result['science_handoff']['cutoff'],server.lab.clock_day)
            self.assertGreater(sum(result['science_handoff']['batch_scored'].values()),0)
            self.assertTrue(server.lab.integrity());self.assertEqual(server.agents.budget()['calls_today'],0)
        finally:server.shutdown();server.server_close();thread.join();server.lab.db.close()


if __name__=='__main__':unittest.main(verbosity=2)
