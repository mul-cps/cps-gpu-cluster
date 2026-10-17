"""Pure, two-phase Gateway/Hub/packaged-Node image adoption intent.

Inputs and returned plans contain private Secret data. Callers must retain them
privately. No capture, filesystem writes, API clients, CLI, readiness or hardware
qualification occurs here. Root owns maintenance, actual creates and readbacks.
"""
import base64
import copy
import hashlib
import json
import re
from types import SimpleNamespace
import uuid

COMPONENTS = ('gateway', 'hub:cps', 'hub:cit', 'node')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def sha(value):
    return 'sha256:' + hashlib.sha256(canonical(value).encode()).hexdigest()


def _parse(value):
    from cps_compute.native_group_capture_protocol import json_document
    return json_document(value.encode())


def _decode(value):
    require(isinstance(value, str), 'Base64 text data required')
    try:
        return _parse(base64.b64decode(value, validate=True).decode())
    except (ValueError, UnicodeError):
        raise ValueError('Valid base64 JSON required') from None


def _encoded(value):
    return base64.b64encode(canonical(value).encode()).decode()


def _guard(obj, kind):
    api = 'apps/v1' if kind == 'Deployment' else 'rbac.authorization.k8s.io/v1' if kind == 'Role' else 'v1'
    require(isinstance(obj, dict) and obj.get('kind') == kind and obj.get('apiVersion') == api,
            'Exact captured resource kind/version required')
    meta = obj.get('metadata', {})
    try:
        valid_uid = isinstance(meta.get('uid'), str) and str(uuid.UUID(meta['uid'])) == meta['uid']
    except ValueError:
        valid_uid = False
    require(valid_uid and isinstance(meta.get('resourceVersion'), str)
        and re.fullmatch('[1-9][0-9]*', meta['resourceVersion']) and meta.get('namespace')
        and meta.get('name') and not meta.get('deletionTimestamp'), 'Actual named UID/RV resource required')
    return meta


def _key(kind, namespace, name):
    return kind.lower() + '/' + namespace + '/' + name


def _get(snapshot, kind, namespace, name):
    obj = snapshot['objects'][_key(kind, namespace, name)]
    meta = _guard(obj, kind)
    require((meta['namespace'], meta['name']) == (namespace, name), 'Captured lookup identity differs')
    return obj


def _one(values, name):
    rows = [value for value in values if value.get('name') == name]
    require(len(rows) == 1, 'One exact named container/volume required')
    return rows[0]


def _volume(snapshot, component, name):
    return _one(snapshot['deployments'][component]['spec']['template']['spec']['volumes'], name)


def volume(snapshot, component, name):
    dep = snapshot['deployments'][component]
    return _get(snapshot, 'ConfigMap', dep['metadata']['namespace'], _volume(snapshot, component, name)['configMap']['name'])


def secret_volume(snapshot, component, name):
    dep = snapshot['deployments'][component]
    return _get(snapshot, 'Secret', dep['metadata']['namespace'], _volume(snapshot, component, name)['secret']['secretName'])


def _immutable(obj):
    require(obj.get('immutable') is True and isinstance(obj.get('data'), dict)
        and not obj.get('binaryData') and not obj['metadata'].get('ownerReferences'),
        'Actual immutable ownerless text authority required')
    return obj


def _candidate(old, prefix, data, *, immutable=True):
    meta = old['metadata']
    result = {'apiVersion': 'v1', 'kind': old['kind'],
        'metadata': {'namespace': meta['namespace'], 'name': prefix + '-' + sha(data)[7:23]}, 'data': data}
    if immutable:
        result['immutable'] = True
    if old['kind'] == 'Secret':
        result['type'] = old['type']
    return result


def _stage(snapshot, plan, label, old, candidate):
    # Reuse the actual immutable UID when an unchanged peer or a previously
    # staged content-addressed object already exists; never CREATE AlreadyExists.
    if old.get('data') == candidate['data'] and old.get('immutable') is True:
        existing = old
    else:
        meta = candidate['metadata']
        existing = (_get(snapshot, candidate['kind'], meta['namespace'], meta['name'])
            if _key(candidate['kind'], meta['namespace'], meta['name']) in snapshot['objects'] else None)
    if existing is not None:
        _guard(existing, candidate['kind']); _immutable(existing)
        require(existing['data'] == candidate['data'] and existing.get('type') == candidate.get('type'),
                'Content-addressed resource collision')
        plan['reuses'][label] = copy.deepcopy(existing)
        return existing
    plan['creates'][label] = candidate
    return candidate


def _patch(obj, path, desired):
    old = obj
    for part in path.strip('/').split('/'):
        old = old[part]
    meta = _guard(obj, obj['kind'])
    return {'target': {'kind': obj['kind'], 'namespace': meta['namespace'], 'name': meta['name']}, 'patch': [
        {'op': 'test', 'path': '/metadata/uid', 'value': meta['uid']},
        {'op': 'test', 'path': '/metadata/resourceVersion', 'value': meta['resourceVersion']},
        {'op': 'test', 'path': path, 'value': copy.deepcopy(old)},
        {'op': 'replace', 'path': path, 'value': desired}]}


def _node_initializer_image(pod, old_image, new_image=None):
    initializer = _one(pod['initContainers'], 'packaged-bootstrap')
    env = _one(initializer.get('env', []), 'NODE_IMAGE')
    require(initializer['image'] == old_image and set(env) == {'name', 'value'}
        and env['value'] == old_image, 'Exact packaged-bootstrap NODE_IMAGE literal required')
    if new_image is not None:
        initializer['image'] = new_image
        env['value'] = new_image


def _role(snapshot, component, names, previous_name):
    ns = snapshot['deployments'][component]['metadata']['namespace']
    name = 'cps-native-approval-gateway' if component == 'gateway' else 'cps-native-approval-node' if component == 'node' else 'cps-native-approval-hub-' + component.split(':')[1]
    role = _get(snapshot, 'Role', ns, name)
    rules = copy.deepcopy(role['rules'])
    rows = [row for row in rules if row.get('apiGroups') == [''] and row.get('resources') == ['configmaps']
            and row.get('verbs') == ['get'] and isinstance(row.get('resourceNames'), list)
            and previous_name in row['resourceNames']]
    require(len(rows) == 1 and all(isinstance(v, str) for v in rows[0]['resourceNames']), 'One named ConfigMap GET rule for the existing authority required')
    rows[0]['resourceNames'] = sorted(set(rows[0]['resourceNames']) | set(names))
    return _patch(role, '/rules', rules)


def _context(snapshot):
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    from cps_compute.native_node.config import NodeConfiguration
    from cps_compute.policy import Policy
    bootstrap = volume(snapshot, 'node', 'packaged-bootstrap-input')
    require(set(bootstrap['data']) == {'config-ref.json', 'policy.json', 'release'}
        and bootstrap['data']['release'] in ('true', 'false'), 'Known packaged bootstrap inputs required')
    policy_cm = volume(snapshot, 'gateway', 'policy')
    require(len(policy_cm['data']) == 1, 'One current policy document required')
    policy = Policy(_parse(next(iter(policy_cm['data'].values()))))
    require(_parse(bootstrap['data']['policy.json']) == policy.catalog, 'Node bootstrap policy differs')
    reference = ImmutableConfigMapRef.from_dict(_parse(bootstrap['data']['config-ref.json']))
    core = SimpleNamespace(read_namespaced_config_map=lambda name, namespace:
        copy.deepcopy(_get(snapshot, 'ConfigMap', namespace, name)))
    configuration = NodeConfiguration.load(core, reference, policy)
    require(configuration is not None, 'Enabled packaged v3 Node required')
    return policy, configuration


def render(snapshot, images, *, expected_snapshot_sha256, expected_revision):
    """Return private create intents and guarded patches; never fabricate API IDs."""
    try:
        return _render(snapshot, images, expected_snapshot_sha256, expected_revision)
    except (KeyError, TypeError, StopIteration, AttributeError):
        raise ValueError('Incomplete coordinated adoption snapshot') from None


def _render(snapshot, images, expected_snapshot_sha256, expected_revision):
    from cps_compute.native_group_revision import ApprovalRevision
    require(isinstance(snapshot, dict) and snapshot.get('version') == 1
        and set(snapshot['deployments']) == set(COMPONENTS) and sha(snapshot) == expected_snapshot_sha256,
        'Exact explicitly pinned four-component snapshot required')
    require(isinstance(images, dict) and set(images) == set(COMPONENTS), 'Closed four-component image map required')
    for component, image in images.items():
        repo = 'cps-native-node' if component == 'node' else 'cps-compute'
        require(isinstance(image, str) and re.fullmatch('ghcr.io/mul-cps/' + repo + '@sha256:[a-f0-9]{64}', image),
                'Qualified immutable component repository image required')
    policy, configuration = _context(snapshot)
    node_body = configuration.document
    node_ref = configuration.reference.to_dict()
    old_node = _get(snapshot, 'ConfigMap', node_ref['namespace'], node_ref['name'])
    runtime_secret = secret_volume(snapshot, 'gateway', 'config')
    require(runtime_secret.get('type') == 'Opaque' and runtime_secret.get('immutable') is not True,
            'Actual mutable Opaque Gateway runtime Secret required')
    runtime = _decode(runtime_secret['data']['runtime.json'])
    approvals = runtime['nativeGroupApprovals']
    require(runtime['policy_hash'] == policy.hash and approvals['enabled'] is True
        and set(approvals['processes']) == set(COMPONENTS)
        and approvals['acknowledgments'] == node_body['acknowledgment_targets']
        and type(approvals['ttlSeconds']) is int and 15 <= approvals['ttlSeconds'] <= 120, 'Current runtime approval authority differs')
    pool = configuration.deployment.node_pool
    epoch = {k: pool[k] for k in ('node_uid', 'boot_id', 'driver_generation', 'gpu_uuid')}
    require(approvals['driver_epoch'] == epoch, 'Qualified driver epoch differs')
    documents = {}
    for component in COMPONENTS:
        dep = snapshot['deployments'][component]; meta = _guard(dep, 'Deployment')
        require(_get(snapshot, 'Deployment', meta['namespace'], meta['name']) == dep, 'Duplicate captured Deployment differs')
        declaration = node_body['component_declarations'][component]
        process = {k: v for k, v in declaration.items() if k != 'service_account_uid'}
        require(process == approvals['processes'][component], 'Runtime and Node process declarations differ')
        pod = dep['spec']['template']['spec']; selected = _one(pod['containers'], process['container'])
        require(all(process[k] == meta[k] for k in ('namespace', 'name', 'uid'))
            and process['kind'] == 'Deployment' and process['image'] == selected['image']
            and pod['serviceAccountName'] == process['service_account'], 'Actual controller/process declaration drift')
        account = _get(snapshot, 'ServiceAccount', meta['namespace'], process['service_account'])
        require(account['metadata']['uid'] == declaration['service_account_uid'], 'Signed ServiceAccount UID drift')
        actual = _immutable(volume(snapshot, component, 'cps-native-approval-document'))
        document = ApprovalRevision.from_configmap(actual, policy, configuration.deployment)
        require(document.reference['revision'] == expected_revision, 'Explicit current approval revision differs')
        documents[component] = document
        if component != 'node':
            refcm = _immutable(volume(snapshot, component, 'cps-native-approval-reference'))
            require(set(refcm['data']) == {'reference.json'} and _parse(refcm['data']['reference.json']) == document.reference,
                    'Actual approval reference projection differs')
    require(all(d.document == documents['node'].document for d in documents.values())
        and documents['node'].reference == node_body['approval_ref'], 'All four exact approval heads must agree')
    node_dep = snapshot['deployments']['node']; node_pod = node_dep['spec']['template']['spec']
    require(node_dep['spec']['strategy']['type'] == 'Recreate'
        and _one(node_pod['containers'], node_body['component_declarations']['node']['container'])['command']
            == ['python', '-m', 'cps_compute.native_node.service']
        and _one(node_pod['initContainers'], 'packaged-bootstrap')['image'] == approvals['processes']['node']['image'],
        'Unchanged single-writer packaged service/initializer required')
    _node_initializer_image(node_pod, approvals['processes']['node']['image'])
    ledger = _get(snapshot, 'ConfigMap', configuration.deployment.authority_namespace, 'cps-native-gpu-allocations')
    ledger_body = _parse(ledger['data']['state.json'])
    require(ledger_body['version'] == 1 and isinstance(ledger_body['allocations'], dict)
        and all(row.get('state') == 'released' for row in ledger_body['allocations'].values()),
        'Quiescent released-only captured ledger required; Root must freshly fence actual writers')
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    terminal_ref = ImmutableConfigMapRef.from_dict(node_body['terminal_index_ref'])
    terminal = terminal_ref.validate(_get(snapshot, 'ConfigMap', terminal_ref.to_dict()['namespace'], terminal_ref.to_dict()['name']))
    plan = {'version': 1, 'kind': 'current-group-kai-image-adoption', 'snapshot_sha256': expected_snapshot_sha256,
        'expected_revision': expected_revision, 'images': copy.deepcopy(images), 'creates': {}, 'reuses': {}, 'patches': {},
        'node_binding_required': True, 'live_applied': False, 'hardware_qualified': False}
    updated = copy.deepcopy(runtime); updated_node = copy.deepcopy(node_body)
    for component in COMPONENTS:
        updated['nativeGroupApprovals']['processes'][component]['image'] = images[component]
        updated_node['component_declarations'][component]['image'] = images[component]
    node_candidate = _candidate(old_node, 'cps-packaged-node-config-v3', {'config.json': canonical(updated_node)})
    node_candidate = _stage(snapshot, plan, 'node-config', old_node, node_candidate)
    plan['patches']['node.role'] = _role(snapshot, 'node', [node_candidate['metadata']['name']], old_node['metadata']['name'])
    seed = _immutable(secret_volume(snapshot, 'gateway', 'capture-seed'))
    require(seed.get('type') == 'Opaque', 'Opaque immutable capture seed required')
    capture = _decode(seed['data']['config.json'])
    require(capture['node_process'] == approvals['processes']['node']
        and capture['node_acknowledgment'] == approvals['acknowledgments']['node'], 'Capture Node declaration/acknowledgment drift')
    capture['node_process']['image'] = images['node']
    seed_data = copy.deepcopy(seed['data']); seed_data['config.json'] = _encoded(capture)
    seed_candidate = _stage(snapshot, plan, 'gateway.capture-seed', seed,
                            _candidate(seed, 'cps-native-capture-seed', seed_data))
    for component in COMPONENTS[:-1]:
        dep = snapshot['deployments'][component]
        publisher = _immutable(volume(snapshot, component, 'cps-native-approval-publisher'))
        require(set(publisher['data']) == {'publisher.json'}, 'One actual publisher document required')
        body = _parse(publisher['data']['publisher.json'])
        require(set(body) == {'version', 'component', 'process', 'acknowledgment', 'driver_epoch', 'ttlSeconds'}
            and type(body['version']) is int and body['version'] == 1
            and body['component'] == component and body['process'] == approvals['processes'][component]
            and body['acknowledgment'] == approvals['acknowledgments'][component]
            and body['driver_epoch'] == epoch and type(body['ttlSeconds']) is int and 15 <= body['ttlSeconds'] <= 120,
            'Actual publisher process, epoch, bounded TTL or target differs')
        # Publisher cadence and reader freshness windows are independently
        # bounded by the SDK; real Hub publisher TTLs need not equal Gateway
        # reader TTL. Preserve each captured value exactly.
        body['process']['image'] = images[component]
        candidate = _stage(snapshot, plan, component + '.publisher', publisher,
                            _candidate(publisher, 'cps-native-approval-publisher', {'publisher.json': canonical(body)}))
        template = copy.deepcopy(dep['spec']['template']); pod = template['spec']
        _one(pod['containers'], approvals['processes'][component]['container'])['image'] = images[component]
        if component == 'gateway':
            for section, name in (('containers', 'approval-capture'), ('initContainers', 'capture-private-inputs')):
                container = _one(pod[section], name)
                require(container['image'] == approvals['processes'][component]['image'], 'Gateway capture/helper image drift')
                container['image'] = images[component]
            _one(pod['volumes'], 'capture-seed')['secret']['secretName'] = seed_candidate['metadata']['name']
        _one(pod['volumes'], 'cps-native-approval-publisher')['configMap']['name'] = candidate['metadata']['name']
        plan['patches'][component + '.deployment'] = _patch(dep, '/spec/template', template)
        plan['patches'][component + '.role'] = _role(snapshot, component, [candidate['metadata']['name']], publisher['metadata']['name'])
    runtime_data = copy.deepcopy(runtime_secret['data']); runtime_data['runtime.json'] = _encoded(updated)
    plan['patches']['gateway.runtime-secret'] = _patch(runtime_secret, '/data', runtime_data)
    plan['preservation'] = {'approval_revision': expected_revision, 'policy_hash': policy.hash,
        'qualification_ref': node_body['qualification_ref'], 'terminal_index_ref': node_body['terminal_index_ref'],
        'terminal_index_data_sha256': terminal_ref.to_dict()['data_sha256'],
        'archived_terminal_records': terminal.get('total_records'), 'released_ledger_entries': len(ledger_body['allocations']),
        'ledger_data_sha256': sha(ledger['data']), 'driver_epoch': epoch,
        'node_config_changed_fields': ['component_declarations.' + c + '.image' for c in COMPONENTS],
        'runtime_changed_fields': ['nativeGroupApprovals.processes.' + c + '.image' for c in COMPONENTS],
        'capture_seed_changed_fields': ['config.json.node_process.image'],
        'bootstrap_binding': 'Requires actual created immutable NodeConfig UID/RV/data; policy and service command retained',
        'unchanged': ['approval documents/references/history', 'qualification/policy/caps/CDI', 'terminal index/archive/ledger',
                      'database/auth/tokens/CA/storage', 'mounts/commands/args/service-account identities'],
        'required_live_gates': ['Root maintenance and writer fence', 'fresh quiescence/UID/RV/full preimages',
            'actual immutable config readback', 'held Node release and observer coordination',
            'fresh genuine four-component ACKs', 'actual KAI lifecycle qualification']}
    return plan


def bind_node(snapshot, plan, actual_node_config, *, stopped=None):
    """Bind actual immutable config identity; retain the release=false hold."""
    try:
        expected = render(snapshot, plan['images'], expected_snapshot_sha256=plan['snapshot_sha256'],
                          expected_revision=plan['expected_revision'])
        require(plan == expected, 'Exact unmodified reviewed adoption plan required')
        candidate = plan['creates'].get('node-config') or plan['reuses']['node-config']
        meta = _guard(actual_node_config, 'ConfigMap'); _immutable(actual_node_config)
        require(actual_node_config['data'] == candidate['data']
            and all(meta[k] == candidate['metadata'][k] for k in ('namespace', 'name')), 'Actual created NodeConfig differs')
        from cps_compute.immutable_configmap import ImmutableConfigMapRef
        reference = ImmutableConfigMapRef.from_dict({**{k: meta[k] for k in ('namespace', 'name', 'uid', 'resourceVersion')},
            'key': 'config.json', 'data_sha256': sha(actual_node_config['data'])})
        reference.validate(actual_node_config)
        old = volume(snapshot, 'node', 'packaged-bootstrap-input')
        data = copy.deepcopy(old['data']); data['config-ref.json'] = canonical(reference.to_dict()); data['release'] = 'false'
        bootstrap = _candidate(old, 'cps-packaged-node-bootstrap', data, immutable=False)
        dep = snapshot['deployments']['node']; desired = copy.deepcopy(dep['spec']); pod = desired['template']['spec']
        process = _parse(actual_node_config['data']['config.json'])['component_declarations']['node']
        main = _one(pod['containers'], process['container'])
        _node_initializer_image(pod, main['image'], plan['images']['node'])
        main['image'] = plan['images']['node']
        _one(pod['volumes'], 'packaged-bootstrap-input')['configMap']['name'] = bootstrap['metadata']['name']
        preimage = dep
        if stopped is not None:
            _guard(stopped, 'Deployment'); held = copy.deepcopy(dep['spec']); held['replicas'] = 0
            require(stopped['metadata']['uid'] == dep['metadata']['uid'] and stopped['metadata']['namespace'] == dep['metadata']['namespace']
                and stopped['metadata']['name'] == dep['metadata']['name'] and stopped['spec'] == held,
                'Actual stopped Node may differ only by replicas0')
            preimage = stopped
        return {'version': 1, 'creates': {'node.bootstrap': bootstrap},
                'patches': {'node.deployment': _patch(preimage, '/spec', desired)}, 'live_applied': False,
                'hardware_qualified': False, 'release_held': True, 'actual_node_config_ref': reference.to_dict()}
    except (KeyError, TypeError, AttributeError):
        raise ValueError('Incomplete actual NodeConfig binding readback') from None
