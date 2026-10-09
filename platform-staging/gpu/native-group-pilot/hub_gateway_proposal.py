#!/usr/bin/env python3
"""Offline Hub/gateway patch preparation. Default invocation is inert.

Requires released cps_compute and PyYAML; never invokes a cluster API or shell.
Operator input schema: version, images {hub,gateway,notebook,gate}, gatewayUrl,
gatewayCAFile, groupSnapshotConfirmed, canonicalMappings {cps,cit}, fixturePeople
{cps,cit}, workspaces [{source,workspace,owner,server,group_id}], nodePool.
Run with --prepare --inputs PRIVATE_JSON --baselines PRIVATE_DIR --output NEW_DIR.
Output contains private credentials: directory 0700, files 0600. Baselines are
read-only. JSON patches test baseline UID/resourceVersion before every mutation.
"""
import argparse
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re

import yaml

PROFILE = 'interactive-native-pilot-5'
NAMESPACES = {'cps': 'jupyterhub', 'cit': 'cit-jhub'}
MOUNT = '/etc/cps-native-hub'


def require(value, message):
    if not value: raise ValueError(message)


def dump(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def merge_people(existing, *mappings):
    result = copy.deepcopy(existing)
    for mapping in mappings:
        require(isinstance(mapping, dict), 'Explicit canonical mapping required')
        for name, person in mapping.items():
            require(isinstance(name, str) and name and isinstance(person, str) and person,
                    'Canonical alias and person required')
            require(name not in result or result[name] == person, 'Canonical identity conflict')
            result[name] = person
    return result


def patch(baseline, operations):
    metadata = baseline['metadata']
    require(metadata.get('uid') and metadata.get('resourceVersion'), 'Pinned baseline identity required')
    return [{'op': 'test', 'path': '/metadata/uid', 'value': metadata['uid']},
            {'op': 'test', 'path': '/metadata/resourceVersion', 'value': metadata['resourceVersion']},
            *operations]


def group_scopes(workspaces):
    scopes = []
    for item in workspaces:
        server = item['owner'] + '/' + item['server']
        scopes.extend(['servers!user=' + item['owner'], 'shares!server=' + server,
                       'admin:groups!group=' + item['group_id']])
    return sorted(set(scopes))


def access_config(source, workspaces, *, group_snapshot_confirmed):
    require(group_snapshot_confirmed is True, 'Confirmed Hub group snapshot required before manage_groups change')
    owners = sorted({item['owner'] for item in workspaces})
    scopes = group_scopes(workspaces)
    observer = sorted({scope + '!user=' + owner for owner in owners
        for scope in ('read:roles:users', 'read:servers', 'admin:server_state')})
    # Login-only denial avoids JupyterHub blocked_users startup revocation.
    return f'''import inspect as _native_inspect
from jupyterhub.app import JupyterHub as _native_hub_class
_native_owners = frozenset({owners!r})
_native_auth_base = _native_hub_class.class_traits()['authenticator_class'].validate(None, c.JupyterHub.authenticator_class)
class CPSNativeLoginGuard(_native_auth_base):
    async def check_blocked_users(self, username, authentication=None):
        if username in _native_owners:
            return False
        result = super().check_blocked_users(username, authentication)
        return await result if _native_inspect.isawaitable(result) else result
    async def refresh_user(self, user, handler=None, **kwargs):
        machine_roles = getattr(getattr(user, 'orm_user', None), 'roles', ())
        if (user.name in _native_owners and not getattr(user, 'admin', False)
                and any(role.name == 'cps-workspace-kernel' for role in machine_roles)):
            return True
        result = super().refresh_user(user, handler=handler, **kwargs)
        return await result if _native_inspect.isawaitable(result) else result
c.JupyterHub.authenticator_class = CPSNativeLoginGuard
c.Authenticator.manage_groups = False
c.GenericOAuthenticator.manage_groups = False
_native_roles = [dict(role) for role in c.JupyterHub.load_roles]
_native_marker = next((role for role in _native_roles if role.get('name') == 'cps-workspace-kernel'), None)
if _native_marker is None:
    _native_marker = {{'name': 'cps-workspace-kernel', 'scopes': []}}
    _native_roles.append(_native_marker)
_native_marker['users'] = sorted(set(_native_marker.get('users', [])) | set(_native_owners))
if any(role.get('name') in ({source + '-native-group-control'!r}, {source + '-native-group-observer'!r}) for role in _native_roles):
    raise RuntimeError('Native scoped role already configured')
_native_roles.extend([{{'name': {source + '-native-group-control'!r}, 'services': [{source + '-admin'!r}], 'scopes': {scopes!r}}},
    {{'name': {source + '-native-group-observer'!r}, 'services': [{source + '-compute-observer'!r}], 'scopes': {observer!r}}}])
c.JupyterHub.load_roles = _native_roles
'''


def render(inputs, baselines):
    from cps_compute.policy import Policy
    from cps_compute.storage import binding
    require(isinstance(inputs, dict) and set(inputs) == {'version', 'images', 'gatewayUrl', 'gatewayCAFile',
        'groupSnapshotConfirmed', 'canonicalMappings', 'fixturePeople', 'workspaces', 'nodePool'},
        'Closed complete operator input schema required')
    require(type(inputs['version']) is int and inputs['version'] == 1 and inputs['groupSnapshotConfirmed'] is True,
            'Versioned inputs with confirmed group snapshot required')
    require(set(inputs['images']) == {'hub', 'gateway', 'notebook', 'gate'}
            and all(re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}', image)
                    and not image.endswith('0' * 64) for image in inputs['images'].values()),
            'Four actual pinned images required')
    workspaces = inputs['workspaces']
    require(isinstance(workspaces, list) and len(workspaces) == 3, 'Exact three-workspace pilot required')
    require(len({item['source'] + ':' + item['workspace'] for item in workspaces}) == 3,
            'Distinct source workspaces required')
    for item in workspaces:
        require(set(item) == {'source', 'workspace', 'owner', 'server', 'group_id'}
                and item['source'] in NAMESPACES
                and all(isinstance(item[key], str) and re.fullmatch(r'[a-zA-Z0-9_.-]{1,128}', item[key])
                        for key in ('workspace', 'owner', 'server', 'group_id')), 'Closed explicit workspace registration required')
    require(inputs['nodePool'] == {'node': 'k3s-wk-gpu2',
        'node_uid': '3336cdd5-d245-436e-b57c-2f66c6dcaa41',
        'gpu_uuid': 'GPU-16128952-b438-556a-00bb-93039ee24e56', 'max_workspaces': 2}, 'Exact approved GPU2 pool required')
    policy_cm = baselines['policy']; catalog = json.loads(policy_cm['data']['policy.json'])
    require(PROFILE not in catalog['profiles'], 'Pilot profile already exists')
    profile = copy.deepcopy(catalog['profiles']['interactive-shared-5'])
    profile.update(enabled=False, cpu='4', memory='16Gi', images=[inputs['images']['notebook']],
                   kind='interactive', queue='interactive')
    profile.pop('qualificationRequired', None)
    profile['gpu'] = {'mode': 'shared', 'nominalMemoryGiB': 5,
        'qualification': {'mechanism': 'r615-native-cgroup-managed-deny', 'status': 'pilot-unqualified'}}
    catalog['profiles'][PROFILE] = profile
    catalog.pop('policyHash', None)
    catalog['policyHash'] = 'sha256:' + hashlib.sha256(dump(catalog).encode()).hexdigest()
    Policy(catalog).native_pilot_resources(PROFILE)
    runtime_secret = baselines['runtime']; runtime = json.loads(base64.b64decode(runtime_secret['data']['runtime.json']))
    runtime['policy_hash'] = catalog['policyHash']
    runtime['nativeGpuPilot'] = {'enabled': True,
        'native_pilot_workspaces': {item['source'] + ':' + item['workspace']: {'profile': PROFILE} for item in workspaces},
        'node_pool': inputs['nodePool'], 'authorityNamespace': 'cps-native-system'}
    result = {'compute-policy.patch.json': patch(policy_cm, [{'op': 'replace', 'path': '/data/policy.json', 'value': dump(catalog)}])}
    summary = {'profile': PROFILE, 'policyHash': catalog['policyHash'], 'images': inputs['images'], 'hubs': {}}
    if 'gatewayCA' in baselines:
        ca_baseline = baselines['gatewayCA']
        require(ca_baseline.get('kind') == 'ConfigMap'
                and ca_baseline.get('metadata', {}).get('name') == 'cps-compute-gateway-ca'
                and ca_baseline.get('metadata', {}).get('namespace') == 'cps-compute',
                'Exact captured gateway trust ConfigMap required')
        ca = ca_baseline['data']['ca.crt']
    else:
        ca = Path(inputs['gatewayCAFile']).read_text()
    import ssl
    ssl.create_default_context(cadata=ca)
    for source, namespace in NAMESPACES.items():
        selected = [item for item in workspaces if item['source'] == source]
        require(bool(selected), 'Both Hubs require explicit pilot workspaces')
        people = merge_people(runtime['hubs'][source]['canonical_people'],
                              inputs['canonicalMappings'][source], inputs['fixturePeople'][source])
        owners = sorted({item['owner'] for item in selected})
        require(not set(owners).intersection(people), 'Neutral owner cannot be a canonical human')
        runtime['hubs'][source]['canonical_people'] = people
        claims = sorted({'cps-workspace-' + binding(source, item['group_id'])[0][:40] for item in selected})
        token_env = runtime['service_token_envs'][source]
        encoded_token = baselines['gatewaySecret']['data'][token_env]
        require(bool(base64.b64decode(encoded_token)), 'Existing source control token required')
        settings = {'enabled': True, 'policyPath': MOUNT + '/policy.json', 'source': source,
            'gatewayUrl': inputs['gatewayUrl'], 'gatewayCAFile': MOUNT + '/ca.crt',
            'serviceTokenEnv': token_env, 'profiles': [PROFILE],
            'workspaces': [source + ':' + item['workspace'] for item in selected], 'owners': owners,
            'gateImage': inputs['images']['gate'], 'workloadImages': [inputs['images']['notebook']],
            'writablePVCClaims': claims, 'writableMountPaths': ['/workspace'], 'readonlyNFS': [],
            'canonicalMappingPath': MOUNT + '/canonical-people.json', 'groupShareTokenCompatibility': True}
        cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': 'cps-native-hub-config', 'namespace': namespace},
            'immutable': True, 'data': {'settings.json': dump(settings), 'policy.json': dump(catalog),
                'canonical-people.json': dump(people), 'ca.crt': ca}}
        secret = {'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'cps-native-hub-control', 'namespace': namespace},
                  'immutable': True, 'type': 'Opaque', 'data': {token_env: encoded_token}}
        result[namespace + '-config.json'] = cm; result[namespace + '-control-secret.json'] = secret
        old_secret = baselines[source]['secret']
        values = yaml.safe_load(base64.b64decode(old_secret['data']['values.yaml']))
        auth_config = values['hub'].get('config', {})
        require(not any(set(owners).intersection(auth_config.get(name, {}).get('blocked_users', []))
                        for name in ('Authenticator', 'GenericOAuthenticator')),
                'Neutral owners cannot already be startup-revoked blocked users')
        extras = values['hub']['extraConfig']
        require(not any(key in extras for key in ('zy-native-group-access', 'zz-native-group-pilot')), 'Native configuration collision')
        extras['zy-native-group-access'] = access_config(source, selected, group_snapshot_confirmed=inputs['groupSnapshotConfirmed'])
        extras['zz-native-group-pilot'] = "import json\nfrom pathlib import Path\nfrom cps_compute.native_hub_config import install_native_hub_configuration\ninstall_native_hub_configuration(c, json.loads(Path('/etc/cps-native-hub/settings.json').read_text()))\n"
        encoded_values = base64.b64encode(yaml.safe_dump(values, sort_keys=False).encode()).decode()
        result[namespace + '-hub-secret.patch.json'] = patch(old_secret, [{'op': 'replace', 'path': '/data/values.yaml', 'value': encoded_values}])
        deployment = baselines[source]['deployment']; spec = deployment['spec']['template']['spec']
        index = next(i for i, c in enumerate(spec['containers']) if c['name'] == 'hub')
        container = spec['containers'][index]
        require(not any(volume['name'] == 'cps-native-hub-config' for volume in spec['volumes']), 'Native volume collision')
        operations = [{'op': 'replace', 'path': f'/spec/template/spec/containers/{index}/image', 'value': inputs['images']['hub']},
            {'op': 'add', 'path': '/spec/template/spec/volumes/-', 'value': {'name': 'cps-native-hub-config', 'configMap': {'name': cm['metadata']['name']}}},
            {'op': 'add', 'path': f'/spec/template/spec/containers/{index}/volumeMounts/-', 'value': {'name': 'cps-native-hub-config', 'mountPath': MOUNT, 'readOnly': True}},
            {'op': 'add', 'path': f'/spec/template/spec/containers/{index}/env/-', 'value': {'name': token_env, 'valueFrom': {'secretKeyRef': {'name': secret['metadata']['name'], 'key': token_env}}}}]
        require(not any(env['name'] == token_env for env in container.get('env', [])), 'Source token environment collision')
        result[namespace + '-hub.patch.json'] = patch(deployment, operations)
        summary['hubs'][source] = {'owners': owners, 'groups': sorted({item['group_id'] for item in selected}),
            'controlScopes': group_scopes(selected), 'claims': claims, 'settingsFields': sorted(settings),
            'personalConfigurationPreserved': True, 'neutralLoginGuard': True,
            'neutralMachineRefreshScoped': True, 'manageGroups': False}
    result['runtime-secret.patch.json'] = patch(runtime_secret, [{'op': 'replace', 'path': '/data/runtime.json',
        'value': base64.b64encode(dump(runtime).encode()).decode()}])
    gateway = baselines['gateway']; index = next(i for i, c in enumerate(gateway['spec']['template']['spec']['containers']) if c['name'] == 'gateway')
    result['gateway.patch.json'] = patch(gateway, [{'op': 'replace', 'path': f'/spec/template/spec/containers/{index}/image', 'value': inputs['images']['gateway']}])
    result['public-summary.json'] = summary
    return result


def prepare(inputs_path, baseline_directory, output):
    root = Path(baseline_directory); output = Path(output)
    require(not output.exists() and not output.is_symlink(), 'New private proposal directory required')
    read = lambda name: json.loads((root / name).read_text())
    baselines = {'policy': read('cps-compute-compute-policy-baseline.json'),
        'runtime': read('cps-compute-runtime-secret-baseline.json'),
        'gateway': read('cps-compute-compute-gateway-baseline.json'),
        'gatewaySecret': read('gateway-secret-baseline.json')}
    for source, namespace in NAMESPACES.items():
        baselines[source] = {'deployment': read(namespace + '-hub-baseline.json'),
                             'secret': read(namespace + '-hub-secret-baseline.json')}
    if (root / 'gateway-ca-baseline.json').is_file():
        baselines['gatewayCA'] = read('gateway-ca-baseline.json')
    proposals = render(json.loads(Path(inputs_path).read_text()), baselines)
    output.mkdir(mode=0o700)
    for name, value in proposals.items():
        fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream: stream.write(json.dumps(value, indent=2) + '\n')
    return {'prepared': True, 'output': str(output), 'files': sorted(proposals), 'activationPerformed': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--inputs'); parser.add_argument('--baselines'); parser.add_argument('--output')
    args = parser.parse_args(argv)
    if not args.prepare:
        print(json.dumps({'prepared': False, 'activationPerformed': False})); return
    require(all((args.inputs, args.baselines, args.output)), 'Explicit private input, baseline and new output paths required')
    print(json.dumps(prepare(args.inputs, args.baselines, args.output)))


if __name__ == '__main__': main()
