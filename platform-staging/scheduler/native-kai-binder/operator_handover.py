"""Pure, CAS-guarded ownership transfer for KAI's unsupported binder flags.

This module makes no API/process/file calls. The operator must be observed
paused with no remaining Pods before the four required operands (and any binder PDB) are detached.
Only then disable its binder operand and resume its other reconciliation.
"""
import copy

RESOURCES=(('apps/v1','Deployment','kai-scheduler','binder'),
    ('v1','ServiceAccount','kai-scheduler','binder'),
    ('v1','Service','kai-scheduler','binder'),
    ('v1','ServiceAccount','kai-resource-reservation','kai-resource-reservation'))
OPTIONAL=('policy/v1','PodDisruptionBudget','kai-scheduler','binder-pdb')
MANAGER='cps-compute-gitops'


def require(value,message):
    if not value:raise ValueError(message)


def identity(obj,expected):
    require(isinstance(obj,dict) and isinstance(obj.get('metadata'),dict),'Actual resource document required')
    meta=obj['metadata']
    actual=(obj.get('apiVersion'),obj.get('kind'),meta.get('namespace',''),meta.get('name'))
    require(actual==expected and all(isinstance(meta.get(k),str) and meta[k] for k in ('uid','resourceVersion'))
        and not meta.get('deletionTimestamp'),'Exact current undeleted resource identity required')
    return meta


def cas(obj,path,old,new):
    meta=obj['metadata']
    return [{'op':'test','path':'/metadata/uid','value':meta['uid']},
        {'op':'test','path':'/metadata/resourceVersion','value':meta['resourceVersion']},
        {'op':'test','path':path,'value':copy.deepcopy(old)},
        {'op':'replace','path':path,'value':copy.deepcopy(new)}]


def operator_state(operator,pods):
    identity(operator,('apps/v1','Deployment','kai-scheduler','kai-operator'))
    require(operator.get('spec',{}).get('replicas')==0
        and type(operator['spec']['replicas']) is int,'Operator must be explicitly paused')
    status=operator.get('status',{})
    generation=operator['metadata'].get('generation')
    require(type(generation) is int and status.get('observedGeneration')==generation
        and all(status.get(k,0)==0 for k in ('replicas','readyReplicas','availableReplicas','updatedReplicas')),
        'Actual observed zero operator replicas required')
    require(isinstance(pods,list) and not pods,'Actual operator Pod list must be empty, including terminating Pods')


def inputs(config,operator,pods,resources):
    identity(config,('kai.scheduler/v1','Config','','kai-config'));operator_state(operator,pods)
    require(not any(config.get('spec',{}).get(scope,{}).get('vpa',{}).get('enabled',False)
        for scope in ('global','binder')),'Enabled VPA needs a separately reviewed operand handover')
    require(isinstance(resources,list) and len(resources) in (len(RESOURCES),len(RESOURCES)+1),
        'Exact required binder operands and optional binder PDB required')
    seen=set();identities=set();binder=None
    for obj in resources:
        meta=obj.get('metadata',{});expected=(obj.get('apiVersion'),obj.get('kind'),meta.get('namespace',''),meta.get('name'))
        require(expected in (*RESOURCES,OPTIONAL) and expected not in identities,'Unexpected or duplicate operand')
        meta=identity(obj,expected);require(meta['uid'] not in seen,'Distinct operand UIDs required');seen.add(meta['uid']);identities.add(expected)
        if expected==RESOURCES[0]:binder=obj
    require(set(RESOURCES)<=identities,'Missing required binder operand')
    require(binder.get('spec',{}).get('strategy')=={'type':'Recreate'}
        and type(binder['spec'].get('replicas')) is int and binder['spec']['replicas']==1,
        'Single Recreate binder required; never overlap stock and successor')


def pause_patch(operator):
    identity(operator,('apps/v1','Deployment','kai-scheduler','kai-operator'))
    require(type(operator.get('spec',{}).get('replicas')) is int and operator['spec']['replicas']==1,
        'Exactly one current operator required')
    return cas(operator,'/spec/replicas',1,0)


def detach_intent(config,operator,operator_pods,resources):
    inputs(config,operator,operator_pods,resources)
    require(config.get('spec',{}).get('binder',{}).get('service',{}).get('enabled') is True,
        'Enabled stock binder operand required before transfer')
    output=[]
    for resource in resources:
        meta=resource['metadata'];owners=meta.get('ownerReferences')
        require(isinstance(owners,list) and len(owners)==1,'One exact Config controller owner required')
        owner=owners[0]
        require(all(owner.get(k)==v for k,v in {'apiVersion':'kai.scheduler/v1','kind':'Config',
            'name':'kai-config','uid':config['metadata']['uid'],'controller':True}.items()),
            'Binder operand must be owned by the captured Config')
        labels=meta.get('labels',{});require(isinstance(labels,dict)
            and labels.get('app.kubernetes.io/managed-by','kai-operator')=='kai-operator','Conflicting management label')
        patch=cas(resource,'/metadata/ownerReferences',owners,[])
        if 'labels' in meta:patch.append({'op':'test','path':'/metadata/labels','value':copy.deepcopy(labels)})
        patch.append({'op':'replace' if 'labels' in meta else 'add','path':'/metadata/labels',
            'value':{**labels,'app.kubernetes.io/managed-by':MANAGER}})
        output.append({'apiVersion':resource['apiVersion'],'kind':resource['kind'],
            'namespace':meta['namespace'],'name':meta['name'],'patch':patch})
    return {'resource_patches':output,'config_patch':cas(config,'/spec/binder/service/enabled',True,False),
        'apply_order':['resource_patches','config_patch'],'live_operations':False}


def resume_patch(config,operator,operator_pods,resources):
    inputs(config,operator,operator_pods,resources)
    require(config.get('spec',{}).get('binder',{}).get('service',{}).get('enabled') is False,
        'Disable stock binder reconciliation before resuming operator')
    for resource in resources:
        meta=resource['metadata']
        require(meta.get('ownerReferences',[])==[] and meta.get('labels',{}).get('app.kubernetes.io/managed-by')==MANAGER,
            'Fresh readback of every transferred operand required before operator resume')
    return cas(operator,'/spec/replicas',0,1)
