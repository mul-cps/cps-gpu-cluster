#!/usr/bin/env python3
"""Default-inert offline Root proposal for explicit 5+10GiB or 5+20GiB qualification.

No Kubernetes client, subprocess, GPU operation, or passed-evidence writer.
Root supplies fresh private captures and later owns source handover and Start.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import node_agent as agent

SCOPES = {'cps:native-group-b': 5, 'cit:native-group-a': 10}
PRESETS = {'cps5-cit10': SCOPES, 'cps5-cit20': {'cps:native-group-b': 5, 'cit:native-group-a': 20}}
CURRENT_GROUP_POLICY = 'sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'
CURRENT_GROUP_APPROVALS = 'sha256:3449819d393ed8026353effa57e9b4b0265779e0ef547179dc6c8e1cf72c74c5'
CURRENT_GATE_IMAGE = 'ghcr.io/mul-cps/cps-compute@sha256:bc5b128f582641eae8395e1121d1fb248eddc39a56c9e863b7c564badd94b167'
CURRENT_CONTROLLER = 'sha256:630d43cc115b5bddf3e5d110a25cc891e0941953bbabd833f0a77a3773ad7880'
CANDIDATE_IMAGE = 'ghcr.io/mul-cps/cps-jupyter-notebook@sha256:531027c8e330d4ce818598e998a29d502433e9064f06a32dfc208a06ef2d0ba4'
CANDIDATE_SOURCE_IMAGE = 'ghcr.io/mul-cps/e2x-course-hub@sha256:dbaad51899ccb634f5a07c44bd9f7022dbca71724d7cfd66e5d67abf9d569ace'
CANDIDATE_SOURCE_CLOSURE_SHA256 = '5f68ec802212eb4c3a8dd8bf37e96354c27a4c68724e525c0ef41c87af356905'


def checksum(raw): return 'sha256:' + hashlib.sha256(raw).hexdigest()


def validate_never_enrolled(evidence, allocations, history, ledger_meta, pool, health, observation, *, now, terminal_authority=None, previous_node=None,current_agent_source=None,validation=None):
    """Root snapshots distinguish released never-enrolled claims from real Pod history.

    This validates captured absence; it never creates an intent or host authority.
    The live node still re-GETs every historical enrollment/completion and its
    original protected journal before publishing a new cap.
    """
    import cps_compute.native_gpu_controller as models
    from current_group_historical_source import validation_context
    agent,map_history=validation or validation_context(current_agent_source)
    missing={binding:record for binding,record in allocations.items() if record['intent'] is None}
    if not missing:
        agent.require(evidence is None, 'No unrelated never-enrolled absence evidence')
        return []
    if terminal_authority is not None:
        agent.require(terminal_authority['authority_maps']==evidence['authority_maps']
            and terminal_authority['host_snapshot']==evidence['host_snapshot'],
            'Never-enrolled and terminal authority must use the same complete captures')
        agent.require(previous_node is not None, 'Full previous node configuration required for recovery authority')
        checked=map_history(terminal_authority, {'apiVersion':'v1','kind':'ConfigMap',
            'metadata':ledger_meta,'data':{'state.json':agent.canonical_json({'version':1,'allocations':allocations})}}, previous_node)
        agent.require(checked==history, 'Complete terminal authority mapping differs from proposal')
    agent.closed(evidence, {'authority_maps','host_snapshot','pods'}, 'Complete actual never-enrolled absence captures required')
    host=evidence['host_snapshot']
    agent.closed(host, {'version','observerPodUid','node','nodeUid','bootId','driverGeneration',
        'healthSourceSha256','observedAt','directories'}, 'Closed protected host snapshot required')
    observed=datetime.fromisoformat(host['observedAt'].replace('Z','+00:00'))
    agent.require(type(host['version']) is int and host['version']==1
        and host['observerPodUid']==observation['observerPodUid']
        and host['node']==pool['node'] and host['nodeUid']==pool['node_uid']
        and host['bootId']==health['bootId'] and host['driverGeneration']==health['driverGeneration']
        and host['healthSourceSha256']==health['sourceSha256']
        and observed.tzinfo is not None and 0<=(now-observed).total_seconds()<=900,
        'Fresh actual protected observer/node/driver epoch snapshot required')
    directories=host['directories']
    agent.closed(directories, {'enrollments','intents','journal'}, 'Complete protected authority directory lists required')
    contents={}
    for name,directory in directories.items():
        agent.closed(directory, {'ownerUid','mode','records'}, 'Closed complete protected directory snapshot required')
        agent.require(type(directory['ownerUid']) is int and directory['ownerUid']==0
            and type(directory['mode']) is int and directory['mode']==0o700
            and isinstance(directory['records'],dict), 'Original Root-private directory protection required')
        contents[name]={}
        for filename,record in directory['records'].items():
            agent.closed(record, {'uid','mode','nlink','rawSha256','value'}, 'Closed original protected file record required')
            agent.require(filename.endswith('.json') and agent.canonical_uuid(filename[:-5])
                and type(record['uid']) is int and record['uid']==0
                and type(record['mode']) is int and record['mode'] in (0o400,0o600)
                and type(record['nlink']) is int and record['nlink']==1
                and isinstance(record['rawSha256'],str)
                and re.fullmatch(r'sha256:[a-f0-9]{64}',record['rawSha256']) is not None and record['rawSha256']!='sha256:'+'0'*64
                and isinstance(record['value'],dict), 'Original no-follow Root file/UID/SHA protection required')
            contents[name][filename[:-5]]=record['value']
    maps=evidence['authority_maps']
    agent.require(isinstance(maps,dict) and maps.get('apiVersion')=='v1'
        and maps.get('kind') in ('List','ConfigMapList') and isinstance(maps.get('items'),list)
        and not maps.get('metadata',{}).get('continue'), 'Complete actual authority ConfigMap list required')
    namespace=ledger_meta['namespace']; by_name={}
    for original in maps['items']:
        cm=copy.deepcopy(original)
        if terminal_authority is not None and maps['kind']=='ConfigMapList' and isinstance(cm,dict):
            cm.setdefault('apiVersion','v1');cm.setdefault('kind','ConfigMap')
        meta=cm.get('metadata',{}) if isinstance(cm,dict) else {}
        agent.require(cm.get('apiVersion')=='v1' and cm.get('kind')=='ConfigMap'
            and meta.get('namespace')==namespace and isinstance(meta.get('name'),str)
            and agent.canonical_uuid(meta.get('uid')) and meta['name'] not in by_name,
            'Distinct actual namespaced authority ConfigMaps required')
        by_name[meta['name']]=cm
    enrolled={record['intent']['pod_uid']:record for record in allocations.values() if record['intent'] is not None}
    agent.require(set(contents['enrollments'])==set(contents['intents'])==set(enrolled)==set(history),
        'All original protected enrolled intents must correspond exactly to real terminal Pod history')
    cm_enrollments={name for name in by_name if name.startswith('cps-native-enrollment-')}
    expected_names={'cps-native-enrollment-'+record['binding_id'][:40] for record in enrolled.values()}
    agent.require(cm_enrollments==expected_names, 'Complete authority enrollment list differs from original enrolled ledger')
    for pod_uid,record in enrolled.items():
        envelope=contents['enrollments'][pod_uid]
        agent.closed(envelope, {'authority_namespace','configmap_name','configmap_uid','enrollment'},
            'Original protected enrollment envelope required')
        name='cps-native-enrollment-'+record['binding_id'][:40];cm=by_name[name]
        enrollment=agent.parse(cm.get('data',{}).get('enrollment.json','{}'))
        agent.require(envelope['authority_namespace']==namespace and envelope['configmap_name']==name
            and envelope['configmap_uid']==cm['metadata']['uid']==history[pod_uid]['enrollment_uid']
            and envelope['enrollment']==enrollment and cm.get('immutable') is True
            and not cm['metadata'].get('ownerReferences') and not cm['metadata'].get('deletionTimestamp')
            and agent.canonical_sha256(enrollment)==history[pod_uid]['enrollment_sha256']
            and enrollment.get('binding_id')==record['binding_id']
            and all(record.get(key)==value for key,value in enrollment.items())
            and contents['intents'][pod_uid]==record['intent'], 'Original immutable enrollment/intent/ledger detached')
    cleanup_uids={pod_uid for pod_uid,entry in history.items() if entry['completion_kind']=='cleanup'}
    agent.require(set(contents['journal'])==cleanup_uids, 'Never-gated abort or unknown claim acquired native cap authority')
    for pod_uid,body in contents['journal'].items():
        record=models.CapRecord.from_dict(body)
        agent.require(record.state in (('cleaned','retired-inert-cap','recovered-cleared-offline-cap')
                if terminal_authority is not None else ('cleaned','retired-inert-cap')) and record.intent.to_dict()==enrolled[pod_uid]['intent']
            and agent.canonical_sha256(body)==history[pod_uid]['journal_sha256'], 'Original typed terminal cap journal changed')
    pods=evidence['pods'];expected_pods={(record['namespace'],record['name']) for record in missing.values()}
    agent.require(isinstance(pods,list) and len(pods)==len(expected_pods), 'Complete distinct candidate Pod absence GETs required')
    seen=set()
    for pod in pods:
        agent.closed(pod, {'namespace','name','status'}, 'Actual candidate Pod GET result required')
        key=(pod['namespace'],pod['name'])
        agent.require(key in expected_pods and key not in seen and type(pod['status']) is int and pod['status']==404,
            'Never-enrolled candidate Pod must actually be absent')
        seen.add(key)
    for binding in missing:
        for cm in maps['items']:
            agent.require(cm.get('metadata',{}).get('labels',{}).get('cps.compute/native-binding')!=binding,
                'Never-enrolled claim acquired immutable enrollment/completion authority')
            for key in ('enrollment.json','abort.json','receipt.json'):
                if key in cm.get('data',{}):
                    body=agent.parse(cm['data'][key])
                    agent.require(body.get('binding_id')!=binding, 'Never-enrolled claim has late authority evidence')
    return sorted(missing)


def render(inputs, observation_raw, health_raw, *, now=None, preset='cps5-cit10', headroom_mib=1024, terminal_authority=None,current_agent_source=None):
    return _render(inputs,observation_raw,health_raw,now=now,preset=preset,headroom_mib=headroom_mib,
        terminal_authority=terminal_authority,current_agent_source=current_agent_source)


def _candidate_history_context():
    """Reuse the retained finite D48/39ef validator; no agent startup or patch."""
    from types import FunctionType,SimpleNamespace
    from historical_configuration_source import definitions
    from current_group_historical_source import historical_validator_source
    import terminal_policy_proposal as terminal
    namespace=dict(vars(agent))
    frozen=definitions(Path(agent.__file__).read_text())
    source=historical_validator_source(frozen['validate_historical_configuration'])
    exec(compile(source,'<existing-finite-retired-configuration-validator>','exec'),namespace)
    history_guard="len(history) <= 64, 'Bounded explicit terminal history required'"
    config_source=frozen['validate_config']
    agent.require(config_source.count(history_guard)==1,'Unique exact terminal history bound required')
    config_source=config_source.replace(history_guard,
        "len(history) <= 128, 'Bounded explicit terminal history required'",1)
    exec(compile(config_source,'<candidate-complete-history-validator>','exec'),namespace)
    reviewed=SimpleNamespace(**namespace)
    mapper=FunctionType(terminal.map_history.__code__,dict(terminal.map_history.__globals__,agent=reviewed))
    return reviewed,mapper


def _render(inputs, observation_raw, health_raw, *, now=None, preset='cps5-cit10', headroom_mib=1024,
        terminal_authority=None,current_agent_source=None,candidate=None):
    from cps_compute.policy import Policy
    from cps_compute.native_groups import WORKLOAD_IMAGE, HEALTH_SHA256
    from cps_compute.native_qualification import NativeGroupQualification
    from cps_compute.native_gpu_control import MeasuredNativeAuthority
    from current_group_historical_source import validation_context,runtime_history
    validation=_candidate_history_context() if candidate is not None else validation_context(current_agent_source)
    agent,map_history=validation
    agent.require(type(preset) is str and preset in PRESETS, 'Explicit reviewed 5/10 or 5/20 preset required')
    agent.require(type(headroom_mib) is int and headroom_mib == 1024, 'Exact additional 1024MiB headroom required')
    if candidate is None:
        scopes = PRESETS[preset]
    elif 'targets' in candidate:
        scopes = {'cps:'+t['workspace']:int(t['profile'].rsplit('-',1)[1]) for t in candidate['targets']}
    else:
        scopes = {'cps:'+candidate['workspace']:5}
    workload_image = WORKLOAD_IMAGE if candidate is None else CANDIDATE_IMAGE
    budget = sum(scopes.values()) * 1024
    agent.closed(inputs, {'version', 'catalog', 'approvals', 'node_config', 'ledger',
        'terminal_history', 'observed_at', 'gate_image', 'never_enrolled_evidence'}, 'Closed offline qualification input required')
    agent.require(type(inputs['version']) is int and inputs['version'] == 1
        and isinstance(inputs['approvals'], dict) and set(inputs['approvals']) == set(scopes),
        'Only the reviewed neutral workspace scopes are supported')
    observed = datetime.fromisoformat(inputs['observed_at'].replace('Z', '+00:00'))
    now = now or datetime.now(timezone.utc)
    agent.require(observed.tzinfo is not None and 0 <= (now - observed).total_seconds() <= 900,
        'Fresh timezone-aware capacity capture within 15 minutes required')
    observation, health = agent.parse(observation_raw), agent.parse(health_raw)
    agent.closed(observation, {'nvmlDriverVersion', 'observerPodUid', 'gpus'}, 'Closed actual NVML observation required')
    agent.closed(health, {'bootId', 'driverGeneration', 'driverVersion', 'healthPassed', 'sourceSha256'},
        'Closed actual protected health observation required')
    agent.require(observation['nvmlDriverVersion'] == health['driverVersion'] == '615.71.09'
        and health['healthPassed'] is True and health['sourceSha256'] == HEALTH_SHA256
        and agent.canonical_uuid(observation['observerPodUid']), 'Exact current R615 observer/health required')
    baseline = inputs['node_config']; agent.validate_config(baseline)
    pool = {key:baseline['pool'][key] for key in ('node', 'node_uid', 'gpu_uuid')}
    gpus = observation['gpus']
    agent.require(isinstance(gpus, list) and 1 <= len(gpus) <= 2
        and len({gpu.get('uuid') for gpu in gpus}) == len(gpus), 'Distinct physical observed devices required')
    selected = [gpu for gpu in gpus if gpu.get('uuid') == pool['gpu_uuid']]
    agent.require(len(selected) == 1, 'Selected physical GPU must occur exactly once')
    gpu = selected[0]
    agent.closed(gpu, {'uuid', 'migCurrent', 'migPending', 'memoryTotalBytes', 'memoryFreeBytes', 'memoryUsedBytes'},
        'Closed selected GPU capacity observation required')
    agent.require(type(gpu['migCurrent']) is int and gpu['migCurrent'] == 0
        and type(gpu['migPending']) is int and gpu['migPending'] == 0
        and all(type(gpu[key]) is int and gpu[key] >= 0
            for key in ('memoryTotalBytes', 'memoryFreeBytes', 'memoryUsedBytes'))
        and gpu['memoryFreeBytes'] + gpu['memoryUsedBytes'] == gpu['memoryTotalBytes'],
        'Exact no-MIG physical memory accounting required')
    pool.update(max_workspaces=2 if candidate is None else len(scopes), total_memory_mib=gpu['memoryTotalBytes'] // 1048576,
        free_memory_mib=gpu['memoryFreeBytes'] // 1048576, headroom_mib=headroom_mib,
        memory_budget_mib=budget, boot_id=health['bootId'], driver_generation=health['driverGeneration'])
    agent.validate_measured_pool(pool)
    ledger = inputs['ledger']; meta = ledger.get('metadata', {})
    agent.require(ledger.get('kind') == 'ConfigMap' and ledger.get('apiVersion') == 'v1'
        and meta.get('name') == 'cps-native-gpu-allocations'
        and meta.get('namespace') == baseline['authority_namespace'] and agent.canonical_uuid(meta.get('uid'))
        and isinstance(meta.get('resourceVersion'), str) and meta['resourceVersion'], 'Actual captured ledger UID/RV required')
    state = agent.parse(ledger.get('data', {}).get('state.json', '{}'))
    agent.closed(state, {'version', 'allocations'}, 'Closed historical ledger required')
    agent.require(type(state['version']) is int and state['version'] == 1, 'Versioned historical ledger required')
    # Source-only schema validation uses no constructor, backend, files or clients.
    validator = MeasuredNativeAuthority.__new__(MeasuredNativeAuthority); validator.pool = pool
    validator._validate_allocations(state['allocations'])
    agent.require((preset!='cps5-cit20' and candidate is None) or not state['allocations'] or terminal_authority is not None,
        'Twenty preset cannot move an existing ledger without complete terminal authority')
    history = inputs['terminal_history']
    agent.require(isinstance(history, dict), 'Actual independently captured terminal history required')
    uids = set()
    for binding, record in state['allocations'].items():
        agent.require(record['state'] == 'released', 'Every previous ledger claim must be released')
        if record['intent'] is None:
            continue
        uid = record['intent']['pod_uid']; uids.add(uid); entry = history.get(uid)
        agent.require(isinstance(entry, dict) and entry.get('binding_id') == binding
            and entry.get('policy_hash') == record['policy_hash'] and entry.get('profile') == record['profile']
            and entry.get('ledger_uid') == meta['uid'], 'Complete actual terminal history for every previous claim required')
    agent.require(set(history) == uids, 'No omitted or invented historical Pod UID')
    if terminal_authority is not None:
        agent.require((preset=='cps5-cit20' or candidate is not None) and map_history(terminal_authority,ledger,baseline)==history,
            'Twenty preset requires the unchanged complete terminal authority mapping')
    never_enrolled=validate_never_enrolled(inputs['never_enrolled_evidence'],state['allocations'],history,meta,pool,health,observation,now=now,terminal_authority=terminal_authority,previous_node=baseline,current_agent_source=current_agent_source,validation=validation)
    catalog = copy.deepcopy(inputs['catalog']); catalog.pop('policyHash', None)
    agent.require(catalog.get('gpuQualification', {}).get('qualified') is False,
                  'Ordinary global GPU qualification must remain false')
    caps = {}; approvals = copy.deepcopy(inputs['approvals'])
    for scope, size in scopes.items():
        name = 'interactive-native-qualification-' + str(size); caps[name] = size * 1024
        entry = copy.deepcopy(catalog['profiles']['interactive-shared-5'])
        entry.update(enabled=False, kind='interactive', queue='interactive', cpu='4', memory='16Gi', images=[workload_image])
        entry.pop('qualificationRequired', None)
        entry['gpu'] = {'mode':'shared', 'nominalMemoryGiB':size, 'qualification':{
            'mechanism':'r615-native-cgroup-managed-deny', 'status':'pilot-unqualified'}}
        if name in catalog['profiles']:
            agent.require((preset == 'cps5-cit20' or candidate is not None) and catalog['profiles'][name] == entry,
                'Existing qualification profile must be exactly the trusted disabled template')
        catalog['profiles'][name] = entry
        approvals[scope]['profiles'] = [name]
        approvals[scope]['ceiling'] = {'cpu':'4', 'memory':'16Gi', 'gpuMemoryGiB':size}
    policy = Policy(catalog)
    catalog['policyHash'] = policy.hash
    mode = {'enabled':True, 'version':1, 'operator_only':True, 'policy_hash':policy.hash,
        'policy_version':policy.version, 'node_pool':pool, 'authorityNamespace':baseline['authority_namespace'],
        'gateImage':inputs['gate_image'], 'workloadImage':workload_image, 'profile_caps':caps,
        'capacity_observation_sha256':checksum(observation_raw), 'workspaces':approvals}
    NativeGroupQualification.from_config(mode, policy)
    node = {'version':2, 'enabled':True, 'mode':'operator-qualification',
        'authority_namespace':baseline['authority_namespace'], 'policy_hash':policy.hash, 'pool':pool,
        'workspaces':{scope:{'profile':body['profiles'][0], 'cap_mib':caps[body['profiles'][0]]}
            for scope,body in approvals.items()}, 'terminal_history':runtime_history(history,policy.hash,current_agent_source)}
    agent.validate_config(node)
    result = {'policy.json':catalog, 'operator-qualification.json':mode, 'node-config.json':node,
        'registration-proposals.json':{scope:{'workspace':scope.split(':',1)[1], 'policy_hash':policy.hash, **body}
            for scope,body in approvals.items()},
        'acceptance.json':{'version':1, 'hardware_qualified':False, 'live_applied':False,
            'source_handover_required':True, 'scopes':scopes, 'budget_mib':budget,
            'observation_sha256':checksum(observation_raw), 'health_sha256':checksum(health_raw),
            'ledger_uid':meta['uid'], 'ledger_resource_version':meta['resourceVersion'],
            'old_terminal_pod_uids':sorted(uids), 'released_never_enrolled_bindings':never_enrolled,
            'never_enrolled_evidence_sha256':agent.canonical_sha256(inputs['never_enrolled_evidence']) if never_enrolled else None,
            'policy_hash':policy.hash}}
    if terminal_authority is not None:
        result['terminal-authority-snapshot.json']=copy.deepcopy({'ledger':ledger, 'previous_node':baseline, **terminal_authority})
        result['acceptance.json']['terminal_authority_sha256']=agent.canonical_sha256(result['terminal-authority-snapshot.json'])
    if current_agent_source is not None:
        result['acceptance.json']['source_node_agent_sha256']=checksum(current_agent_source.encode())
    return result


def render_prospective_candidate(inputs, observation_raw, health_raw, *, target_snapshot_raw,
        target_snapshot_sha256, source_closure_raw, source_closure_sha256, terminal_authority, now=None,
        peer_target_snapshot_raw=None, peer_target_snapshot_sha256=None):
    """Pure Root-pinned single5 or CPS5+20 proposal, never a hardware proof."""
    from cps_compute.native_groups import APPROVAL_FIELDS,canonical_sha256
    from cps_compute.native_qualification import NativeGroupQualification
    from cps_compute.policy import Policy
    import inspect
    agent.require(isinstance(target_snapshot_raw,bytes) and len(target_snapshot_raw)<=1048576
        and hashlib.sha256(target_snapshot_raw).hexdigest()==target_snapshot_sha256
        and isinstance(source_closure_raw,bytes) and len(source_closure_raw)<=65536
        and hashlib.sha256(source_closure_raw).hexdigest()==source_closure_sha256==CANDIDATE_SOURCE_CLOSURE_SHA256,'Independent Root raw target/source closure pins required')
    target=agent.parse(target_snapshot_raw);closure=agent.parse(source_closure_raw)
    agent.closed(closure,{'version','modules'},'Closed runtime source closure required')
    modules={'e2x_course_hub.course_service.app','e2x_course_hub.cps.compute','e2x_course_hub.cps.workspaces',
        'e2x_course_hub.cps.providers','e2x_course_hub.cps.validation','e2x_course_hub.cps.identity','e2x_course_hub.cps.expiry',
        'cps_compute.native_groups','cps_compute.native_pool','cps_compute.native_qualification','cps_compute.policy',
        'cps_compute.internal','cps_compute.identity','cps_compute.reservations','cps_compute.native_gpu_control','cps_compute.native_gpu_controller'}
    agent.require(type(closure['version']) is int and closure['version']==1 and isinstance(closure['modules'],dict)
        and set(closure['modules'])==modules and all(isinstance(h,str) and re.fullmatch('[a-f0-9]{64}',h)
            and h!='0'*64 for h in closure['modules'].values()),'Exact application/service source closure required')
    agent.require(closure['modules']['cps_compute.native_qualification']==hashlib.sha256(
        Path(inspect.getfile(NativeGroupQualification)).read_bytes()).hexdigest(),'Current reviewed candidate qualification source required')
    agent.closed(target,{'version','source','workspace','profile','workload_image','operator_members','source_policy_hash',
        'source_closure_sha256','current_authority_sha256','source_instance','registration','state','observed_at'},
        'Closed Root operator target snapshot required')
    source_policy=Policy(inputs['catalog']);now=now or datetime.now(timezone.utc)
    targets=[target]
    if peer_target_snapshot_raw is not None or peer_target_snapshot_sha256 is not None:
        agent.require(isinstance(peer_target_snapshot_raw,bytes) and len(peer_target_snapshot_raw)<=1048576
            and isinstance(peer_target_snapshot_sha256,str) and re.fullmatch('[0-9a-f]{64}',peer_target_snapshot_sha256)
            and hashlib.sha256(peer_target_snapshot_raw).hexdigest()==peer_target_snapshot_sha256,
            'Independent Root peer raw pin required before pair interpretation')
        peer=agent.parse(peer_target_snapshot_raw)
        agent.require(target.get('profile')=='interactive-native-qualification-5'
            and peer.get('profile')=='interactive-native-qualification-20','Primary5 and independently pinned peer20 must retain their raw target identities')
        from prospective_source_qualification_workspace import validate_pair_targets
        targets=validate_pair_targets(target,peer,now=now)
    captured_approvals={}
    for index,target in enumerate(targets):
        workspace=target['workspace']
        agent.require(type(target['version']) is int and target['version']==1 and target['source']=='cps'
            and isinstance(workspace,str) and re.fullmatch(r'operator-qualification-531-[a-z0-9](?:[a-z0-9-]{0,36}[a-z0-9])?',workspace)
            and target['profile']==('interactive-native-qualification-5' if index==0 else 'interactive-native-qualification-20') and target['workload_image']==CANDIDATE_IMAGE
            and target['source_policy_hash']==source_policy.hash==inputs['node_config']['policy_hash']
            and target['source_closure_sha256']==source_closure_sha256 and target['state']=='stopped',
            'Dedicated stopped CPS candidate5 scope and unchanged source policy required')
        instance=target['source_instance'];agent.closed(instance,{'namespace','deployment_uid','pod_uid','image'},'Closed actual Source instance required')
        agent.require(instance['namespace']=='cps-compute' and instance['image']==CANDIDATE_SOURCE_IMAGE
            and all(agent.canonical_uuid(instance[k]) and instance[k]!='00000000-0000-0000-0000-000000000000'
                for k in ('deployment_uid','pod_uid')),'Exact reviewed notebook531-capable Source namespace/image/UIDs required')
        for timestamp in (target['observed_at'],inputs['observed_at'],(terminal_authority or {}).get('host_snapshot',{}).get('observedAt')):
            agent.require(isinstance(timestamp,str),'Fresh target and full retired authority timestamps required')
            observed=datetime.fromisoformat(timestamp.replace('Z','+00:00'))
            agent.require(observed.tzinfo is not None and observed.utcoffset().total_seconds()==0
                and 0<=(now-observed).total_seconds()<=900,'Fresh Root UTC source/authority snapshot required')
        agent.require(isinstance(terminal_authority,dict) and target['current_authority_sha256']==canonical_sha256(
            dict(ledger=inputs['ledger'],previous_node=inputs['node_config'],**terminal_authority)),
            'Complete independently pinned current retired authority required')
        registered=target['registration'];agent.closed(registered,set(APPROVAL_FIELDS)|{'workspace','policy_hash','workspace_label','workspace_hash'},
            'Exact normal Source registered workspace required')
        members=target['operator_members']
        agent.require(isinstance(members,list) and 1<=len(members)<=8 and len(set(members))==len(members)
            and all(agent.canonical_uuid(p) and p!='00000000-0000-0000-0000-000000000000' for p in members)
            and not set(members)&{'15164372-7ae5-4cfd-8b5d-fd402aa891bd','85de720c-94b0-4bc7-807e-c04512133494'}
            and registered['members']==members,'Only explicit nonstudent canonical operator members required')
        owner=registered['owner'];scope='cps:'+workspace
        agent.require(isinstance(owner,str) and re.fullmatch('cps-ws-[a-f0-9]{32}',owner)
            and owner!='cps-ws-27c474f74f9d41c53eac0be01fcca8a3'
            and registered['workspace']==workspace and registered['policy_hash']==source_policy.hash
            and registered['namespace']=='jupyterhub' and registered['server']=='rtc'
            and registered['pod']=='jupyter-'+owner+'--rtc' and registered['principal']=='workspace:'+scope
            and registered['profiles']==['interactive-cpu']
            and registered['workspace_label']==source_policy.labels['workspace'] and registered['workspace_hash']==source_policy.owner_label(scope)
            and all(isinstance(registered[k],str) and registered[k].startswith('operator-') for k in ('course_id','term_id','group_id')),
            'Exact dedicated neutral owner/descriptor/CPU registration required')
        approval={k:copy.deepcopy(registered[k]) for k in APPROVAL_FIELDS}
        agent.require(approval['storage'].pop('state',None)=='active','Current provisioned operator storage required')
        captured_approvals[scope]=approval
    agent.require(inputs['approvals']==captured_approvals and inputs['gate_image']==CURRENT_GATE_IMAGE,
        'Exact captured Source registrations/storage and unchanged Gate required')
    # Real provisioned registrations retain NFS provenance metadata. Runtime
    # approvals carry only the fixed descriptor; snapshots keep every byte.
    from cps_compute.native_groups import STORAGE_FIELDS
    candidate_inputs=copy.deepcopy(inputs)
    for approval in candidate_inputs['approvals'].values():
        storage=approval['storage']
        agent.require(isinstance(storage,dict) and STORAGE_FIELDS <= set(storage)
            and not set(storage)-(STORAGE_FIELDS|{'server','evidence'})
            and ('server' not in storage or (isinstance(storage['server'],str)
                and re.fullmatch(r'[A-Za-z0-9.-]{1,253}',storage['server'])))
            and ('evidence' not in storage or isinstance(storage['evidence'],dict)),
            'Only typed provisioning metadata may accompany a fixed native storage descriptor')
        approval['storage']={key:copy.deepcopy(storage[key]) for key in STORAGE_FIELDS}
    result=_render(candidate_inputs,observation_raw,health_raw,now=now,terminal_authority=terminal_authority,candidate=target if len(targets)==1 else {'targets':targets})
    result['acceptance.json'].update(source_mode='prospective-candidate',target_snapshot_sha256=target_snapshot_sha256,
        source_closure_sha256=source_closure_sha256,current_authority_sha256=target['current_authority_sha256'],
        terminal_history_sha256=canonical_sha256(result['node-config.json']['terminal_history']))
    result['target-snapshot.json']=copy.deepcopy(targets[0]);result['source-closure.json']=copy.deepcopy(closure)
    if len(targets)==2:
        result['peer-target-snapshot.json']=copy.deepcopy(targets[1])
        result['acceptance.json']['peer_target_snapshot_sha256']=peer_target_snapshot_sha256
    return result


def render_current_approved_groups(inputs, observation_raw, health_raw, *,
        source_runtime_raw, source_runtime_sha256, source_hubs_raw, source_hubs_sha256,
        source_controller_raw, terminal_authority, now=None,current_agent_source=None):
    """Separate actual group-mode input, never relabelled as old qualification.

    Outputs are prospective native-field overlays, not complete application
    configurations or an apply packet. Unrelated CPU/Argo settings are omitted
    so a later reviewed custody/CAS handover must preserve them unchanged.
    """
    from cps_compute.policy import Policy
    from cps_compute.native_groups import NativeGroupDeployment
    from cps_compute import native_gpu_controller as models
    from current_group_historical_source import validation_context
    agent,_=validation_context(current_agent_source)
    agent.require(checksum(source_controller_raw)==CURRENT_CONTROLLER
        and source_controller_raw==Path(models.__file__).read_bytes(),
        'Exact current captured and loaded 630 controller model dependency required')
    agent.require(checksum(source_runtime_raw)==source_runtime_sha256
        and checksum(source_hubs_raw)==source_hubs_sha256, 'Exact raw current source pins required')
    runtime=agent.parse(source_runtime_raw); hubs=agent.parse(source_hubs_raw)
    agent.closed(runtime, {'policy_hash','nativeGpuGroups','nativeGpuQualification','nativeGpuPilot'},
        'Closed sanitized actual native runtime projection required')
    policy=Policy(inputs['catalog'])
    agent.require(runtime['policy_hash']==policy.hash==CURRENT_GROUP_POLICY
        and runtime['nativeGpuQualification']==runtime['nativeGpuPilot']=={'enabled':False},
        'Exact reviewed d48 group mode with qualification/pilot disabled required')
    group=runtime['nativeGpuGroups']; deployment=NativeGroupDeployment.from_config(group,policy)
    agent.require(deployment is not None and group['evidence']['version']==2
        and agent.canonical_sha256(group['workspaces'])==CURRENT_GROUP_APPROVALS
        and group['gateImage']==CURRENT_GATE_IMAGE
        and group['evidence']['profile_caps']=={'interactive-shared-5':5120,'interactive-shared-10':10240}
        and group['node_pool']['max_workspaces']==2 and group['node_pool']['memory_budget_mib']==15360
        and group['node_pool']['headroom_mib']==1024,
        'Only the exact two approved current 5/10 group slots are supported')
    node=inputs['node_config']; agent.validate_config(node)
    expected={scope:{'profile':body['profiles'][0],'cap_mib':body['ceiling']['gpuMemoryGiB']*1024}
        for scope,body in group['workspaces'].items()}
    agent.require(node['version']==2 and node['enabled'] is True and node['mode']=='qualified-group'
        and node['policy_hash']==policy.hash and node['authority_namespace']==group['authorityNamespace']
        and node['pool']==group['node_pool'] and node['workspaces']==expected
        and inputs['approvals']==group['workspaces'] and inputs['gate_image']==group['gateImage'],
        'Actual current group/node/approval configuration must agree')
    health=agent.parse(health_raw)
    agent.require(health['bootId']==group['node_pool']['boot_id']
        and health['driverGeneration']==group['node_pool']['driver_generation'],
        'Current group source must remain in the captured actual driver epoch')
    agent.closed(hubs, {'cps','cit'}, 'Both actual Hub native settings projections required')
    preserved_profiles={}
    for source,size in SCOPES.items():
        hub=source.split(':',1)[0]; settings=hubs[hub]
        optional={'qualificationDeployment','pilotDeployment'} & set(settings)
        agent.closed(settings, {'source','groupDeployment','profiles'} | optional,
            'Closed actual Hub native settings projection required')
        profiles=settings['profiles']; expected_profile='interactive-shared-'+str(size)
        agent.require(settings['source']==hub and settings['groupDeployment']==group
            and all(settings[k]=={'enabled':False} for k in optional)
            and isinstance(profiles,list) and all(type(p) is str for p in profiles)
            and len(profiles)==len(set(profiles)) and expected_profile in profiles,
            'Exact current per-Hub group deployment and permitted profile required')
        cpu=[p for p in profiles if p!=expected_profile]
        agent.require(all(p in policy.catalog['profiles']
            and policy.catalog['profiles'][p].get('gpu',{}).get('mode')=='none'
            and policy.catalog['profiles'][p].get('kind')=='interactive' for p in cpu),
            'No foreign, batch or additional GPU Hub profiles are permitted')
        preserved_profiles[hub]=cpu
    agent.require(terminal_authority is not None, 'Complete fresh released terminal custody required')
    result=render(inputs,observation_raw,health_raw,now=now,preset='cps5-cit20',terminal_authority=terminal_authority,current_agent_source=current_agent_source)
    mode=result['operator-qualification.json']
    result['runtime-native-overlay.json']={'policy_hash':mode['policy_hash'],
        'nativeGpuGroups':{'enabled':False},'nativeGpuPilot':{'enabled':False},'nativeGpuQualification':copy.deepcopy(mode)}
    result['hub-native-overlays.json']={hub:{'groupDeployment':{'enabled':False},
        'pilotDeployment':{'enabled':False},'qualificationDeployment':copy.deepcopy(mode),
        'profiles':profiles+[mode['workspaces'][hub+':native-group-'+('b' if hub=='cps' else 'a')]['profiles'][0]]}
        for hub,profiles in preserved_profiles.items()}
    result['current-source.json']={'runtime':runtime,'hubs':hubs}
    result['acceptance.json'].update(source_mode='current-approved-groups',
        source_runtime_sha256=source_runtime_sha256,source_hubs_sha256=source_hubs_sha256,
        source_controller_sha256=CURRENT_CONTROLLER, controller_rollout_required=False,
        source_policy_hash=policy.hash,source_node_config_sha256=agent.canonical_sha256(node),
        configuration_application_required=True, unrelated_configuration_must_remain_unchanged=True)
    return result


def private_read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        agent.require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.geteuid()
            and stat.S_IMODE(before.st_mode) in (0o400, 0o600) and 0 < before.st_size <= 4194304,
            'Private owned bounded regular proposal input required')
        raw = os.read(fd, 4194305); after = os.fstat(fd)
        agent.require(len(raw) == before.st_size and all(getattr(before,key) == getattr(after,key)
            for key in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')), 'Proposal input changed during read')
        return raw
    finally: os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--terminal-authority', type=Path)
    parser.add_argument('--preset', choices=tuple(PRESETS), default='cps5-cit10')
    parser.add_argument('--source-mode', choices=('legacy-qualification','current-approved-groups','prospective-candidate'), default='legacy-qualification')
    parser.add_argument('--source-runtime', type=Path)
    parser.add_argument('--source-runtime-sha256')
    parser.add_argument('--source-hubs', type=Path)
    parser.add_argument('--source-hubs-sha256')
    parser.add_argument('--source-controller', type=Path)
    parser.add_argument('--target-snapshot',type=Path)
    parser.add_argument('--target-snapshot-sha256')
    parser.add_argument('--source-closure',type=Path)
    parser.add_argument('--source-closure-sha256')
    parser.add_argument('--peer-target-snapshot',type=Path)
    parser.add_argument('--peer-target-snapshot-sha256')
    for key in ('input','observation','health','output'): parser.add_argument('--'+key, type=Path)
    args = parser.parse_args(argv)
    if not args.render:
        agent.require(args.source_mode=='legacy-qualification' and not any((args.input,args.observation,args.health,args.output,args.terminal_authority,
            args.source_runtime,args.source_runtime_sha256,args.source_hubs,args.source_hubs_sha256,args.source_controller,
            args.target_snapshot,args.target_snapshot_sha256,args.source_closure,args.source_closure_sha256,args.peer_target_snapshot,args.peer_target_snapshot_sha256)), 'Inputs require explicit offline --render')
        print(json.dumps({'enabled':False, 'live_applied':False, 'hardware_qualified':False}))
        return 0
    agent.require(all((args.input,args.observation,args.health,args.output)), 'Complete private offline input/output paths required')
    candidate=args.source_mode=='prospective-candidate'
    agent.require(not any((args.target_snapshot,args.target_snapshot_sha256,args.source_closure,args.source_closure_sha256,args.peer_target_snapshot,args.peer_target_snapshot_sha256)) or candidate,
        'Candidate target/closure pins require explicit prospective-candidate mode')
    if candidate:
        agent.require(args.preset=='cps5-cit10' and all((args.target_snapshot,args.source_closure,args.terminal_authority))
            and all(isinstance(pin,str) and re.fullmatch('[a-f0-9]{64}',pin) and pin!='0'*64
                for pin in (args.target_snapshot_sha256,args.source_closure_sha256))
            and not any((args.source_runtime,args.source_runtime_sha256,args.source_hubs,args.source_hubs_sha256,args.source_controller)),
            'Explicit candidate raw pins and complete retired authority required before private input')
    agent.require((args.peer_target_snapshot is None and args.peer_target_snapshot_sha256 is None) or
        (candidate and args.peer_target_snapshot is not None and isinstance(args.peer_target_snapshot_sha256,str)
         and re.fullmatch('[a-f0-9]{64}',args.peer_target_snapshot_sha256) and args.peer_target_snapshot_sha256!='0'*64),
        'Complete independent Root peer raw pins required before private input')
    agent.require(args.preset!='cps5-cit20' or args.terminal_authority is not None,
        'Twenty preset requires the full terminal authority bundle')
    authority=agent.parse(private_read(args.terminal_authority)) if args.terminal_authority else None
    if candidate:
        values=render_prospective_candidate(agent.parse(private_read(args.input)),private_read(args.observation),private_read(args.health),
            target_snapshot_raw=private_read(args.target_snapshot),target_snapshot_sha256=args.target_snapshot_sha256,
            source_closure_raw=private_read(args.source_closure),source_closure_sha256=args.source_closure_sha256,terminal_authority=authority,
            peer_target_snapshot_raw=private_read(args.peer_target_snapshot) if args.peer_target_snapshot else None,
            peer_target_snapshot_sha256=args.peer_target_snapshot_sha256)
    elif args.source_mode=='current-approved-groups':
        agent.require(args.preset=='cps5-cit20' and all((args.source_runtime,args.source_runtime_sha256,args.source_hubs,args.source_hubs_sha256,args.source_controller)),
            'Current source mode requires explicit twenty preset and exact runtime/Hub source pins')
        values=render_current_approved_groups(agent.parse(private_read(args.input)),private_read(args.observation),private_read(args.health),
            terminal_authority=authority,source_runtime_raw=private_read(args.source_runtime),source_runtime_sha256=args.source_runtime_sha256,
            source_hubs_raw=private_read(args.source_hubs),source_hubs_sha256=args.source_hubs_sha256,
            source_controller_raw=private_read(args.source_controller))
    else:
        agent.require(not any((args.source_runtime,args.source_runtime_sha256,args.source_hubs,args.source_hubs_sha256,args.source_controller)),
            'Current source pins cannot be silently interpreted as legacy qualification mode')
        values=render(agent.parse(private_read(args.input)),private_read(args.observation),private_read(args.health),preset=args.preset,
            terminal_authority=authority)
    args.output.mkdir(mode=0o700)
    hashes = {}
    for name,value in values.items():
        raw = (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
        fd = os.open(args.output/name, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
        try: os.write(fd,raw)
        finally: os.close(fd)
        hashes[name] = checksum(raw)
    print(json.dumps({'offline_proposal':True, 'hardware_qualified':False, 'files':hashes},sort_keys=True))
    return 0


if __name__ == '__main__': raise SystemExit(main())
