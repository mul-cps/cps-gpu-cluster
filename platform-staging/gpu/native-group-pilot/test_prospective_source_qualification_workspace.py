"""Offline Source CLI checks: no credentials, real endpoints or hardware reads."""
import importlib.util
from pathlib import Path

import pytest
import source_qualification_workspace as legacy

HERE=Path(__file__).parent
if (HERE/'prospective_source_qualification_workspace.py').exists():
    spec=importlib.util.spec_from_file_location('prospective_source_workspace',HERE/'prospective_source_qualification_workspace.py')
    proposal=importlib.util.module_from_spec(spec);spec.loader.exec_module(proposal)
else:
    proposal=legacy


def test_legacy_cli_rejects_new_operator_scope_instead_of_reusing_student_workspaces():
    target=legacy.SOURCES['cps']
    row={'id':'native-qualification-531-unit','course_id':'native-qualification-531-unit',
         'term_id':'qualification-531-unit','group_id':'native-qualification-531-unit',
         'hub_user':'cps-operator-531-unit','hub_server':'rtc','namespace':'jupyterhub',
         'pod':'jupyter-cps-operator-531-unit--rtc','source':'local',
         'profile':target['profile'],'course_ceiling':target['ceiling'],'state':'stopped'}
    with pytest.raises(ValueError,match='Exact source-owned migrated workspace'):
        legacy.workspace_guard(row,'cps')


def test_new_cli_accepts_explicit_candidate_target_contract():
    assert callable(getattr(proposal,'validate_target',None)), 'Explicit prospective Source target validation is missing'

import asyncio
import copy
from datetime import datetime, timezone, timedelta
import json
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock


def arguments():
    fields={key:'/offline/'+key+'.json' for key in proposal.PINNED_FILES}
    fields.update({key+'_sha256':'1'*64 for key in proposal.PINNED_FILES})
    fields.update(source='cps',operation='get',source_sha256='2'*64,handover_file_sha256=proposal.HANDOVER_SHA,
        current_authority_sha256='sha256:'+'3'*64,terminal_history_sha256='sha256:'+'4'*64)
    return SimpleNamespace(**fields)


@pytest.fixture
def configuration():
    # Only synthetic Core fixtures, imported from the reviewed efa3 source.
    from cps_compute.policy import Policy
    from cps_compute.native_qualification import NativeGroupQualification
    from test_native_qualification import fixture
    source_policy,mode=fixture((5,),budget=5120)
    workspace='operator-qualification-531-unit';scope='cps:'+workspace
    body=copy.deepcopy(next(iter(mode['workspaces'].values())))
    body.update(owner='cps-ws-'+'a'*32,server='rtc',pod='jupyter-cps-ws-'+'a'*32+'--rtc',
        principal='workspace:'+scope,members=['11111111-1111-4111-8111-111111111111'],
        group_id=workspace,course_id=workspace,term_id='operator-qualification-531-unit')
    body['storage'].update(pvc='operator-531-pvc',pv='operator-531-pv',path='/mnt/operator-531',group_hash='opaque-unit-group')
    catalog=copy.deepcopy(source_policy.catalog);catalog.pop('policyHash',None)
    catalog['gpuQualification']['qualified']=False
    catalog['profiles'][proposal.PROFILE]['images']=[proposal.WORKLOAD_IMAGE]
    policy=Policy(catalog)
    mode['node_pool']['max_workspaces']=1
    mode.update(policy_hash=policy.hash,policy_version=policy.version,gateImage=proposal.GATE_IMAGE,
        workloadImage=proposal.WORKLOAD_IMAGE,workspaces={scope:body})
    typed=NativeGroupQualification.from_config(mode,policy)
    old=copy.deepcopy(body);old.update(workspace=workspace,policy_hash=source_policy.hash,profiles=['interactive-cpu'],
        ceiling={'cpu':'4','memory':'16Gi','gpuMemoryGiB':0},workspace_label=source_policy.labels['workspace'],workspace_hash=source_policy.owner_label(scope))
    old['storage']['state']='active'
    now=datetime.now(timezone.utc)
    target={'version':1,'source':'cps','workspace':workspace,'profile':proposal.PROFILE,'workload_image':proposal.WORKLOAD_IMAGE,
        'operator_members':copy.deepcopy(body['members']),'source_policy_hash':source_policy.hash,'source_closure_sha256':'1'*64,
        'current_authority_sha256':'sha256:'+'3'*64,'source_instance':{'namespace':'cps-compute',
            'deployment_uid':'22222222-2222-4222-8222-222222222222','pod_uid':'33333333-3333-4333-8333-333333333333','image':proposal.SOURCE_IMAGE},
        'registration':old,'state':'stopped','observed_at':now.isoformat()}
    history={'44444444-4444-4444-8444-444444444444':{'opaque_retired_record':'retained-exactly'}}
    node={'version':2,'enabled':True,'mode':'operator-qualification','authority_namespace':typed.authority_namespace,
        'policy_hash':policy.hash,'pool':typed.node_pool,'workspaces':{scope:{'profile':proposal.PROFILE,'cap_mib':5120}},'terminal_history':history}
    kwargs={'source_closure_sha256':target['source_closure_sha256'],'current_authority_sha256':target['current_authority_sha256'],
        'terminal_history_sha256':proposal.canonical_sha256(history)}
    return target,source_policy,policy,typed,node,kwargs,now


def test_explicit_candidate_target_and_actual_typed_configuration_pass(configuration):
    target,old,policy,mode,node,kwargs,now=configuration
    assert proposal.validate_target(target,now=now)==target
    expected=proposal.validate_configuration(target,old,policy,mode,node,**kwargs)
    assert expected==proposal.expected_registration(target,policy)
    assert expected['members']==target['registration']['members'] and expected['storage']==target['registration']['storage']
    assert target['registration']['profiles']==['interactive-cpu']
    assert expected['profiles']==[proposal.PROFILE] and expected['ceiling']==proposal.CEILING


@pytest.mark.parametrize('field,value', [('source','cit'),('operation','delete'),('source_sha256',None),
    ('target_snapshot_sha256','A'*64),('policy_sha256','0'*64),('source_closure_sha256','missing'),
    ('node_config_sha256',None),('config_file_sha256',None),('source_policy_sha256',None),
    ('handover_file_sha256','7'*64),('current_authority_sha256',None),('terminal_history_sha256',None)])
def test_bad_or_missing_pin_denies_before_any_private_input_or_api(monkeypatch,field,value):
    args=arguments();setattr(args,field,value)
    def forbidden(*args,**kwargs):raise AssertionError('Private access before complete Root pins')
    monkeypatch.setattr(proposal,'protected',forbidden)
    with pytest.raises(ValueError):asyncio.run(proposal.execute(args))


@pytest.mark.parametrize('tamper',['source','student-scope','student-owner','human-owner','student-member','profile','image','extra',
    'source-image','source-uid','source-namespace','old-policy','registration-fields','storage-inactive','stale','future'])
def test_target_denials_precede_config_app_and_api(configuration,tamper):
    target,*_,now=configuration
    if tamper=='source':target['source']='cit'
    elif tamper=='student-scope':target['workspace']='shared-gpu-lab'
    elif tamper=='student-owner':target['registration']['owner']=proposal.STUDENT_OWNER
    elif tamper=='human-owner':target['registration']['owner']='mikasa'
    elif tamper=='student-member':target['operator_members']=[next(iter(proposal.STUDENT_PEOPLE))]
    elif tamper=='profile':target['profile']='interactive-native-qualification-20'
    elif tamper=='image':target['workload_image']='unreviewed'
    elif tamper=='extra':target['unknown']=True
    elif tamper=='source-image':target['source_instance']['image']='unreviewed'
    elif tamper=='source-uid':target['source_instance']['pod_uid']='not-a-uuid'
    elif tamper=='source-namespace':target['source_instance']['namespace']='jupyterhub'
    elif tamper=='old-policy':target['registration']['policy_hash']='sha256:'+'0'*64
    elif tamper=='registration-fields':target['registration']['unknown']=True
    elif tamper=='storage-inactive':target['registration']['storage']['state']='deleted'
    else:target['observed_at']=(now+timedelta(seconds=1) if tamper=='future' else now-timedelta(seconds=901)).isoformat()
    with pytest.raises(ValueError):proposal.validate_target(target,now=now)


@pytest.mark.parametrize('tamper',['history','pool','source-label','authority','closure','pvc','policy-enabled','workload'])
def test_configuration_history_and_scope_mixes_fail_before_source_loading(configuration,tamper):
    target,old,policy,mode,node,kwargs,_=configuration
    if tamper=='history':node['terminal_history'].clear()
    elif tamper=='pool':node['pool']=copy.deepcopy(node['pool']);node['pool']['memory_budget_mib']+=1
    elif tamper=='source-label':target['registration']['workspace_hash']='unreviewed'
    elif tamper=='authority':kwargs['current_authority_sha256']='sha256:'+'8'*64
    elif tamper=='closure':kwargs['source_closure_sha256']='8'*64
    elif tamper=='pvc':target['registration']['storage']['pvc']='different-pvc'
    elif tamper=='policy-enabled':policy.catalog['profiles'][proposal.PROFILE]['enabled']=True
    elif tamper=='workload':target['registration']['members']=['55555555-5555-4555-8555-555555555555']
    with pytest.raises(ValueError):proposal.validate_configuration(target,old,policy,mode,node,**kwargs)


def local_workspace(target,state='stopped'):
    body=target['registration']
    return {'id':target['workspace'],'course_id':body['course_id'],'term_id':body['term_id'],'group_id':body['group_id'],
        'hub_user':body['owner'],'hub_server':'rtc','namespace':'jupyterhub','pod':body['pod'],'source':'local',
        'profile':proposal.PROFILE,'course_ceiling':proposal.CEILING,'state':state}


def service_fixture(configuration,state='stopped',after='stopped'):
    target,old,policy,mode,node,kwargs,_=configuration
    expected=proposal.validate_configuration(target,old,policy,mode,node,**kwargs)
    service=SimpleNamespace(hub=SimpleNamespace(hub=SimpleNamespace(get_user=AsyncMock(return_value={'name':proposal.ACTOR,'admin':True}))),
        compute=SimpleNamespace(_request=AsyncMock(return_value=expected)),get=AsyncMock(side_effect=[local_workspace(target,state),local_workspace(target,after)]),
        start=AsyncMock(),close=AsyncMock())
    return service,target,mode,expected


def test_normal_start_get_and_stop_are_exact_existing_service_calls(configuration):
    for operation,before,after in [('start','stopped','running'),('stop','running','stopped'),('get','stopped','stopped')]:
        service,target,mode,expected=service_fixture(configuration,before,after)
        result=asyncio.run(proposal.operate(service,target,operation,mode,expected))
        assert result['state']==after and result['hardware_qualified'] is False
        assert 'before' not in result and 'registration' not in result
        if operation=='start':service.start.assert_awaited_once_with(target['workspace'],actor=proposal.ACTOR)
        else:service.start.assert_not_called()
        if operation=='stop':service.close.assert_awaited_once_with(target['workspace'],actor=proposal.ACTOR,archive=False)
        else:service.close.assert_not_called()


def test_missing_operator_workspace_is_clear_pending_normal_creation_with_no_api(configuration):
    service,target,mode,expected=service_fixture(configuration)
    service.get=AsyncMock(side_effect=KeyError(target['workspace']))
    with pytest.raises(ValueError,match='normal Source console/API'):
        asyncio.run(proposal.operate(service,target,'start',mode,expected))
    service.start.assert_not_called();service.close.assert_not_called()
    service.hub.hub.get_user.assert_not_called();service.compute._request.assert_not_called()


def test_foreign_registration_or_actor_never_starts(configuration):
    for tamper in ('actor','registration'):
        service,target,mode,expected=service_fixture(configuration,'stopped','running')
        if tamper=='actor':service.hub.hub.get_user.return_value={'name':proposal.ACTOR,'admin':False}
        else:
            wrong=copy.deepcopy(expected);wrong['storage']['pvc']='foreign';service.compute._request.return_value=wrong
        with pytest.raises(ValueError):asyncio.run(proposal.operate(service,target,'start',mode,expected))
        service.start.assert_not_called();service.close.assert_not_called()


def test_default_cli_is_inert_without_source_or_core_imports():
    result=subprocess.run([sys.executable,str(HERE/'prospective_source_qualification_workspace.py')],capture_output=True,text=True,check=True)
    assert json.loads(result.stdout)=={'version':1,'state':'inert','live_execution':False}


@pytest.mark.parametrize('tamper',['owner','profile','history-authority'])
def test_bad_root_target_denies_before_other_private_inputs_and_api(configuration,monkeypatch,tamper):
    target,*_=configuration;args=arguments();reads=[]
    if tamper=='owner':target['registration']['owner']='armin'
    elif tamper=='profile':target['profile']='interactive-shared-5'
    else:target['current_authority_sha256']='sha256:'+'9'*64
    def protected(path,digest):
        reads.append(str(path))
        if str(path)==proposal.__file__:return b'synthetic-self-bytes'
        if str(path)==args.target_snapshot:return json.dumps(target).encode()
        raise AssertionError('Rejected target reached private configuration/source loader')
    monkeypatch.setattr(proposal,'protected',protected)
    monkeypatch.setattr(proposal.os,'geteuid',lambda:10001)
    with pytest.raises(ValueError):asyncio.run(proposal.execute(args))
    assert reads==[proposal.__file__,args.target_snapshot]


def test_stale_or_archived_local_workspace_never_reaches_api(configuration):
    for field,value in [('archived',True),('external_id','foreign'),('profile','interactive-cpu')]:
        service,target,mode,expected=service_fixture(configuration)
        row=local_workspace(target);row[field]=value;service.get=AsyncMock(return_value=row)
        with pytest.raises(ValueError):asyncio.run(proposal.operate(service,target,'start',mode,expected))
        service.start.assert_not_called();service.compute._request.assert_not_called()


def test_nonstopped_start_and_unknown_operation_never_mutate(configuration):
    for operation,state in [('start','starting'),('start','running'),('delete','stopped')]:
        service,target,mode,expected=service_fixture(configuration,state,'running')
        with pytest.raises(ValueError):asyncio.run(proposal.operate(service,target,operation,mode,expected))
        service.start.assert_not_called();service.close.assert_not_called()


@pytest.mark.parametrize('field',['course_id','term_id','group_id'])
def test_all_source_owner_group_context_is_operator_only(configuration,field):
    target,*_,now=configuration;target['registration'][field]='student-course'
    with pytest.raises(ValueError):proposal.validate_target(target,now=now)


@pytest.mark.parametrize('field,value',[('max_workspaces',2),('memory_budget_mib',10240)])
def test_typed_mode_cannot_expand_the_single5_pool(configuration,field,value):
    from cps_compute.native_qualification import NativeGroupQualification
    target,old,policy,mode,node,kwargs,_=configuration
    config=mode._config();config['node_pool'][field]=value
    larger=NativeGroupQualification.from_config(config,policy)
    node['pool']=larger.node_pool
    with pytest.raises(ValueError):proposal.validate_configuration(target,old,policy,larger,node,**kwargs)
