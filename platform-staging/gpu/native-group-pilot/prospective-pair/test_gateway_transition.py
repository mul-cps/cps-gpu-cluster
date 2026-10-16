"""Real policy models and pair proposal; synthetic private Gateway objects."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import uuid

import pytest
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE.parent))
import test_prospective531_pair as pair
import qualification_transition_proposal as transition

raw=lambda v:json.dumps(v,sort_keys=True,separators=(',',':')).encode()
uid=lambda n:str(uuid.UUID(int=n))


def tool():
    path=HERE/'gateway_transition.py'
    assert path.exists(), 'Coordinated prospective Gateway transition required'
    spec=importlib.util.spec_from_file_location('prospective_gateway_transition',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def fixture():
    values,peer=pair.pair_fixture();proposal=pair.render(values,peer);body=values[0][0]
    source=json.loads((HERE.parent/'testdata/reviewed-d48-native-source.json').read_bytes())
    runtime=copy.deepcopy(source['runtime']);runtime['privateSetting']='preserve-exactly'
    components={'gateway':'cps-compute','hub:cps':'jupyterhub','hub:cit':'cit-jhub','node':'cps-native-system'}
    runtime['nativeGroupApprovals']=dict(enabled=True,ttlSeconds=60,
        driver_epoch={k:body['node_config']['pool'][k] for k in ('node_uid','boot_id','driver_generation','gpu_uuid')},
        acknowledgments={c:dict(namespace=ns,name='epoch-'+str(i),uid=uid(400+i)) for i,(c,ns) in enumerate(components.items())},
        processes={c:dict(namespace=ns,kind='Deployment',name='process-'+str(i),uid=uid(410+i),container='gateway' if c=='gateway' else 'component',image='registry.example/process@sha256:'+'9'*64,service_account='component') for i,(c,ns) in enumerate(components.items())})
    obj=lambda kind,name,n,data:dict(apiVersion='v1',kind=kind,metadata=dict(namespace='cps-compute',name=name,uid=uid(n),resourceVersion='10'),data=data)
    policy=obj('ConfigMap','compute-policy',100,{'policy.json':transition.canonical(body['catalog']),'unrelated':'preserve'})
    secret=obj('Secret','compute-runtime',101,{'runtime.json':base64.b64encode(raw(runtime)).decode(),'unrelated':'cHJlc2VydmU='})
    gateway=dict(apiVersion='apps/v1',kind='Deployment',metadata=dict(namespace='cps-compute',name='compute-gateway',uid=uid(102),resourceVersion='11'),
        spec=dict(replicas=1,template=dict(metadata={'annotations':{'other':'preserve'}},spec=dict(containers=[dict(name='gateway',image='registry.example/gateway@sha256:'+'9'*64,env=[dict(name='CPS_NATIVE_APPROVAL_PUBLISHER_PATH',value='/etc/cps-native/bootstrap.json'),dict(name='PRIVATE_SETTING',valueFrom={'secretKeyRef':{'name':'credentials','key':'private'}})])],volumes=[dict(name='runtime',secret={'secretName':'compute-runtime'})]))))
    originals=dict(policy=policy,runtime=secret,gateway_deployment=gateway,node_config=body['node_config'])
    node=proposal['node-config.json']
    people={scope:proposal['operator-qualification.json']['workspaces'][scope]['members'] for scope in node['workspaces']}
    contract=dict(version=1,policy_hash=node['policy_hash'],workspaces=node['workspaces'],terminal_history_sha256=transition.digest(node['terminal_history']),
        operator_people=sorted(p for members in people.values() for p in members),operator_members=people)
    return dict(proposal=proposal,originals=originals,contract_raw=raw(contract),contract_sha256=hashlib.sha256(raw(contract)).hexdigest())


def test_gateway_forward_preserves_private_fields_and_inverse_restores_exact_objects():
    args=fixture();before=copy.deepcopy(args)
    result=tool().forward_intent(**args)
    assert result['hardware_qualified'] is result['live_applied'] is result['enabled'] is False
    current={}
    for key in ('policy','runtime','gateway_deployment'):
        current[key]=copy.deepcopy(args['originals'][key]);current[key]['metadata']['resourceVersion']='20'
        patch=result[{'policy':'policy.patch.json','runtime':'runtime.patch.json','gateway_deployment':'gateway-deployment.patch.json'}[key]]
        current[key]['data' if key!='gateway_deployment' else 'spec']=copy.deepcopy(patch[-1]['value'])
    inverse=tool().inverse_intent(current=current,**args)
    for key,file,field in [('policy','policy.patch.json','data'),('runtime','runtime.patch.json','data'),('gateway_deployment','gateway-deployment.patch.json','spec')]:
        patch=inverse[file]
        assert [op['op'] for op in patch]==['test','test','test','replace']
        assert patch[1]['value']=='20'
        assert patch[-1]['value']==args['originals'][key][field]
    assert current['runtime']['data']['unrelated']==args['originals']['runtime']['data']['unrelated']
    actual=json.loads(base64.b64decode(current['runtime']['data']['runtime.json']))
    assert actual['privateSetting']=='preserve-exactly'
    assert args==before


@pytest.mark.parametrize('fault',['ordinary-profile','enabled-alias','foreign-image','foreign-scope','wrong-person','changed-history','changed-epoch','general-mode'])
def test_gateway_forward_rejects_changes_outside_the_exact_unqualified_pair(fault):
    args=fixture();proposal=args['proposal'];mode=proposal['operator-qualification.json']
    if fault=='ordinary-profile': proposal['policy.json']['profiles']['interactive-cpu']['cpu']='999'
    elif fault=='enabled-alias': proposal['policy.json']['profiles']['interactive-native-qualification-20']['enabled']=True
    elif fault=='foreign-image': mode['workloadImage']='foreign@sha256:'+'a'*64
    elif fault=='foreign-scope': mode['workspaces']['cit:foreign']=copy.deepcopy(next(iter(mode['workspaces'].values())))
    elif fault=='wrong-person': next(iter(mode['workspaces'].values()))['members']=[uid(9999)]
    elif fault=='changed-history': proposal['node-config.json']['terminal_history'].clear()
    elif fault=='changed-epoch': proposal['node-config.json']['pool']['driver_generation']=uid(9999)
    else: proposal['acceptance.json']['hardware_qualified']=True
    with pytest.raises(ValueError): tool().forward_intent(**args)


@pytest.mark.parametrize('fault',['policy','runtime-private','runtime-mode','image','mount','owner','replaced-runtime'])
def test_gateway_inverse_requires_exact_full_fresh_forward_readbacks(fault):
    args=fixture();forward=tool().forward_intent(**args);current={}
    for key,file,field in [('policy','policy.patch.json','data'),('runtime','runtime.patch.json','data'),('gateway_deployment','gateway-deployment.patch.json','spec')]:
        current[key]=copy.deepcopy(args['originals'][key]);current[key]['metadata']['resourceVersion']='20'
        current[key][field]=copy.deepcopy(forward[file][-1]['value'])
    if fault=='policy': current['policy']['data']['unrelated']='changed'
    elif fault=='runtime-private': current['runtime']['data']['unrelated']='changed'
    elif fault=='runtime-mode':
        value=json.loads(base64.b64decode(current['runtime']['data']['runtime.json']));value['privateSetting']='changed'
        current['runtime']['data']['runtime.json']=base64.b64encode(raw(value)).decode()
    elif fault=='image': current['gateway_deployment']['spec']['template']['spec']['containers'][0]['image']='foreign'
    elif fault=='mount': current['gateway_deployment']['spec']['template']['spec']['volumes'].append({'name':'foreign','hostPath':{'path':'/'}})
    elif fault=='owner': current['gateway_deployment']['metadata']['uid']=uid(9999)
    else: current['runtime']['metadata']['uid']=uid(9999)
    with pytest.raises(ValueError): tool().inverse_intent(current=current,**args)


def test_gateway_qualification_target_disables_only_dynamic_group_reader_and_heartbeat():
    from cps_compute.runtime import native_group_approval_configuration, native_gpu_group_configuration, native_gpu_qualification_configuration
    from cps_compute.policy import Policy
    args=fixture();forward=tool().forward_intent(**args)
    runtime=json.loads(base64.b64decode(forward['runtime.patch.json'][-1]['value']['runtime.json']))
    policy=Policy(args['proposal']['policy.json'])
    assert native_group_approval_configuration(runtime) is None
    assert native_gpu_group_configuration(runtime,policy) is None
    assert native_gpu_qualification_configuration(runtime,policy) is not None
    env=forward['gateway-deployment.patch.json'][-1]['value']['template']['spec']['containers'][0]['env']
    assert [e['name'] for e in env]==['PRIVATE_SETTING']
    assert env[0]==args['originals']['gateway_deployment']['spec']['template']['spec']['containers'][0]['env'][1]

CAPTURE_IMAGE='ghcr.io/mul-cps/cps-compute@sha256:042b8b60c0bbdfd2c4506ddf8007677016ef5d278ad5720d7d6b7ac41d136b1b'

def capture_fixture():
 args=fixture();containers=args['originals']['gateway_deployment']['spec']['template']['spec']['containers']
 containers.extend([dict(name='approval-capture',image=CAPTURE_IMAGE,command=['python','-m','cps_compute.native_group_capture_server'],args=['--config','/capture-private/server/config.json']),dict(name='unrelated-observer',image='registry.example/observer')])
 return args


def test_qualification_removes_only_the_pinned_group_capture_and_inverse_restores_it():
 args=capture_fixture();forward=tool().forward_intent(**args)
 desired=forward['gateway-deployment.patch.json'][-1]['value']
 assert [c['name'] for c in desired['template']['spec']['containers']]==['gateway','unrelated-observer']
 current={}
 for key,file,field in [('policy','policy.patch.json','data'),('runtime','runtime.patch.json','data'),('gateway_deployment','gateway-deployment.patch.json','spec')]:
  current[key]=copy.deepcopy(args['originals'][key]);current[key]['metadata']['resourceVersion']='99';current[key][field]=forward[file][-1]['value']
 inverse=tool().inverse_intent(current=current,**args)
 assert inverse['gateway-deployment.patch.json'][-1]['value']==args['originals']['gateway_deployment']['spec']


@pytest.mark.parametrize('field,value',[('image','foreign'),('command',['python','foreign']),('args',['--config','/foreign.json'])])
def test_foreign_capture_container_is_never_silently_removed(field,value):
 args=capture_fixture();args['originals']['gateway_deployment']['spec']['template']['spec']['containers'][1][field]=value
 with pytest.raises(ValueError):tool().forward_intent(**args)


def test_gateway_reentry_requires_exact_prior_qualification_reference():
 args=fixture();node=args['proposal']['node-config.json']
 cm=dict(apiVersion='v1',kind='ConfigMap',immutable=True,metadata=dict(namespace='cps-native-system',name='cps-native-node-qualification-repeat',uid=uid(905),resourceVersion='1'),data={'config.json':transition.canonical(node)})
 from test_node_successor import fixture as node_fixture
 entry=copy.deepcopy(node_fixture()[3]);entry.update(policy_hash=node['policy_hash'],profile='interactive-native-qualification-5',cap_mib=5120)
 entry['configuration_authority']={k:cm['metadata'][k] for k in ('namespace','name','uid')}
 entry['configuration_authority'].update(data_sha256=transition.digest(cm['data']),policy_hash=node['policy_hash'])
 args['originals']['node_config']['terminal_history'][uid(906)]=entry
 with pytest.raises(ValueError):tool().forward_intent(**args)
 args['retained_qualification']=cm
 result=tool().forward_intent(**args);assert result['live_applied'] is False
 for fault in ('uid','data','mutable'):
  bad=copy.deepcopy(args)
  if fault=='uid':bad['retained_qualification']['metadata']['uid']=uid(907)
  elif fault=='data':bad['retained_qualification']['data']['config.json']+=' '
  else:bad['retained_qualification']['immutable']=False
  with pytest.raises(ValueError):tool().forward_intent(**bad)
