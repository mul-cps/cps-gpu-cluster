#!/usr/bin/env python3
"""Prepare private personal-Argo files from Root-staged captures; no API calls."""
import argparse
import base64
import copy
import json
import os
from pathlib import Path
import re
import ssl
import stat
import subprocess
import sys
import tempfile

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FRONTEND_IMAGE = 'ghcr.io/mul-cps/e2x-course-hub@sha256:7e1509969062bc3b0855671c12f181548494cb6095669b949e0426a5e74c2b2e'
CA_NAME = 'cps-personal-argo-upstream-ca'
ENV_NAME = 'PERSONAL_ARGO_OAUTH_CLIENT_SECRET'
CONFIG_KEY = '99-personal-argo-service'


class PreparationRejected(ValueError):
    """A fixed structural error message safe to print."""


def require(condition, message):
    if not condition:
        raise PreparationRejected(message)


def json_text(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def encoded(text):
    return base64.b64encode(text.encode()).decode()


def decoded(resource, key):
    return base64.b64decode(resource['data'][key], validate=True).decode()


def private_read(path):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and not info.st_mode & 0o077,
            'private regular file required for input captures')
    return path.read_text()


def capture(inputs, key, kind, name, namespace):
    resource = json.loads(private_read(Path(inputs[key])))
    if resource.get('kind') == 'List':
        matches = [item for item in resource['items'] if item.get('kind') == kind
                   and item.get('metadata', {}).get('name') == name
                   and item.get('metadata', {}).get('namespace') == namespace]
        require(len(matches) == 1, 'capture must select exactly one expected object')
        resource = matches[0]
    meta = resource.get('metadata', {})
    require(resource.get('kind') == kind and meta.get('name') == name
            and meta.get('namespace') == namespace, 'capture identity mismatch')
    require(all(isinstance(meta.get(k), str) and meta[k] for k in ('uid', 'resourceVersion')),
            'captured UID and resourceVersion required')
    return resource


def cas(resource):
    return [{'op': 'test', 'path': '/metadata/' + key, 'value': resource['metadata'][key]}
            for key in ('uid', 'resourceVersion')]


def secret_patch(resource, key, text):
    return cas(resource) + [{'op': 'test', 'path': '/data/' + key, 'value': resource['data'][key]},
                           {'op': 'replace', 'path': '/data/' + key, 'value': encoded(text)}]


def container(resource, name):
    pod = resource['spec']['template']['spec']
    indices = [i for i, value in enumerate(pod['containers']) if value['name'] == name]
    require(len(indices) == 1, 'expected one named container')
    index = indices[0]
    return pod, index, pod['containers'][index]


def append_patch(operations, target, path, field, entry):
    if field in target:
        require(isinstance(target[field], list), 'expected captured array')
        operations.append({'op': 'add', 'path': path + '/' + field + '/-', 'value': entry})
    else:
        operations.append({'op': 'add', 'path': path + '/' + field, 'value': [entry]})


def prepare(inputs):
    files = {}
    gateway = capture(inputs, 'gateway_deployment', 'Deployment', 'compute-gateway', 'cps-compute')
    pod, index, gateway_container = container(gateway, 'gateway')
    policy_cm = capture(inputs, 'policy_configmap', 'ConfigMap', 'compute-policy', 'cps-compute')
    require([v.get('configMap', {}).get('name') for v in pod['volumes'] if v['name'] == 'policy']
            == [policy_cm['metadata']['name']], 'policy capture does not match gateway')
    policy_json = policy_cm['data']['policy.json']
    policy = json.loads(policy_json)
    require(re.fullmatch(r'sha256:[a-f0-9]{64}', policy['policyHash']), 'captured policy hash required')
    require(re.fullmatch(r'[^@ ]+@sha256:[a-f0-9]{64}', gateway_container['image']), 'captured gateway digest required')
    runtime_secret = capture(inputs, 'gateway_runtime_secret', 'Secret', 'cps-compute-runtime', 'cps-compute')
    require([v.get('secret', {}).get('secretName') for v in pod['volumes'] if v['name'] == 'config']
            == [runtime_secret['metadata']['name']], 'runtime capture does not match gateway')
    runtime = json.loads(decoded(runtime_secret, 'runtime.json'))
    require(runtime.get('artifacts') and runtime.get('argo_ca_file'), 'existing artifact and Argo CA configuration required')
    require('argoUi' not in runtime or runtime['argoUi'] == {'enabled': False}, 'existing gateway argoUi conflicts')
    runtime.update(json.loads((HERE / 'runtime-argo-fragment.json').read_text()))
    files['gateway-runtime.patch.json'] = json_text(secret_patch(runtime_secret, 'runtime.json', json_text(runtime)))

    fragment = json.loads((HERE / 'gateway-reader-template-patch.json').read_text())['spec']['template']['spec']
    volume = fragment['volumes'][0]
    mount = fragment['containers'][0]['volumeMounts'][0]
    require(not any(v['name'] == volume['name'] for v in pod['volumes']), 'existing gateway reader volume conflicts')
    require(not any(v['name'] == mount['name'] or v['mountPath'] == mount['mountPath']
                    for v in gateway_container.get('volumeMounts', [])), 'existing gateway reader mount conflicts')
    operations = cas(gateway)
    append_patch(operations, pod, '/spec/template/spec', 'volumes', volume)
    append_patch(operations, gateway_container, '/spec/template/spec/containers/' + str(index), 'volumeMounts', mount)
    files['gateway-deployment.patch.json'] = json_text(operations)

    for source, namespace in (('cps', 'jupyterhub'), ('cit', 'cit-jhub')):
        secret = capture(inputs, source + '_hub_secret', 'Secret', 'hub', namespace)
        deployment = capture(inputs, source + '_hub_deployment', 'Deployment', 'hub', namespace)
        hub_pod, hub_index, hub_container = container(deployment, 'hub')
        if source == 'cit':
            existing = [v.get('secret', {}).get('secretName') for v in hub_pod['volumes'] if v['name'] == 'existing-secret']
            if existing:
                require(existing == ['jupyterhub-secrets'], 'unexpected CIT existing-secret reference')
                existing_secret = capture(inputs, 'cit_existing_secret', 'Secret', 'jupyterhub-secrets', namespace)
                require('values.yaml' not in existing_secret.get('data', {}), 'CIT existing-secret values override needs review')
        values = yaml.safe_load(decoded(secret, 'values.yaml'))
        hub = values['hub']
        require(isinstance(hub.get('extraConfig'), dict) and CONFIG_KEY not in hub['extraConfig'], 'existing Hub extraConfig conflicts')
        services = hub.get('config', {}).get('JupyterHub', {}).get('services', [])
        require(not any(s.get('name') == source + '-argo-ui' for s in services), 'existing Hub service conflicts')
        additions = yaml.safe_load((HERE / (source + '-hub-values-fragment.yaml')).read_text())['hub']
        entry = additions['extraEnv'][0]
        env = hub['extraEnv']
        if source == 'cps':
            require(isinstance(env, list) and not any(e.get('name') == ENV_NAME for e in env), 'CPS extraEnv list conflicts')
            env.append(copy.deepcopy(entry))
        else:
            require(isinstance(env, dict) and ENV_NAME not in env, 'CIT extraEnv dictionary conflicts')
            env[ENV_NAME] = {k: v for k, v in entry.items() if k != 'name'}
        hub['extraConfig'].update(additions['extraConfig'])
        merged_yaml = yaml.safe_dump(values, sort_keys=False)
        files[source + '-hub-values.yaml'] = merged_yaml
        files[source + '-hub-secret.patch.json'] = json_text(secret_patch(secret, 'values.yaml', merged_yaml))
        require(not any(e.get('name') == ENV_NAME for e in hub_container.get('env', [])), 'existing Hub deployment env conflicts')
        operations = cas(deployment)
        append_patch(operations, hub_container, '/spec/template/spec/containers/' + str(hub_index), 'env', entry)
        files[source + '-hub-deployment.patch.json'] = json_text(operations)

    certificates = []
    require(isinstance(inputs['ca_files'], list) and inputs['ca_files'], 'explicit public CA bundle files required')
    for path in inputs['ca_files']:
        raw = Path(path).read_text()
        ssl.create_default_context(cadata=raw)
        for certificate in re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', raw, re.S):
            if certificate not in certificates:
                certificates.append(certificate)
    require(certificates, 'CA certificate bundle required')
    ca = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': CA_NAME, 'namespace': 'cps-compute'},
          'data': {'ca.crt': '\n'.join(certificates) + '\n'}}
    values = yaml.safe_load((HERE / 'values.yaml').read_text())
    values.update(policyJson=policy_json, policyHash=policy['policyHash'])
    values['gateway']['image'] = gateway_container['image']
    values['gateway']['argoUi'].update(readerServiceAccount='cps-personal-argo-reader', readerNamespace='cps-argo')
    values['personalArgo'].update(image=FRONTEND_IMAGE, upstreamCaConfigMapRef=CA_NAME,
                                  hubCaFile='/trust/ca.crt', nativeCaFile='/trust/ca.crt')
    files['render-values.yaml'] = yaml.safe_dump(values, sort_keys=False)
    with tempfile.TemporaryDirectory(prefix='personal-argo-render-') as directory:
        render_values = Path(directory) / 'values.yaml'
        render_values.touch(mode=0o600)
        render_values.write_text(files['render-values.yaml'])
        result = subprocess.run(['helm', 'template', 'personal-argo', str(ROOT / 'platform-staging/chart'),
            '--values', str(render_values), '--show-only', 'templates/argo-ui-reader.yaml',
            '--show-only', 'templates/personal-argo.yaml'], capture_output=True, text=True, timeout=60)
        require(result.returncode == 0, 'offline Helm render failed; no files prepared')
    objects = [ca, *yaml.safe_load_all((HERE / 'network-policies.yaml').read_text()), *yaml.safe_load_all(result.stdout)]
    require(not any(o and o['kind'] == 'Ingress' for o in objects), 'nonpublic resource set required')
    files['resources.yaml'] = yaml.safe_dump_all([o for o in objects if o], sort_keys=False)
    files['reader-rbac.yaml'] = (HERE / 'reader-rbac.yaml').read_text()
    receipt = {'preparedOnly': True, 'apiCalls': False, 'frontendImage': FRONTEND_IMAGE,
               'policyHash': policy['policyHash'], 'readerServiceAccount': 'cps-argo/cps-personal-argo-reader',
               'rotationSuspended': True, 'publicIngressCreated': False, 'files': sorted(files)}
    files['receipt.json'] = json_text(receipt)
    return files, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        require(not args.output.exists(), 'fresh output directory required')
        inputs = json.loads(private_read(args.inputs))
        files, receipt = prepare(inputs)
        args.output.mkdir(mode=0o700)
        for name, contents in files.items():
            descriptor = os.open(args.output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w') as stream:
                stream.write(contents)
        print(json_text({'output': str(args.output), **receipt}), end='')
        return 0
    except PreparationRejected as error:
        print('Preparation rejected: ' + str(error), file=sys.stderr)
        return 1
    except Exception:
        print('Preparation rejected: invalid input or offline preparation failure; private contents suppressed', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
