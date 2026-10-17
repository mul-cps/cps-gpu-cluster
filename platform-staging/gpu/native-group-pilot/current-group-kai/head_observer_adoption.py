"""Pure, prospective ObserverRelease1-to-2 composition for a held head rollout.

Actual captured API identities and independently pinned baselines are inputs.
No API call, process operation, image change or release occurs in this module.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import re


def _module(path):
    spec = importlib.util.spec_from_file_location('head_observer_' + path.stem, path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def _require(value, message):
    if not value: raise ValueError(message)


def _key(obj):
    return obj['metadata']['namespace'], obj['metadata']['name']


def _one(values, name):
    found = [value for value in values if value.get('name') == name]
    _require(len(found) == 1, 'One exact existing runtime entry required')
    return found[0]


def compose(previous_release, reviewed_sha256, catalog, old_configuration, new_configuration,
            held_bootstrap, heads, capture, runtime_specs, *, reviewed_runtime_specs_sha256,
            actual_gateway_capture_seed=None, head_get_rows=None):
    """Return a planning-only release/capture and guarded exact named GET deltas."""
    try:
        return _compose(previous_release, reviewed_sha256, catalog, old_configuration, new_configuration,
            held_bootstrap, heads, capture, runtime_specs, reviewed_runtime_specs_sha256,
            actual_gateway_capture_seed, head_get_rows)
    except (KeyError, TypeError, AttributeError, StopIteration, IndexError):
        raise ValueError('Incomplete head observer adoption inputs') from None


def _compose(previous_release, reviewed_sha256, catalog, old, new, held, heads, capture, specs, specs_hash, seed, rows):
    from cps_compute.native_groups import canonical_sha256 as sha
    from cps_compute.native_node.config import NodeConfiguration
    from cps_compute.native_observer_permissions import ObserverRelease, mutable_rows, observe_head_permissions
    from cps_compute.native_group_revision import COMPONENTS, _uid
    from cps_compute.policy import Policy
    source = _module(Path(__file__).resolve().parents[3] / 'native-observer-operator' / 'render.py')
    bootstrap = _module(Path(__file__).with_name('head_bootstrap.py'))
    _require(sha(previous_release) == reviewed_sha256 and sha(specs) == specs_hash,
             'Independently reviewed previous release and exact proposed runtime pins required')
    previous = ObserverRelease.from_dict(previous_release).document
    _require(previous['version'] == 1 and type(old) is NodeConfiguration and type(new) is NodeConfiguration
        and old.document['version'] == 3 and new.document['version'] == 4
        and previous['node_configuration'] == old.reference.to_dict(), 'Actual v3 baseline and v4 successor required')
    _require(isinstance(capture, dict) and set(capture) == {'version', 'configmaps', 'deployments', 'roles'}
        and type(capture['version']) is int and capture['version'] == 1, 'Closed actual capture required')
    maps = source._inventory(capture['configmaps'], 'ConfigMap', 'v1', limit=544)
    controllers = source._inventory(capture['deployments'], 'Deployment', 'apps/v1')
    roles = source._inventory(capture['roles'], 'Role', 'rbac.authorization.k8s.io/v1')
    for value in list(controllers.values()) + list(roles.values()):
        meta = value['metadata']
        _require(_uid(meta.get('uid')) and isinstance(meta.get('resourceVersion'), str)
            and re.fullmatch(r'[1-9][0-9]*', meta['resourceVersion']) and not meta.get('ownerReferences'),
            'Actual original controller/Role UID and resourceVersion required')
    class CapturedCore:
        reads = set()
        def read_namespaced_config_map(self, name, namespace):
            key = namespace, name
            _require(key in maps, 'Missing actual captured authority ConfigMap')
            self.reads.add(key); return deepcopy(maps[key])
    core = CapturedCore(); policy = Policy(catalog)
    _require(NodeConfiguration.load(core, old.reference, policy).document == old.document,
             'Actual previous Node configuration differs')
    old_reads = set(core.reads)
    _require(NodeConfiguration.load(core, new.reference, policy).document == new.document,
             'Actual successor Node configuration differs')
    declarations = old.document['component_declarations']
    expected_keys = {(d['namespace'], d['name']) for d in declarations.values()}
    baseline = {(r['namespace'], r['name']): r for r in previous['roles']}
    _require(set(controllers) == expected_keys and len(controllers) == 4 and set(roles) == set(baseline)
        and len(roles) == 7 and isinstance(heads, dict) and set(heads) == COMPONENTS,
        'Exact four original controllers, seven Roles and four head bindings required')
    approvals, pointers, anchors, original = {}, {}, {}, {}
    for component, declaration in declarations.items():
        binding = heads[component]; initial = binding['anchor']['initial']; pointer = binding['anchor']['pointer']; anchor = binding['projection']
        approvals[component] = core.read_namespaced_config_map(initial['name'], initial['namespace'])
        pointers[component] = core.read_namespaced_config_map(pointer['name'], pointer['namespace'])
        anchors[component] = core.read_namespaced_config_map(anchor['name'], anchor['namespace'])
        original[component] = controllers[(declaration['namespace'], declaration['name'])]
    bound = bootstrap.bind(old, approvals, policy, pointers, anchors)
    _require(bound['heads'] == heads and new.document == source.document(bound['node_configuration']['data']['config.json'])
        and new.reference.to_dict()['name'] == bound['node_configuration']['metadata']['name'],
        'Only the deterministic v3-to-v4 head authority transition is permitted')
    _require(_key(held) in maps and maps[_key(held)] == held and held.get('immutable') in (None, False)
        and _uid(held['metadata'].get('uid')) and re.fullmatch(r'[1-9][0-9]*', held['metadata'].get('resourceVersion', ''))
        and not held['metadata'].get('ownerReferences') and not held.get('binaryData')
        and set(held.get('data', {})) == {'config-ref.json', 'policy.json', 'release'}
        and held['data']['release'] == 'false' and source.document(held['data']['config-ref.json']) == new.reference.to_dict()
        and source.document(held['data']['policy.json']) == catalog, 'Actual held bootstrap must bind the exact new config/policy')
    candidates = bootstrap.runtime_candidates(old, approvals, policy, pointers, anchors)
    bindings = {c: core.read_namespaced_config_map(cm['metadata']['name'], cm['metadata']['namespace']) for c, cm in candidates.items()}
    expected = {c: patch[-1]['value'] for c, patch in bootstrap.bind_runtime(
        old, approvals, policy, pointers, anchors, bindings, original).items()}
    _one(expected['node']['template']['spec']['volumes'], 'packaged-bootstrap-input')['configMap']['name'] = held['metadata']['name']
    _require(held['metadata']['namespace'] == declarations['node']['namespace'], 'Node bootstrap must remain namespace-local')
    if seed is not None:
        meta = seed.get('metadata', {})
        _require(seed.get('apiVersion') == 'v1' and seed.get('kind') == 'Secret' and seed.get('immutable') is True
            and meta.get('namespace') == declarations['gateway']['namespace'] and _uid(meta.get('uid'))
            and isinstance(meta.get('resourceVersion'), str) and re.fullmatch(r'[1-9][0-9]*', meta['resourceVersion'])
            and isinstance(meta.get('name'), str) and bool(meta['name']) and not meta.get('ownerReferences')
            and not meta.get('deletionTimestamp'), 'Actual immutable local Gateway capture-seed identity required')
        _one(expected['gateway']['template']['spec']['volumes'], 'capture-seed')['secret']['secretName'] = meta['name']
    _require(isinstance(specs, dict) and set(specs) == COMPONENTS and specs == expected,
             'Proposed specs may add only exact head mounts and verified bootstrap/capture-seed names')
    if rows is None:
        rows = []
        for key, pinned in baseline.items():
            component = next(c for c, d in declarations.items() if d['namespace'] == key[0])
            eligible = [i for i, row in enumerate(pinned['rules']) if row.get('apiGroups') == ['']
                and row.get('resources') == ['configmaps'] and row.get('verbs') == ['get'] and row.get('resourceNames')]
            anchored = [i for i in eligible if heads[component]['anchor']['initial']['name'] in pinned['rules'][i]['resourceNames']]
            selected = anchored if anchored else eligible
            _require(len(selected) == 1, 'One independently pinned eligible head GET row per Role required')
            rows.append({'namespace': key[0], 'name': key[1], 'index': selected[0]})
    successor = deepcopy(previous)
    successor.update(version=2, node_configuration=new.reference.to_dict(), heads=deepcopy(heads),
        head_get_rows=deepcopy(rows), held_node_template_sha256=sha(specs['node']['template']))
    # Factory validates all seven selected row identities/indexes against pinned
    # rules before any captured live names are considered.
    release = ObserverRelease.from_dict(successor)
    _, authenticated = observe_head_permissions(core, release, new, policy)
    selected = {(r['namespace'], r['name']): r['index'] for r in rows}
    patches, old_roles = {}, []
    for pinned in successor['roles']:
        key = pinned['namespace'], pinned['name']; actual = roles[key]; index = selected[key]
        _require(actual['metadata']['uid'] == pinned['uid'] and mutable_rows(actual['rules']) == mutable_rows(pinned['rules']),
                 'Original Role UID/schema must survive migration')
        target = deepcopy(pinned['rules']); target[index]['resourceNames'] = sorted(set(target[index]['resourceNames']) | set(authenticated[key[0]]))
        if key[0] == old.reference.to_dict()['namespace']:
            for row in target:
                if row.get('apiGroups') == [''] and row.get('resources') == ['configmaps'] and row.get('verbs') == ['get'] and old.reference.to_dict()['name'] in row.get('resourceNames', []):
                    row['resourceNames'] = sorted(set(row['resourceNames']) | {new.reference.to_dict()['name']})
        comparison = deepcopy(actual['rules']); desired = deepcopy(actual['rules'])
        for offset, (before, after) in enumerate(zip(pinned['rules'], target)):
            if before != after:
                _require(set(before['resourceNames']) <= set(comparison[offset]['resourceNames']) <= set(after['resourceNames']),
                         'Unrelated or removed static named GET permission')
                comparison[offset]['resourceNames'] = before['resourceNames']; desired[offset]['resourceNames'] = after['resourceNames']
        old_actual = deepcopy(actual); old_actual['rules'] = deepcopy(comparison); old_roles.append(old_actual)
        for offset in mutable_rows(pinned['rules']).values(): comparison[offset]['resourceNames'] = pinned['rules'][offset]['resourceNames']
        _require(comparison == pinned['rules'], 'Unrelated live privileges cannot become a new observer baseline')
        if actual['rules'] != desired:
            meta = actual['metadata']; patches['/'.join(key)] = {'target': {field: meta[field] for field in ('namespace', 'name', 'uid', 'resourceVersion')}, 'patch': [
                {'op': 'test', 'path': '/metadata/uid', 'value': meta['uid']},
                {'op': 'test', 'path': '/metadata/resourceVersion', 'value': meta['resourceVersion']},
                {'op': 'test', 'path': '/rules', 'value': deepcopy(actual['rules'])},
                {'op': 'replace', 'path': '/rules', 'value': desired}]}
        actual['rules'] = desired; pinned['rules'] = target
    old_node = original['node']; old_volume = _one(old_node['spec']['template']['spec']['volumes'], 'packaged-bootstrap-input')
    old_reads.add((declarations['node']['namespace'], old_volume['configMap']['name']))
    old_capture = {'version': 1, 'configmaps': [maps[key] for key in sorted(old_reads)],
        'deployments': list(original.values()), 'roles': old_roles}
    source.render(previous, reviewed_sha256, catalog, old_capture, declarations['node']['image'])
    future = []
    for component, actual in original.items():
        value = deepcopy(actual); value['spec'] = deepcopy(specs[component]); future.append(value)
    prospective = {'version': 1, 'configmaps': list(maps.values()), 'deployments': future, 'roles': list(roles.values())}
    ObserverRelease.from_dict(successor)
    source.render(successor, sha(successor), catalog, prospective, declarations['node']['image'])
    return {'version': 1, 'release': successor, 'release_sha256': sha(successor), 'capture': prospective,
        'static_role_patches': patches, 'previous_release_sha256': reviewed_sha256,
        'runtime_specs_sha256': specs_hash, 'prospective': True, 'live_applied': False,
        'process_readiness_verified': False, 'actual_only_render_required': True}
