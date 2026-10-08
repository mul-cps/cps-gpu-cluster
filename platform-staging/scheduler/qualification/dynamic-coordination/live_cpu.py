"""Render/execute a bounded isolated CPU-only coordination transport gate.

Explicit CLI phases create ONLY fresh dedicated QA resources. No base/chart,
GPU/device, protected registry, old policy or production resource is modified.
TLS private bytes exist only in a mode0700 temporary directory and live Secret.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

import cpu_probe as probe
import fence

HERE = Path(__file__).resolve().parent
SERVICE_NS = 'cps-dynamic-coordination-live-20261008'
WEBHOOK = SERVICE_NS + '-transport'


def sources():
    return {name: (HERE / name).read_text() for name in ('service.py', 'fence.py', 'lifecycle.py', 'cpu_probe.py')}


def code_mounts():
    # SubPath files preserve the adjacent layout despite ConfigMap ..data symlinks.
    return [{'name': 'code', 'mountPath': '/qualification/dynamic-coordination/' + name,
             'subPath': name, 'readOnly': True} for name in sources()] + [
        {'name': 'quota', 'mountPath': '/qualification/dynamic-admission/quota_policy.py',
         'subPath': 'quota_policy.py', 'readOnly': True}]


def bundle(ca):
    ns, svc = probe.NAMESPACE, SERVICE_NS
    def obj(kind, name, namespace=ns, **kwargs):
        return dict(apiVersion='v1', kind=kind, metadata={'name': name, 'namespace': namespace}, **kwargs)
    def role(name, rules, namespace=ns):
        return dict(apiVersion='rbac.authorization.k8s.io/v1', kind='Role', metadata={'name': name, 'namespace': namespace}, rules=rules)
    def binding(name, sa, source_ns=ns, namespace=ns):
        return dict(apiVersion='rbac.authorization.k8s.io/v1', kind='RoleBinding', metadata={'name': name, 'namespace': namespace},
            roleRef={'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': name},
            subjects=[{'kind': 'ServiceAccount', 'name': sa, 'namespace': source_ns}])
    data = sources()
    quota = (HERE.parent / 'dynamic-admission' / 'quota_policy.py').read_text()
    items = [{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': name, 'labels': {
        'pod-security.kubernetes.io/enforce': 'restricted', 'pod-security.kubernetes.io/enforce-version': 'v1.34'}}} for name in (ns, svc)]
    items += [obj('ResourceQuota', 'cpu-only-ceiling', spec={'hard': {'requests.cpu': '1', 'limits.cpu': '3',
        'requests.memory': '1Gi', 'limits.memory': '2Gi', 'pods': '8', 'requests.nvidia.com/gpu': '0'}}),
        obj('ServiceAccount', 'cpu-workload'), obj('ServiceAccount', 'native-probe'), obj('ServiceAccount', 'generation-fence', svc),
        obj('ConfigMap', 'reviewed-code', svc, immutable=True, data=data),
        obj('ConfigMap', 'reviewed-quota-source', svc, immutable=True, data={'quota_policy.py': quota}),
        obj('ConfigMap', 'reviewed-code', immutable=True, data=data),
        obj('ConfigMap', 'reviewed-quota-source', immutable=True, data={'quota_policy.py': quota}),
        obj('ConfigMap', 'empty-registry', svc, immutable=True, data={'registry.json': json.dumps(dict(schemaVersion=1, namespace=ns,
            bindingWriters=['system:serviceaccount:kai-scheduler:binder'], cleanupWriters=[],
            sealWriter='system:serviceaccount:' + svc + ':trusted-sealer', records=[]))}),
        role('native-probe', [{'apiGroups': [''], 'resources': ['pods', 'configmaps'], 'verbs': ['create']},
            {'apiGroups': [''], 'resources': ['pods'], 'resourceNames': list(probe.PODS), 'verbs': ['get', 'patch', 'delete']},
            {'apiGroups': [''], 'resources': ['configmaps'], 'resourceNames': list(probe.MAPS), 'verbs': ['get', 'patch', 'delete']},
            {'apiGroups': [''], 'resources': ['pods/binding'], 'resourceNames': list(probe.PODS[:3]), 'verbs': ['create']}]),
        binding('native-probe', 'native-probe'),
        obj('Service', 'generation-fence', svc, spec={'selector': {'app': 'coordination-cpu-transport'},
            'ports': [{'port': 443, 'targetPort': 8443}]})]
    # Admission is read-only. No Node/Pod/map writes or Node GET are granted to service.
    items += [role('generation-fence', [{'apiGroups': [''], 'resources': ['pods', 'configmaps'], 'verbs': ['get']},
        {'apiGroups': ['argoproj.io'], 'resources': ['workflows'], 'verbs': ['get']}]), binding('generation-fence', 'generation-fence', svc)]
    items += [{'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRole', 'metadata': {'name': SERVICE_NS + '-node-read'},
        'rules': [{'apiGroups': [''], 'resources': ['nodes'], 'resourceNames': [probe.NODE], 'verbs': ['get']}]},
        {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'ClusterRoleBinding', 'metadata': {'name': SERVICE_NS + '-node-read'},
        'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'ClusterRole', 'name': SERVICE_NS + '-node-read'},
        'subjects': [{'kind': 'ServiceAccount', 'namespace': ns, 'name': 'native-probe'}]}]
    template = probe.cpu_pod('native-bind')['spec']
    template['serviceAccountName'] = 'generation-fence'; template['automountServiceAccountToken'] = True
    template['schedulerName'] = 'default-scheduler'; template.pop('activeDeadlineSeconds')
    template['containers'][0].update(name='webhook', command=['python', '-B', '/qualification/dynamic-coordination/service.py'],
        args=['--registry=/registry/registry.json', '--tls-cert=/tls/tls.crt', '--tls-key=/tls/tls.key',
              '--api-server=https://kubernetes.default.svc', '--decision-log'],
        ports=[{'containerPort': 8443}], readinessProbe={'httpGet': {'scheme': 'HTTPS', 'path': '/healthz', 'port': 8443}},
        volumeMounts=code_mounts() + [{'name': name, 'mountPath': path, 'readOnly': True} for name, path in (
            ('registry', '/registry'), ('tls', '/tls'))])
    template['volumes'] = [{'name': 'code', 'configMap': {'name': 'reviewed-code'}},
        {'name': 'quota', 'configMap': {'name': 'reviewed-quota-source'}}, {'name': 'registry', 'configMap': {'name': 'empty-registry'}},
        {'name': 'tls', 'secret': {'secretName': 'generation-fence-tls'}}]
    template['restartPolicy'] = 'Always'
    items.append({'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'generation-fence', 'namespace': svc},
        'spec': {'replicas': 1, 'selector': {'matchLabels': {'app': 'coordination-cpu-transport'}},
                 'template': {'metadata': {'labels': {'app': 'coordination-cpu-transport'}}, 'spec': template}}})
    webhook = {'apiVersion': 'admissionregistration.k8s.io/v1', 'kind': 'ValidatingWebhookConfiguration',
        'metadata': {'name': WEBHOOK}, 'webhooks': [{'name': 'cpu-transport.qa.compute.cps.unileoben.ac.at',
        'admissionReviewVersions': ['v1'], 'sideEffects': 'None', 'failurePolicy': 'Fail', 'matchPolicy': 'Exact', 'timeoutSeconds': 5,
        'namespaceSelector': {'matchLabels': {'kubernetes.io/metadata.name': ns}},
        'matchConditions': [{'name': 'two-exact-cpu-probes-only', 'expression': "request.name in ['kai-cpu-deny', 'unregistered-map']"}],
        'rules': [{'apiGroups': [''], 'apiVersions': ['v1'], 'operations': ['CREATE'], 'resources': ['pods/binding', 'configmaps'], 'scope': 'Namespaced'}],
        'clientConfig': {'caBundle': base64.b64encode(ca).decode(), 'service': {'namespace': svc, 'name': 'generation-fence', 'path': '/validate', 'port': 443}}}]}
    return items, webhook


def runner():
    spec = probe.cpu_pod('native-bind')['spec']
    spec.update(serviceAccountName='native-probe', automountServiceAccountToken=True,
                schedulerName='default-scheduler', activeDeadlineSeconds=200)
    spec['containers'][0].update(command=['python', '-B', '/qualification/dynamic-coordination/cpu_probe.py'],
        env=[{'name': 'POD_NAMESPACE', 'value': probe.NAMESPACE}],
        volumeMounts=code_mounts())
    spec['volumes'] = [{'name': 'code', 'configMap': {'name': 'reviewed-code'}}, {'name': 'quota', 'configMap': {'name': 'reviewed-quota-source'}}]
    return {'apiVersion': 'batch/v1', 'kind': 'Job', 'metadata': {'name': 'native-probe', 'namespace': probe.NAMESPACE},
        'spec': {'backoffLimit': 0, 'activeDeadlineSeconds': 200, 'template': {'spec': spec}}}


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run', 'deactivate'))
    parser.add_argument('--context', required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args(); args.evidence.mkdir(parents=True, exist_ok=True)
    def kubectl(*command, data=None, check=True):
        result = subprocess.run(['kubectl', '--context', args.context, '--request-timeout=15s', *command],
            input=None if data is None else json.dumps(data), capture_output=True, text=True, timeout=30)
        if check and result.returncode: raise RuntimeError('kubectl phase failed: ' + result.stderr[:2000])
        return result
    def create(obj):
        result = kubectl('create', '-f', '-', '-o', 'json', data=obj)
        actual = json.loads(result.stdout)
        return {'kind': actual['kind'], 'name': actual['metadata']['name'], 'uid': actual['metadata']['uid'],
                'resourceVersion': actual['metadata']['resourceVersion']}
    if args.phase == 'prepare':
        # Neither existing namespace may be reused. No apply, merge or overwrite.
        for name in (probe.NAMESPACE, SERVICE_NS):
            result = kubectl('get', 'namespace', name, check=False)
            if result.returncode == 0: raise RuntimeError('Fresh QA namespaces required')
            if '(NotFound)' not in result.stderr: raise RuntimeError('Confirmed namespace absence required')
        with tempfile.TemporaryDirectory(prefix='coordination-qa-tls-') as directory:
            root = Path(directory); cert, key = root / 'tls.crt', root / 'tls.key'
            dns = 'generation-fence.' + SERVICE_NS + '.svc'
            subprocess.run(['openssl', 'req', '-x509', '-nodes', '-newkey', 'rsa:2048', '-days', '1', '-subj', '/CN=' + dns,
                '-addext', 'subjectAltName=DNS:' + dns, '-keyout', str(key), '-out', str(cert)], check=True, capture_output=True)
            key.chmod(0o600)
            items, webhook = bundle(cert.read_bytes()); receipts = []
            for item in items[:2]: receipts.append(create(item))
            kubectl('create', 'secret', 'tls', 'generation-fence-tls', '-n', SERVICE_NS,
                    '--cert=' + str(cert), '--key=' + str(key))
            for item in items[2:]: receipts.append(create(item))
            kubectl('rollout', 'status', 'deployment/generation-fence', '-n', SERVICE_NS, '--timeout=20s')
            receipts.append(create(webhook))
            (args.evidence / 'webhook-public.json').write_text(json.dumps(webhook, indent=2) + '\n')
            (args.evidence / 'resource-receipts.json').write_text(json.dumps(receipts, indent=2) + '\n')
            (args.evidence / 'source-sha256.json').write_text(json.dumps({name: hashlib.sha256(text.encode()).hexdigest()
                for name, text in sources().items()}, indent=2) + '\n')
    elif args.phase == 'run':
        for name in ('kai-cpu-allow', 'kai-cpu-deny'): create(probe.cpu_pod(name, kai=True))
        create(runner())
        kubectl('wait', '--for=condition=complete', 'job/native-probe', '-n', probe.NAMESPACE, '--timeout=25s', check=False)
        for filename, command in (
            ('native-probe.log', ('logs', 'job/native-probe', '-n', probe.NAMESPACE)),
            ('webhook-decisions.jsonl', ('logs', 'deployment/generation-fence', '-n', SERVICE_NS)),
            ('pods-after.json', ('get', 'pods', '-n', probe.NAMESPACE, '-o', 'json')),
            ('bindrequests-after.json', ('get', 'bindrequests', '-n', probe.NAMESPACE, '-o', 'json')),
            ('events-after.json', ('get', 'events', '-n', probe.NAMESPACE, '-o', 'json'))):
            result = kubectl(*command, check=False)
            (args.evidence / filename).write_text(result.stdout if not result.returncode else result.stderr)
    else:
        # Native UID/RV CAS removal and scale-to-zero; only this isolated webhook.
        hook = json.loads(kubectl('get', 'validatingwebhookconfiguration', WEBHOOK, '-o', 'json').stdout)
        registry = json.loads((args.evidence / 'resource-receipts.json').read_text())
        pinned = next(v for v in registry if v['kind'] == 'ValidatingWebhookConfiguration')
        if any(hook['metadata'][key] != pinned[key] for key in ('uid', 'resourceVersion')): raise RuntimeError('Webhook changed; review before deactivation')
        options = {'apiVersion': 'v1', 'kind': 'DeleteOptions', 'preconditions': {key: pinned[key] for key in ('uid', 'resourceVersion')}}
        kubectl('delete', '--raw=/apis/admissionregistration.k8s.io/v1/validatingwebhookconfigurations/' + WEBHOOK, '-f', '-', data=options)
        deployment = json.loads(kubectl('get', 'deployment', 'generation-fence', '-n', SERVICE_NS, '-o', 'json').stdout)
        patch = [{'op': 'test', 'path': '/metadata/' + key, 'value': deployment['metadata'][key]} for key in ('uid', 'resourceVersion')]
        patch.append({'op': 'replace', 'path': '/spec/replicas', 'value': 0})
        kubectl('patch', 'deployment', 'generation-fence', '-n', SERVICE_NS, '--type=json', '-p', json.dumps(patch))
        (args.evidence / 'deactivated.json').write_text(json.dumps({'webhookUid': pinned['uid'], 'webhookRemoved': True,
            'serviceReplicas': 0, 'registryRecords': 0, 'productionActivated': False}, indent=2) + '\n')


if __name__ == '__main__': cli()
