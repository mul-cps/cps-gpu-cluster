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
from cps_compute.native_group_revision import ApprovalRevision, approval_envelope, validate_ack, validate_reference
from cps_compute.native_gpu_controller import DriverEpoch
from cps_compute.native_groups import NativeGroupDeployment, canonical_sha256
from cps_compute.policy import Policy
from qualification_transition_proposal import object_guard, immutable_config, replace_patch

COMPONENTS = ('gateway', 'hub:cps', 'hub:cit', 'node')
DIRECTORY = '/var/run/cps-native-approvals'
DOC_VOLUME = 'cps-native-approval-document'
REF_VOLUME = 'cps-native-approval-reference'
BOOTSTRAP_VOLUME = 'cps-native-approval-bootstrap'
OWNED_VOLUMES = {DOC_VOLUME, REF_VOLUME, BOOTSTRAP_VOLUME}
ENV = {
    'CPS_NATIVE_GROUP_APPROVALS_PATH': {'value':DIRECTORY+'/approval.json'},
    'CPS_NATIVE_GROUP_APPROVAL_REFERENCE': {'value':DIRECTORY+'/reference.json'},
    'CPS_NATIVE_APPROVAL_POD_UID': {'valueFrom':{'fieldRef':{'fieldPath':'metadata.uid'}}},
    'CPS_NATIVE_APPROVAL_POD_NAME': {'valueFrom':{'fieldRef':{'fieldPath':'metadata.name'}}},
    'CPS_NATIVE_APPROVAL_POD_NAMESPACE': {'valueFrom':{'fieldRef':{'fieldPath':'metadata.namespace'}}},
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


def _node_bootstrap(document, row, qualification):
    pod=row['deployment']['spec']['template']['spec']
    container=next(c for c in pod['containers'] if c['name']==row['container'])
    process={'namespace':row['deployment']['metadata']['namespace'], 'container':row['container'],
        'image':container['image'], 'service_account':pod['serviceAccountName']}
    return immutable_config(document, {'template.json':canonical(qualification._config()),
        'process.json':canonical(process)}, 'cps-native-approval-bootstrap')


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
        and [v for v in container.get('env', []) if v.get('name') in set(ENV)|{'CPS_NATIVE_APPROVAL_COMPONENT'}]
        ==[v for v in target['env'] if v.get('name') in set(ENV)|{'CPS_NATIVE_APPROVAL_COMPONENT'}]
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
    args=parser.parse_args(argv)
    if not args.render:
        print('Inert: --render requires a private operator input; no cluster access performed.'); return 0
    require(args.input is not None and args.output is not None, 'Private input and new output directory required')
    request=_private_json(args.input)
    require(isinstance(request, dict) and set(request)=={'version','source_raw','source_sha256','trusted_revision',
        'policy','qualification','baselines','captured_at','documents'} and type(request['version']) is int
        and request['version']==1, 'Closed operator render request required')
    policy=Policy(request['policy']); qualification=NativeGroupDeployment.from_config(request['qualification'], policy)
    kwargs={k:request[k] for k in ('source_sha256','trusted_revision','baselines')}
    kwargs.update(source_raw=request['source_raw'].encode(), policy=policy, qualification=qualification,
        captured_at=datetime.fromisoformat(request['captured_at'].replace('Z','+00:00')), now=datetime.now(timezone.utc))
    result=(document_intent(**kwargs) if request['documents'] is None
        else projection_intent(**kwargs, documents=request['documents']))
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    target=args.output/'intent.json'
    with target.open('x', encoding='utf-8') as handle:
        os.chmod(target, 0o600); handle.write(canonical(result)+'\n')
    print(canonical({'version':1, 'revision':result['revision'], 'components':len(result['documents']),
        'output_sha256':'sha256:'+hashlib.sha256(target.read_bytes()).hexdigest(), 'live_applied':False}))
    return 0


if __name__=='__main__':raise SystemExit(main())
