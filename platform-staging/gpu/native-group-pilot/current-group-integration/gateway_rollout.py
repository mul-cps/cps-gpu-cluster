"""Pure, guarded rollout proposals; no clients, credentials or executor."""
from copy import deepcopy
import hashlib
import json
from pathlib import PurePosixPath
import re
from uuid import UUID


def require(value,message):
    if not value:raise ValueError(message)


def _metadata(obj,kind):
    require(obj.get('apiVersion')==('apps/v1' if kind=='Deployment' else 'v1') and obj.get('kind')==kind,'Actual object kind differs')
    meta=obj.get('metadata',{})
    try:valid=str(UUID(meta.get('uid','')))==meta['uid']
    except (ValueError,TypeError,KeyError):valid=False
    require(valid and isinstance(meta.get('resourceVersion'),str) and re.fullmatch('[1-9][0-9]*',meta['resourceVersion'])
        and not meta.get('deletionTimestamp'),'Actual current UID/resourceVersion required')
    return meta


def _named(values):
    require(isinstance(values,list) and all(isinstance(v,dict) and isinstance(v.get('name'),str) and v['name'] for v in values),'Named list required')
    names=[v['name'] for v in values]
    require(len(names)==len(set(names)),'Duplicate name in captured or proposed list')
    return set(names)


def _append(old,new):
    require(not (_named(old)&_named(new)),'Proposed name already exists')
    return deepcopy(old)+deepcopy(new)


def _mounts(old,new):
    _named(new)
    paths=[]
    for mount in old+new:
        raw=mount.get('mountPath');require(isinstance(raw,str),'Mount path required')
        path=PurePosixPath(raw)
        require(path.is_absolute() and str(path)==raw and '..' not in path.parts,'Canonical absolute mount path required')
        paths.append(path)
    require(len(paths)==len(set(paths)),'Duplicate mount path')
    require(not any(a==b or a in b.parents or b in a.parents for a in paths[:len(old)] for b in paths[len(old):]),'Proposed mount shadows an existing path')
    return deepcopy(old)+deepcopy(new)


def _start(deployment,expected,container,actor):
    meta=_metadata(deployment,'Deployment')
    require(isinstance(expected,dict) and set(expected)=={'namespace','name','uid','resourceVersion'}
        and all(meta.get(k)==v for k,v in expected.items()),'Deployment differs from independent identity pin')
    spec=deepcopy(deployment['spec']);pod=spec['template']['spec']
    require(actor=='system:serviceaccount:'+meta['namespace']+':'+pod.get('serviceAccountName',''),'Actual service account differs')
    _named(pod.get('containers',[]));_named(pod.get('initContainers',[]));_named(pod.get('volumes',[]))
    require(not (_named(pod.get('containers',[]))&_named(pod.get('initContainers',[]))),'Container/init name collision')
    selected=[c for c in pod['containers'] if c['name']==container]
    require(len(selected)==1,'One exact main container required')
    main=selected[0];_named(main.get('env',[]))
    return spec,pod,main


def _plan(deployment,spec):
    meta=deployment['metadata']
    return {'prospective':True,'target':{'kind':'Deployment','namespace':meta['namespace'],'name':meta['name']},
        'spec':spec,'patch':[{'op':'test','path':'/metadata/uid','value':meta['uid']},
            {'op':'test','path':'/metadata/resourceVersion','value':meta['resourceVersion']},
            {'op':'test','path':'/spec','value':deepcopy(deployment['spec'])},
            {'op':'replace','path':'/spec','value':deepcopy(spec)}]}


def _seed(proposal,actual,namespace):
    expected=proposal['seed'];meta=_metadata(actual,'ConfigMap')
    data=expected.get('data')
    require(isinstance(data,dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in data.items()),'Public seed data required')
    suffix=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]
    require(expected.get('apiVersion')=='v1' and expected.get('kind')=='ConfigMap' and expected.get('immutable') is True
        and expected['metadata']=={'namespace':namespace,'name':'cps-native-kai-config-'+suffix},'Seed content-address identity differs')
    require(meta.get('namespace')==namespace and meta.get('name')==expected['metadata']['name'] and actual.get('immutable') is True
        and actual.get('data')==data and not actual.get('binaryData') and not meta.get('ownerReferences'),'Actual immutable seed readback differs')
    return {k:meta[k] for k in ('namespace','name','uid','resourceVersion')}


def compose_gateway(deployment,proposal,actual_seed,*,expected,container='gateway'):
    """Append the reviewed Gateway fragments after actual seed CREATE readback."""
    seed_ref=_seed(proposal,actual_seed,expected['namespace'])
    fragment=proposal['gateway'];config=proposal['coordinator']
    spec,pod,main=_start(deployment,expected,container,config['settings']['coordinator_actor'])
    require(type(pod.get('securityContext',{}).get('fsGroup')) is int and pod['securityContext']['fsGroup']==10001,'Gateway fsGroup10001 prerequisite differs')
    require(main.get('image')==fragment['initContainer']['image'],'Gateway/init image differs')
    require(_named(fragment['volumes'])=={'cps-kai-api','kai-private','kai-seed'} and len(fragment['volumeMounts'])==2
        and _named(fragment['env'])=={'CPS_NATIVE_KAI_COORDINATOR_CONFIG'},'Exact emitted Gateway fragments required')
    seed_volume=next(v for v in fragment['volumes'] if v['name']=='kai-seed')
    require(seed_volume.get('configMap',{}).get('name')==seed_ref['name'],'Gateway seed mount differs from actual readback')
    data=[m for m in main.get('volumeMounts',[]) if m.get('mountPath')=='/data' and not m.get('readOnly') and not m.get('subPath') and not m.get('subPathExpr')]
    init_data=[m for m in fragment['initContainer']['volumeMounts'] if m.get('mountPath')=='/data']
    require(len(data)==len(init_data)==1 and data[0]['name']==init_data[0]['name'],'Private initializer must share the complete actual data mount')
    volume=next((v for v in pod['volumes'] if v['name']==data[0]['name']),{})
    require('persistentVolumeClaim' in volume and not volume['persistentVolumeClaim'].get('readOnly'),'Existing writable data PVC required')
    main['env']=_append(main.get('env',[]),fragment['env'])
    main['volumeMounts']=_mounts(main.get('volumeMounts',[]),fragment['volumeMounts'])
    pod['volumes']=_append(pod.get('volumes',[]),fragment['volumes'])
    require(fragment['initContainer']['name'] not in _named(pod['containers']),'Initializer/main name collision')
    pod['initContainers']=_append(pod.get('initContainers',[]),[fragment['initContainer']])
    result=_plan(deployment,spec);result['seed_ref']=seed_ref
    return result


def _flag(args,name):
    found=[i for i,arg in enumerate(args) if arg==name or arg.startswith(name+'=')]
    require(len(found)<=1,'Duplicate binder flag '+name)
    if not found:return None
    index=found[0]
    if args[index]!=name:return index,1,args[index].split('=',1)[1]
    require(index+1<len(args) and not args[index+1].startswith('--'),'Missing binder flag value')
    return index,2,args[index+1]


def compose_binder(deployment,proposal,*,expected,container='binder'):
    """Stage the existing binder with the native bridge explicitly false."""
    config=proposal['coordinator'];fragment=proposal['binder']
    spec,pod,main=_start(deployment,expected,container,config['settings']['binder_actor'])
    security=pod.setdefault('securityContext',{})
    require('fsGroup' not in security or (type(security['fsGroup']) is int and security['fsGroup']==10000),'Binder fsGroup differs')
    security['fsGroup']=10000
    image=config['reservationTemplate']['image']
    require(isinstance(image,str) and re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}',image),'Immutable reservation digest required')
    flags=fragment['args'];require(isinstance(flags,list) and all(isinstance(v,str) and '=' in v for v in flags),'Closed binder flags required')
    emitted=dict(v.split('=',1) for v in flags)
    required={'--native-pending-coordinator-enabled','--native-coordinator-url','--native-coordinator-authority-namespace',
        '--native-coordinator-token-file','--native-coordinator-ca-file','--resource-reservation-pod-image'}
    require(set(emitted)==required and len(flags)==6 and emitted.get('--native-pending-coordinator-enabled')=='false'
        and emitted.get('--resource-reservation-pod-image')==image,'Binder proposal must stay disabled with exact reservation image')
    args=deepcopy(main.get('args',[]));require(all(isinstance(v,str) for v in args),'String binder args required')
    current=_flag(args,'--resource-reservation-pod-image');require(current is not None,'Existing explicit reservation image flag required')
    index,width,_=current;args[index:index+width]=['--resource-reservation-pod-image='+image]
    for name,value in emitted.items():
        if name=='--resource-reservation-pod-image':continue
        old=_flag(args,name)
        if old is None:args.append(name+'='+value)
        else:require(old[2]==value,'Existing binder native setting differs')
    main['args']=args
    main['volumeMounts']=_mounts(main.get('volumeMounts',[]),fragment['volumeMounts'])
    pod['volumes']=_append(pod.get('volumes',[]),fragment['volumes'])
    return _plan(deployment,spec)
