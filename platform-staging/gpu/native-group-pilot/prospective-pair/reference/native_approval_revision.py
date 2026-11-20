"""Separate immutable Source approvals for the unchanged native node authority.

The qualification template and base node configuration are operator inputs.
Approval documents may change only workspace rows. A previous document is
terminal evidence only: it cannot open a gate or authorize a new Pod lifetime.
No Kubernetes, GPU, file or publication action occurs at import time.
"""
from __future__ import annotations
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid
import urllib.error
import urllib.request

BASE_SOURCE_SHA256='3bae6d53e4ce42a54b6dcd372839ef5f7286084212c5930d1deeb93da8d6c688'
PROCESS_SOURCE_SHA256='dc72f653da935bf60d563430b643f18c2852417c138fdb281df563f79da4b772'
PROCESS_OVERLAY_SHA256='e121dd491d709d945b96fa475902486f783151f76f903344d06871b49aab2875'
REFERENCE_FIELDS={'namespace','name','uid','data_sha256','revision','policy_hash'}
APPROVAL_FIELDS={'owner','server','members','principal','profiles','ceiling','namespace','pod','group_id','course_id','term_id','storage'}
STORAGE_FIELDS={'namespace','pvc','pv','path','group_hash','storage_version','readonly_mounts'}
SHA=re.compile(r'sha256:[a-f0-9]{64}')
NAME=re.compile(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?')
TOKEN=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.@-]{0,127}')
IMAGE=re.compile(r'[^\s@]+@sha256:[a-f0-9]{64}')


def require(value,message):
    if not value:raise ValueError(message)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(value):return 'sha256:'+hashlib.sha256(canonical(value).encode()).hexdigest()


def parse(raw):
    require(isinstance(raw,(str,bytes)) and 0<len(raw if isinstance(raw,bytes) else raw.encode())<=1048576,'Bounded approval JSON required')
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'Duplicate approval field');result[key]=value
        return result
    value=json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite approval JSON')))
    return value


def reference(value):
    require(isinstance(value,dict) and set(value)==REFERENCE_FIELDS,'Closed immutable approval reference required')
    require(all(isinstance(value[k],str) and NAME.fullmatch(value[k]) for k in ('namespace','name')),'Exact document namespace/name required')
    import uuid
    try: valid=isinstance(value['uid'],str) and str(uuid.UUID(value['uid']))==value['uid'] and uuid.UUID(value['uid']).int!=0
    except (ValueError,TypeError,AttributeError):valid=False
    require(valid and all(isinstance(value[k],str) and SHA.fullmatch(value[k]) and value[k]!='sha256:'+'0'*64
        for k in ('data_sha256','revision','policy_hash')),'Actual document UID/data/revision/policy required')
    return copy.deepcopy(value)


def validate_approvals(rows,caps):
    require(isinstance(rows,dict) and len(rows)<=32,'Bounded Source-owned workspace approvals required')
    for scope,row in rows.items():
        require(isinstance(scope,str) and re.fullmatch(r'(cps|cit):[A-Za-z0-9_.-]{1,128}',scope)
            and isinstance(row,dict) and set(row)==APPROVAL_FIELDS,'Closed Source-owned approval required')
        source,_=scope.split(':',1)
        require(all(isinstance(row[k],str) and TOKEN.fullmatch(row[k]) for k in ('owner','server','pod','group_id','course_id','term_id')),'Stable neutral/course/group identity required')
        require(row['namespace']=={'cps':'jupyterhub','cit':'cit-jhub'}[source] and row['principal']=='workspace:'+scope
            and isinstance(row['profiles'],list) and len(row['profiles'])==1 and row['profiles'][0] in caps,'Exact approved namespace/principal/profile required')
        members=row['members']
        require(isinstance(members,list) and 1<=len(members)<=64 and len(set(members))==len(members)
            and all(isinstance(v,str) and re.fullmatch(r'[^\s]{1,256}',v) for v in members)
            and row['owner'] not in members,'Sorted distinct canonical members required')
        ceiling=row['ceiling']
        require(isinstance(ceiling,dict) and set(ceiling)=={'cpu','memory','gpuMemoryGiB'} and ceiling['cpu']=='4'
            and ceiling['memory']=='16Gi' and type(ceiling['gpuMemoryGiB']) is int
            and ceiling['gpuMemoryGiB']*1024==caps[row['profiles'][0]],'Exact fixed qualified course ceiling required')
        storage=row['storage']
        require(isinstance(storage,dict) and set(storage)==STORAGE_FIELDS and storage['namespace']==row['namespace']
            and all(isinstance(storage[k],str) and storage[k] for k in ('pvc','pv','path','group_hash'))
            and storage['path'].startswith('/mnt/') and '..' not in storage['path'].split('/')
            and type(storage['storage_version']) is int and storage['storage_version'] in (1,2)
            and isinstance(storage['readonly_mounts'],list),'Exact centrally provisioned storage required')
        for mount in storage['readonly_mounts']:
            require(isinstance(mount,dict) and set(mount)=={'server','path','mount_path','read_only'}
                and mount['read_only'] is True and isinstance(mount['server'],str) and re.fullmatch(r'[A-Za-z0-9.-]{1,253}',mount['server'])
                and all(isinstance(mount[k],str) and mount[k].startswith('/') and not mount[k].startswith('//')
                    and '..' not in mount[k].split('/') and mount[k] not in ('/','/workspace') for k in ('path','mount_path'))
                and not mount['mount_path'].startswith('/workspace/'),'Exact approved readonly storage required')
    for key in ('owner','pod'):
        require(len({(row['namespace'],row[key]) for row in rows.values()})==len(rows),'Distinct neutral accounts and Pod identities required')


class ApprovalConsumer:
    def __init__(self,agent,base_config,qualification,expected_ref,get_configmap):
        agent.validate_config(base_config)
        require(base_config.get('version')==2 and base_config.get('mode')=='qualified-group','Unchanged qualified group base required')
        self.agent=agent;self.base=copy.deepcopy(base_config);self.template=copy.deepcopy(qualification)
        self.reference=reference(expected_ref);self.get=get_configmap
        require(isinstance(qualification,dict) and set(qualification)=={'enabled','policy_hash','node_pool','authorityNamespace',
            'gateImage','workloadImage','evidence','evidence_sha256','workspaces'} and qualification['enabled'] is True
            and qualification['policy_hash']==base_config['policy_hash']==self.reference['policy_hash']
            and qualification['authorityNamespace']==base_config['authority_namespace']
            and qualification['node_pool']==base_config['pool'],'Exact external qualification/base-policy/pool binding required')
        self.caps=qualification['evidence'].get('profile_caps')
        require(self.caps=={'interactive-shared-5':5120,'interactive-shared-10':10240}
            and all(isinstance(qualification[k],str) and IMAGE.fullmatch(qualification[k]) for k in ('gateImage','workloadImage')),
            'Only existing measured 5/10 profiles and pinned images are supported')
        self.loaded=None

    def document(self,ref):
        ref=reference(ref);cm=self.get(ref['namespace'],ref['name'])
        meta=cm.get('metadata',{}) if isinstance(cm,dict) else {}
        require(isinstance(cm,dict) and cm.get('apiVersion')=='v1' and cm.get('kind')=='ConfigMap'
            and cm.get('immutable') is True and not cm.get('binaryData') and isinstance(meta,dict)
            and not meta.get('ownerReferences') and not meta.get('deletionTimestamp')
            and all(meta.get(k)==ref[k] for k in ('namespace','name','uid'))
            and isinstance(cm.get('data'),dict) and set(cm['data'])=={'approval.json'}
            and digest(cm['data'])==ref['data_sha256'],'Actual immutable approval UID/full-data pin required')
        raw=cm['data']['approval.json'];doc=parse(raw)
        require(raw==canonical(doc) and isinstance(doc,dict) and set(doc)=={'version','revision','policy_hash','registry','history'}
            and type(doc['version']) is int and doc['version']==1,'Closed canonical approval document required')
        registry=doc['registry']
        require(isinstance(registry,dict) and set(registry)=={'version','generation','deployment'}
            and type(registry['version']) is int and registry['version']==1 and type(registry['generation']) is int
            and registry['generation']>=0 and isinstance(registry['deployment'],dict)
            and doc['revision']==ref['revision']==digest(registry) and doc['policy_hash']==ref['policy_hash']==self.base['policy_hash'],
            'Exact canonical registry revision/policy required')
        deployment=registry['deployment']
        require(set(deployment)==set(self.template) and {k:v for k,v in deployment.items() if k!='workspaces'}==
            {k:v for k,v in self.template.items() if k!='workspaces'},'Qualification, images and measured pool cannot change')
        validate_approvals(deployment['workspaces'],self.caps)
        history=doc['history']
        require(isinstance(history,list) and len(history)<=256,'Bounded prior document references required')
        refs=[reference(v) for v in history]
        require(len({(r['namespace'],r['name'],r['uid']) for r in refs})==len(refs)
            and all(r['policy_hash']==doc['policy_hash']
                and r['revision']!=doc['revision'] for r in refs),'Distinct same-policy prior document references required')
        return doc

    def current(self):
        value=self.document(self.reference)
        if self.loaded is not None:require(value==self.loaded,'Loaded approval document changed')
        self.loaded=copy.deepcopy(value);return value

    def _envelope(self,cm,models,doc,ref):
        body=self.agent.parse(cm.get('data',{}).get('enrollment.json','{}'))
        require(isinstance(body,dict) and body.get('approval_ref')==ref,'Frozen approved document reference required')
        require(cm['data']['enrollment.json']==canonical(body),'Canonical immutable approved enrollment required')
        scope=str(body.get('source'))+':'+str(body.get('workspace'))
        approval=doc['registry']['deployment']['workspaces'].get(scope)
        require(approval is not None and body.get('members')==sorted(approval['members']) and body.get('name')==approval['pod']
            and body.get('namespace')==approval['namespace'] and body.get('principal')==approval['principal']
            and body.get('profile')==approval['profiles'][0],'Exact Source-approved membership/Pod/profile binding required')
        structural=copy.deepcopy(cm);structural_body=copy.deepcopy(body);del structural_body['approval_ref']
        structural['data']['enrollment.json']=self.agent.canonical_json(structural_body)
        config=copy.deepcopy(self.base);config['terminal_history']={}
        config['workspaces']={scope:{'profile':approval['profiles'][0],'cap_mib':self.caps[approval['profiles'][0]]}}
        envelope=self.agent.validate_enrollment(structural,config,models)
        envelope['enrollment']=copy.deepcopy(body);return envelope

    def validate_enrollment(self,cm,models,store=None,journal=None):
        current=self.current();body=self.agent.parse(cm.get('data',{}).get('enrollment.json','{}'))
        ref=reference(body.get('approval_ref'))
        require(ref['namespace']==self.reference['namespace'] and (ref==self.reference or ref in current['history']),
            'Only the selected node copy can bind enrollment authority')
        doc=current if ref==self.reference else self.document(ref)
        scope=str(body.get('source'))+':'+str(body.get('workspace'))
        require(doc['registry']['deployment']['workspaces'].get(scope)==current['registry']['deployment']['workspaces'].get(scope)
            and scope in current['registry']['deployment']['workspaces'],'Revoked/changed approval cannot authorize an active lifetime')
        envelope=self._envelope(cm,models,current,ref)
        if ref!=self.reference:
            uid=envelope['enrollment']['intent']['pod_uid'];body=envelope['enrollment']
            require(store is not None and journal is not None,'Prior approval cannot authorize a new or pending lifetime')
            expected=dict(version=1,approval_ref=ref,enrollment_uid=envelope['configmap_uid'],enrollment_sha256=digest(body))
            record=journal.read(uid)
            require(store.backend.private_read(self._ref_path(store,uid),store.uid)==expected
                and store.backend.private_read(store.state/'enrollments'/(uid+'.json'),store.uid)==envelope
                and type(record) is models.CapRecord and record.state=='sealed' and record.intent.to_dict()==body['intent']
                and record.readback.soft==record.readback.hard==body['cap_mib']*1048576,
                'Prior reference permits only an original protected sealed continuation under the latest unchanged approval')
            self.agent.validate_pool_epoch(self.base,record.identity.epoch)
        return envelope

    def _ref_path(self,store,uid):return store.state/'approval-references'/(uid+'.json')

    def remember(self,envelope,store):
        body=envelope['enrollment'];uid=body['intent']['pod_uid'];ref=reference(body['approval_ref'])
        require(store.backend.private_read(store.state/'enrollments'/(uid+'.json'),store.uid)==envelope,
            'Original protected enrollment must precede approval custody')
        directory=store.state/'approval-references';directory.mkdir(mode=0o700,exist_ok=True)
        store.backend.private_directory(directory,store.uid)
        expected=dict(version=1,approval_ref=ref,enrollment_uid=envelope['configmap_uid'],enrollment_sha256=digest(body))
        prior=store.backend.private_read(self._ref_path(store,uid),store.uid)
        require(prior is None or prior==expected,'Original per-UID approval authority changed')
        if prior is None:
            require(ref==self.reference,'Prior revisions cannot synthesize new protected enrollment authority')
            store.backend.private_write(self._ref_path(store,uid),expected,store.uid,create=True)

    def _terminal(self,cm,models,store,journal,kube,current):
        body=self.agent.parse(cm.get('data',{}).get('enrollment.json','{}'));uid=body['intent']['pod_uid'];ref=reference(body.get('approval_ref'))
        require(ref['namespace']==self.reference['namespace'] and (ref==self.reference or ref in current['history']),
            'Original node approval reference was not retained')
        old=self.document(ref);envelope=self._envelope(cm,models,old,ref)
        expected=dict(version=1,approval_ref=ref,enrollment_uid=envelope['configmap_uid'],enrollment_sha256=digest(body))
        require(store.backend.private_read(self._ref_path(store,uid),store.uid)==expected
            and store.backend.private_read(store.state/'enrollments'/(uid+'.json'),store.uid)==envelope
            and store.backend.private_read(store.state/'intents'/(uid+'.json'),store.uid)==body['intent'],
            'Original protected per-UID approval/enrollment/intent required')
        def read_envelope():
            require(self.document(ref)==old,'Original approval document changed')
            return self._envelope(kube.configmap(envelope['authority_namespace'],envelope['configmap_name']),models,old,ref)
        return self._completed(envelope,models,store,journal,kube,read_envelope)

    def _completed(self,envelope,models,store,journal,kube,read_envelope):
        body=envelope['enrollment'];uid=body['intent']['pod_uid'];intent=models.CapIntent(**body['intent'])
        require(store.backend.private_read(store.state/'enrollments'/(uid+'.json'),store.uid)==envelope
            and store.backend.private_read(store.state/'intents'/(uid+'.json'),store.uid)==body['intent'],
            'Original protected enrollment and intent required for terminal acceptance')
        for _ in range(2):
            require(read_envelope()==envelope,'Original immutable completed enrollment changed on fresh GET')
            ledger_cm=kube.configmap(self.base['authority_namespace'],'cps-native-gpu-allocations')
            allocation=self.agent.abort_ledger(ledger_cm,self.base['authority_namespace'])['allocations'].get(body['binding_id'])
            require(isinstance(allocation,dict) and allocation.get('state')=='released' and all(allocation.get(k)==v for k,v in body.items()),
                'Exact frozen released allocation required')
            record=journal.read(uid)
            if record is None:
                prior=store.abort_record(uid)
                if prior is None:
                    reader=getattr(self,'abort_epoch_reader',None)
                    require(callable(reader),'Fresh healthy epoch required before first approved abort recognition')
                    recognized=self.agent.recognize_aborts(store,journal,{uid:envelope},kube,None,models,epoch_reader=reader)
                    require(uid in recognized,'Actual immutable never-gated abort proof required')
                    prior=store.abort_record(uid)
                require(prior is not None,'Never-gated completion must be protected')
                completion=kube.configmap(self.base['authority_namespace'],'cps-native-abort-'+body['binding_id'][:40])
                proof=self.agent.validate_abort(completion,envelope,ledger_cm,models.DriverEpoch(**prior['payload']['node_epoch']),models)
                require(store.abort_published(uid,envelope,proof),'Original immutable abort completion required')
            else:
                require(type(record) is models.CapRecord and record.intent.to_dict()==body['intent']
                    and record.state=='retired-inert-cap' and record.retirement is not None
                    and record.retirement.entry.used==0 and record.retirement.entry.offline is True
                    and record.readback.soft==record.readback.hard==record.retirement.entry.soft==record.retirement.entry.hard==intent.cap_mib*1048576,
                    'Original finite zero-charge retirement required')
                self.agent.validate_pool_epoch(self.base,record.identity.epoch)
                completion=kube.configmap(self.base['authority_namespace'],'cps-native-cleanup-'+body['binding_id'][:40])
                require(store.cleanup_published(uid,envelope,record,completion),'Original immutable cleanup publication required')
            pod=kube.pod(intent)
            if pod is not None:
                meta=pod.get('metadata',{}) if isinstance(pod,dict) else {}
                require(isinstance(pod,dict) and pod.get('apiVersion')=='v1' and pod.get('kind')=='Pod'
                    and meta.get('namespace')==intent.namespace and meta.get('name')==intent.name
                    and self.agent.canonical_uuid(meta.get('uid')) and meta['uid']!=uid,'Original approved Pod UID must remain absent')
        return envelope

    def _allocation(self,allocation,body,states):
        require(isinstance(allocation,dict) and allocation.get('state') in states
            and all(allocation.get(k)==v for k,v in body.items()),'Exact actual frozen allocation and state required')

    def validate_enrollments(self,cms,models,store,journal,kube):
        current=self.current();legacy=[];dynamic=[]
        self.store,self.journal=store,journal
        for cm in cms:
            body=self.agent.parse(cm.get('data',{}).get('enrollment.json','{}'))
            (dynamic if 'approval_ref' in body else legacy).append(cm)
        envelopes,historical=self.agent.validate_authority_enrollments(legacy,self.base,models,store,journal,kube)
        ledger=self.agent.abort_ledger(kube.configmap(self.base['authority_namespace'],'cps-native-gpu-allocations'),self.base['authority_namespace'])
        for envelope in list(envelopes):
            body=envelope['enrollment'];uid=body['intent']['pod_uid']
            if uid in historical:continue  # Original configured historical context stays untouched.
            allocation=ledger['allocations'].get(body['binding_id'])
            self._allocation(allocation,body,{'enrolling','enrolled','releasing','released'})
            if isinstance(allocation,dict) and allocation.get('state')=='released':
                self._completed(envelope,models,store,journal,kube,lambda envelope=envelope:
                    self.agent.validate_enrollment(kube.configmap(envelope['authority_namespace'],envelope['configmap_name']),self.base,models))
                historical.add(uid)
            else:
                scope=body['source']+':'+body['workspace']
                approval=current['registry']['deployment']['workspaces'].get(scope)
                require(approval is not None and approval==self.template['workspaces'].get(scope)
                    and body['members']==sorted(approval['members']) and body['name']==approval['pod']
                    and body['profile']==approval['profiles'][0]
                    and store.backend.private_read(store.state/'enrollments'/(uid+'.json'),store.uid)==envelope,
                    'A revoked seed or new unreferenced lifetime cannot bypass the current approval revision')
        for cm in dynamic:
            body=self.agent.parse(cm['data']['enrollment.json']);uid=body['intent']['pod_uid']
            allocation=ledger['allocations'].get(body['binding_id'])
            require(uid not in historical,'Duplicate old/new Pod identity')
            self._allocation(allocation,body,{'enrolling','enrolled','releasing','released'})
            if isinstance(allocation,dict) and allocation.get('state')=='released':
                envelope=self._terminal(cm,models,store,journal,kube,current);historical.add(uid)
            else:envelope=self.validate_enrollment(cm,models,store,journal)
            envelopes.append(envelope)
        folder=store.state/'approval-references'
        existing={p.stem for p in folder.glob('*.json')} if folder.exists() else set()
        require(existing<={e['enrollment']['intent']['pod_uid'] for e in envelopes},'Missing immutable approved enrollment blocks authority')
        return envelopes,historical

    def acknowledge(self,process,pod,epoch,successful,publish):
        require(successful is True,'Failed/incomplete custody iteration cannot acknowledge readiness')
        require(self.loaded is not None and self.current()==self.loaded,'Actually loaded document required')
        require(isinstance(process,dict) and set(process)=={'namespace','name','uid','container','image','service_account'}
            and all(isinstance(process[k],str) and NAME.fullmatch(process[k]) for k in ('namespace','name','container','service_account'))
            and self.agent.canonical_uuid(process['uid']) and isinstance(process['image'],str) and IMAGE.fullmatch(process['image'])
            and process['namespace']==self.reference['namespace'],'Exact operator-selected process declaration required')
        meta=pod.get('metadata',{}) if isinstance(pod,dict) else {};spec=pod.get('spec',{}) if isinstance(pod,dict) else {};status=pod.get('status',{}) if isinstance(pod,dict) else {}
        require(isinstance(pod,dict) and pod.get('apiVersion')=='v1' and pod.get('kind')=='Pod'
            and all(meta.get(k)==process[k] for k in ('namespace','name','uid')) and not meta.get('deletionTimestamp')
            and spec.get('nodeName')==self.base['pool']['node'] and spec.get('serviceAccountName')==process['service_account']
            and status.get('phase')=='Running' and any(c.get('type')=='Ready' and c.get('status')=='True' for c in status.get('conditions',[]))
            and any(c.get('name')==process['container'] and c.get('image')==process['image'] for c in spec.get('containers',[]))
            and any(c.get('name')==process['container'] and c.get('ready') is True
                and isinstance(c.get('imageID'),str) and c['imageID'].endswith('sha256:'+process['image'].split('@sha256:',1)[1])
                for c in status.get('containerStatuses',[])),
            'Actual live Ready process UID/service-account/image required')
        require(isinstance(epoch,dict) and set(epoch)=={'node_uid','boot_id','driver_generation','gpu_uuid'}
            and all(epoch[k]==self.base['pool'][k] for k in epoch),'Actual unchanged driver epoch required')
        ack=dict(version=1,component='node',revision=self.reference['revision'],policy_hash=self.reference['policy_hash'],
            document=copy.deepcopy(self.reference),process=copy.deepcopy(process),driver_epoch=copy.deepcopy(epoch),
            observed_at=datetime.now(timezone.utc).isoformat())
        publish(copy.deepcopy(ack));return ack


def read_private(path,*,trusted_uid=0,limit=1048576):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==trusted_uid and info.st_nlink==1
            and stat.S_IMODE(info.st_mode)==0o400 and info.st_size<=limit,'Root-selected bounded regular0400 approval input required')
        raw=os.read(fd,limit+1);require(len(raw)<=limit,'Oversized approval input');return parse(raw)
    finally:os.close(fd)


def validate_approved_pod(consumer,pod,envelope):
    """Current approval pins images and storage in the already admitted spec."""
    consumer.validate_enrollment(_enrollment_object(envelope),consumer.models,getattr(consumer,'store',None),getattr(consumer,'journal',None))
    body=envelope['enrollment'];consumer.agent.validate_actual_pod(pod,body)
    ledger=consumer.agent.abort_ledger(consumer.get(consumer.base['authority_namespace'],'cps-native-gpu-allocations'),consumer.base['authority_namespace'])
    consumer._allocation(ledger['allocations'].get(body['binding_id']),body,{'enrolling','enrolled'})
    approval=consumer.current()['registry']['deployment']['workspaces'][body['source']+':'+body['workspace']]
    spec=pod['spec'];init=spec['initContainers'];containers=spec['containers'];storage=approval['storage']
    require(init[0]['image']==consumer.template['gateImage']
        and all(c['image']==consumer.template['workloadImage'] for c in containers+init[1:]),'Current approved gate/workload images required')
    volumes=spec.get('volumes',[]);require(isinstance(volumes,list) and len({v.get('name') for v in volumes})==len(volumes),'Distinct reviewed volumes required')
    by_name={v.get('name'):v for v in volumes}
    pvc=[v for v in volumes if 'persistentVolumeClaim' in v]
    require(len(pvc)==1 and pvc[0].get('persistentVolumeClaim')=={'claimName':storage['pvc']},'Only the approved writable group PVC may be mounted')
    require(all(any(m.get('name')==pvc[0]['name'] and m.get('mountPath')=='/workspace'
        and m.get('readOnly',False) is False and not m.get('subPath') and not m.get('subPathExpr')
        for m in c.get('volumeMounts',[])) for c in containers),'Exact writable group workspace mount required')
    nfs={v['name']:v['nfs'] for v in volumes if 'nfs' in v}
    expected={(m['server'],m['path'],m['mount_path']) for m in storage['readonly_mounts']}
    actual=set()
    for c in containers:
        for mount in c.get('volumeMounts',[]):
            if mount.get('name') in nfs:
                volume=nfs[mount['name']]
                require(set(volume)=={'server','path','readOnly'} and volume['readOnly'] is True
                    and mount.get('readOnly') is True,'Readonly course data required')
                actual.add((volume['server'],volume['path'],mount['mountPath']))
    require(actual==expected and len(nfs)==len(expected),'Exact approved readonly dataset mounts required')
    controls={'cps-native-receipts':'/run/cps-native-gpu/receipts','cps-native-authority':'/run/cps-native-gpu/authority',
        'cps-native-driver-metadata':'/sys/module'}
    for volume in volumes:
        if 'hostPath' in volume:
            require(volume['name'] in controls and volume['hostPath']=={'path':controls[volume['name']],'type':'Directory'},'Only trusted readonly CPU gate host paths required')
            for c in containers+init:
                for mount in c.get('volumeMounts',[]):
                    if mount.get('name')==volume['name']:
                        require(c['name']=='cps-native-cap-gate' and mount.get('readOnly') is True,'Workloads may never mount node control paths')
        require(set(volume) in ({'name','persistentVolumeClaim'},{'name','nfs'},{'name','emptyDir'},{'name','hostPath'}),'Unknown volume source forbidden')


ApprovalConsumer.validate_approved_pod = validate_approved_pod


def _enrollment_object(envelope):
    body=envelope['enrollment']
    return {'apiVersion':'v1','kind':'ConfigMap','immutable':True,
        'metadata':{'namespace':envelope['authority_namespace'],'name':envelope['configmap_name'],
            'uid':envelope['configmap_uid'],'labels':{'cps.compute/native-binding':body['binding_id']}},
        'data':{'enrollment.json':canonical(body)}}


def render_process_observer(raw):
    """Stdlib overlay of the reviewed SDK observer; security checks unchanged."""
    require(isinstance(raw,bytes) and hashlib.sha256(raw).hexdigest()==PROCESS_SOURCE_SHA256,
        'Exact reviewed process observer source required')
    source=raw.decode();anchor='from .native_group_revision import _api_document, _uid'
    replacement="""import uuid

def _api_document(core,value):
    if isinstance(value,dict):return json.loads(json.dumps(value,allow_nan=False))
    return core.api_client.sanitize_for_serialization(value)

def _uid(value):
    try:return isinstance(value,str) and str(uuid.UUID(value))==value and uuid.UUID(value).int!=0
    except (ValueError,TypeError,AttributeError):return False
"""
    require(source.count(anchor)==1,'Exact process import adapter anchor required')
    result=source.replace(anchor,replacement)
    original={n.name:ast.get_source_segment(source,n) for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)}
    derived={n.name:ast.get_source_segment(result,n) for n in ast.parse(result).body if isinstance(n,ast.FunctionDef)}
    require(all(derived[name]==body for name,body in original.items()),'Unchanged process security matcher required')
    require(hashlib.sha256(result.encode()).hexdigest()==PROCESS_OVERLAY_SHA256,
        'Exact process observer overlay closure required')
    compile(result,'native_approval_process.py','exec');return result


def acknowledgment_target(value):
    require(isinstance(value,dict) and set(value)=={'namespace','name','uid'}
        and all(isinstance(value[k],str) and NAME.fullmatch(value[k]) for k in ('namespace','name')),
        'Exact precreated acknowledgment namespace/name required')
    try:valid=isinstance(value['uid'],str) and str(uuid.UUID(value['uid']))==value['uid'] and uuid.UUID(value['uid']).int!=0
    except (ValueError,TypeError,AttributeError):valid=False
    require(valid,'Actual precreated acknowledgment UID required');return copy.deepcopy(value)


def _acknowledgment_body(value,target,*,initial=False):
    if initial and value=={}:return value
    fields={'version','component','revision','policy_hash','document','process','driver_epoch','observed_at'}
    require(isinstance(value,dict) and set(value)==fields and type(value['version']) is int and value['version']==1
        and value['component']=='node','Only the node component acknowledgment may be updated')
    ref=reference(value['document'])
    require(ref['namespace']==target['namespace'] and value['revision']==ref['revision']
        and value['policy_hash']==ref['policy_hash'] and isinstance(value['process'],dict)
        and value['process'].get('namespace')==target['namespace'],'Exact node acknowledgment document/process scope required')
    return value


def _acknowledgment_map(cm,target):
    meta=cm.get('metadata',{}) if isinstance(cm,dict) else {}
    require(isinstance(cm,dict) and cm.get('apiVersion')=='v1' and cm.get('kind')=='ConfigMap'
        and cm.get('immutable') is not True and not cm.get('binaryData') and isinstance(meta,dict)
        and all(meta.get(k)==target[k] for k in target) and not meta.get('ownerReferences')
        and not meta.get('deletionTimestamp') and isinstance(meta.get('resourceVersion'),str)
        and 0<len(meta['resourceVersion'])<=256 and not any(c.isspace() for c in meta['resourceVersion'])
        and isinstance(cm.get('data'),dict) and set(cm['data'])=={'ack.json'},
        'Existing exact mutable acknowledgment ConfigMap required')
    old=parse(cm['data']['ack.json'])
    require(cm['data']['ack.json']==canonical(old),'Canonical acknowledgment preimage required')
    _acknowledgment_body(old,target,initial=True);return cm


def patch_acknowledgment(kube,path,operations):
    """Existing own-SA fixed resource PATCH, never create/list credentials."""
    require(isinstance(path,str) and re.fullmatch('/api/v1/namespaces/[a-z0-9.-]+/configmaps/[a-z0-9.-]+',path),
        'Exact named acknowledgment API path required')
    raw=canonical(operations).encode();require(len(raw)<=65536,'Bounded acknowledgment CAS required')
    request=urllib.request.Request(kube.base+path,data=raw,method='PATCH',
        headers={'Authorization':'Bearer '+kube.token,'Content-Type':'application/json-patch+json'})
    try:
        with kube.opener.open(request,timeout=5) as response:
            body=response.read(1048577)
            require(len(body)<=1048576,'Bounded acknowledgment response required');return parse(body)
    except urllib.error.HTTPError as error:
        raise ValueError('Acknowledgment API failed with HTTP '+str(error.code)) from None


def publish_existing_acknowledgment(kube,target,ack,verify,*,patch=None):
    """Full UID/RV/data CAS on one precreated CM after fresh trusted proof."""
    target=acknowledgment_target(target);_acknowledgment_body(ack,target)
    require(callable(verify) and verify()==ack,'Fresh protected acknowledgment proof required')
    path='/api/v1/namespaces/'+target['namespace']+'/configmaps/'+target['name']
    before=copy.deepcopy(_acknowledgment_map(kube.call('GET',path),target))
    require(verify()==ack,'Acknowledgment proof changed before CAS')
    desired={'ack.json':canonical(ack)}
    operations=[{'op':'test','path':'/metadata/uid','value':target['uid']},
        {'op':'test','path':'/metadata/resourceVersion','value':before['metadata']['resourceVersion']},
        {'op':'test','path':'/data','value':before['data']},{'op':'replace','path':'/data','value':desired}]
    result=(patch or (lambda path,ops:patch_acknowledgment(kube,path,ops)))(path,operations)
    _acknowledgment_map(result,target)
    require(result['data']==desired,'Acknowledgment response did not contain the verified proof')
    after=copy.deepcopy(result);after['data']=before['data']
    after['metadata']['resourceVersion']=before['metadata']['resourceVersion']
    original=copy.deepcopy(before)
    # Kubernetes may record this PATCH's field manager. No user metadata,
    # immutable identity, data precondition or other field is normalized.
    after['metadata'].pop('managedFields',None);original['metadata'].pop('managedFields',None)
    require(after==original,'Acknowledgment CAS changed unrelated fields')
    observed=_acknowledgment_map(kube.call('GET',path),target)
    require(observed==result and verify()==ack,'Acknowledgment changed during final observation')
    return copy.deepcopy(result)


class ProcessObservationAPI:
    """Fixed named GET adapter for the unchanged SDK process observer."""
    def __init__(self,kube):self.kube=kube
    def _get(self,group,kind,name,namespace):
        require(all(isinstance(v,str) and NAME.fullmatch(v) for v in (name,namespace)),
            'Exact named process observation required')
        return self.kube.call('GET',group+'/namespaces/'+namespace+'/'+kind+'/'+name)
    def read_namespaced_pod(self,name,namespace):return self._get('/api/v1','pods',name,namespace)
    def read_namespaced_deployment(self,name,namespace):return self._get('/apis/apps/v1','deployments',name,namespace)
    def read_namespaced_replica_set(self,name,namespace):return self._get('/apis/apps/v1','replicasets',name,namespace)
    def read_namespaced_daemon_set(self,name,namespace):return self._get('/apis/apps/v1','daemonsets',name,namespace)


class EnrollmentSnapshotAdvanced(ValueError):
    """A validated current-ref append requires a new complete custody iteration."""


def require_same_enrollment_snapshot(accepted,fresh,current_reference,journal):
    # The caller must first run the full existing authority validator and all
    # document/process/epoch checks. This never converts a validation denial.
    actual={e['enrollment']['intent']['pod_uid']:e for e in fresh}
    require(len(actual)==len(fresh),'Duplicate immutable enrollment snapshot')
    records=journal.records()
    require(all(r.intent.pod_uid in accepted and r.intent.to_dict()==accepted[r.intent.pod_uid]['enrollment']['intent']
        for r in records),'Original full journal custody changed during acknowledgment')
    if actual==accepted:return
    require(all(actual.get(uid)==row for uid,row in accepted.items()),
        'Original accepted enrollment removed or changed before acknowledgment')
    additions=set(actual)-set(accepted)
    require(bool(additions) and all(actual[uid]['enrollment'].get('approval_ref')==current_reference for uid in additions),
        'Only validated new current-reference enrollments may restart custody')
    raise EnrollmentSnapshotAdvanced('Validated immutable enrollment snapshot advanced; recheck full custody')


class NodeApprovalRuntime:
    """Optional service-loop bridge. Private ack transport confers no API RBAC."""
    def __init__(self,agent,reference_path,qualification_path,process_path,state,*,acknowledgment_path=None,process_observer=None):
        self.agent=agent;self.reference_path=reference_path;self.qualification_path=qualification_path
        self.process_path=process_path;self.state=Path(state);self.consumer=None
        require((acknowledgment_path is None)==(process_observer is None),'Complete optional own-SA publisher inputs required')
        self.acknowledgment_path=acknowledgment_path;self.process_observer=process_observer

    def begin(self,config,kube):
        self.consumer=ApprovalConsumer(self.agent,config,read_private(self.qualification_path),
            read_private(self.reference_path,limit=8192),kube.configmap)
        self.consumer.current()
        # An interrupted/failed iteration must not leave a newly current ack.
        backend=self.agent.load_source('_approval_private_backend',self.agent.snapshot_sources()['node_backend.py'].encode(),
            self.agent.SOURCE_PINS['node_backend.py'],'node_backend.py')
        path=self.state/'approval-loaded.json'
        if backend.private_read(path,0) is not None:path.unlink()
        return self.consumer

    def finish(self,config,models,store,journal,kube,accepted,driver,verifier,successful):
        require(successful is True,'Blocked custody iteration cannot publish readiness')
        consumer=self.consumer;require(consumer is not None,'Actually loaded approval runtime required')
        fresh,historical=consumer.validate_enrollments(kube.enrollments(config['authority_namespace']),models,store,journal,kube)
        records=journal.records()
        require(all(r.intent.pod_uid in accepted and r.intent.to_dict()==accepted[r.intent.pod_uid]['enrollment']['intent'] for r in records),
            'Full native journal/enrollment custody required before acknowledgment')
        document_path=Path(self.reference_path).parent/'approval.json'
        require(read_private(document_path)==consumer.loaded,'Actually mounted and API approval document differ')
        declaration=read_private(self.process_path,limit=8192)
        if self.process_observer is not None:
            declaration=self.process_observer.validate_process_declaration(declaration)
        else:require(isinstance(declaration,dict) and set(declaration) in (
            {'namespace','container','image','service_account'},
            {'namespace','kind','name','uid','container','image','service_account'}),'Trusted fixed process template required')
        process={k:declaration[k] for k in ('namespace','container','image','service_account')}
        require(os.environ.get('CPS_NATIVE_APPROVAL_POD_NAMESPACE')==process['namespace'],'Downward process namespace disagrees')
        process.update(name=os.environ.get('CPS_NATIVE_APPROVAL_POD_NAME'),uid=os.environ.get('CPS_NATIVE_APPROVAL_POD_UID'))
        require(self.agent.canonical_uuid(process['uid']) and isinstance(process['name'],str) and NAME.fullmatch(process['name']),'Actual downward process identity required')
        pod=kube.call('GET','/api/v1/namespaces/'+process['namespace']+'/pods/'+process['name'])
        epoch=self.agent.abort_current_epoch(config,self.state,driver,verifier,models)
        def publish(value):
            path=self.state/'approval-loaded.json'
            store.backend.private_write(path,value,store.uid,create=store.backend.private_read(path,store.uid) is None)
        ack=consumer.acknowledge(process,pod,dict(node_uid=epoch.node_uid,boot_id=epoch.boot_id,
            driver_generation=epoch.driver_generation,gpu_uuid=epoch.gpu_uuid),True,lambda _:None)
        require_same_enrollment_snapshot(accepted,fresh,consumer.reference,journal)
        publish(ack)
        if self.process_observer is not None:
            self.publish(kube,config,models,store,journal,accepted,driver,verifier,declaration,ack)
        return ack

    def publish(self,kube,config,models,store,journal,accepted,driver,verifier,declaration,ack):
        """Revalidate private proof and full custody before one named CM CAS."""
        target=acknowledgment_target(read_private(self.acknowledgment_path,limit=8192))
        require(target['namespace']==declaration['namespace']==self.consumer.reference['namespace'],
            'Only the own-node component acknowledgment may be published')
        api=ProcessObservationAPI(kube);path=self.state/'approval-loaded.json'
        def verify():
            require(store.backend.private_read(path,store.uid)==ack,'Original protected private acknowledgment required')
            fresh,historical=self.consumer.validate_enrollments(kube.enrollments(config['authority_namespace']),models,store,journal,kube)
            records=journal.records()
            require(all(r.intent.pod_uid in accepted and r.intent.to_dict()==accepted[r.intent.pod_uid]['enrollment']['intent'] for r in records),
                'Full original journal custody required before acknowledgment publication')
            require(read_private(Path(self.reference_path).parent/'approval.json')==self.consumer.loaded,
                'Mounted approval changed before acknowledgment publication')
            pod,expected=self.process_observer.observe_process(api,api,declaration,ack['process'])
            volumes={row.get('name') for row in pod['spec'].get('volumes',[]) if isinstance(row,dict)
                and isinstance(row.get('configMap'),dict) and row['configMap'].get('name')==self.consumer.reference['name']}
            selected=[row for row in pod['spec']['containers'] if row.get('name')==expected['container']]
            require(len(selected)==1 and any(row.get('name') in volumes and row.get('readOnly') is True
                and row.get('mountPath')=='/var/run/cps-native-approvals/approval.json' and row.get('subPath')=='approval.json'
                and not row.get('subPathExpr') for row in selected[0].get('volumeMounts',[])),
                'Actual readonly own-node approval mount required')
            current=self.agent.abort_current_epoch(config,self.state,driver,verifier,models)
            regenerated=self.consumer.acknowledge(expected,pod,dict(node_uid=current.node_uid,boot_id=current.boot_id,
                driver_generation=current.driver_generation,gpu_uuid=current.gpu_uuid),True,lambda _:None)
            require({k:v for k,v in regenerated.items() if k!='observed_at'}=={k:v for k,v in ack.items() if k!='observed_at'},
                'Current process/document/epoch differs from the private proof')
            try:observed=datetime.fromisoformat(ack['observed_at'].replace('Z','+00:00'))
            except (ValueError,TypeError,AttributeError):raise ValueError('Aware protected acknowledgment timestamp required') from None
            require(observed.tzinfo is not None and 0<=(datetime.now(timezone.utc)-observed).total_seconds()<=30,
                'Stale or future protected node acknowledgment')
            require(store.backend.private_read(path,store.uid)==ack,'Private proof changed during observation')
            require_same_enrollment_snapshot(accepted,fresh,self.consumer.reference,journal)
            return copy.deepcopy(ack)
        try:return publish_existing_acknowledgment(kube,target,ack,verify)
        except EnrollmentSnapshotAdvanced:
            require(store.backend.private_read(path,store.uid)==ack,'Private proof changed while invalidating superseded iteration')
            path.unlink()
            raise


def render_current_agent(original,module_raw):
    """Exact source derivative of reviewed 3bae; legacy repo defaults unchanged.

    Only run/main are altered. No validator, source pin, controller, recovery,
    historical context, driver call or cleanup protocol is replaced.
    """
    require(isinstance(original,str) and hashlib.sha256(original.encode()).hexdigest()==BASE_SOURCE_SHA256,'Exact reviewed current3bae node source required')
    require(isinstance(module_raw,bytes) and module_raw==Path(__file__).read_bytes(),'Exact reviewed approval consumer source required')
    result=original
    def change(old,new):
        nonlocal result
        require(result.count(old)==1,'Exact current node adapter anchor required');result=result.replace(old,new)
    change('def run(config, bundle, state, kube, driver, *, iterations, interval, crictl, cri_socket):',
        'def run(config, bundle, state, kube, driver, *, iterations, interval, crictl, cri_socket, approval=None):')
    change("        cms = kube.enrollments(config['authority_namespace'])\n", "        cms = kube.enrollments(config['authority_namespace'])\n        consumer = approval.begin(config, kube) if approval is not None else None\n        if consumer is not None:\n            consumer.models = models\n            consumer.abort_epoch_reader = lambda: abort_current_epoch(config, state, driver, verifier, models)\n")
    change('            envelopes, historical = validate_authority_enrollments(cms, config, models, store, journal, kube)',
        '            envelopes, historical = validate_authority_enrollments(cms, config, models, store, journal, kube) if consumer is None else consumer.validate_enrollments(cms, models, store, journal, kube)')
    change('            accepted = store.synchronize(envelopes)',
        "            accepted = store.synchronize(envelopes)\n            if consumer is not None:\n                for envelope in envelopes:\n                    if 'approval_ref' in envelope['enrollment']: consumer.remember(envelope, store)")
    change("            validate_actual_pod(pod, accepted[intent.pod_uid]['enrollment'])",
        "            if consumer is not None and 'approval_ref' in accepted[intent.pod_uid]['enrollment']:\n                consumer.validate_approved_pod(pod, accepted[intent.pod_uid])\n            validate_actual_pod(pod, accepted[intent.pod_uid]['enrollment'])")
    change("                if pod is not None: validate_actual_pod(pod, accepted[intent.pod_uid]['enrollment'])",
        "                if pod is not None:\n                    if consumer is not None and 'approval_ref' in accepted[intent.pod_uid]['enrollment']:\n                        consumer.validate_approved_pod(pod, accepted[intent.pod_uid])\n                    validate_actual_pod(pod, accepted[intent.pod_uid]['enrollment'])")
    change("        if iteration + 1 < iterations: time.sleep(interval)\n    require(not failures, 'Node agent observed blocked errors; allocations and protection retained')",
        "        if approval is not None:\n            try:\n                approval.finish(config, models, store, journal, kube, accepted, driver, verifier, not failures)\n            except approval_module.EnrollmentSnapshotAdvanced:\n                print(json.dumps({'state': 'approval-snapshot-advanced-retry', 'iteration': iteration, 'production_qualified': False}), flush=True)\n                continue\n        if iteration + 1 < iterations: time.sleep(interval)\n    require(not failures, 'Node agent observed blocked errors; allocations and protection retained')")
    change("    parser.add_argument('--config', type=Path)","    parser.add_argument('--config', type=Path)\n    parser.add_argument('--approval-reference', type=Path)\n    parser.add_argument('--approval-template', type=Path)\n    parser.add_argument('--approval-process', type=Path)\n    parser.add_argument('--approval-acknowledgment', type=Path)")
    change("    config = read_config(args.config)","    config = read_config(args.config)\n    require(all(v is not None for v in (args.approval_reference,args.approval_template,args.approval_process)) or\n            all(v is None for v in (args.approval_reference,args.approval_template,args.approval_process)), 'Complete optional approval inputs required')\n    require(args.approval_acknowledgment is None or args.approval_reference is not None, 'Publisher requires installed approval consumer')")
    module_sha=hashlib.sha256(module_raw).hexdigest()
    change("        driver = modules['manual'].Nvml()", "        approval = None\n        if args.approval_reference is not None:\n            global approval_module\n            approval_module = load_source('_native_approval_revision', (args.bundle / 'native_approval_revision.py').read_bytes(),\n                '"+module_sha+"', 'native_approval_revision.py')\n            process_observer = None\n            if args.approval_acknowledgment is not None:\n                process_observer = load_source('_native_approval_process', (args.bundle / 'native_approval_process.py').read_bytes(),\n                    '"+PROCESS_OVERLAY_SHA256+"', 'native_approval_process.py')\n            approval = approval_module.NodeApprovalRuntime(sys.modules[__name__],args.approval_reference,args.approval_template,args.approval_process,state,\n                acknowledgment_path=args.approval_acknowledgment,process_observer=process_observer)\n        driver = modules['manual'].Nvml()")
    change('            crictl=args.crictl, cri_socket=args.cri_socket)', '            crictl=args.crictl, cri_socket=args.cri_socket, approval=approval)')
    before={n.name:ast.get_source_segment(original,n) for n in ast.parse(original).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    after={n.name:ast.get_source_segment(result,n) for n in ast.parse(result).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    require(set(before)==set(after) and all(before[name]==after[name] for name in before if name not in ('run','main')),
        'Unchanged historical, driver, recovery and source-loading definitions required')
    compile(result,'node_agent.py','exec');return result
