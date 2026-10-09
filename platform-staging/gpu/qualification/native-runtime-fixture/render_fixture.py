#!/usr/bin/env python3
"""Render an inert trusted GPU2 proposal; never apply, enroll, set caps or use CUDA."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
import types


HERE = Path(__file__).resolve().parent
NAMESPACE = 'cps-native-gpu-20261009'
NODE = 'k3s-wk-gpu2'
NODE_UID = '3336cdd5-d245-436e-b57c-2f66c6dcaa41'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
IMAGE = 'ghcr.io/mul-cps/cps-compute:qualification-40b9525@sha256:b3802a7f70077ff56adbc060d1177409eeff76c8b3cf8ccf9f39047c1e6716bf'
SDK_COMMIT = 'a11fc3954a86433648298e54b4fd9def2a99a139'
RUNTIME_SHA = 'd63655ffa6b8fa56f945f6a7c5705ae900223ad62104f293ac3be171d1ac0002'
BINARY_SHA = '0e19d4ec396dd64cabe364607fee151c001821cdcb2da5e5b181d7f902a76f69'
CUDA_SHA = 'e0a3e28c00336d9dd5bc2c6267eb2b0792ef467940fd96c86aa11cd1c180e2eb'
SESSION_SHA = 'a54bba4924b8ce72480c1bbcc3cb64865a5802c6a168058868c2ed2142ce3973'
RUNTIME_SOURCE = Path('/tmp/cps-compute-native-runtime-20261009/src/cps_compute/native_gpu_runtime.py')
BINARY_SOURCE = Path('/tmp/cps-native-socket-ubuntu-build-20261009/native-imports-socket-fixed')
CUDA_SOURCE = HERE.parents[2] / 'scheduler/qualification/r615-pod-cap/cuda_probe.py'
SESSION_SOURCE = Path('/home/bjoern/git/cps-gpu-cluster-worktrees/no-mig-native-20261009/platform-staging/gpu/qualification/native-live/session_probe.py')
EXCEPTIONS = ['immutable reviewed source ConfigMap gate-only Python package',
              'immutable reviewed qualification probes/binary mounted read-only in main',
              'runtimeClassName=nvidia with exact bound UUID and gate GPU visibility void',
              'cached immutable images only: imagePullPolicy=Never',
              'bounded 128Mi writable emptyDir at /tmp',
              'temporary empty test exchange hostPath only at /exchange',
              'main900s idle with no automatic CUDA execution; peer restartPolicy=Always']
PROFILE = {'enabled': False, 'gpu': {'mode': 'shared', 'nominalMemoryGiB': 5,
    'qualification': {'mechanism': 'r615-native-cgroup-managed-deny', 'status': 'pilot-unqualified'}}}
POLICY_HASH = 'sha256:' + hashlib.sha256(json.dumps({'profile': PROFILE, 'exceptions': EXCEPTIONS,
    'sdkCommit': SDK_COMMIT}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _snapshot() -> dict:
    path = HERE / 'proposal.json'
    if not path.exists():
        return {}
    return next(i for i in json.loads(path.read_text())['items'] if i['kind'] == 'ConfigMap')


def _pinned(path, default: Path, key: str, expected: str, *, binary: bool = False) -> bytes:
    chosen = Path(path) if path is not None else default
    if chosen.exists():
        raw = chosen.read_bytes()
    elif path is not None:
        raise ValueError('Explicit reviewed source path does not exist: ' + str(chosen))
    else:
        # The committed immutable proposal is an exact byte snapshot of the
        # reviewed SDK/probe artifacts, allowing offline fixture verification.
        snapshot = _snapshot()
        if binary:
            raw = base64.b64decode(snapshot.get('binaryData', {}).get(key, ''), validate=True)
        else:
            raw = snapshot.get('data', {}).get(key, '').encode()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Reviewed source digest mismatch: ' + key)
    return raw


def runtime(source: bytes | None = None):
    source = source or _pinned(None, RUNTIME_SOURCE, 'native_gpu_runtime.py', RUNTIME_SHA)
    name = 'cps_reviewed_native_runtime_fixture'
    module = types.ModuleType(name)
    sys.modules[name] = module
    exec(compile(source, 'reviewed-sdk-' + SDK_COMMIT, 'exec'), module.__dict__)
    return module


def _idle_source() -> str:
    return f'''"""Trusted idle fixture; root runs each bounded probe explicitly."""
import hashlib,json,os,pathlib,shutil,time
source=pathlib.Path('/qualification/native-imports')
assert hashlib.sha256(source.read_bytes()).hexdigest()=='{BINARY_SHA}'
assert (os.getuid(),os.getgid())==(1000,100)
assert not os.environ.get('LD_PRELOAD')
target=pathlib.Path('/tmp/native-imports')
shutil.copyfile(source,target)
target.chmod(0o700)
print(json.dumps({{'state':'native-fixture-ready','pid':os.getpid(),'gpu_uuid':'{GPU}',
 'binary_sha256':'{BINARY_SHA}','idle_seconds':900,'production_qualified':False}}),flush=True)
time.sleep(900)
'''


def _binding(module, name: str):
    return module.NativeGpuBinding(namespace=NAMESPACE, name=name, node=NODE,
        node_uid=NODE_UID, gpu_uuid=GPU, profile='native-gpu-5g-pilot', policy_hash=POLICY_HASH)


def render(*, runtime_path=None, binary_path=None, cuda_path=None, session_path=None) -> dict:
    source = _pinned(runtime_path, RUNTIME_SOURCE, 'native_gpu_runtime.py', RUNTIME_SHA)
    binary = _pinned(binary_path, BINARY_SOURCE, 'native-imports', BINARY_SHA, binary=True)
    if binary[:4] != b'\x7fELF':
        raise ValueError('Reviewed Linux ELF qualification binary required')
    data = {'__init__.py': '', 'native_gpu_runtime.py': source.decode(),
        'cuda_probe.py': _pinned(cuda_path, CUDA_SOURCE, 'cuda_probe.py', CUDA_SHA).decode(),
        'session_probe.py': _pinned(session_path, SESSION_SOURCE, 'session_probe.py', SESSION_SHA).decode(),
        'main_idle.py': _idle_source()}
    binary_data = {'native-imports': base64.b64encode(binary).decode()}
    payload_sha = hashlib.sha256(json.dumps({'data': data, 'binaryData': binary_data},
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    cm_name = 'native-runtime-' + payload_sha[:12]
    cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,
        'metadata': {'namespace': NAMESPACE, 'name': cm_name, 'annotations': {
            'source.payload.sha256': payload_sha, 'source.sdk.commit': SDK_COMMIT,
            'qualification.production': 'false'}}, 'data': data, 'binaryData': binary_data}
    items = [{'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': NAMESPACE,
        'labels': {'pod-security.kubernetes.io/enforce': 'privileged',
                   'compute.cps.unileoben.ac.at/qualification': 'trusted-native-cap-only'}}}, cm]
    module = runtime(source)
    settings = module.NativeGpuRuntimeSettings(gate_image=IMAGE, approved_gate_images=frozenset({IMAGE}),
        approved_workload_images=frozenset({IMAGE}), enabled=True)
    for name, restart in (('native-cap-main', 'Never'), ('native-cap-peer', 'Always')):
        baseline = {'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': name, 'namespace': NAMESPACE},
            'spec': {'restartPolicy': restart, 'containers': [{'name': 'main', 'image': IMAGE,
                'command': ['python', '-u', '/qualification/main_idle.py'],
                'env': [{'name': 'HOME', 'value': '/tmp'},
                        {'name': 'PYTHONDONTWRITEBYTECODE', 'value': '1'}],
                'resources': {'requests': {'cpu': '100m', 'memory': '256Mi'},
                              'limits': {'cpu': '2', 'memory': '2Gi'}}}]}}
        contract = module.compile_native_gpu_pod(baseline, PROFILE, binding=_binding(module, name),
                                                 settings=settings, qualification_pilot=True)
        pod = copy.deepcopy(contract.pod)
        spec = pod['spec']
        spec['runtimeClassName'] = 'nvidia'
        spec['volumes'] += [
            {'name': 'qualification-source', 'configMap': {'name': cm_name, 'defaultMode': 0o555}},
            {'name': 'gate-package', 'configMap': {'name': cm_name, 'defaultMode': 0o444, 'items': [
                {'key': '__init__.py', 'path': 'cps_compute/__init__.py'},
                {'key': 'native_gpu_runtime.py', 'path': 'cps_compute/native_gpu_runtime.py'}]}},
            {'name': 'scratch', 'emptyDir': {'sizeLimit': '128Mi'}},
            {'name': 'qualification-exchange', 'hostPath': {
                'path': '/run/cps-native-gpu/exchange', 'type': 'Directory'}}]
        gate = spec['initContainers'][0]
        gate['env'].append({'name': 'PYTHONPATH', 'value': '/opt/native'})
        gate['volumeMounts'].append({'name': 'gate-package', 'mountPath': '/opt/native', 'readOnly': True})
        main = spec['containers'][0]
        main['env'].append({'name': 'PYTHONPATH', 'value': '/qualification'})
        main['volumeMounts'] = [
            {'name': 'qualification-source', 'mountPath': '/qualification', 'readOnly': True},
            {'name': 'scratch', 'mountPath': '/tmp'},
            {'name': 'qualification-exchange', 'mountPath': '/exchange'}]
        for container in [*spec['initContainers'], *spec['containers']]:
            container['imagePullPolicy'] = 'Never'
        pod['metadata']['annotations'].update({'source.payload.sha256': payload_sha,
            'qualification.production': 'false', 'qualification.controller': 'experimental-native',
            'qualification.operator-exceptions': json.dumps(EXCEPTIONS, separators=(',', ':')),
            'qualification.expected-node-uid': NODE_UID, 'qualification.expected-gpu': GPU,
            'qualification.policy-hash': POLICY_HASH, 'qualification.expected-cap-mib': '5120'})
        # The trusted operator explicitly rebases its reviewed fixture additions
        # BEFORE dry-run finalization. This is never a browser/API override hook.
        pod['metadata']['annotations'][module.SPEC_ANNOTATION] = module.native_spec_sha256(pod)
        items.append(pod)
    return {'apiVersion': 'v1', 'kind': 'List', 'items': items}


def finalize(proposed: dict, dryrun: dict, *, pod_uid: str | None = None):
    module = runtime()
    name = proposed['metadata']['name']
    if name not in ('native-cap-main', 'native-cap-peer'):
        raise ValueError('Exact trusted fixture Pod required')
    # Verify the complete proposed body against the source-owned rendered object
    # so an arbitrary caller cannot rebase a hostile spec as an operator fixture.
    expected = next(i for i in render()['items'] if i['kind'] == 'Pod' and i['metadata']['name'] == name)
    if proposed != expected:
        raise ValueError('Trusted proposal changed before admission')
    contract = module.NativePodContract(copy.deepcopy(proposed), _binding(module, name), 5120,
                                       module.native_spec_sha256(proposed))
    result = module.finalize_native_admitted_pod(contract, dryrun)
    return result.pod, result.intent_for_pod_uid(pod_uid) if pod_uid is not None else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-source', type=Path)
    parser.add_argument('--binary-source', type=Path)
    parser.add_argument('--cuda-source', type=Path)
    parser.add_argument('--session-source', type=Path)
    parser.add_argument('--proposed-pod', type=Path)
    parser.add_argument('--dryrun-pod', type=Path)
    parser.add_argument('--pod-uid')
    args = parser.parse_args()
    if args.proposed_pod or args.dryrun_pod:
        if not args.proposed_pod or not args.dryrun_pod:
            parser.error('Proposed and API dry-run Pod must be provided together')
        pod, intent = finalize(json.loads(args.proposed_pod.read_text()),
                               json.loads(args.dryrun_pod.read_text()), pod_uid=args.pod_uid)
        print(json.dumps({'pod': pod, 'intent': intent}, indent=2))
    else:
        print(json.dumps(render(runtime_path=args.runtime_source, binary_path=args.binary_source,
            cuda_path=args.cuda_source, session_path=args.session_source), indent=2))


if __name__ == '__main__':
    main()
