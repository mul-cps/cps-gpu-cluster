import copy
import importlib.util
import json
from pathlib import Path
import pytest
from cps_compute.native_node.config import NodeConfiguration
from cps_compute.native_groups import canonical_sha256,NativeGroupDeployment
from cps_compute.native_qualification_authority import NativeQualificationAuthority
from cps_compute.native_group_revision import ApprovalRevision
from test_native_node_config import node_fixture,ref


def fixture():
    policy,value,core,maps=node_fixture();body=json.loads(value['data']['config.json'])
    deployment=json.loads(maps['deployment']['data']['deployment.json']);ns='cps-native-runtime'
    proof=maps[deployment['qualification_ref']['name']];proof['metadata']['namespace']=ns
    deployment['authorityNamespace']=ns;deployment['qualification_ref']=ref(proof).to_dict()
    authority=NativeQualificationAuthority.from_configmap(proof,ref(proof).to_dict(),policy)
    typed=NativeGroupDeployment.from_config(deployment,policy,authority=authority)
    deployed=maps['deployment'];deployed['metadata']['namespace']=ns;deployed['data']['deployment.json']=json.dumps(deployment,sort_keys=True,separators=(',',':'))
    registry={'version':2,'generation':1,'deployment':deployment}
    approval=maps['approval'];approval['metadata']['namespace']=ns
    approval['data']['approval.json']=json.dumps({'version':2,'registry':registry,'revision':canonical_sha256(registry),'policy_hash':policy.hash,'history':[]},sort_keys=True,separators=(',',':'))
    body['qualification_ref']=ref(deployed).to_dict();body['approval_ref']=ApprovalRevision.from_configmap(approval,policy,typed).reference
    maps['terminal-index']['metadata']['namespace']=ns;body['terminal_index_ref']=ref(maps['terminal-index']).to_dict()
    for c in body['component_declarations']:body['component_declarations'][c]['namespace']=ns;body['acknowledgment_targets'][c]['namespace']=ns
    body['cdi_pins']['selected_filename']='cps-native-selected-147.json'
    value['metadata']['namespace']=ns;value['data']['config.json']=json.dumps(body,sort_keys=True,separators=(',',':'))
    configuration=NodeConfiguration.from_configmap(value,ref(value),policy,deployment=typed,qualification_cm=deployed)
    d=body['component_declarations']['node']
    controller={'apiVersion':'apps/v1','kind':'Deployment','metadata':{k:d[k] for k in ('namespace','name','uid')},
        'spec':{'replicas':0,'template':{'spec':{'serviceAccountName':d['service_account'],
        'containers':[{'name':d['container'],'image':d['image'],'command':['unchanged']}],
        'initContainers':[{'name':'packaged-bootstrap','image':d['image'],'command':['unchanged']}],
        'volumes':[]}}}}
    s=importlib.util.spec_from_file_location('startup',Path(__file__).with_name('startup.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    return m,configuration,controller


def test_real_typed_cold_node_init_precedes_original_startup_and_preserves_spec():
    m,config,controller=fixture();before=copy.deepcopy(controller)
    result=m.candidates(config,controller,authority_directory='var/lib/cps-native-gpu/domains/100876ac-14e6-4292-bf52-7d129f7f08f0/custody/authority')
    pod=result['spec']['template']['spec'];init=pod['initContainers'].pop(0)
    assert init['name']=='selected-cdi-prepare' and init['image']==pod['containers'][0]['image']
    assert init['env']==[{'name':'NVIDIA_VISIBLE_DEVICES','value':'void'}]
    assert [v for v in init['volumeMounts'] if v.get('readOnly') is False]==[{'name':'selected-cdi-output','mountPath':'/cdi','readOnly':False}]
    assert len(pod['volumes'])==3;pod['volumes']=[]
    assert result['spec']==before['spec'] and controller==before
    assert result['configmap']['immutable'] is True

@pytest.mark.parametrize('fault',['image','uid','collision','authority'])
def test_wrong_target_or_colliding_hook_denied(fault):
    m,c,d=fixture();authority='var/lib/cps-native-gpu/domains/100876ac-14e6-4292-bf52-7d129f7f08f0/custody/authority'
    if fault=='image':d['spec']['template']['spec']['initContainers'][0]['image']='different'
    elif fault=='uid':d['metadata']['uid']='different'
    elif fault=='collision':d['spec']['template']['spec']['volumes'].append({'name':'selected-cdi-output'})
    elif fault=='authority':authority='../authority'
    with pytest.raises(ValueError):m.candidates(c,d,authority_directory=authority)
