#!/usr/bin/env python3
"""Bounded, isolated live qualification; generated credentials never leave Secrets."""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import secrets
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

import yaml

ROOT = Path(__file__).resolve().parents[4]
NS = 'cps-personal-argo-qualification-20261008'
COMPUTE = 'ghcr.io/mul-cps/cps-compute@sha256:74cfb93dcf0078c116b88662b19b6ef14611f616e34ae3141f1fd24ceb3e12ce'
FRONTEND = 'ghcr.io/mul-cps/e2x-course-hub@sha256:ead8754358daf3fe0462f2d9990eea9ab04c2078b8d1b20b0d256ff1d038e272'


def command(args, *, payload=None):
    result = subprocess.run(args, input=payload, capture_output=True, text=True)
    if result.returncode:
        # Never include kubectl request bodies or generated credentials in errors.
        raise RuntimeError(f'{args[0]} {args[1]} failed with exit {result.returncode}')
    return result.stdout


def apply(objects):
    return command(['kubectl', 'apply', '-f', '-'], payload=yaml.safe_dump_all(objects))


def get(kind, name, namespace=NS):
    return json.loads(command(['kubectl', '-n', namespace, 'get', kind, name, '-o', 'json']))


def metadata(name):
    return {'name': name, 'namespace': NS}


def render(chart_root=ROOT):
    policy = json.loads((ROOT / 'compute-policy/generated/policy.json').read_text())
    values = {
        'enabled': True, 'namespace': NS, 'policyJson': json.dumps(policy), 'policyHash': policy['policyHash'],
        'gateway': {'image': COMPUTE, 'argoUi': {'enabled': True, 'readerNamespace': NS,
                    'readerServiceAccount': 'scratch-reader', 'readerSecretRef': 'scratch-reader-token'}},
        'consoles': {source: {'image': FRONTEND, 'publicCallbackUrl': f'https://{source}.invalid/services/{source}-admin/oauth_callback'} for source in ('cps', 'cit')},
        'personalArgo': {'enabled': True, 'image': FRONTEND,
            'nativeUrl': 'https://jupyterhub.dshl.unileoben.ac.at/argo',
            'nativeCaFile': '/etc/ssl/certs/ca-certificates.crt', 'upstreamCaConfigMapRef': 'scratch-compute-ca',
            'sources': {'cps': {'enabled': True, 'publicOrigin': 'https://jupyterhub.dshl.unileoben.ac.at',
                'hubApiUrl': 'https://jupyterhub.dshl.unileoben.ac.at/hub/api',
                'secretRef': 'scratch-cps-oauth', 'ingress': {'enabled': False}}, 'cit': {'enabled': False}}}}
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml') as handle:
        yaml.safe_dump(values, handle); handle.flush()
        rendered = command(['helm', 'template', 'scratch-personal', str(chart_root / 'platform-staging/chart'),
                            '-f', handle.name, '--show-only', 'templates/argo-ui-reader.yaml',
                            '--show-only', 'templates/personal-argo.yaml'])
    objects = [obj for obj in yaml.safe_load_all(rendered) if obj]
    assert all(obj['metadata']['namespace'] == NS for obj in objects)
    assert not any(obj['kind'] == 'Ingress' for obj in objects)
    cron = next(obj for obj in objects if obj['kind'] == 'CronJob')
    cron['metadata']['annotations'] = {'qualification.cps/rotator-template-sha256':
        hashlib.sha256((chart_root / 'platform-staging/chart/templates/argo-ui-reader.yaml').read_bytes()).hexdigest()}
    return objects


PROBE = r'''
import base64, json, time
from pathlib import Path
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
config.load_incluster_config()
api = client.CoreV1Api()
result = {}
def denied(name, call):
    try:
        call()
    except ApiException as error:
        assert error.status == 403, name + ': unexpected status'
        result[name] = 403
    else:
        raise AssertionError(name + ': unexpectedly authorized')
def projected(expected):
    for _ in range(90):
        if Path('/reader/token').read_text().strip() == expected:
            return
        time.sleep(1)
    raise AssertionError('Secret projection did not update within 90 seconds')
try:
    exec(ROTATOR_CODE)
    result['chart_rotator_unmodified'] = 'passed'
except AttributeError as error:
    assert str(error) == "module 'kubernetes.client' has no attribute 'V1TokenRequest'"
    result['chart_rotator_unmodified'] = 'failed-unsupported-client-model'
    ROTATOR_CODE = ROTATOR_CODE.replace(
        'client.V1TokenRequest(spec=client.V1TokenRequestSpec(audiences=[], expiration_seconds=900))',
        "{'apiVersion': 'authentication.k8s.io/v1', 'kind': 'TokenRequest', 'spec': {'audiences': [], 'expirationSeconds': 900}}")
    result['protocol_probe_correction'] = 'TokenRequest request dictionary only'
    exec(ROTATOR_CODE)
first = token
projected(first)
reader_config = client.Configuration.get_default_copy()
reader_config.refresh_api_key_hook = None
reader_config.api_key['authorization'] = first
reader_config.api_key_prefix['authorization'] = 'Bearer'
reader_api = client.CoreV1Api(client.ApiClient(reader_config))
assert reader_api.read_namespaced_config_map('reader-proof', NAMESPACE, _request_timeout=(5,15)).data['proof'] == 'scratch-only'
result['issued_reader_token_authenticated'] = True
claims = json.loads(base64.urlsafe_b64decode(first.split('.')[1] + '==='))
assert claims['sub'] == 'system:serviceaccount:' + NAMESPACE + ':scratch-reader'
assert claims['exp'] - claims['iat'] <= 900
result['token_lifetime_seconds'] = claims['exp'] - claims['iat']
time.sleep(2)
exec(ROTATOR_CODE)
second = token
assert second != first
projected(second)
result['secret_credential_rotated_and_projected'] = True
reader_config.api_key['authorization'] = second
reader_api = client.CoreV1Api(client.ApiClient(reader_config))
assert reader_api.read_namespaced_config_map('reader-proof', NAMESPACE, _request_timeout=(5,15)).data['proof'] == 'scratch-only'
result['rotated_token_authenticated'] = True
request = {'apiVersion':'authentication.k8s.io/v1','kind':'TokenRequest','spec':{'audiences':[],'expirationSeconds':900}}
denied('extra_serviceaccount_token_request', lambda: api.create_namespaced_service_account_token('scratch-extra-reader', NAMESPACE, request, _request_timeout=(5,15)))
denied('extra_secret_read', lambda: api.read_namespaced_secret('scratch-extra-secret', NAMESPACE, _request_timeout=(5,15)))
denied('extra_secret_patch', lambda: api.patch_namespaced_secret('scratch-extra-secret', NAMESPACE, {'metadata':{'annotations':{'denied':'true'}}}, _request_timeout=(5,15)))
denied('target_secret_read', lambda: api.read_namespaced_secret('scratch-reader-token', NAMESPACE, _request_timeout=(5,15)))
print('QUALIFICATION_JSON=' + json.dumps(result, sort_keys=True))
'''


def runner(cron, pull_secret=None):
    job_spec = copy.deepcopy(cron['spec']['jobTemplate']['spec'])
    job_spec['activeDeadlineSeconds'] = 300; job_spec['backoffLimit'] = 0
    pod = job_spec['template']['spec']
    # No pull credential is read or copied by this harness.
    pod.pop('imagePullSecrets', None)
    if pull_secret:
        pod['imagePullSecrets'] = [{'name':pull_secret}]
    pod['volumes'] = [{'name':'reader','secret':{'secretName':'scratch-reader-token'}}]
    container = pod['containers'][0]
    original = container['args'][0]
    container['args'] = ['ROTATOR_CODE = ' + repr(original) + '\nNAMESPACE = ' + repr(NS) + '\n' + PROBE]
    container['resources']['limits'] = {'cpu':'1','memory':'512Mi'}
    container['volumeMounts'] = [{'name':'reader','mountPath':'/reader','readOnly':True}]
    apply([{'apiVersion':'batch/v1','kind':'Job','metadata':metadata('bounded-personal-probe'),'spec':job_spec}])


def run(pull_secret=None, retry=False, chart_root=ROOT):
    if retry:
        if not pull_secret:
            raise RuntimeError('Retry requires an operator-provisioned scratch pull Secret reference')
        command(['kubectl','-n',NS,'patch','deployment','cps-argo-ui','--type=merge','-p',
                 json.dumps({'spec':{'template':{'spec':{'imagePullSecrets':[{'name':pull_secret}]}}}})])
        command(['kubectl','-n',NS,'delete','job','bounded-personal-probe','--ignore-not-found=true','--wait=true'])
        reader_objects = [obj for obj in render(chart_root) if obj['kind'] not in ('Deployment','Service','NetworkPolicy')]
        next(obj for obj in reader_objects if obj['kind'] == 'CronJob')['spec']['suspend'] = True
        apply(reader_objects)
        runner(get('cronjob','argo-ui-token-rotator'), pull_secret)
        print(json.dumps({'namespace':NS,'retried':True,'pullSecretReference':pull_secret}), flush=True)
        return
    if command(['kubectl', 'get', 'namespace', NS, '--ignore-not-found']).strip():
        raise RuntimeError('Scratch namespace exists; refuse to overwrite another run')
    objects = render(chart_root)
    cron = next(o for o in objects if o['kind'] == 'CronJob')
    cron['spec']['suspend'] = True
    if pull_secret:
        for obj in objects:
            if obj['kind'] == 'Deployment':
                obj['spec']['template']['spec']['imagePullSecrets'] = [{'name':pull_secret}]
    else:
        for obj in objects:
            if obj['kind'] == 'Deployment':
                obj['spec']['template']['spec'].pop('imagePullSecrets',None)
    ca = get('configmap', 'cps-compute-gateway-ca', 'cps-compute')['data']['ca.crt']
    ssl.create_default_context(cadata=ca)
    initial = [{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': NS,
                'labels': {'qualification.cps/scope': 'supporting-not-production'}}}]
    for name in ('scratch-reader', 'scratch-extra-reader'):
        initial.append({'apiVersion':'v1','kind':'ServiceAccount','metadata':metadata(name),'automountServiceAccountToken':False})
    for name in ('scratch-reader-token', 'scratch-extra-secret'):
        initial.append({'apiVersion':'v1','kind':'Secret','metadata':metadata(name),'type':'Opaque','stringData':{'token':''}})
    initial.extend([
        {'apiVersion':'v1','kind':'Secret','metadata':metadata('scratch-cps-oauth'),'type':'Opaque',
         'stringData':{'oauth-client-secret':secrets.token_urlsafe(48),'cookie-secret':secrets.token_urlsafe(48)}},
        {'apiVersion':'v1','kind':'ConfigMap','metadata':metadata('scratch-compute-ca'),'data':{'ca.crt':ca}},
        {'apiVersion':'v1','kind':'ConfigMap','metadata':metadata('reader-proof'),'data':{'proof':'scratch-only'}},
        {'apiVersion':'rbac.authorization.k8s.io/v1','kind':'Role','metadata':metadata('scratch-reader-proof'),
         'rules':[{'apiGroups':[''],'resources':['configmaps'],'resourceNames':['reader-proof'],'verbs':['get']}]},
        {'apiVersion':'rbac.authorization.k8s.io/v1','kind':'RoleBinding','metadata':metadata('scratch-reader-proof'),
         'subjects':[{'kind':'ServiceAccount','name':'scratch-reader','namespace':NS}],
         'roleRef':{'apiGroup':'rbac.authorization.k8s.io','kind':'Role','name':'scratch-reader-proof'}}])
    apply(initial)
    # The credential-free rendered objects retain chart RBAC and frontend defaults.
    apply(objects)
    runner(cron, pull_secret)
    print(json.dumps({'namespace':NS,'job':'bounded-personal-probe','scope':'supporting-not-production','started':True}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pull-secret', help='Reference to independently provisioned scratch pull auth; its data is never read')
    parser.add_argument('--retry', action='store_true', help='Recreate only this qualification runner and update its frontend pull reference')
    parser.add_argument('--chart-source-root', type=Path, default=ROOT, help='Render the exact chart source under qualification')
    options = parser.parse_args()
    run(options.pull_secret, options.retry, options.chart_source_root)
