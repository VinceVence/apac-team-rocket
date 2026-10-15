"""Default admission follows reserved dollars, not an arbitrary daily counter."""
import tempfile,unittest
from pathlib import Path
from agents import Config,Agents
from lab import Lab,now
from server import make_server

class SpendAdmissionChecks(unittest.TestCase):
    def test_count_does_not_block_but_money_does(self):
        with tempfile.TemporaryDirectory() as folder:
            lab=Lab(Path(folder)/'meter.db');meter=Agents(lab,Config())
            try:
                self.assertIsNone(meter.config.daily_calls)
                self.assertEqual(meter.call_ceiling(100,.1,.15),290)
                self.assertEqual(meter.call_ceiling(100,1.995,.15),100)
                self.assertEqual(meter.call_ceiling(100,.1,7.995),100)
                meter.config.daily_calls=10
                self.assertEqual(meter.call_ceiling(10,.01,.01),10)
            finally:lab.db.close()

    def test_run_lease_pauses_without_resetting_spend_or_scene(self):
        with tempfile.TemporaryDirectory() as folder:
            s=make_server(0,Path(folder)/'world.db',Config(live=False),seed_history=False)
            try:
                state=s.world_demo.start(0,mode='simulation',background=False);scene=state['scene_id'];budget=s.agents.budget()
                with s.lab.db:s.lab.db.execute("UPDATE world_demo_state SET lease_until='2020-01-01T00:00:00+00:00'")
                stopped=s.world_demo.tick(state['run_id']);self.assertFalse(stopped['running']);self.assertIn('15 minutes',stopped['note'])
                resumed=s.world_demo.start(state['run_id'],mode='simulation',background=False)
                self.assertEqual(resumed['scene_id'],scene);self.assertTrue(resumed['running']);self.assertGreater(resumed['lease_until'],now())
                self.assertEqual(budget,s.agents.budget())
            finally:s.server_close();s.lab.db.close()

if __name__=='__main__':unittest.main()
