"""Exact CPS5+20 candidate leaves; synthetic inputs, no transport/hardware."""
import copy,hashlib,json
import pytest
import test_prospective531_proposal as single
import qualification_proposal as p
import prospective_source_qualification_workspace as source
from cps_compute.policy import Policy
from cps_compute.native_qualification import NativeGroupQualification


def pair_fixture():
    values=single.fixture();args,authority,first,closure=values
    second=copy.deepcopy(first);second['workspace']='operator-qualification-531-20'
    second['profile']='interactive-native-qualification-20';registration=second['registration']
    registration.update(workspace=second['workspace'],owner='cps-ws-'+'b'*32,pod='jupyter-cps-ws-'+'b'*32+'--rtc',
        principal='workspace:cps:'+second['workspace'],group_id='operator-531-peer',course_id='operator-531-peer',term_id='operator-531-peer')
    registration['storage'].update(pvc='operator-531-peer-pvc',pv='operator-531-peer-pv',path='/mnt/operator-531-peer')
    policy=Policy(args[0]['catalog']);registration['workspace_hash']=policy.owner_label('cps:'+second['workspace'])
    second['operator_members']=registration['members']=['c98fbadd-d9a0-4981-8d20-1ab58bb75745']
    peer_approval={k:copy.deepcopy(v) for k,v in registration.items() if k in single.APPROVAL_FIELDS}
    peer_approval['storage'].pop('state');args[0]['approvals']['cps:'+second['workspace']]=peer_approval
    return values,second


def render(values,second):
    return single.render(values,peer_target_snapshot_raw=single.raw(second),
        peer_target_snapshot_sha256=single.raw_sha(single.raw(second)))


def test_pair_is_exact_two_cps531_profiles_with_25gib_budget():
    values,second=pair_fixture();before=copy.deepcopy((values,second));result=render(values,second)
    mode=NativeGroupQualification.from_config(result['operator-qualification.json'],Policy(result['policy.json']))
    assert mode.profiles=={'interactive-native-qualification-5','interactive-native-qualification-20'}
    assert mode.node_pool['memory_budget_mib']==25600 and mode.node_pool['max_workspaces']==2
    assert {x['profiles'][0] for x in mode.workspaces.values()}==mode.profiles
    assert result['node-config.json']['terminal_history']==values[0][0]['terminal_history']
    assert result['acceptance.json']['hardware_qualified'] is result['acceptance.json']['live_applied'] is False
    assert (values,second)==before


@pytest.mark.parametrize('fault',['foreign','student','duplicate-workspace','duplicate-owner','duplicate-pod','duplicate-pvc','wrong-profile','mixed-source','missing-pin','missing-history','low-memory'])
def test_pair_rejects_unreviewed_or_mixed_targets(fault):
    values,second=pair_fixture()
    if fault=='foreign':second['source']='cit'
    elif fault=='student':second['operator_members']=second['registration']['members']=[next(iter(source.STUDENT_PEOPLE))]
    elif fault=='duplicate-workspace':second['workspace']=values[2]['workspace']
    elif fault=='duplicate-owner':second['registration']['owner']=values[2]['registration']['owner']
    elif fault=='duplicate-pod':second['registration']['pod']=values[2]['registration']['pod']
    elif fault=='duplicate-pvc':second['registration']['storage']['pvc']=values[2]['registration']['storage']['pvc']
    elif fault=='wrong-profile':second['profile']='interactive-native-qualification-10'
    elif fault=='mixed-source':second['source_instance']['pod_uid']='33333333-3333-4333-8333-333333333333'
    elif fault=='missing-history':values[0][0]['terminal_history'].clear()
    elif fault=='low-memory':
        observed=json.loads(values[0][1]);gpu=next(x for x in observed['gpus'] if x['uuid']==values[0][0]['node_config']['pool']['gpu_uuid'])
        gpu['memoryFreeBytes']=26623*1048576;gpu['memoryUsedBytes']=gpu['memoryTotalBytes']-gpu['memoryFreeBytes']
        values[0][1]=single.raw(observed)
    if fault=='missing-pin':
        with pytest.raises(ValueError):single.render(values,peer_target_snapshot_raw=single.raw(second))
    else:
        with pytest.raises(ValueError):render(values,second)


def test_source_pair_configuration_selects_each_exact_target():
    values,second=pair_fixture();result=render(values,second);old=Policy(values[0][0]['catalog']);policy=Policy(result['policy.json'])
    mode=NativeGroupQualification.from_config(result['operator-qualification.json'],policy);node=result['node-config.json']
    from datetime import datetime,timezone
    for target in [values[2],second]:target['observed_at']=datetime.now(timezone.utc).isoformat()
    for target in [values[2],second]:
        kwargs=dict(source_closure_sha256=target['source_closure_sha256'],current_authority_sha256=target['current_authority_sha256'],
            terminal_history_sha256=source.canonical_sha256(node['terminal_history']),peer_target=second if target is values[2] else values[2])
        expected=source.validate_configuration(target,old,policy,mode,node,**kwargs)
        assert expected['profiles']==[target['profile']]
        assert expected['ceiling']['gpuMemoryGiB']==(5 if target is values[2] else 20)


def test_source_pair_checks_peer_original_labels_before_lifecycle():
    from datetime import datetime,timezone
    values,peer=pair_fixture();result=render(values,peer);old=Policy(values[0][0]['catalog']);policy=Policy(result['policy.json'])
    mode=NativeGroupQualification.from_config(result['operator-qualification.json'],policy)
    first=values[2]
    for t in (first,peer):t['observed_at']=datetime.now(timezone.utc).isoformat()
    peer['registration']['workspace_hash']='unreviewed-peer-label'
    with pytest.raises(ValueError,match='Both original Source labels'):
        source.validate_configuration(first,old,policy,mode,result['node-config.json'],
            source_closure_sha256=first['source_closure_sha256'],current_authority_sha256=first['current_authority_sha256'],
            terminal_history_sha256=source.canonical_sha256(result['node-config.json']['terminal_history']),peer_target=peer)


def test_candidate20_uses_normal_source_start_with_own_profile_and_ceiling():
    import asyncio
    from datetime import datetime,timezone
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    values,target=pair_fixture();result=render(values,target);old=Policy(values[0][0]['catalog']);policy=Policy(result['policy.json'])
    mode=NativeGroupQualification.from_config(result['operator-qualification.json'],policy);peer=values[2]
    for t in (target,peer):t['observed_at']=datetime.now(timezone.utc).isoformat()
    expected=source.validate_configuration(target,old,policy,mode,result['node-config.json'],
        source_closure_sha256=target['source_closure_sha256'],current_authority_sha256=target['current_authority_sha256'],
        terminal_history_sha256=source.canonical_sha256(result['node-config.json']['terminal_history']),peer_target=peer)
    row={'id':target['workspace'],'source':'local','profile':target['profile'],'course_ceiling':expected['ceiling']}
    for dest,key in [('course_id','course_id'),('term_id','term_id'),('group_id','group_id'),('hub_user','owner'),('hub_server','server'),('namespace','namespace'),('pod','pod')]:row[dest]=target['registration'][key]
    service=SimpleNamespace(hub=SimpleNamespace(hub=SimpleNamespace(get_user=AsyncMock(return_value={'name':source.ACTOR,'admin':True}))),
        compute=SimpleNamespace(_request=AsyncMock(return_value=expected)),get=AsyncMock(side_effect=[dict(row,state='stopped'),dict(row,state='running')]),
        start=AsyncMock(),close=AsyncMock())
    receipt=asyncio.run(source.operate(service,target,'start',mode,expected))
    service.start.assert_awaited_once_with(target['workspace'],actor=source.ACTOR)
    assert receipt['profile']=='interactive-native-qualification-20' and receipt['hardware_qualified'] is False


def test_incomplete_peer_cli_pins_deny_before_private_input(monkeypatch):
    from test_prospective_source_qualification_workspace import arguments
    import asyncio
    args=arguments();args.peer_target_snapshot='/offline/peer.json';args.peer_target_snapshot_sha256=None
    monkeypatch.setattr(source,'protected',lambda *a:pytest.fail('Peer pin denied after protected input'))
    with pytest.raises(ValueError,match='peer path/raw pin'):asyncio.run(source.execute(args))


def test_pair_rejects_reusing_one_persons_global_gpu_allowance():
    values,peer=pair_fixture()
    peer['operator_members']=peer['registration']['members']=copy.deepcopy(values[2]['operator_members'])
    values[0][0]['approvals']['cps:'+peer['workspace']]['members']=copy.deepcopy(peer['operator_members'])
    with pytest.raises(ValueError,match='Disjoint canonical operator members'):
        render(values,peer)


def test_source_pair_rejects_shared_person_even_with_valid_individual_targets():
    from datetime import datetime,timezone
    values,peer=pair_fixture();first=values[2]
    for t in (first,peer):t['observed_at']=datetime.now(timezone.utc).isoformat()
    peer['operator_members']=peer['registration']['members']=copy.deepcopy(first['operator_members'])
    with pytest.raises(ValueError,match='Disjoint canonical operator members'):
        source.validate_pair_targets(first,peer)
