"""Pure Hub pending-adapter handover; fixtures contain no real credentials."""
import ast
import base64
import copy
import importlib
import json
import uuid

import pytest
import yaml


HOOK='''import asyncio
import json
from pathlib import Path
from cps_compute.native_hub_config import install_native_group_hub_configuration
install_native_group_hub_configuration(c, json.loads(Path('/etc/cps-native-hub/settings.json').read_text()))
_pull_before = c.KubeSpawner.modify_pod_hook
async def _private_pull(spawner, pod):
    pod = await _pull_before(spawner, pod)
    pod['spec']['imagePullSecrets'] = [{'name': 'existing-private-pull'}]
    return pod
c.KubeSpawner.modify_pod_hook = _private_pull
'''


def inputs(source='cps',replicas=1):
    namespace={'cps':'jupyterhub','cit':'cit-jhub'}[source]
    values={'hub':{'extraConfig':{'01-unchanged':'c.JupyterHub.allow_named_servers = True',
        'zz-native-group-pilot':HOOK},'services':{'test':{'apiToken':'synthetic-only'}}},
        'singleuser':{'storage':{'static':{'pvcName':'unchanged-data'}}}}
    secret={'apiVersion':'v1','kind':'Secret','metadata':{'namespace':namespace,'name':'hub',
        'uid':str(uuid.UUID(int=31)),'resourceVersion':'21'},'type':'Opaque','data':{
        'values.yaml':base64.b64encode(yaml.safe_dump(values,sort_keys=False).encode()).decode(),
        'unchanged-key':base64.b64encode(b'synthetic opaque bytes').decode()}}
    spec={'replicas':replicas,'strategy':{'type':'Recreate'},'selector':{'matchLabels':{'app':'hub'}},'template':{
        'metadata':{'labels':{'app':'hub'},'annotations':{'recovery':'preserve-exact'}},'spec':{
            'serviceAccountName':'hub','securityContext':{'runAsUser':1000,'fsGroup':1000},
            'volumes':[{'name':'group-private','emptyDir':{}},{'name':'head-anchor','configMap':{'name':'existing-anchor'}}],
            'initContainers':[{'name':'existing-private-group-inputs','image':'registry.invalid/hub@sha256:'+'a'*64,
                'command':['python','-c','pass'],'volumeMounts':[{'name':'group-private','mountPath':'/private'}]}],
            'containers':[{'name':'hub','image':'registry.invalid/hub@sha256:'+'a'*64,
                'env':[{'name':'CPS_NATIVE_GROUP_APPROVAL_HEAD','value':'/protected/head.json'}],
                'volumeMounts':[{'name':'group-private','mountPath':'/etc/cps-native-hub','readOnly':True},
                    {'name':'head-anchor','mountPath':'/var/run/cps-native-approvals/head-anchor.json','subPath':'anchor.json','readOnly':True}]},
                {'name':'existing-sidecar','image':'registry.invalid/sidecar@sha256:'+'b'*64}]}}}
    deployment={'apiVersion':'apps/v1','kind':'Deployment','metadata':{'namespace':namespace,'name':'hub',
        'uid':str(uuid.UUID(int=32)),'resourceVersion':'22'},'spec':spec}
    from endpoint import projected,AUDIENCE,ORIGIN
    plain={'enabled':True,'source':source,'gatewayUrl':ORIGIN,'gatewayCAFile':'/etc/cps-native-hub/ca.crt',
        'groupDeployment':{'enabled':True,'policy_hash':'sha256:'+'c'*64}}
    hub={'settings':{'enabled':True,'version':2,'groupHub':plain,'coordinator':{'origin':ORIGIN,
        'caFile':plain['gatewayCAFile'],'tokenFile':'/var/run/cps-kai-service/credentials/token','queue':'cps-interactive'}},
        'volumes':[projected('cps-kai-service',AUDIENCE)],'volumeMounts':[{'name':'cps-kai-service',
        'mountPath':'/var/run/cps-kai-service','readOnly':True}],
        'ca_requirement':{'path':plain['gatewayCAFile'],'source_configmap':'cps-compute-gateway-ca','key':'ca.crt'}}
    return deployment,secret,hub


def load():
    try:return importlib.import_module('hub_rollout')
    except ModuleNotFoundError:pytest.fail('Pure pending Hub rollout composer is not implemented')


def created(candidate):
    value=copy.deepcopy(candidate);value['metadata'].update(uid=str(uuid.UUID(int=33)),resourceVersion='23')
    return value


def apply_patch(value,patch):
    value=copy.deepcopy(value)
    for operation in patch:
        path=operation['path'].strip('/').split('/');parent=value
        for key in path[:-1]:parent=parent[key]
        if operation['op']=='test':assert parent[path[-1]]==operation['value']
        else:parent[path[-1]]=copy.deepcopy(operation['value'])
    return value


@pytest.mark.parametrize('source',['cps','cit'])
@pytest.mark.parametrize('replicas',[0,1])
def test_exact_installer_replacement_and_additive_private_mounts_preserve_everything_else(source,replicas):
    module=load();dep,secret,hub=inputs(source,replicas);before=copy.deepcopy((dep,secret,hub))
    cm=created(module.candidate(dep['metadata']['namespace'],hub))
    result=module.compose(dep,secret,hub,cm)
    newdep=apply_patch(dep,result['deployment_patch']);newsecret=apply_patch(secret,result['secret_patch'])
    assert (dep,secret,hub)==before
    oldvalues=yaml.safe_load(base64.b64decode(secret['data']['values.yaml']))
    values=yaml.safe_load(base64.b64decode(newsecret['data']['values.yaml']))
    hook=values['hub']['extraConfig']['zz-native-group-pilot']
    assert 'from cps_compute_hub.native_pending_hub import install_pending_group_hub_configuration' in hook
    assert '/etc/cps-native-kai-hub/config/settings.json' in hook
    assert hook[hook.index('_pull_before ='):]==HOOK[HOOK.index('_pull_before ='):]
    oldvalues['hub']['extraConfig']['zz-native-group-pilot']=hook
    assert values==oldvalues and newsecret['data']['unchanged-key']==secret['data']['unchanged-key']
    assert newsecret|{'data':secret['data']}==secret
    pod=newdep['spec']['template']['spec'];old=dep['spec']['template']['spec']
    assert newdep['spec']['replicas']==replicas and newdep['spec']['template']['metadata']==dep['spec']['template']['metadata']
    assert pod['serviceAccountName']==old['serviceAccountName'] and pod['securityContext']==old['securityContext']
    assert pod['volumes'][:len(old['volumes'])]==old['volumes']
    assert pod['initContainers'][:-1]==old['initContainers']
    assert pod['containers'][1:]==old['containers'][1:]
    assert pod['containers'][0]|{'volumeMounts':old['containers'][0]['volumeMounts']}==old['containers'][0]
    assert pod['initContainers'][-1]['securityContext']['runAsUser']==1000
    assert pod['initContainers'][-1]['image']==old['containers'][0]['image']
    assert pod['containers'][0]['volumeMounts'][-2:]==hub['volumeMounts']+[
        {'name':'cps-native-kai-hub-private','mountPath':'/etc/cps-native-kai-hub','readOnly':True}]
    assert result['configuration_reference']['uid']==cm['metadata']['uid']
    restored=copy.deepcopy(newdep)
    restoredpod=restored['spec']['template']['spec']
    restoredpod['volumes']=copy.deepcopy(old['volumes'])
    restoredpod['initContainers']=copy.deepcopy(old['initContainers'])
    restoredpod['containers'][0]['volumeMounts']=copy.deepcopy(old['containers'][0]['volumeMounts'])
    assert restored==dep  # These are the only allowed Deployment fields.


@pytest.mark.parametrize('fault',['missing','uid','rv','name','namespace','data','mutable','owner'])
def test_activation_requires_actual_created_immutable_cm_readback(fault):
    m=load();dep,secret,hub=inputs();cm=created(m.candidate('jupyterhub',hub))
    if fault=='missing':cm={}
    elif fault=='uid':cm['metadata'].pop('uid')
    elif fault=='rv':cm['metadata']['resourceVersion']=''
    elif fault=='name':cm['metadata']['name']='foreign'
    elif fault=='namespace':cm['metadata']['namespace']='cit-jhub'
    elif fault=='data':cm['data']['settings.json']='{}'
    elif fault=='mutable':cm['immutable']=False
    else:cm['metadata']['ownerReferences']=[{'uid':str(uuid.uuid4())}]
    with pytest.raises(ValueError):m.compose(dep,secret,hub,cm)


@pytest.mark.parametrize('fault',['volume','init','path','mount-name','fsGroup','uid','ca','replicas'])
def test_existing_volume_private_init_or_process_collisions_are_never_overwritten(fault):
    m=load();dep,secret,hub=inputs();pod=dep['spec']['template']['spec'];main=pod['containers'][0]
    if fault=='volume':pod['volumes'].append({'name':'cps-kai-service','emptyDir':{}})
    elif fault=='init':pod['initContainers'][0]['name']='cps-native-kai-hub-inputs'
    elif fault=='path':main['volumeMounts'].append({'name':'existing','mountPath':'/etc/cps-native-kai-hub'})
    elif fault=='mount-name':main['volumeMounts'].append({'name':'cps-native-kai-hub-private','mountPath':'/other'})
    elif fault=='fsGroup':pod['securityContext']['fsGroup']=1001
    elif fault=='uid':pod['securityContext']['runAsUser']=1001
    elif fault=='ca':main['volumeMounts'][0]['readOnly']=False
    else:dep['spec']['replicas']=2
    before=copy.deepcopy((dep,secret,hub))
    with pytest.raises(ValueError):m.compose(dep,secret,hub,created(m.candidate('jupyterhub',hub)))
    assert (dep,secret,hub)==before


@pytest.mark.parametrize('fault',['double-import','double-call','path','alias','other-config','shadow-json','shadow-path'])
def test_only_the_single_existing_trusted_installer_can_be_replaced(fault):
    m=load();dep,secret,hub=inputs();v=yaml.safe_load(base64.b64decode(secret['data']['values.yaml']))
    h=v['hub']['extraConfig']['zz-native-group-pilot']
    if fault=='double-import':h+='from cps_compute_hub.native_pending_hub import install_pending_group_hub_configuration\n'
    elif fault=='double-call':h+=h.splitlines()[4]+'\n'
    elif fault=='path':h=h.replace('/etc/cps-native-hub/settings.json','/foreign/settings.json')
    elif fault=='alias':h=h.replace('import install_native_group_hub_configuration','import install_native_group_hub_configuration as other')
    elif fault=='other-config':v['hub']['extraConfig']['unrelated-duplicate']='from cps_compute.native_hub_config import install_native_group_hub_configuration'
    elif fault=='shadow-json':h=h.replace('import json','import json\njson = foreign')
    else:h=h.replace('from pathlib import Path','from other import Path')
    v['hub']['extraConfig']['zz-native-group-pilot']=h
    secret['data']['values.yaml']=base64.b64encode(yaml.safe_dump(v).encode()).decode()
    with pytest.raises(ValueError):m.compose(dep,secret,hub,created(m.candidate('jupyterhub',hub)))


@pytest.mark.parametrize("parent_mode",[0o700,0o2770])
def test_materializer_creates_regular_private_bytes_restarts_and_refuses_mutated_seed(tmp_path,parent_mode):
    import subprocess,sys,stat
    from cps_compute.native_scheduler_coordinator_auth import private_bytes
    m=load();dep,secret,hub=inputs();cm=created(m.candidate('jupyterhub',hub));r=m.compose(dep,secret,hub,cm)
    desired=apply_patch(dep,r['deployment_patch']);init=desired['spec']['template']['spec']['initContainers'][-1]
    seed=tmp_path/'seed';seed.mkdir();(seed/'settings.json').write_text(cm['data']['settings.json'])
    private=tmp_path/'private';private.mkdir();private.chmod(parent_mode)
    code=init['command'][-1].replace('/kai-hub-seed',str(seed)).replace('/kai-hub-private',str(private))
    for _ in range(2):subprocess.run([sys.executable,'-I','-S','-c',code],check=True,capture_output=True)
    directory=private/'config';actual=directory/'settings.json'
    assert stat.S_IMODE(private.stat().st_mode)==parent_mode
    assert stat.S_IMODE(directory.stat().st_mode)==0o700 and stat.S_IMODE(actual.stat().st_mode)==0o600
    assert json.loads(private_bytes(str(actual)))==hub['settings'] and actual.stat().st_nlink==1
    (seed/'settings.json').write_text('{}')
    assert subprocess.run([sys.executable,'-I','-S','-c',code],capture_output=True).returncode!=0
    assert json.loads(actual.read_bytes())==hub['settings']


def test_cas_refuses_stale_secret_and_deployment_preimages():
    m=load();dep,secret,hub=inputs();result=m.compose(dep,secret,hub,created(m.candidate('jupyterhub',hub)))
    assert [p['path'] for p in result['secret_patch']]==['/metadata/uid','/metadata/resourceVersion','/data','/data']
    assert [p['path'] for p in result['deployment_patch']]==['/metadata/uid','/metadata/resourceVersion','/spec','/spec']
    for original,key in ((secret,'secret_patch'),(dep,'deployment_patch')):
        for field in ('uid','resourceVersion'):
            stale=copy.deepcopy(original);stale['metadata'][field]='changed'
            with pytest.raises(AssertionError):apply_patch(stale,result[key])
        stale=copy.deepcopy(original)
        if key=='secret_patch':stale['data']['untouched']='changed'
        else:stale['spec']['replicas']=0
        with pytest.raises(AssertionError):apply_patch(stale,result[key])


@pytest.mark.parametrize('source',['cps','cit'])
def test_nested_token_path_requires_new_wrapper_and_rotation_safe_whole_volume(source):
    m=load();dep,secret,hub=inputs(source)
    hub['settings']['coordinator']['tokenFile']='/var/run/cps-kai-service/credentials/token'
    namespace=dep['metadata']['namespace']
    old_settings=copy.deepcopy(hub['settings'])
    old_settings['coordinator']['tokenFile']='/var/run/cps-kai-service/token'
    old_data={'settings.json':m.canonical(old_settings)}
    old_cm=created({'apiVersion':'v1','kind':'ConfigMap','metadata':{'namespace':namespace,
        'name':'cps-native-kai-hub-settings-'+m.digest(old_data)[7:23]},'immutable':True,'data':old_data})
    candidate=m.candidate(namespace,hub)
    assert candidate['metadata']['name']!=old_cm['metadata']['name']
    cm=created(candidate);result=m.compose(dep,secret,hub,cm)
    assert json.loads(cm['data']['settings.json'])['coordinator']['tokenFile']=='/var/run/cps-kai-service/credentials/token'
    with pytest.raises(ValueError):m.compose(dep,secret,hub,old_cm)
    old_hub=copy.deepcopy(hub);old_hub['settings']=old_settings
    with pytest.raises(ValueError):m.candidate(namespace,old_hub)
    pod=apply_patch(dep,result['deployment_patch'])['spec']['template']['spec']
    mounts=[mount for mount in pod['containers'][0]['volumeMounts']if mount['name']=='cps-kai-service']
    assert mounts==[{'name':'cps-kai-service','mountPath':'/var/run/cps-kai-service','readOnly':True}]
    assert not any('subPath' in mount or 'subPathExpr' in mount for mount in mounts)
    projected=next(v for v in pod['volumes']if v['name']=='cps-kai-service')['projected']
    token=[s['serviceAccountToken']for s in projected['sources']if 'serviceAccountToken'in s]
    assert len(token)==1 and token[0]['path']=='credentials/token'
