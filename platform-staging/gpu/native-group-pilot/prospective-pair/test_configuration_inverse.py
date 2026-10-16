"""CPU-only two fresh CPS lifetimes; no cluster, driver or secret operations."""
import copy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import uuid
from unittest.mock import patch

import pytest

HERE = Path(__file__).parent
sys.path.insert(0,str(HERE.parent))
import test_node_agent as legacy
import terminal_policy_proposal as terminal
import qualification_configuration_inverse as custody
from test_node_successor import fixture as node_fixture, successor, BASE
from test_node_epoch_successor import EPOCH

HERE = Path(__file__).parent
uid = lambda n: str(uuid.UUID(int=n))
raw = lambda v: json.dumps(v, sort_keys=True, separators=(',', ':')).encode()
pin = lambda v: hashlib.sha256(v).hexdigest()


def module():
    path = HERE / 'configuration_inverse.py'
    assert path.exists(), 'Finite prospective CPS pair terminal inverse is required'
    spec = importlib.util.spec_from_file_location('prospective_pair_inverse', path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def fixture(retained=True):
    current, _, _, _, contract = node_fixture()
    current['terminal_history'] = {}
    contract['terminal_history_sha256'] = terminal.agent.canonical_sha256({})
    original = copy.deepcopy(current)
    original.update(mode='qualified-group', policy_hash='sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0',
        workspaces={'cps:native-group-b': {'profile': 'interactive-shared-5', 'cap_mib': 5120},
                    'cit:native-group-a': {'profile': 'interactive-shared-10', 'cap_mib': 10240}})
    original['pool']['memory_budget_mib'] = 15360
    original['pool'].update(boot_id='209f8bc9-a478-48e4-925a-6e07ffa56f7a', driver_generation='e148263b-805d-4ccd-857c-84a03d4f4229')
    current['pool'].update(boot_id=original['pool']['boot_id'], driver_generation=original['pool']['driver_generation'])
    config_cm = lambda n, body: dict(apiVersion='v1', kind='ConfigMap', immutable=True,
        metadata=dict(namespace=body['authority_namespace'], name='cps-native-node-qualification-'+str(n), uid=uid(n), resourceVersion='2'),
        data={'config.json': terminal.canonical(body)})
    original_cm, current_cm = config_cm(500, original), config_cm(501, current)
    directories = {k: {'ownerUid': 0, 'mode': 0o700, 'records': {}} for k in ('enrollments', 'intents', 'journal')}
    authority = {'authority_maps': {'apiVersion': 'v1', 'kind': 'ConfigMapList', 'metadata': {'resourceVersion': '3'}, 'items': []},
        'host_snapshot': {'node': current['pool']['node'], 'nodeUid': current['pool']['node_uid'],
            'bootId': current['pool']['boot_id'], 'driverGeneration': current['pool']['driver_generation'], 'directories': directories}}
    ledger = dict(apiVersion='v1', kind='ConfigMap', metadata=dict(namespace=current['authority_namespace'],
        name='cps-native-gpu-allocations', uid=uid(502), resourceVersion='4'), data={'state.json': terminal.canonical({'version': 1, 'allocations': {}})})
    history = dict(version=2, protocol='synthetic', controller_sha256='sha256:'+'1'*64, recovery=None, records=[],
        **{k: current['pool'][k] for k in ('node','node_uid','gpu_uuid','boot_id','driver_generation')})
    physical = dict(kind='native-group-host-observation', observed_at_ns=1, inventory_sha256='sha256:'+'2'*64,
        targets=[], retired_caps=[], **custody.PHYSICAL_PINS,
        **{k: current['pool'][k] for k in ('node','node_uid','gpu_uuid','boot_id','driver_generation')})
    baseline = dict(authority=copy.deepcopy(authority), ledger=copy.deepcopy(ledger), history=copy.deepcopy(history), physical=copy.deepcopy(physical))
    claims = []
    plans = list(contract['workspaces'].items())
    if retained: plans.insert(0, ('cps:native-group-b', original['workspaces']['cps:native-group-b']))
    for index, (scope, profile) in enumerate(plans, 1):
        historical = scope == 'cps:native-group-b'
        person = [uid(9003)] if historical else contract['operator_members'][scope]
        f = legacy.TerminalHistoryTest(); f.setUp(); f.config = copy.deepcopy(original if historical else current)
        f.enrollment.update(source='cps', actor='service:cps-hub', workspace=scope.split(':',1)[1], principal='workspace:'+scope,
            members=person, group_id='operator-group-'+str(index), ceiling={'cpu':'4','memory':'16Gi','gpuMemoryGiB':profile['cap_mib']//1024},
            attempt=uid(600+index), profile=profile['profile'], policy_hash=f.config['policy_hash'], cap_mib=profile['cap_mib'], name='jupyter-operator-'+str(index))
        f.enrollment['intent'].update(pod_uid=uid(700+index), policy_hash=f.config['policy_hash'], cap_mib=profile['cap_mib'], name=f.enrollment['name'])
        extra_claim = {k:f.enrollment.pop(k) for k in ('group_id','ceiling')}
        identity = dict({k:v for k,v in f.enrollment.items() if k not in {'version','binding_id','intent'}}, **extra_claim)
        binding = pin(raw(identity))[:60]; f.enrollment['binding_id'] = binding
        f.cm['metadata'].update(namespace=current['authority_namespace'], name='cps-native-enrollment-'+binding[:40], uid=uid(800+index), labels={'cps.compute/native-binding':binding})
        f.cm['data']['enrollment.json'] = terminal.canonical(f.enrollment)
        original_builder = f.agent_cleanup_fixture
        def distinct(*args, _builder=original_builder, _index=index):
            backend, record = _builder(*args)
            return backend, replace(record, identity=replace(record.identity, cgroup_inode=71+_index))
        f.agent_cleanup_fixture = distinct
        with patch.object(legacy, 'POD', uid(700+index)), patch.object(legacy, 'BINDING', binding), tempfile.TemporaryDirectory() as tmp:
            values = f.completed(Path(tmp), retired=True)
            maps, records = values[4:6]
            for name in ('enrollments','intents'):
                for path in (Path(tmp)/name).glob('*.json'):
                    directories[name]['records'][path.name] = dict(uid=0, mode=0o600, nlink=1, rawSha256=terminal.raw_sha(path.read_bytes()), value=json.loads(path.read_text()))
            record = records[uid(700+index)]; body = record.to_dict(); digest = terminal.raw_sha((terminal.canonical(body)+'\n').encode())
            directories['journal']['records'][record.intent.pod_uid+'.json'] = dict(uid=0,mode=0o600,nlink=1,rawSha256=digest,value=body)
            history['records'].append(dict(pod_uid=record.intent.pod_uid,journal_sha256=digest,record=body))
            physical['retired_caps'].append(dict(pod_uid=record.intent.pod_uid,identity=body['identity'],inventory_row=body['retirement']['entry'],journal_sha256=digest,retirement=body['retirement']))
            authority['authority_maps']['items'].extend(copy.deepcopy(cm) for name,cm in maps.items() if name!='cps-native-gpu-allocations')
            state=json.loads(ledger['data']['state.json']); state['allocations'].update({b:dict(r,**extra_claim) for b,r in json.loads(maps['cps-native-gpu-allocations']['data']['state.json'])['allocations'].items()})
            ledger['data']['state.json']=terminal.canonical(state)
        if historical:
            baseline = dict(authority=copy.deepcopy(authority),ledger=copy.deepcopy(ledger),history=copy.deepcopy(history),physical=copy.deepcopy(physical))
            current['terminal_history'] = terminal.map_history(authority,ledger,original)
            contract['terminal_history_sha256'] = terminal.agent.canonical_sha256(current['terminal_history'])
        else:
            claims.append({k:copy.deepcopy(identity[k]) for k in custody.IDENTITY})
    final = dict(authority=authority,ledger=ledger,history=history,physical=physical,pods=dict(apiVersion='v1',kind='PodList',metadata={},items=[]))
    current_cm['data']['config.json'] = terminal.canonical(current)
    approval = dict(version=1, original_data_sha256=terminal.agent.canonical_sha256(original_cm['data']),
        current_data_sha256=terminal.agent.canonical_sha256(current_cm['data']),
        baseline_ledger_sha256=pin(baseline['ledger']['data']['state.json'].encode()), claims=claims)
    return dict(original=original_cm,current=current_cm,baseline=baseline,final=final,contract_raw=raw(contract),contract_sha256=pin(raw(contract)),
                approval_raw=raw(approval),approval_sha256=pin(raw(approval)), original_node_source=BASE, original_epoch_source=EPOCH, now_ns=2)


def test_fresh_cps_pair_restores_original_node_without_discarding_terminal_authority():
    inputs=fixture(); before=copy.deepcopy(inputs)
    result=module().derive_node_inverse(**inputs)
    old=json.loads(inputs['original']['data']['config.json']); restored=copy.deepcopy(result['node-config.json'])
    assert len(restored['terminal_history'])==2
    restored['terminal_history']=old['terminal_history']; assert restored==old
    assert len(result['full-terminal-authority-archive.json'])==3
    assert result['hardware_qualified'] is result['live_applied'] is result['enabled'] is False
    assert inputs==before


@pytest.mark.parametrize('fault', ['raw-pin','approval-policy','missing-old-ledger','missing-cleanup',
    'missing-journal','missing-old-history','charged-physical','stale-physical','live-pod',
    'replacement-pod','paginated-pods','extra-claim','unreleased','wrong-person','source-bytes'])
def test_incomplete_or_changed_pair_custody_never_produces_inverse(fault):
    inputs=fixture()
    from cps_compute.native_gpu_control import NativeAuthorityError
    approval=json.loads(inputs['approval_raw']); final=inputs['final']
    if fault=='raw-pin': inputs['approval_sha256']='0'*64
    elif fault=='approval-policy':
        approval['claims'][0]['policy_hash']='sha256:'+'b'*64
        inputs['approval_raw']=raw(approval); inputs['approval_sha256']=pin(inputs['approval_raw'])
    elif fault in ('missing-old-ledger','extra-claim','unreleased','wrong-person'):
        state=json.loads(final['ledger']['data']['state.json']); rows=state['allocations']
        first=next(iter(rows))
        if fault=='missing-old-ledger': rows.pop(first)
        elif fault=='extra-claim': rows['a'*60]=copy.deepcopy(rows[first])
        elif fault=='unreleased': next(reversed(rows.values()))['state']='enrolled'
        else: next(reversed(rows.values()))['members']=[uid(9999)]
        final['ledger']['data']['state.json']=terminal.canonical(state)
    elif fault=='missing-cleanup':
        final['authority']['authority_maps']['items']=[c for c in final['authority']['authority_maps']['items'] if 'receipt.json' not in c['data']]
    elif fault=='missing-journal': final['authority']['host_snapshot']['directories']['journal']['records'].popitem()
    elif fault=='missing-old-history': final['history']['records'].pop(0)
    elif fault=='charged-physical': final['physical']['retired_caps'][-1]['inventory_row']['used']=1
    elif fault=='stale-physical': inputs['now_ns']=60_000_000_002
    elif fault in ('live-pod','replacement-pod'):
        state=json.loads(final['ledger']['data']['state.json']); r=next(r for r in state['allocations'].values() if r['workspace'].startswith('operator-qualification-531-'))
        final['pods']['items']=[{'metadata':{'namespace':r['namespace'],'name':r['name'],
            'uid':r['intent']['pod_uid'] if fault=='live-pod' else uid(9999)}}]
    elif fault=='paginated-pods': final['pods']['metadata']['continue']='more'
    else: inputs['original_node_source']+=b'\n'
    with pytest.raises((ValueError,NativeAuthorityError)): module().derive_node_inverse(**inputs)


def test_empty_retained_baseline_is_supported_without_manufacturing_old_claims():
    result=module().derive_node_inverse(**fixture(retained=False))
    assert len(result['full-terminal-authority-archive.json'])==2


def handover_fixture():
    inputs=fixture()
    import node_successor
    bundle=node_successor.successor_bundle(BASE,EPOCH,inputs['contract_raw'],inputs['contract_sha256'])
    cm=lambda name, ident, data:dict(apiVersion='v1',kind='ConfigMap',immutable=True,
        metadata=dict(namespace='cps-native-system',name=name,uid=uid(ident),resourceVersion='3'),data=data)
    oldcode=cm('cps-native-node-code-original',901,dict(**{'node_agent.py':BASE.decode(),'native_operator_epoch.py':EPOCH.decode()},unchanged_helper='exact'))
    newcode=cm('cps-native-node-code-prospective',902,dict(oldcode['data'],**bundle))
    old=dict(apiVersion='apps/v1',kind='Deployment',metadata=dict(namespace='cps-native-system',name='native-node',uid=uid(903),resourceVersion='4'),
        spec=dict(replicas=1,template=dict(metadata={'labels':{'app':'native-node'}},spec=dict(
            containers=[dict(name='node',image='registry.example/node@sha256:'+'f'*64)],
            volumes=[dict(name='code',configMap={'name':oldcode['metadata']['name']}),
                     dict(name='node-config',configMap={'name':inputs['original']['metadata']['name']})]))))
    current=copy.deepcopy(old);current['metadata']['resourceVersion']='5'
    current['spec']['template']['spec']['volumes'][0]['configMap']['name']=newcode['metadata']['name']
    current['spec']['template']['spec']['volumes'][1]['configMap']['name']=inputs['current']['metadata']['name']
    return dict(terminal_inputs=inputs,original_deployment=old,current_deployment=current,original_code=oldcode,current_code=newcode)


def test_node_deployment_inverse_retains_reviewed_code_and_restores_only_configuration():
    args=handover_fixture(); tool=module()
    assert hasattr(tool,'derive_node_handover_inverse'), 'Finite Node deployment inverse required'
    result=tool.derive_node_handover_inverse(**args)
    patch=result['node-deployment.patch.json']
    assert [op['op'] for op in patch]==['test','test','test','replace']
    assert patch[0]['value']==args['current_deployment']['metadata']['uid']
    assert patch[1]['value']=='5'
    assert patch[2]['value']==args['current_deployment']['spec']
    desired=patch[-1]['value']['template']['spec']
    assert desired['containers']==args['original_deployment']['spec']['template']['spec']['containers']
    assert desired['volumes'][0]['configMap']['name']==args['current_code']['metadata']['name']
    assert desired['volumes'][1]['configMap']['name']==result['node-configmap.json']['metadata']['name']


@pytest.mark.parametrize('fault',['original-namespace','original-zero-uid','current-zero-uid'])
def test_original_and_current_configurations_require_actual_owned_metadata(fault):
    args=fixture()
    if fault=='original-namespace': args['original']['metadata']['namespace']='foreign'
    else: args['original' if fault=='original-zero-uid' else 'current']['metadata']['uid']=uid(0)
    with pytest.raises(ValueError): module().derive_node_inverse(**args)


@pytest.mark.parametrize('fault',['image','uid','code','mount','config','nonimmutable'])
def test_node_handover_rejects_drift_outside_exact_two_reference_changes(fault):
    args=handover_fixture()
    if fault=='image': args['current_deployment']['spec']['template']['spec']['containers'][0]['image']='foreign'
    elif fault=='uid': args['current_deployment']['metadata']['uid']=uid(9999)
    elif fault=='code': args['current_code']['data']['unchanged_helper']+='changed'
    elif fault=='mount': args['current_deployment']['spec']['template']['spec']['volumes'].append({'name':'foreign','hostPath':{'path':'/'}})
    elif fault=='config': args['current_deployment']['spec']['template']['spec']['volumes'][1]['configMap']['name']='foreign'
    else: args['current_code']['immutable']=False
    with pytest.raises(ValueError): module().derive_node_handover_inverse(**args)


def unstarted_fixture():
    args=fixture()
    args['final']={k:copy.deepcopy(v) for k,v in args['baseline'].items()}
    args['final']['physical']['observed_at_ns']=2
    args['final']['pods']=dict(apiVersion='v1',kind='PodList',metadata={},items=[])
    return args


def test_unstarted_inverse_restores_exact_original_without_inventing_pair_lifetimes():
    args=unstarted_fixture();inverse=module()
    assert hasattr(inverse,'derive_unstarted_node_inverse'), 'Pre-start pair unwind is required'
    result=inverse.derive_unstarted_node_inverse(**args)
    assert result['node-config.json']==json.loads(args['original']['data']['config.json'])
    assert len(result['full-terminal-authority-archive.json'])==1
    assert result['live_applied'] is result['hardware_qualified'] is False


def test_unstarted_inverse_cannot_be_used_after_either_new_claim_exists():
    args=fixture();inverse=module()
    assert hasattr(inverse,'derive_unstarted_node_inverse'), 'Pre-start pair unwind is required'
    with pytest.raises(ValueError): inverse.derive_unstarted_node_inverse(**args)


def partial_fixture():
    args=fixture();final=args['final'];state=json.loads(final['ledger']['data']['state.json'])
    binding,row=next((b,r) for b,r in state['allocations'].items() if r['workspace'].startswith('operator-qualification-531-') and r['cap_mib']==20480)
    pod_uid=row['intent']['pod_uid'];state['allocations'].pop(binding)
    final['ledger']['data']['state.json']=terminal.canonical(state)
    final['authority']['authority_maps']['items']=[c for c in final['authority']['authority_maps']['items'] if c['metadata']['name'] not in ('cps-native-enrollment-'+binding[:40],'cps-native-cleanup-'+binding[:40])]
    for directory in final['authority']['host_snapshot']['directories'].values(): directory['records'].pop(pod_uid+'.json')
    final['history']['records']=[r for r in final['history']['records'] if r['pod_uid']!=pod_uid]
    final['physical']['retired_caps']=[r for r in final['physical']['retired_caps'] if r['pod_uid']!=pod_uid]
    return args


def test_partial_start_failure_can_restore_after_the_one_started_peer_is_released():
    args=partial_fixture();inverse=module()
    assert hasattr(inverse,'derive_partial_node_inverse'), 'Single-peer failure inverse is required'
    result=inverse.derive_partial_node_inverse(**args)
    assert len(result['node-config.json']['terminal_history'])==1
    assert len(result['full-terminal-authority-archive.json'])==2
    with pytest.raises(ValueError): inverse.derive_unstarted_node_inverse(**args)
    with pytest.raises(ValueError): inverse.derive_node_inverse(**args)


@pytest.mark.parametrize('phase',['unstarted','partial'])
def test_node_deployment_inverse_supports_both_failure_phases(phase):
    args=handover_fixture();args['terminal_inputs']=unstarted_fixture() if phase=='unstarted' else partial_fixture()
    result=module().derive_node_handover_inverse(phase=phase,**args)
    code=result['node-deployment.patch.json'][-1]['value']['template']['spec']['volumes'][0]['configMap']['name']
    assert code==args['original_code' if phase=='unstarted' else 'current_code']['metadata']['name']
    assert result['restoration_phase']==phase
