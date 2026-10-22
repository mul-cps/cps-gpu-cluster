import importlib.util
from pathlib import Path
HERE=Path(__file__).parent

def module():
 spec=importlib.util.spec_from_file_location('packaged_cleanup',HERE/'prepare_packaged_cleanup.py')
 value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

def test_preparation_exists():
 assert callable(module().build_sources)

import hashlib,os,subprocess,sys,json
import pytest
COHORT='3b217fe8-5750-4ead-954a-09286afd7d3f'

def test_exact_sources_new_bundle_and_dependent_observer_pin():
 m=module();new=m.build_sources(COHORT)
 old=m.load('prepare_packaged_gate.py',(HERE/'prepare_packaged_gate.py').read_bytes()).build_sources(COHORT)
 assert {n for n in new if new[n]!=old[n]}=={'controller.py','observe.py'}
 assert m.sha(new['controller.py']).encode() in new['observe.py']
 assert all(m.sha(raw)==m.PINS[n] for n,raw in m.bundle_sources().items())
 for name,raw in new.items():compile(raw,name,'exec')

def test_default_inert_has_no_source_access(monkeypatch,capsys):
 m=module();monkeypatch.setattr(m,'build_sources',lambda *a:pytest.fail('inert source access'))
 m.main([]);assert 'inert' in capsys.readouterr().out

@pytest.mark.parametrize('fault',['none','missing','usage','epoch','unknown-state','setter','peer-client'])
def test_real_protected_cleanup_record_and_fresh_backend_only(fault):
 # Separate interpreter prevents older fixture imports from replacing SDK768 types.
 program=r'''
import importlib.util,sys,shutil
from dataclasses import replace
from pathlib import Path
from test_native_node_backend import NodeBackendTests
p=Path(sys.argv[1]);spec=importlib.util.spec_from_file_location('prep',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
c=m.load('controller.py',m.build_sources(sys.argv[2])['controller.py'])
f=NodeBackendTests();f.setUp()
try:
 original=f.controller.reconcile(f.intent);original=replace(original,state='cleanup-prepared');f.journal.write(original)
 f.stop();f.pod=None;shutil.rmtree(f.group);(f.state/'receipts'/f'{f.intent.pod_uid}.json').unlink()
 f.retired_inventory(original,soft=0,hard=f.m.MAX_LIMIT)
 terminal=f.controller.cleanup(f.intent);assert terminal.state=='cleanup-offline-unlimited'
 old=m.load('old.py',m.load('prepare_packaged_gate.py',(p.parent/'prepare_packaged_gate.py').read_bytes()).build_sources(sys.argv[2])['controller.py'])
 try:old.verify_retirements(f.backend,f.journal,[terminal])
 except ValueError:pass
 else:raise AssertionError('Original finite-only observer accepted new terminal')
 writes=list(f.driver.writes);fault=sys.argv[3]
 if fault=='peer-client':f.backend.gpu_clients=lambda _: [12345]
 if fault=='none':f.backend.gpu_clients=lambda _: (_ for _ in ()).throw(ValueError('Readonly observer never cleans'))
 if fault=='missing':f.journal.path(f.intent.pod_uid).unlink()
 if fault=='usage':f.retired_inventory(original,soft=0,hard=f.m.MAX_LIMIT,used=1)
 if fault=='epoch':f.node['metadata']['uid']='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
 if fault=='unknown-state':
  f.journal.write(original);terminal=original
 if fault=='setter':
  actual=f.backend._inventory
  def attempts_set(*args):f.backend.set_limit(original.identity,original.limit);return actual(*args)
  f.backend._inventory=attempts_set
 try:rows=c.verify_retirements(f.backend,f.journal,[terminal])
 except ValueError:
  assert fault not in ('none','peer-client')
 else:
  assert fault in ('none','peer-client') and rows[terminal.identity.cgroup_inode]['soft']==0
  try:f.backend.set_limit(original.identity,original.limit)
  except ValueError:pass
  else:raise AssertionError('Prior observer retained SET capability')
 assert f.driver.writes==writes
finally:f.doCleanups()
'''
 env={**os.environ,'PYTHONPATH':'/home/bjoern/git/cps-compute-worktrees/native-cleanup-offline-unlimited-20261023/src:/home/bjoern/git/cps-compute-worktrees/native-cleanup-offline-unlimited-20261023/tests'}
 result=subprocess.run([sys.executable,'-B','-c',program,str(HERE/'prepare_packaged_cleanup.py'),COHORT,fault],env=env,capture_output=True,text=True)
 assert result.returncode==0,result.stderr

@pytest.mark.parametrize('fault',['none','retired-charge','retired-hard','active-overcap'])
def test_generated_observer_accounting_preserves_proven_unlimited_and_active_charge(fault):
 from copy import deepcopy
 from types import SimpleNamespace
 m=module();sources=m.build_sources(COHORT);source=sources['observe.py'].decode()
 start=source.index("        for row in normalized['entries']:")
 end=source.index('        require(processes==',start)
 block=source[start:end]
 import textwrap
 cap=5120*1048576
 retired={11:{'inode':11,'soft':0,'hard':(1<<64)-1,'used':0,'offline':True,'pinned':True,'default_hierarchy':True}}
 actual={'entries':[deepcopy(retired[11]),{'inode':22,'soft':cap,'hard':cap,'used':123},{'inode':33,'soft':2*cap,'hard':2*cap,'used':456}]}
 if fault=='retired-charge':actual['entries'][0]['used']=1
 if fault=='retired-hard':actual['entries'][0]['hard']-=1
 if fault=='active-overcap':actual['entries'][1]['used']=cap+1
 calls=[]
 def inventory(value,caps,*,retired,sealed):
  calls.append(value)
  assert sealed and value['entries'][0]==retired[11]
  assert [r['used'] for r in value['entries'][1:]]==[0,0]
 scope=dict(normalized=deepcopy(actual),actual=actual,caps={22:cap,33:2*cap},retired=retired,c=SimpleNamespace(inventory=inventory),require=m.require)
 if fault=='none':
  exec(textwrap.dedent(block),scope);assert len(calls)==1
  assert [r['used'] for r in actual['entries']]==[0,123,456]
 else:
  with pytest.raises(ValueError):exec(textwrap.dedent(block),scope)
