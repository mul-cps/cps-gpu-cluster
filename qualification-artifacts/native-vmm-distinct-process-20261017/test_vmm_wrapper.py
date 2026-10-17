import copy,unittest
from unittest.mock import Mock
import run_vmm_cross_parent as w
class WrapperTests(unittest.TestCase):
 def test_marker_bound_exact_open_result_finish_order(self):
  trace=[];denied=Mock();witness=Mock();result={'phase':'import-result','api':'cuMemImportFromShareableHandle'}
  denied.send.side_effect=lambda op,t:trace.append(op);denied.wait.side_effect=lambda phase:(trace.append('result')or result);denied.complete.side_effect=lambda:(trace.append('complete')or [])
  witness.begin.side_effect=lambda a:trace.append('begin');witness.end.side_effect=lambda r:(trace.append('end')or ({},{}))
  w.open_denied(denied,'trial',{},witness)
  self.assertEqual(trace,['begin','open','result','end','finish','complete'])
 def test_failed_begin_never_sends_open(self):
  denied=Mock();witness=Mock();witness.begin.side_effect=ValueError()
  with self.assertRaises(ValueError):w.open_denied(denied,'t',{},witness)
  denied.send.assert_not_called()
 def test_default_inert_no_preflight(self):
  from unittest.mock import patch
  with patch.object(w,'load_preflight',side_effect=AssertionError('API called')),patch('builtins.print') as out:w.main([])
  self.assertIn('inert',out.call_args.args[0])
 def test_missing_source_pins_fail_before_transport(self):
  from unittest.mock import patch
  with patch.object(w,'load_preflight',side_effect=AssertionError('API called')):
   with self.assertRaises(ValueError):w.main(['--execute'])
if __name__=='__main__':unittest.main()

class OrchestrationTests(unittest.TestCase):
 def fixture(self,tmp):
  import hashlib,json,types,uuid
  from pathlib import Path
  trial='e9c5edb3-8474-4f7d-8ca2-20a6d7f4d562';parent=Path(w.__file__).parent
  args=['--execute','--observer-pod-uid','8a3a0296-2a41-49e0-ba20-28f503ec5887','--output',str(tmp/'run')]
  for flag,file in [('preflight-source-sha256','current_preflight.py'),('wrapper-source-sha256','run_vmm_cross_parent.py'),('endpoint-source-sha256','vmm_endpoint.py'),('bridge-source-sha256','vmm_bridge.py'),('witness-collector-sha256','kernel_witness_collector.py'),('witness-validator-sha256','kernel_witness_validator.py'),('witness-transport-sha256','kernel_witness_transport.py')]:args.extend(['--'+flag,hashlib.sha256((parent/file).read_bytes()).hexdigest()])
  ident={'device':1,'inode':2,'mode':3,'rdev':0};event=lambda phase,**v:{'phase':phase,'trial_id':trial,'namespace_pid':3,'monotonic_ns':10,'production_qualified':False,**v}
  def vector(phase,**v):return event(phase,vector_verified=True,vector_elements=256,**v)
  exporter=[event('exporter-ready',backing_bytes=67108864,fd_identity=ident),vector('exporter-tick',tick=1,monotonic_ns=1),vector('exporter-tick',tick=2,monotonic_ns=500),vector('exporter-recovery',monotonic_ns=501),event('exporter-finished'),event('receipt',state='measurement-completed',explicit_native_cleanup_completed=True)]
  def imports(expect):return [event('socket-ready'),event('importer-ready'),vector('importer-before-kernel'),event('import-result',api='cuMemImportFromShareableHandle',expect=expect,cuda_result=0 if expect=='allow' else 800,cuda_name='CUDA_SUCCESS' if expect=='allow' else 'CUDA_ERROR_NOT_PERMITTED',call_started_monotonic_ns=100,call_ended_monotonic_ns=200),vector('importer-after-kernel'),event('receipt',state='measurement-completed',explicit_native_cleanup_completed=True)]
  sessions=[]
  class Session:
   def __init__(self,target,args,source,label,output):
    expected='jupyter-b' if label=='cross-parent-importer' else 'jupyter-a'
    if target['name']!=expected:raise AssertionError('Manifest key order changed authority mapping')
    self.label=label;self.events=exporter if label=='exporter' else imports('allow' if label=='same-parent-positive' else 'deny');self.closed=False;sessions.append(self)
   def wait(self,phase):return next(e for e in self.events if e['phase']==phase)
   def wait_matching(self,p):return next(e for e in self.events if p(e))
   def send(self,*a):pass
   def complete(self):return self.events
   def abandon(self):self.closed=True
  before={'pods':{'stable':True},'host':{'targets':[{'pod_uid':uid,'identity':{'pod_uid':uid,'cgroup_inode':i},'inventory_row':{'used':0},'intent':{},'seal_id':'seal','journal_sha256':'x','gate_sha256':'y'}for i,uid in enumerate(('4010edf4-f407-409b-aa4c-de0615e8c05c','879a4589-faee-4569-bdb8-f2e7c154ef19'),1)]}}
  manifest=__import__('current_preflight').validate_targets({'pods':{k:dict(namespace='jupyterhub',name='jupyter-'+k,uid=uid,cap_mib=5120)for k,uid in zip(('a','b'),('4010edf4-f407-409b-aa4c-de0615e8c05c','879a4589-faee-4569-bdb8-f2e7c154ef19'))},'node':dict(namespace='cps-native-system',name='node-agent',uid=str(uuid.uuid4())),'observer':dict(namespace='gpu-operator',name='cps-native-driver-control',uid=args[2])})
  manifest['pods']=dict(reversed(list(manifest['pods'].items())))
  h=types.SimpleNamespace(read_targets=Mock(return_value=manifest),configure=Mock(),GPU='GPU-16128952-b438-556a-00bb-93039ee24e56',OBSERVER_ARGV=['root-python','-'],preflight=Mock(return_value=before),canonical_uuid=lambda u:uuid.UUID(u))
  proof=lambda transfer:{'state':'one-bounded-vmm-descriptor-forwarded','trial_id':trial,'transfer':transfer,'descriptor_count':1,'backing_bytes':67108864,'network_namespace_entered':False,'fd_identity':ident,'importer_attribution':{'host_tgid':7779}}
  class Witness:
   def __init__(self,*a,**k):pass
   def begin(self,a):pass
   def end(self,r):return {},{'kernel_witness_correlated':True,'trial_id':trial,'host_tgid':7779}
   def close(self):pass
  return args,trial,h,Session,types.SimpleNamespace(ROOT='/root-witness',KernelWitness=Witness),[proof('positive'),proof('cross')],sessions
 def run_case(self,fault=None):
  import json,tempfile
  from pathlib import Path
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as raw:
   tmp=Path(raw);tmp.chmod(0o700);args,trial,h,S,T,B,sessions=self.fixture(tmp)
   with patch.object(w,'load_preflight',return_value=h),patch.object(w,'load_witness',return_value=T),patch.object(w,'Session',S),patch.object(w,'bridge',side_effect=B),patch.object(w.uuid,'uuid4',return_value=__import__('uuid').UUID(trial)),patch.object(w.signal,'signal'):
    if fault=='after':h.preflight.side_effect=[h.preflight.return_value,ValueError('late API proof failure')]
    if fault=='cleanup':original=S.abandon;S.abandon=lambda self:(_ for _ in ()).throw(ValueError())if self.label=='exporter'else original(self)
    if fault:
     with self.assertRaises(SystemExit):w.main(args)
    else:w.main(args)
   receipt=json.loads((tmp/'run/receipt.json').read_text());return receipt,sessions
 def test_actual_main_orchestration_success_and_late_failures(self):
  r,s=self.run_case();self.assertEqual(r['state'],'bounded-cross-parent-vmm-kernel-denial-measured');self.assertTrue(all(x.closed for x in s));self.assertFalse(r['production_qualified'])
  for fault in ['after','cleanup']:
   with self.subTest(fault=fault):r,s=self.run_case(fault);self.assertEqual(r['state'],'inconclusive')
