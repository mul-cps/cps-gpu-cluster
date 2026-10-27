"""CPU-only closed-target/source-closure tests; no hardware qualification."""
import importlib.util
from pathlib import Path
import pytest

HERE=Path(__file__).parent

def module():
 s=importlib.util.spec_from_file_location('second_card_prepare',HERE/'prepare.py')
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def observations():
 return {'policy_hash':'sha256:'+'a'*64,'node':{'metadata':{'name':'k3s-wk-gpu2','uid':'3336cdd5-d245-436e-b57c-2f66c6dcaa41'},'status':{'nodeInfo':{'bootID':'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'}}},
 'namespace':{'metadata':{'name':'cps-native-second-card-qa','uid':'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'}},
 'guard':{'node_uid':'3336cdd5-d245-436e-b57c-2f66c6dcaa41','boot_id':'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','driver_generation':'cccccccc-cccc-4ccc-8ccc-cccccccccccc','driver_version':'615.71.09'},
 'device':{'node_uid':'3336cdd5-d245-436e-b57c-2f66c6dcaa41','boot_id':'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','gpu_uuid':'GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6'},
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
