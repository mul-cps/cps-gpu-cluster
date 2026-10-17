"""GET-only actual held/ready process-role CAS capture. Never patches."""
import argparse,copy,json,os
from pathlib import Path
from publication import COMPONENTS,cas,require,save
import subprocess

def get(kind,ns,name):return json.loads(subprocess.check_output(['kubectl','-n',ns,'get',kind,name,'-o','json'],timeout=30))

def bind(deployment,pod,rs,role,*,container,held=False):
    ns=deployment['metadata']['namespace'];spec=deployment['spec']['template']['spec']
    require(not any(x['metadata'].get('deletionTimestamp') for x in (deployment,pod,rs,role)),'Deleting process/role')
    require(pod['metadata']['namespace']==rs['metadata']['namespace']==role['metadata']['namespace']==ns,'Process namespaces differ')
    owner=next(o for o in pod['metadata']['ownerReferences'] if o.get('controller'));parent=next(o for o in rs['metadata']['ownerReferences'] if o.get('controller'))
    require(owner['kind']=='ReplicaSet' and owner['name']==rs['metadata']['name'] and owner['uid']==rs['metadata']['uid'],'Actual Pod owner chain differs')
    require(parent['kind']=='Deployment' and parent['name']==deployment['metadata']['name'] and parent['uid']==deployment['metadata']['uid'],'Actual ReplicaSet owner differs')
    expected=next(c['image'] for c in spec['containers'] if c['name']==container)
    require(pod['spec']['serviceAccountName']==spec['serviceAccountName'] and next(c['image'] for c in pod['spec']['containers'] if c['name']==container)==expected,'Process image/service account differs')
    if held:
        expected_bootstrap=next(v['configMap']['name'] for v in spec['volumes'] if v['name']=='packaged-bootstrap-input')
        require(next(v['configMap']['name'] for v in pod['spec'].get('volumes',[]) if v['name']=='packaged-bootstrap-input')==expected_bootstrap,
                'Selected held Pod bootstrap differs from current Deployment')
        require(container=='node-agent' and pod['spec']['nodeName']==spec['nodeName'] and not any('running' in c.get('state',{}) for c in pod.get('status',{}).get('containerStatuses',[]) if c['name']==container),'Node must remain held before main service runs')
    else:
        status=next(c for c in pod['status']['containerStatuses'] if c['name']==container)
        require(status['ready'] is True and 'running' in status['state'] and status['imageID'].removeprefix('docker-pullable://').removeprefix('docker://')==expected,'Actual imageID/process not ready')
    rules=copy.deepcopy(role['rules']);seen=set()
    for row in rules:
        if row.get('resources') in (['pods'],['replicasets']):
            require(row.get('verbs')==['get'] and isinstance(row.get('resourceNames'),list),'Only closed namedGET may bind')
            name=pod['metadata']['name'] if row['resources']==['pods'] else rs['metadata']['name']
            row['resourceNames']=[name] if held else sorted(set(row['resourceNames'])|{name});seen.add(row['resources'][0])
    require(seen=={'pods','replicasets'},'Named Pod/ReplicaSet rules missing')
    return cas(role,'/rules',rules)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture-process',action='store_true');p.add_argument('--component',choices=COMPONENTS);p.add_argument('--pod');p.add_argument('--held-node',action='store_true');p.add_argument('--snapshot',type=Path);p.add_argument('--output',type=Path);a=p.parse_args(argv)
    if not a.capture_process:print('{"inert":true,"live_writes":false}');return
    require(a.component and a.pod and a.snapshot and a.output,'Actual explicit Pod and baseline snapshot required');require(not a.held_node or a.component=='node','Only Node may be held')
    baseline=json.loads(a.snapshot.read_text());old=baseline['deployments'][a.component];ns,name,container=COMPONENTS[a.component];dep=get('deployment',ns,name)
    require(dep['metadata']['uid']==old['metadata']['uid'] and dep['spec']['template']['spec']['containers']==old['spec']['template']['spec']['containers'],'Controller/image/runtime changed')
    if a.held_node:
        v=next(v for v in dep['spec']['template']['spec']['volumes'] if v['name']=='packaged-bootstrap-input')
        require(get('configmap',ns,v['configMap']['name'])['data']['release']=='false','Actual bootstrap must remain releasefalse')
    pod=get('pod',ns,a.pod);owner=next(o for o in pod['metadata']['ownerReferences'] if o.get('controller'));rs=get('replicaset',ns,owner['name'])
    os.umask(0o077);a.output.mkdir(mode=0o700,exist_ok=False)
    names=['cps-native-approval-node'] if a.held_node else ['cps-native-approval-gateway']+(['cps-native-approval-hub-'+a.component.split(':')[1]] if a.component.startswith('hub:') else [])
    for role_name in names:
        role=get('role',ns,role_name);save(a.output,role_name+'.preimage.private.json',role);save(a.output,role_name+'.patch.private.json',bind(dep,pod,rs,role,container=container,held=a.held_node))
    for k,v in [('deployment',dep),('pod',pod),('replicaset',rs)]:save(a.output,k+'.private.json',v)
    print(json.dumps({'actual_pod_uid':pod['metadata']['uid'],'held_node':a.held_node,'role_patches':len(names),'live_writes':False}))
if __name__=='__main__':main()
