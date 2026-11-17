#!/usr/bin/env python3
"""Render stock-KAI two-card placement witness; deliberately no execution mode."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import uuid

import yaml

ROOT = Path(__file__).resolve().parents[3]
HISTORICAL = ROOT / 'docs/operations/evidence/upstream-sharing-20261116/mixed-profiles'
PROBE_SHA = 'd2a4f4cdb9ee1e6c09622a3277fffc711d0be0a2ddd140e74b03e0a20dd02515'
DRIVER = 'ghcr.io/mul-cps/cps-nvidia-driver@sha256:c3b71557aa17df43faad5a2661d81f1025ba355ac3adf784096de12cd2ef3e73'
OUTER = '6ce276301723a902da671058730611591c59b5f016b816f57f2d97b05c88fe2c'
INNER = '0ca3be05fd3fcdd9682e68bbff5821ea15027773404a7e47517b822bcb57387a'


def render(a):
    source = (HISTORICAL / 'probe.py').read_text()
    assert hashlib.sha256(source.encode()).hexdigest() == PROBE_SHA
    # Same retained CUDA allocation/fill/progress/free/destroy probe. Bound a longer
    # crossover window, and skip fractional OOM only for the exclusive seed.
    start = source.index(" limit=int(os.environ['NVIDIA_GPU_MEMORY_LIMIT'])")
    end = source.index(" if mode=='managed':", start)
    block = source[start:end]
    source = source[:start] + " if 'NVIDIA_GPU_MEMORY_LIMIT' in os.environ:\n" + ''.join(
        ' ' + line + '\n' for line in block.splitlines()) + source[end:]
    source = source.replace('time.monotonic()+120', 'time.monotonic()+600')
    identity = """count=C.c_int();check('visible-device-count',api('cuDeviceGetCount',[C.POINTER(C.c_int)])(C.byref(count)))
if count.value!=1:raise RuntimeError('exactly one visible CUDA device required')
u=(C.c_ubyte*16)();check('device-uuid',api('cuDeviceGetUuid_v2',[C.c_void_p,C.c_int])(C.byref(u),dev))
import uuid
emit(step='cuda-identity',gpu_uuid='GPU-'+str(uuid.UUID(bytes=bytes(u))),device_count=count.value)
"""
    source = source.replace('p=C.c_uint64();n=mib*1024**2', identity + 'p=C.c_uint64();n=mib*1024**2')
    compile(source, 'kai-placement-probe.py', 'exec')
    base = yaml.safe_load((HISTORICAL / 'gpu2-mixed-a-5.yaml').read_text())
    cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {
        'name': a.run_id, 'namespace': a.namespace}, 'data': {'probe.py': source}}
    pods = {}

    def pod(role, profile=None, fill=None):
        p = copy.deepcopy(base)
        p['metadata'].update(name=a.run_id + '-' + role, namespace=a.namespace)
        p['metadata']['labels'] = {'kai.scheduler/queue': a.queue,
                                   'cps.unileoben.ac.at/kai-placement-run': a.run_id}
        ann = {'required-plugins.noderesource.dev/container.main': '["gpu-fractioning"]'}
        if profile is not None:
            ann.update({f'nvidia.com/container.main.gpu-memory.{tier}': f'{profile * 1024}Mi'
                        for tier in ('request', 'limit')})
            ann['nvidia.com/container.main.gpu-compute.mode'] = 'time-slicing'
        p['metadata']['annotations'] = ann
        s = p['spec']
        s.pop('nodeName', None)
        s.pop('runtimeClassName', None)
        s.update(schedulerName='kai-scheduler', priorityClassName='cps-peer-protocol-20261108',
                 preemptionPolicy='Never', automountServiceAccountToken=False,
                 nodeSelector={'kubernetes.io/hostname': a.node,
                               'cps.unileoben.ac.at/upstream-gpu-sharing': 'qualified'},
                 activeDeadlineSeconds=900)
        s['volumes'][0]['configMap']['name'] = a.run_id
        c = s['containers'][0]
        # Stock KAI owns assigned CDI/devices/env. Image defaults are not Pod env.
        c.pop('env', None)
        c['command'] = ['python3', '-u', '/probe/probe.py', 'ordinary',
                        str(fill if fill is not None else profile * 1024 - 1024), role]
        c['resources'] = {'requests': {'cpu': '200m', 'memory': '16Gi'},
                          'limits': {'cpu': '1', 'memory': '16Gi'}}
        if profile is None:
            c['resources']['requests']['nvidia.com/gpu'] = '1'
            c['resources']['limits']['nvidia.com/gpu'] = '1'
        assert not any('devices' in k or k.startswith(('cdi.k8s.io/', 'nvidia.cdi.k8s.io/')) for k in ann)
        assert 'nodeName' not in s and 'runtimeClassName' not in s
        pods[role] = p

    pod('seed-exclusive', fill=1)
    for r, cards, profiles in ((0, 'ab', (5, 10, 20)), (1, 'ba', (20, 10, 5))):
        for card in cards:
            for profile in profiles:
                pod(f'r{r}-{card}-{profile}', profile)
    pod('guard-a', 5, 1)
    pod('guard-b', 5, 1)
    sequence = [
        {'create': ['seed-exclusive'], 'expect': 'KAI selects one UUID; discover it as B; other allowed UUID is A'},
        {'create': ['r0-a-5', 'r0-a-10', 'r0-a-20', 'guard-a'], 'expect': 'all A; logical reservation 40GiB on A, seed exclusively reserves B'},
        {'release_delete': ['seed-exclusive'], 'expect': 'UID-guarded seed release; B is available'},
        {'create': ['r0-b-5', 'r0-b-10', 'r0-b-20'], 'expect': 'all B; A logical40GiB; both cards profiles5/10/20 coexist and independently progress'},
        {'checkpoint': 'round0-AB: physical32GiB/card +1MiB guard; capture BindRequests, leaf limits, progress and NVML'},
        {'release_delete': ['r0-b-5', 'r0-b-10', 'r0-b-20'], 'expect': 'B payload stops before refill; preserve original A logical40GiB'},
        {'create': ['r1-b-20', 'r1-b-10', 'r1-b-5', 'guard-b'], 'expect': 'all original B; B logical40GiB; reverse profile order'},
        {'release_delete': ['r0-a-5', 'r0-a-10', 'r0-a-20', 'guard-a'], 'expect': 'original A becomes free while B remains booked40GiB'},
        {'create': ['r1-a-20', 'r1-a-10', 'r1-a-5'], 'expect': 'all original A; both cards profiles20/10/5 coexist and independently progress'},
        {'checkpoint': 'round1-BA: physical32GiB/card +1MiB guard; same witness set'},
        {'release_delete': ['r1-b-20', 'r1-b-10', 'r1-b-5', 'guard-b', 'r1-a-20', 'r1-a-10', 'r1-a-5'],
         'expect': 'all owned Pods/CM gone; no owned BindRequests/reservations; no CUDA clients; <=1MiB/card'},
    ]
    provenance = {'status': 'render-only-not-executed', 'node': a.node,
                  'node_ip': a.node_ip, 'operator_selected_worker': a.operator_selected_worker,
                  'accepted_qualified_peers': dict(sorted(a.accepted_qualified_peers.items())),
                  'allowed_gpu_uuids': [a.gpu_a, a.gpu_b], 'expected_boot_id': a.expected_boot_id,
                  'expected_module_srcversion': a.expected_module_srcversion,
                  'driver_image': DRIVER, 'uvm_source_sha256': '5648dbfe43957eb257d9efb715906de0fb6caa43458752544221d90db6efdb18',
                  'k3s_outer_sha256': OUTER, 'k3s_inner_containerd_sha256': INNER,
                  'historical_probe_sha256': PROBE_SHA,
                  'derived_probe_sha256': hashlib.sha256(source.encode()).hexdigest(),
                  'roles_to_pod_names': {k: v['metadata']['name'] for k, v in pods.items()},
                  'sequence': sequence}
    return cm, pods, provenance


def arguments(argv=None, execution=False):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--node', required=True, choices=[f'k3s-wk-gpu{i}' for i in range(1, 5)])
    p.add_argument('--operator-selected-worker', required=True)
    p.add_argument('--accepted-qualified-peer', action='append', default=[],
                   dest='accepted_qualified_peers', metavar='NAME=NODE_UID',
                   help='Previously accepted qualified peer; repeat for each exact Ready identity')
    p.add_argument('--node-ip', required=True)
    p.add_argument('--gpu-a', required=True)
    p.add_argument('--gpu-b', required=True)
    p.add_argument('--expected-boot-id', required=True)
    p.add_argument('--expected-module-srcversion', required=True)
    p.add_argument('--namespace', default='gpu-operator')
    p.add_argument('--queue', default='cps-interactive')
    p.add_argument('--run-id', default='kai-place-' + uuid.uuid4().hex[:8])
    p.add_argument('--output', type=Path, required=True)
    if execution:
        p.add_argument('--execute', action='store_true')
        p.add_argument('--parent-idle-release')
        p.add_argument('--ssh-target')
        p.add_argument('--ssh-key', type=Path)
    a = p.parse_args(argv)
    if a.node != a.operator_selected_worker:
        p.error('single operator-selected worker must match --node')
    peers = {}
    for entry in a.accepted_qualified_peers:
        name, separator, uid = entry.partition('=')
        if (not separator or name not in [f'k3s-wk-gpu{i}' for i in range(1, 5)]
                or name == a.node or name in peers):
            p.error('accepted peer must be a distinct other worker NAME=NODE_UID')
        try:
            if str(uuid.UUID(uid)) != uid:
                raise ValueError('noncanonical NodeUID')
        except ValueError:
            p.error('accepted peer requires exact canonical NodeUID')
        peers[name] = uid
    a.accepted_qualified_peers = peers
    for value in (a.namespace, a.queue, a.run_id):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,39}', value):
            p.error('bounded DNS namespace/queue/run ID required')
    for gpu in (a.gpu_a, a.gpu_b):
        if not gpu.startswith('GPU-'):
            p.error('full GPU UUID required')
        uuid.UUID(gpu[4:])
    uuid.UUID(a.expected_boot_id)
    if a.gpu_a == a.gpu_b or not re.fullmatch('[0-9a-fA-F]{1,24}', a.expected_module_srcversion):
        p.error('distinct GPU UUIDs and exact loaded module identity required')
    return a


def main():
    a = arguments()
    cm, pods, evidence = render(a)
    a.output.mkdir(parents=True, exist_ok=False)
    (a.output / 'configmap.yaml').write_text(yaml.safe_dump(cm, sort_keys=False))
    for role, pod in pods.items():
        (a.output / (role + '.yaml')).write_text(yaml.safe_dump(pod, sort_keys=False))
    (a.output / 'sequence.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(f'Rendered {len(pods)} scheduler-assigned fixtures; no kubectl/SSH or execution: {a.output}')


if __name__ == '__main__':
    main()
