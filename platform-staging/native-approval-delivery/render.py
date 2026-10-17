"""Pure opt-in runtime renderer for the installed dynamic-head producer.

Root supplies actual typed authority and separately bootstraps pointer/anchor
objects. Admission bounds writes; the SDK owns payload authentication and full
UID/RV/data/rules CAS. No API, credential read, or deployment occurs here.
"""
from copy import deepcopy
import json
from pathlib import PurePosixPath
import re
from urllib.parse import urlsplit

NAME = 'cps-native-head-delivery'
INPUTS = '/inputs/delivery'
APPROVAL_NAME = '^cps-native-approvals-[0-9a-f]{16}$'
POLICY_RULE_FIELDS = ('apiGroups', 'resources', 'verbs', 'resourceNames', 'nonResourceURLs')


def require(value, message):
    if not value: raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def _static_rule_equal(path, rule):
    # Admission supplies typed PolicyRule objects, not maps. Freeze every
    # field explicitly, including absence, in both object and oldObject.
    return ['has(' + path + '.' + field + ') && ' + path + '.' + field + ' == ' + canonical(rule[field])
        if field in rule else '!has(' + path + '.' + field + ')' for field in POLICY_RULE_FIELDS]


def _metadata_unchanged():
    fields = ('labels', 'annotations', 'ownerReferences', 'finalizers', 'generateName',
              'deletionTimestamp', 'deletionGracePeriodSeconds')
    return ' && '.join('has(object.metadata.' + field + ') == has(oldObject.metadata.' + field + ') && '
        '(!has(oldObject.metadata.' + field + ') || object.metadata.' + field + ' == oldObject.metadata.' + field + ')'
        for field in fields)


def _policies(config, namespace):
    actor = 'system:serviceaccount:' + namespace + ':' + NAME
    targets = [h['anchor']['pointer'] for h in config['observer_release']['heads'].values()]
    namespaces = sorted(t['namespace'] for t in targets)
    def obj(kind, name, **fields):
        return {'apiVersion': 'admissionregistration.k8s.io/v1', 'kind': kind,
                'metadata': {'name': name}, **fields}
    def policy(suffix, group, resource, operation, selected, expressions):
        name = NAME + suffix
        return [obj('ValidatingAdmissionPolicy', name, spec={'failurePolicy': 'Fail',
            'matchConstraints': {'resourceRules': [{'apiGroups': [group], 'apiVersions': ['v1'],
                'resources': [resource], 'operations': [operation]}]},
            'matchConditions': [{'name': 'bounded-writer-or-protected-target', 'expression': selected}],
            'validations': [{'expression': expression, 'message': 'Only the reviewed dynamic delivery write is permitted'}
                for expression in expressions]}), obj('ValidatingAdmissionPolicyBinding', name,
                    spec={'policyName': name, 'validationActions': ['Deny']})]
    writer = 'request.userInfo.username == ' + canonical(actor)
    selected = ' || '.join('(request.namespace == ' + canonical(p['namespace']) +
        ' && object.metadata.name == ' + canonical(p['name']) + ')' for p in targets)
    identity = ' || '.join('(request.namespace == ' + canonical(p['namespace']) +
        ' && object.metadata.namespace == request.namespace && oldObject.metadata.namespace == request.namespace'
        ' && object.metadata.name == ' + canonical(p['name']) + ' && oldObject.metadata.name == object.metadata.name'
        ' && object.metadata.uid == ' + canonical(p['uid']) + ' && oldObject.metadata.uid == object.metadata.uid'
        ' && object.data["head.json"].contains(' + canonical('"namespace":' + canonical(p['namespace'])) + '))'
        for p in targets)
    pointer = policy('-pointer-update', '', 'configmaps', 'UPDATE', '(' + writer + ') || (' + selected + ')', [
        writer, 'has(object.data) && size(object.data) == 1 && "head.json" in object.data',
        '(!has(object.immutable) || object.immutable == false) && (!has(object.binaryData) || size(object.binaryData) == 0)',
        '(!has(object.metadata.ownerReferences) || size(object.metadata.ownerReferences) == 0) && !has(object.metadata.deletionTimestamp)',
        'size(object.data["head.json"]) <= 8192 && object.data["head.json"].startsWith("{\\"generation\\":")'
            ' && object.data["head.json"].endsWith(",\\"version\\":1}")',
        identity, _metadata_unchanged()])
    create_target = ('(request.namespace in ' + canonical(namespaces) +
        ' && object.metadata.name.matches(' + canonical(APPROVAL_NAME) + '))')
    create = policy('-approval-create', '', 'configmaps', 'CREATE', '(' + writer + ') || ' + create_target, [
        writer, 'request.namespace in ' + canonical(namespaces) + ' && object.metadata.namespace == request.namespace',
        'object.metadata.name.matches(' + canonical(APPROVAL_NAME) + ') && has(object.immutable) && object.immutable == true',
        'has(object.data) && size(object.data) == 1 && "approval.json" in object.data'
            ' && size(object.data["approval.json"]) <= 1048576'
            ' && object.data["approval.json"].startsWith("{\\"history\\":[")'
            ' && object.data["approval.json"].endsWith(",\\"version\\":2}")',
        '(!has(object.binaryData) || size(object.binaryData) == 0)'
            ' && (!has(object.metadata.ownerReferences) || size(object.metadata.ownerReferences) == 0)'
            ' && (!has(object.metadata.labels) || size(object.metadata.labels) == 0)'
            ' && (!has(object.metadata.annotations) || size(object.metadata.annotations) == 0)'
            ' && (!has(object.metadata.finalizers) || size(object.metadata.finalizers) == 0)'
            ' && (!has(object.metadata.generateName) || object.metadata.generateName == "")'
            ' && !has(object.metadata.deletionTimestamp)'])
    selected_roles = ' || '.join('(request.namespace == ' + canonical(r['namespace']) +
        ' && object.metadata.name == ' + canonical(r['name']) + ')' for r in config['pregrant_roles'])
    cases = []
    for row in config['pregrant_roles']:
        index = row['index']; current = 'object.rules[' + str(index) + ']'; old = 'oldObject.rules[' + str(index) + ']'
        conditions = ['request.namespace == ' + canonical(row['namespace']),
            'object.metadata.namespace == request.namespace', 'oldObject.metadata.namespace == request.namespace',
            'object.metadata.name == ' + canonical(row['name']), 'oldObject.metadata.name == object.metadata.name',
            'object.metadata.uid == ' + canonical(row['uid']), 'oldObject.metadata.uid == object.metadata.uid',
            'size(object.rules) == ' + str(len(row['rules'])), 'size(oldObject.rules) == ' + str(len(row['rules']))]
        for offset, rule in enumerate(row['rules']):
            require(isinstance(rule, dict) and set(rule) <= set(POLICY_RULE_FIELDS), 'Closed PolicyRule baseline required')
            if offset != index:
                for prefix in ('object', 'oldObject'):
                    conditions.extend(_static_rule_equal(prefix + '.rules[' + str(offset) + ']', rule))
        for rule in (current, old):
            conditions.extend([rule + '.apiGroups == [""]', rule + '.resources == ["configmaps"]',
                rule + '.verbs == ["get"]', '(!has(' + rule + '.nonResourceURLs) || size(' + rule + '.nonResourceURLs) == 0)',
                'has(' + rule + '.resourceNames) && size(' + rule + '.resourceNames) > 0 && size(' + rule + '.resourceNames) <= 128',
                canonical(row['rules'][index]['resourceNames']) + '.all(n, n in ' + rule + '.resourceNames)'])
        conditions.extend([old + '.resourceNames.all(n, n in ' + current + '.resourceNames)',
            current + '.resourceNames.all(n, n in ' + old + '.resourceNames || n.matches(' + canonical(APPROVAL_NAME) + '))',
            current + '.resourceNames.all(n, ' + current + '.resourceNames.filter(other, other == n).size() == 1)'])
        cases.append('(' + ' && '.join(conditions) + ')')
    pregrant = policy('-pregrant-update', 'rbac.authorization.k8s.io', 'roles', 'UPDATE',
        '(' + writer + ') || (' + selected_roles + ')', [writer, '(' + ' || '.join(cases) + ')', _metadata_unchanged()])
    return pointer + create + pregrant


# The reviewed legacy inode/lock checks are retained for a NEW PVC child only.
JOURNAL_PRIVATE_INIT = """
import fcntl
import stat

def require_private(value):
    if not value:
        raise ValueError('Owned recognized delivery journal required')

parent = os.open('/journal', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
directory = None
files = {}
try:
    try:
        os.mkdir('head-delivery', mode=0o700, dir_fd=parent)
    except FileExistsError:
        pass
    directory = os.open('head-delivery', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    info = os.fstat(directory)
    require_private(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) in (0o700, 0o770, 0o2700, 0o2770))
    names = os.listdir(directory)
    require_private(set(names) <= {'state.json', 'lock', 'anchor.json', 'legacy-state.json', 'legacy-seed.json',
        'state.json.new', 'anchor.json.new', 'legacy-state.json.new', 'legacy-seed.json.new'})
    for name in names:
        observed = os.stat(name, dir_fd=directory, follow_symlinks=False)
        require_private(stat.S_ISREG(observed.st_mode) and observed.st_uid == os.getuid()
            and observed.st_nlink == 1 and stat.S_IMODE(observed.st_mode) in (0o600, 0o660))
        handle = os.open(name, os.O_RDWR | os.O_NOFOLLOW, dir_fd=directory)
        files[name] = handle
        current = os.fstat(handle)
        require_private((current.st_dev, current.st_ino) == (observed.st_dev, observed.st_ino)
            and stat.S_ISREG(current.st_mode) and current.st_uid == os.getuid() and current.st_nlink == 1
            and stat.S_IMODE(current.st_mode) in (0o600, 0o660))
    if 'lock' in files:
        fcntl.flock(files['lock'], fcntl.LOCK_EX | fcntl.LOCK_NB)
    require_private(set(os.listdir(directory)) == set(names))
    current = os.stat('head-delivery', dir_fd=parent, follow_symlinks=False)
    require_private((current.st_dev, current.st_ino) == (info.st_dev, info.st_ino))
    for name, handle in files.items():
        current = os.stat(name, dir_fd=directory, follow_symlinks=False)
        opened = os.fstat(handle)
        require_private((current.st_dev, current.st_ino) == (opened.st_dev, opened.st_ino)
            and stat.S_ISREG(current.st_mode) and current.st_nlink == 1)
    # Validate every inode before repairing any mode. Never read, rewrite,
    # unlink or traverse journal contents or change the PVC mount root.
    for handle in files.values():
        os.fchmod(handle, 0o600)
        os.fsync(handle)
    os.fchmod(directory, 0o700)
    os.fsync(directory)
    os.fsync(parent)
finally:
    for handle in files.values():
        os.close(handle)
    if directory is not None:
        os.close(directory)
    os.close(parent)
"""


def render(config, *, configuration, image, config_secret, journal_pvc, namespace='cps-compute', image_pull_secret=None):
    from cps_compute.native_node.config import NodeConfiguration
    from cps_compute.native_observer_permissions import ObserverRelease, names, valid_uid
    require(isinstance(config, dict) and set(config) == {'version', 'enabled', 'policy_path', 'node_configuration',
        'observer_release', 'pregrant_roles', 'capture', 'ttlSeconds'} and type(config['version']) is int
        and config['version'] == 1 and config['enabled'] is True, 'Explicit closed enabled producer config v1 required')
    require(type(configuration) is NodeConfiguration and configuration.document['version'] == 4,
            'Actual immutable NodeConfiguration v4 required')
    release = ObserverRelease.from_dict(config['observer_release']).document
    require(release['version'] == 2 and config['node_configuration'] == release['node_configuration']
        == configuration.reference.to_dict() and release['heads']['node'] == configuration.approval_head,
        'Producer, observer and actual Node configuration must agree')
    declarations = configuration.document['component_declarations']
    require(all(release['heads'][c]['anchor']['pointer']['namespace'] == d['namespace'] for c, d in declarations.items()),
            'All four immutable bindings must be component-local')
    namespaces = {d['namespace'] for d in declarations.values()}
    require(len(namespaces) == 4 and isinstance(config['pregrant_roles'], list) and len(config['pregrant_roles']) == 4,
            'Four exact observer pregrant Role baselines required')
    seen = set()
    for row in config['pregrant_roles']:
        require(isinstance(row, dict) and set(row) == {'namespace', 'name', 'uid', 'index', 'rules'}
            and row['namespace'] in namespaces and row['namespace'] not in seen
            and row['name'] == 'cps-native-observer-operator' and valid_uid(row['uid'])
            and isinstance(row['rules'], list) and 1 <= len(row['rules']) <= 32 and type(row['index']) is int
            and 0 <= row['index'] < len(row['rules']), 'Exact four original observer Role identities/rows required')
        seen.add(row['namespace']); selected = row['rules'][row['index']]
        require(isinstance(selected, dict) and set(selected) == {'apiGroups', 'resources', 'verbs', 'resourceNames'}
            and (selected['apiGroups'], selected['resources'], selected['verbs']) == ([''], ['configmaps'], ['get']),
            'Only one named core ConfigMap GET row may grow')
        names(selected['resourceNames'])
    require(type(config['ttlSeconds']) is int and 15 <= config['ttlSeconds'] <= 120, 'Bounded receipt TTL required')
    capture = config['capture']
    require(isinstance(capture, dict) and set(capture) == {'origin', 'ca_file', 'token_file'}, 'Closed capture transport required')
    origin = urlsplit(capture['origin'])
    require(origin.scheme == 'https' and origin.hostname and origin.username is None and origin.password is None
        and origin.path == '' and not origin.query and not origin.fragment
        and '?' not in capture['origin'] and '#' not in capture['origin']
        and not any(c.isspace() for c in capture['origin'])
        and (origin.port is None or 1 <= origin.port <= 65535), 'Explicit authenticated HTTPS capture origin required')
    paths = [config['policy_path'], capture['ca_file'], capture['token_file']]
    require(all(isinstance(p, str) and str(PurePosixPath(p).parent) == INPUTS
        and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', PurePosixPath(p).name) for p in paths)
        and len(set(paths)) == 3 and INPUTS + '/delivery.json' not in paths, 'Three distinct private input files required')
    require(isinstance(image, str) and re.fullmatch(r'ghcr.io/mul-cps/cps-compute@sha256:[a-f0-9]{64}', image)
        and image.rsplit(':', 1)[1] != '0' * 64,
            'Qualified immutable installed SDK image required')
    for value in (namespace, config_secret, journal_pvc):
        require(isinstance(value, str) and re.fullmatch(r'[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?', value), 'Canonical runtime identity required')
    if image_pull_secret is not None:
        require(isinstance(image_pull_secret, str) and re.fullmatch(r'[a-z0-9](?:[-a-z0-9]{0,61}[a-z0-9])?', image_pull_secret), 'Canonical pull Secret reference required')
    def obj(kind, name, ns, **fields):
        version = 'apps/v1' if kind == 'Deployment' else 'rbac.authorization.k8s.io/v1' if kind in ('Role', 'RoleBinding') else 'v1'
        return {'apiVersion': version, 'kind': kind, 'metadata': {'namespace': ns, 'name': name}, **fields}
    subject = {'kind': 'ServiceAccount', 'namespace': namespace, 'name': NAME}
    result = [obj('ServiceAccount', NAME, namespace)]
    for component, declaration in declarations.items():
        ns = declaration['namespace']; pointer = release['heads'][component]['anchor']['pointer']
        result += [obj('Role', NAME, ns, rules=[
            {'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['get', 'create']},
            {'apiGroups': [''], 'resources': ['configmaps'], 'verbs': ['patch'], 'resourceNames': [pointer['name']]},
            {'apiGroups': ['apps'], 'resources': ['deployments'], 'verbs': ['get'], 'resourceNames': [declaration['name']]},
            {'apiGroups': [''], 'resources': ['serviceaccounts'], 'verbs': ['get'], 'resourceNames': [declaration['service_account']]},
            {'apiGroups': [''], 'resources': ['pods'], 'verbs': ['get']},
            {'apiGroups': ['apps'], 'resources': ['replicasets'], 'verbs': ['get']},
            {'apiGroups': ['rbac.authorization.k8s.io'], 'resources': ['roles'], 'verbs': ['get', 'patch', 'escalate'],
                'resourceNames': ['cps-native-observer-operator']}]),
            obj('RoleBinding', NAME, ns, subjects=[deepcopy(subject)], roleRef={
                'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': NAME})]
    result += _policies(config, namespace)
    files = ['delivery.json'] + [PurePosixPath(p).name for p in paths]
    code = "from pathlib import Path; import os; p=Path('/inputs/delivery'); p.mkdir(mode=0o700); " + \
        "[(p.joinpath(n).write_bytes(Path('/seed').joinpath(n).read_bytes()),os.chmod(p/n,0o600)) for n in " + repr(files) + "]\n" + JOURNAL_PRIVATE_INIT
    security = {'runAsNonRoot': True, 'runAsUser': 1000, 'runAsGroup': 1000, 'allowPrivilegeEscalation': False,
                'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}}
    pod = {'serviceAccountName': NAME, 'securityContext': {'fsGroup': 1000, 'fsGroupChangePolicy': 'OnRootMismatch',
        'seccompProfile': {'type': 'RuntimeDefault'}}, 'initContainers': [{'name': 'private-inputs', 'image': image,
            'command': ['python', '-I', '-B', '-c', code], 'securityContext': deepcopy(security), 'volumeMounts': [
                {'name': 'seed', 'mountPath': '/seed', 'readOnly': True}, {'name': 'inputs', 'mountPath': '/inputs'},
                {'name': 'journal', 'mountPath': '/journal'}]}], 'containers': [{'name': 'delivery', 'image': image,
            'command': ['python', '-I', '-B', '-m', 'cps_compute.native_approval_delivery'],
            'args': ['--config', '/inputs/delivery/delivery.json', '--state-dir', '/journal/delivery', '--execute'],
            'securityContext': deepcopy(security), 'resources': {'requests': {'cpu': '50m', 'memory': '128Mi'},
                'limits': {'cpu': '500m', 'memory': '512Mi'}}, 'volumeMounts': [
                {'name': 'inputs', 'mountPath': '/inputs', 'readOnly': True},
                {'name': 'journal', 'mountPath': '/journal/delivery', 'subPath': 'head-delivery'},
                {'name': 'tmp', 'mountPath': '/tmp'}]}], 'volumes': [
        {'name': 'seed', 'secret': {'secretName': config_secret, 'defaultMode': 0o444}},
        {'name': 'inputs', 'emptyDir': {}}, {'name': 'journal', 'persistentVolumeClaim': {'claimName': journal_pvc}},
        {'name': 'tmp', 'emptyDir': {}}]}
    if image_pull_secret is not None: pod['imagePullSecrets'] = [{'name': image_pull_secret}]
    result.append(obj('Deployment', NAME, namespace, spec={'replicas': 0, 'strategy': {'type': 'Recreate'},
        'selector': {'matchLabels': {'app': NAME}}, 'template': {'metadata': {'labels': {'app': NAME}}, 'spec': pod}}))
    return result


if __name__ == '__main__':
    print(canonical({'enabled': False, 'api_calls': False, 'gpu_calls': False}))
