#!/usr/bin/env python3
"""Strict offline evaluator for the suspended mixed-profile candidate.

Even complete synthetic inputs cannot authorize GPU sharing or MPS changes.
"""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import uuid

import mixed_contract as contract
import mixed_render as renderer
import render as original
from evaluate_compiled import (contains_fragment, defaulted_container, mount_mapping,
                               owned_configmap, unique_mapping)
from probe_compiled import CACHE_PATH, normalized_uuid


COMPILER = {'sourceCommit':contract.SOURCE,'moduleSha256':contract.MODULE_SHA,'version':'0.1.0'}


def validate_executable_pod(pod, template, receipts, gib):
    """Allow only the fixed compiler plan, API defaults and bounded KAI additions."""
    if type(gib) is not int or gib not in contract.QUOTAS:
        raise ValueError('Reviewed profile required')
    actual, expected = copy.deepcopy(pod['spec']), copy.deepcopy(template['spec'])
    main = actual['containers'][0]
    selection = [e for e in main['env'] if e['name'] == 'NVIDIA_VISIBLE_DEVICES']
    contract.require(len(selection) == 1, 'One actual KAI selection required')
    ref = selection[0]['valueFrom']['configMapKeyRef']
    contract.require(set(ref) == {'name','key'} and ref['key'] == 'NVIDIA_VISIBLE_DEVICES',
                     'Bound KAI selection reference required')
    cm_name = ref['name']; gpu = pod['metadata']['annotations'][original.REVIEWED_GPU_ANNOTATION]
    quota = contract.QUOTAS[gib]
    cm = owned_configmap(cm_name,pod,receipts)
    for observed in (cm,owned_configmap(cm_name+'-evar',pod,receipts)):
        owners = observed['metadata']['ownerReferences']
        contract.require(len(owners) == 1 and set(owners[0]) <= {'apiVersion','kind','name','uid','controller','blockOwnerDeletion'}
            and all(type(owners[0][k]) is bool for k in ('controller','blockOwnerDeletion') if k in owners[0]),
            'Only the exact observed Pod owner may own injector data')
    contract.require(cm.get('data') == {'CUDA_DEVICE_MEMORY_LIMIT':str(quota['globalMiB'])+'m',
        'GPU_PORTION':quota['portion'],'RUNAI_NUM_OF_GPUS':quota['portion'],
        'NVIDIA_VISIBLE_DEVICES':'k8s.device-plugin.nvidia.com/gpu='+gpu},
        'Actual owned KAI quota must match the explicitly unqualified profile candidate')
    empty = owned_configmap(cm_name+'-evar',pod,receipts)
    contract.require(empty.get('data') in (None,{}), 'Injector envFrom must remain empty')
    wanted = expected['containers'][0]
    wanted['env'].extend([
        {'name':'POD_UID','valueFrom':{'fieldRef':{'apiVersion':'v1','fieldPath':'metadata.uid'}}},
        {'name':'CONTAINER_NAME','value':'main'},
        {'name':'CONTAINER_VGPU_MOUNT','value':'/usr/local/vgpu'},
        *[{'name':name,'valueFrom':{'configMapKeyRef':{'name':cm_name,'key':name,
            **({'optional':True} if name == 'CUDA_DEVICE_MEMORY_LIMIT' else {})}}}
          for name in ('NVIDIA_VISIBLE_DEVICES','RUNAI_NUM_OF_GPUS','GPU_PORTION','CUDA_DEVICE_MEMORY_LIMIT')]])
    wanted['envFrom'] = [{'configMapRef':{'name':cm_name+'-evar','optional':False}}]
    wanted['volumeMounts'].extend([
        {'name':'kai-resource-isolator-vgpu','mountPath':'/usr/local/vgpu'},
        {'name':'kai-resource-isolator-vgpu','mountPath':'/etc/ld.so.preload','readOnly':True,'subPath':'ld.so.preload'},
        {'name':'kai-resource-isolator-containers','mountPath':'/usr/local/vgpu/containers'},
        {'name':'kai-resource-isolator-vgpulock','mountPath':'/tmp/vgpulock'}])
    expected['volumes'].extend([
        {'name':'kai-resource-isolator-vgpu','hostPath':{'path':'/usr/local/vgpu','type':'DirectoryOrCreate'}},
        {'name':'kai-resource-isolator-containers','hostPath':{'path':'/usr/local/vgpu/containers','type':'DirectoryOrCreate'}},
        {'name':'kai-resource-isolator-vgpulock','hostPath':{'path':'/tmp/vgpulock','type':'DirectoryOrCreate'}},
        {'name':cm_name+'-vol','configMap':{'name':cm_name,'defaultMode':420}}])
    for field in ('containers','initContainers'):
        current,wanted_list = actual.pop(field),expected.pop(field)
        contract.require([v['name'] for v in current] == [v['name'] for v in wanted_list], 'Executable order changed')
        for container,template_container in zip(current,wanted_list):
            container,template_container = defaulted_container(container),defaulted_container(template_container)
            contract.require(unique_mapping(container.pop('env',[]),'name') ==
                unique_mapping(template_container.pop('env',[]),'name'), 'Executable environment changed')
            contract.require(mount_mapping(container.pop('volumeMounts',[])) ==
                mount_mapping(template_container.pop('volumeMounts',[])), 'Executable mounts changed')
            contract.require(container == template_container, 'Executable command/security/resources/probes changed')
    contract.require(unique_mapping(actual.pop('volumes'),'name') == unique_mapping(expected.pop('volumes'),'name'),
                     'Volume sources changed')
    defaults = {'dnsPolicy':'ClusterFirst','enableServiceLinks':True,'terminationGracePeriodSeconds':30,
        'serviceAccountName':'default','serviceAccount':'default','preemptionPolicy':'PreemptLowerPriority',
        'priority':10,'runtimeClassName':'nvidia','nodeName':original.NODE,'hostIPC':False,'hostPID':False,
        'hostNetwork':False,'shareProcessNamespace':False}
    for field,value in defaults.items():
        if field in actual:
            current = actual.pop(field)
            contract.require(current == value and type(current) is type(value), 'Pod runtime/API default changed')
    if 'tolerations' in actual:
        contract.require(actual.pop('tolerations') == [{'effect':'NoExecute','key':'node.kubernetes.io/'+key,
            'operator':'Exists','tolerationSeconds':300} for key in ('not-ready','unreachable')], 'Tolerations changed')
    contract.require(actual == expected, 'Whole Pod execution contract changed')
    for field in ('annotations','labels'):
        contract.require(contains_fragment(pod['metadata'].get(field,{}),template['metadata'][field]),
                         'Rendered Pod metadata changed')
    return {'name':cm_name,'uid':cm['metadata']['uid'],'resourceVersion':cm['metadata']['resourceVersion'],
            'ownerPodUid':pod['metadata']['uid'],'profileGiB':gib,'observedData':cm['data'],
            'livePackingQualified':False}


def validate_status(pod):
    status = pod['status']
    contract.require(status['phase'] == 'Succeeded', 'Pod did not succeed')
    digest = contract.IMAGE.split('@')[1]
    for field,spec_field in (('containerStatuses','containers'),('initContainerStatuses','initContainers')):
        records = unique_mapping(status[field],'name')
        contract.require(set(records) == {v['name'] for v in pod['spec'][spec_field]}, 'Executable image statuses missing')
        for record in records.values():
            image_id = record['imageID']
            contract.require(isinstance(image_id,str) and image_id.endswith('@'+digest) and
                image_id.removeprefix('docker-pullable://') == contract.IMAGE.split('@')[0].split(':qualification-')[0]+'@'+digest,
                'Actual executable imageID differs from the pinned registry manifest')
            contract.require(type(record.get('restartCount')) is int and record['restartCount'] == 0 and
                type(record['state']['terminated']['exitCode']) is int and record['state']['terminated']['exitCode'] == 0,
                             'Executable exit/restart receipt failed')


def valid_cache(cache):
    return (cache.get('uid'),cache.get('gid')) == (contract.UID,contract.GID) and cache.get('path') == CACHE_PATH and \
        cache.get('mappingVerified') is True and cache.get('noTmpFallback') is True and \
        all(type(cache.get(key)) is int and cache[key] > 0 for key in ('device','inode'))


def validate_value(value,role,pod_uid,run_id,gpu,cache,preflight):
    gib = contract.ROLES[role]; hami = value['hami']; quota = contract.QUOTAS[gib]
    contract.require(value['podUid'] == pod_uid and value['runId'] == run_id and value['role'] == role and
        value['profileGiB'] == gib and value['gpu'] == gpu and value['compiler'] == COMPILER and
        value['cache'] == cache and valid_cache(cache), 'Child identity/compiler/GPU/cache receipt changed')
    contract.require(type(value['pid']) is int and value['pid'] > 0, 'Actual child PID required')
    contract.require(hami['referenceSourceRevision'] == original.HAMI_REVISION and hami['sourceRevisionVerified'] is False and
        hami['libraryPath'] == original.HAMI_PATH and hami['sha256'] == preflight['hami']['sha256'] and
        hami['loaded'] is True and hami['preloadVerified'] is True and hami['perDeviceLimitVerified'] is True and
        hami['singleVisibleDeviceVerified'] is True and hami['effectiveLimitBytes'] == gib*1024**3 and
        hami['canonicalLimitBytes'] == gib*1024**3 and hami['schedulerInjectedLimitBytes'] == quota['globalMiB']*1024**2,
        'Observed preloaded HAMi bytes/effective per-device quota changed')


def validate_response(value,action,label,code,children):
    contract.require(value['event'] == 'response' and value['action'] == action and value['label'] == label and
        type(value['cudaResult']) is int and value['cudaResult'] == code and
        sum(value == v for v in children) == 1, 'Exact child operation receipt required')
    start,end = value['operationStartedNs'],value['operationFinishedNs']
    contract.require(type(start) is int and type(end) is int and 0 < start <= end, 'Actual CUDA operation interval required')
    if code == 0 and action in ('allocate','tick'):
        a,b = value['writeStartedNs'],value['writeFinishedNs']
        contract.require(type(a) is int and type(b) is int and start <= a <= b <= end and
            type(value['writeBytes']) is int and value['writeBytes'] > 0, 'Actual successful CUDA write interval required')
    if code != 0:
        contract.require(not any(k in value for k in ('writeBytes','writeStartedNs','writeFinishedNs')),
                         'Denied allocations cannot contain a successful write receipt')


def validate_ordinary(report,children):
    results = report['ordinary']; role = report['role']; mib = contract.ALLOCATIONS[contract.ROLES[role]]
    contract.require(set(results) == {'aHold','bDenied','aContinued','aFree','bAfterFree','bContinued','bFree'},
                     'Complete ordinary denial/progress/free/recovery receipts required')
    actions = {'aHold':'allocate','bDenied':'allocate','aContinued':'tick','aFree':'free',
               'bAfterFree':'allocate','bContinued':'tick','bFree':'free'}
    pids = {v['pid'] for v in report['children']}
    for key,value in results.items():
        validate_response(value,actions[key],'ordinary',2 if key == 'bDenied' else 0,children)
        contract.require(value['pid'] in pids, 'Ordinary receipt must belong to an initialized child')
        if actions[key] == 'allocate':
            contract.require(value['allocationMiB'] == mib and type(value['startMonotonicNs']) is int and
                type(value['endMonotonicNs']) is int and 0 < value['startMonotonicNs'] <= value['endMonotonicNs'],
                'Ordinary allocation size/actual interval changed')
            if value['cudaResult'] == 0:
                contract.require(value['writeBytes'] == mib*1024**2, 'Successful allocation must write its full payload')
        elif actions[key] == 'tick':
            contract.require(value['writeBytes'] == 1024**2, 'Ordinary continuation requires an actual MiB CUDA write')
    contract.require(len(pids) == 2 and results['aHold']['pid'] != results['bDenied']['pid'] and
        all(results[k]['pid'] == results['aHold']['pid'] for k in ('aContinued','aFree')) and
        all(results[k]['pid'] == results['bDenied']['pid'] for k in ('bAfterFree','bContinued','bFree')),
        'Ordinary recovery changed child identity')
    sequence = [results[k] for k in ('aHold','bDenied','aContinued','aFree','bAfterFree','bContinued','bFree')]
    contract.require(all(a['operationFinishedNs'] <= b['operationStartedNs'] for a,b in zip(sequence,sequence[1:])),
                     'Ordinary denial/progress/free/recovery order is unproven')
    contract.require(report['ordinaryPassed'] is True and report['ordinaryStartedNs'] <= sequence[0]['operationStartedNs'] and
        sequence[-1]['operationFinishedNs'] <= report['ordinaryFinishedNs'], 'Ordinary time window is unbound')


def validate_hold(report,children):
    hold = report['hold']; role = report['role']; sizes = contract.HOLD_ALLOCATIONS[contract.ROLES[role]]
    start,finish,target = hold['startedNs'],hold['finishedNs'],hold['startTargetNs']
    expected_target = int(contract.instant(report['approval']['mps']['observedAt']).timestamp()*1e9)+30*10**9
    contract.require(target == expected_target and target <= start <= target+2*10**9 and
        20*10**9 <= finish-start <= 25*10**9 and hold['durationSeconds'] == 20 and hold['payloadMiB'] == sum(sizes),
        'Common bounded full-payload hold timing changed')
    allocations,frees = hold['allocations'],hold['frees']
    contract.require(len(allocations) == len(frees) == len(sizes) and
        len({v['pid'] for v in allocations}) == len(sizes), 'Independent held child receipts required')
    for value,mib in zip(allocations,sizes):
        validate_response(value,'allocate','mixed-hold',0,children)
        contract.require(value['allocationMiB'] == mib and value['writeBytes'] == mib*1024**2 and
            value['operationFinishedNs'] <= start, 'Hold full-payload allocation/write receipt changed')
    pids = {v['pid'] for v in allocations}
    for value in frees:
        validate_response(value,'free','mixed-hold',0,children)
        contract.require(value['pid'] in pids and value['operationStartedNs'] >= finish, 'Hold freed before its observation window')
    ticks = hold['ticks']
    contract.require(len(ticks) == 40 and [t['tick'] for t in ticks] == list(range(40)), 'All40hold ticks required')
    times = [t['observedNs'] for t in ticks]
    contract.require(all(type(t) is int for t in times) and times == sorted(times) and
        start <= times[0] <= start+10**9 and finish-10**9 <= times[-1] <= finish and
        all(0 < b-a <= 10**9 for a,b in zip(times,times[1:])), 'Hold tick cadence is stale or incomplete')
    for tick in ticks:
        values = tick['values']
        contract.require(len(values) == len(sizes) and {v['pid'] for v in values} == pids,
                         'Every held child must make actual progress')
        for value in values:
            validate_response(value,'tick','mixed-hold',0,children)
            contract.require(value['writeBytes'] == 1024**2 and start <= value['operationStartedNs'] <=
                value['operationFinishedNs'] <= finish, 'Hold write interval is unbound')


def evaluate(events,pods,node,preflight,configmaps,*,fixture,compiler_wheel):
    result = {'status':'failed-or-inconclusive','reasons':[],'productionQualified':False,
        'hostileIsolationQualified':False,'mpsThreeClientQualified':False,'mixedPackingQualified':False,
        'schedulerQuotaCandidatesLiveQualified':False,'compilerSource':contract.SOURCE,'runtimeIdentity':{'uid':1000,'gid':100},
        'temporaryMpsMutationImplemented':False,'tamper':{'status':'not-run','existingFailureRemains':True}}
    try:
        contract.require(set(events) == set(pods) == set(contract.ROLES), 'Exactly three reviewed roles required')
        proof = json.loads(fixture['items'][0]['data']['preflight.json'])
        trusted = renderer.render(preflight,proof['runId'],compiler_wheel,now=contract.instant(preflight['observedAt']))
        contract.require(fixture == trusted, 'Original manifest/source/WHEEL/compiled plan differs from trusted regeneration')
        contract.require(node['metadata']['name'] == original.NODE and node['metadata']['uid'] == proof['nodeUid'],
                         'Actual node identity changed')
        ready = [c for c in node['status']['conditions'] if c['type'] == 'Ready']
        contract.require(len(ready) == 1 and ready[0]['status'] == 'True', 'Actual Node Ready condition missing')
        uids = [pods[role]['metadata']['uid'] for role in contract.ROLES]
        contract.require(len(set(uids)) == 3 and all(str(uuid.UUID(v)) == v for v in uids), 'Three distinct canonical Pod UIDs required')
        gpu = pods['peer5']['metadata']['annotations'][original.REVIEWED_GPU_ANNOTATION]
        contract.require(gpu in proof['gpuUuidAllowlist'], 'Actual selected physical GPU outside observed inventory')
        gpu_value = normalized_uuid(gpu); reports = {}; receipts = []; common_mps = None; caches = []
        for index,(role,gib) in enumerate(contract.ROLES.items(),1):
            pod = pods[role]; metadata = pod['metadata']; stream = events[role]
            contract.require(metadata['namespace'] == original.NAMESPACE and pod['spec']['nodeName'] == original.NODE and
                metadata['annotations'][original.REVIEWED_GPU_ANNOTATION] == gpu, 'All three Pods must be on the same reviewed GPU2 card')
            receipts.append(validate_executable_pod(pod,trusted['items'][index]['spec']['template'],configmaps,gib))
            validate_status(pod)
            contract.require(stream and all(e['podUid'] == metadata['uid'] and e['runId'] == proof['runId'] and
                e['role'] == role for e in stream), 'Log stream identity differs from observed Pod/run/role')
            gates = [e for e in stream if e['event'] == 'mixed-cpu-gate-released']
            reported = [e for e in stream if e['event'] == 'mixed-result']
            contract.require(len(gates) == len(reported) == 1, 'One bound CPU gate and one final report required')
            gate,report = gates[0],reported[0]; approval = gate['approval']
            contract.require(type(gate['observedNs']) is int, 'Actual gate release time required')
            contract.validate_approval(approval,proof,role,metadata['uid'],
                now=dt.datetime.fromtimestamp(gate['observedNs']/1e9,dt.timezone.utc))
            contract.require(set(approval['podUids']) == set(uids) and approval['gpuUuid'] == gpu and
                report['approval'] == approval, 'Gate report does not bind all actual reviewed Pods')
            if common_mps is None:common_mps = approval['mps']
            contract.require(approval['mps'] == common_mps, 'Three roles must use the same actual server readback/window')
            contract.require(report['compiler'] == COMPILER and report['profileGiB'] == gib and
                report['requestedMiB'] == gib*1024 and report['allocationMiB'] == contract.ALLOCATIONS[gib] and
                report['productionQualified'] is False and report['hostileIsolationQualified'] is False and
                report['mpsThreeClientQualified'] is False, 'Role report source/quota/qualification boundary changed')
            children = [e['value'] for e in stream if e['event'] == 'mixed-child-evidence']
            initialized = [v for v in children if v['event'] == 'ready']
            contract.require(len(initialized) == 2 and report['children'] == initialized and
                len({v['pid'] for v in initialized}) == 2, 'Both initialized child identities required')
            cache = initialized[0]['cache']; caches.append((cache['device'],cache['inode']))
            for value in children:
                validate_value(value,role,metadata['uid'],proof['runId'],gpu_value,cache,preflight)
                contract.require(value['pid'] in {v['pid'] for v in initialized}, 'Unknown child process receipt')
            validate_hold(report,children);validate_ordinary(report,children)
            contract.require(report['startedNs'] <= report['hold']['startedNs'] <= report['hold']['finishedNs'] <=
                report['ordinaryStartedNs'] <= report['ordinaryFinishedNs'] <= report['finishedNs'] and
                gate['observedNs'] <= report['startedNs'] and report['finishedNs'] < common_mps['windowEndsAtNs'] and
                report['status'] == 'bounded-mixed-role-passed', 'Bounded role timing/status failed')
            reports[role] = report
        contract.require(len(set(caches)) == 3, 'Each workspace must use its own independent cache inode')
        overlap = min(r['hold']['finishedNs'] for r in reports.values())-max(r['hold']['startedNs'] for r in reports.values())
        contract.require(overlap >= 18*10**9, 'All three full-payload holds must actually overlap')
        progress = reports['peer5']['peerProgress']; peer_children = [e['value'] for e in events['peer5'] if e['event'] == 'mixed-child-evidence']
        contract.require(len(progress) == 90 and [v['tick'] for v in progress] == list(range(90)), 'All45seconds of peer progress required')
        times = [v['observedNs'] for v in progress]
        contract.require(all(type(v) is int for v in times) and times == sorted(times) and
            all(0 < b-a <= 10**9 for a,b in zip(times,times[1:])), 'Independent peer progress is stale or interrupted')
        for record in progress:
            validate_response(record['value'],'tick','peer-heartbeat',0,peer_children)
            contract.require(record['value']['writeBytes'] == 1024**2, 'Peer must continue actual CUDA writes')
        for role in ('workspace10','workspace20'):
            contract.require(reports[role]['peerProgress'] == [] and times[0] <= reports[role]['ordinaryStartedNs'] and
                times[-1] >= reports[role]['ordinaryFinishedNs'], 'Independent peer did not cover workspace denial/recovery')
        result.update(status='bounded-mixed-candidate-cases-passed',boundedMixedCasesPassed=True,
            observedGpu=gpu,nodeUid=proof['nodeUid'],podUids=uids,schedulerQuotaReceipts=receipts,
            simultaneousPayloadMiB=proof['simultaneousPayloadMiB'],nominalBudgetMiB=proof['nominalBudgetMiB'])
    except (KeyError,TypeError,ValueError,OSError,IndexError) as error:
        result['reasons'].append(str(error));result['boundedMixedCasesPassed'] = False
    return result


def json_events(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip().startswith('{')]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('preflight','fixture','compiler-wheel','node','pods','configmaps','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    for role in contract.ROLES:parser.add_argument('--'+role+'-log',type=Path,required=True)
    args = parser.parse_args()
    result = evaluate({role:json_events(getattr(args,role+'_log')) for role in contract.ROLES},
        json.loads(args.pods.read_text()),json.loads(args.node.read_text()),json.loads(args.preflight.read_text()),
        json.loads(args.configmaps.read_text()),fixture=json.loads(args.fixture.read_text()),compiler_wheel=args.compiler_wheel)
    with args.output.open('x') as output:json.dump(result,output,indent=2);output.write('\n')
    print(json.dumps({'status':result['status'],'productionQualified':False,'mpsThreeClientQualified':False}))
    raise SystemExit(0 if result['boundedMixedCasesPassed'] else 1)
