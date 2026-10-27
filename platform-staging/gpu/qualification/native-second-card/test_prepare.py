"""CPU-only closed-target/source-closure tests; no hardware qualification."""
import importlib.util
from pathlib import Path
import pytest

HERE=Path(__file__).parent

def module():
 s=importlib.util.spec_from_file_location('second_card_prepare',HERE/'prepare.py')
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def observations():
 return {'cdi':{'path':'/var/run/cdi/k8s.device-plugin.nvidia.com-gpu.json','sha256':'b940041ddae78f5570f05ede8347b4eb366892342a581cc01fac2edacf4cd087','raw':(HERE/'fixtures/second-device-cdi.json').read_text()},'policy_hash':'sha256:'+'a'*64,'node':{'metadata':{'name':'k3s-wk-gpu2','uid':'3336cdd5-d245-436e-b57c-2f66c6dcaa41'},'status':{'nodeInfo':{'bootID':'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'}}},
 'namespace':{'metadata':{'name':'cps-native-second-card-qa','uid':'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'}},
 'guard':{'node_uid':'3336cdd5-d245-436e-b57c-2f66c6dcaa41','boot_id':'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','driver_generation':'cccccccc-cccc-4ccc-8ccc-cccccccccccc','driver_version':'615.71.09'},
 'device':{'node_uid':'3336cdd5-d245-436e-b57c-2f66c6dcaa41','boot_id':'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','gpu_uuid':'GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6','pci_bdf':'0000:06:11.0','minor_number':1,'native_inventory':{'version':1,'backend':'misc-fallback','gpu_uuid':'GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6','gpu_id':1553,'entries':[]}},
 'cohort_uid':'dddddddd-dddd-4ddd-8ddd-dddddddddddd'}

def test_wrong_device_and_changed_preimage_refused(tmp_path):
 m=module();v=observations();v['device']['gpu_uuid']='GPU-16128952-b438-556a-00bb-93039ee24e56'
 with pytest.raises(ValueError,match='second'):m.build_sources(v)
 with pytest.raises(ValueError,match='preimage'):m.checked_source('native-fresh-unequal/prepare.py',b'changed')

def test_generated_closed_sources_and_dependency_pins():
 m=module();before={n:m.source_path(n).read_bytes() for n in m.PINS}
 out=m.build_sources(observations())
 assert all(m.source_path(n).read_bytes()==r for n,r in before.items())
 assert set(out['families'])=={'cap-assignment','oom-peer','aggregate','memory-import','restart-cleanup','mps','capacity'}
 assert all(v['state']=='unrun' for v in out['families'].values())
 files=out['files']
 assert m.SECOND_GPU.encode() in files['controller.py']
 assert b'GPU-16128952' not in files['controller.py']
 assert m.sha(files['controller.py']).encode() in files['observe.py']
 assert b'/proc/self/fd/' in files['bundle/cps_compute/native_node/nvml.py']
 assert m.sha(files['bundle/cps_compute/native_node/nvml.py']).encode() in files['controller.py']
 for name,raw in files.items():
  if name.endswith('.py'):compile(raw,name,'exec')

def request():
 v=observations()
 return {'version':1,'pair':'5-10','namespace':v['namespace']['metadata']['name'],
         'namespace_uid':v['namespace']['metadata']['uid'],'cohort_uid':v['cohort_uid'],
         'gate_image':'ghcr.io/mul-cps/cps-native-node@sha256:'+'a'*64,'policy_hash':v['policy_hash']}

def test_actual_compiler_finalize_and_postfinalize_family_sources(tmp_path):
 """Synthetic API objects only; real compiler/parser path, never hardware truth."""
 import json
 m=module();v=observations();out=m.build_sources(v);files=out['files']
 r=m.load('second_test_renderer',files['render_fixture.py'],tmp_path/'render_fixture.py')
 rendered=r.render(request(),approve_qa_hostpaths=True)
 manifest={'version':1,'cohort_uid':v['cohort_uid'],'namespace_uid':v['namespace']['metadata']['uid'],
           'pods':{},'observer_argv':['ssh','host','observe.py','--execute','--cohort-uid',v['cohort_uid']],
           'physical_argv':['ssh','host','physical_samples.py','--execute']}
 for label,cap in (('a',5120),('b',10240)):
  pod=rendered['pods'][label];actual=__import__('copy').deepcopy(pod)
  actual['metadata']['uid']=('1' if label=='a' else '2')*8+'-1111-4111-8111-111111111111'
  f=r.finalize(request(),pod,pod,actual=actual,approve_qa_hostpaths=True)
  assert f['intent']['gpu_uuid']==m.SECOND_GPU and f['intent']['cap_mib']==cap
  manifest['pods'][label]={'namespace':actual['metadata']['namespace'],'name':actual['metadata']['name'],
                           'uid':actual['metadata']['uid'],'cap_mib':cap,'spec_sha256':f['spec_sha256']}
 raw=json.dumps(manifest).encode()
 closed=m.finalize_import_sources(v,raw,m.sha(raw),['ssh','host','sudo','-n','python3','-I','-B','-'])
 assert closed['manifest.json']==raw
 assert b"inventory['gpu_id']==1553" in closed['vmm-cross-parent/vmm_bridge.py']
 assert b"a['gpu_id']==1553" in closed['vmm-cross-parent/kernel_witness_validator.py']
 for name in ('vmm-owner-exit/host_owner_observer.py','vmm-cross-parent/vmm_bridge.py'):
  assert b'driver/nvidia/gpus/0000:06:11.0/cps_native_caps' in closed[name]
 for name,data in closed.items():
  if name.endswith('.py') and name!='source-preparation.py':
   assert b'0000:06:10.0' not in data and m.FIRST_GPU.encode() not in data
   assert b"gpu_id']==1552" not in data
 for field,wrongvalue in (('pci_bdf','0000:06:10.0'),('minor_number',0)):
  changed=__import__('copy').deepcopy(v);changed['device'][field]=wrongvalue
  with pytest.raises(ValueError,match='native GPU identity'):
   m.finalize_import_sources(changed,raw,m.sha(raw),['ssh','host','sudo','-n','python3','-I','-B','-'])
 import ast
 for name,var in (('vmm_bridge.py','inventory'),('kernel_witness_validator.py','a')):
  tree=ast.parse(closed['vmm-cross-parent/'+name])
  guard=next(n for n in ast.walk(tree) if isinstance(n,ast.Compare) and isinstance(n.left,ast.Subscript)
             and isinstance(n.left.value,ast.Name) and n.left.value.id==var
             and isinstance(n.left.slice,ast.Constant) and n.left.slice.value=='gpu_id'
             and any(isinstance(c,ast.Constant) and c.value==1553 for c in n.comparators))
  expr=compile(ast.Expression(guard),name,'eval')
  assert eval(expr,{var:{'gpu_id':1553}})
  assert not eval(expr,{var:{'gpu_id':1552}})
 # Runner authenticates these changed source bytes through separately pinned CLI
 # arguments (not embedded constants); retain that original refusal boundary.
 assert b"hashlib.sha256((parent/f).read_bytes()).hexdigest()==s" in closed['vmm-cross-parent/run_vmm_cross_parent.py']
 wrong=__import__('copy').deepcopy(v);wrong['device']['native_inventory']['gpu_id']=1552
 with pytest.raises(ValueError,match='native GPU identity'):
  m.finalize_import_sources(wrong,raw,m.sha(raw),['ssh','host','sudo','-n','python3','-I','-B','-'])
 for name,data in closed.items():
  if name.endswith('.py'):
   compile(data,name,'exec')
   if name!='source-preparation.py':assert m.FIRST_GPU.encode() not in data
 assert m.SECOND_GPU.encode() in closed['managed/managed_probe.py']
 # Every generated managed helper pin follows changed GPU bytes.
 assert m.sha(closed['managed/managed_probe.py']).encode() in closed['managed/run_managed.py']
 with pytest.raises(ValueError):
  altered=__import__('copy').deepcopy(manifest);altered['cohort_uid']='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee'
  bad=json.dumps(altered).encode();m.finalize_import_sources(v,bad,m.sha(bad),['ssh','host','sudo','python3','-'])

def test_default_inert_and_real_prepare_exclusive_private_output(tmp_path,monkeypatch,capsys):
 import json
 m=module()
 with monkeypatch.context() as patch:
  patch.setattr(Path,'read_bytes',lambda *a: (_ for _ in ()).throw(AssertionError('inert IO')))
  m.main([])
 assert '"gpu_calls":false' in capsys.readouterr().out
 obs=tmp_path/'observations.json';obs.write_bytes(json.dumps(observations()).encode())
 req=tmp_path/'request.json';req.write_bytes(json.dumps(request()).encode())
 out=tmp_path/'prepared'
 args=['--prepare','--observations',str(obs),'--observations-sha256',m.sha(obs.read_bytes()),
       '--inputs',str(req),'--inputs-sha256',m.sha(req.read_bytes()),'--output',str(out),'--approve-qa-hostpaths']
 m.main(args)
 receipt=json.loads((out/'preparation.json').read_bytes())
 assert not receipt['hardware_qualified'] and not receipt['launch_authorized']
 assert out.stat().st_mode&0o777==0o700
 for name,pin in receipt['generated_sha256'].items():
  assert m.sha((out/name).read_bytes())==pin
  assert (out/name).stat().st_mode&0o777==0o600
 with pytest.raises(FileExistsError):m.main(args)

def test_generated_mps_runner_authenticates_every_emitted_dependency():
 import ast
 m=module();files=m.build_sources(observations())['files']
 tree=ast.parse(files['mps/run_mps.py'])
 values={node.targets[0].id:ast.literal_eval(node.value) for node in tree.body
         if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name)
         and isinstance(node.value,ast.Constant)}
 mismatches={}
 for constant,name in (('MAPPER_SHA','mapper.py'),('ENGINE_SHA','engine.py'),
                       ('PROBE_SHA','mps_probe.py'),('PREFLIGHT_SHA','fresh_preflight.py'),
                       ('PEER_RUNNER_SHA','run_peer_oom.py'),('PEER_SHA','peer_probe.py')):
  if values[constant]!=m.sha(files['mps/'+name]):mismatches[constant]=(values[constant],m.sha(files['mps/'+name]))
 assert mismatches=={}

def test_compiled_finalized_pods_support_one_real_kubelet_restart(tmp_path):
 import copy
 m=module();files=m.build_sources(observations())['files']
 r=m.load('restart_renderer',files['render_fixture.py'],tmp_path/'render_fixture.py')
 f=m.load('restart_preflight',files['restart/fresh_preflight.py'],tmp_path/'fresh_preflight.py')
 initial=m.load('initial_preflight',files['fresh_preflight.py'],tmp_path/'initial.py')
 rendered=r.render(request(),approve_qa_hostpaths=True)
 for label,expected in (('a',1),('b',0)):
  pod=rendered['pods'][label]
  assert pod['spec']['restartPolicy']=='Always'
  actual=copy.deepcopy(pod);actual['metadata']['uid']=('1' if label=='a' else '2')*8+'-1111-4111-8111-111111111111'
  finalized=r.finalize(request(),pod,pod,actual=actual,approve_qa_hostpaths=True)
  assert finalized['pod']['spec']['restartPolicy']=='Always'
  assert finalized['spec_sha256']==r.runtime.native_spec_sha256(actual)
  row={'namespace':actual['metadata']['namespace'],'name':actual['metadata']['name'],
       'uid':actual['metadata']['uid'],'cap_mib':5120 if label=='a' else 10240,'spec_sha256':finalized['spec_sha256']}
  actual['status']={'phase':'Running','containerStatuses':[{'name':'notebook','ready':True,
       'restartCount':expected,'state':{'running':{'startedAt':'2026-10-27T00:00:00Z'}},
       'imageID':initial.NOTEBOOK_IMAGE}]}
  f.checked_pod(actual,row)
  for wrong in ((0,2) if label=='a' else (1,2)):
   altered=copy.deepcopy(actual);altered['status']['containerStatuses'][0]['restartCount']=wrong
   with pytest.raises(ValueError):f.checked_pod(altered,row)
  if label=='a':
   with pytest.raises(ValueError):initial.checked_pod(actual,row)


def test_actual_observed_cdi_kind_mapping_and_compiled_environment(tmp_path):
 import copy,json
 m=module();value=observations();files=m.build_sources(value)['files']
 r=m.load('cdi_renderer',files['render_fixture.py'],tmp_path/'render_fixture.py')
 rendered=r.render(request(),approve_qa_hostpaths=True)
 for label,pod in rendered['pods'].items():
  expected='k8s.device-plugin.nvidia.com/gpu='+m.SECOND_GPU
  gate,*identities=pod['spec']['initContainers']
  assert next(e['value']for e in gate['env']if e['name']=='NVIDIA_VISIBLE_DEVICES')=='void'
  for c in [*identities,*pod['spec']['containers']]:
   assert next(e['value']for e in c['env']if e['name']=='NVIDIA_VISIBLE_DEVICES')==expected
  actual=copy.deepcopy(pod);actual['metadata']['uid']=('1'if label=='a'else'2')*8+'-1111-4111-8111-111111111111'
  finalized=r.finalize(request(),pod,pod,actual=actual,approve_qa_hostpaths=True)
  assert finalized['intent']['gpu_uuid']==m.SECOND_GPU
  assert finalized['spec_sha256']==r.runtime.native_spec_sha256(actual)
  assert identities[0]['args']==[m.SECOND_GPU]
 # A self-consistent caller hash never authorizes another runtime provider/mapping.
 for drift in ('kind','minor','hash'):
  wrong=copy.deepcopy(value);doc=json.loads(wrong['cdi']['raw'])
  if drift=='kind':doc['kind']='management.nvidia.com/gpu'
  elif drift=='minor':
   next(d for d in doc['devices']if d['name']==m.SECOND_GPU)['containerEdits']['deviceNodes'][0]['hostPath']='/run/nvidia/driver/dev/nvidia0'
  raw=json.dumps(doc);wrong['cdi'].update(raw=raw,sha256=m.sha(raw.encode()))
  if drift=='hash':wrong['cdi'].update(raw=value['cdi']['raw'],sha256='0'*64)
  with pytest.raises(ValueError,match='CDI'):m.build_sources(wrong)
 # MPS binds both the initial CDI edit and the distinct configured CRI exec env.
 assert b'compiler_environment()' in files['mps/mps_probe.py']

def test_actual_retired_a5_b10_records_keep_original_cohort_cap_binding(tmp_path,monkeypatch):
 """Actual nonsecret retired records, deterministic fake native IO only."""
 import copy,json,types,sys
 m=module();original=json.loads((HERE/'fixtures/retired-second-card-2526f16c.json').read_bytes())
 v=observations();v['namespace']['metadata']={'name':'cps-native-second-card-20261027','uid':'036ea170-dc16-4100-96e6-9d896c2be30c'}
 identity=original['records'][0]['identity'];v['node']['status']['nodeInfo']['bootID']=identity['boot_id']
 v['guard'].update(boot_id=identity['boot_id'],driver_generation=identity['driver_generation']);v['device']['boot_id']=identity['boot_id']
 files=m.build_sources(v)['files']
 c=m.load('retirement_controller',files['controller.py'],tmp_path/'controller.py')
 models=types.ModuleType('second_card_retirement_models');models.__file__=str(tmp_path/'models.py')
 monkeypatch.setitem(sys.modules,models.__name__,models)
 exec(compile(files['bundle/cps_compute/native_gpu_controller.py'],models.__file__,'exec'),models.__dict__)
 original=json.loads((HERE/'fixtures/retired-second-card-2526f16c.json').read_bytes())
 records=[models.CapRecord.from_dict(r)for r in original['records']]
 current=c.cohort_state(observations()['cohort_uid'])
 # No real file/native mutation; original source verifies complete record equality.
 monkeypatch.setattr(models.PrivateJournal,'records',lambda self:records)
 monkeypatch.setattr(c.os,'stat',lambda path,**kw:types.SimpleNamespace(st_dev=29,st_ino=1 if str(path)==current else 2))
 back=types.SimpleNamespace(private_directory=lambda path:None)
 class Backend:
  def retired_inert_cap(self,identity,limit):return next(r.retirement for r in records if r.identity==identity)
  def read_gate(self,identity):return None
 def check(doc):
  path=tmp_path/'retirement.json';raw=json.dumps(doc).encode();path.write_bytes(raw)
  args=types.SimpleNamespace(retirement=path,retirement_sha256=m.sha(raw))
  return c.retirement_inputs(args,models,back,lambda intents,state:Backend(),current)
 assert set(check(original))=={1254502,1254660}
 for drift in ('cohort','name','cap'):
  bad=copy.deepcopy(original)
  if drift=='cohort':bad['state_root']=bad['state_root'].replace('2526f16c-8cd4-4448-aa46-7a59565a1487','eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee')
  elif drift=='name':bad['records'][1]['intent']['name']='native-second-card-a-2526f16c'
  else:bad['records'][1]['intent']['cap_mib']=5120
  with pytest.raises(ValueError):check(bad)

def test_mps_initial_oci_environment_uses_exact_provider_edits():
 """Authenticated CDI edits initial OCI env, not the CRI exec config."""
 import ast,json,types
 m=module();files=m.build_sources(observations())['files']
 tree=ast.parse(files['mps/mps_probe.py'])
 provider=json.loads(observations()['cdi']['raw'])
 device=next(d for d in provider['devices']if d['name']==m.SECOND_GPU)
 env={'CUDA_VISIBLE_DEVICES':'0','NVIDIA_VISIBLE_DEVICES':m.CDI_DEVICE}
 for edits in (provider['containerEdits'],device['containerEdits']):
  for entry in edits.get('env',[]):
   key,value=entry.split('=',1);env[key]=value  # CDI AddMultipleProcessEnv replacement.
 assert env['NVIDIA_VISIBLE_DEVICES']=='void'
 assert env['NVIDIA_VISIBLE_DEVICES']!=m.CDI_DEVICE
 assignment=next(n for n in tree.body if isinstance(n,ast.Assign)and isinstance(n.targets[0],ast.Name)and n.targets[0].id=='GPU')
 assert ast.literal_eval(assignment.value)==m.SECOND_GPU

def test_mps_actual_initial_oci_and_cri_exec_environments():
 """Actual observed two environments, fake /proc bytes only; never CUDA calls."""
 import ast,io,types
 m=module();raw=m.build_sources(observations())['files']['mps/mps_probe.py'];tree=ast.parse(raw)
 preflight=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='preflight')
 check=next(n for n in ast.walk(preflight)if isinstance(n,ast.Call)and isinstance(n.func,ast.Name)
            and n.func.id=='require'and len(n.args)>1 and isinstance(n.args[1],ast.Constant)
            and n.args[1].value=='Compiler-owned single device environment required')
 expected='k8s.device-plugin.nvidia.com/gpu='+m.SECOND_GPU
 initial={'raw':b'CUDA_VISIBLE_DEVICES=0\0NVIDIA_VISIBLE_DEVICES=void\0'}
 class Proc:
  def __init__(self,path):assert path=='/proc/1/environ'
  def open(self,mode):
   assert mode=='rb'
   if initial.get('error'):raise PermissionError('fake unreadable PID1')
   return io.BytesIO(initial['raw'])
 env={'CUDA_VISIBLE_DEVICES':'0','NVIDIA_VISIBLE_DEVICES':expected}
 scope={'os':types.SimpleNamespace(environ=env),'Path':Proc,'require':m.require}
 helper=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='compiler_environment']
 if helper:exec(compile(ast.Module(body=helper,type_ignores=[]),'actual-emitted-env','exec'),scope)
 statement=compile(ast.Expression(check),'actual-emitted-preflight-check','eval')
 eval(statement,scope) # Actual CRI exec qualified + initial OCI void must pass.
 for exec_value,initial_raw in [('void',initial['raw']),(expected.replace(m.SECOND_GPU,m.FIRST_GPU),initial['raw']),
                              (expected,b'CUDA_VISIBLE_DEVICES=0\0NVIDIA_VISIBLE_DEVICES='+expected.encode()+b'\0'),
                              (expected,b'CUDA_VISIBLE_DEVICES=0\0NVIDIA_VISIBLE_DEVICES=void\0NVIDIA_VISIBLE_DEVICES=void\0'),
                              (expected,b'CUDA_VISIBLE_DEVICES=0\0CUDA_VISIBLE_DEVICES=0\0NVIDIA_VISIBLE_DEVICES=void\0'),
                              (expected,b'x'*262145)]:
  env['NVIDIA_VISIBLE_DEVICES']=exec_value;initial['raw']=initial_raw
  with pytest.raises(ValueError):eval(statement,scope)

 env['NVIDIA_VISIBLE_DEVICES']=expected;initial['error']=True
 with pytest.raises(PermissionError):eval(statement,scope)
