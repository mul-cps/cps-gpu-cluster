"""Exact Node8c image-backed code overlay and terminal-custody inverse.

Only two generated Python files are mounted read-only. The image, driver,
privileges, host mounts and all unrelated spec fields remain unchanged. No API
or hardware action is performed by this module.
"""
import copy
import json
import sys
from types import ModuleType

import configuration_inverse as inverse
import node_agent as guard
import node_successor
import qualification_transition_proposal as transition

IMAGE='ghcr.io/mul-cps/cps-compute@sha256:8c2c456b90330622645d509f94882a11a465ac208a6fa7fc824900d6320e5c0b'
VOLUME='cps-native-qualification-code'
FLAGS={'--approval-reference':'/var/run/cps-native-approvals/reference.json',
       '--approval-template':'/var/run/cps-native-approvals/template.json',
       '--approval-process':'/var/run/cps-native-approvals/process.json',
       '--approval-acknowledgment':'/var/run/cps-native-approvals/acknowledgment.json'}


def owner(obj,kind):
    meta=transition.object_guard(obj,kind)
    guard.require(meta['namespace']=='cps-native-system' and not meta.get('deletionTimestamp')
        and not meta.get('ownerReferences'),'Actual retained native object required')
    return meta


def overlay(spec,code_name,reuse=False):
    value=copy.deepcopy(spec);pod=value['template']['spec'];container=pod['containers'][0]
    if reuse:
        expected=dict(name=VOLUME,configMap={'name':code_name,'defaultMode':0o644})
        existing=[v for v in pod.get('volumes',[]) if v.get('name')==VOLUME]
        mounts=[m for m in container.get('volumeMounts',[]) if m.get('name')==VOLUME]
        wanted=[dict(name=VOLUME,mountPath='/opt/native/'+name,subPath=name,readOnly=True)
                for name in ('node_agent.py','native_operator_epoch.py')]
        guard.require(existing==[expected] and mounts==wanted, 'Exact retained generated code overlay required')
        other=copy.deepcopy(value)
        other['template']['spec']['volumes'].remove(expected)
        other['template']['spec']['containers'][0]['volumeMounts']=[m for m in container['volumeMounts'] if m not in wanted]
        guard.require(overlay(other,code_name)==value, 'No unrelated code overlap may survive reentry')
        return value
    guard.require(all(v.get('name')!=VOLUME for v in pod.get('volumes',[])),'Code overlay volume already exists')
    for mount in container.get('volumeMounts',[]):
        path=mount.get('mountPath','')
        guard.require(path not in ('/','/opt','/opt/native') and not path.startswith('/opt/native/'),
            'Existing mount overlaps the immutable image code')
    pod['volumes'].append(dict(name=VOLUME,configMap={'name':code_name,'defaultMode':0o644}))
    for name in ('node_agent.py','native_operator_epoch.py'):
        container.setdefault('volumeMounts',[]).append(dict(name=VOLUME,mountPath='/opt/native/'+name,subPath=name,readOnly=True))
    return value


def configuration_reference(spec,old_name,new_name):
    count=0
    for volume in spec['template']['spec']['volumes']:
        if volume.get('configMap',{}).get('name')==old_name:
            guard.require(volume['name']=='config','Unexpected configuration volume identity')
            volume['configMap']['name']=new_name;count+=1
    guard.require(count==1,'Exactly one original configuration reference required')


def forward_intent(*,original_deployment,original_configuration,proposed_node,
                   original_node_source,original_epoch_source,contract_raw,contract_sha256,retained_qualification=None):
    meta=owner(original_deployment,'Deployment');oldmeta=owner(original_configuration,'ConfigMap')
    guard.require(original_deployment.get('apiVersion')=='apps/v1' and meta['name']=='cps-native-node-agent'
        and original_configuration.get('apiVersion')=='v1' and original_configuration.get('immutable') is True
        and not original_configuration.get('binaryData'),'Original Node8c Deployment and immutable configuration required')
    contract=node_successor.validate_contract(contract_raw,contract_sha256)
    bundle=node_successor.successor_bundle(original_node_source,original_epoch_source,contract_raw,contract_sha256)
    agent=ModuleType('reviewed_image_node_transition');agent.__file__=guard.__file__;sys.modules[agent.__name__]=agent
    exec(compile(bundle['node_agent.py'],'<reviewed-image-backed-node>','exec'),agent.__dict__)
    old=agent.validate_config(json.loads(original_configuration['data']['config.json']))
    new=agent.validate_config(copy.deepcopy(proposed_node))
    if retained_qualification is not None:
        owner(retained_qualification,'ConfigMap')
        guard.require(retained_qualification.get('apiVersion')=='v1'
            and retained_qualification.get('immutable') is True and not retained_qualification.get('binaryData')
            and retained_qualification.get('data')=={'config.json':transition.canonical(new)},
            'Exact immutable original qualification configuration required for reentry')
    guard.require(old['mode']=='qualified-group'  and old['enabled'] is True
        and old['policy_hash']=='sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'
        and new['mode']=='operator-qualification' and new['enabled'] is True
        and new['policy_hash']==contract['policy_hash'] and new['workspaces']==contract['workspaces']
        and agent.canonical_sha256(new['terminal_history'])==contract['terminal_history_sha256']
        and all(new['terminal_history'].get(k)==v or (retained_qualification is not None
            and inverse.retained_as_current(v,retained_qualification,new))
            for k,v in old['terminal_history'].items())
        and new['authority_namespace']==old['authority_namespace']=='cps-native-system'
        and all(new['pool'][k]==old['pool'][k] for k in ('node','node_uid','gpu_uuid','boot_id','driver_generation','total_memory_mib'))
        and new['pool']['memory_budget_mib']==25600 and new['pool']['max_workspaces']==2
        and new['pool']['headroom_mib']==1024 and new['pool']['free_memory_mib']>=26624,
        'Only the independently pinned operator pair and unchanged physical epoch may transition')
    spec=copy.deepcopy(original_deployment['spec']);pod=spec['template']['spec']
    guard.require(spec['replicas']==1 and len(pod['containers'])==1 and not pod.get('initContainers'),
        'Exact single-process image-backed Node required')
    container=pod['containers'][0]
    guard.require(container.get('name')=='node-agent' and container.get('image')==IMAGE
        and container.get('command')==['python3','/opt/native/node_agent.py']
        and any(m==dict(name='config',mountPath='/config/config.json',subPath='config.json',readOnly=True)
            for m in container.get('volumeMounts',[])), 'Exact published Node8c image entrypoint and configuration mount required')
    args=container.get('args');guard.require(isinstance(args,list) and all(isinstance(a,str) for a in args),'Exact argument vector required')
    for flag,path in FLAGS.items():
        guard.require(args.count(flag)==1,'Exactly one original dynamic approval flag required')
        index=args.index(flag);guard.require(index+1<len(args) and args[index+1]==path,'Exact original approval path required')
        del args[index:index+2]
    code=transition.immutable_config(original_configuration,bundle,'cps-native-node-code-qualification')
    config=transition.immutable_config(original_configuration,{'config.json':transition.canonical(new)},'cps-native-node-qualification')
    configuration_reference(spec,oldmeta['name'],config['metadata']['name'])
    configuration=next(v['configMap'] for v in spec['template']['spec']['volumes'] if v['name']=='config')
    configuration['defaultMode']=0o400
    for item in configuration.get('items',[]):
        guard.require(item.get('key')==item.get('path')=='config.json','Exact operator configuration projection required')
        item['mode']=0o400
    spec=overlay(spec,code['metadata']['name'],reuse=retained_qualification is not None)
    return dict(version=1,enabled=False,live_applied=False,hardware_qualified=False,
        **{'code.json':code,'configuration.json':config,
           'deployment.patch.json':transition.replace_patch(original_deployment,'/spec',original_deployment['spec'],spec)})


def inverse_intent(*,forward_inputs,current_deployment,current_configuration,current_code,terminal_inputs,phase):
    guard.require(phase in ('unstarted','partial','complete'),'Explicit terminal restoration phase required')
    forward=forward_intent(**forward_inputs)
    original=forward_inputs['original_deployment'];before=owner(original,'Deployment');now=owner(current_deployment,'Deployment')
    guard.require(all(before[k]==now[k] for k in ('namespace','name','uid'))
        and current_deployment['spec']==forward['deployment.patch.json'][-1]['value'],
        'Complete current Node spec must match the exact reviewed overlay')
    for actual,key in ((current_code,'code.json'),(current_configuration,'configuration.json')):
        owner(actual,'ConfigMap');expected=forward[key]
        guard.require(actual.get('apiVersion')=='v1' and actual.get('immutable') is True
            and not actual.get('binaryData') and actual['metadata']['name']==expected['metadata']['name']
            and actual['data']==expected['data'],'Actual created immutable overlay/configuration changed')
    guard.require(terminal_inputs['original']==forward_inputs['original_configuration']
        and terminal_inputs['current']==current_configuration
        and all(terminal_inputs[k]==forward_inputs[k] for k in ('original_node_source','original_epoch_source','contract_raw','contract_sha256')),
        'Full terminal custody must belong to this exact original and current transition')
    derive={'unstarted':inverse.derive_unstarted_node_inverse,'partial':inverse.derive_partial_node_inverse,'complete':inverse.derive_node_inverse}[phase]
    result=derive(**terminal_inputs)
    desired=copy.deepcopy(original['spec'])
    if phase!='unstarted':
        desired=overlay(desired,current_code['metadata']['name'],reuse=forward_inputs.get('retained_qualification') is not None)
        configuration_reference(desired,forward_inputs['original_configuration']['metadata']['name'],result['node-configmap.json']['metadata']['name'])
    result.update(restoration_phase=phase,**{'node-deployment.patch.json':transition.replace_patch(current_deployment,'/spec',current_deployment['spec'],desired)})
    return result
