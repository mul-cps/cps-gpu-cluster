import copy, importlib.util
from pathlib import Path
import pytest
import os, subprocess, sys
P=Path(__file__).with_name('plain_lifecycle_pilot.py')
def module():
 s=importlib.util.spec_from_file_location('plain_lifecycle_pilot',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def inputs():
 from test_native_qualification import fixture
 p,c=fixture((5,10)); approvals=copy.deepcopy(c['workspaces'])
 for v in approvals.values():
  v['profiles']=['interactive-shared-5'];v['ceiling']['gpuMemoryGiB']=5
 hubs={s:{'policyPath':'/reviewed/policy.json','gatewayUrl':'https://gateway.example','gatewayCAFile':'/reviewed/ca.crt','serviceTokenEnv':'NATIVE_TOKEN','canonicalMappingPath':'/reviewed/people.json'} for s in ('cps','cit')}
 return dict(policy=p,approvals=approvals,pool={k:c['node_pool'][k] for k in ('node','node_uid','gpu_uuid','max_workspaces')},authority_namespace='cps-native-lifecycle-147',gate_image=c['gateImage'],workload_image=c['workloadImage'],hub_transports=hubs,database_paths={'store':'/data/control.sqlite','reservations':'/data/reservations.sqlite'})

def contract_positive():
 from cps_compute.policy import Policy,PolicyError
 a=inputs();before=copy.deepcopy(a['policy'].catalog);r=module().build(**a);p=Policy(r['policy']);name=r['profile']
 assert p.hash!=a['policy'].hash and a['policy'].catalog==before
 assert p.native_pilot_resources(name)=={'cpu':'4','memory':'16Gi'}
 with pytest.raises(PolicyError):p.resources(name)
 assert r['node']['version']==1 and r['node']['policy_hash']==p.hash and len(r['node']['workspaces'])==2
 from cps_compute.native_gpu_control import NativeGpuAuthority
 NativeGpuAuthority(p,object(),object(),type('Durable',(),{'durable':True})(),**r['authority'],authorize_workspace=lambda *a:None)
 from cps_compute_hub.native_hub_config import _validate
 for s,h in r['hubs'].items():
  _validate(h);assert h['source']==s and h['profiles']==[name]
 assert r['database_paths']==a['database_paths'] and r['production_qualified'] is False
 assert r['source_registry_update'] is None
 from cps_compute.runtime import native_gpu_pilot_configuration
 assert r['runtime']['state_directory']=='/data'
 assert native_gpu_pilot_configuration(r['runtime'])==r['runtime']['nativeGpuPilot']
 # qa path is qualification/unequal; legacy sibling is gpu/native-group-pilot.
 legacy=P.parents[2]/'native-group-pilot'/'node_agent.py'
 spec=importlib.util.spec_from_file_location('legacy_pilot_validator',legacy)
 agent=importlib.util.module_from_spec(spec);spec.loader.exec_module(agent)
 assert agent.validate_config(r['node'])==r['node']
 unchanged=copy.deepcopy(r['policy']);unchanged.pop('policyHash');unchanged['profiles'].pop(name)
 original=copy.deepcopy(before);original.pop('policyHash',None)
 assert unchanged==original

def contract_negative(fault):
 from cps_compute.policy import Policy
 a=inputs();rows=list(a['approvals'].values())
 if fault=='one':a['approvals'].pop(next(iter(a['approvals'])))
 if fault=='duplicate-owner':rows[1]['owner']=rows[0]['owner']
 if fault=='overlap-member':rows[1]['members']=rows[0]['members']
 if fault=='pool':a['pool']['max_workspaces']=3
 if fault=='image':a['workload_image']='image:latest'
 if fault=='namespace':a['authority_namespace']='jupyterhub'
 if fault=='production-namespace':a['authority_namespace']='cps-native-runtime'
 if fault=='wrong-basename':a['database_paths']['store']='/data/hub.db'
 if fault=='db':a['database_paths']['store']='/tmp/fake.db'
 if fault=='extra':rows[0]['fake']=True
 if fault=='enabled-alias':
  raw=copy.deepcopy(a['policy'].catalog);raw.pop('policyHash',None);raw['profiles']['interactive-native-pilot-5']={'enabled':True};a['policy']=Policy(raw)
 with pytest.raises(ValueError):module().build(**a)

SDK=Path('/home/bjoern/git/cps-compute-worktrees/native-cleanup-offline-unlimited-20261023')
PYTHON=Path('/home/bjoern/git/cps-compute/.venv/bin/python')

@pytest.mark.parametrize('case',['positive','one','duplicate-owner','overlap-member','pool','image','namespace','db','extra','enabled-alias','production-namespace','wrong-basename'])
def test_isolated_sdk_contract(case):
 # Parent imports neither SDK nor its fixtures, preserving pinned harness imports.
 env=dict(os.environ)
 env['PYTHONPATH']=os.pathsep.join(str(SDK/p) for p in ('src','tests','packages/hub/src'))
 command="import runpy,sys; d=runpy.run_path(sys.argv[1]); d['contract_positive']() if sys.argv[2]=='positive' else d['contract_negative'](sys.argv[2])"
 result=subprocess.run([str(PYTHON),'-B','-c',command,str(Path(__file__).resolve()),case],
                       env=env,capture_output=True,text=True,timeout=30)
 assert result.returncode==0,result.stdout+result.stderr
