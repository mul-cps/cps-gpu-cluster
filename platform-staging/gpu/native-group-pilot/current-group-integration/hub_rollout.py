"""Pure pending-Hub handover. Returns CREATE/CAS inputs; performs no I/O."""
import ast
import base64
from copy import deepcopy
import hashlib
import json
import re
import uuid

from endpoint import AUDIENCE, ORIGIN, projected

OLD_MODULE='cps_compute.native_hub_config'
OLD_INSTALLER='install_native_group_hub_configuration'
NEW_MODULE='cps_compute_hub.native_pending_hub'
NEW_INSTALLER='install_pending_group_hub_configuration'
OLD_PATH='/etc/cps-native-hub/settings.json'
PRIVATE='/etc/cps-native-kai-hub'
NEW_PATH=PRIVATE+'/config/settings.json'
SEED='cps-native-kai-hub-seed'
DATA='cps-native-kai-hub-private'
INIT='cps-native-kai-hub-inputs'
HOOK='zz-native-group-pilot'


def require(value,message):
    if not value:raise ValueError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def digest(value):return 'sha256:'+hashlib.sha256(canonical(value).encode()).hexdigest()


def identity(obj,kind,namespace):
    meta=obj.get('metadata',{}) if isinstance(obj,dict) else {}
    require(obj.get('kind')==kind and obj.get('apiVersion')==('apps/v1' if kind=='Deployment' else 'v1')
        and meta.get('namespace')==namespace and meta.get('name')=='hub'
        and not meta.get('deletionTimestamp') and not meta.get('ownerReferences'), 'Actual owning Hub object required')
    try:valid=str(uuid.UUID(meta['uid']))==meta['uid'] and uuid.UUID(meta['uid']).int!=0
    except (ValueError,TypeError,KeyError,AttributeError):valid=False
    require(valid and isinstance(meta.get('resourceVersion'),str) and re.fullmatch(r'[1-9][0-9]*',meta['resourceVersion']),
        'Actual Hub UID and resourceVersion required')
    return meta


def settings(namespace,hub):
    require(isinstance(hub,dict) and set(hub)=={'settings','volumes','volumeMounts','ca_requirement'},
        'Exact endpoint-emitted Hub fragment required')
    wrapper=hub['settings']
    require(isinstance(wrapper,dict) and set(wrapper)=={'enabled','version','groupHub','coordinator'}
        and wrapper['enabled'] is True and type(wrapper['version']) is int and wrapper['version']==2,
        'Explicit pending-group Hub settings version2 required')
    plain=wrapper['groupHub'];remote=wrapper['coordinator']
    require(isinstance(plain,dict) and plain.get('enabled') is True and plain.get('source') in ('cps','cit')
        and namespace=={'cps':'jupyterhub','cit':'cit-jhub'}[plain['source']], 'Source-owned Hub namespace required')
    require(isinstance(remote,dict) and set(remote)=={'origin','caFile','tokenFile','queue'}
        and remote['origin']==plain.get('gatewayUrl')==ORIGIN
        and remote['caFile']==plain.get('gatewayCAFile')=='/etc/cps-native-hub/ca.crt'
        and remote['tokenFile']=='/var/run/cps-kai-service/token'
        and isinstance(remote['queue'],str) and re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',remote['queue']),
        'Existing trusted TLS, CA, token path and bounded queue required')
    require(hub['volumes']==[projected('cps-kai-service',AUDIENCE)]
        and hub['volumeMounts']==[{'name':'cps-kai-service','mountPath':'/var/run/cps-kai-service','readOnly':True}]
        and hub['ca_requirement']=={'path':remote['caFile'],'source_configmap':'cps-compute-gateway-ca','key':'ca.crt'},
        'Exact signed-token projection and existing public CA requirement required')
    return deepcopy(wrapper)


def candidate(namespace,hub):
    data={'settings.json':canonical(settings(namespace,hub))}
    name='cps-native-kai-hub-settings-'+digest(data)[7:23]
    return {'apiVersion':'v1','kind':'ConfigMap','metadata':{'namespace':namespace,'name':name},'immutable':True,'data':data}


def actual_reference(actual,expected):
    meta=actual.get('metadata',{}) if isinstance(actual,dict) else {}
    try:valid=str(uuid.UUID(meta['uid']))==meta['uid'] and uuid.UUID(meta['uid']).int!=0
    except (ValueError,TypeError,KeyError,AttributeError):valid=False
    require(isinstance(actual,dict) and actual.get('apiVersion')=='v1' and actual.get('kind')=='ConfigMap'
        and actual.get('immutable') is True and not actual.get('binaryData') and actual.get('data')==expected['data']
        and all(meta.get(k)==expected['metadata'][k] for k in ('namespace','name')) and valid
        and isinstance(meta.get('resourceVersion'),str) and re.fullmatch(r'[1-9][0-9]*',meta['resourceVersion'])
        and not any(meta.get(k) for k in ('ownerReferences','deletionTimestamp','labels','annotations','finalizers')),
        'Actual API-created immutable wrapper identity and exact data required before activation')
    return {k:meta[k] for k in ('namespace','name','uid','resourceVersion')}|{'key':'settings.json','data_sha256':digest(actual['data'])}


def replace_hook(raw):
    require(isinstance(raw,str) and 0<len(raw.encode())<=65536,'Bounded existing native installer hook required')
    try:tree=ast.parse(raw)
    except (SyntaxError,ValueError):raise ValueError('Valid existing native installer hook required') from None
    imports=[n for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and (
        n.module in (OLD_MODULE,NEW_MODULE) or any(a.name in (OLD_INSTALLER,NEW_INSTALLER) for a in n.names))]
    require(len(imports)==1 and imports[0] in tree.body and imports[0].module==OLD_MODULE
        and imports[0].level==0 and len(imports[0].names)==1 and imports[0].names[0].name==OLD_INSTALLER
        and imports[0].names[0].asname is None, 'Exactly one existing direct installer import required')
    require(not any(isinstance(n,ast.Import) and any(a.name in (OLD_MODULE,NEW_MODULE) for a in n.names)
        for n in ast.walk(tree)), 'No duplicate module installer imports permitted')
    calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)
        and n.func.id in (OLD_INSTALLER,NEW_INSTALLER)]
    expected=ast.parse("install_native_group_hub_configuration(c, json.loads(Path('/etc/cps-native-hub/settings.json').read_text()))").body[0].value
    require(len(calls)==1 and any(isinstance(n,ast.Expr) and n.value is calls[0] for n in tree.body)
        and ast.dump(calls[0])==ast.dump(expected),'Exactly one existing canonical installer call/path required')
    call=calls[0]
    paths_import=[n for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and any(a.name=='Path' for a in n.names)]
    require(len(paths_import)==1 and paths_import[0] in tree.body and paths_import[0].module=='pathlib'
        and paths_import[0].level==0 and paths_import[0].lineno<call.lineno
        and len(paths_import[0].names)==1 and paths_import[0].names[0].asname is None,
        'Existing direct pathlib Path import required')
    json_imports=[(n,a) for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names if a.name=='json' or a.asname=='json']
    require(len(json_imports)==1 and json_imports[0][0] in tree.body and json_imports[0][0].lineno<call.lineno
        and json_imports[0][1].name=='json' and json_imports[0][1].asname is None,
        'Existing unaliased json import required')
    require(not any(isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store) and n.id in ('Path','json',OLD_INSTALLER,NEW_INSTALLER)
        for n in ast.walk(tree)), 'Installer inputs cannot be shadowed')
    require(sum(isinstance(n,ast.Name) and n.id==OLD_INSTALLER for n in ast.walk(tree))==1
        and not any(isinstance(n,ast.Attribute) and n.attr in (OLD_INSTALLER,NEW_INSTALLER) for n in ast.walk(tree)),
        'No additional installer references permitted')
    paths=[n for n in ast.walk(tree) if isinstance(n,ast.Constant) and n.value==OLD_PATH]
    require(len(paths)==1 and not any(isinstance(n,ast.Constant) and n.value==NEW_PATH for n in ast.walk(tree)),
        'Exactly one old settings path required')
    path=paths[0];imp=imports[0]
    # Modify only selected AST spans. Existing helper bytes/comments survive;
    # unparsing the full hook would silently rewrite the pull-owner wrapper.
    lines=raw.encode().splitlines(keepends=True);offsets=[0]
    for line in lines:offsets.append(offsets[-1]+len(line))
    def span(node):return offsets[node.lineno-1]+node.col_offset,offsets[node.end_lineno-1]+node.end_col_offset
    edits=[(*span(imp),f'from {NEW_MODULE} import {NEW_INSTALLER}'.encode()),
           (*span(call.func),NEW_INSTALLER.encode()),(*span(path),repr(NEW_PATH).encode())]
    result=raw.encode()
    for start,end,text in sorted(edits,reverse=True):result=result[:start]+text+result[end:]
    modified=deepcopy(tree)
    for node in ast.walk(modified):
        if isinstance(node,ast.ImportFrom) and node.module==OLD_MODULE:
            node.module=NEW_MODULE;node.names[0].name=NEW_INSTALLER
        elif isinstance(node,ast.Name) and node.id==OLD_INSTALLER:node.id=NEW_INSTALLER
        elif isinstance(node,ast.Constant) and node.value==OLD_PATH:node.value=NEW_PATH
    result=result.decode()
    require(ast.dump(ast.parse(result))==ast.dump(modified),'Only exact installer import/call/path AST edits permitted')
    compile(result,'pending-native-hub-hook','exec')
    return result


def values_document(raw):
    import yaml
    class Unique(yaml.SafeLoader):pass
    def mapping(loader,node,deep=False):
        loader.flatten_mapping(node);result={}
        for key_node,value_node in node.value:
            key=loader.construct_object(key_node,deep=deep)
            require(key not in result,'Duplicate Hub values YAML key')
            result[key]=loader.construct_object(value_node,deep=deep)
        return result
    Unique.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,mapping)
    try:result=yaml.load(raw,Loader=Unique)
    except Exception:raise ValueError('Unique full Hub values YAML required') from None
    require(isinstance(result,dict),'Full Hub values mapping required')
    return result


def patch(actual,field,desired):
    meta=actual['metadata']
    return [{'op':'test','path':'/metadata/uid','value':meta['uid']},
        {'op':'test','path':'/metadata/resourceVersion','value':meta['resourceVersion']},
        {'op':'test','path':'/'+field,'value':deepcopy(actual[field])},
        {'op':'replace','path':'/'+field,'value':deepcopy(desired)}]


def compose(deployment,secret,hub,actual_configmap):
    """Pure proposal; caller scales Hub down before Secret+Deployment handover."""
    import yaml
    wrapper=hub.get('settings',{});source=wrapper.get('groupHub',{}).get('source')
    require(source in ('cps','cit'),'Source-owned endpoint settings required')
    namespace={'cps':'jupyterhub','cit':'cit-jhub'}[source]
    identity(deployment,'Deployment',namespace);identity(secret,'Secret',namespace)
    expected=candidate(namespace,hub);reference=actual_reference(actual_configmap,expected)
    spec=deployment.get('spec',{});pod=spec.get('template',{}).get('spec',{})
    require(type(spec.get('replicas')) is int and spec['replicas'] in (0,1), 'Actual stopped or single Hub replica required')
    require(type(pod.get('securityContext',{}).get('fsGroup')) is int and pod['securityContext']['fsGroup']==1000,
        'Existing Hub fsGroup1000 required for UID1000 private emptyDir inputs')
    containers=pod.get('containers',[]);selected=[c for c in containers if c.get('name')=='hub']
    require(len(selected)==1 and isinstance(selected[0].get('image'),str)
        and re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}',selected[0]['image']), 'One existing immutable Hub container required')
    main=selected[0]
    uid=main.get('securityContext',{}).get('runAsUser',pod['securityContext'].get('runAsUser'))
    require(type(uid) is int and uid==1000,
        'Existing Hub process must run as UID1000')
    volumes=pod.get('volumes',[]);initial=pod.get('initContainers',[])
    names=[v.get('name') for v in volumes];allcontainers=containers+initial
    reserved={SEED,DATA,'cps-kai-service'}
    require(len(names)==len(set(names)) and not reserved.intersection(names)
        and all(c.get('name')!=INIT for c in allcontainers),'New Hub volume/init names collide with existing inputs')
    newpaths=(PRIVATE,'/var/run/cps-kai-service','/kai-hub-seed','/kai-hub-private')
    for container in allcontainers:
        for mount in container.get('volumeMounts',[]):
            require(mount.get('name') not in reserved,'Reserved Hub volume already mounted')
            old=mount.get('mountPath','').rstrip('/')
            require(old and not any(old==path or old.startswith(path+'/') or path.startswith(old+'/') for path in newpaths),
                'New Hub mount paths collide with existing inputs')
    require(any(m.get('readOnly') is True and not m.get('subPathExpr') and (
        m.get('mountPath')=='/etc/cps-native-hub' or m.get('mountPath')=='/etc/cps-native-hub/ca.crt')
        for m in main.get('volumeMounts',[])), 'Existing read-only trusted Hub CA mount required')
    content=expected['data']['settings.json'].encode();sha=hashlib.sha256(content).hexdigest()
    code=("from pathlib import Path; import os, stat, hashlib; os.umask(0o077); "
        "raw=Path('/kai-hub-seed/settings.json').read_bytes(); "
        f"assert hashlib.sha256(raw).hexdigest()=={sha!r}, 'Immutable settings bytes differ'; "
        "p=Path('/kai-hub-private/config'); p.mkdir(mode=0o700,exist_ok=True); s=p.lstat(); "
        "assert stat.S_ISDIR(s.st_mode) and s.st_uid==os.geteuid() and stat.S_IMODE(s.st_mode)==0o700; "
        "fd=os.open(p/'settings.json',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600); s=os.fstat(fd); "
        "assert stat.S_ISREG(s.st_mode) and s.st_uid==os.geteuid() and s.st_nlink==1 and stat.S_IMODE(s.st_mode)==0o600; "
        "os.ftruncate(fd,0); stream=os.fdopen(fd,'wb'); stream.write(raw); stream.flush(); os.fsync(stream.fileno()); stream.close()")
    desired=deepcopy(spec);newpod=desired['template']['spec']
    newpod.setdefault('volumes',[]).extend(deepcopy(hub['volumes'])+[
        {'name':SEED,'configMap':{'name':reference['name'],'defaultMode':0o444,'items':[{'key':'settings.json','path':'settings.json'}]}},
        {'name':DATA,'emptyDir':{}}])
    next(c for c in newpod['containers'] if c['name']=='hub').setdefault('volumeMounts',[]).extend(
        deepcopy(hub['volumeMounts'])+[{'name':DATA,'mountPath':PRIVATE,'readOnly':True}])
    newpod.setdefault('initContainers',[]).append({'name':INIT,'image':main['image'],'command':['python','-I','-S','-c',code],
        'securityContext':{'runAsUser':1000,'runAsGroup':1000,'runAsNonRoot':True,'readOnlyRootFilesystem':True,
            'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},
        'volumeMounts':[{'name':SEED,'mountPath':'/kai-hub-seed','readOnly':True},{'name':DATA,'mountPath':'/kai-hub-private'}]})
    data=secret.get('data')
    require(isinstance(data,dict) and 'values.yaml' in data and not secret.get('stringData') and secret.get('immutable') is not True, 'Actual full Hub Secret data required')
    try:raw=base64.b64decode(data['values.yaml'],validate=True)
    except Exception:raise ValueError('Encoded full Hub values required') from None
    before=values_document(raw);after=deepcopy(before)
    try:oldhook=before['hub']['extraConfig'][HOOK]
    except (KeyError,TypeError):raise ValueError('Existing single native hook required') from None
    extras=before['hub']['extraConfig']
    require(isinstance(extras,dict),'Full extraConfig mapping required')
    for key,code in extras.items():
        if key==HOOK:continue
        require(isinstance(code,str),'Existing extraConfig Python source required')
        try:other=ast.parse(code)
        except (SyntaxError,ValueError):raise ValueError('Valid existing extraConfig Python required') from None
        for node in ast.walk(other):
            require(not (isinstance(node,ast.ImportFrom) and (node.module in (OLD_MODULE,NEW_MODULE)
                or any(a.name in (OLD_INSTALLER,NEW_INSTALLER) for a in node.names)))
                and not (isinstance(node,ast.Import) and any(a.name in (OLD_MODULE,NEW_MODULE) for a in node.names))
                and not (isinstance(node,ast.Name) and node.id in (OLD_INSTALLER,NEW_INSTALLER))
                and not (isinstance(node,ast.Attribute) and node.attr in (OLD_INSTALLER,NEW_INSTALLER)),
                'Additional native installer in other extraConfig refused')
    after['hub']['extraConfig'][HOOK]=replace_hook(oldhook)
    encoded=yaml.safe_dump(after,sort_keys=False,allow_unicode=True).encode();parsed=values_document(encoded)
    require(parsed==after,'Full Hub values YAML semantic round trip required')
    previous=deepcopy(before);remaining=deepcopy(parsed)
    del previous['hub']['extraConfig'][HOOK];del remaining['hub']['extraConfig'][HOOK]
    require(previous==remaining,'All other Hub values must remain semantically unchanged')
    replacement=deepcopy(data);replacement['values.yaml']=base64.b64encode(encoded).decode()
    return {'configuration_reference':reference,'secret_patch':patch(secret,'data',replacement),
        'deployment_patch':patch(deployment,'spec',desired)}
