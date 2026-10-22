"""CPU-only boundaries for the explicit two5 legacy lifecycle adapter."""
import importlib.util
from pathlib import Path
import subprocess
import sys
from functools import lru_cache
import pytest

HERE = Path(__file__).parent
SDK = Path('/home/bjoern/git/cps-compute-worktrees/native-cleanup-offline-unlimited-20261023/src/cps_compute')


@lru_cache
def module():
    path = HERE / 'prepare_plain_node_agent.py'
    assert path.exists(), 'Explicit current-SDK direct Node adapter is missing'
    spec = importlib.util.spec_from_file_location('plain_node_prepare', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_default_is_inert_without_reading_or_loading_dependencies(capsys):
    m = module()
    m.main([])
    assert '"state": "inert"' in capsys.readouterr().out


def test_materialized_agent_is_inert_and_all_dependencies_authenticated(tmp_path):
    m = module()
    sources = m.build_sources()
    assert set(sources) == {'plain_node_agent.py'}
    path = tmp_path / 'plain_node_agent.py'
    path.write_bytes(sources[path.name])
    result = subprocess.run([sys.executable, '-I', '-B', str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '"api_calls": false' in result.stdout
    module_raw = m.installed_sources(SDK)
    assert len(module_raw) == 9
    corrupted = tmp_path / 'sdk'
    import shutil
    shutil.copytree(SDK, corrupted)
    (corrupted / 'native_node/backend.py').write_bytes(b'raise RuntimeError("UNVERIFIED EXECUTED")')
    import pytest
    with pytest.raises(ValueError, match='installed SDK'):
        m.installed_sources(corrupted)


def test_original_pod_and_device_barrier_validation_retained():
    # The runtime intentionally refuses SDK modules loaded by other callers;
    # exercise it in the same fresh-interpreter boundary used on the host.
    program = r'''
import importlib.util,sys
from pathlib import Path
p=Path(sys.argv[1]);s=importlib.util.spec_from_file_location('prep',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
a=m.agent_for_tests(Path(sys.argv[2]))
assert a.load_models_from_snapshot().__name__=='cps_compute.native_gpu_controller'
assert a._installed_backend.QualificationNodeBackend.__module__=='cps_compute.native_node.backend'
intent={'namespace':'qa','name':'x','pod_uid':'11111111-1111-4111-8111-111111111111','node':'k3s-wk-gpu2','spec_sha256':'a'*64}
pod={'metadata':{k:intent[k] for k in ('namespace','name')},'spec':{'nodeName':intent['node']}}
pod['metadata']['uid']=intent['pod_uid']
try:a.validate_actual_pod(pod,{'intent':intent})
except ValueError as e:assert 'specification changed' in str(e)
else:raise AssertionError('Changed admitted spec accepted')
'''
    result = subprocess.run([sys.executable, '-B', '-c', program,
        str(HERE / 'prepare_plain_node_agent.py'), str(SDK)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_global_partition_rejects_unrelated_rows_and_preserves_prior_rows():
    m = module()
    cap = 5120 * 1048576
    def row(inode, **kw):
        return dict(cgroup_id=inode, kernfs_id=inode, inode=inode, offline=False, pinned=True,
                    default_hierarchy=True, soft=cap, hard=cap, used=123, **kw)
    actual = {'version': 1, 'backend': 'misc-fallback', 'gpu_uuid': m.GPU,
              'gpu_id': 0, 'entries': [row(11), row(22)]}
    m.partition_inventory(actual, {11: cap, 22: cap}, {}, set())
    import copy, pytest
    for fault in ('foreign', 'cap', 'charge', 'prior'):
        bad = copy.deepcopy(actual)
        prior = {}
        if fault == 'foreign': bad['entries'].append(row(33))
        if fault == 'cap': bad['entries'][0]['hard'] = 2 * cap
        if fault == 'charge': bad['entries'][0]['used'] = cap + 1
        if fault == 'prior': prior[33] = row(33)
        with pytest.raises(ValueError): m.partition_inventory(bad, {11: cap, 22: cap}, prior, set())
    prior = row(33); prior.update(offline=True, soft=0, hard=(1 << 64) - 1, used=0)
    actual['entries'].append(prior)
    m.partition_inventory(actual, {11: cap, 22: cap}, {33: prior}, set())
    actual['entries'][-1]['used'] = 1
    with pytest.raises(ValueError): m.partition_inventory(actual, {11: cap, 22: cap}, {33: prior}, set())


def test_preexisting_module_object_with_matching_filename_is_rejected():
    # Disk bytes/__file__ alone must not authenticate executed module objects.
    program = r'''
import importlib.util, sys, types
from pathlib import Path
p=Path(sys.argv[1]);s=importlib.util.spec_from_file_location('prep',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
fake=types.ModuleType('cps_compute');fake.__file__=str(Path(sys.argv[2])/'__init__.py');fake.__path__=[sys.argv[2]]
sys.modules['cps_compute']=fake
try:m.installed_modules(Path(sys.argv[2]))
except ValueError as e:assert 'unowned' in str(e)
else:raise AssertionError('Unowned executable module was trusted')
'''
    result = subprocess.run([sys.executable, '-B', '-c', program,
        str(HERE / 'prepare_plain_node_agent.py'), str(SDK)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_original_uid_absence_only_accepts_authenticated_replacement():
    program = r'''
import importlib.util,sys,copy
from pathlib import Path
from types import SimpleNamespace
p=Path(sys.argv[1]);s=importlib.util.spec_from_file_location('prep',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
a=m.agent_for_tests(Path(sys.argv[2]))
intent=SimpleNamespace(namespace='qa',name='notebook',pod_uid='11111111-1111-4111-8111-111111111111')
pod={'apiVersion':'v1','kind':'Pod','metadata':{'namespace':'qa','name':'notebook','uid':'22222222-2222-4222-8222-222222222222'}}
assert m.original_uid_absence(None,intent,a) is None
assert m.original_uid_absence(pod,intent,a)==pod['metadata']['uid']
for fault in ('same','namespace','name','missing','zero','kind'):
 bad=copy.deepcopy(pod)
 if fault=='same':bad['metadata']['uid']=intent.pod_uid
 if fault=='namespace':bad['metadata']['namespace']='foreign'
 if fault=='name':bad['metadata']['name']='foreign'
 if fault=='missing':bad['metadata'].pop('uid')
 if fault=='zero':bad['metadata']['uid']='00000000-0000-0000-0000-000000000000'
 if fault=='kind':bad['kind']='ConfigMap'
 try:m.original_uid_absence(bad,intent,a)
 except ValueError:pass
 else:raise AssertionError('Invalid original-absence response accepted: '+fault)
'''
    result = subprocess.run([sys.executable, '-B', '-c', program,
        str(HERE / 'prepare_plain_node_agent.py'), str(SDK)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_real_sdk_completed_cleanup_receipt_with_unrelated_peer_and_tampering():
    # Only external host/driver operations are synthetic. The SDK controller,
    # complete journal, original backend and typed completion/receipt are real.
    program = r'''
import importlib.util,sys,shutil,json
from pathlib import Path
from dataclasses import replace
p=Path(sys.argv[1]);s=importlib.util.spec_from_file_location('prep',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
a=m.agent_for_tests(Path(sys.argv[2]))
from test_native_node_backend import NodeBackendTests
from cps_compute.native_gpu_control import validate_cleanup_record
f=NodeBackendTests();f.setUp()
try:
 original=f.controller.reconcile(f.intent);original=replace(original,state='cleanup-prepared');f.journal.write(original)
 f.stop();f.pod=None;shutil.rmtree(f.group);(f.state/'receipts'/f'{f.intent.pod_uid}.json').unlink()
 f.retired_inventory(original,soft=0,hard=f.m.MAX_LIMIT)
 terminal=f.controller.cleanup(f.intent);assert terminal.state=='cleanup-offline-unlimited'
 enrollment={'binding_id':'a'*60,'attempt':'22222222-2222-4222-8222-222222222222','intent':f.intent.to_dict()}
 envelope={'enrollment':enrollment,'configmap_uid':'44444444-4444-4444-8444-444444444444','authority_namespace':'pilot'}
 f.clients={98765};writes=list(f.driver.writes)
 actual=a.cleanup_receipt(envelope,terminal,f.backend,None,f.m)
 receipt=json.loads(actual['data']['receipt.json'])
 expected={k:v for k,v in receipt.items() if k!='cleanup_offline'}
 validate_cleanup_record(receipt,expected)
 assert f.driver.writes==writes
 f.retired_inventory(original,soft=0,hard=f.m.MAX_LIMIT,used=1)
 try:a.cleanup_receipt(envelope,terminal,f.backend,None,f.m)
 except ValueError:pass
 else:raise AssertionError('Changed native terminal accepted')
 assert f.driver.writes==writes
finally:f.doCleanups()
'''
    import os
    env = {**os.environ, 'PYTHONPATH': str(SDK.parent) + ':' + str(SDK.parent.parent / 'tests')}
    result = subprocess.run([sys.executable, '-B', '-c', program,
        str(HERE / 'prepare_plain_node_agent.py'), str(SDK)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_guarded_native_set_denies_foreign_inventory_and_keeps_emergency_stop():
    program = r'''
import importlib.util,sys
from pathlib import Path
p=Path(sys.argv[1]);s=importlib.util.spec_from_file_location('prep',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
a=m.agent_for_tests(Path(sys.argv[2]))
from test_native_node_backend import NodeBackendTests
f=NodeBackendTests();f.setUp()
try:
 record=f.controller.reconcile(f.intent)
 guard=object.__new__(m.InventoryGuard);guard.agent=a;guard.back=a._installed_backend
 def denied(source):raise ValueError('Unrelated physical native entry')
 guard.check=denied
 cls=guard.backend_type()
 backend=cls(f.m,f.manual,intents=[f.intent],driver=f.driver,get_pod=f.backend.get_pod,get_node=f.backend.get_node,
  get_cri=f.backend.get_cri,delete_pod=f.backend.delete_pod,gpu_clients=f.backend.gpu_clients,health=f.backend.health,
  proc_root=f.proc,cgroup_root=f.cg,state_root=f.state,trusted_uid=f.uid)
 writes=list(f.driver.writes)
 for operation in (lambda:backend.set_limit(record.identity,record.limit),lambda:backend.observe(f.intent),
                   lambda:backend.seal_gate(record.identity,record.receipt),lambda:backend.check_cleanup(record.identity)):
  try:operation()
  except ValueError as e:assert 'Unrelated' in str(e)
  else:raise AssertionError('Guarded operation bypassed full inventory')
 assert f.driver.writes==writes
 backend.quarantine(record.identity,'test')
 assert f.deleted==[f.intent.pod_uid] and f.driver.writes==writes
 assert f.backend.read_gate(record.identity) is None
finally:f.doCleanups()
'''
    import os
    env = {**os.environ, 'PYTHONPATH': str(SDK.parent) + ':' + str(SDK.parent.parent / 'tests')}
    result = subprocess.run([sys.executable, '-B', '-c', program,
        str(HERE / 'prepare_plain_node_agent.py'), str(SDK)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('completion', ['finite', 'unlimited'])
def test_full_original_retirement_partition_native_cleanup_and_published_name_reuse(completion):
    program = r'''
import importlib.util,sys,shutil,json,hashlib,copy
from pathlib import Path
from dataclasses import replace,asdict
from types import SimpleNamespace
p=Path(sys.argv[1]);s=importlib.util.spec_from_file_location('prep',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
a=m.agent_for_tests(Path(sys.argv[2]))
import test_native_node_backend as fixtures
old=fixtures.NodeBackendTests();old.setUp()
fixtures.UID='99999999-9999-4999-8999-999999999999'
f=fixtures.NodeBackendTests();f.setUp()
try:
 previous=old.controller.reconcile(old.intent);old.stop();old.pod=None;shutil.rmtree(old.group)
 old.retired_inventory(previous);previous=old.controller.cleanup(old.intent)
 assert previous.state=='retired-inert-cap'
 from cps_compute.native_gpu_runtime import GPU_IDENTITY_SOURCE
 image='ghcr.io/mul-cps/cps-jupyter-notebook@sha256:5427088986bc06ad0713875d1aa2f31439f0bd1fbe6099d4669570fcf3e85be4'
 f.pod['spec']['initContainers'][0]['image']='ghcr.io/mul-cps/cps-native-node@sha256:81aac20157965ed5503b0d208b0326fef1ba10d71089d9e635128cea48dafe82'
 f.pod['spec']['initContainers'].append({'name':'cps-native-device-identity','image':image,
  'command':['python','-I','-S','-c',GPU_IDENTITY_SOURCE],'args':[f.intent.gpu_uuid],
  'env':[{'name':'NVIDIA_VISIBLE_DEVICES','value':f.intent.gpu_uuid},{'name':'CUDA_VISIBLE_DEVICES','value':'0'}]})
 f.pod['spec']['containers'][0]['image']=image
 f.pod['metadata']['namespace']='jupyterhub'
 f.pod['status']['initContainerStatuses']=[{'name':'cps-native-cap-gate','state':{'running':{}},'restartCount':0}]
 spec=hashlib.sha256(json.dumps(f.pod['spec'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
 f.intent=replace(f.intent,namespace='jupyterhub',spec_sha256=spec)
 f.backend.intents={f.intent.pod_uid:f.intent}
 f.cri['status']['labels']['io.kubernetes.pod.namespace']='jupyterhub'
 identity=f.backend.observe(f.intent).identity
 path=f.retired_inventory(previous)
 prior_row=json.loads(path.read_text())['entries'][0]
 current_row=copy.deepcopy(prior_row);inode=identity.cgroup_inode
 current_row.update(cgroup_id=inode,kernfs_id=inode,inode=inode,offline=False)
 physical=json.loads(path.read_text())
 def physical_write():
  path.chmod(0o600);path.write_text(json.dumps(physical));path.chmod(0o400)
 physical_write()
 c=a._retirement;c.NS='qualification';c.NODE_UID=f.intent.node_uid;c.BOOT=identity.boot_id
 c.GENERATION=identity.driver_generation;c.STATE=str(old.state)
 descriptor={'version':2,'states':[{'state_root':str(old.state),'records':[previous.to_dict()]}]}
 proof=f.root/'prior.json';proof.write_text(json.dumps(descriptor))
 args=SimpleNamespace(retirement=proof,retirement_sha256=hashlib.sha256(proof.read_bytes()).hexdigest())
 config={'version':1,'enabled':True,'authority_namespace':'pilot','policy_hash':f.intent.policy_hash,
  'pool':{'node':f.intent.node,'node_uid':f.intent.node_uid,'gpu_uuid':f.intent.gpu_uuid,'max_workspaces':2},
  'workspaces':{'cps:pilot':{'profile':'interactive-native-pilot-5'}}}
 enrollment={'version':1,'binding_id':'a'*60,'source':'cps','actor':'service:cps-hub','workspace':'pilot',
  'principal':'workspace:cps:pilot','members':['person:one'],'attempt':'22222222-2222-4222-8222-222222222222',
  'profile':'interactive-native-pilot-5','intent':f.intent.to_dict()}
 enrollment.update({k:getattr(f.intent,k) for k in ('policy_hash','namespace','name','node','node_uid','gpu_uuid','cap_mib')})
 cm={'apiVersion':'v1','kind':'ConfigMap','immutable':True,'metadata':{'namespace':'pilot',
  'name':'cps-native-enrollment-'+'a'*40,'uid':'44444444-4444-4444-8444-444444444444',
  'labels':{a.LABEL:'a'*60}},'data':{'enrollment.json':json.dumps(enrollment)}}
 envelope=a.validate_enrollment(cm,config,f.m)
 store=a.EnrollmentStore(f.state,f.m,trusted_uid=f.uid);store.synchronize([envelope])
 settings={'version':1,'namespace_uid':'55555555-5555-4555-8555-555555555555','host_root':'/host',
  'cdi_runtime_pins':{'version':1,'common_edits_sha256':'a'*64,'selected_filename':'selected.json',
   'other_cdi_files':{'other.json':'b'*64},'runtime_files':{'runtime.toml':'c'*64}}}
 guard=m.InventoryGuard(a,config,args,settings)
 # Preserve the real private-file validator, targeting the test user's files.
 # Runtime uses the unchanged default root UID; no runtime override is exposed.
 guard.back=SimpleNamespace(**vars(a._installed_backend))
 guard.back.private_directory=lambda path:a._installed_backend.private_directory(path,f.uid)
 objects={cm['metadata']['name']:cm}
 class API:
  def call(self,method,url):
   assert method=='GET'
   return {'metadata':{'uid':settings['namespace_uid'] if url.endswith('/pilot') else c.NS_UID}}
  def configmap(self,namespace,name):assert namespace=='pilot';return objects.get(name)
 guard.kube=API()
 get_pod=lambda i:f.pod if i.pod_uid==f.intent.pod_uid else None
 cls=guard.backend_type()
 backend=cls(f.m,f.manual,intents=[f.intent],driver=f.driver,get_pod=get_pod,get_node=f.backend.get_node,
  get_cri=f.backend.get_cri,delete_pod=f.backend.delete_pod,gpu_clients=f.backend.gpu_clients,health=f.backend.health,
  proc_root=f.proc,cgroup_root=f.cg,state_root=f.state,trusted_uid=f.uid)
 guard.check(backend)
 def driver_changed():
  current_row.update(soft=f.driver.value['soft'],hard=f.driver.value['hard'],used=f.driver.value['used'])
  physical['entries']=[prior_row,current_row];physical_write()
 f.driver.after_set=driver_changed
 controller=f.m.NativeCapController(backend,f.journal,enabled=True)
 record=controller.reconcile(f.intent)
 assert record.state=='sealed' and f.backend.read_gate(record.identity) is not None
 writes=list(f.driver.writes)
 foreign=copy.deepcopy(current_row);foreign.update(cgroup_id=inode+1,kernfs_id=inode+1,inode=inode+1)
 physical['entries'].append(foreign);physical_write()
 try:backend.set_limit(record.identity,record.limit)
 except ValueError:pass
 else:raise AssertionError('Unknown full-inventory parent permitted SET')
 assert f.driver.writes==writes
 physical['entries'].pop();physical_write()
 f.stop();f.pod=None;shutil.rmtree(f.group);current_row['offline']=True
 if sys.argv[3]=='unlimited':
  record=replace(record,state='cleanup-prepared');f.journal.write(record)
  (f.state/'receipts'/f'{f.intent.pod_uid}.json').unlink()
  current_row.update(soft=0,hard=f.m.MAX_LIMIT)
 physical['entries'][1]=current_row;physical_write()
 controller=f.m.NativeCapController(backend,f.journal,enabled=True)
 terminal=controller.cleanup(f.intent)
 assert terminal.state==('cleanup-offline-unlimited' if sys.argv[3]=='unlimited' else 'retired-inert-cap')
 f.clients={12345}  # Existing completed-terminal proof is target-specific.
 replacement={'apiVersion':'v1','kind':'Pod','metadata':{'namespace':f.intent.namespace,'name':f.intent.name,
  'uid':'77777777-7777-4777-8777-777777777777'}}
 f.pod=replacement
 try:guard.check(backend)
 except ValueError:pass
 else:raise AssertionError('Unpublished terminal used replacement shortcut')
 f.pod=None
 receipt=a.cleanup_receipt(envelope,terminal,backend,None,f.m)
 receipt['metadata']['uid']='66666666-6666-4666-8666-666666666666'
 objects[receipt['metadata']['name']]=receipt
 store.mark_cleanup_published(f.intent.pod_uid,envelope,receipt,terminal)
 f.pod=replacement;guard.check(backend)
 assert backend.get_pod(f.intent) is replacement
 for fault in ('same','namespace','name','missing','tombstone','entry'):
  f.pod=copy.deepcopy(replacement)
  if fault=='same':f.pod['metadata']['uid']=f.intent.pod_uid
  if fault=='namespace':f.pod['metadata']['namespace']='foreign'
  if fault=='name':f.pod['metadata']['name']='foreign'
  if fault=='missing':f.pod['metadata'].pop('uid')
  if fault=='tombstone':receipt['metadata']['uid']='88888888-8888-4888-8888-888888888888'
  if fault=='entry':physical['entries'][1]['used']=1;physical_write()
  try:guard.check(backend)
  except ValueError:pass
  else:raise AssertionError('Original published proof mutation accepted: '+fault)
  receipt['metadata']['uid']='66666666-6666-4666-8666-666666666666'
  physical['entries'][1]['used']=0;physical_write()
 assert f.driver.writes==writes
finally:f.doCleanups();old.doCleanups()
'''
    import os
    env = {**os.environ, 'PYTHONPATH': str(SDK.parent) + ':' + str(SDK.parent.parent / 'tests')}
    result = subprocess.run([sys.executable, '-B', '-c', program,
        str(HERE / 'prepare_plain_node_agent.py'), str(SDK), completion], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
