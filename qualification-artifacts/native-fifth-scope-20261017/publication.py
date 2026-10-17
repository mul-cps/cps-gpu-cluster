"""Read-only capture / pure packaged-node publication renderer. Default inert.

No apply, Secret mutation, Pod exec, process signaling, driver or GPU operations.
Authenticated export acquisition and actual creates/rollouts are Root operations.
"""
import argparse,base64,copy,hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
import subprocess

BASE=Path(__file__).resolve().parent
COMPONENTS={'gateway':('cps-compute','compute-gateway','gateway'),
            'hub:cps':('jupyterhub','hub','hub'),'hub:cit':('cit-jhub','hub','hub'),
            'node':('cps-native-system','cps-native-node-agent','node-agent')}

def require(ok,message):
    if not ok:raise ValueError(message)

def raw(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def sha(x):return 'sha256:'+hashlib.sha256(raw(x).encode()).hexdigest()
def save(directory,name,x):
    fd=os.open(directory/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as f:json.dump(x,f,sort_keys=True,indent=2);f.write('\n')
def cm(namespace,prefix,data,immutable=True):
    obj={'apiVersion':'v1','kind':'ConfigMap','metadata':{'namespace':namespace,'name':prefix+'-'+sha(data)[7:23]},'data':data}
    if immutable:obj['immutable']=True
    return obj

def cas(obj,path,value):
    old=obj
    for part in path.strip('/').split('/'):old=old[part]
    return [{'op':'test','path':'/metadata/uid','value':obj['metadata']['uid']},
            {'op':'test','path':'/metadata/resourceVersion','value':obj['metadata']['resourceVersion']},
            {'op':'test','path':path,'value':old},{'op':'replace','path':path,'value':value}]

def key(kind,ns,name):return kind+'/'+ns+'/'+name

def capture(directory):
    objects={}
    def get(kind,ns,name):
        k=key(kind,ns,name)
        if k not in objects:
            command=['kubectl']+(['-n',ns] if ns else [])+['get',kind,name,'-o','json']
            objects[k]=json.loads(subprocess.check_output(command,timeout=30))
        return objects[k]
    deployments={}
    for component,(ns,name,container) in COMPONENTS.items():
        dep=get('deployment',ns,name);deployments[component]=dep
        spec=dep['spec']['template']['spec'];get('serviceaccount',ns,spec['serviceAccountName'])
        for v in spec.get('volumes',[]):
            if 'configMap' in v and v['name'] in ('cps-native-approval-document','cps-native-approval-reference','cps-native-approval-publisher','cps-native-hub-config','packaged-bootstrap-input'):
                obj=get('configmap',ns,v['configMap']['name'])
                if v['name']=='packaged-bootstrap-input':
                    ref=json.loads(obj['data']['config-ref.json']);node=get('configmap',ref['namespace'],ref['name']);body=json.loads(node['data'][ref['key']])
                    q=body['qualification_ref'];deployment=get('configmap',q['namespace'],q['name']);proof=json.loads(deployment['data'][q['key']])['qualification_ref'];get('configmap',proof['namespace'],proof['name'])
                    terminal=body['terminal_index_ref'];get('configmap',terminal['namespace'],terminal['name'])
        for role_name in ['cps-native-approval-gateway']+(['cps-native-approval-hub-'+component.split(':')[1]] if component.startswith('hub:') else ['cps-native-approval-node'] if component=='node' else []):get('role',ns,role_name)
    runtime=get('secret','cps-compute','cps-compute-runtime');r=json.loads(base64.b64decode(runtime['data']['runtime.json']))
    pin=r['nativeGpuGroups']['qualification_ref'];get('configmap',pin['namespace'],pin['name'])
    get('configmap','cps-compute','compute-policy');get('configmap','cps-native-system','cps-native-gpu-allocations')
    snapshot={'version':1,'captured_at':datetime.now(timezone.utc).isoformat(),'objects':objects,'deployments':deployments}
    save(directory,'snapshot.private.json',snapshot)
    print(json.dumps({'readonly_captured_objects':len(objects),'live_writes':False}))

def volume(snapshot,component,name):
    dep=snapshot['deployments'][component];ns=dep['metadata']['namespace'];v=next(x for x in dep['spec']['template']['spec']['volumes'] if x['name']==name)
    return snapshot['objects'][key('configmap',ns,v['configMap']['name'])]

def context(snapshot):
    from cps_compute.policy import Policy
    from cps_compute.native_groups import NativeGroupDeployment
    from cps_compute.native_qualification_authority import NativeQualificationAuthority
    o=snapshot['objects'];runtime=json.loads(base64.b64decode(o[key('secret','cps-compute','cps-compute-runtime')]['data']['runtime.json']))
    policy_data=o[key('configmap','cps-compute','compute-policy')]['data'];policy=Policy(json.loads(policy_data.get('catalog.json',next(iter(policy_data.values())))))
    config=runtime['nativeGpuGroups'];pin=config['qualification_ref'];proof=o[key('configmap',pin['namespace'],pin['name'])]
    authority=NativeQualificationAuthority.from_configmap(proof,pin,policy)
    group=NativeGroupDeployment.from_config(config,policy,authority=authority)
    return policy,group

def document_candidates(snapshot,packet,expected_revision,now,fixture):
    from cps_compute.native_group_capture_protocol import validate_capture,json_document
    from cps_compute.native_group_approvals import ApprovalSnapshot
    from cps_compute.native_group_revision import ApprovalRevision,approval_envelope
    packet=validate_capture(packet);require(packet['trusted_revision']==expected_revision,'Actual capture revision differs from explicit operator pin')
    captured=datetime.fromisoformat(packet['captured_at'].replace('Z','+00:00'))
    require(0<=(now-captured).total_seconds()<=120,'Fresh authenticated capture required')
    policy,group=context(snapshot)
    previous={component:ApprovalRevision.from_configmap(volume(snapshot,component,'cps-native-approval-document'),policy,group) for component in COMPONENTS}
    old=previous['node'].document
    require(all(doc.document==old for doc in previous.values()),'All four old projections must match')
    require(old['revision']==fixture['expected_revision'],'Fixture baseline head changed')
    approved=ApprovalSnapshot.from_document(json_document(packet['source_raw']),policy,group,expected_revision=expected_revision)
    new=approved.document;before=old['registry'];scope='cps:'+fixture['workspace']
    require(new['generation']==before['generation']+1,'Exactly one new server-owned generation required')
    olddep,newdep=before['deployment'],new['deployment']
    require({k:v for k,v in newdep.items() if k!='workspaces'}=={k:v for k,v in olddep.items() if k!='workspaces'},'Policy, qualification, pool, caps or image changed')
    require(set(newdep['workspaces'])==set(olddep['workspaces'])|{scope} and scope not in olddep['workspaces'],'Only explicit fifth scope may be added')
    require(all(newdep['workspaces'][k]==v for k,v in olddep['workspaces'].items()),'Existing approvals changed')
    added=newdep['workspaces'][scope]
    require(added['members']==sorted(p['canonical_person_id'] for p in fixture['people']) and added['profiles']==['interactive-shared-5']
            and added['owner']==fixture['owner'] and added['pod']==fixture['pod'] and added['server']=='rtc'
            and added['course_id']==fixture['course'] and added['term_id']==fixture['term'] and added['group_id']==fixture['group']
            and added['ceiling']==fixture['ceiling'] and added['namespace']=='jupyterhub'
            and added['storage']['storage_version']==2 and added['storage']['path']==fixture['expected_storage_path'], 'New scope differs from reviewed fixture')
    history=old['history']+[previous[c].reference for c in COMPONENTS]
    envelope=approval_envelope(approved,history)
    data={'approval.json':raw(envelope)}
    return {c:cm(ns,'cps-native-approvals',data) for c,(ns,_,_) in COMPONENTS.items()},policy,group

def actual_references(candidates,created,policy,group):
    from cps_compute.native_group_revision import ApprovalRevision
    objects=created['items'] if created.get('kind')=='List' else created
    require(isinstance(objects,list) and len(objects)==4,'Four actual API-created approval objects required')
    result={}
    for component,candidate in candidates.items():
        actual=[x for x in objects if x['metadata']['namespace']==candidate['metadata']['namespace'] and x['metadata']['name']==candidate['metadata']['name']]
        require(len(actual)==1 and actual[0].get('immutable') is True and actual[0]['data']==candidate['data'],'Actual approval identity/content mismatch')
        result[component]=ApprovalRevision.from_configmap(actual[0],policy,group).reference
    return result

def stage(snapshot,candidates,refs):
    outputs={};roles={}
    for component,(ns,_,_) in COMPONENTS.items():
        dep=snapshot['deployments'][component]
        if component!='node':
            refcm=cm(ns,'cps-native-approval-reference',{'reference.json':raw(refs[component])})
            outputs[component+'.reference.create']=refcm
            desired=copy.deepcopy(dep['spec']['template'])
            for v in desired['spec']['volumes']:
                if v['name']=='cps-native-approval-document':v['configMap']['name']=candidates[component]['metadata']['name']
                if v['name']=='cps-native-approval-reference':v['configMap']['name']=refcm['metadata']['name']
            outputs[component+'.deployment.patch']=cas(dep,'/spec/template',desired)
        own='cps-native-approval-gateway' if component=='gateway' else 'cps-native-approval-hub-'+component.split(':')[1] if component.startswith('hub:') else 'cps-native-approval-node'
        names=[own]+(['cps-native-approval-gateway'] if component!='gateway' else [])
        for name in names:
            role=snapshot['objects'][key('role',ns,name)];rules=copy.deepcopy(role['rules'])
            rows=[r for r in rules if r.get('resources')==['configmaps'] and r.get('verbs')==['get'] and 'resourceNames' in r]
            require(rows,'Closed named ConfigMap GET rule required')
            rows[0]['resourceNames']=sorted(set(rows[0]['resourceNames'])|{candidates[component]['metadata']['name']})
            roles[ns+'.'+name]= (role,rules)
    bootstrap=volume(snapshot,'node','packaged-bootstrap-input');oldref=json.loads(bootstrap['data']['config-ref.json'])
    old=snapshot['objects'][key('configmap',oldref['namespace'],oldref['name'])]
    node=json.loads(old['data']['config.json']);new=copy.deepcopy(node);new['approval_ref']=refs['node']
    require(node['version']==3 and node['enabled'] is True,'Actual enabled packaged v3 node required')
    candidate=cm(old['metadata']['namespace'],'cps-packaged-node-config-v3',{'config.json':raw(new)})
    outputs['node-config.create']=candidate
    role,rules=roles[old['metadata']['namespace']+'.cps-native-approval-node']
    row=next(r for r in rules if r.get('resources')==['configmaps'] and r.get('verbs')==['get']);row['resourceNames']=sorted(set(row['resourceNames'])|{candidate['metadata']['name']})
    for name,(role,rules) in roles.items():outputs[name+'.role.patch']=cas(role,'/rules',rules)
    return outputs

def bind_node(snapshot,candidates,node_candidate,actual,stopped=None):
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    require(actual['metadata']['namespace']==node_candidate['metadata']['namespace'] and actual['metadata']['name']==node_candidate['metadata']['name'] and actual['data']==node_candidate['data'],'Actual node config differs')
    ref=ImmutableConfigMapRef.from_dict({**{k:actual['metadata'][k] for k in ('namespace','name','uid','resourceVersion')},'key':'config.json','data_sha256':sha(actual['data'])})
    ref.validate(actual)
    oldbootstrap=volume(snapshot,'node','packaged-bootstrap-input');data=copy.deepcopy(oldbootstrap['data']);data['config-ref.json']=raw(ref.to_dict());data['release']='false'
    bootstrap=cm(actual['metadata']['namespace'],'cps-packaged-node-bootstrap',data,immutable=False)
    dep=snapshot['deployments']['node'];desired=copy.deepcopy(dep['spec'])
    for v in desired['template']['spec']['volumes']:
        if v['name']=='packaged-bootstrap-input':v['configMap']['name']=bootstrap['metadata']['name']
        if v['name']=='cps-native-approval-document':v['configMap']['name']=candidates['node']['metadata']['name']
    require(next(c for c in desired['template']['spec']['containers'] if c['name']=='node-agent')['command']==['python','-m','cps_compute.native_node.service'],'Packaged service command changed')
    require(desired['strategy']['type']=='Recreate','Single node writer Recreate required')
    preimage=dep
    if stopped is not None:
        expected=copy.deepcopy(dep['spec']);expected['replicas']=0
        require(stopped['metadata']['uid']==dep['metadata']['uid'] and stopped['spec']==expected,
                'Stopped Deployment differs beyond replicas0; fresh review required')
        preimage=stopped
    return {'node-bootstrap.create':bootstrap,'node-deployment.patch':cas(preimage,'/spec',desired)}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',action='store_true');p.add_argument('--snapshot',type=Path);p.add_argument('--packet',type=Path);p.add_argument('--packet-sha256');p.add_argument('--expected-revision');p.add_argument('--fixture',type=Path);p.add_argument('--created-approvals',type=Path);p.add_argument('--created-node-config',type=Path);p.add_argument('--stopped-node-deployment',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args(argv)
    if not a.capture and not a.packet:print('{"inert":true,"live_writes":false}');return
    require(a.output is not None,'Fresh private output directory required');os.umask(0o077);a.output.mkdir(mode=0o700,exist_ok=False)
    if a.capture:capture(a.output);return
    from cps_compute.native_group_capture_protocol import private_bytes,json_document
    require(a.snapshot and a.packet_sha256 and a.expected_revision and a.fixture,'Explicit trusted capture pins and fixture required')
    packet_raw=private_bytes(a.packet,maximum=8*1024*1024);require('sha256:'+hashlib.sha256(packet_raw).hexdigest()==a.packet_sha256,'Raw authenticated capture pin differs')
    snapshot=json_document(private_bytes(a.snapshot,maximum=32*1024*1024),maximum=32*1024*1024)
    fixture=json_document(private_bytes(a.fixture,maximum=1024*1024));packet=json_document(packet_raw)
    candidates,policy,group=document_candidates(snapshot,packet,a.expected_revision,datetime.now(timezone.utc),fixture)
    save(a.output,'approval-documents.create.private.json',{'apiVersion':'v1','kind':'List','items':list(candidates.values())})
    if a.created_approvals:
        refs=actual_references(candidates,json_document(private_bytes(a.created_approvals,maximum=8*1024*1024)),policy,group)
        outputs=stage(snapshot,candidates,refs)
        if a.created_node_config:outputs.update(bind_node(snapshot,candidates,outputs['node-config.create'],json_document(private_bytes(a.created_node_config,maximum=8*1024*1024)),json_document(private_bytes(a.stopped_node_deployment,maximum=8*1024*1024)) if a.stopped_node_deployment else None))
        for name,obj in outputs.items():save(a.output,name+'.private.json',obj)
    print(json.dumps({'revision':a.expected_revision,'documents':4,'packaged_node':True,'live_writes':False}))

if __name__=='__main__':main()
