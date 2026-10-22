import ast,hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
import pytest
HERE=Path(__file__).parent

def module(name):
 s=importlib.util.spec_from_file_location(name,HERE/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def test_runner_default_inert():
 p=subprocess.run([sys.executable,'-I','-B',str(HERE/'run_mps.py')],capture_output=True,text=True)
 assert p.returncode==0,p.stderr
 assert json.loads(p.stdout)['state']=='inert'

def test_probe_and_measurement_engine_are_unchanged():
 # Canonical AST pins extracted from original trusted wrapper
 # faddd67f25417c0861cf27f82bf213ac1601fcd772d51962431e92112881f9da.
 expected={'require': '95ed15b88b3b6c7b88bde1e84b8a2d618008ed49f62129659be39b79a7e0bf48', 'assess': '818b5db2826a0e40e517699f594cf6f91d2a499ddd666f8df983c1a66826ba16', 'Session': '3577d81b95c6eabdf4718d3230c6eac7f1304765090203f7c2edda353f629c1e', 'finish_all': '5037a2d3c617208fd7d1ab4fd511e9a77d14f586039576f258acd8e38cdf8760', 'registration_processes': '3c66e2c548e2279fd00fce23c03c2e6d50373b4d5fb0c6e4b3c80767cd1bd9ad'}
 actual=ast.parse((HERE/'engine.py').read_text())
 for name,pin in expected.items():
  node=next(n for n in actual.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
  assert hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest()==pin
 assert hashlib.sha256((HERE/'mps_probe.py').read_bytes()).hexdigest()=='a235f486239056bedf2afd6e48536c5024da5efa62340a6e7d3545dd0a1b4a8e'


@pytest.mark.parametrize('fault',['none','initial','peer-wait','mps-constructor','live-map','peer-cleanup','mps-cleanup','cleaned-map','postflight','changed-seal','cancelled'])
def test_actual_main_success_and_each_failure_stays_inconclusive(tmp_path,monkeypatch,fault):
 import copy,time
 from types import SimpleNamespace
 from unittest.mock import Mock
 w=module('run_mps');engine=module('engine');fixtures=module('test_engine').fixtures
 mps_events,peer_events=fixtures()
 targets={'pods':{'a':{'namespace':'qa','name':'a','uid':'a'},'b':{'namespace':'qa','name':'b','uid':'b'}}}
 before={'pods':[{'uid':'a'},{'uid':'b'}],'host':{'processes':[{'pid':1},{'pid':2}],'targets':[
  {'identity':{'pod_uid':k},'seal_id':'seal','limit':{'soft':5120,'hard':5120,'used':0}} for k in ('a','b')]}}
 after=copy.deepcopy(before)
 if fault=='changed-seal':after['host']['targets'][0]['seal_id']='different'
 current=SimpleNamespace(read_targets=lambda *a:targets,preflight=Mock(side_effect=[ValueError('initial') if fault=='initial' else before,ValueError('post') if fault=='postflight' else after]))
 peer=Mock();peer.wait.side_effect=ValueError('wait') if fault=='peer-wait' else None
 peer.complete.return_value=peer_events
 if fault=='peer-cleanup':peer.complete.side_effect=ValueError('peer cleanup')
 mps=Mock();mps.wait.side_effect=lambda phase:{'phase':phase,'pipe':'/tmp/cps-mps-example/pipe'};mps.finish.return_value=mps_events
 if fault=='mps-cleanup':mps.finish.side_effect=ValueError('mps cleanup')
 constructor=Mock(return_value=mps,side_effect=ValueError('constructor') if fault=='mps-constructor' else None)
 monkeypatch.setattr(engine,'Session',constructor)
 transport=SimpleNamespace(ProbeRun=Mock(return_value=peer))
 def load(path,raw):return {'engine':engine,'fresh_preflight':current,'run_peer_oom':transport}[path.stem]
 monkeypatch.setattr(w,'load',load)
 live={'mapping':{'processes':[{'host_tgid':i} for i in range(1,5)]}}
 mapper=Mock(side_effect=[InterruptedError('cancelled') if fault=='cancelled' else ValueError('live') if fault=='live-map' else live,
  ValueError('cleaned') if fault=='cleaned-map' else {'mapping':{'processes':[]}}])
 monkeypatch.setattr(w,'attribute',mapper)
 vector=tmp_path/'mapper.json';vector.write_text(json.dumps(['ssh','host','python3','/root/mapper.py','--execute','--source-sha256',w.MAPPER_SHA]));vector.chmod(0o600)
 manifest=tmp_path/'manifest.json';manifest.write_text('{}');manifest.chmod(0o600)
 output=tmp_path/'output'
 args=['--execute','--manifest',str(manifest),'--manifest-sha256',hashlib.sha256(manifest.read_bytes()).hexdigest(),
  '--runner-sha256',hashlib.sha256((HERE/'run_mps.py').read_bytes()).hexdigest(),'--mapper-argv',str(vector),
  '--mapper-argv-sha256',hashlib.sha256(vector.read_bytes()).hexdigest(),'--output',str(output)]
 if fault=='none':w.main(args)
 else:
  with pytest.raises(SystemExit):w.main(args)
 receipt=json.loads((output/'receipt.json').read_text())
 assert receipt['state']==('bounded-mps-peer-and-cleanup-measurements-passed' if fault=='none' else 'inconclusive')
 assert receipt['production_qualified'] is False
 if fault!='initial':peer.complete.assert_called_once()
 if fault not in ('initial','peer-wait','mps-constructor'):mps.finish.assert_called_once()


@pytest.mark.parametrize('fault',['none','pid','parent','stale','wrong-pod','changed-seal','cleaned','remote-error'])
def test_actual_attribute_checks_root_lifetimes_and_full_fresh_brackets(monkeypatch,tmp_path,fault):
 import copy,time
 from types import SimpleNamespace
 from unittest.mock import Mock
 w=module('run_mps');e=module('engine')
 def ident(pid):return {'uid':1000,'gid':100,'start_ticks':pid+20,'namespace_pids':[pid]}
 registration={'clients':[{'identity':ident(10)},{'identity':ident(11)}],
  'daemon_processes':[{**ident(12),'executable':'nvidia-cuda-mps-control'},{**ident(13),'executable':'nvidia-cuda-mps-server'}],
  'registered_clients':[10,11],'registered_server':13}
 identity={'pod_uid':'actual-a','cgroup_relative':'/kubepods/actual-a','cgroup_inode':77}
 before={'pods':['actual-a','actual-b'],'host':{'processes':[{'pid':100},{'pid':200}],
  'targets':[{'identity':identity,'seal':'old','limit':{'soft':5120,'hard':5120,'used':0}},
             {'identity':{'pod_uid':'actual-b'},'seal':'other','limit':{'soft':5120,'hard':5120,'used':0}}]}}
 after=copy.deepcopy(before)
 if fault=='changed-seal':after['host']['targets'][0]['seal']='changed'
 current=SimpleNamespace(preflight=Mock(side_effect=[before,after]))
 rows=[{'role':r['role'],'host_pid':1000+i,'host_tgid':1000+i,'pid_start_ticks':r['start_ticks'],
  'namespace_pid':r['namespace_pid'],'pid_namespace_inode':88,'process_cgroup_relative':'/kubepods/actual-a/container',
  'pod_cgroup_inode':77,'cmdline_sha256':'a'*64} for i,r in enumerate(e.registration_processes(registration))]
 receipt={'kind':'root-mps-process-attribution','mode':'cleaned' if fault=='cleaned' else 'live','trial_id':'trial',
  'pod_uid':'actual-a','driver_generation':w.GENERATION,'observed_time_ns':time.time_ns(),
  'processes':[] if fault=='cleaned' else rows}
 if fault=='pid':rows[0]['namespace_pid']=999
 elif fault=='parent':rows[0]['process_cgroup_relative']='/foreign'
 elif fault=='stale':receipt['observed_time_ns']-=31000000000
 elif fault=='wrong-pod':receipt['pod_uid']='other'
 monkeypatch.setattr(w.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=1 if fault=='remote-error' else 0,stdout=json.dumps(receipt).encode(),stderr=b'ValueError: Original MPS process remains\n'))
 args=(current,e,{'pods':{}},before,0,registration,{'pipe':'/tmp/cps-mps-example/pipe'},'trial',['trusted'])
 if fault in ('none','cleaned'):
  result=w.attribute(*args,original=rows if fault=='cleaned' else None)
  assert result['mapping']==receipt and current.preflight.call_count==2
 else:
  with pytest.raises(ValueError):w.attribute(*args,diagnostics=tmp_path/'mapper-failure.json')
  if fault=='remote-error':
   evidence=json.loads((tmp_path/'mapper-failure.json').read_text())
   assert evidence['stderr']=='ValueError: Original MPS process remains\n'
   assert (tmp_path/'mapper-failure.json').stat().st_mode&0o777==0o600


def test_diagnostic_error_contains_bounded_message_and_trace_without_locals():
 w=module('run_mps')
 try:raise ValueError('x'*5000)
 except ValueError as error:
  value=w.error_evidence(error,'clean-map')
 assert value['stage']=='clean-map' and value['type']=='ValueError'
 assert len(value['message'])==1024 and len(value['frames'])<=8
 assert all(set(frame)=={'file','function','line'} for frame in value['frames'])
 assert all('/' not in frame['file'] for frame in value['frames'])
