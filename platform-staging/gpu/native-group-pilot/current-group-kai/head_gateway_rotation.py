"""Pure, private v4 Gateway/Node successor intents; never apply or qualify them.

The endpoint seed may be staged or installed. Installed Coordinator fragments
must match an independently reviewed proposal pin. Root owns journal rotation
and actual post-rollout observer captures. Plans retain private input data.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from types import SimpleNamespace

import image_adoption as image


def _module(path):
    spec = importlib.util.spec_from_file_location('rotation_' + path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _guard(obj, kind):
    from cps_compute.native_observer_permissions import valid_uid
    if kind == 'RoleBinding':
        image.require(isinstance(obj, dict) and obj.get('apiVersion') == 'rbac.authorization.k8s.io/v1'
            and obj.get('kind') == kind, 'Exact actual RoleBinding required')
        meta = obj.get('metadata', {})
        image.require(isinstance(meta.get('resourceVersion'), str)
            and re.fullmatch(r'[1-9][0-9]*', meta['resourceVersion']) and meta.get('namespace')
            and meta.get('name') and not meta.get('deletionTimestamp'), 'Actual named UID/RV resource required')
    else:
        meta = image._guard(obj, kind)
    image.require(valid_uid(meta['uid']) and not meta.get('ownerReferences'),
                  'Actual nonzero ownerless UID required')
    return meta


def _actual(candidate, actual, *, immutable=True):
    meta = _guard(actual, candidate['kind'])
    image.require(all(meta[k] == candidate['metadata'][k] for k in ('namespace', 'name'))
        and actual.get('data') == candidate['data'] and not actual.get('binaryData')
        and actual.get('type') == candidate.get('type')
        and (actual.get('immutable') is True if immutable else actual.get('immutable') in (None, False)),
        'Actual staged authority identity, immutability or complete data differs')


def _core(snapshot):
    return SimpleNamespace(read_namespaced_config_map=lambda name, namespace:
        deepcopy(image._get(snapshot, 'ConfigMap', namespace, name)))


def _reference(cm):
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    meta = _guard(cm, 'ConfigMap')
    return ImmutableConfigMapRef.from_dict({**{k: meta[k] for k in ('namespace', 'name', 'uid', 'resourceVersion')},
        'key': 'config.json', 'data_sha256': image.sha(cm['data'])})


def _mounted_head(snapshot, component, declaration, binding):
    """Prove the existing local projections, without rewriting a head binding."""
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    pod = snapshot['deployments'][component]['spec']['template']['spec']
    main = image._one(pod['containers'], declaration['container'])
    anchor = image.volume(snapshot, component, 'cps-native-head-anchor')
    ImmutableConfigMapRef.from_dict(binding['projection']).validate(anchor)
    mount = image._one(main['volumeMounts'], 'cps-native-head-anchor')
    image.require(mount == {'name': 'cps-native-head-anchor',
        'mountPath': '/var/run/cps-native-approvals/head-anchor.json', 'subPath': 'anchor.json', 'readOnly': True},
        'Existing immutable head anchor mount changed')
    if component != 'node':
        actual = image._immutable(image.volume(snapshot, component, 'cps-native-head-binding'))
        image.require(set(actual['data']) == {'head-binding.json'}
            and image._parse(actual['data']['head-binding.json']) == binding,
            'Mounted namespace-local binding differs from reviewed head')
        mount = image._one(main['volumeMounts'], 'cps-native-head-binding')
        image.require(mount == {'name': 'cps-native-head-binding', 'mountPath': '/etc/cps-native-head-binding.json',
            'subPath': 'head-binding.json', 'readOnly': True}
            and image._one(main.get('env', []), 'CPS_NATIVE_GROUP_APPROVAL_HEAD') == {
                'name': 'CPS_NATIVE_GROUP_APPROVAL_HEAD', 'value': '/etc/cps-native-head-binding.json'},
            'Existing component binding mount or literal path changed')


def _role_rules(actual, pinned, index, head_names, *, component):
    """Compare against independent baseline; live privileges never become pins."""
    from cps_compute.native_observer_permissions import mutable_rows, names
    meta = _guard(actual, 'Role')
    image.require(meta['uid'] == pinned['uid'], 'Pinned Role UID changed')
    rules = deepcopy(actual['rules'])
    image.require(isinstance(pinned['rules'], list) and isinstance(rules, list)
        and len(rules) == len(pinned['rules']), 'Complete original Role rules required')
    image.require(type(index) is int and 0 <= index < len(pinned['rules']), 'Exact selected GET row required')
    row = pinned['rules'][index]
    image.require(set(row) == {'apiGroups', 'resources', 'verbs', 'resourceNames'}
        and (row['apiGroups'], row['resources'], row['verbs']) == ([''], ['configmaps'], ['get']),
        'Only an existing closed named ConfigMap GET row may grow')
    names(row['resourceNames'])
    if component:
        indexes = mutable_rows(pinned['rules'])
        image.require(mutable_rows(rules) == indexes, 'Component Role schema changed')
        for offset in indexes.values():
            rules[offset]['resourceNames'] = pinned['rules'][offset]['resourceNames']
    required = set(row['resourceNames']); allowed = required | set(head_names)
    names(sorted(allowed)); names(actual['rules'][index]['resourceNames'])
    image.require(required <= set(actual['rules'][index]['resourceNames']) <= allowed,
                  'Actual GET names exceed pinned baseline and authenticated retained heads')
    rules[index]['resourceNames'] = row['resourceNames']
    image.require(rules == pinned['rules'], 'Actual static privileges differ from independent baseline')


def _context(inputs):
    from cps_compute.native_observer_permissions import ObserverRelease, observe_head_permissions, role_targets
    from cps_compute.native_group_process import _template
    snapshot = inputs['snapshot']; previous = inputs['previous_release']; operators = inputs['operator_baselines']
    image.require(isinstance(snapshot, dict) and snapshot.get('version') == 1
        and set(snapshot['deployments']) == set(image.COMPONENTS)
        and image.sha(snapshot) == inputs['expected_snapshot_sha256']
        and image.sha(previous) == inputs['expected_release_sha256']
        and image.sha(operators) == inputs['expected_operator_baselines_sha256'],
        'Independent snapshot, release and operator baseline pins required')
    policy, configuration = image._context(snapshot); document = configuration.document
    release = ObserverRelease.from_dict(previous)
    image.require(document['version'] == 4 and previous['version'] == 2
        and previous['node_configuration'] == configuration.reference.to_dict(),
        'Actual matching v4 Node and v2 observer release required')
    heads, head_names = observe_head_permissions(_core(snapshot), release, configuration, policy)
    image.require(isinstance(inputs['expected_revision'], str)
        and re.fullmatch(r'sha256:[a-f0-9]{64}', inputs['expected_revision'])
        and all(h.reference['revision'] == inputs['expected_revision'] for h in heads.values()),
        'Independently pinned current Source revision differs')
    gateway_image = inputs['gateway_image']; declarations = document['component_declarations']
    image.require(isinstance(gateway_image, str) and re.fullmatch(r'ghcr.io/mul-cps/cps-compute@sha256:[a-f0-9]{64}', gateway_image)
        and not gateway_image.endswith('0' * 64), 'Qualified immutable Gateway image required')
    node_image = inputs.get('node_image')
    if node_image is not None:
        image.require(isinstance(node_image, str) and re.fullmatch(r'ghcr.io/mul-cps/cps-native-node@sha256:[a-f0-9]{64}', node_image)
            and not node_image.endswith('0' * 64) and node_image != declarations['node']['image'],
            'Distinct qualified immutable Node successor image required')
    image.require(gateway_image != declarations['gateway']['image'] or node_image is not None,
                  'Distinct qualified immutable Gateway or Node successor required')
    runtime_secret = image.secret_volume(snapshot, 'gateway', 'config')
    _guard(runtime_secret, 'Secret')
    image.require(runtime_secret.get('type') == 'Opaque' and runtime_secret.get('immutable') is not True,
                  'Existing mutable Opaque Gateway runtime Secret required')
    runtime = image._decode(runtime_secret['data']['runtime.json']); approvals = runtime['nativeGroupApprovals']
    epoch = {k: configuration.deployment.node_pool[k] for k in ('node_uid', 'boot_id', 'driver_generation', 'gpu_uuid')}
    image.require(runtime['policy_hash'] == policy.hash and set(approvals) == {
        'enabled', 'version', 'acknowledgments', 'processes', 'driver_epoch', 'ttlSeconds', 'heads'}
        and type(approvals['version']) is int and approvals['version'] == 2 and approvals['enabled'] is True
        and set(approvals['processes']) == set(image.COMPONENTS)
        and approvals['heads'] == previous['heads'] and approvals['acknowledgments'] == document['acknowledgment_targets']
        and approvals['driver_epoch'] == epoch and type(approvals['ttlSeconds']) is int
        and 15 <= approvals['ttlSeconds'] <= 120, 'Actual dynamic runtime approval authority differs')
    for component, declaration in declarations.items():
        dep = snapshot['deployments'][component]; meta = _guard(dep, 'Deployment')
        process = {k: v for k, v in declaration.items() if k != 'service_account_uid'}
        pod = dep['spec']['template']['spec']
        image.require(image._get(snapshot, 'Deployment', meta['namespace'], meta['name']) == dep
            and all(meta[k] == process[k] for k in ('namespace', 'name', 'uid'))
            and process == approvals['processes'][component]
            and pod['serviceAccountName'] == process['service_account']
            and image._one(pod['containers'], process['container'])['image'] == process['image'],
            'Actual controller, duplicate capture or process declaration drift')
        account = image._get(snapshot, 'ServiceAccount', meta['namespace'], process['service_account'])
        image.require(_guard(account, 'ServiceAccount')['uid'] == declaration['service_account_uid'],
                      'Declared actual ServiceAccount UID differs')
        _mounted_head(snapshot, component, declaration, previous['heads'][component])
    node = snapshot['deployments']['node']; node_pod = node['spec']['template']['spec']
    image.require(previous['held_node_template_sha256'] == image.sha(_template(node)),
                  'Independent old full Node template pin differs')
    image._node_initializer_image(node_pod, declarations['node']['image'])
    image.require(image._one(node_pod['containers'], declarations['node']['container'])['command']
        == ['python', '-m', 'cps_compute.native_node.service'], 'Packaged Node service command differs')
    bootstrap = image.volume(snapshot, 'node', 'packaged-bootstrap-input'); _guard(bootstrap, 'ConfigMap')
    image.require(bootstrap['data']['release'] == 'true' and bootstrap.get('immutable') is not True,
                  'Actual released mutable old bootstrap required')
    pod = snapshot['deployments']['gateway']['spec']['template']['spec']
    rollout = _module(Path(__file__).parent.parent / 'current-group-integration' / 'gateway_rollout.py')
    proposal = inputs['endpoint_proposal']; seed = inputs['actual_endpoint_seed']
    _guard(seed, 'ConfigMap'); rollout._seed(proposal, seed, declarations['gateway']['namespace'])
    image.require(proposal['coordinator']['nodeConfigurationRef'] == configuration.reference.to_dict()
        and set(proposal['gateway']['private_files']) == set(proposal['seed']['data'])
        and all(proposal['gateway']['private_files'][k] == image._parse(v) for k, v in proposal['seed']['data'].items())
        and image._parse(proposal['seed']['data']['coordinator.json']) == proposal['coordinator']
        and proposal['gateway']['initContainer']['image'] == declarations['gateway']['image'],
        'Staged endpoint Coordinator config differs from actual old Node/Gateway')
    installed_env = [(c['name'], e) for c in pod['containers'] for e in c.get('env', [])
                     if e.get('name') == 'CPS_NATIVE_KAI_COORDINATOR_CONFIG']
    mounted = bool(installed_env) or any(v.get('name') == 'kai-seed' for v in pod['volumes']) \
        or any(c.get('name') == 'native-kai-private-inputs' for c in pod.get('initContainers', []))
    if mounted:
        image.require(inputs.get('expected_endpoint_proposal_sha256') == image.sha(proposal),
                      'Independent reviewed mounted endpoint proposal pin required')
        fragment = proposal['gateway']; main_name = declarations['gateway']['container']
        expected_env = {'name': 'CPS_NATIVE_KAI_COORDINATOR_CONFIG', 'value': '/kai-private/config/coordinator.json'}
        image.require(fragment['env'] == [expected_env] and installed_env == [(main_name, expected_env)]
            and image._one(pod['volumes'], 'kai-private') == {'name': 'kai-private', 'emptyDir': {}}
            and image._one(image._one(pod['containers'], main_name)['volumeMounts'], 'kai-private') == {
                'name': 'kai-private', 'mountPath': '/kai-private', 'readOnly': True},
            'Exact installed Coordinator environment and private read-only mount required')
        initializer = deepcopy(image._one(pod.get('initContainers', []), 'native-kai-private-inputs'))
        api_defaults = {}
        for field, default in {'imagePullPolicy': 'IfNotPresent', 'resources': {},
                'terminationMessagePath': '/dev/termination-log', 'terminationMessagePolicy': 'File'}.items():
            if field not in fragment['initContainer'] and field in initializer:
                image.require(initializer[field] == default, 'Unreviewed Coordinator initializer API default differs')
                api_defaults[field] = initializer.pop(field)
        image.require(initializer == fragment['initContainer'],
                      'Installed Coordinator initializer differs from independently reviewed full command and spec')
        # Reuse the original append-only compositor to prove the complete mounted
        # fragments, data PVC, fsGroup and collision rules against the reviewed input.
        absent = deepcopy(snapshot['deployments']['gateway']); absent_pod = absent['spec']['template']['spec']
        main = image._one(absent_pod['containers'], main_name)
        for field in ('env', 'volumeMounts'):
            names = {v['name'] for v in fragment[field]}
            main[field] = [v for v in main.get(field, []) if v.get('name') not in names]
        for field, values in (('volumes', fragment['volumes']), ('initContainers', [fragment['initContainer']])):
            names = {v['name'] for v in values}
            absent_pod[field] = [v for v in absent_pod.get(field, []) if v.get('name') not in names]
        expected = {k: absent['metadata'][k] for k in ('namespace', 'name', 'uid', 'resourceVersion')}
        rebuilt = rollout.compose_gateway(absent, proposal, seed, expected=expected, container=main_name)
        image._one(rebuilt['spec']['template']['spec']['initContainers'], 'native-kai-private-inputs').update(api_defaults)
        image.require(rebuilt['spec'] == snapshot['deployments']['gateway']['spec'],
                      'Installed Coordinator fragments differ from reviewed append-only proposal')
    else:
        image.require(not any(v.get('configMap', {}).get('name') == seed['metadata']['name'] for v in pod['volumes']),
                      'Endpoint seed must be staged but not mounted')
    image.require(image._get(snapshot, 'ConfigMap', seed['metadata']['namespace'], seed['metadata']['name']) == seed,
                  'Duplicate actual staged endpoint seed differs')
    capture = image._immutable(image.secret_volume(snapshot, 'gateway', 'capture-seed'))
    settings = image._decode(capture['data']['config.json'])
    image.require(settings['version'] == 2 and settings['approval_head'] == previous['heads']['node']
        and settings['node_process'] == approvals['processes']['node']
        and settings['node_acknowledgment'] == approvals['acknowledgments']['node'], 'Unchanged capture seed authority differs')
    publisher = image._immutable(image.volume(snapshot, 'gateway', 'cps-native-approval-publisher'))
    _guard(publisher, 'ConfigMap')
    body = image._parse(publisher['data']['publisher.json'])
    image.require(set(publisher['data']) == {'publisher.json'} and set(body) == {
        'version', 'component', 'process', 'acknowledgment', 'driver_epoch', 'ttlSeconds'}
        and type(body['version']) is int and body['version'] == 1 and body['component'] == 'gateway'
        and body['process'] == approvals['processes']['gateway'] and body['driver_epoch'] == epoch
        and body['acknowledgment'] == approvals['acknowledgments']['gateway']
        and type(body['ttlSeconds']) is int and 15 <= body['ttlSeconds'] <= 120,
        'Gateway immutable publisher authority differs')
    baseline = {(r['namespace'], r['name']): r for r in previous['roles']}
    image.require(set(baseline) == set(role_targets(document)), 'Exact seven component Role baselines required')
    rows = {(r['namespace'], r['name']): r['index'] for r in previous['head_get_rows']}
    for key, pinned in baseline.items():
        _role_rules(image._get(snapshot, 'Role', *key), pinned, rows[key], head_names[key[0]], component=True)
    namespaces = {d['namespace'] for d in declarations.values()}
    image.require(isinstance(operators, list) and len(operators) == 4
        and {r['namespace'] for r in operators} == namespaces, 'Four distinct namespace-local operator reader baselines required')
    for pinned in operators:
        image.require(set(pinned) == {'namespace', 'name', 'uid', 'index', 'rules'}, 'Closed independent operator Role baseline required')
        _role_rules(image._get(snapshot, 'Role', pinned['namespace'], pinned['name']), pinned,
                    pinned['index'], head_names[pinned['namespace']], component=False)
    ledger = image._get(snapshot, 'ConfigMap', configuration.deployment.authority_namespace, 'cps-native-gpu-allocations')
    state = image._parse(ledger['data']['state.json'])
    image.require(state.get('version') == 1 and isinstance(state.get('allocations'), dict)
        and all(v.get('state') == 'released' for v in state['allocations'].values()),
        'Released-only ledger capture required; actual SQL/writer fences remain Root gates')
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    terminal = ImmutableConfigMapRef.from_dict(document['terminal_index_ref'])
    terminal.validate(image._get(snapshot, 'ConfigMap', terminal.to_dict()['namespace'], terminal.to_dict()['name']))
    return policy, configuration, runtime, publisher, body


def prepare(snapshot, previous_release, operator_baselines, gateway_image, endpoint_proposal, actual_endpoint_seed,
            *, expected_snapshot_sha256, expected_release_sha256, expected_operator_baselines_sha256, expected_revision, expected_endpoint_proposal_sha256=None, node_image=None):
    """First phase: create an immutable Node4 image successor candidate."""
    inputs = deepcopy(locals())
    if node_image is None: inputs.pop('node_image')
    if expected_endpoint_proposal_sha256 is None:
        inputs.pop('expected_endpoint_proposal_sha256')
    try:
        policy, configuration, _, _, _ = _context(inputs)
        document = configuration.document; document['component_declarations']['gateway']['image'] = gateway_image
        if node_image is not None: document['component_declarations']['node']['image'] = node_image
        old = image._get(snapshot, 'ConfigMap', configuration.reference.to_dict()['namespace'], configuration.reference.to_dict()['name'])
        return {'version': 1, 'kind': 'head-gateway-rotation', 'inputs': inputs,
            'creates': {'node-config': image._candidate(old, 'cps-native-head-config', {'config.json': image.canonical(document)})},
            'live_applied': False, 'hardware_qualified': False, 'journal_rotation_required': True}
    except (KeyError, TypeError, AttributeError, StopIteration):
        raise ValueError('Incomplete pinned Gateway successor inputs') from None


def bind_node(snapshot, prepared, actual_node_config):
    """Bind the actual new six-field ref before generating its three dependents."""
    try:
        image.require(snapshot == prepared['inputs']['snapshot'] and prepared == prepare(**prepared['inputs']),
                      'Exact prepared plan and captured preimages required')
        _actual(prepared['creates']['node-config'], actual_node_config)
        policy, old, runtime, publisher, publisher_body = _context(prepared['inputs'])
        reference = _reference(actual_node_config); reference.validate(actual_node_config)
        extended = deepcopy(snapshot); meta = actual_node_config['metadata']
        extended['objects'][image._key('ConfigMap', meta['namespace'], meta['name'])] = deepcopy(actual_node_config)
        from cps_compute.native_node.config import NodeConfiguration
        new = NodeConfiguration.load(_core(extended), reference, policy)
        image.require(new.document == image._parse(prepared['creates']['node-config']['data']['config.json']),
                      'Typed successor configuration differs')
        bootstrap = image.volume(snapshot, 'node', 'packaged-bootstrap-input')
        data = deepcopy(bootstrap['data']); data.update({'config-ref.json': image.canonical(reference.to_dict()), 'release': 'false'})
        bootstrap_candidate = image._candidate(bootstrap, 'cps-native-head-bootstrap', data, immutable=False)
        publisher_body['process']['image'] = prepared['inputs']['gateway_image']
        publisher_candidate = image._candidate(publisher, 'cps-native-approval-publisher', {'publisher.json': image.canonical(publisher_body)})
        proposal = deepcopy(prepared['inputs']['endpoint_proposal'])
        proposal['coordinator']['nodeConfigurationRef'] = reference.to_dict()
        node_image = prepared['inputs'].get('node_image')
        if node_image is not None: proposal['coordinator']['epoch']['nodeProcess']['image'] = node_image
        proposal['seed']['data']['coordinator.json'] = image.canonical(proposal['coordinator'])
        suffix = hashlib.sha256(json.dumps(proposal['seed']['data'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:16]
        proposal['seed']['metadata']['name'] = 'cps-native-kai-config-' + suffix
        proposal['gateway']['private_files']['coordinator.json'] = deepcopy(proposal['coordinator'])
        image._one(proposal['gateway']['volumes'], 'kai-seed')['configMap']['name'] = proposal['seed']['metadata']['name']
        proposal['gateway']['initContainer']['image'] = prepared['inputs']['gateway_image']
        specs = {c: deepcopy(d['spec']) for c, d in snapshot['deployments'].items()}
        node_pod = specs['node']['template']['spec']
        image._one(node_pod['volumes'], 'packaged-bootstrap-input')['configMap']['name'] = bootstrap_candidate['metadata']['name']
        if node_image is not None:
            image._one(node_pod['containers'], old.document['component_declarations']['node']['container'])['image'] = node_image
            image._one(node_pod['initContainers'], 'packaged-bootstrap')['image'] = node_image
        gateway_pod = specs['gateway']['template']['spec']; old_image = old.document['component_declarations']['gateway']['image']
        main = image._one(gateway_pod['containers'], old.document['component_declarations']['gateway']['container'])
        main['image'] = prepared['inputs']['gateway_image']
        for section, name in (('containers', 'approval-capture'), ('initContainers', 'capture-private-inputs')):
            child = image._one(gateway_pod[section], name)
            image.require(child['image'] == old_image, 'Same-component Gateway capture/helper image drift')
            child['image'] = prepared['inputs']['gateway_image']
        if any(c.get('name') == 'native-kai-private-inputs' for c in gateway_pod.get('initContainers', [])):
            image._one(gateway_pod['initContainers'], 'native-kai-private-inputs')['image'] = prepared['inputs']['gateway_image']
            image._one(gateway_pod['volumes'], 'kai-seed')['configMap']['name'] = proposal['seed']['metadata']['name']
        image._one(gateway_pod['volumes'], 'cps-native-approval-publisher')['configMap']['name'] = publisher_candidate['metadata']['name']
        runtime['nativeGroupApprovals']['processes']['gateway']['image'] = prepared['inputs']['gateway_image']
        creates = {'node.bootstrap': bootstrap_candidate, 'gateway.publisher': publisher_candidate,
                   'coordinator.seed': deepcopy(proposal['seed'])}
        if node_image is not None:
            runtime['nativeGroupApprovals']['processes']['node']['image'] = node_image
            capture = image.secret_volume(snapshot, 'gateway', 'capture-seed')
            capture_data = deepcopy(capture['data']); settings = image._decode(capture_data['config.json'])
            settings['node_process']['image'] = node_image
            capture_data['config.json'] = image._encoded(settings)
            creates['gateway.capture-seed'] = image._candidate(capture, 'cps-native-head-capture', capture_data)
            image._one(gateway_pod['volumes'], 'capture-seed')['secret']['secretName'] = creates['gateway.capture-seed']['metadata']['name']
        secret = image.secret_volume(snapshot, 'gateway', 'config'); runtime_data = deepcopy(secret['data'])
        runtime_data['runtime.json'] = image._encoded(runtime)
        return {'version': 1, 'prepared': deepcopy(prepared), 'actual_node_config': deepcopy(actual_node_config),
            'node_config_ref': reference.to_dict(), 'creates': creates,
            'endpoint_proposal': proposal, 'runtime_specs': specs,
            'gateway_runtime_patch': image._patch(secret, '/data', runtime_data),
            'live_applied': False, 'hardware_qualified': False}
    except (KeyError, TypeError, AttributeError, StopIteration):
        raise ValueError('Incomplete Gateway successor actual config binding') from None


def _grow(pinned, actual, index, additions):
    from cps_compute.native_observer_permissions import names
    trusted = deepcopy(pinned); desired = deepcopy(actual['rules'])
    for rules in (trusted['rules'], desired):
        rules[index]['resourceNames'] = sorted(set(rules[index]['resourceNames']) | set(additions))
        names(rules[index]['resourceNames'])
    return trusted, desired


def _permissions(snapshot, plan, actual_creates, actual_permissions):
    """Separate static reads from the existing head-producer-owned reader Roles."""
    from cps_compute.native_observer_permissions import names
    namespace = plan['node_config_ref']['namespace']
    account_name = 'cps-native-observer-operator'
    subject = {'kind': 'ServiceAccount', 'namespace': namespace, 'name': account_name}
    account_key = image._key('ServiceAccount', namespace, account_name)
    account = image._get(snapshot, 'ServiceAccount', namespace, account_name) if account_key in snapshot['objects'] else None
    account_ref = {'namespace': namespace, 'name': account_name}
    if account is not None:
        account_ref['uid'] = _guard(account, 'ServiceAccount')['uid']
    reads = sorted({plan['node_config_ref']['name'], actual_creates['node.bootstrap']['metadata']['name']})
    image.require(len(reads) == 2, 'Two distinct actual new Node configuration/bootstrap names required')
    names(reads)
    rules = [{'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['get'], 'resourceNames': reads}]
    suffix = image.sha({'namespace': namespace, 'subject': subject, 'rules': rules})[7:23]
    name = 'cps-native-observer-rotation-' + suffix
    metadata = {'namespace': namespace, 'name': name}
    role = {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role',
            'metadata': deepcopy(metadata), 'rules': rules}
    binding = {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding',
        'metadata': deepcopy(metadata), 'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': name},
        'subjects': [subject]}
    candidates = {'observer.read-role': role, 'observer.read-binding': binding}
    if actual_permissions is None:
        return candidates, {}, account_ref
    image.require(isinstance(actual_permissions, dict) and set(actual_permissions) == set(candidates),
                  'Exactly two actual supplemental permission readbacks required')
    for label, candidate in candidates.items():
        actual = actual_permissions[label]; meta = _guard(actual, candidate['kind'])
        image.require(all(meta[k] == candidate['metadata'][k] for k in ('namespace', 'name'))
            and {k: v for k, v in actual.items() if k != 'metadata'}
                == {k: v for k, v in candidate.items() if k != 'metadata'},
            'Actual supplemental permission rules, subject, reference or identity differ')
    return {}, deepcopy(actual_permissions), account_ref


def bind(snapshot, plan, actual_creates, *, actual_permissions=None):
    """Return CAS patches only after exact supplemental permission readbacks.

    The fixed observer subject retains its existing name-based Kubernetes RBAC
    identity. Its actual UID is validated when included in the pinned capture;
    RoleBinding itself cannot pin a ServiceAccount UID. The four original
    producer-owned operator Roles and their independent baselines stay exact.
    """
    try:
        expected = bind_node(snapshot, plan['prepared'], plan['actual_node_config'])
        image.require(plan == expected, 'Exact bound Node/config/dependent plan required')
        image.require(isinstance(actual_creates, dict) and set(actual_creates) == set(plan['creates']),
                      'Exact actual dependent CREATE readbacks required')
        for label, candidate in plan['creates'].items():
            _actual(candidate, actual_creates[label], immutable=label != 'node.bootstrap')
        inputs = plan['prepared']['inputs']; previous = inputs['previous_release']
        _, old, _, _, _ = _context(inputs)
        declarations = old.document['component_declarations']; node_ns = declarations['node']['namespace']
        additions = {(node_ns, 'cps-native-approval-node'): {plan['node_config_ref']['name']},
            (node_ns, 'cps-native-approval-gateway'): {plan['node_config_ref']['name']}}
        release = deepcopy(previous); release['node_configuration'] = deepcopy(plan['node_config_ref'])
        from cps_compute.native_group_process import _template
        old_template = _template(snapshot['deployments']['node'])
        new_node = deepcopy(snapshot['deployments']['node']); new_node['spec'] = deepcopy(plan['runtime_specs']['node'])
        release['held_node_template_sha256'] = image.sha(_template(new_node))
        rows = {(r['namespace'], r['name']): r['index'] for r in release['head_get_rows']}
        patches = {'gateway.runtime-secret': deepcopy(plan['gateway_runtime_patch'])}; roles = []
        for offset, pinned in enumerate(previous['roles']):
            key = pinned['namespace'], pinned['name']; actual = image._get(snapshot, 'Role', *key)
            trusted, desired = _grow(pinned, actual, rows[key], additions.get(key, set()))
            release['roles'][offset] = trusted
            value = deepcopy(actual); value['rules'] = desired; roles.append(value)
            if desired != actual['rules']: patches['component-role:' + '/'.join(key)] = image._patch(actual, '/rules', desired)
        operators = deepcopy(inputs['operator_baselines'])
        controllers = []
        for component, original in snapshot['deployments'].items():
            value = deepcopy(original); value['spec'] = deepcopy(plan['runtime_specs'][component]); controllers.append(value)
            if value['spec'] != original['spec']: patches[component + '.deployment'] = image._patch(original, '/spec', value['spec'])
        maps = {image._key('ConfigMap', o['metadata']['namespace'], o['metadata']['name']): deepcopy(o)
                for o in snapshot['objects'].values() if o['kind'] == 'ConfigMap'}
        for value in [plan['actual_node_config'], *actual_creates.values()]:
            if value['kind'] != 'ConfigMap': continue
            maps[image._key('ConfigMap', value['metadata']['namespace'], value['metadata']['name'])] = deepcopy(value)
        from cps_compute.native_observer_permissions import ObserverRelease
        ObserverRelease.from_dict(release)
        permissions, verified_permissions, observer_account = _permissions(snapshot, plan, actual_creates, actual_permissions)
        pending = actual_permissions is None
        return {'version': 1, 'observer_release': release, 'prospective_capture': {'version': 1,
            'configmaps': list(maps.values()), 'deployments': controllers, 'roles': roles},
            'creates': permissions, 'permissions_pending': pending,
            'actual_permissions': verified_permissions, 'observer_service_account': observer_account,
            'patches': {} if pending else patches, 'operator_baselines': operators, 'endpoint_proposal': deepcopy(plan['endpoint_proposal']),
            'actual_endpoint_seed': deepcopy(actual_creates['coordinator.seed']), 'node_config_ref': deepcopy(plan['node_config_ref']),
            'previous_node_template': old_template, 'previous_node_template_sha256': image.sha(old_template),
            'runtime_specs': deepcopy(plan['runtime_specs']), 'prospective': True, 'live_applied': False,
            'hardware_qualified': False, 'process_readiness_verified': False,
            'actual_only_render_required': True, 'journal_rotation_required': True}
    except (KeyError, TypeError, AttributeError, StopIteration):
        raise ValueError('Incomplete actual Gateway successor dependent readbacks') from None
