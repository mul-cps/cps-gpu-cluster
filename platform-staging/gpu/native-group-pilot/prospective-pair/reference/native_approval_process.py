"""Fresh controller provenance for opt-in native approval acknowledgments.

Operator declarations bind a controller's actual UID, immutable image and
service account. A receipt only locates a Pod; it never supplies that authority.
These helpers issue no reads until explicitly invoked.
"""
from __future__ import annotations

import json
import re

import uuid

def _api_document(core,value):
    if isinstance(value,dict):return json.loads(json.dumps(value,allow_nan=False))
    return core.api_client.sanitize_for_serialization(value)

def _uid(value):
    try:return isinstance(value,str) and str(uuid.UUID(value))==value and uuid.UUID(value).int!=0
    except (ValueError,TypeError,AttributeError):return False



def _require(value,message):
    if not value:raise ValueError(message)


def validate_process_declaration(value):
    fields={'namespace','kind','name','uid','container','image','service_account'}
    name=re.compile(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?')
    _require(isinstance(value,dict) and set(value)==fields
             and value['kind'] in ('Deployment','DaemonSet') and _uid(value['uid'])
             and all(isinstance(value[k],str) and name.fullmatch(value[k])
                     for k in fields-{'kind','uid','image'})
             and isinstance(value['image'],str) and re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}',value['image']),
             'Exact trusted controller identity and immutable image required')
    return json.loads(json.dumps(value))


def _object(value,kind,namespace,name,uid):
    meta=value.get('metadata',{}) if isinstance(value,dict) else {}
    _require(isinstance(value,dict) and value.get('apiVersion')==('v1' if kind=='Pod' else 'apps/v1')
             and value.get('kind')==kind and isinstance(meta,dict)
             and (meta.get('namespace'),meta.get('name'),meta.get('uid'))==(namespace,name,uid)
             and not meta.get('deletionTimestamp'),'Actual current controller/Pod identity required')
    return value


def _owner(value,kind):
    refs=value['metadata'].get('ownerReferences')
    _require(isinstance(refs,list),'Actual controller owner required')
    owners=[row for row in refs if isinstance(row,dict) and row.get('controller') is True]
    _require(len(owners)==1 and owners[0].get('apiVersion')=='apps/v1'
             and owners[0].get('kind')==kind and isinstance(owners[0].get('name'),str)
             and _uid(owners[0].get('uid')),'Exact controller owner chain required')
    return owners[0]


def _contains(actual,expected):
    """Match the API-defaulted template while permitting Pod scheduling fields."""
    if isinstance(expected,dict):
        return isinstance(actual,dict) and all(k in actual and _contains(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):
        return isinstance(actual,list) and len(actual)==len(expected) and all(_contains(a,e) for a,e in zip(actual,expected))
    return type(actual) is type(expected) and actual==expected


def _normalized_pod_spec(actual,desired):
    """Remove only Kubernetes' exact default service-account token injection."""
    _require(isinstance(actual,dict),'Actual Pod spec required')
    result=json.loads(json.dumps(actual))
    volumes=result.get('volumes',[])
    _require(isinstance(volumes,list),'Actual Pod volume list required')
    approved_names={row.get('name') for row in desired.get('volumes',[]) if isinstance(row,dict)}
    automatic=[]
    for volume in volumes:
        if not isinstance(volume,dict) or volume.get('name') in approved_names:continue
        name=volume.get('name');projection=volume.get('projected',{})
        if not isinstance(name,str) or not re.fullmatch(r'kube-api-access-[a-z0-9]{5}',name):continue
        for seconds in (3600,3607):
            expected={'name':name,'projected':{'defaultMode':420,'sources':[
                {'serviceAccountToken':{'expirationSeconds':seconds,'path':'token'}},
                {'configMap':{'name':'kube-root-ca.crt','items':[{'key':'ca.crt','path':'ca.crt'}]}},
                {'downwardAPI':{'items':[{'path':'namespace','fieldRef':{'apiVersion':'v1','fieldPath':'metadata.namespace'}}]}}]}}
            if volume==expected:automatic.append(name);break
    _require(len(automatic)<=1,'At most one default service-account projection allowed')
    if automatic:
        _require(desired.get('automountServiceAccountToken') is not False
                 and result.get('automountServiceAccountToken') is not False,
                 'Disabled service-account automount cannot gain a projection')
        name=automatic[0];mount={'name':name,'readOnly':True,'mountPath':'/var/run/secrets/kubernetes.io/serviceaccount'}
        result['volumes']=[row for row in volumes if row.get('name')!=name]
        for container in result.get('containers',[]):
            _require(isinstance(container,dict) and isinstance(container.get('volumeMounts',[]),list),
                     'Actual container mount list required')
            _require(all(row==mount for row in container.get('volumeMounts',[]) if isinstance(row,dict) and row.get('name')==name),
                     'Only the exact readonly default service-account mount allowed')
            if 'volumeMounts' in container:
                container['volumeMounts']=[row for row in container['volumeMounts'] if row!=mount]
                original=next((row for row in desired.get('containers',[]) if row.get('name')==container.get('name')),None)
                if not container['volumeMounts'] and original is not None and 'volumeMounts' not in original:
                    del container['volumeMounts']
        if not result['volumes'] and 'volumes' not in desired:del result['volumes']
    return result


def _match_pod_spec(actual,desired):
    normalized=_normalized_pod_spec(actual,desired)
    # Containers can execute code or expose mounts. No subset comparison is
    # permitted here, including fields absent from the approved template.
    _require(normalized.get('containers')==desired.get('containers')
             and normalized.get('volumes',[])==desired.get('volumes',[]),
             'Exact approved executable containers and volumes required')
    for key in ('initContainers','ephemeralContainers','securityContext','hostPID','hostIPC','hostNetwork',
                'shareProcessNamespace','runtimeClassName','hostAliases','os'):
        _require(normalized.get(key)==desired.get(key),'Unreviewed Pod execution/security field: '+key)
    _require(_contains(normalized,desired),'Actual Pod does not match current controller template')


def _template(value):
    spec=value.get('spec',{});template=spec.get('template') if isinstance(spec,dict) else None
    _require(isinstance(template,dict) and isinstance(template.get('spec'),dict)
             and isinstance(template.get('metadata',{}),dict),'Actual controller Pod template required')
    return template


def _selector(labels,selector):
    _require(isinstance(labels,dict) and isinstance(selector,dict)
             and set(selector)<={'matchLabels','matchExpressions'}
             and isinstance(selector.get('matchLabels',{}),dict)
             and isinstance(selector.get('matchExpressions',[]),list),'Closed controller selector required')
    _require(all(labels.get(k)==v for k,v in selector.get('matchLabels',{}).items()),'Actual controller selector mismatch')
    for row in selector.get('matchExpressions',[]):
        _require(isinstance(row,dict) and set(row)<={'key','operator','values'}
                 and isinstance(row.get('key'),str) and isinstance(row.get('values',[]),list),
                 'Closed controller selector expression required')
        key=row['key'];op=row.get('operator');values=row.get('values',[])
        _require(op in ('In','NotIn','Exists','DoesNotExist'),'Unsupported controller selector')
        _require((op=='In' and key in labels and labels[key] in values)
                 or (op=='NotIn' and labels.get(key) not in values)
                 or (op=='Exists' and key in labels) or (op=='DoesNotExist' and key not in labels),
                 'Actual controller selector mismatch')


def observe_process(core,apps,declaration,receipt_process):
    """Return fresh actual Pod and trusted six-field process scope.

Deployment Pods must belong to an actual ReplicaSet of the pinned Deployment
and its current template. DaemonSet Pods must belong directly to the pinned
DaemonSet. Foreign/ad-hoc Pods and previous rollout templates are denied.
"""
    expected=validate_process_declaration(declaration)
    fields={'namespace','name','uid','container','image','service_account'}
    _require(isinstance(receipt_process,dict) and set(receipt_process)==fields
             and all(receipt_process.get(k)==expected[k] for k in ('namespace','container','image','service_account'))
             and isinstance(receipt_process.get('name'),str) and _uid(receipt_process.get('uid')),
             'Receipt process cannot choose its controller scope')
    try:
        pod=_object(_api_document(core,core.read_namespaced_pod(receipt_process['name'],expected['namespace'])),
                    'Pod',expected['namespace'],receipt_process['name'],receipt_process['uid'])
        method=apps.read_namespaced_deployment if expected['kind']=='Deployment' else apps.read_namespaced_daemon_set
        controller=_object(_api_document(apps,method(expected['name'],expected['namespace'])),expected['kind'],
                           expected['namespace'],expected['name'],expected['uid'])
        desired=_template(controller)
        containers=desired['spec'].get('containers');selected=[row for row in containers or []
            if isinstance(row,dict) and row.get('name')==expected['container']]
        _require(isinstance(containers,list) and len(selected)==1 and selected[0].get('image')==expected['image']
                 and desired['spec'].get('serviceAccountName')==expected['service_account'],
                 'Trusted controller image/service account changed')
        owner=_owner(pod,'ReplicaSet' if expected['kind']=='Deployment' else 'DaemonSet')
        if expected['kind']=='Deployment':
            rs=_object(_api_document(apps,apps.read_namespaced_replica_set(owner['name'],expected['namespace'])),
                       'ReplicaSet',expected['namespace'],owner['name'],owner['uid'])
            parent=_owner(rs,'Deployment')
            _require((parent['name'],parent['uid'])==(expected['name'],expected['uid']),'Foreign ReplicaSet controller')
            template=_template(rs)
            normalized=json.loads(json.dumps(template))
            normalized.get('metadata',{}).get('labels',{}).pop('pod-template-hash',None)
            _require(normalized==desired,'Previous or changed ReplicaSet template')
        else:
            _require((owner['name'],owner['uid'])==(expected['name'],expected['uid']),'Foreign DaemonSet controller')
        _selector(pod['metadata'].get('labels',{}),controller['spec'].get('selector'))
        _match_pod_spec(pod.get('spec'),desired['spec'])
        _require(all(_contains(pod['metadata'].get(key,{}),desired.get('metadata',{}).get(key,{}))
                         for key in ('labels','annotations')),'Actual Pod does not match current controller template')
        status=pod.get('status',{})
        _require(isinstance(status,dict) and status.get('phase')=='Running'
                 and isinstance(status.get('conditions'),list) and any(
                     isinstance(row,dict) and row.get('type')=='Ready' and row.get('status')=='True'
                     for row in status['conditions']),'Actual component Pod is not running and ready')
        return pod,{**{k:expected[k] for k in ('namespace','container','image','service_account')},
                    'name':pod['metadata']['name'],'uid':pod['metadata']['uid']}
    except (AttributeError,TypeError,KeyError) as exc:
        raise ValueError('Incomplete fresh controller observation') from exc
