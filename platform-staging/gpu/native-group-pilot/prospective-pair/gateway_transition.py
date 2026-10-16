"""Default-inert Gateway policy/runtime forward and inverse for the Root CPS pair.

Only constructs UID/resource-version/data/spec-tested JSON patches. No API,
credential, filesystem, Source, Hub, driver or workload operations are performed.
"""
import base64
import copy

import node_agent as agent
import node_successor
import qualification_transition_proposal as transition
from qualification_proposal import _candidate_history_context, CANDIDATE_IMAGE, CURRENT_GATE_IMAGE


def owner(obj,kind):
    meta=transition.object_guard(obj,kind)
    agent.require(obj.get('apiVersion')==('apps/v1' if kind=='Deployment' else 'v1')
        and meta.get('namespace')=='cps-compute' and meta['uid']!='00000000-0000-0000-0000-000000000000'
        and not meta.get('deletionTimestamp'),'Actual nonzero owning Gateway configuration required')
    return meta


def forward_intent(*,proposal,originals,contract_raw,contract_sha256):
    from cps_compute.policy import Policy
    from cps_compute.native_groups import NativeGroupDeployment
    from cps_compute.native_qualification import NativeGroupQualification
    contract=node_successor.validate_contract(contract_raw,contract_sha256)
    agent.closed(originals,{'policy','runtime','gateway_deployment','node_config'},'Complete original Gateway objects and Node configuration required')
    for key,kind in [('policy','ConfigMap'),('runtime','Secret'),('gateway_deployment','Deployment')]:owner(originals[key],kind)
    acceptance=proposal['acceptance.json']
    agent.require(acceptance.get('hardware_qualified') is False and acceptance.get('live_applied') is False
        and acceptance.get('source_mode')=='prospective-candidate','Separate unqualified prospective proposal required')
    oldpolicy=Policy(agent.parse(originals['policy']['data']['policy.json']))
    policy=Policy(proposal['policy.json']);mode=proposal['operator-qualification.json']
    NativeGroupQualification.from_config(mode,policy)
    validator,_=_candidate_history_context()
    old=validator.validate_config(originals['node_config']);node=validator.validate_config(proposal['node-config.json'])
    agent.require(oldpolicy.hash==old['policy_hash']=='sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'
        and old['mode']=='qualified-group' and old['enabled'] is True
        and oldpolicy.catalog['gpuQualification']['qualified'] is False
        and policy.hash==mode['policy_hash']==node['policy_hash']==contract['policy_hash']
        and policy.catalog['gpuQualification']['qualified'] is False
        and node['enabled'] is True and node['mode']=='operator-qualification'
        and node['workspaces']==contract['workspaces']
        and all(node['terminal_history'].get(u)==e for u,e in old['terminal_history'].items())
        and transition.digest(node['terminal_history'])==contract['terminal_history_sha256']
        and node['pool']==mode['node_pool'] and node['authority_namespace']==mode['authorityNamespace']==old['authority_namespace']
        and node['pool']['memory_budget_mib']==25600 and node['pool']['max_workspaces']==2
        and node['pool']['headroom_mib']==1024 and node['pool']['free_memory_mib']>=26624
        and all(node['pool'][k]==old['pool'][k] for k in ('node','node_uid','gpu_uuid','boot_id','driver_generation','total_memory_mib')),
        'Exact original D48 and Root-pinned prospective pair/policy/history/physical epoch required')
    agent.require(mode['gateImage']==CURRENT_GATE_IMAGE and mode['workloadImage']==CANDIDATE_IMAGE
        and mode['profile_caps']=={'interactive-native-qualification-5':5120,'interactive-native-qualification-20':20480}
        and set(mode['workspaces'])==set(contract['workspaces']), 'Only exact immutable candidate images and two CPS scopes required')
    for scope,profile in contract['workspaces'].items():
        approved=mode['workspaces'][scope]
        agent.require(approved['profiles']==[profile['profile']]
            and approved['members']==sorted(contract['operator_members'][scope])
            and approved['ceiling']=={'cpu':'4','memory':'16Gi','gpuMemoryGiB':profile['cap_mib']//1024},
            'Exact disjoint Root operator people and fixed profile ceilings required')
    expected=copy.deepcopy(oldpolicy.catalog);expected.pop('policyHash',None)
    for size in (5,20):
        name='interactive-native-qualification-'+str(size)
        row=copy.deepcopy(expected['profiles']['interactive-shared-5'])
        row.update(enabled=False,kind='interactive',queue='interactive',cpu='4',memory='16Gi',images=[CANDIDATE_IMAGE])
        row.pop('qualificationRequired',None)
        row['gpu']={'mode':'shared','nominalMemoryGiB':size,'qualification':{'mechanism':'r615-native-cgroup-managed-deny','status':'pilot-unqualified'}}
        expected['profiles'][name]=row
    expected['policyHash']=Policy(expected).hash
    agent.require(policy.catalog==expected,'Only the two disabled trusted qualification aliases may extend the original catalog')
    runtime_secret=originals['runtime'];runtime=agent.parse(base64.b64decode(runtime_secret['data']['runtime.json'],validate=True))
    group=NativeGroupDeployment.from_config(runtime['nativeGpuGroups'],oldpolicy)
    agent.require(group is not None and runtime['policy_hash']==oldpolicy.hash
        and runtime['nativeGpuPilot']==runtime['nativeGpuQualification']=={'enabled':False}
        and group.node_pool==old['pool'],'Exact current native group runtime and Node pool required')
    from cps_compute.runtime import native_group_approval_configuration
    dynamic=native_group_approval_configuration(runtime)
    newruntime=dict(copy.deepcopy(runtime),policy_hash=policy.hash,nativeGpuGroups={'enabled':False},
        nativeGpuPilot={'enabled':False},nativeGpuQualification=copy.deepcopy(mode))
    if dynamic is not None:newruntime['nativeGroupApprovals']={'enabled':False}
    policy_data=dict(originals['policy']['data'],**{'policy.json':transition.canonical(policy.catalog)})
    runtime_data=dict(runtime_secret['data'],**{'runtime.json':base64.b64encode(transition.canonical(newruntime).encode()).decode()})
    spec=copy.deepcopy(originals['gateway_deployment']['spec'])
    publishers=[]
    for container in spec['template']['spec']['containers']:
        selected=[e for e in container.get('env',[]) if e.get('name')=='CPS_NATIVE_APPROVAL_PUBLISHER_PATH']
        if selected:
            agent.require(dynamic is not None and container.get('name')==dynamic['processes']['gateway']['container']
                and len(selected)==1,'Only exact owning Gateway heartbeat bootstrap may be removed')
            publishers.extend(selected)
            container['env']=[e for e in container['env'] if e.get('name')!='CPS_NATIVE_APPROVAL_PUBLISHER_PATH']
    agent.require(len(publishers)==(1 if dynamic is not None else 0),
        'Dynamic approval mode must match exactly one explicit Gateway heartbeat bootstrap')
    spec['template'].setdefault('metadata',{}).setdefault('annotations',{})['cps.compute/native-qualification-config']=transition.digest({'policy_hash':policy.hash,'mode':mode})
    return {'version':1,'enabled':False,'live_applied':False,'hardware_qualified':False,
        'policy.patch.json':transition.replace_patch(originals['policy'],'/data',originals['policy']['data'],policy_data),
        'runtime.patch.json':transition.replace_patch(runtime_secret,'/data',runtime_secret['data'],runtime_data),
        'gateway-deployment.patch.json':transition.replace_patch(originals['gateway_deployment'],'/spec',originals['gateway_deployment']['spec'],spec)}


def inverse_intent(*,current,**forward_inputs):
    forward=forward_intent(**forward_inputs)
    agent.closed(current,{'policy','runtime','gateway_deployment'},'Complete actual current Gateway readbacks required')
    originals=forward_inputs['originals'];result={'version':1,'enabled':False,'live_applied':False,'hardware_qualified':False}
    for key,file,kind,field in [('policy','policy.patch.json','ConfigMap','data'),('runtime','runtime.patch.json','Secret','data'),
        ('gateway_deployment','gateway-deployment.patch.json','Deployment','spec')]:
        previous=owner(originals[key],kind);actual=owner(current[key],kind)
        agent.require(all(actual[k]==previous[k] for k in ('namespace','name','uid'))
            and current[key][field]==forward[file][-1]['value'], 'Current full Gateway objects must match the exact coordinated prospective forward intent')
        result[file]=transition.replace_patch(current[key],'/'+field,current[key][field],originals[key][field])
    result['execution_requires_complete_node_and_source_inverse']=True
    return result
