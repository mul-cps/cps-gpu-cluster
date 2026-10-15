#!/usr/bin/env python3
"""Bounded API-server qualification; never create a Pod or bind a real Pod.

Run only under an explicitly authorized qualification namespace. Fixture actors,
Workflow owners and GPU assignments remain synthetic and do not establish live
controller, scheduler or GPU-isolation integration.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import time

import yaml

import render_runtime

NS = 'cps-dynamic-admission-live-20261008'
EXECUTOR = 'quay.io/argoproj/argoexec:v3.7.18@sha256:8651f0d1a1050be46ef28a7362cbb7387b5f5c29ce691ebddd5d99a0bb7281a9'
DEFAULT_FIXTURES = Path('/home/bjoern/git/cps-gpu-cluster/qualification-artifacts/dynamic-runtime-admission-20261007/offline-evidence')


def kubectl(args, obj=None, actor=None):
    command = ['kubectl', '--request-timeout=20s']
    if actor:
        command += ['--as', actor]
    command += args
    run = subprocess.run(command, input=None if obj is None else json.dumps(obj),
        capture_output=True, text=True, timeout=30)
    return {'command': command, 'exitCode': run.returncode,
        'stdout': run.stdout, 'stderr': run.stderr}


def save(directory, name, data):
    (directory / name).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def contains_expected(observed, expected):
    """Allow server-added defaults while refusing drift in declared fields."""
    if isinstance(expected, dict):
        return isinstance(observed, dict) and all(
            key in observed and contains_expected(observed[key], value)
            for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(observed, list) and len(observed) == len(expected) and all(
            contains_expected(left, right) for left, right in zip(observed, expected))
    return observed == expected


def ensure_owned_namespace():
    response = kubectl(['get', 'namespace', NS, '-o', 'json'])
    if response['exitCode']:
        raise RuntimeError('Qualification namespace must be created after verifying NotFound')
    namespace = json.loads(response['stdout'])
    if namespace['metadata'].get('labels', {}).get('compute.cps.unileoben.ac.at/purpose') != 'admission-qualification':
        raise RuntimeError('Namespace lacks qualification ownership label')
    pods = kubectl(['get', 'pods', '-n', NS, '-o', 'json'])
    if pods['exitCode'] or json.loads(pods['stdout'])['items']:
        raise RuntimeError('Namespace contains Pods or cannot be inventoried; preserve it')


def render(registry=None):
    return render_runtime.build(namespace=NS, executor_image=EXECUTOR, registry=registry)['items']


def update_params(items):
    results = []
    for item in items:
        if item['kind'] not in ('DynamicGpuAdmissionPolicy', 'DynamicGpuQuotaPolicy', 'DynamicGpuBindingPolicy'):
            continue
        current = kubectl(['get', item['kind'], item['metadata']['name'], '-n', NS, '-o', 'json'])
        if current['exitCode']:
            raise RuntimeError(current['stderr'])
        item = copy.deepcopy(item)
        item['metadata']['resourceVersion'] = json.loads(current['stdout'])['metadata']['resourceVersion']
        result = kubectl(['replace', '-f', '-', '-o', 'json'], item)
        results.append(result)
        if result['exitCode']:
            raise RuntimeError(result['stderr'])
    return results


def install_empty(directory):
    items = render()
    (directory / 'candidate-final-empty.yaml').write_text(yaml.safe_dump_all(items, sort_keys=False))
    results = []
    kinds = ('CustomResourceDefinition', 'DynamicGpuAdmissionPolicy', 'DynamicGpuQuotaPolicy',
        'DynamicGpuBindingPolicy', 'ValidatingAdmissionPolicy', 'ValidatingAdmissionPolicyBinding')
    for kind in kinds:
        for item in items:
            if item['kind'] != kind:
                continue
            if 'namespace' not in item['metadata'] and NS not in item['metadata']['name']:
                raise RuntimeError('Cluster-scoped candidate name lacks the qualification namespace')
            get_args = ['get', kind, item['metadata']['name'], '-o', 'json']
            if 'namespace' in item['metadata']:
                get_args += ['-n', NS]
            existing = kubectl(get_args)
            candidate = copy.deepcopy(item)
            verb = 'create'
            if not existing['exitCode']:
                observed = json.loads(existing['stdout'])
                if not contains_expected(observed.get('spec'), candidate.get('spec')):
                    raise RuntimeError('Existing resource differs; manual ownership review required: ' + item['metadata']['name'])
                candidate['metadata']['resourceVersion'] = observed['metadata']['resourceVersion']
                verb = 'replace'
            dry = kubectl([verb, '--dry-run=server', '-f', '-', '-o', 'json'], candidate)
            results.append({'kind': kind, 'name': item['metadata']['name'], 'phase': 'dry-run', **dry})
            if dry['exitCode']:
                save(directory, 'installation.json', results)
                raise RuntimeError(dry['stderr'])
            if existing['exitCode']:
                actual = kubectl(['create', '-f', '-', '-o', 'json'], item)
                results.append({'kind': kind, 'name': item['metadata']['name'], 'phase': 'install', **actual})
                if actual['exitCode']:
                    raise RuntimeError(actual['stderr'])
            if kind == 'CustomResourceDefinition':
                wait = kubectl(['wait', '--for=condition=Established', 'crd/' + item['metadata']['name'], '--timeout=20s'])
                if wait['exitCode']:
                    raise RuntimeError(wait['stderr'])
    save(directory, 'installation.json', results)


def pod_inputs(fixtures, index):
    result = []
    for gib in (5, 10, 20):
        original = json.loads((fixtures / f'pod-index{index}-batch-shared-{gib}-input.json').read_text())
        obj = copy.deepcopy(original['object'])
        obj['metadata']['namespace'] = NS
        obj['metadata'].pop('uid', None)
        for container in obj['spec']['containers'] + obj['spec'].get('initContainers', []):
            if container['name'] in ('init', 'wait'):
                container['image'] = EXECUTOR
        result.append((gib, original, obj))
    return result


def probe(directory, name, obj, actor, allow=False, raw_path=None):
    identity = kubectl(['auth', 'whoami', '-o', 'json'], actor=actor)
    observed = json.loads(identity['stdout']).get('status', {}).get('userInfo', {}).get('username') if not identity['exitCode'] else None
    if observed != actor:
        raise RuntimeError('Requested actor is not authenticated by this API route: ' +
            str(observed) + '; use verified direct credentials or incluster_probe.py')
    args = ['create', '--dry-run=server', '-f', '-', '-o', 'json']
    if raw_path:
        args = ['create', '--raw', raw_path + '?dryRun=All', '-f', '-']
    result = kubectl(args, obj, actor)
    result.update(name=name, expected='allow' if allow else 'policy-deny',
        inputSha256=hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest())
    if allow:
        result['matchedExpectation'] = result['exitCode'] == 0
    else:
        result['matchedExpectation'] = result['exitCode'] != 0 and 'cps-dynamic-admission-live-20261008-' in result['stderr']
    save(directory, name + '.json', {'input': obj, **result})
    print(name, result['exitCode'], result['matchedExpectation'], result['stderr'][:1200], flush=True)
    return result


def probe_empty(directory, fixtures):
    update_params(render())
    time.sleep(1)
    _, original, obj = pod_inputs(fixtures, 1)[0]
    results = [probe(directory, 'empty-pod-denied', obj, original['request']['userInfo']['username'])]
    quota = json.loads((fixtures / 'capabilities-input.json').read_text())
    quota['object']['metadata']['namespace'] = NS
    quota['object']['metadata'].pop('uid', None)
    results.append(probe(directory, 'empty-configmap-denied', quota['object'], quota['request']['userInfo']['username']))
    binding = json.loads((fixtures / 'binding-input.json').read_text())
    binding['object']['metadata']['namespace'] = NS
    results.append(probe(directory, 'empty-binding-denied', binding['object'], binding['request']['userInfo']['username'],
        raw_path=f'/api/v1/namespaces/{NS}/pods/{binding["object"]["metadata"]["name"]}/binding'))
    save(directory, 'empty-registry-probes.json', results)


def probe_reviewed(directory, fixtures):
    results = []
    for index in (0, 1):
        inputs = pod_inputs(fixtures, index)
        params = inputs[0][1]['params']
        registry = {'createCreators': params['createCreators'], 'updateCreators': params['updateCreators'],
            'owners': params['owners'], 'reviewedPods': [
                {k: r[k] for k in ('name', 'ownerUid', 'configMapPrefix', 'mainIndex', 'gpuMemory')}
                for r in params['reviewedPods']]}
        update_params(render(registry))
        time.sleep(1)
        for gib, original, obj in inputs:
            actor = original['request']['userInfo']['username']
            results.append(probe(directory, f'reviewed-pod-index{index}-{gib}-allowed', obj, actor, allow=True))
        _, original, obj = inputs[0]
        actor = original['request']['userInfo']['username']
        mutations = {
            'wrong-creator': (copy.deepcopy(obj), 'system:serviceaccount:offline:unreviewed'),
            'wrong-owner': (copy.deepcopy(obj), actor),
            'extra-hostpath': (copy.deepcopy(obj), actor),
            'loader-override': (copy.deepcopy(obj), actor),
            'wrong-index': (copy.deepcopy(obj), actor),
        }
        mutations['wrong-owner'][0]['metadata']['ownerReferences'][0]['uid'] = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
        mutations['extra-hostpath'][0]['spec']['volumes'].append({'name':'unreviewed-host','hostPath':{'path':'/etc','type':'Directory'}})
        main = next(c for c in mutations['loader-override'][0]['spec']['containers'] if c['name']=='main')
        main['env'].append({'name':'LD_PRELOAD','value':'/tmp/unreviewed.so'})
        wrong = next(c for c in mutations['wrong-index'][0]['spec']['containers'] if c['name']=='main')
        next(e for e in wrong['env'] if e['name']=='CUDA_DEVICE_MEMORY_LIMIT_0')['name'] = 'CUDA_DEVICE_MEMORY_LIMIT_1'
        for case, (mutant, mutation_actor) in mutations.items():
            results.append(probe(directory, f'reviewed-pod-index{index}-{case}-denied', mutant, mutation_actor))
    save(directory, 'reviewed-registry-probes.json', results)


def inventory(directory):
    results = {}
    for resource in ('pods', 'configmaps', 'dynamicgpuadmissionpolicies', 'dynamicgpuquotapolicies', 'dynamicgpubindingpolicies'):
        results[resource] = kubectl(['get', resource, '-n', NS, '-o', 'json'])
    for resource in ('validatingadmissionpolicies', 'validatingadmissionpolicybindings'):
        results[resource] = kubectl(['get', resource, NS+'-boundary', NS+'-quota', NS+'-binding', '-o', 'json'])
    save(directory, 'final-inventory.json', results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('install-empty', 'probe-empty', 'probe-reviewed', 'inventory'))
    parser.add_argument('--fixtures', type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument('--evidence', type=Path, default=Path(__file__).parent / 'live-evidence-20261008')
    args = parser.parse_args()
    args.evidence.mkdir(exist_ok=True)
    ensure_owned_namespace()
    {'install-empty': lambda: install_empty(args.evidence),
        'probe-empty': lambda: probe_empty(args.evidence, args.fixtures),
        'probe-reviewed': lambda: probe_reviewed(args.evidence, args.fixtures),
        'inventory': lambda: inventory(args.evidence)}[args.phase]()
    if args.phase in ('probe-empty', 'probe-reviewed'):
        name = 'empty-registry-probes.json' if args.phase == 'probe-empty' else 'reviewed-registry-probes.json'
        if any(not row['matchedExpectation'] for row in json.loads((args.evidence / name).read_text())):
            raise RuntimeError('Admission results did not meet the declared expectations')


if __name__ == '__main__':
    main()
