#!/usr/bin/env python3
"""Inert Root-only QA renderer. Never creates objects, enrolls or executes CUDA."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

SDK = Path('/home/bjoern/git/cps-compute-worktrees/native-health-147-build-pins-20261023/src')
SDK_COMMIT = '6360ab1f840754c63e4d4f092e4dbf537472a05d'
SOURCE_PINS = {'native_gpu_runtime.py': '035fa64027c09965fcb7557f4346b449b637aa39de804a94565deffe067b0e74',
               'native_gpu_health.py': 'fc9dd634b8a31c15939cf6ddf3b18e84b9fa5a60d21424831a410a5ba4322fe8'}
NAMESPACE = 'cps-native-qa147-20261022'
NAMESPACE_UID = '1f7d941a-872d-4453-a1ba-fd489d8aff14'
QA_STATE = '/var/lib/cps-native-gpu/qualification/' + NAMESPACE_UID + '/state'
LOAD_AUTHORITY = '/var/lib/cps-native-gpu/domains/100876ac-14e6-4292-bf52-7d129f7f08f0/custody/authority'
NODE = 'k3s-wk-gpu2'
NODE_UID = '3336cdd5-d245-436e-b57c-2f66c6dcaa41'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
BOOT = 'a464df41-e391-4443-b8e8-ad7ecd052318'
GENERATION = '4ebffc96-e25e-4583-a3b8-0d853fd90efd'
WORKLOAD_IMAGE = 'ghcr.io/mul-cps/cps-jupyter-notebook@sha256:5427088986bc06ad0713875d1aa2f31439f0bd1fbe6099d4669570fcf3e85be4'
PROFILE = {'enabled': False, 'gpu': {'mode': 'shared', 'nominalMemoryGiB': 5,
           'qualification': {'mechanism': 'r615-native-cgroup-managed-deny', 'status': 'pilot-unqualified'}}}
GATE_LAUNCH = "import runpy,sys; sys.dont_write_bytecode=True; sys.path.insert(0,'/opt/cps-qa'); runpy.run_module('cps_compute.native_gpu_runtime',run_name='__main__')"


def require(condition, message):
    if not condition: raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sources():
    result = {'__init__.py': ''}
    for name, pin in SOURCE_PINS.items():
        path = SDK / 'cps_compute' / name
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == pin, 'Exact reviewed SDK source required: ' + name)
        result[name] = raw.decode()
    return result


sources()  # Validate both exact source pins before importing any SDK code.
sys.path.insert(0, str(SDK))
from cps_compute import native_gpu_runtime as runtime
require(Path(runtime.__file__).resolve() == SDK / 'cps_compute/native_gpu_runtime.py', 'Wrong compiler import')


def validate_request(value):
    require(type(value) is dict and set(value) in ({'version', 'namespace', 'namespace_uid', 'gate_image', 'policy_hash'},
            {'version', 'namespace', 'namespace_uid', 'gate_image', 'policy_hash', 'cohort_uid'})
            and type(value['version']) is int and value['version'] == 1
            and value['namespace'] == NAMESPACE and value['namespace_uid'] == NAMESPACE_UID,
            'Exact independently reviewed fresh QA namespace identity required')
    require(type(value['gate_image']) is str
            and re.fullmatch(r'ghcr\.io/mul-cps/(?:cps-compute|cps-native-node)@sha256:[a-f0-9]{64}', value['gate_image'])
            and type(value['policy_hash']) is str and re.fullmatch(r'sha256:[a-f0-9]{64}', value['policy_hash'])
            and not value['policy_hash'].endswith('0' * 64), 'Exact reviewed gate image and policy hash required')
    if 'cohort_uid' in value:
        require(type(value['cohort_uid']) is str and re.fullmatch('[a-f0-9-]{36}',value['cohort_uid'])
                and str(uuid.UUID(value['cohort_uid']))==value['cohort_uid']
                and uuid.UUID(value['cohort_uid']).int>0,'Reviewed canonical nonzero cohort UUID required')
    return deepcopy(value)


def qa_state(request):
    return (QA_STATE if 'cohort_uid' not in request else str(Path(QA_STATE).parent/'cohorts'/request['cohort_uid']/'state'))


def _contracts(request, *, approve_qa_hostpaths=False):
    request = validate_request(request)
    require(approve_qa_hostpaths is True, 'Root must explicitly approve the dedicated QA hostPath exception')
    data = sources()
    state = qa_state(request)
    cm_name = 'cps-native-qa-gate-' + hashlib.sha256(encoded(data)).hexdigest()[:16]
    cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,
          'metadata': {'namespace': NAMESPACE, 'name': cm_name}, 'data': data}
    settings = runtime.NativeGpuRuntimeSettings(gate_image=request['gate_image'],
        approved_gate_images=frozenset({request['gate_image']}),
        approved_workload_images=frozenset({WORKLOAD_IMAGE}), enabled=True)
    result = {}
    for label, name in (('a', 'native-qa147-a'), ('b', 'native-qa147-b')):
        if 'cohort_uid' in request: name += '-'+request['cohort_uid'][:8]
        binding = runtime.NativeGpuBinding(namespace=NAMESPACE, name=name, node=NODE, node_uid=NODE_UID,
            gpu_uuid=GPU, profile='native-gpu-5g-pilot', policy_hash=request['policy_hash'])
        base = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'namespace': NAMESPACE, 'name': name},
                'spec': {'restartPolicy': 'Never', 'containers': [{'name': 'notebook', 'image': WORKLOAD_IMAGE,
                    'command': ['python', '-I', '-u', '-c', 'import time; print("qa-idle-no-gpu",flush=True); time.sleep(1800)'],
                    'resources': {'requests': {'cpu': '100m', 'memory': '256Mi'},
                                  'limits': {'cpu': '2', 'memory': '4Gi'}}}]}}
        original = runtime.compile_native_gpu_pod(base, PROFILE, binding=binding, settings=settings,
                                                 qualification_pilot=True)
        pod = deepcopy(original.pod)
        for volume in pod['spec']['volumes']:
            if volume['name'] == 'cps-native-receipts': volume['hostPath']['path'] = state + '/receipts'
            elif volume['name'] == 'cps-native-authority': volume['hostPath']['path'] = LOAD_AUTHORITY
        pod['spec']['volumes'].append({'name': 'qa-gate-package', 'configMap': {'name': cm_name, 'defaultMode': 0o444,
            'items': [{'key': name, 'path': 'cps_compute/' + name} for name in data]}})
        gate = pod['spec']['initContainers'][0]
        gate['command'] = ['python', '-I', '-S', '-c', GATE_LAUNCH]
        gate['volumeMounts'].append({'name': 'qa-gate-package', 'mountPath': '/opt/cps-qa', 'readOnly': True})
        for container in [*pod['spec']['initContainers'], *pod['spec']['containers']]:
            container['imagePullPolicy'] = 'Never'
        pod['metadata']['annotations'].update({'qualification.production': 'false',
            'qualification.namespace-uid': NAMESPACE_UID, 'qualification.sdk-commit': SDK_COMMIT,
            'qualification.root-approved-hostpaths': encoded({'receipts': state + '/receipts',
                                                             'authority': LOAD_AUTHORITY}).decode()})
        digest = runtime.native_spec_sha256(pod)
        pod['metadata']['annotations'][runtime.SPEC_ANNOTATION] = digest
        result[label] = runtime.NativePodContract(pod, binding, 5120, digest, qualification='pilot-unqualified')
    return request, cm, result


def render(request, *, approve_qa_hostpaths=False):
    request, cm, contracts = _contracts(request, approve_qa_hostpaths=approve_qa_hostpaths)
    return {'version': 1, 'request': request, 'namespace_uid': NAMESPACE_UID, 'source_configmap': cm,
            'pods': {key: deepcopy(c.pod) for key, c in contracts.items()},
            'source_paths': {name: str(SDK / 'cps_compute' / name) for name in SOURCE_PINS},
            'source_sha256': deepcopy(SOURCE_PINS), 'qa_state': qa_state(request),
            'epoch': {'node_uid': NODE_UID, 'boot_id': BOOT, 'driver_generation': GENERATION, 'gpu_uuid': GPU},
            'live_applied': False, 'hardware_qualified': False}


def finalize(request, proposed, dryrun, *, actual=None, approve_qa_hostpaths=False):
    _, _, contracts = _contracts(request, approve_qa_hostpaths=approve_qa_hostpaths)
    matching = [c for c in contracts.values() if c.pod == proposed]
    require(len(matching) == 1, 'Exact complete Root-reviewed proposed Pod required')
    contract = runtime.finalize_native_admitted_pod(matching[0], dryrun)
    intent = None
    if actual is not None:
        require(type(actual) is dict and actual.get('apiVersion') == 'v1' and actual.get('kind') == 'Pod'
                and actual.get('metadata', {}).get('namespace') == contract.binding.namespace
                and actual['metadata'].get('name') == contract.binding.name
                and not actual['metadata'].get('deletionTimestamp')
                and runtime.native_spec_sha256(actual) == contract.spec_sha256,
                'Exact actual admitted Pod identity and full spec readback required')
        intent = contract.intent_for_pod_uid(actual['metadata'].get('uid'))
    return {'version': 1, 'pod': contract.pod, 'spec_sha256': contract.spec_sha256, 'intent': intent,
            'namespace_uid': NAMESPACE_UID, 'live_applied': False, 'hardware_qualified': False}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--prepare', action='store_true'); mode.add_argument('--finalize', action='store_true')
    for flag in ('inputs', 'inputs-sha256', 'proposed-pod', 'dryrun-pod', 'actual-pod', 'output'): p.add_argument('--' + flag)
    p.add_argument('--approve-qa-hostpaths', action='store_true')
    args = p.parse_args(argv)
    if not (args.prepare or args.finalize):
        print(json.dumps({'inert': True, 'api_calls': False, 'gpu_calls': False})); return
    require(args.inputs and args.inputs_sha256 and args.output, 'Pinned inputs and exclusive output directory required')
    raw = Path(args.inputs).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == args.inputs_sha256, 'Reviewed QA input bytes changed')
    request = json.loads(raw)
    if args.prepare: result = render(request, approve_qa_hostpaths=args.approve_qa_hostpaths)
    else:
        require(args.proposed_pod and args.dryrun_pod, 'Actual server dry-run and original proposal required')
        result = finalize(request, json.loads(Path(args.proposed_pod).read_bytes()),
            json.loads(Path(args.dryrun_pod).read_bytes()),
            actual=json.loads(Path(args.actual_pod).read_bytes()) if args.actual_pod else None,
            approve_qa_hostpaths=args.approve_qa_hostpaths)
    output = Path(args.output); output.mkdir(mode=0o700)
    documents = {'review.json': result, 'inputs.json': request}
    if args.prepare:
        documents.update({'gate-source.configmap.json': result['source_configmap'],
                          **{key + '.proposed.json': value for key, value in result['pods'].items()}})
    else: documents.update({'pod.finalized.json': result['pod'], 'intent.json': result['intent']})
    for name, document in documents.items():
        fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream: stream.write(encoded(document) + b'\n')
    print(json.dumps({'prepared': True, 'output': str(output), 'api_calls': False, 'gpu_calls': False}))


if __name__ == '__main__': main()
