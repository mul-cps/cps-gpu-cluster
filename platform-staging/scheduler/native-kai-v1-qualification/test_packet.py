import copy
import importlib.util
import json
from pathlib import Path
import pytest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('kai_packet', HERE / 'packet.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
BASE = HERE.parents[1] / 'gpu/native-group-pilot/qualification/cpu-runner-policy-20261012'
PRIVATE = HERE

def inputs():
    return [json.loads((BASE / 'catalog.json').read_text()),
            json.loads((PRIVATE / 'node-config-before.json').read_text()),
            json.loads((BASE / 'cit-settings.json').read_text())]


def test_one_disabled_ten_profile_normal_compiler_and_real_authority():
    from cps_compute.policy import Policy, PolicyError
    from cps_compute.native_qualification import NativeGroupQualification
    result = m.render(*inputs())
    p = Policy(result['policy.json'])
    mode = NativeGroupQualification.from_config(result['operator-qualification.json'], p)
    assert set(mode.profiles) == {m.PROFILE}
    assert set(mode.workspaces) == {'cit:native-group-a'}
    assert mode.cap_mib(m.PROFILE) == 10240
    assert p.native_pilot_resources(m.PROFILE) == {'cpu': '4', 'memory': '16Gi'}
    with pytest.raises(PolicyError): p.resources(m.PROFILE)
    assert all(not x['enabled'] for x in p.catalog['profiles'].values() if x['gpu']['mode'] != 'none')
    assert result['node-config.json']['version'] == 2
    assert result['node-config.json']['mode'] == 'operator-qualification'
    assert result['node-config.json']['terminal_history'] == inputs()[1]['terminal_history']
    assert result['hub-pending.json']['qualificationHub']['owners'] == ['citnativegroupa']
    assert result['gateway-runtime-overlay.json']['nativeGroupApprovals'] == {'enabled': False}


@pytest.mark.parametrize('field', ['owner', 'members', 'ceiling', 'profiles', 'storage'])
def test_foreign_approval_does_not_emit_packet(field):
    args = inputs(); row = args[2]['groupDeployment']['workspaces']['cit:native-group-a']
    row[field] = 'foreign'
    with pytest.raises(ValueError): m.render(*args)


def test_v2_enabling_or_different_epoch_cannot_be_relabelled():
    args = inputs(); args[0]['gpuQualification']['qualified'] = True
    with pytest.raises(ValueError): m.render(*args)
    args = inputs(); args[1]['pool']['driver_generation'] = '00000000-0000-0000-0000-000000000001'
    with pytest.raises(ValueError): m.render(*args)


def test_normal_close_even_unknown_start_or_failed_witness_and_hold_on_cleanup_failure():
    class Backend:
        def __init__(self): self.ops=[]
        def start(self): self.ops.append('start'); raise TimeoutError('unknown CREATE')
        def close(self): self.ops.append('normal-source-close')
        def terminal(self): self.ops.append('genuine-terminal'); return {k: True for k in ['clean','native_zero','exact_pod_absent','maps_absent','ledger_released','member_reservations_zero','custody_clean','reservation_absent','shares_closed']}
    b=Backend()
    with pytest.raises(TimeoutError): m.run_lifecycle(b)
    assert b.ops == ['start', 'normal-source-close', 'genuine-terminal']
    b=Backend(); b.close=lambda: (_ for _ in ()).throw(RuntimeError('held'))
    with pytest.raises(m.CustodyHeld): m.run_lifecycle(b)


def test_incomplete_cap_or_epoch_proof_fails_and_does_not_restore():
    for x in [{}, {'clean': False}, {'clean': True, 'native_zero': False}]:
        with pytest.raises(ValueError): m.validate_terminal(x)


def fresh_source():
    proposal=m.render(*inputs())['registration-proposal.json']
    old=copy.deepcopy(proposal);old['profiles']=['interactive-shared-10'];old['policy_hash']='sha256:'+m.CATALOG_SHA;old['storage']['state']='active'
    w={'id':'native-group-a','source':'local','state':'stopped','profile':'interactive-shared-10','hub_user':old['owner'],
       'course_ceiling':old['ceiling'],**{k:old[k] for k in ['course_id','term_id','group_id','namespace','pod']}}
    c={'id':old['course_id'],'source':'local','resource_ceiling':old['ceiling']}
    members=[{'id':'member-'+str(i),'source':'local','role':'student','group_id':w['group_id'],
              'person_id':'citgpumember'+chr(97+i),'canonical_person_id':person} for i,person in enumerate(old['members'])]
    records={'workspaces':[w], 'courses':[c], 'memberships':members}
    grants={person:[{'id':'owned-'+str(i),'source':'cit','person':person,'allowance':1,'profiles':['interactive-cpu','interactive-shared-10'],
                    'starts':'2026-10-14T00:00:00+00:00','expires':'2026-10-14T06:00:00+00:00','projects':[],'reason':'existing'}] for i,person in enumerate(old['members'])}
    return {'actor_model':{'name':'akadmin','admin':True},'records':records,'all_records':copy.deepcopy(records),
            'grants':grants,'people':{r['person_id']:r['canonical_person_id'] for r in members},'aliases':{},'servers':[]},old,proposal


def test_exact_normal_http_profile_and_existing_grants_preserve_windows_ids_and_ceiling():
    before,old,proposal=fresh_source();result=m.source_delta(before,old,proposal)
    assert [x['path'] for x in result['http_mutations']]==['compute','compute','workspaces/native-group-a/profile']
    assert result['http_mutations'][-1]['body']=={'profile':m.PROFILE}
    assert all('source' not in x['body'] for x in result['http_mutations'])
    for op in result['operations'][:2]:
        assert {k:v for k,v in op['previous'].items() if k!='profiles'}=={k:v for k,v in op['current'].items() if k!='profiles'}
    assert result['expected_registration']['storage']==old['storage']
    assert all(op['audit_required'] and op['full_readback_required'] for op in result['operations'])


@pytest.mark.parametrize('damage',['admin','member','allowance','owner','storage','running','pending'])
def test_foreign_uncertain_or_enlarged_source_preimage_denies(damage):
    before,old,p=fresh_source()
    if damage=='admin':before['actor_model']['admin']=False
    elif damage=='member':before['records']['memberships'][0]['canonical_person_id']='foreign'
    elif damage=='allowance':before['grants'][p['members'][0]][0]['allowance']=2
    elif damage=='owner':old['owner']='foreign'
    elif damage=='storage':old['storage']['state']='unknown'
    elif damage=='running':before['records']['workspaces'][0]['state']='running'
    else:before['records']['workspaces'][0]['archive_pending']=True
    with pytest.raises(ValueError):m.source_delta(before,old,p)


def test_all_executors_are_really_inert_before_env_credentials_api_or_gpu(tmp_path):
    import os,subprocess,sys
    env={k:v for k,v in os.environ.items() if not k.startswith('CPS_')};env['HOME']=str(tmp_path)
    for name in ['packet.py','observe_node.py','gateway_observer.py','execute_source.py']:
        r=subprocess.run([sys.executable,str(HERE/name)],env=env,capture_output=True,text=True,timeout=5)
        assert r.returncode==0, r.stderr
        value=json.loads(r.stdout);assert value['state']=='inert' and value['api_calls'] is False
    assert list(tmp_path.iterdir())==[]
