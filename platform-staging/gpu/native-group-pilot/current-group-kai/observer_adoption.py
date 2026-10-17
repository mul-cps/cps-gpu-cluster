"""Pure, explicitly prospective observer successor for reviewed image adoption.

No API, process, file writes or release execution. Actual identities are inputs;
future controller/rule values are labelled prospective, never fresh readbacks.
"""
import copy
import importlib.util
from pathlib import Path

import image_adoption as image


def _renderer():
    path = Path(__file__).resolve().parents[3] / 'native-observer-operator' / 'render.py'
    spec = importlib.util.spec_from_file_location('current_group_observer_render', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(obj):
    return obj['metadata']['namespace'], obj['metadata']['name']


def _inventory(values, kind):
    image.require(isinstance(values, list), 'Actual API object inventory required')
    result = {}
    for obj in values:
        image._guard(obj, kind)
        key = _identity(obj)
        image.require(key not in result, 'Duplicate actual inventory identity')
        result[key] = copy.deepcopy(obj)
    return result


def _actual(candidate, actual, *, immutable):
    image._guard(actual, 'ConfigMap')
    image.require(_identity(actual) == _identity(candidate) and actual.get('data') == candidate['data']
        and not actual.get('binaryData') and not actual['metadata'].get('ownerReferences'),
        'Actual created ConfigMap differs from reviewed candidate')
    if immutable:
        image._immutable(actual)
        if candidate['metadata'].get('uid') is not None:
            image.require(actual['metadata']['uid'] == candidate['metadata']['uid'], 'Reused immutable UID changed')
    else:
        image.require(actual.get('immutable') in (None, False), 'Held bootstrap must remain mutable')


def compose(previous_release, reviewed_sha256, catalog, image_snapshot, image_plan,
            actual_node_config, actual_bootstrap, capture, *, actual_configmaps):
    """Return successor release, prospective capture and exact static GET CAS.

    Fresh captures may have either the reviewed preimage or already applied
    desired controller/static rules. Unrelated drift is never adopted. A later
    actual-only source render remains mandatory before observer activation.
    """
    try:
        return _compose(previous_release, reviewed_sha256, catalog, image_snapshot, image_plan,
                        actual_node_config, actual_bootstrap, capture, actual_configmaps)
    except (KeyError, TypeError, AttributeError, StopIteration):
        raise ValueError('Incomplete observer adoption inputs') from None


def _compose(previous_release, reviewed_sha256, catalog, snapshot, plan, node_config, bootstrap, capture, actual_configmaps):
    from cps_compute.native_observer_permissions import ObserverRelease, mutable_rows
    from cps_compute.immutable_configmap import ImmutableConfigMapRef
    image.require(image.sha(previous_release) == reviewed_sha256, 'Independently reviewed previous observer release pin required')
    previous = ObserverRelease.from_dict(previous_release).document
    expected = image.render(snapshot, plan['images'], expected_snapshot_sha256=plan['snapshot_sha256'],
                            expected_revision=plan['expected_revision'])
    image.require(plan == expected, 'Exact reviewed image adoption plan required')
    old_ref = image._parse(image.volume(snapshot, 'node', 'packaged-bootstrap-input')['data']['config-ref.json'])
    image.require(previous['node_configuration'] == old_ref, 'Old observer release differs from image baseline')
    bound = image.bind_node(snapshot, plan, node_config)
    _actual(bound['creates']['node.bootstrap'], bootstrap, immutable=False)
    image.require(bootstrap['data']['release'] == 'false', 'Actual new bootstrap must hold Node release')
    image.require(isinstance(capture, dict) and set(capture) == {'version', 'configmaps', 'deployments', 'roles'}
        and type(capture['version']) is int and capture['version'] == 1, 'Closed actual four/seven capture required')
    controllers = _inventory(capture['deployments'], 'Deployment')
    roles = _inventory(capture['roles'], 'Role')
    maps = _inventory(capture['configmaps'], 'ConfigMap')
    baseline = {(r['namespace'], r['name']): r for r in previous['roles']}
    image.require(set(roles) == set(baseline) and len(controllers) == 4, 'Exact seven Role and four controller captures required')
    # Validate the old independently reviewed baseline against the image plan's
    # actual preimages, using the existing pure source renderer, not live rules.
    source = _renderer()
    old_capture = {'version': 1, 'configmaps': [copy.deepcopy(o) for o in snapshot['objects'].values() if o['kind'] == 'ConfigMap'],
        'deployments': list(copy.deepcopy(snapshot['deployments']).values()),
        'roles': [copy.deepcopy(image._get(snapshot, 'Role', ns, name)) for ns, name in baseline]}
    source.render(previous, reviewed_sha256, catalog, old_capture, plan['images']['node'])
    candidates = {label: plan['creates'].get(label) or plan['reuses'].get(label)
                  for label in ('gateway.publisher', 'hub:cps.publisher', 'hub:cit.publisher')}
    image.require(all(candidates.values()), 'All three reviewed publisher candidates required')
    if isinstance(actual_configmaps, dict):
        labels = set(candidates)
        image.require(set(actual_configmaps) in (labels, labels | {'node-config', 'node.bootstrap'}),
                      'Closed labelled actual ConfigMap inventory required')
        actual_configmaps = list(actual_configmaps.values())
    actuals = _inventory(actual_configmaps, 'ConfigMap')
    required = {_identity(c) for c in candidates.values()}
    optional = {_identity(node_config), _identity(bootstrap)}
    image.require(required <= set(actuals) <= required | optional, 'Exactly actual publisher and optional Node/bootstrap objects required')
    for candidate in candidates.values():
        _actual(candidate, actuals[_identity(candidate)], immutable=True)
    for obj in (node_config, bootstrap):
        if _identity(obj) in actuals:
            image.require(actuals[_identity(obj)] == obj, 'Duplicate actual readbacks disagree')
        actuals[_identity(obj)] = copy.deepcopy(obj)
    for key, obj in actuals.items():
        image.require(key not in maps or maps[key] == obj, 'Captured immutable/held readback identity collision')
        maps[key] = obj
    # Only four explicit new immutable authorities may extend static GET names.
    # Pod/ReplicaSet GET rows remain independently baseline-pinned and mutable
    # solely under the existing observer's actual-process validation.
    permitted = {}
    for component in image.COMPONENTS:
        dep = snapshot['deployments'][component]
        label = component + '.role'
        record = plan['patches'][label]
        target = record['target']; role_key = target['namespace'], target['name']
        image.require(role_key in baseline, 'Image role is outside seven reviewed identities')
        old = image._get(snapshot, 'Role', *role_key)
        pinned = baseline[role_key]
        indexes = mutable_rows(pinned['rules'])
        comparison = copy.deepcopy(old['rules'])
        image.require(old['metadata']['uid'] == pinned['uid'] and mutable_rows(comparison) == indexes,
                      'Image baseline Role identity/schema changed')
        for index in indexes.values():
            comparison[index]['resourceNames'] = pinned['rules'][index]['resourceNames']
        image.require(comparison == pinned['rules'], 'Image baseline contains unreviewed static privileges')
        if component == 'node':
            old_name, new_name = old_ref['name'], node_config['metadata']['name']
        else:
            old_name = image.volume(snapshot, component, 'cps-native-approval-publisher')['metadata']['name']
            new_name = candidates[component + '.publisher']['metadata']['name']
        rows = [i for i, r in enumerate(pinned['rules']) if r['apiGroups'] == ['']
                and r['resources'] == ['configmaps'] and r['verbs'] == ['get'] and old_name in r['resourceNames']]
        image.require(len(rows) == 1, 'One existing static authority GET row required')
        index = rows[0]
        desired = copy.deepcopy(pinned['rules'])
        desired[index]['resourceNames'] = sorted(set(desired[index]['resourceNames']) | {new_name})
        # The independently regenerated image plan must request that same delta.
        planned = copy.deepcopy(record['patch'][-1]['value'])
        for mutable in indexes.values():
            planned[mutable]['resourceNames'] = pinned['rules'][mutable]['resourceNames']
        image.require(planned == desired, 'Image role delta is not the exact named authority GET')
        permitted[role_key] = index, desired
    successor = copy.deepcopy(previous)
    successor['node_configuration'] = bound['actual_node_config_ref']
    new_node_template = bound['patches']['node.deployment']['patch'][-1]['value']['template']
    successor['held_node_template_sha256'] = image.sha(new_node_template)
    patches = {}
    for pinned in successor['roles']:
        key = pinned['namespace'], pinned['name']; actual = roles[key]
        image.require(actual['metadata']['uid'] == pinned['uid'], 'Original Role UID changed')
        indexes = mutable_rows(pinned['rules'])
        image.require(mutable_rows(actual['rules']) == indexes, 'Actual Role schema changed')
        comparison = copy.deepcopy(actual['rules']); desired = copy.deepcopy(actual['rules'])
        for index in indexes.values():
            comparison[index]['resourceNames'] = pinned['rules'][index]['resourceNames']
        if key in permitted:
            index, target = permitted[key]
            old_names = set(pinned['rules'][index]['resourceNames'])
            new_names = set(target[index]['resourceNames'])
            actual_names = set(comparison[index]['resourceNames'])
            image.require(old_names <= actual_names <= new_names, 'Unrelated or removed static GET permission')
            comparison[index]['resourceNames'] = pinned['rules'][index]['resourceNames']
            desired[index]['resourceNames'] = target[index]['resourceNames']
            pinned['rules'] = copy.deepcopy(target)
        image.require(comparison == baseline[key]['rules'], 'Unrelated live static privileges cannot be adopted')
        if desired != actual['rules']:
            patches['/'.join(key)] = image._patch(actual, '/rules', desired)
        roles[key]['rules'] = desired
    expected_keys = {_identity(d) for d in snapshot['deployments'].values()}
    image.require(set(controllers) == expected_keys, 'Actual controller capture identities changed')
    for component, old in snapshot['deployments'].items():
        key = _identity(old); actual = controllers[key]
        image.require(actual['metadata']['uid'] == old['metadata']['uid'], 'Original controller UID changed')
        desired = copy.deepcopy(old['spec'])
        if component == 'node':
            desired = copy.deepcopy(bound['patches']['node.deployment']['patch'][-1]['value'])
        else:
            desired['template'] = copy.deepcopy(plan['patches'][component + '.deployment']['patch'][-1]['value'])
        allowed = [old['spec'], desired]
        if component == 'node':
            held_old = copy.deepcopy(old['spec']); held_old['replicas'] = 0
            held_new = copy.deepcopy(desired); held_new['replicas'] = 0
            allowed.extend((held_old, held_new))
        image.require(actual['spec'] in allowed, 'Actual controller differs beyond reviewed adoption')
        controllers[key]['spec'] = desired
    prospective = {'version': 1, 'configmaps': list(maps.values()),
                   'deployments': list(controllers.values()), 'roles': list(roles.values())}
    ObserverRelease.from_dict(successor)
    # Existing source renderer independently checks the prospective typed config,
    # exact controller images, seven static baselines and held Node bootstrap.
    source.render(successor, image.sha(successor), catalog, prospective, plan['images']['node'])
    return {'version': 1, 'release': successor, 'release_sha256': image.sha(successor), 'capture': prospective,
        'static_role_patches': patches, 'prospective': True, 'live_applied': False,
        'process_readiness_verified': False, 'actual_only_render_required': True,
        'previous_release_sha256': reviewed_sha256, 'image_plan_sha256': image.sha(plan),
        'permitted_static_authorities': {component: node_config['metadata']['name'] if component == 'node'
            else candidates[component + '.publisher']['metadata']['name'] for component in image.COMPONENTS}}
