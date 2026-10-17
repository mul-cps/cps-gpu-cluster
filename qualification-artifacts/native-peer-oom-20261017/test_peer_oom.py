import copy,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import peer_probe as probe
import run_peer_oom as runner

class OOM(Exception):pass
class Tensor:
 def __init__(self,torch,size):self.torch=torch;self.size=size;self.value=0;torch.held+=size
 def __del__(self):self.torch.held-=self.size
 def fill_(self,value):self.value=value;return self
 def __getitem__(self,i):return self
 def item(self):return self.value
class Torch:
 OutOfMemoryError=OOM;uint8='uint8'
 def __init__(self,limit=4608):self.cuda=self;self.limit=limit*1048576;self.held=0;self.cache_clears=0
 def empty(self,size,**kw):
  if self.held+size>self.limit:raise OOM()
  return Tensor(self,size)
 def synchronize(self):pass
 def empty_cache(self):self.cache_clears+=1

class HoldTests(unittest.TestCase):
 def test_actual_tensor_pressure_retained_through_exact_eight_second_hold_then_recovery(self):
  torch=Torch();events=[];holds=[]
  with patch.object(probe.time,'sleep',side_effect=lambda seconds:holds.append((seconds,torch.held))):
   result=probe.run_steps(torch,lambda phase,extra=None:events.append((phase,extra or {})))
  self.assertEqual(holds,[(8,4608*1048576)])
  self.assertTrue(result['bounded_step_sequence_passed']);self.assertEqual(torch.held,0)
  names=[x[0]for x in events];self.assertLess(names.index('oom-held-start'),names.index('oom-held-end'));self.assertLess(names.index('oom-held-end'),names.index('after-over-cleanup'))
 def test_early_oom_cannot_qualify(self):
  with patch.object(probe.time,'sleep'):result=probe.run_steps(Torch(512),lambda *a:None)
  self.assertFalse(result['bounded_step_sequence_passed'])

class AssessmentTests(unittest.TestCase):
 def fixture(self):
  peer=[{'phase':'peer_tick','tick':i+1,'monotonic_ns':n,'holder_tensor_mib':0}for i,n in enumerate(range(1_000_000_000,13_000_000_000,1_000_000_000))]
  peer.append({'phase':'receipt','state':'measurement-completed','case':'peer','hardware':{'gpu_uuid':runner.GPU,'torch_version':'2.11.0'},'peer_loop_passed':True,'production_qualified':False})
  oom=[{'phase':'over-allocation-error','monotonic_ns':2_000_000_000,'typed_oom':True},
   {'phase':'oom-held-start','monotonic_ns':2_100_000_000,'held_tensor_mib':4608},
   {'phase':'oom-held-end','monotonic_ns':10_100_000_000,'held_tensor_mib':4608},
   {'phase':'after-recovery-free64','monotonic_ns':10_500_000_000},
   {'phase':'receipt','case':'oom','state':'measurement-completed','hardware':{'gpu_uuid':runner.GPU,'torch_version':'2.11.0'},'bounded_step_sequence_passed':True,'over_denied':True,'ordinary_byte':19,'recovery_byte':37,'held_before_oom_mib':4608,'over_error':{'kind':'torch.OutOfMemoryError','cuda_error_code':None},'production_qualified':False}]
  samples=[{'observed_monotonic_ns':n,'physical_free_bytes':8*1024**3,'physical_total_bytes':40*1024**3,'gpu_uuid':runner.GPU,'node_pod_uid':'node'}for n in (3_000_000_000,5_000_000_000,7_000_000_000)]
  return peer,oom,samples
 def test_peer_must_progress_inside_oom_hold_and_physical_headroom(self):
  result=runner.assess(*self.fixture());self.assertTrue(result['measurement_passed']);self.assertGreaterEqual(result['peer_ticks_inside_oom_hold'],2)
 def test_global_bracket_only_or_virtualized_headroom_cannot_pass(self):
  for kind in ('no-inside-peer','cap-virtualized','low-free','no-inside-sample','hold-short','generic-error'):
   peer,oom,samples=self.fixture()
   if kind=='no-inside-peer':peer=[x for x in peer if x['phase']!='peer_tick' or x['monotonic_ns']in (1_000_000_000,12_000_000_000)]
   elif kind=='cap-virtualized':samples[0]['physical_total_bytes']=5*1024**3
   elif kind=='low-free':samples[1]['physical_free_bytes']=6*1024**3
   elif kind=='no-inside-sample':samples[0]['observed_monotonic_ns']=1;samples[1]['observed_monotonic_ns']=2;samples[2]['observed_monotonic_ns']=3
   elif kind=='hold-short':oom[2]['monotonic_ns']=3_000_000_000
   else:oom[-1]['over_error']={'kind':'RuntimeError','cuda_error_code':None}
   with self.subTest(kind=kind),self.assertRaises(ValueError):runner.assess(peer,oom,samples)
 def test_default_inert_before_any_source_manifest_or_api_read(self):
  with patch.object(Path,'read_bytes',side_effect=AssertionError('I/O')),patch('subprocess.run',side_effect=AssertionError('API')),patch('builtins.print')as output:runner.main([])
  self.assertTrue(json.loads(output.call_args.args[0])['inert'])

class SafetyTests(unittest.TestCase):
 def test_unexpected_overcap_success_is_not_touched_or_qualified(self):
  class Tracked(Tensor):
   def fill_(self,value):
    if self.torch.held>5120*1048576:raise AssertionError('Unexpected over-cap allocation touched')
    return super().fill_(value)
  class Unlimited(Torch):
   def empty(self,size,**kw):return Tracked(self,size)
  torch=Unlimited();events=[]
  with patch.object(probe.time,'sleep',side_effect=AssertionError('Must not hold unexpected success')):
   result=probe.run_steps(torch,lambda phase,extra=None:events.append(phase))
  self.assertFalse(result['bounded_step_sequence_passed']);self.assertIn('unexpected-over-allocation-success',events);self.assertEqual(torch.held,0)
 def test_generic_error_cannot_be_typed_as_oom(self):
  self.assertIsNone(probe.oom_proof(RuntimeError('CUDA out of memory'),Torch()))
 def test_current_target_uid_image_or_restart_drift_rejected(self):
  current=runner.current;row={'name':'current','namespace':'jupyterhub','uid':'actual'}
  pod={'metadata':{'uid':'actual'},'spec':{'nodeName':'k3s-wk-gpu2','containers':[{'name':'notebook','image':current.NOTEBOOK_IMAGE}]},'status':{'phase':'Running','containerStatuses':[{'name':'notebook','ready':True,'restartCount':0,'state':{'running':{}},'imageID':current.NOTEBOOK_IMAGE}]}}
  self.assertEqual(current.checked_pod(pod,row,'notebook',current.NOTEBOOK_IMAGE)['uid'],'actual')
  for change in ('uid','image','restart'):
   altered=copy.deepcopy(pod)
   if change=='uid':altered['metadata']['uid']='replaced'
   elif change=='image':altered['spec']['containers'][0]['image']='old'
   else:altered['status']['containerStatuses'][0]['restartCount']=1
   with self.subTest(change=change),self.assertRaises(ValueError):current.checked_pod(altered,row,'notebook',current.NOTEBOOK_IMAGE)
 def test_sha_drift_refused_before_reading_targets_or_creating_output(self):
  with tempfile.TemporaryDirectory()as directory:
   path=Path(directory)/'source';path.write_text('reviewed')
   with self.assertRaises(ValueError):runner.verified_source(path,'0'*64)
 def test_execute_missing_identity_refuses_before_any_api_or_source_read(self):
  with patch.object(Path,'read_bytes',side_effect=AssertionError('I/O')),patch('subprocess.run',side_effect=AssertionError('API')):
   with self.assertRaises(ValueError):runner.main(['--execute'])

class KernelWiringTests(unittest.TestCase):
 def test_kernel_mode_default_inert_before_reads(self):
  with patch.object(runner,'verified_source',side_effect=AssertionError('source read')),patch.object(runner.current,'read_targets',side_effect=AssertionError('manifest read')),patch('builtins.print')as output:
   runner.main(['--mode','kernel','--kernel-manifest','/not/read'])
  self.assertTrue(json.loads(output.call_args.args[0])['inert'])
 def test_abandon_uses_owned_kernel_close_not_process_kill(self):
  from unittest.mock import Mock
  run=Mock(spec=['close']);runner.abandon(run);run.close.assert_called_once()
 def test_kernel_mode_requires_separate_sha_before_import_or_tokens(self):
  argv=['--execute','--mode','kernel','--manifest','manifest','--manifest-sha256','a'*64,'--output','unused','--probe-sha256','b'*64,'--preflight-sha256','c'*64,'--runner-sha256','d'*64]
  with patch.object(runner,'verified_source',return_value=b'source'),patch.object(runner.current,'read_targets',return_value={'pods':{}}),patch('kernel_probe_run.read_token',side_effect=AssertionError('token read')):
   with self.assertRaisesRegex(ValueError,'Separately reviewed'):runner.main(argv)

class TransportTests(unittest.TestCase):
 def test_remote_python_is_isolated_from_notebook_cwd_and_pythonpath(self):
  from unittest.mock import Mock
  process=Mock();process.stdout=[]
  with tempfile.TemporaryDirectory()as directory,patch.object(runner.subprocess,'Popen',return_value=process)as popen:
   run=runner.ProbeRun({'namespace':'jupyterhub','name':'current'},'peer',60,b'reviewed',Path(directory))
   run.reader.join(timeout=1);run.stderr.close()
  command=popen.call_args.args[0];start=command.index('python')
  self.assertEqual(command[start:start+4],['python','-I','-u','-'])

 def test_timeout_kill_wait_is_also_bounded(self):
  from unittest.mock import Mock
  run=object.__new__(runner.ProbeRun);run.duration=45;run.started=runner.time.monotonic();run.error=None
  run.process=Mock();run.process.wait.side_effect=[runner.subprocess.TimeoutExpired('kubectl',45),0]
  run.reader=Mock();run.reader.is_alive.return_value=False;run.stderr=Mock()
  with self.assertRaises(ValueError):run.complete()
  self.assertEqual(run.process.wait.call_args.kwargs,{'timeout':5})
  run.process.kill.assert_called_once();run.stderr.close.assert_called_once()

if __name__=='__main__':unittest.main()
