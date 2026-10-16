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
    obj=lambda kind,name,n,data:dict(apiVersion='v1',kind=kind,metadata=dict(namespace='cps-compute',name=name,uid=uid(n),resourceVersion='10'),data=data)
    policy=obj('ConfigMap','compute-policy',100,{'policy.json':transition.canonical(body['catalog']),'unrelated':'preserve'})
    secret=obj('Secret','compute-runtime',101,{'runtime.json':base64.b64encode(raw(runtime)).decode(),'unrelated':'cHJlc2VydmU='})
    gateway=dict(apiVersion='apps/v1',kind='Deployment',metadata=dict(namespace='cps-compute',name='compute-gateway',uid=uid(102),resourceVersion='11'),
        spec=dict(replicas=1,template=dict(metadata={'annotations':{'other':'preserve'}},spec=dict(containers=[dict(name='gateway',image='registry.example/gateway@sha256:'+'9'*64)],volumes=[dict(name='runtime',secret={'secretName':'compute-runtime'})]))))
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
