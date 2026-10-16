"""Inert CPS-only Hub configuration/hook handover for the pinned operator pair."""
import ast
import base64
import copy
import hashlib
import json

import yaml
import node_agent as agent
import qualification_transition_proposal as transition
import gateway_transition


def owner(obj,kind):
    meta=transition.object_guard(obj,kind)
    agent.require(obj.get('apiVersion')==('apps/v1' if kind=='Deployment' else 'v1')
        and meta.get('namespace')=='jupyterhub' and meta['uid']!='00000000-0000-0000-0000-000000000000'
        and not meta.get('deletionTimestamp'),'Actual CPS Hub ownership required')
    return meta


def values(raw):
    class Unique(yaml.SafeLoader):pass
    def mapping(loader,node,deep=False):
        loader.flatten_mapping(node);result={}
        for key_node,value_node in node.value:
            key=loader.construct_object(key_node,deep=deep)
            agent.require(key not in result,'Duplicate complete Hub YAML key')
            result[key]=loader.construct_object(value_node,deep=deep)
        return result
    Unique.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,mapping)
    result=yaml.load(raw,Loader=Unique)
    agent.require(isinstance(result,dict),'Complete Hub YAML mapping required')
    return result


def forward_intent(*,gateway_inputs,originals):
    gateway_transition.forward_intent(**gateway_inputs)
    agent.closed(originals,{'config','secret','deployment'},'Full CPS Hub configuration, Secret and Deployment required')
    for key,kind in [('config','ConfigMap'),('secret','Secret'),('deployment','Deployment')]:owner(originals[key],kind)
    config=originals['config'];secret=originals['secret'];deployment=originals['deployment']
    agent.require(config.get('immutable') is True and not config.get('binaryData')
        and not config['metadata'].get('ownerReferences') and secret['metadata']['name']=='hub',
        'Actual immutable CPS native config and owning Hub Secret required')
    mode=gateway_inputs['proposal']['operator-qualification.json'];policy=gateway_inputs['proposal']['policy.json']
    oldpolicy=agent.parse(gateway_inputs['originals']['policy']['data']['policy.json'])
    runtime=agent.parse(base64.b64decode(gateway_inputs['originals']['runtime']['data']['runtime.json'],validate=True))
    old=agent.parse(config['data']['settings.json'])
    agent.require(old['enabled'] is True and old['source']=='cps' and old['groupDeployment']==runtime['nativeGpuGroups']
        and all(old.get(k,{'enabled':False})=={'enabled':False} for k in ('qualificationDeployment','pilotDeployment'))
        and agent.parse(config['data']['policy.json'])==oldpolicy,'Exact original CPS group settings and catalog required')
    approved=mode['workspaces']
    agent.require(all(scope.startswith('cps:') for scope in approved) and len(approved)==2,'Only the two CPS operator targets required')
    new=copy.deepcopy(old)
    mounts=sorted({(r['server'],r['path'],r['mount_path']) for body in approved.values() for r in body['storage']['readonly_mounts']})
    new.update(groupDeployment={'enabled':False},pilotDeployment={'enabled':False},qualificationDeployment=copy.deepcopy(mode),
        profiles=sorted({p for body in approved.values() for p in body['profiles']}),
        owners=sorted(body['owner'] for body in approved.values()),workspaces=sorted(approved),
        gateImage=mode['gateImage'],workloadImages=[mode['workloadImage']],
        writablePVCClaims=sorted({body['storage']['pvc'] for body in approved.values()}),writableMountPaths=['/workspace'],
        readonlyNFS=[dict(server=s,path=p,mountPath=m) for s,p,m in mounts])
    from cps_compute_hub.native_hub_config import _validate
    _validate({k:v for k,v in new.items() if k not in ('groupDeployment','pilotDeployment','qualificationDeployment')})
    newdata=dict(config['data'],**{'settings.json':transition.canonical(new),'policy.json':transition.canonical(policy)})
    created=transition.immutable_config(config,newdata,'cps-native-hub-qualification')
    before=values(base64.b64decode(secret['data']['values.yaml'],validate=True))
    oldhook=before['hub']['extraConfig']['zz-native-group-pilot']
    agent.require(isinstance(oldhook,str) and hashlib.sha256(oldhook.encode()).hexdigest()==transition.CURRENT_HUB_HOOK_PINS['cps']
        and oldhook.startswith(transition._GROUP_HOOK_PREFIX),'Exact actual CPS native hook required')
    suffix=oldhook[len(transition._GROUP_HOOK_PREFIX):]
    nodes=[n for n in ast.parse(suffix).body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='_native_pull_owners' for t in n.targets)]
    agent.require(len(nodes)==1 and isinstance(nodes[0].value,ast.Call)
        and isinstance(nodes[0].value.func,ast.Name) and nodes[0].value.func.id=='frozenset'
        and len(nodes[0].value.args)==1 and not nodes[0].value.keywords,'One exact native private-image owner assignment required')
    expression=ast.get_source_segment(suffix,nodes[0].value)
    agent.require(suffix.count(expression)==1,'Unique exact private-image owner literal required')
    suffix=suffix.replace(expression,'frozenset('+repr(new['owners'])+')',1)
    newhook=transition._QUALIFICATION_HOOK_PREFIX+suffix
    compile(newhook,'cps-operator-pair-hook','exec')
    after=copy.deepcopy(before);after['hub']['extraConfig']['zz-native-group-pilot']=newhook
    encoded=yaml.safe_dump(after,sort_keys=False,allow_unicode=True).encode()
    agent.require(values(encoded)==after,'Complete Hub YAML semantic round trip required')
    secret_data=dict(secret['data'],**{'values.yaml':base64.b64encode(encoded).decode()})
    spec=copy.deepcopy(deployment['spec']);changed=0
    for volume in spec['template']['spec'].get('volumes',[]):
        if volume.get('configMap',{}).get('name')==config['metadata']['name']:
            volume['configMap']['name']=created['metadata']['name'];changed+=1
    agent.require(changed==1,'One exact CPS native configuration mount required')
    spec['template'].setdefault('metadata',{}).setdefault('annotations',{})['cps.compute/native-qualification-hook']='sha256:'+hashlib.sha256(newhook.encode()).hexdigest()
    return {'version':1,'enabled':False,'live_applied':False,'hardware_qualified':False,'modified_sources':['cps'],
        'configuration.json':created,'secret.patch.json':transition.replace_patch(secret,'/data',secret['data'],secret_data),
        'deployment.patch.json':transition.replace_patch(deployment,'/spec',deployment['spec'],spec),
        'coordinated_gateway_node_source_execution_required':True}


def inverse_intent(*,current,**forward_inputs):
    forward=forward_intent(**forward_inputs);originals=forward_inputs['originals']
    agent.closed(current,{'config','secret','deployment'},'Full fresh CPS Hub readbacks required')
    config=current['config'];meta=owner(config,'ConfigMap');expected=forward['configuration.json']
    agent.require(config.get('immutable') is True and not config.get('binaryData') and not meta.get('ownerReferences')
        and meta['name']==expected['metadata']['name'] and config['data']==expected['data'], 'Actual created immutable CPS configuration must match full forward plan')
    result={'version':1,'enabled':False,'live_applied':False,'hardware_qualified':False,'modified_sources':['cps']}
    for key,kind,file,field in [('secret','Secret','secret.patch.json','data'),('deployment','Deployment','deployment.patch.json','spec')]:
        old=owner(originals[key],kind);actual=owner(current[key],kind)
        agent.require(all(actual[k]==old[k] for k in ('namespace','name','uid'))
            and current[key][field]==forward[file][-1]['value'],'Full fresh CPS Hub object differs from exact forward handover')
        result[file]=transition.replace_patch(current[key],'/'+field,current[key][field],originals[key][field])
    result['coordinated_gateway_node_source_execution_required']=True
    return result
