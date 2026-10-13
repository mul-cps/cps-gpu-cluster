"""Pure approval-document, projection-CAS and observed-readiness intents.

Only an operator-pinned authenticated Source export may supply source_sha256
and trusted_revision. This module performs no API calls, Secret lookup, GPU
operations or deployment; actual ConfigMap UIDs must be supplied after create.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat

from cps_compute.native_group_approvals import ApprovalSnapshot
from cps_compute.native_group_revision import (ApprovalRevision, approval_envelope, validate_ack,
    validate_reference, validate_acknowledgment_reference)
from cps_compute.native_group_process import validate_process_declaration, observe_process
from cps_compute.native_gpu_controller import DriverEpoch
from cps_compute.native_groups import NativeGroupDeployment, canonical_sha256
from cps_compute.policy import Policy
from qualification_transition_proposal import object_guard, immutable_config, replace_patch

COMPONENTS = ('gateway', 'hub:cps', 'hub:cit', 'node')
DIRECTORY = '/var/run/cps-native-approvals'
DOC_VOLUME = 'cps-native-approval-document'
REF_VOLUME = 'cps-native-approval-reference'
BOOTSTRAP_VOLUME = 'cps-native-approval-bootstrap'
PUBLISHER_VOLUME = 'cps-native-approval-publisher'
OWNED_VOLUMES = {DOC_VOLUME, REF_VOLUME, BOOTSTRAP_VOLUME, PUBLISHER_VOLUME}
PUBLISHER_ENV = 'CPS_NATIVE_APPROVAL_PUBLISHER_PATH'
ENV = {
    'CPS_NATIVE_GROUP_APPROVALS_PATH': {'value':DIRECTORY+'/approval.json'},
    'CPS_NATIVE_GROUP_APPROVAL_REFERENCE': {'value':DIRECTORY+'/reference.json'},
    'CPS_NATIVE_APPROVAL_POD_UID': {'valueFrom':{'fieldRef':{'apiVersion':'v1','fieldPath':'metadata.uid'}}},
    'CPS_NATIVE_APPROVAL_POD_NAME': {'valueFrom':{'fieldRef':{'apiVersion':'v1','fieldPath':'metadata.name'}}},
    'CPS_NATIVE_APPROVAL_POD_NAMESPACE': {'valueFrom':{'fieldRef':{'apiVersion':'v1','fieldPath':'metadata.namespace'}}},
}


def require(value, message):
    if not value:raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def parse(raw):
    def unique(pairs):
        result={}
        for key, value in pairs:
            require(key not in result, 'Duplicate input JSON key')
            result[key]=value
        return result
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite input JSON')))


def _namespaces(qualification):
    result={'gateway':'cps-compute', 'hub:cps':'jupyterhub', 'hub:cit':'cit-jhub',
        'node':qualification._config()['authorityNamespace']}
    require(len(set(result.values()))==4, 'Four distinct component projection namespaces required')
    return result


def _baselines(baselines, policy, qualification):
    require(isinstance(baselines, dict) and set(baselines)==set(COMPONENTS), 'All four component baselines required')
    namespaces=_namespaces(qualification); previous={}
    for component, row in baselines.items():
        require(isinstance(row, dict) and set(row)=={'deployment','container','previous_document','previous_reference'},
            'Closed full deployment and optional prior projection required')
        deployment=row['deployment']; meta=object_guard(deployment, 'Deployment')
        require(deployment.get('apiVersion')=='apps/v1' and meta.get('namespace')==namespaces[component]
            and isinstance(meta.get('name'), str) and not meta.get('deletionTimestamp')
            and isinstance(deployment.get('spec'), dict), 'Actual component Deployment required')
        spec=deployment['spec'].get('template', {}).get('spec', {})
        containers=[c for c in spec.get('containers', []) if isinstance(c, dict) and c.get('name')==row['container']]
        require(len(containers)==1 and isinstance(spec.get('serviceAccountName'), str), 'One explicit service container required')
        image=containers[0].get('image', '')
        require(isinstance(image, str) and '@sha256:' in image and len(image.split('@sha256:')[-1])==64
            and all(c in '0123456789abcdef' for c in image.split('@sha256:')[-1]), 'Preserved immutable service image required')
        require((row['previous_document'] is None)==(row['previous_reference'] is None), 'Complete prior projection pair required')
        if row['previous_document'] is not None:
            doc=ApprovalRevision.from_configmap(row['previous_document'], policy, qualification)
            ref=row['previous_reference']; refmeta=object_guard(ref, 'ConfigMap')
            require(ref.get('apiVersion')=='v1' and ref.get('immutable') is True
                and refmeta.get('namespace')==namespaces[component] and doc.reference['namespace']==namespaces[component]
                and not refmeta.get('deletionTimestamp') and not refmeta.get('ownerReferences') and not ref.get('binaryData')
                and isinstance(ref.get('data'), dict) and set(ref['data'])=={'reference.json'}
                and ref['data']['reference.json']==canonical(doc.reference), 'Exact actual prior immutable reference required')
            previous[component]=doc
    require(not previous or set(previous)==set(COMPONENTS), 'Partial prior rollout requires operator repair, not a new revision')
    if previous:
        require(len({canonical(doc.document) for doc in previous.values()})==1, 'Previous component documents must agree')
    return previous


def document_intent(*, source_raw, source_sha256, trusted_revision, policy, qualification, baselines,
                    captured_at, now):
    """Create candidates without inventing API identity or mutating registry state."""
    require(isinstance(source_raw, bytes) and 0<len(source_raw)<=1024*1024
        and source_sha256=='sha256:'+hashlib.sha256(source_raw).hexdigest(), 'Exact trusted Source export raw pin required')
    require(isinstance(captured_at, datetime) and captured_at.tzinfo is not None
        and isinstance(now, datetime) and now.tzinfo is not None
        and 0<=(now-captured_at).total_seconds()<=120, 'Fresh authenticated Source capture required')
    snapshot=ApprovalSnapshot.from_document(parse(source_raw), policy, qualification, expected_revision=trusted_revision)
    previous=_baselines(baselines, policy, qualification)
    history=[]
    if previous:
        old=previous['node'].document
        require(snapshot.document['generation']>old['registry']['generation'], 'Source generation must advance')
        history=copy.deepcopy(old['history'])+[previous[c].reference for c in COMPONENTS]
        require(len(history)<=256, 'Approval history bound reached; retain custody and review compaction')
    document=approval_envelope(snapshot, history)
    data={'approval.json':canonical(document)}; name='cps-native-approvals-'+canonical_sha256(data)[7:23]
    documents={}
    for component, row in baselines.items():
        if component in previous:
            cm=immutable_config(row['previous_document'], data, 'cps-native-approvals')
        else:
            # Initial create has a guarded actual Deployment, never a fabricated CM UID.
            cm={'apiVersion':'v1', 'kind':'ConfigMap', 'immutable':True,
                'metadata':{'namespace':row['deployment']['metadata']['namespace'], 'name':name}, 'data':copy.deepcopy(data)}
        documents[component]=cm
    return {'version':1, 'source_sha256':source_sha256, 'revision':snapshot.revision, 'policy_hash':policy.hash,
        'documents':documents, 'baseline_guards':{c:{'uid':row['deployment']['metadata']['uid'],
            'resourceVersion':row['deployment']['metadata']['resourceVersion'],
            'spec_sha256':canonical_sha256(row['deployment']['spec'])} for c,row in baselines.items()},
        'live_applied':False, 'process_readiness_verified':False}


def _process_declaration(row):
    meta=object_guard(row['deployment'], 'Deployment')
    pod=row['deployment']['spec']['template']['spec']
    container=next(c for c in pod['containers'] if c['name']==row['container'])
    return validate_process_declaration({'namespace':meta['namespace'],'kind':'Deployment','name':meta['name'],
        'uid':meta['uid'],'container':row['container'],'image':container['image'],'service_account':pod['serviceAccountName']})


def _node_bootstrap(document, row, qualification):
    process=_process_declaration(row)
    return immutable_config(document, {'template.json':canonical(qualification._config()),
        'process.json':canonical(process)}, 'cps-native-approval-bootstrap')


def _projected_preimage(spec, component):
    """Remove only this packet's known additions for a complete baseline check."""
    value=copy.deepcopy(spec);pod=value['template']['spec']
    for container in pod['containers']:
        if 'volumeMounts' in container:
            container['volumeMounts']=[m for m in container['volumeMounts'] if m.get('name') not in OWNED_VOLUMES]
        if 'env' in container:
            container['env']=[e for e in container['env'] if e.get('name') not in set(ENV)|{'CPS_NATIVE_APPROVAL_COMPONENT',PUBLISHER_ENV}]
        if component=='node' and 'args' in container:
            suffix=[item for name in ('reference','template','process') for item in ('--approval-'+name,DIRECTORY+'/'+name+'.json')]
            require(container['args'][-6:]==suffix,'Exact node projection arguments required')
            container['args']=container['args'][:-6]
    if 'volumes' in pod:pod['volumes']=[v for v in pod['volumes'] if v.get('name') not in OWNED_VOLUMES]
    return value


def _projection_rows(component, doc, ref, bootstrap=None):
    mode=0o400 if component=='node' else 0o444
    volumes=[{'name':DOC_VOLUME, 'configMap':{'name':doc['metadata']['name'], 'defaultMode':mode,
                 'items':[{'key':'approval.json', 'path':'approval.json'}]}},
             {'name':REF_VOLUME, 'configMap':{'name':ref['metadata']['name'], 'defaultMode':mode,
                 'items':[{'key':'reference.json', 'path':'reference.json'}]}}]
    mounts=[{'name':DOC_VOLUME, 'mountPath':DIRECTORY+'/approval.json', 'subPath':'approval.json', 'readOnly':True},
            {'name':REF_VOLUME, 'mountPath':DIRECTORY+'/reference.json', 'subPath':'reference.json', 'readOnly':True}]
    if component=='node':
        require(isinstance(bootstrap, dict), 'Qualified node template and trusted process prerequisite required')
        volumes.append({'name':BOOTSTRAP_VOLUME, 'configMap':{'name':bootstrap['metadata']['name'], 'defaultMode':0o400,
            'items':[{'key':name, 'path':name} for name in ('template.json','process.json')]}})
        mounts.extend({'name':BOOTSTRAP_VOLUME, 'mountPath':DIRECTORY+'/'+name, 'subPath':name, 'readOnly':True}
            for name in ('template.json','process.json'))
    env=[{'name':name, **copy.deepcopy(value)} for name,value in ENV.items()]
    env.append({'name':'CPS_NATIVE_APPROVAL_COMPONENT', 'value':component})
    return volumes, mounts, env


def _replace_owned(rows, owned, previous, message):
    require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows), message)
    names={row['name'] for row in owned}; found=[row for row in rows if row.get('name') in names]
    require(found==previous, message)
    return [copy.deepcopy(row) for row in rows if row.get('name') not in names]+copy.deepcopy(owned)


def projection_intent(*, documents, **kwargs):
    """Bind actual immutable document UIDs, then minimally project with full CAS."""
    plan=document_intent(**kwargs); baselines=kwargs['baselines']; policy=kwargs['policy']; qualification=kwargs['qualification']
    require(isinstance(documents, dict) and set(documents)==set(COMPONENTS), 'All four actual document readbacks required')
    references={}; reference_maps={}; bootstrap_maps={}; patches={}; expected={}
    for component, actual in documents.items():
        candidate=plan['documents'][component]
        revision=ApprovalRevision.from_configmap(actual, policy, qualification)
        object_guard(actual, 'ConfigMap')
        require(actual['data']==candidate['data'] and all(actual['metadata'].get(k)==candidate['metadata'][k]
            for k in ('name','namespace')), 'Actual created document must match reviewed candidate')
        ref=immutable_config(actual, {'reference.json':canonical(revision.reference)}, 'cps-native-approval-reference')
        references[component]=revision.reference; reference_maps[component]=ref
        row=baselines[component]; spec=copy.deepcopy(row['deployment']['spec']); pod=spec['template']['spec']
        container=next(c for c in pod['containers'] if c['name']==row['container'])
        bootstrap=_node_bootstrap(actual, row, qualification) if component=='node' else None
        if bootstrap is not None:bootstrap_maps[component]=bootstrap
        volumes, mounts, env=_projection_rows(component, actual, ref, bootstrap)
        oldvol, oldmount, oldenv=([], [], [])
        if row['previous_document'] is not None:
            oldbootstrap=_node_bootstrap(row['previous_document'], row, qualification) if component=='node' else None
            oldvol, oldmount, oldenv=_projection_rows(component, row['previous_document'], row['previous_reference'], oldbootstrap)
        pod['volumes']=_replace_owned(pod.get('volumes', []), volumes, oldvol, 'Unknown approval volume collision')
        container['volumeMounts']=_replace_owned(container.get('volumeMounts', []), mounts, oldmount, 'Unknown approval mount collision')
        require(not any(m.get('mountPath','').rstrip('/')==DIRECTORY or m.get('mountPath','').startswith(DIRECTORY+'/')
            for m in container['volumeMounts'] if m.get('name') not in OWNED_VOLUMES), 'Approval path mount collision')
        container['env']=_replace_owned(container.get('env', []), env, oldenv, 'Unknown approval environment collision')
        if component=='node':
            args=container.get('args', []); require(isinstance(args, list) and all(isinstance(a, str) for a in args), 'Explicit node args required')
            suffix=[item for name in ('reference','template','process') for item in
                ('--approval-'+name, DIRECTORY+'/'+name+'.json')]
            indices=[i for i,a in enumerate(args) if any(a=='--approval-'+name or a.startswith('--approval-'+name+'=')
                for name in ('reference','template','process'))]
            if row['previous_document'] is None:
                require(not indices, 'Unexpected prior node approval argument')
            else:
                require(indices==list(range(len(args)-6,len(args),2)) and args[-6:]==suffix,
                    'Exact prior node approval argument required')
                args=args[:-6]
            container['args']=args+suffix
        patches[component]=replace_patch(row['deployment'], '/spec', row['deployment']['spec'], spec)
        expected[component]={'namespace':row['deployment']['metadata']['namespace'],
            'name':row['deployment']['metadata']['name'], 'uid':row['deployment']['metadata']['uid'],
            'container':row['container'], 'spec':copy.deepcopy(spec)}
    return {**plan, 'references':references, 'reference_maps':reference_maps, 'bootstrap_maps':bootstrap_maps, 'patches':patches,
        'expected_deployments':expected, 'requires_actual_process_ack':True}


def publisher_intent(*, projection, documents, baselines, acknowledgments, policy, qualification,
                     driver_epoch, ttl_seconds=30):
    """Add actual UID-pinned publication prerequisites; never manufacture acks."""
    _baselines(baselines, policy, qualification)
    require(type(ttl_seconds) is int and 15<=ttl_seconds<=120, 'Bounded acknowledgment TTL required')
    pool=qualification._config()['node_pool']
    require(type(driver_epoch) is DriverEpoch and driver_epoch.__dict__=={
        'node_uid':pool['node_uid'],'boot_id':pool['boot_id'],'driver_generation':pool['driver_generation'],
        'gpu_uuid':pool['gpu_uuid']}, 'Actual qualified driver epoch required')
    require(isinstance(projection,dict) and projection.get('policy_hash')==policy.hash
        and projection.get('process_readiness_verified') is False
        and projection.get('live_applied') is False, 'Unapplied reviewed projection required')
    for values in (documents, acknowledgments, projection.get('references'),projection.get('expected_deployments')):
        require(isinstance(values,dict) and set(values)==set(COMPONENTS), 'All four actual projection identities required')
    result=copy.deepcopy(projection);refs={};processes={}
    for component in COMPONENTS:
        actual=documents[component]
        ApprovalRevision.from_configmap(actual,policy,qualification,expected_ref=projection['references'][component])
        ack=acknowledgments[component];meta=object_guard(ack,'ConfigMap')
        require(ack.get('apiVersion')=='v1' and ack.get('immutable') in (None,False)
            and meta.get('namespace')==actual['metadata']['namespace'] and not meta.get('deletionTimestamp')
            and not meta.get('ownerReferences') and not ack.get('binaryData')
            and isinstance(ack.get('data'),dict) and set(ack['data'])=={'ack.json'}
            and isinstance(ack['data']['ack.json'],str) and isinstance(parse(ack['data']['ack.json']),dict),
            'Actual mutable acknowledgment ConfigMap with one JSON record required')
        refs[component]=validate_acknowledgment_reference({k:meta[k] for k in ('namespace','name','uid')})
        row=baselines[component];processes[component]=_process_declaration(row)
        expected=projection['expected_deployments'][component]
        require(all(expected.get(k)==row['deployment']['metadata'][k] for k in ('namespace','name','uid'))
            and expected.get('container')==row['container']
            and projection['baseline_guards'][component]=={'uid':row['deployment']['metadata']['uid'],
                'resourceVersion':row['deployment']['metadata']['resourceVersion'],
                'spec_sha256':canonical_sha256(row['deployment']['spec'])}, 'Exact captured projection baseline required')
        # Initial installation cannot hide unrelated changes in a supplied packet.
        if row['previous_document'] is None:
            preimage=_projected_preimage(expected['spec'],component)
            original=copy.deepcopy(row['deployment']['spec'])
            for container in original['template']['spec']['containers']:
                container.setdefault('env',[]);container.setdefault('volumeMounts',[])
            original['template']['spec'].setdefault('volumes',[])
            require(preimage==original,'Projection must preserve the complete original static spec')
        spec=copy.deepcopy(expected['spec']);pod=spec['template']['spec']
        container=next(c for c in pod['containers'] if c['name']==row['container'])
        require(container['image']==processes[component]['image'] and pod['serviceAccountName']==processes[component]['service_account'],
            'Preserved controller image and service account required')
        if component=='node':
            data=copy.deepcopy(result['bootstrap_maps']['node']['data']);data['acknowledgment.json']=canonical(refs[component])
            require(data['process.json']==canonical(processes[component]),'Exact node controller declaration required')
            bootstrap=immutable_config(actual,data,'cps-native-approval-bootstrap')
            volume=next(v for v in pod['volumes'] if v['name']==BOOTSTRAP_VOLUME)
            volume['configMap']['name']=bootstrap['metadata']['name']
            volume['configMap']['items'].append({'key':'acknowledgment.json','path':'acknowledgment.json'})
            container['volumeMounts'].append({'name':BOOTSTRAP_VOLUME,'mountPath':DIRECTORY+'/acknowledgment.json',
                'subPath':'acknowledgment.json','readOnly':True})
            require(not any(a=='--approval-acknowledgment' or a.startswith('--approval-acknowledgment=')
                for a in container.get('args',[])), 'Unexpected prior acknowledgment argument')
            container['args']+=['--approval-acknowledgment',DIRECTORY+'/acknowledgment.json']
        else:
            require(not any(v.get('name')==PUBLISHER_VOLUME for v in pod.get('volumes',[]))
                and not any(e.get('name')==PUBLISHER_ENV for e in container.get('env',[])),
                'Unexpected prior publisher projection')
            value={'version':1,'component':component,'acknowledgment':refs[component],'process':processes[component],
                'driver_epoch':driver_epoch.__dict__,'ttlSeconds':ttl_seconds}
            bootstrap=immutable_config(actual,{'publisher.json':canonical(value)},'cps-native-approval-publisher')
            pod['volumes'].append({'name':PUBLISHER_VOLUME,'configMap':{'name':bootstrap['metadata']['name'],
                'defaultMode':0o444,'items':[{'key':'publisher.json','path':'publisher.json'}]}})
            container['volumeMounts'].append({'name':PUBLISHER_VOLUME,'mountPath':DIRECTORY+'/publisher.json',
                'subPath':'publisher.json','readOnly':True})
            container['env'].append({'name':PUBLISHER_ENV,'value':DIRECTORY+'/publisher.json'})
        result['bootstrap_maps'][component]=bootstrap
        result['patches'][component]=replace_patch(row['deployment'],'/spec',row['deployment']['spec'],spec)
        result['expected_deployments'][component]['spec']=copy.deepcopy(spec)
    result['acknowledgment_references']=refs;result['process_declarations']=processes
    result['runtime_settings']={'enabled':True,'acknowledgments':copy.deepcopy(refs),'processes':copy.deepcopy(processes),
        'driver_epoch':copy.deepcopy(driver_epoch.__dict__),'ttlSeconds':ttl_seconds}
    return result


def access_name(component):
    require(component in COMPONENTS,'Known component required')
    return 'cps-native-approval-'+component.replace(':','-')


def _installed_publication_rows(component, doc, ref, bootstrap):
    """Exact first-install projection, including the installed publisher inputs."""
    volumes,mounts,env=_projection_rows(component,doc,ref,bootstrap if component=='node' else None)
    if component=='node':
        volumes[-1]['configMap']['items'].append({'key':'acknowledgment.json','path':'acknowledgment.json'})
        mounts.append({'name':BOOTSTRAP_VOLUME,'mountPath':DIRECTORY+'/acknowledgment.json',
            'subPath':'acknowledgment.json','readOnly':True})
    else:
        volumes.append({'name':PUBLISHER_VOLUME,'configMap':{'name':bootstrap['metadata']['name'],
            'defaultMode':0o444,'items':[{'key':'publisher.json','path':'publisher.json'}]}})
        mounts.append({'name':PUBLISHER_VOLUME,'mountPath':DIRECTORY+'/publisher.json',
            'subPath':'publisher.json','readOnly':True})
        env.append({'name':PUBLISHER_ENV,'value':DIRECTORY+'/publisher.json'})
    return volumes,mounts,env


def revision_projection_intent(*, documents, previous_publication, previous_publication_sha256,
        previous_bootstrap_maps, acknowledgments, driver_epoch, ttl_seconds=30, **kwargs):
    """Advance an installed revision; preserve publishers and actual ack identities."""
    allowed={'version','source_sha256','revision','policy_hash','documents','baseline_guards','live_applied',
        'process_readiness_verified','references','reference_maps','bootstrap_maps','patches',
        'expected_deployments','requires_actual_process_ack','acknowledgment_references',
        'process_declarations','runtime_settings'}
    rollover={'previous_publication_sha256','publisher_reinstall_required'}
    require(isinstance(previous_publication,dict) and set(previous_publication) in
        (allowed,allowed|{'initial_access'},allowed|rollover,allowed|rollover|{'initial_access'})
        and previous_publication_sha256==canonical_sha256(previous_publication),
        'Exact pinned reviewed previous publication required')
    if 'publisher_reinstall_required' in previous_publication:
        require(previous_publication['publisher_reinstall_required'] is False
            and isinstance(previous_publication['previous_publication_sha256'],str)
            and previous_publication['previous_publication_sha256'].startswith('sha256:'),
            'Known previous rollover provenance required')
    _publisher_scope(previous_publication)
    policy=kwargs['policy'];qualification=kwargs['qualification'];baselines=kwargs['baselines']
    previous=_baselines(baselines,policy,qualification)
    require(set(previous)==set(COMPONENTS),'Fully installed prior revision required')
    require(type(ttl_seconds) is int and 15<=ttl_seconds<=120,'Bounded acknowledgment TTL required')
    pool=qualification._config()['node_pool']
    require(type(driver_epoch) is DriverEpoch and driver_epoch.__dict__=={
        'node_uid':pool['node_uid'],'boot_id':pool['boot_id'],'driver_generation':pool['driver_generation'],
        'gpu_uuid':pool['gpu_uuid']},'Unchanged qualified driver epoch required')
    for values in (documents,previous_bootstrap_maps,acknowledgments):
        require(isinstance(values,dict) and set(values)==set(COMPONENTS),'All four complete actual readbacks required')
    settings={'enabled':True,'acknowledgments':previous_publication['acknowledgment_references'],
        'processes':previous_publication['process_declarations'],'driver_epoch':driver_epoch.__dict__,'ttlSeconds':ttl_seconds}
    require(previous_publication['runtime_settings']==settings and previous_publication['policy_hash']==policy.hash
        and previous_publication['revision']==previous['node'].reference['revision'],
        'Previous process, epoch, TTL and policy custody must remain unchanged')
    plan=document_intent(**kwargs);references={};reference_maps={};patches={};expected={}
    for component in COMPONENTS:
        row=baselines[component];old=previous[component];publication=previous_publication
        require(publication['references'][component]==old.reference
            and publication['documents'][component]['data']==row['previous_document']['data']
            and all(publication['documents'][component]['metadata'].get(k)==row['previous_document']['metadata'][k]
                for k in ('namespace','name'))
            and publication['reference_maps'][component]['data']==row['previous_reference']['data']
            and all(publication['reference_maps'][component]['metadata'].get(k)==row['previous_reference']['metadata'][k]
                for k in ('namespace','name')),'Exact retained prior document and reference required')
        process=_process_declaration(row);old_expected=publication['expected_deployments'][component]
        require(process==publication['process_declarations'][component]
            and all(old_expected.get(k)==row['deployment']['metadata'][k] for k in ('namespace','name','uid'))
            and old_expected.get('container')==row['container'] and old_expected.get('spec')==row['deployment']['spec'],
            'Complete unchanged previously reviewed Deployment spec required')
        ack=acknowledgments[component];meta=object_guard(ack,'ConfigMap')
        require(set(ack)<= {'apiVersion','kind','metadata','immutable','data'}
            and ack.get('apiVersion')=='v1' and ack.get('immutable') in (None,False)
            and not meta.get('deletionTimestamp') and not meta.get('ownerReferences') and not ack.get('binaryData')
            and isinstance(ack.get('data'),dict) and set(ack['data'])=={'ack.json'}
            and isinstance(ack['data']['ack.json'],str) and isinstance(parse(ack['data']['ack.json']),dict)
            and {k:meta.get(k) for k in ('namespace','name','uid')}==publication['acknowledgment_references'][component],
            'Original actual acknowledgment identity required')
        bootstrap=previous_bootstrap_maps[component];bmeta=object_guard(bootstrap,'ConfigMap')
        if component=='node':
            data={'template.json':canonical(qualification._config()),'process.json':canonical(process),
                'acknowledgment.json':canonical(publication['acknowledgment_references'][component])}
            prefix='cps-native-approval-bootstrap'
        else:
            data={'publisher.json':canonical({'version':1,'component':component,
                'acknowledgment':publication['acknowledgment_references'][component],'process':process,
                'driver_epoch':driver_epoch.__dict__,'ttlSeconds':ttl_seconds})}
            prefix='cps-native-approval-publisher'
        candidate=immutable_config(row['previous_document'],data,prefix)
        require(set(bootstrap)<= {'apiVersion','kind','metadata','immutable','data'}
            and bootstrap.get('apiVersion')=='v1' and bootstrap.get('immutable') is True
            and not bmeta.get('deletionTimestamp') and not bmeta.get('ownerReferences')
            and bootstrap.get('data')==candidate['data']
            and all(bmeta.get(k)==candidate['metadata'][k] for k in ('namespace','name'))
            and publication['bootstrap_maps'][component]['data']==data
            and all(publication['bootstrap_maps'][component]['metadata'].get(k)==bmeta[k] for k in ('namespace','name')),
            'Actual immutable unchanged publisher bootstrap required')
        prior_uid=publication['bootstrap_maps'][component]['metadata'].get('uid')
        require(prior_uid is None or prior_uid==bmeta['uid'],'Previously bound publisher ConfigMap UID must remain unchanged')
        actual=documents[component];revision=ApprovalRevision.from_configmap(actual,policy,qualification)
        object_guard(actual,'ConfigMap')
        require(actual['data']==plan['documents'][component]['data']
            and all(actual['metadata'].get(k)==plan['documents'][component]['metadata'][k] for k in ('namespace','name')),
            'Actual new document must match reviewed candidate')
        reference=immutable_config(actual,{'reference.json':canonical(revision.reference)},'cps-native-approval-reference')
        references[component]=revision.reference;reference_maps[component]=reference
        spec=copy.deepcopy(row['deployment']['spec']);pod=spec['template']['spec']
        container=next(c for c in pod['containers'] if c['name']==row['container'])
        old_volumes,old_mounts,old_env=_installed_publication_rows(component,row['previous_document'],row['previous_reference'],bootstrap)
        require([v for v in pod.get('volumes',[]) if v.get('name') in OWNED_VOLUMES]==old_volumes
            and [m for m in container.get('volumeMounts',[]) if m.get('name') in OWNED_VOLUMES]==old_mounts
            and [e for e in container.get('env',[]) if e.get('name') in set(ENV)|{'CPS_NATIVE_APPROVAL_COMPONENT',PUBLISHER_ENV}]==old_env,
            'Exact installed prior publication inputs required')
        require(not any(m.get('mountPath','').rstrip('/')==DIRECTORY or m.get('mountPath','').startswith(DIRECTORY+'/')
            for m in container.get('volumeMounts',[]) if m.get('name') not in OWNED_VOLUMES), 'Approval path mount collision')
        require(not any(any(v.get('name') in OWNED_VOLUMES for v in c.get('volumeMounts',[]))
            or any(e.get('name') in set(ENV)|{'CPS_NATIVE_APPROVAL_COMPONENT',PUBLISHER_ENV} for e in c.get('env',[]))
            for c in pod['containers'] if c['name']!=row['container']), 'Foreign container approval input collision')
        if component=='node':
            suffix=[item for name in ('reference','template','process','acknowledgment')
                for item in ('--approval-'+name,DIRECTORY+'/'+name+'.json')]
            args=container.get('args',[])
            require(isinstance(args,list) and args[-8:]==suffix
                and not any(a=='--approval-'+name or a.startswith('--approval-'+name+'=')
                    for a in args[:-8] for name in ('reference','template','process','acknowledgment')),
                'Exact installed node publication arguments required')
        for volume in pod['volumes']:
            if volume['name']==DOC_VOLUME:volume['configMap']['name']=actual['metadata']['name']
            elif volume['name']==REF_VOLUME:volume['configMap']['name']=reference['metadata']['name']
        patches[component]=replace_patch(row['deployment'],'/spec',row['deployment']['spec'],spec)
        expected[component]={**{k:row['deployment']['metadata'][k] for k in ('namespace','name','uid')},
            'container':row['container'],'spec':spec}
    return {**plan,'references':references,'reference_maps':reference_maps,'bootstrap_maps':copy.deepcopy(previous_bootstrap_maps),
        'patches':patches,'expected_deployments':expected,'requires_actual_process_ack':True,
        'acknowledgment_references':copy.deepcopy(settings['acknowledgments']),
        'process_declarations':copy.deepcopy(settings['processes']),'runtime_settings':copy.deepcopy(settings),
        'previous_publication_sha256':previous_publication_sha256,'publisher_reinstall_required':False}


def _publisher_scope(projection):
    for key in ('acknowledgment_references','process_declarations','references','expected_deployments'):
        require(isinstance(projection.get(key),dict) and set(projection[key])==set(COMPONENTS),'Closed publisher scope required')
    for component in COMPONENTS:
        process=validate_process_declaration(projection['process_declarations'][component])
        ref=validate_reference(projection['references'][component])
        ack=validate_acknowledgment_reference(projection['acknowledgment_references'][component])
        expected=projection['expected_deployments'][component]
        container=next(c for c in expected['spec']['template']['spec']['containers'] if c['name']==expected['container'])
        require(all(process[k]==expected[k] for k in ('namespace','name','uid','container'))
            and process['image']==container['image']
            and process['service_account']==expected['spec']['template']['spec']['serviceAccountName']
            and process['kind']=='Deployment' and ack['namespace']==ref['namespace']==process['namespace']
            and (component=='node' or process['namespace']=={'gateway':'cps-compute','hub:cps':'jupyterhub','hub:cit':'cit-jhub'}[component]),
            'Actual same-scope publisher controller and named references required')
    require(len({p['namespace'] for p in projection['process_declarations'].values()})==4,'Four distinct publisher scopes required')


def _access_rows(projection, process_names=None):
    """Only the gateway reads peers; every publisher patches its own ack only."""
    result=[];process_names=process_names or {}
    for reader in COMPONENTS:
        scope=COMPONENTS if reader=='gateway' else (reader,)
        process=projection['process_declarations'][reader]
        subject={'kind':'ServiceAccount','name':process['service_account'],'namespace':process['namespace']}
        for target in scope:
            namespace=projection['references'][target]['namespace'];name=access_name(reader)
            ack=projection['acknowledgment_references'][target]
            rules=[{'apiGroups':[''],'resources':['configmaps'],'resourceNames':sorted([
                projection['references'][target]['name'],ack['name']]),'verbs':['get']},
                {'apiGroups':['apps'],'resources':['deployments'],
                    'resourceNames':[projection['process_declarations'][target]['name']],'verbs':['get']}]
            if target==reader:rules.append({'apiGroups':[''],'resources':['configmaps'],
                'resourceNames':[ack['name']],'verbs':['patch']})
            if target in process_names:
                names=process_names[target]
                rules.extend([{'apiGroups':[''],'resources':['pods'],'resourceNames':[names['pod']],'verbs':['get']},
                    {'apiGroups':['apps'],'resources':['replicasets'],'resourceNames':[names['replicaset']],'verbs':['get']}])
            metadata={'namespace':namespace,'name':name}
            result.extend([{'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':metadata,'rules':rules},
                {'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':copy.deepcopy(metadata),
                    'subjects':[subject],'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':name}}])
    return result


def access_intent(*, projection):
    """Initial named-CM/controller RBAC candidates, with no guessed future Pods."""
    _publisher_scope(projection)
    return {'version':1,'objects':_access_rows(projection),'requires_actual_new_process_capture':True,'live_applied':False}


def process_access_intent(*, projection, deployments, replicasets, pods, roles):
    """Bind fresh real Pod/RS names after rollout, guarded by full old Role rules."""
    _publisher_scope(projection)
    for values in (deployments,replicasets,pods):
        require(isinstance(values,dict) and set(values)==set(COMPONENTS),'All actual current process records required')
    names={}
    core,apps=_captured_apis(deployments,replicasets,pods)
    for component in COMPONENTS:
        expected=projection['expected_deployments'][component];deployment=deployments[component]
        require(deployment.get('spec')==expected['spec'],'Actual applied process spec required')
        pod=pods[component];meta=object_guard(pod,'Pod');rs=replicasets[component];object_guard(rs,'ReplicaSet')
        receipt={**{k:projection['process_declarations'][component][k] for k in ('namespace','container','image','service_account')},
            'name':meta['name'],'uid':meta['uid']}
        observed,_=observe_process(core,apps,projection['process_declarations'][component],receipt)
        require(observed==pod and _owner(pod,rs,'ReplicaSet'),'Exact captured ReplicaSet required')
        names[component]={'pod':meta['name'],'replicaset':rs['metadata']['name']}
    initial={o['metadata']['namespace']+'/'+o['metadata']['name']:o for o in _access_rows(projection) if o['kind']=='Role'}
    require(isinstance(roles,dict) and set(roles)==set(initial),'All exact initial approval Roles required')
    patches={}
    for target in _access_rows(projection,names):
        if target['kind']!='Role':continue
        namespace=target['metadata']['namespace'];name=target['metadata']['name'];key=namespace+'/'+name;baseline=roles[key]
        meta=object_guard(baseline,'Role')
        require(baseline.get('apiVersion')=='rbac.authorization.k8s.io/v1' and not meta.get('deletionTimestamp')
            and (meta.get('namespace'),meta.get('name'))==(namespace,name) and baseline.get('rules')==initial[key]['rules'],
            'Actual initial named Role with exact reviewed rules required')
        patches[key]=replace_patch(baseline,'/rules',baseline['rules'],target['rules'])
    return {'version':1,'patches':patches,'actual_process_names':names,'live_applied':False,'process_readiness_verified':False}


def _revision_access_scope(projection, previous_publication):
    _publisher_scope(projection);_publisher_scope(previous_publication)
    require(projection.get('previous_publication_sha256')==canonical_sha256(previous_publication)
        and projection.get('publisher_reinstall_required') is False
        and projection['revision']!=previous_publication['revision']
        and projection['policy_hash']==previous_publication['policy_hash']
        and all(projection[key]==previous_publication[key] for key in
            ('acknowledgment_references','process_declarations','runtime_settings')),
        'Exact reviewed installed revision transition required')


def _revision_process_names(projection, deployments, replicasets, pods):
    for values in (deployments,replicasets,pods):
        require(isinstance(values,dict) and set(values)==set(COMPONENTS),'All actual current process records required')
    core,apps=_captured_apis(deployments,replicasets,pods);names={}
    for component in COMPONENTS:
        expected=projection['expected_deployments'][component];deployment=deployments[component]
        meta=object_guard(deployment,'Deployment')
        require(all(meta.get(k)==expected[k] for k in ('namespace','name','uid'))
            and deployment.get('spec')==expected['spec'],'Exact applied reviewed controller required')
        pod=pods[component];pmeta=object_guard(pod,'Pod');rs=replicasets[component];object_guard(rs,'ReplicaSet')
        receipt={**{k:projection['process_declarations'][component][k] for k in ('namespace','container','image','service_account')},
            'name':pmeta['name'],'uid':pmeta['uid']}
        observed,_=observe_process(core,apps,projection['process_declarations'][component],receipt)
        require(observed==pod and _owner(pod,rs,'ReplicaSet'),'Exact captured current ReplicaSet required')
        _observed_projection(pod,expected,component)
        names[component]={'pod':pmeta['name'],'replicaset':rs['metadata']['name']}
    return names


def _revision_role_patches(projection, old_rows, new_rows, roles):
    expected={o['metadata']['namespace']+'/'+o['metadata']['name']:o for o in old_rows if o['kind']=='Role'}
    targets={o['metadata']['namespace']+'/'+o['metadata']['name']:o for o in new_rows if o['kind']=='Role'}
    require(isinstance(roles,dict) and set(roles)==set(expected)==set(targets),'All exact prior approval Roles required')
    patches={}
    for key,baseline in roles.items():
        meta=object_guard(baseline,'Role');wanted=expected[key]
        require(set(baseline)=={'apiVersion','kind','metadata','rules'}
            and baseline['apiVersion']=='rbac.authorization.k8s.io/v1'
            and not meta.get('deletionTimestamp') and not meta.get('ownerReferences')
            and all(meta.get(k)==wanted['metadata'][k] for k in ('namespace','name'))
            and baseline['rules']==wanted['rules'],'Exact complete prior named Role rules required')
        patches[key]=replace_patch(baseline,'/rules',baseline['rules'],targets[key]['rules'])
    return {'version':1,'patches':patches,'live_applied':False,'process_readiness_verified':False,
        'previous_publication_sha256':projection['previous_publication_sha256']}


def revision_access_intent(*, projection, previous_publication, deployments, replicasets, pods, roles):
    """Before rollout, replace named document GET while retaining actual old Pod names."""
    _revision_access_scope(projection,previous_publication)
    names=_revision_process_names(previous_publication,deployments,replicasets,pods)
    result=_revision_role_patches(projection,_access_rows(previous_publication,names),_access_rows(projection,names),roles)
    return {**result,'previous_process_names':names,'requires_actual_new_process_capture':True}


def revision_process_access_intent(*, projection, previous_publication, previous_process_records,
        deployments, replicasets, pods, roles):
    """After rollout, replace only old Pod/RS GET targets using genuine new processes."""
    _revision_access_scope(projection,previous_publication)
    require(isinstance(previous_process_records,dict)
        and set(previous_process_records)=={'deployments','replicasets','pods'},'Closed retained prior process capture required')
    old_names=_revision_process_names(previous_publication,**previous_process_records)
    names=_revision_process_names(projection,deployments,replicasets,pods)
    result=_revision_role_patches(projection,_access_rows(projection,old_names),_access_rows(projection,names),roles)
    return {**result,'actual_process_names':names}


def _captured_apis(deployments,replicasets,pods):
    def find(values,name,namespace):
        rows=[p for p in values.values() if (p.get('metadata',{}).get('name'),p.get('metadata',{}).get('namespace'))==(name,namespace)]
        require(len(rows)==1,'One exact captured process object required')
        return rows[0]
    class Core:
        def read_namespaced_pod(self,name,namespace):return find(pods,name,namespace)
    class Apps:
        def read_namespaced_deployment(self,name,namespace):return find(deployments,name,namespace)
        def read_namespaced_replica_set(self,name,namespace):return find(replicasets,name,namespace)
    return Core(),Apps()


def _owner(child, parent, kind):
    refs=child.get('metadata', {}).get('ownerReferences', [])
    controllers=[row for row in refs if row.get('controller') is True]
    return len(controllers)==1 and all(controllers[0].get(k)==v for k,v in
        {'kind':kind, 'name':parent['metadata']['name'], 'uid':parent['metadata']['uid']}.items())


def _replica_template(rs, deployment, pod):
    """Allow only the actual Deployment controller's bound Pod-template label."""
    template=copy.deepcopy(rs.get('spec', {}).get('template'))
    expected=deployment['spec']['template']
    if template==expected:return True
    if not isinstance(template, dict):return False
    labels=template.get('metadata', {}).get('labels', {})
    value=labels.get('pod-template-hash')
    if not isinstance(value, str) or not value or 'pod-template-hash' in expected.get('metadata', {}).get('labels', {}):return False
    selector=copy.deepcopy(rs.get('spec', {}).get('selector', {}))
    if selector.get('matchLabels', {}).get('pod-template-hash')!=value or pod.get('metadata', {}).get('labels', {}).get('pod-template-hash')!=value:return False
    del selector['matchLabels']['pod-template-hash']
    del labels['pod-template-hash']
    return template==expected and selector==deployment['spec']['selector']


def _observed_projection(pod, expected, component):
    wanted=expected['spec']['template']['spec']; actual=pod.get('spec', {})
    require([v for v in actual.get('volumes', []) if v.get('name') in OWNED_VOLUMES]
        ==[v for v in wanted.get('volumes', []) if v.get('name') in OWNED_VOLUMES],
        'Actual process must mount both exact document and reference projections')
    containers=[c for c in actual.get('containers', []) if c.get('name')==expected['container']]
    require(len(containers)==1, 'One actual approved process container required')
    container=containers[0]; target=next(c for c in wanted['containers'] if c['name']==expected['container'])
    require([v for v in container.get('volumeMounts', []) if v.get('name') in OWNED_VOLUMES]
        ==[v for v in target['volumeMounts'] if v.get('name') in OWNED_VOLUMES]
        and [v for v in container.get('env', []) if v.get('name') in set(ENV)|{'CPS_NATIVE_APPROVAL_COMPONENT',PUBLISHER_ENV}]
        ==[v for v in target['env'] if v.get('name') in set(ENV)|{'CPS_NATIVE_APPROVAL_COMPONENT',PUBLISHER_ENV}]
        and (component!='node' or container.get('args')==target.get('args')),
        'Actual process approval inputs must match the applied reviewed projection')


def readiness_intent(*, projection, documents, policy, qualification, deployments, replicasets, pods,
                     expected_processes, acknowledgments, driver_epoch, now, ttl_seconds=30):
    """Require real owner chain, applied spec and successful loaded-process acks."""
    for values in (documents, deployments, replicasets, pods, expected_processes, acknowledgments):
        require(isinstance(values, dict) and set(values)==set(COMPONENTS), 'All four complete current observations required')
    pool=qualification._config()['node_pool']
    require(type(driver_epoch) is DriverEpoch and driver_epoch.__dict__=={
        'node_uid':pool['node_uid'], 'boot_id':pool['boot_id'], 'driver_generation':pool['driver_generation'],
        'gpu_uuid':pool['gpu_uuid']}, 'Actual qualified driver epoch required')
    verified={}
    core,apps=_captured_apis(deployments,replicasets,pods)
    for component in COMPONENTS:
        actual=ApprovalRevision.from_configmap(documents[component], policy, qualification,
            expected_ref=projection['references'][component])
        deployment=deployments[component]; expected=projection['expected_deployments'][component]
        meta=object_guard(deployment, 'Deployment'); rs=replicasets[component]; pod=pods[component]
        object_guard(rs, 'ReplicaSet'); object_guard(pod, 'Pod')
        require(all(meta.get(k)==expected[k] for k in ('namespace','name','uid'))
            and deployment.get('spec')==expected['spec'] and not meta.get('deletionTimestamp')
            and type(meta.get('generation')) is int and deployment.get('status', {}).get('observedGeneration')==meta['generation']
            and deployment.get('status', {}).get('readyReplicas',0)>0
            and deployment.get('status', {}).get('updatedReplicas',0)>0
            and rs.get('apiVersion')=='apps/v1'
            and rs.get('metadata', {}).get('namespace')==meta['namespace'] and not rs['metadata'].get('deletionTimestamp')
            and _owner(rs, deployment, 'Deployment') and _owner(pod, rs, 'ReplicaSet')
            and _replica_template(rs, deployment, pod), 'Actual current Deployment/ReplicaSet/Pod chain required')
        _observed_projection(pod, expected, component)
        process=expected_processes[component]
        container=next(c for c in expected['spec']['template']['spec']['containers'] if c['name']==expected['container'])
        require(process.get('container')==expected['container'] and process.get('image')==container['image']
            and process.get('namespace')==expected['namespace']
            and process.get('service_account')==expected['spec']['template']['spec']['serviceAccountName'],
            'Process declaration must match reviewed current service scope')
        trusted={'namespace':expected['namespace'],'kind':'Deployment','name':expected['name'],'uid':expected['uid'],
            'container':expected['container'],'image':container['image'],
            'service_account':expected['spec']['template']['spec']['serviceAccountName']}
        observed,scope=observe_process(core,apps,trusted,process)
        require(observed==pod and scope==process,'Current exact executable Pod template required')
        verified[component]=validate_ack(acknowledgments[component], component=component, document=actual,
            actual_pod=pod, expected_process=process, driver_epoch=driver_epoch, now=now, ttl_seconds=ttl_seconds)
    return {'version':1, 'ready':True, 'revision':projection['revision'], 'policy_hash':policy.hash,
        'acknowledgments':verified, 'enrollment_approval_reference':copy.deepcopy(projection['references']['node']),
        'observed_at':now.isoformat(), 'live_applied':False}


def _private_json(path, maximum=8*1024*1024):
    path=Path(path); info=path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600
        and info.st_nlink==1 and 0<info.st_size<=maximum, 'Private bounded regular input required')
    return parse(path.read_bytes())


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render', action='store_true', help='Offline only: write document or projection intents')
    parser.add_argument('--input', type=Path); parser.add_argument('--output', type=Path)
    parser.add_argument('--publisher-input', type=Path, help='Actual pre-created acknowledgment readbacks and qualified epoch')
    parser.add_argument('--process-access', action='store_true', help='Offline guarded named Pod/ReplicaSet access after rollout')
    args=parser.parse_args(argv)
    if not args.render:
        print('Inert: --render requires a private operator input; no cluster access performed.'); return 0
    require(args.input is not None and args.output is not None, 'Private input and new output directory required')
    request=_private_json(args.input)
    if args.process_access:
        require(args.publisher_input is None and isinstance(request,dict) and set(request)=={
            'version','projection','deployments','replicasets','pods','roles'} and type(request['version']) is int
            and request['version']==1,'Closed actual process access request required')
        result=process_access_intent(**{k:request[k] for k in request if k!='version'})
    else:
        require(isinstance(request, dict) and set(request)=={'version','source_raw','source_sha256','trusted_revision',
            'policy','qualification','baselines','captured_at','documents'} and type(request['version']) is int
            and request['version']==1, 'Closed operator render request required')
        policy=Policy(request['policy']); qualification=NativeGroupDeployment.from_config(request['qualification'], policy)
        kwargs={k:request[k] for k in ('source_sha256','trusted_revision','baselines')}
        kwargs.update(source_raw=request['source_raw'].encode(), policy=policy, qualification=qualification,
            captured_at=datetime.fromisoformat(request['captured_at'].replace('Z','+00:00')), now=datetime.now(timezone.utc))
        result=(document_intent(**kwargs) if request['documents'] is None
            else projection_intent(**kwargs, documents=request['documents']))
        if args.publisher_input is not None:
            publisher=_private_json(args.publisher_input)
            require(request['documents'] is not None and isinstance(publisher,dict) and set(publisher)=={
                'version','acknowledgments','driver_epoch','ttlSeconds'} and type(publisher['version']) is int
                and publisher['version']==1 and isinstance(publisher['driver_epoch'],dict)
                and set(publisher['driver_epoch'])=={'node_uid','boot_id','driver_generation','gpu_uuid'},
                'Closed actual publisher prerequisites required')
            result=publisher_intent(projection=result,documents=request['documents'],baselines=request['baselines'],
                acknowledgments=publisher['acknowledgments'],policy=policy,qualification=qualification,
                driver_epoch=DriverEpoch(**publisher['driver_epoch']),ttl_seconds=publisher['ttlSeconds'])
            result['initial_access']=access_intent(projection=result)
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    target=args.output/'intent.json'
    with target.open('x', encoding='utf-8') as handle:
        os.chmod(target, 0o600); handle.write(canonical(result)+'\n')
    print(canonical({'version':1, 'revision':result.get('revision'), 'components':len(result.get('documents',{})),
        'output_sha256':'sha256:'+hashlib.sha256(target.read_bytes()).hexdigest(), 'live_applied':False}))
    return 0


if __name__=='__main__':raise SystemExit(main())
