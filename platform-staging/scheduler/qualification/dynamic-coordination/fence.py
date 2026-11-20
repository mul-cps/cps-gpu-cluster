"""QA-only, fail-closed AdmissionReview decisions over trusted frozen receipts.

No writes, watches, registry enrollment, or inference from workflow annotations.
Native immutable ConfigMaps and Binding.metadata.uid are mandatory prerequisites.
"""
import copy
import importlib.util
import json
from pathlib import Path
import re


def _adjacent(name):
    path = Path(__file__).resolve().parent.parent / 'dynamic-admission' / (name + '.py')
    spec = importlib.util.spec_from_file_location('coordination_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


quota_policy = _adjacent('quota_policy')
UID = re.compile(quota_policy.UID_PATTERN)
NAME = re.compile(quota_policy.DNS_PATTERN)
ACTOR = re.compile(quota_policy.ACTOR_PATTERN)
MAX_BYTES = 1024 * 1024


class Denied(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Denied(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def identity(obj, kind, namespace=None):
    require(isinstance(obj, dict) and obj.get('kind') == kind, 'Exact persisted object kind required')
    expected_api = 'argoproj.io/v1alpha1' if kind == 'Workflow' else 'v1'
    require(obj.get('apiVersion') == expected_api, 'Exact API version required')
    meta = obj['metadata']
    require(isinstance(meta.get('name'), str) and len(meta['name']) <= 253 and NAME.fullmatch(meta['name']), 'Canonical object name required')
    require(isinstance(meta.get('uid'), str) and UID.fullmatch(meta['uid']), 'Persisted exact UID required')
    require(isinstance(meta.get('resourceVersion'), str) and re.fullmatch(r'[1-9][0-9]{0,19}', meta['resourceVersion']), 'Persisted resourceVersion required')
    if namespace is not None:
        require(meta.get('namespace') == namespace, 'Owning namespace must match')
    return meta


def pod_shape(pod):
    spec = copy.deepcopy(pod['spec'])
    spec.pop('nodeName', None)
    meta = pod['metadata']
    return dict(spec=spec, ownerReferences=meta.get('ownerReferences'),
                annotations=meta.get('annotations', {}), labels=meta.get('labels', {}))


def node_shape(node):
    return dict(spec=node.get('spec', {}), labels=node['metadata'].get('labels', {}),
                annotations=node['metadata'].get('annotations', {}),
                allocatable=node.get('status', {}).get('allocatable', {}))


def injected_names(pod, workflow):
    """Derive the random KAI prefix from every actual main configMapKeyRef."""
    containers = pod['spec']['containers']
    indexes = [i for i, container in enumerate(containers) if container.get('name') == 'main']
    require(len(indexes) == 1 and indexes[0] in (0, 1), 'One actual indexed main container required')
    index = indexes[0]
    main = containers[index]
    names = []
    for key in ('NVIDIA_VISIBLE_DEVICES', 'RUNAI_NUM_OF_GPUS', 'GPU_PORTION', 'CUDA_DEVICE_MEMORY_LIMIT'):
        values = [env for env in main.get('env', []) if env.get('name') == key]
        require(len(values) == 1 and 'value' not in values[0], 'Exact injected quota environment required')
        ref = values[0]['valueFrom']['configMapKeyRef']
        require(set(ref) <= {'name', 'key', 'optional'} and ref['key'] == key, 'Exact KAI key reference required')
        require(ref.get('optional', False) is (key == 'CUDA_DEVICE_MEMORY_LIMIT'), 'Exact optional quota reference required')
        names.append(ref['name'])
    require(len(set(names)) == 1, 'All KAI capability references must agree')
    cap = names[0]
    suffix = '-' + str(index)
    require(cap.endswith(suffix), 'Actual capability name must retain container index')
    prefix = cap[:-len(suffix)]
    base = workflow['metadata']['name'][:33].rstrip('.-')
    require(re.fullmatch(re.escape(base) + r'-[bcdfghjklmnpqrstvwxz2456789]{7}-shared-gpu', prefix), 'Observed random prefix must match pinned KAI naming rule')
    require(main.get('envFrom') == [{'configMapRef': {'name': cap + '-evar', 'optional': False}}], 'Exact empty evar reference required')
    volumes = [v for v in pod['spec'].get('volumes', []) if v.get('configMap', {}).get('name') == cap]
    volume_name = re.sub('[^a-z0-9-]+', '-', cap.lower() + '-vol').strip('-')
    require(len(volumes) == 1 and volumes[0]['name'] == volume_name, 'Actual KAI capability volume required')
    # Annotation equality is corroboration only: it never selects either map.
    require(pod['metadata'].get('annotations', {}).get('runai/shared-gpu-configmap') == prefix, 'Injected annotation disagrees with actual references')
    return cap, cap + '-evar'


def quota_records(record, namespace):
    pod, workflow = record['pod'], record['workflow']
    cap, evar = injected_names(pod, workflow)
    require(len(record['configMaps']) == 2, 'Both complete map receipts required')
    maps = {cm['metadata']['name']: cm for cm in record['configMaps']}
    require(set(maps) == {cap, evar}, 'Complete exact capabilities and evar pair required')
    budget = pod['metadata'].get('annotations', {}).get('gpu-memory')
    require(budget in ('5120', '10240', '20480'), 'One disabled fixed-profile candidate required')
    require(set(record['device']) == {'gpuUuid', 'visibleDevices', 'physicalGpuMemoryMiB', 'gpuPortion', 'runaiNumOfGpus', 'cudaDeviceMemoryLimit'}, 'Complete independently reviewed physical device inventory required')
    require(record['node']['metadata'].get('labels', {}).get('nvidia.com/gpu.memory') == record['device']['physicalGpuMemoryMiB'], 'Reviewed Node memory label must agree')
    inventory = record['nodeInventory']
    require(set(inventory) == {'nodeName', 'nodeUid', 'nodeResourceVersion', 'evidenceSha256', 'devices'}, 'Complete independently reviewed Node inventory receipt required')
    node_meta = record['node']['metadata']
    require(all(inventory[k] == node_meta[v] for k, v in {'nodeName': 'name', 'nodeUid': 'uid', 'nodeResourceVersion': 'resourceVersion'}.items()), 'Inventory must pin the same Node generation')
    require(isinstance(inventory['evidenceSha256'], str) and re.fullmatch('[0-9a-f]{64}', inventory['evidenceSha256']), 'Reviewed inventory evidence digest required')
    count = int(record['node']['status']['allocatable']['nvidia.com/gpu'])
    devices = inventory['devices']
    require(isinstance(devices, list) and 1 <= count <= 32 and len(devices) == count, 'Full fixed Node device inventory required')
    require(all(set(d) == {'index', 'gpuUuid', 'physicalGpuMemoryMiB'} and type(d['index']) is int and 0 <= d['index'] < count and isinstance(d['gpuUuid'], str) and re.fullmatch(quota_policy.GPU_PATTERN, d['gpuUuid']) and d['physicalGpuMemoryMiB'] == record['device']['physicalGpuMemoryMiB'] for d in devices), 'Canonical complete Node device entries required')
    require(len({d['index'] for d in devices}) == count and len({d['gpuUuid'] for d in devices}) == count, 'Node device indexes and UUIDs must be unique')
    selector = record['device']['visibleDevices']
    selected = selector[len(quota_policy.CDI_PREFIX):] if selector.startswith(quota_policy.CDI_PREFIX) else selector
    matches = [d for d in devices if str(d['index']) == selected or d['gpuUuid'] == selected]
    require(len(matches) == 1 and matches[0]['gpuUuid'] == record['device']['gpuUuid'], 'Selected device must match the independently reviewed Node inventory; never infer UUID from CDI syntax')
    require(int(record['device']['cudaDeviceMemoryLimit'][:-1]) >= int(budget), 'Reviewed KAI limit must cover nominal indexed budget')
    rows = []
    for name, kind in ((cap, 'capabilities'), (evar, 'evar')):
        cm = maps[name]
        meta = identity(cm, 'ConfigMap', namespace)
        owner = [{'apiVersion': 'v1', 'kind': 'Pod', 'name': pod['metadata']['name'], 'uid': pod['metadata']['uid']}]
        refs = meta.get('ownerReferences')
        require(isinstance(refs, list) and len(refs) == 1 and set(refs[0]) <= {'apiVersion', 'kind', 'name', 'uid', 'controller', 'blockOwnerDeletion'}, 'One exact non-controller Pod owner required')
        require(all(refs[0].get(k) == v for k, v in owner[0].items()) and refs[0].get('controller', False) is False and refs[0].get('blockOwnerDeletion', False) is False, 'Exact original Pod owner required')
        require('binaryData' not in cm and cm.get('immutable', False) in (False, True) and type(cm.get('immutable', False)) is bool, 'Only explicit native immutability is modeled')
        device = record['device']
        expected = {} if kind == 'evar' else dict(NVIDIA_VISIBLE_DEVICES=device['visibleDevices'], GPU_PORTION=device['gpuPortion'], RUNAI_NUM_OF_GPUS=device['runaiNumOfGpus'], CUDA_DEVICE_MEMORY_LIMIT=device['cudaDeviceMemoryLimit'])
        require(cm.get('data', {}) == expected, 'Complete current quota/evar data required')
        require(not meta.get('deletionTimestamp'), 'Deleting map cannot qualify')
        rows.append(dict(namespace=namespace, name=name, type=kind, podName=pod['metadata']['name'], podUid=pod['metadata']['uid'], cmUid=meta['uid'], **device))
    require(len({cm['metadata']['uid'] for cm in maps.values()} | {pod['metadata']['uid']}) == 3, 'Distinct map and Pod generations required')
    return quota_policy.reviewed_records(namespace, rows)


def validate_record(record, namespace):
    require(isinstance(record, dict) and set(record) == {'pod', 'workflow', 'node', 'nodeInventory', 'configMaps', 'device'}, 'Exact reviewed snapshot fields required')
    pod = identity(record['pod'], 'Pod', namespace)
    parent = identity(record['workflow'], 'Workflow', namespace)
    identity(record['node'], 'Node')
    refs = pod.get('ownerReferences', [])
    require(len(refs) == 1 and set(refs[0]) <= {'apiVersion', 'kind', 'name', 'uid', 'controller', 'blockOwnerDeletion'}, 'Exactly one reviewed Workflow owner required')
    require(all(refs[0].get(k) == v for k, v in dict(apiVersion='argoproj.io/v1alpha1', kind='Workflow', name=parent['name'], uid=parent['uid']).items()), 'Actual parent Workflow UID required')
    require(not pod.get('deletionTimestamp') and not parent.get('deletionTimestamp') and not record['node']['metadata'].get('deletionTimestamp'), 'No deleting generation may enroll')
    require(record['pod']['spec'].get('nodeName', record['node']['metadata']['name']) == record['node']['metadata']['name'], 'Wrong actual target Node')
    quota_records(record, namespace)
    return record


def validate_registry(registry):
    require(isinstance(registry, dict) and set(registry) == {'schemaVersion', 'namespace', 'bindingWriters', 'cleanupWriters', 'sealWriter', 'records'}, 'Exact protected registry schema required')
    require(registry['schemaVersion'] == 1 and type(registry['schemaVersion']) is int, 'Registry version required')
    ns = registry['namespace']
    require(isinstance(ns, str) and len(ns) <= 63 and re.fullmatch(quota_policy.NAMESPACE_PATTERN, ns), 'Separate fixed QA namespace required')
    require(len(canonical(registry)) <= MAX_BYTES, 'Bounded protected registry required')
    for field in ('bindingWriters', 'cleanupWriters'):
        actors = registry[field]
        require(isinstance(actors, list) and len(actors) <= 8 and len(set(actors)) == len(actors), 'Bounded distinct authenticated actors required')
        require(all(isinstance(a, str) and len(a) <= 343 and ACTOR.fullmatch(a) for a in actors), 'Reviewed service-account identity required')
    require(isinstance(registry['sealWriter'], str) and len(registry['sealWriter']) <= 343 and ACTOR.fullmatch(registry['sealWriter']), 'One reviewed coordinator identity required')
    require(isinstance(registry['records'], list) and len(registry['records']) <= 32, 'Bounded manual registry required')
    seen_pods, seen_maps, nodes = set(), set(), {}
    for record in registry['records']:
        validate_record(record, ns)
        pod = record['pod']['metadata']
        require(pod['name'] not in seen_pods, 'Duplicate reviewed Pod name')
        seen_pods.add(pod['name'])
        for cm in record['configMaps']:
            require(cm['metadata']['name'] not in seen_maps, 'Duplicate reviewed quota map')
            seen_maps.add(cm['metadata']['name'])
        node = record['node']
        key = node['metadata']['name']
        require(key not in nodes or nodes[key] == node, 'One fixed Node generation per window')
        nodes[key] = node
    return registry


def observed(read, resource, namespace, expected, *, exact_version=False):
    obj = read(resource, namespace, expected['metadata']['name'])
    meta = identity(obj, expected['kind'], namespace if namespace else None)
    require(meta['name'] == expected['metadata']['name'] and meta['uid'] == expected['metadata']['uid'], 'Missing or recreated object generation')
    require(not meta.get('deletionTimestamp'), 'Terminating object is still present and cannot bind')
    if exact_version:
        require(meta['resourceVersion'] == expected['metadata']['resourceVersion'], 'Stale generation receipt')
    return obj


def check_map(actual, expected, namespace, *, sealed):
    meta = identity(actual, 'ConfigMap', namespace)
    require(all(meta.get(k) == expected['metadata'][k] for k in ('name', 'uid', 'resourceVersion', 'ownerReferences')), 'Exact pinned map generation and owner required')
    require(actual.get('data', {}) == expected.get('data', {}) and 'binaryData' not in actual, 'Exact complete map data required')
    require(not meta.get('deletionTimestamp'), 'Deleting map cannot qualify')
    require(actual.get('immutable', False) is (True if sealed else expected.get('immutable', False)), 'Both maps must be natively sealed before binding')


def check_live_record(record, namespace, read, *, sealed, allow_sealed_siblings=False):
    pod = observed(read, 'pods', namespace, record['pod'])
    require(pod_shape(pod) == pod_shape(record['pod']) and pod['spec'].get('nodeName', record['node']['metadata']['name']) == record['node']['metadata']['name'], 'Actual final injected Pod contract changed')
    parent = observed(read, 'workflows', namespace, record['workflow'])
    require(parent['spec'] == record['workflow']['spec'], 'Reviewed parent Workflow changed')
    node = observed(read, 'nodes', '', record['node'], exact_version=True)
    require(node_shape(node) == node_shape(record['node']), 'Reviewed Node inventory changed')
    require(injected_names(pod, parent) == injected_names(record['pod'], record['workflow']), 'Actual injected prefix changed')
    for expected in record['configMaps']:
        actual = observed(read, 'configmaps', namespace, expected, exact_version=not allow_sealed_siblings)
        comparison = expected
        if allow_sealed_siblings and actual.get('immutable') is True:
            # The first seal changes RV. The second seal may observe that native
            # immutable sibling, but its UID, complete data and owner stay pinned.
            comparison = copy.deepcopy(expected)
            comparison['metadata']['resourceVersion'] = actual['metadata']['resourceVersion']
            check_map(actual, comparison, namespace, sealed=True)
        else:
            check_map(actual, comparison, namespace, sealed=sealed)
    # Narrow the independent-read race; these reads are not a transaction.
    pod_again = observed(read, 'pods', namespace, record['pod'])
    require(pod_shape(pod_again) == pod_shape(record['pod']), 'Final Pod generation changed')
    observed(read, 'nodes', '', record['node'], exact_version=True)
    parent_again = observed(read, 'workflows', namespace, record['workflow'])
    require(parent_again['spec'] == record['workflow']['spec'], 'Final parent generation changed')
    return pod_again


def _authorize(request, registry, read):
    resource = request['resource']
    require(resource.get('group', '') == '' and resource.get('version') == 'v1', 'Exact core v1 request required')
    kind = resource['resource']
    if kind == 'nodes':
        expected = [r['node'] for r in registry['records'] if r['node']['metadata']['name'] == request['name']]
        require(expected and request.get('namespace', '') == '', 'Only explicitly fixed QA Nodes are modeled')
        require(request['operation'] == 'UPDATE' and request.get('subResource', '') in ('', 'status'), 'Node generation is frozen for whole QA window')
        old, new = request['oldObject'], request['object']
        require(old['metadata']['uid'] == new['metadata']['uid'] == expected[0]['metadata']['uid'] and not new['metadata'].get('deletionTimestamp'), 'Node UID and presence are frozen')
        require(node_shape(old) == node_shape(new) == node_shape(expected[0]), 'Relevant Node inventory/spec edits are frozen')
        return
    namespace = registry['namespace']
    require(request.get('namespace') == namespace, 'Exact isolated namespace required')
    actor = request['userInfo']['username']
    if kind == 'pods':
        require(request['operation'] == 'CREATE' and request.get('subResource') == 'binding' and actor in registry['bindingWriters'], 'Only explicitly reviewed binding writers may bind')
        obj = request['object']
        require(obj.get('apiVersion') == 'v1' and obj.get('kind') == 'Binding', 'Exact Binding required')
        matches = [r for r in registry['records'] if r['pod']['metadata']['name'] == request['name']]
        require(len(matches) == 1, 'One exact reviewed final Pod required')
        record = matches[0]
        require(obj['metadata'].get('namespace') == namespace and obj['metadata'].get('name') == request['name'] and obj['metadata'].get('uid') == record['pod']['metadata']['uid'], 'Binding must include actual Pod UID precondition')
        require(not obj['metadata'].get('annotations') and not obj['metadata'].get('labels'), 'Binding cannot merge annotations or labels into the reviewed Pod')
        target = obj['target']
        require(set(target) <= {'kind', 'name', 'apiVersion'} and target.get('kind') == 'Node' and target.get('apiVersion', 'v1') == 'v1' and target.get('name') == record['node']['metadata']['name'], 'Exact reviewed target Node required')
        require(all(cm.get('immutable') is True for cm in record['configMaps']), 'Both sealed receipts must be manually enrolled before binding')
        current = check_live_record(record, namespace, read, sealed=True)
        require(obj['metadata'].get('resourceVersion') == current['metadata']['resourceVersion'], 'Binding must include current final Pod resourceVersion precondition')
        return
    require(kind == 'configmaps' and not request.get('subResource'), 'Only quota map mutations or binding are modeled')
    matches = [(r, cm) for r in registry['records'] for cm in r['configMaps'] if cm['metadata']['name'] == request['name']]
    require(len(matches) == 1, 'No unregistered or recreated quota maps')
    record, expected = matches[0]
    require(request['operation'] in ('UPDATE', 'DELETE'), 'Pinned names may never be recreated')
    old = request['oldObject']
    check_map(old, expected, namespace, sealed=expected.get('immutable', False))
    if request['operation'] == 'UPDATE':
        require(actor == registry['sealWriter'] and expected.get('immutable', False) is False, 'Only trusted coordinator may seal once')
        new = request['object']
        check_map(new, expected, namespace, sealed=True)
        old_rest, new_rest = copy.deepcopy(old), copy.deepcopy(new)
        old_rest.pop('immutable', None); new_rest.pop('immutable', None)
        require(old_rest == new_rest, 'Sealing cannot change any data, owner, or metadata')
        check_live_record(record, namespace, read, sealed=False, allow_sealed_siblings=True)
        return
    require(actor in registry['cleanupWriters'], 'Explicit cleanup actor required')
    preconditions = request['options']['preconditions']
    require(all(preconditions.get(k) == expected['metadata'][k] for k in ('uid', 'resourceVersion')), 'Cleanup requires UID and resourceVersion preconditions')
    actual = read('configmaps', namespace, expected['metadata']['name'])
    check_map(actual, expected, namespace, sealed=expected.get('immutable', False))
    pod = read('pods', namespace, record['pod']['metadata']['name'])
    # A named replacement does not resurrect the old immutable UID generation.
    if pod is not None:
        identity(pod, 'Pod', namespace)
        require(pod['metadata']['name'] == record['pod']['metadata']['name'], 'Unexpected Pod API response')
        require(pod['metadata']['uid'] != record['pod']['metadata']['uid'], 'Original Pod UID exists, including terminating')


def authorize(review, registry, read):
    """Pure decision function; injected read may return None only for confirmed 404."""
    request = review.get('request') if isinstance(review, dict) else None
    response = {'apiVersion': 'admission.k8s.io/v1', 'kind': 'AdmissionReview',
                'response': {'uid': request.get('uid', '') if isinstance(request, dict) else '', 'allowed': False}}
    try:
        require(isinstance(review, dict) and isinstance(request, dict), 'AdmissionReview request object required')
        require(review.get('apiVersion') == 'admission.k8s.io/v1' and review.get('kind') == 'AdmissionReview', 'AdmissionReview v1 required')
        uid = review['request']['uid']
        require(isinstance(uid, str) and 0 < len(uid) <= 128 and len(canonical(review)) <= MAX_BYTES, 'Bounded request UID and body required')
        validate_registry(registry)
        _authorize(review['request'], registry, read)
        response['response']['allowed'] = True
    except Exception as error:
        reason = str(error) if isinstance(error, Denied) else 'Missing, invalid, stale identity or API lookup failure'
        response['response']['status'] = {'code': 403, 'message': reason}
    return response
