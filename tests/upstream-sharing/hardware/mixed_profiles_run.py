#!/usr/bin/env python3
"""Replay historical six-profile ordinary-memory fixtures; render-only by default.

Execution requires an exclusive parent-released hardware window. No driver,
node, scheduler, or accounting configuration is changed. Existing fixture
probe.py bytes are mounted unchanged; all deletes carry UID preconditions.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
import uuid

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HISTORICAL = ROOT / 'docs/operations/evidence/upstream-sharing-20261116/mixed-profiles'
DRIVER = 'ghcr.io/mul-cps/cps-nvidia-driver@sha256:c3b71557aa17df43faad5a2661d81f1025ba355ac3adf784096de12cd2ef3e73'
SOURCE_SHA = '5648dbfe43957eb257d9efb715906de0fb6caa43458752544221d90db6efdb18'
PROBE_SHA = 'd2a4f4cdb9ee1e6c09622a3277fffc711d0be0a2ddd140e74b03e0a20dd02515'


def run(argv, data=None, timeout=25):
    return subprocess.check_output(argv, input=data, text=True, timeout=timeout,
                                   stderr=subprocess.STDOUT)


def render(a):
    probe = (HISTORICAL / 'probe.py').read_text()
    if hashlib.sha256(probe.encode()).hexdigest() != PROBE_SHA:
        raise RuntimeError('Historical mixed-profile probe changed; review required')
    cm = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {
        'name': a.run_id, 'namespace': a.namespace}, 'data': {'probe.py': probe}}
    rounds = []
    for index, (cards, profiles) in enumerate([('ab', (5, 10, 20)), ('ba', (20, 10, 5))]):
        pods = []
        for card in cards:
            for profile in profiles:
                path = HISTORICAL / f'gpu2-mixed-{card}-{profile}.yaml'
                pod = yaml.safe_load(path.read_text())
                name = f'{a.run_id}-r{index}-{card}-{profile}'
                pod['metadata'].update(name=name, namespace=a.namespace)
                pod['metadata']['labels'] = {'cps.unileoben.ac.at/mixed-run': a.run_id}
                pod['metadata']['annotations']['nvidia.com/container.main.gpus.devices'] = (
                    'k8s.device-plugin.nvidia.com/gpu=' + getattr(a, 'gpu_' + card))
                pod['spec']['nodeName'] = a.node
                pod['spec']['activeDeadlineSeconds'] = 240
                pod['spec']['volumes'][0]['configMap']['name'] = a.run_id
                container = pod['spec']['containers'][0]
                container['command'][-1] = name
                container['resources']['requests']['memory'] = '16Gi'
                container['resources']['limits']['memory'] = '16Gi'
                assert container['command'][3:5] == ['ordinary', str(profile * 1024 - 1024)]
                annotations = pod['metadata']['annotations']
                assert annotations['required-plugins.noderesource.dev/container.main'] == '["gpu-fractioning"]'
                for field in ('request', 'limit'):
                    assert annotations['nvidia.com/container.main.gpu-memory.' + field] == f'{profile * 1024}Mi'
                pods.append(pod)
        rounds.append(pods)
    return cm, rounds


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--node', required=True, choices=[f'k3s-wk-gpu{i}' for i in range(1, 5)])
    p.add_argument('--operator-selected-worker', required=True)
    p.add_argument('--node-ip', required=True)
    p.add_argument('--gpu-a', required=True)
    p.add_argument('--gpu-b', required=True)
    p.add_argument('--expected-boot-id', required=True)
    p.add_argument('--expected-module-srcversion', required=True)
    p.add_argument('--ssh-target')
    p.add_argument('--ssh-key', type=Path)
    p.add_argument('--namespace', default='gpu-operator')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--run-id', default='mixed-' + uuid.uuid4().hex[:10])
    p.add_argument('--execute', action='store_true')
    p.add_argument('--parent-idle-release')
    a = p.parse_args()
    if a.node != a.operator_selected_worker:
        p.error('selected worker must equal the one explicit operator-selected worker')
    for value in (a.gpu_a, a.gpu_b):
        if not re.fullmatch(r'GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', value):
            p.error('explicit complete GPU UUIDs required')
    if a.gpu_a == a.gpu_b:
        p.error('two distinct physical GPUs required')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,39}', a.run_id):
        p.error('invalid bounded run ID')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}', a.namespace):
        p.error('invalid namespace')
    try:
        uuid.UUID(a.expected_boot_id)
    except ValueError:
        p.error('full expected boot UUID required')
    if not re.fullmatch(r'[0-9A-Fa-f]{1,24}', a.expected_module_srcversion):
        p.error('explicit loaded module srcversion hex text required (up to 24 digits)')
    if a.execute and (not a.parent_idle_release or not a.ssh_target):
        p.error('--execute requires --parent-idle-release and --ssh-target')
    if a.ssh_target and not re.fullmatch(r'(?:[\w.-]+@)?[\w.-]+', a.ssh_target):
        p.error('SSH target must be a hostname or user@hostname')
    cm, rounds = render(a)
    observer_source = (HERE / 'extended_host_observer.py').read_text()
    # Snapshot a read-only extension; do not edit the shared observer file.
    anchor = '    print(json.dumps(result))'
    assert observer_source.count(anchor) == 1
    observer_source = observer_source.replace(anchor, '''    if a.container_id:
        result['memory_limits'] = command([smi, 'memory-limits', '--get', '-n',
            '/sys/fs/cgroup' + rows[0], '-i', a.gpu_uuid])
    print(json.dumps(result))''')
    a.output.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'prepared-only', 'node': a.node, 'gpu_a': a.gpu_a, 'gpu_b': a.gpu_b,
               'driver_image': DRIVER, 'expected_boot_id': a.expected_boot_id,
               'expected_module_srcversion': a.expected_module_srcversion,
               'probe_sha256': hashlib.sha256(cm['data']['probe.py'].encode()).hexdigest(),
               'observer_sha256': hashlib.sha256(observer_source.encode()).hexdigest(),
               'parent_idle_release': a.parent_idle_release, 'rounds': []}

    def save(name, value):
        (a.output / name).write_text(value if isinstance(value, str) else json.dumps(value, indent=2) + '\n')

    save('configmap.json', cm)
    save('host-observer.py', observer_source)
    for index, pods in enumerate(rounds):
        for pod in pods:
            save(pod['metadata']['name'] + '.json', pod)
    save('summary.json', summary)
    if not a.execute:
        print(f'Rendered 12 Pods/two orders; no kubectl/SSH execution: {a.output}')
        return
    kube = ['kubectl', '--request-timeout=15s']

    def get(*args):
        return json.loads(run(kube + ['get', *args, '-o', 'json']))

    def observe(gpu, container=None):
        argv = ['sudo', '-n', 'python3', '-', '--node', a.node, '--gpu-uuid', gpu]
        if container:
            argv += ['--container-id', container]
        identity = ['-i', str(a.ssh_key), '-o', 'IdentitiesOnly=yes'] if a.ssh_key else []
        state = json.loads(run(['ssh', *identity, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
                               a.ssh_target, shlex.join(argv)], data=observer_source, timeout=30))
        if state['gpu'].split(',')[1].strip() != '620.70.06':
            raise RuntimeError('Unexpected physical GPU driver version')
        if state['boot_id'] != a.expected_boot_id or state.get('uvm_source_sha256') != SOURCE_SHA:
            raise RuntimeError('boot or effective driver source identity changed')
        uvm = state['uvm']
        if (uvm.get('srcversion') != a.expected_module_srcversion or
                any(uvm.get('parameters/' + key) != 'Y' for key in
                    ('uvm_reject_managed_memory', 'uvm_disable_hmm'))):
            raise RuntimeError('loaded module identity/policy mismatch')
        return state

    def idle():
        for pod in get('pods', '-A', '--field-selector', 'spec.nodeName=' + a.node)['items']:
            if pod['status'].get('phase') in ('Succeeded', 'Failed'):
                continue
            annotations = pod['metadata'].get('annotations', {})
            fractional = any(k.startswith(('nvidia.com/container.', 'required-plugins.noderesource.dev/',
                                          'gpu-memory', 'gpu-fraction')) for k in annotations)
            requested = any(k.startswith('nvidia.com/') for c in pod['spec'].get('containers', [])
                            for group in ('requests', 'limits')
                            for k in c.get('resources', {}).get(group, {}))
            if fractional or requested:
                raise RuntimeError('Concurrent GPU consumer: ' + pod['metadata']['name'])
        states = [observe(gpu) for gpu in (a.gpu_a, a.gpu_b)]
        if any(s['compute_processes'].strip() or int(s['gpu'].split(',')[2].strip()) > 1 for s in states):
            raise RuntimeError('Physical GPUs must return to no clients and <=1 MiB each')
        return states

    node = get('node', a.node)
    labels = node['metadata']['labels']
    if (not node['spec'].get('unschedulable') or
            labels.get('nvidia.com/gpu-operator.driver.owner') != 'cps-r620-workers' or
            not any(c['type'] == 'Ready' and c['status'] == 'True' for c in node['status']['conditions']) or
            not any(x['type'] == 'InternalIP' and x['address'] == a.node_ip for x in node['status']['addresses'])):
        raise RuntimeError('Selected worker must be fenced, Ready, managed, and match explicit IP')
    drivers = [pod for pod in get('pods', '-n', 'gpu-operator')['items']
               if pod['spec'].get('nodeName') == a.node and any(
                   c['name'] == 'nvidia-driver-ctr' for c in pod['spec']['containers']) and
               pod['status'].get('phase') == 'Running']
    if (len(drivers) != 1 or drivers[0]['metadata'].get('deletionTimestamp') or
            not any(c['image'] == DRIVER for c in drivers[0]['spec']['containers']) or
            not any(DRIVER.split('@')[1] in c.get('imageID', '')
                    for c in drivers[0]['status'].get('containerStatuses', []))):
        raise RuntimeError('Exactly one running selected-worker candidate driver/imageID required')
    summary.update(node_uid=node['metadata']['uid'], driver_pod_uid=drivers[0]['metadata']['uid'])
    save('baseline.json', idle())
    created, config_uid = {}, None

    def owned(name):
        pod = get('pod', name, '-n', a.namespace)
        if pod['metadata']['uid'] != created[name]:
            raise RuntimeError('Unexpected same-name replacement retained: ' + name)
        return pod

    def execute(name, *command):
        owned(name)
        return run(kube + ['exec', '-n', a.namespace, name, '-c', 'main', '--', *command])

    def logs(name):
        owned(name)
        text = run(kube + ['logs', '-n', a.namespace, name, '-c', 'main'])
        save(name + '.log', text)
        return [json.loads(line) for line in text.splitlines() if line.startswith('{')]

    def wait_for(name, step):
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            pod = owned(name)
            if any(row.get('step') == step for row in logs(name)):
                return pod
            if pod['status'].get('phase') in ('Failed', 'Succeeded'):
                raise RuntimeError(name + ' terminated before ' + step)
            time.sleep(.5)
        raise TimeoutError(name + ':' + step)

    def delete(kind, name, uid):
        resource = get(kind, name, '-n', a.namespace)
        if resource['metadata']['uid'] != uid:
            raise RuntimeError('Cleanup refuses replacement ' + name)
        options = {'apiVersion': 'v1', 'kind': 'DeleteOptions', 'gracePeriodSeconds': 15,
                   'preconditions': {'uid': uid, 'resourceVersion': resource['metadata']['resourceVersion']}}
        plural = 'pods' if kind == 'pod' else 'configmaps'
        run(kube + ['delete', '--raw', f'/api/v1/namespaces/{a.namespace}/{plural}/{name}', '-f', '-'],
            data=json.dumps(options))
        run(kube + ['wait', '--for=delete', kind + '/' + name, '-n', a.namespace, '--timeout=45s'], timeout=50)

    def cleanup():
        errors = []
        for name, uid in list(created.items()):
            try:
                pod = owned(name)
                save(name + '.final-state.json', pod)
                try:
                    # Never open /tmp/start just to clean up an unstarted probe.
                    # A normal 15-second Pod deletion handles that case.
                    if pod['status'].get('phase') == 'Running' and any(
                            row.get('step') == 'holding-filled-vram' for row in logs(name)):
                        execute(name, 'touch', '/tmp/release')
                        wait_for(name, 'process-finished')
                    logs(name)
                except Exception as error:
                    errors.append(name + ' graceful release: ' + str(error))
                delete('pod', name, uid)
                del created[name]
            except Exception as error:
                errors.append(name + ': ' + str(error))
        if errors:
            raise RuntimeError('Cleanup incomplete; no force deletion: ' + '; '.join(errors))

    try:
        result = json.loads(run(kube + ['create', '-f', '-', '-o', 'json'], data=json.dumps(cm)))
        config_uid = result['metadata']['uid']
        for index, manifests in enumerate(rounds):
            record = {'order': [pod['metadata']['name'] for pod in manifests], 'identities': []}
            summary['rounds'].append(record)
            for manifest in manifests:
                pod = json.loads(run(kube + ['create', '-f', '-', '-o', 'json'], data=json.dumps(manifest)))
                created[pod['metadata']['name']] = pod['metadata']['uid']
            # All six containers first wait at the unchanged historical /tmp/start gate.
            for manifest in manifests:
                name = manifest['metadata']['name']
                run(kube + ['wait', '--for=condition=Ready', 'pod/' + name, '-n', a.namespace,
                            '--timeout=45s'], timeout=50)
            for manifest in manifests:
                name = manifest['metadata']['name']
                pod = owned(name)
                if any(c.get('restartCount', 0) for c in pod['status']['containerStatuses']):
                    raise RuntimeError('Unexpected restarted fixture container')
                cid = next(c['containerID'].split('://', 1)[1] for c in pod['status']['containerStatuses']
                           if c['name'] == 'main')
                gpu = manifest['metadata']['annotations']['nvidia.com/container.main.gpus.devices'].split('=')[1]
                expected = int(manifest['metadata']['annotations']['nvidia.com/container.main.gpu-memory.limit'][:-2])
                state = observe(gpu, cid)
                for limit in ('soft', 'hard'):
                    if not re.search(rf'{limit} limit:\s*{expected}\s*MiB', state['memory_limits'], re.I):
                        raise RuntimeError('Actual leaf memory limit does not match profile')
                if state['accounting'].get('memory.max', '').strip() != str(16 * 1024**3):
                    raise RuntimeError('Actual host leaf budget is not 16 GiB')
                record['identities'].append({'pod': name, 'uid': created[name], 'gpu': gpu, 'observation': state})
                execute(name, 'touch', '/tmp/start')
                wait_for(name, 'holding-filled-vram')
                rows = logs(name)
                oom = [r for r in rows if r.get('step') == 'above-hard-limit-allocation']
                if len(oom) != 1 or oom[0].get('result') != 2 or oom[0].get('mib') != expected + 1024:
                    raise RuntimeError('Above-hard+1GiB did not return typed CUDA OOM=2')
            before = {name: sum(r.get('step') == 'progress' and r.get('result') == 0 for r in logs(name))
                      for name in created}
            time.sleep(6)
            for item in record['identities']:
                name = item['pod']
                rows = logs(name)
                if sum(r.get('step') == 'progress' and r.get('result') == 0 for r in rows) <= before[name]:
                    raise RuntimeError('Independent six-way coexistence progress stalled: ' + name)
                if any(r.get('step') == 'progress-error' for r in rows):
                    raise RuntimeError('CUDA progress error: ' + name)
                state = observe(item['gpu'], item['observation']['container_id'])
                pids = {int(x['pid']) for x in state['processes']}
                if not any(int(line.split(',')[1].strip()) in pids for line in
                           state['compute_processes'].splitlines() if line.strip()):
                    raise RuntimeError('Container has no physical CUDA client on selected UUID')
                item['coexistence'] = state
            save(f'round-{index}-coexistence.json', record)
            # Signal all six first so teardown cannot strand later peers at the 120s gate.
            for name in created:
                execute(name, 'touch', '/tmp/release')
            for name in created:
                wait_for(name, 'process-finished')
                rows = logs(name)
                if any(r.get('result', 0) != 0 for r in rows
                       if r.get('step') in ('free', 'destroy', 'fill', 'sync')):
                    raise RuntimeError('CUDA fill or graceful teardown failed: ' + name)
                run(kube + ['wait', '--for=jsonpath={.status.phase}=Succeeded', 'pod/' + name,
                            '-n', a.namespace, '--timeout=20s'], timeout=25)
            cleanup()
            if get('node', a.node)['metadata']['uid'] != summary['node_uid']:
                raise RuntimeError('Selected node replaced during run')
            record['returned_idle'] = idle()
            save('summary.json', summary)
        summary['status'] = 'passed'
    except BaseException as error:
        summary.update(status='failed', error=str(error))
        raise
    finally:
        failures = []
        try:
            try:
                cleanup()
            except Exception as error:
                failures.append(str(error))
            if config_uid and not created:
                try:
                    delete('configmap', a.run_id, config_uid)
                except Exception as error:
                    failures.append(str(error))
            # Observe physical return even if release/delete had an error.
            try:
                summary['final_idle'] = idle()
            except Exception as error:
                failures.append(str(error))
            if failures:
                summary.update(status='failed', cleanup_error=failures)
                raise RuntimeError('Cleanup/physical return failed; see summary.json')
        finally:
            save('summary.json', summary)
    print(json.dumps({'status': summary['status'], 'output': str(a.output)}))


if __name__ == '__main__':
    main()
