"""Restricted idle Source operator and actual exclusive-writer freeze verifier.

No database is opened and no Kubernetes action is performed here. Root supplies
fresh API readbacks and a protected review of active start-path/token custody.
Only after this verifier succeeds may the genuine Source factory open providers.
"""
import copy
from datetime import datetime,timezone
import hashlib
import json
import re
from uuid import UUID

IMAGE='ghcr.io/mul-cps/e2x-course-hub@sha256:dbaad51899ccb634f5a07c44bd9f7022dbca71724d7cfd66e5d67abf9d569ace'
ACCOUNT='cps-qa531-source-operator'
MARKER='cps.compute/profile-handover-operator'


def require(value,message):
    if not value:raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def deployment(value,source):
    require(isinstance(value,dict) and value.get('apiVersion')=='apps/v1' and value.get('kind')=='Deployment'
        and value.get('metadata',{}).get('namespace')=='cps-compute'
        and value['metadata'].get('name')==source+'-admin' and value['metadata'].get('uid')
        and not value['metadata'].get('deletionTimestamp')
        and value['spec']['selector']=={'matchLabels':{'app':source+'-admin'}},'Exact actual source Deployment required')
    return value


def maintenance_pod(original_deployment,*,node_name,freeze_id,helper_configmap):
    original=deployment(original_deployment,'cps')
    require(str(UUID(freeze_id))==freeze_id and UUID(freeze_id).int!=0,'Canonical nonzero external freeze identifier required')
    require(all(isinstance(v,str) and re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,252}',v) for v in (node_name,helper_configmap)),
        'Explicit original source node and helper ConfigMap required')
    spec=copy.deepcopy(original['spec']['template']['spec'])
    require(len(spec['containers'])==1 and not spec.get('initContainers') and not spec.get('ephemeralContainers')
        and not any(spec.get(k) for k in ('hostNetwork','hostPID','hostIPC'))
        and not any('hostPath' in v for v in spec.get('volumes',[])), 'Restricted original single-container Source required')
    container=spec['containers'][0]
    require(container['name']=='console' and container['image']==IMAGE,'Exact reviewed Source531 runtime image required')
    require(any(v.get('persistentVolumeClaim',{}).get('claimName')=='cps-admin-data' for v in spec['volumes'])
        and not any(v['name'] in ('operator-control','operator-helpers') for v in spec['volumes']),
        'Original CPS database binding and unused control mounts required')
    container['name']='operator';container['command']=['python','-B','-c'];container['args']=['import time; time.sleep(3600)']
    for key in ('ports','readinessProbe','livenessProbe','startupProbe','lifecycle'):container.pop(key,None)
    security=dict(runAsUser=10001,runAsGroup=10001,runAsNonRoot=True)
    container['securityContext']={**security,'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,
        'capabilities':{'drop':['ALL']},'seccompProfile':{'type':'RuntimeDefault'}}
    container.setdefault('volumeMounts',[]).extend([dict(name='operator-control',mountPath='/operator'),
        dict(name='operator-helpers',mountPath='/opt/qualification',readOnly=True)])
    spec['volumes'].extend([dict(name='operator-control',emptyDir={}),dict(name='operator-helpers',configMap={'name':helper_configmap,'defaultMode':0o444})])
    spec.update(serviceAccountName=ACCOUNT,automountServiceAccountToken=True,nodeName=node_name,restartPolicy='Never',
        activeDeadlineSeconds=3600,securityContext={**security,'fsGroup':10001,'seccompProfile':{'type':'RuntimeDefault'}})
    return dict(apiVersion='v1',kind='Pod',metadata=dict(namespace='cps-compute',name=ACCOUNT+'-'+freeze_id[:8],labels={'app':ACCOUNT,MARKER:freeze_id}),spec=spec)


def verify_freeze(*,originals,current,pods,operator,review,gateway):
    require(set(originals)==set(current)=={'cps','cit'},'Both complete original/current Source deployments required')
    require(isinstance(review,dict) and set(review)=={'version','freeze_id','operator_uid','operator_spec_sha256','source_deployment_uids','gateway',
        'no_alternate_group_start_path','source_service_token_custody','passed','observed_at'},'Closed protected Root exclusion review required')
    require(isinstance(gateway,dict) and set(gateway)=={'pod_uid','policy_hash','contract_sha256'}
        and str(UUID(gateway['pod_uid']))==gateway['pod_uid'] and UUID(gateway['pod_uid']).int!=0
        and re.fullmatch(r'sha256:[a-f0-9]{64}',gateway['policy_hash'])
        and re.fullmatch(r'[a-f0-9]{64}',gateway['contract_sha256'])
        and review['gateway']==gateway,'Independent current Gateway process/policy and Root contract binding required')
    observed=datetime.fromisoformat(review['observed_at'].replace('Z','+00:00'))
    require(type(review['version']) is int and review['version']==1 and review['passed'] is True
        and review['no_alternate_group_start_path'] is True
        and review['source_service_token_custody']=='root-exclusive-during-external-freeze'
        and observed.tzinfo is not None and 0<=(datetime.now(timezone.utc)-observed).total_seconds()<=600,
        'Fresh reviewed active start exclusion and service-token custody required')
    meta=operator.get('metadata',{});spec=operator.get('spec',{});containers=spec.get('containers',[])
    require(operator.get('apiVersion')=='v1' and operator.get('kind')=='Pod' and meta.get('namespace')=='cps-compute'
        and digest(spec)==review['operator_spec_sha256'] and meta.get('uid')==review['operator_uid'] and meta.get('labels',{}).get(MARKER)==review['freeze_id']
        and not meta.get('deletionTimestamp') and operator.get('status',{}).get('phase')=='Running'
        and spec.get('serviceAccountName')==ACCOUNT and not spec.get('initContainers') and not spec.get('ephemeralContainers')
        and not any(spec.get(k) for k in ('hostNetwork','hostPID','hostIPC')) and len(containers)==1,
        'Actual unique restricted operator Pod required')
    container=containers[0];security=container.get('securityContext',{})
    require(container.get('name')=='operator' and container.get('image')==IMAGE
        and container.get('command')==['python','-B','-c'] and container.get('args')==['import time; time.sleep(3600)']
        and all(security.get(k)==v for k,v in {'runAsUser':10001,'runAsGroup':10001,'runAsNonRoot':True,'allowPrivilegeEscalation':False,'readOnlyRootFilesystem':True,'capabilities':{'drop':['ALL']}}.items())
        and not any('hostPath' in v for v in spec.get('volumes',[])), 'Original runtime and restricted maintenance command required')
    require(pods.get('apiVersion')=='v1' and pods.get('kind')=='PodList' and isinstance(pods.get('items'),list)
        and isinstance(pods.get('metadata'),dict) and not pods['metadata'].get('continue'),'Complete unpaginated actual PodList required')
    require(sum(p.get('metadata',{}).get('uid')==meta['uid'] for p in pods['items'])==1
        and next(p for p in pods['items'] if p.get('metadata',{}).get('uid')==meta['uid'])==operator,
        'Actual operator must occur once in the same complete observation')
    claims=set()
    for source in ('cps','cit'):
        before=deployment(originals[source],source);actual=deployment(current[source],source)
        require(actual['metadata']['uid']==before['metadata']['uid']==review['source_deployment_uids'].get(source)
            and type(actual['spec'].get('replicas')) is int and actual['spec']['replicas']==0
            and actual['spec']=={**before['spec'],'replicas':0},'Source is not exclusively scaled down or its original spec changed')
        claims.update(v['persistentVolumeClaim']['claimName'] for v in before['spec']['template']['spec']['volumes'] if 'persistentVolumeClaim' in v)
        require(not any(p.get('metadata',{}).get('labels',{}).get('app')==source+'-admin' for p in pods['items']),
            'An original/in-flight Source writer Pod still exists')
    for pod in pods['items']:
        require(pod.get('metadata',{}).get('namespace')=='cps-compute','PodList contains a foreign namespace')
        if pod['metadata']['uid']==meta['uid']:continue
        used={v['persistentVolumeClaim']['claimName'] for v in pod.get('spec',{}).get('volumes',[]) if 'persistentVolumeClaim' in v}
        if used & claims:
            states=pod.get('status',{}).get('containerStatuses',[])+pod.get('status',{}).get('initContainerStatuses',[])
            require(pod.get('status',{}).get('phase') in ('Succeeded','Failed') and states and all('terminated' in s.get('state',{}) for s in states),
                'Another live/terminating database writer remains')
    return dict(version=1,freeze_id=review['freeze_id'],active=True,sources=['cit','cps'],writer_pods=[],external_starts_excluded=True,observed_at=datetime.now(timezone.utc).isoformat())
