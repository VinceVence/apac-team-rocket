"""Hosted work admission is bounded and survives a process restart."""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from demo_guard import DemoGuard
from fraud_desk import FraudDesk
from lab import Lab, LabError
from world import World


class GuardChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'guard.db'
        self.lab=Lab(self.path);self.desk=FraudDesk(self.lab,World(self.lab));self.saves=[];self.tick=0
        self.guard=DemoGuard(self.lab,lambda:self.saves.append(True),monotonic=lambda:self.tick)
    def tearDown(self):self.lab.db.close();self.temp.cleanup()

    def test_disabled_routes_and_live_or_manual_starts_do_no_work(self):
        for method,path,body in [('GET','/api/science',None),('POST','/api/science/run',{}),
            ('POST','/api/mesh/start',{}),('POST','/api/fraud-agent/step',{}),
            ('POST','/api/fraud-agent/start',{'mode':'gemini'}),('POST','/api/fraud-agent/start',{'automatic':False})]:
            with self.assertRaises(LabError):self.guard.allow(method,path,body)
        self.assertFalse(self.saves);self.assertEqual(self.guard.status()['used']['writes'],0)

    def test_daily_admission_survives_restart_and_checkpoint_failure(self):
        with patch('demo_guard.DAILY_WRITES',2),patch('demo_guard.DAILY_WORLD_STEPS',1):
            self.guard.allow('POST','/api/world/step',{})
            with self.assertRaisesRegex(LabError,'world-step'):self.guard.allow('POST','/api/world/step',{})
            restored=DemoGuard(self.lab,lambda:self.saves.append(True))
            restored.allow('POST','/api/fraud-agent/start',{})
            with self.assertRaisesRegex(LabError,'write limit'):restored.allow('POST','/api/fraud-agent/start',{})
        def fail():raise LabError('Checkpoint unavailable',503)
        broken=DemoGuard(self.lab,fail)
        with self.assertRaisesRegex(LabError,'Checkpoint'):broken.allow('POST','/api/fraud-desk/review',{})
        self.assertEqual(broken.status()['used']['writes'],3)

    def test_read_throttle_does_not_checkpoint_and_recovers_after_window(self):
        for _ in range(600):self.guard.allow('GET','/api/state')
        with self.assertRaisesRegex(LabError,'rate limit'):self.guard.allow('GET','/api/state')
        self.assertFalse(self.saves)
        self.tick=60;self.guard.allow('GET','/api/state')

    def test_existing_reports_count_toward_cap_and_replay_is_not_a_new_report(self):
        self.desk.demo('benign','existing-report')
        restored=DemoGuard(self.lab,lambda:None)
        with patch('demo_guard.DAILY_REPORTS',1):
            restored.allow('POST','/api/fraud-desk/demo',{'request_id':'existing-report'})
            with self.assertRaisesRegex(LabError,'new-report'):restored.allow('POST','/api/fraud-desk/demo',{'request_id':'new-report'})
        self.assertEqual(restored.status()['used']['reports'],1)

    def test_real_hosted_http_boundary_disables_legacy_jobs(self):
        from cloud_data import CloudData
        from server import make_server
        from test_cloud_data import FakeCloud
        cloud=CloudData('test','test-bucket','simulation',session=FakeCloud())
        server=make_server(0,Path(self.temp.name)/'http.db',cloud=cloud)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            state=requests.get(base+'/api/state',timeout=10).json()
            headers={'X-MintTown-Token':state['csrf_token']}
            for path,body,code in [('/api/science/run',{},403),('/api/fraud-agent/step',{},403),
                ('/api/fraud-agent/start',{'report_id':'unused','mode':'gemini'},409)]:
                self.assertEqual(requests.post(base+path,json=body,headers=headers,timeout=10).status_code,code)
            self.assertEqual(requests.get(base+'/api/science',timeout=10).status_code,403)
            status=requests.get(base+'/api/cloud',timeout=10).json()
            self.assertIsNone(status['guardrails']['limits']['new_reports_per_day'])
            self.assertEqual(status['guardrails']['used']['writes'],0)
            self.assertEqual(server.lab.db.execute('SELECT count(*) FROM fraud_agent_turns').fetchone()[0],0)
        finally:server.shutdown();server.server_close();thread.join();server.lab.db.close()

    def test_default_admission_has_no_arbitrary_daily_counter_stop(self):
        with self.lab.db:self.lab.db.execute('UPDATE demo_daily_usage SET reports=9999,writes=9999,world_steps=9999,starts=9999')
        self.guard.allow('POST','/api/fraud-desk/report',{'request_id':'next-request'})
        self.assertEqual(self.guard.status()['used']['reports'],10000)
        self.assertIsNone(self.guard.status()['limits']['writes_per_day'])


if __name__=='__main__':unittest.main()
