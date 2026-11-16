"""Bounded GPU2 managed contention witness with the deployed 16 GiB RAM budget.

Administrator fixture only; run after all real pilot workspaces have stopped.
Uses standard upstream annotations, a pinned image, and explicit GPU identity.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid

import yaml


def kubectl(*args, timeout=45):
    return subprocess.check_output(['kubectl', *args], text=True, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gpu-uuid', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--peer-profile', type=int, choices=[5, 10, 20], default=20)
    parser.add_argument('--peer-mode', choices=['managed', 'ordinary'], default='ordinary')
    parser.add_argument('--borrower-mib', type=int, default=36864)
    parser.add_argument('--reverse', action='store_true')
    parser.add_argument('--expect-managed-rejection', action='store_true',
                        help='Require driver-boundary borrower rejection and protected ordinary peer progress')
    args = parser.parse_args()
    if args.expect_managed_rejection and args.peer_mode != 'ordinary':
        parser.error('rejection witness requires a supported ordinary-memory peer')
    if not args.gpu_uuid.startswith('GPU-') or not 5120 < args.borrower_mib < 40960:
        parser.error('require an explicit GPU UUID and bounded managed borrower size')
    args.out.mkdir(parents=True, exist_ok=False)
    node = json.loads(kubectl('get', 'node', 'k3s-wk-gpu2', '-o', 'json'))
    if node['status']['nodeInfo']['osImage'] != 'Ubuntu 26.04.1 LTS':
        raise RuntimeError('wrong target operating system')
    pods = json.loads(kubectl('get', 'pods', '-n', 'gpu-operator', '-o', 'json'))['items']
    driver = next(p['metadata']['name'] for p in pods
                  if p['spec'].get('nodeName') == 'k3s-wk-gpu2'
                  and any('cps-nvidia-driver@sha256:' in c['image']
                          for c in p['spec']['containers']))

    def smi(*query):
        return kubectl('exec', '-n', 'gpu-operator', driver, '--', 'nvidia-smi', *query)

    inventory = smi('--query-gpu=uuid,driver_version,memory.total', '--format=csv,noheader')
    if args.gpu_uuid not in inventory or '620.70.06' not in inventory:
        raise RuntimeError('GPU UUID or driver mismatch')
    clients = smi('--query-compute-apps=gpu_uuid,pid,used_gpu_memory', '--format=csv,noheader')
    if clients.strip():
        raise RuntimeError('GPU2 has active CUDA clients; refusing contention fixture')
    (args.out / 'identity.json').write_text(json.dumps({
        'node': node['metadata']['name'], 'node_uid': node['metadata']['uid'],
        'gpu_uuid': args.gpu_uuid, 'inventory': inventory, 'arguments': {
            **vars(args), 'out': str(args.out)}, 'host_memory_limit': '16Gi'}, indent=2))
    prefix = 'gpu2-managed16-' + uuid.uuid4().hex[:8]
    config = prefix + '-probe'
    names = [prefix + '-borrower', prefix + '-peer']
    created = []
    base = yaml.safe_load(Path(__file__).with_name('raw-driver-pod.yaml').read_text())

    def save_logs():
        for name in created:
            try:
                (args.out / (name + '.log')).write_text(kubectl('logs', '-n', 'gpu-operator', name))
                (args.out / (name + '.state.json')).write_text(kubectl('get', 'pod', '-n', 'gpu-operator', name, '-o', 'json'))
            except subprocess.CalledProcessError:
                pass

    def wait_filled(name):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            logs = kubectl('logs', '-n', 'gpu-operator', name)
            if 'holding-filled-vram' in logs:
                return
            pod = json.loads(kubectl('get', 'pod', '-n', 'gpu-operator', name, '-o', 'json'))
            if pod['status']['phase'] in ['Failed', 'Succeeded']:
                raise RuntimeError(name + ' exited before completing its working set')
            time.sleep(1)
        raise TimeoutError(name + ' working set')

    try:
        kubectl('create', 'configmap', config, '-n', 'gpu-operator',
                '--from-file=probe.py=' + str(Path(__file__).with_name('managed_contention_probe.py')))
        for i, name in enumerate(names):
            pod = json.loads(json.dumps(base))
            pod['metadata']['name'] = name
            annotations = pod['metadata']['annotations']
            for key in ['request', 'limit']:
                annotations['nvidia.com/container.main.gpu-memory.' + key] = str((5 if i == 0 else args.peer_profile)*1024) + 'Mi'
            annotations['nvidia.com/container.main.gpus.devices'] = 'k8s.device-plugin.nvidia.com/gpu=' + args.gpu_uuid
            container = pod['spec']['containers'][0]
            container['command'] += ['managed' if i == 0 else args.peer_mode,
                                     str(args.borrower_mib if i == 0 else (args.peer_profile*1024 - 512)),
                                     'borrower' if i == 0 else 'peer']
            container['resources']['limits']['memory'] = '16Gi'
            container['resources']['limits']['cpu'] = '4'
            pod['spec']['volumes'][0]['configMap']['name'] = config
            path = args.out / (name + '.yaml')
            path.write_text(yaml.safe_dump(pod))
            kubectl('create', '-f', str(path))
            created.append(name)
            kubectl('wait', '-n', 'gpu-operator', '--for=condition=Ready', 'pod/' + name, '--timeout=90s', timeout=100)
            observed = json.loads(kubectl('get', 'pod', '-n', 'gpu-operator', name, '-o', 'json'))
            if observed['spec']['nodeName'] != node['metadata']['name']:
                raise RuntimeError('fixture placed on wrong node')
            pod_uid = observed['metadata']['uid'].replace('-', '_')
            # The standard driver container has hostPID and the host cgroup tree.
            cgroups = kubectl('exec', '-n', 'gpu-operator', driver, '--', 'sh', '-c',
                'find /sys/fs/cgroup -path "*pod' + pod_uid + '*" -name cgroup.procs '
                r'-print -exec cat {} \;')
            if not cgroups.strip():
                raise RuntimeError('no host cgroup identity found')
            (args.out / (name + '-host-cgroups.txt')).write_text(cgroups)
            container_id = observed['status']['containerStatuses'][0]['containerID'].split('://', 1)[1]
            leaves = [line.rsplit('/', 1)[0] for line in cgroups.splitlines()
                      if line.endswith('/cri-containerd-' + container_id + '.scope/cgroup.procs')]
            if len(leaves) != 1:
                raise RuntimeError('one real container leaf cgroup required')
            limits = smi('memory-limits', '--get', '--namespace', leaves[0], '-i', args.gpu_uuid)
            (args.out / (name + '-driver-limits.txt')).write_text(limits)
        order = names[::-1] if args.reverse else names
        for name in order:
            kubectl('exec', '-n', 'gpu-operator', name, '--', 'touch', '/tmp/start')
            try:
                wait_filled(name)
            except RuntimeError:
                if name != names[0] or not (args.reverse or args.expect_managed_rejection):
                    raise
                logs = kubectl('logs', '-n', 'gpu-operator', name)
                if args.expect_managed_rejection:
                    events = [json.loads(line) for line in logs.splitlines() if line.startswith('{')]
                    allocations = [e for e in events if e.get('step') == 'allocation']
                    if not allocations or not all(e.get('result', 0) != 0 for e in allocations):
                        raise RuntimeError('borrower failed without an observed driver allocation rejection')
                # Preserve the exact error; a rejection is only expected in the opt-in policy witness.
                (args.out / 'borrower-rejected-under-contention.txt').write_text(logs)
            else:
                if args.expect_managed_rejection and name == names[0]:
                    raise RuntimeError('managed borrower unexpectedly accepted by rejection policy')
            (args.out / (name + '-filled.csv')).write_text(smi('--query-gpu=uuid,memory.used', '--format=csv,noheader'))
        # The protected peer must continue real memset+sync work after contention.
        time.sleep(12)
        logs = kubectl('logs', '-n', 'gpu-operator', names[1])
        if '"step": "progress"' not in logs:
            raise RuntimeError('protected peer has no continued CUDA progress')
        for name in names:
            pod = json.loads(kubectl('get', 'pod', '-n', 'gpu-operator', name, '-o', 'json'))
            if pod['status']['phase'] == 'Running':
                kubectl('exec', '-n', 'gpu-operator', name, '--', 'touch', '/tmp/release')
        time.sleep(2)
        save_logs()
        (args.out / 'result.json').write_text(json.dumps({'protected_peer_progress': True,
            'borrower_survival_required': False, 'idle_borrowing_allowed': True,
            'managed_rejection_required': args.expect_managed_rejection}, indent=2))
    except Exception as error:
        (args.out / 'result.json').write_text(json.dumps({'protected_peer_progress': False,
            'error': str(error), 'error_type': type(error).__name__}, indent=2))
        raise
    finally:
        save_logs()
        for name in created:
            kubectl('delete', 'pod', '-n', 'gpu-operator', name, '--wait=true', '--timeout=60s', timeout=70)
        kubectl('delete', 'configmap', '-n', 'gpu-operator', config, '--ignore-not-found=true')
        (args.out / 'physical-after.csv').write_text(smi('--query-gpu=uuid,memory.used', '--format=csv,noheader'))
        (args.out / 'clients-after.csv').write_text(smi('--query-compute-apps=gpu_uuid,pid,used_gpu_memory', '--format=csv,noheader'))


if __name__ == '__main__':
    main()
