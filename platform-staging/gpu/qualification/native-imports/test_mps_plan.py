import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
class MpsPlanTests(unittest.TestCase):
 def test_plan_is_inert_and_tracks_two_client_and_server_cgroups(self):
  self.assertTrue((HERE/'mps_plan.py').exists(),'Offline MPS plan missing')
  spec=importlib.util.spec_from_file_location('mps_plan',HERE/'mps_plan.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  p=m.plan('GPU-16128952-b438-556a-00bb-93039ee24e56','/run/cps-canary-mps','cps_canary','/sys/fs/cgroup/server',[(1001,'/sys/fs/cgroup/client_a',512),(1002,'/sys/fs/cgroup/client_b',5120)])
  self.assertEqual(p['state'],'inert');self.assertFalse(p['gpu_calls']);self.assertFalse(p['mpsQualified'])
  self.assertEqual(len(p['chargeObservers']),3)
  self.assertTrue(any(c['argv'][1:]==['client','list','--server=cps_canary','--format=csv,noheader'] for c in p['readOnlyCommands']))
  for bad in ([(1001,'/sys/fs/cgroup/a',512),(1001,'/sys/fs/cgroup/b',512)],[(0,'/sys/fs/cgroup/a',512),(1002,'/sys/fs/cgroup/b',512)]):
   with self.assertRaises(ValueError):m.plan('GPU-16128952-b438-556a-00bb-93039ee24e56','/run/cps-canary-mps','cps_canary','/sys/fs/cgroup/server',bad)
if __name__=='__main__':unittest.main()
