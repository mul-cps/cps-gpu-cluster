#!/usr/bin/env python3
"""Default-inert root-only node qualification loop. No production enrollment."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from node_backend import QualificationNodeBackend, GATE, private_directory, private_read, require


CORE_SHA256 = '2c9770188a79406c674560616a8d9da8f4dafa275f0644d9669dfab001e7690e'
HEALTH_SHA256 = '22107515ecdc2ffe18afbafa8f15432ed9439aa6fc56ed9531649f790b29e769'
MANUAL_SHA256 = '5c84ab668dd276b0216199a964f42886712af9225f9fc702740bfa9bb361a39f'


def load_pinned(name, path, expected):
    path = Path(path)
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected, 'Pinned module source hash mismatch')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    # Execute the exact hashed bytes, with no second path read after validation.
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


class Kubernetes:
    def __init__(self, directory):
        directory = Path(directory)
        self.token = (directory / 'token').read_text().strip()
        require(bool(self.token), 'Projected Kubernetes credential required')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=str(directory / 'ca.crt'))))
        host = os.environ['KUBERNETES_SERVICE_HOST']
        port = os.environ.get('KUBERNETES_SERVICE_PORT_HTTPS', '443')
        require(re.fullmatch(r'[0-9a-fA-F:.]+', host) and port.isdigit(), 'Actual in-cluster Kubernetes endpoint required')
        self.base = 'https://' + ('[' + host + ']' if ':' in host else host) + ':' + port

    def call(self, method, path, value=None):
        raw = json.dumps(value).encode() if value is not None else None
        request = urllib.request.Request(self.base + path, data=raw, method=method,
            headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        try:
            with self.opener.open(request, timeout=5) as response:
                return json.loads(response.read(1048576))
        except urllib.error.HTTPError as error:
            if error.code == 404 and method == 'GET': return None
            raise ValueError('Kubernetes request failed with HTTP ' + str(error.code)) from None

    @staticmethod
    def pod_path(intent):
        return '/api/v1/namespaces/' + urllib.parse.quote(intent.namespace, safe='') + '/pods/' + urllib.parse.quote(intent.name, safe='')

    def pod(self, intent): return self.call('GET', self.pod_path(intent))
    def node(self, name): return self.call('GET', '/api/v1/nodes/' + urllib.parse.quote(name, safe=''))
    def delete(self, intent):
        return self.call('DELETE', self.pod_path(intent),
            {'apiVersion': 'v1', 'kind': 'DeleteOptions', 'preconditions': {'uid': intent.pod_uid}})


def command(argv):
    result = subprocess.run(argv, check=False, text=True, capture_output=True, timeout=10)
    require(result.returncode == 0, 'Qualification subprocess failed: ' + Path(argv[0]).name)
    return result.stdout


def cri_reader(binary, socket):
    prefix = [str(binary), '--runtime-endpoint', socket]
    def read(intent):
        value = json.loads(command(prefix + ['ps', '--label', 'io.kubernetes.pod.uid=' + intent.pod_uid,
            '--label', 'io.kubernetes.container.name=' + GATE, '-o', 'json']))
        containers = value.get('containers', [])
        require(len(containers) == 1, 'Exactly one actual running first gate required')
        cid = containers[0]['id']
        require(re.fullmatch(r'[a-f0-9]{64}', cid), 'Actual exact first-gate container ID required')
        return json.loads(command(prefix + ['inspect', cid]))
    return read


def gpu_clients(gpu_uuid):
    rows = command(['nvidia-smi', '--query-compute-apps=pid,gpu_uuid', '--format=csv,noheader,nounits'])
    clients = set()
    for line in rows.splitlines():
        if not line.strip(): continue
        parts = [part.strip() for part in line.split(',')]
        require(len(parts) == 2 and parts[0].isdigit() and parts[1].startswith('GPU-'), 'Unknown GPU client telemetry')
        if parts[1] == gpu_uuid:
            clients.add(int(parts[0]))
    return clients


def health(driver, verifier, *, module_directory='/sys/module',
           authority_directory='/run/cps-native-gpu/authority', boot_id=None):
    """Use the same source-pinned exact-load verifier as the first CPU gate."""
    require(driver.version == '615.71.09', 'Exact615.71.09 loaded driver/NVML agreement required')
    verifier.validate_native_driver_health(module_directory,
        authority_directory=authority_directory, boot_id=boot_id)
    return True


def awaiting_first_gate(pod, intent):
    """Recognize only a verified fresh Pending Pod whose first gate never ran.

    Caller must have no journal for this UID. This authorizes no mutation and
    does not substitute for the backend's actual CRI/proc/health checks.
    """
    require(isinstance(pod, dict), 'Actual Pod object required')
    status = pod.get('status', {})
    require(isinstance(status, dict), 'Actual Pod status required')
    if status.get('phase') != 'Pending':
        return False
    meta, spec = pod.get('metadata'), pod.get('spec')
    require(isinstance(meta, dict) and isinstance(spec, dict), 'Actual Pod identity/specification required')
    require(not meta.get('deletionTimestamp') and all(meta.get(k) == getattr(intent, attr) for k, attr in
        [('uid', 'pod_uid'), ('namespace', 'namespace'), ('name', 'name')]), 'Actual exact live enrolled Pod required')
    require(spec.get('nodeName') == intent.node and
        hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == intent.spec_sha256,
        'Reviewed enrolled Pod specification changed')
    init = spec.get('initContainers')
    containers = spec.get('containers')
    require(isinstance(init, list) and init and all(isinstance(c, dict) for c in init)
        and init[0].get('name') == GATE and isinstance(containers, list) and containers
        and all(isinstance(c, dict) for c in containers), 'Trusted first init gate required')
    require(not status.get('ephemeralContainerStatuses'), 'Ephemeral workload may have started')
    conditions = status.get('conditions', [])
    require(isinstance(conditions, list) and all(isinstance(c, dict) for c in conditions)
        and not any(c.get('type') == 'Initialized' and c.get('status') == 'True' for c in conditions),
        'Init sequence already completed')
    gate_running = False
    for key, approved in [('initContainerStatuses', init), ('containerStatuses', containers)]:
        values = status.get(key, [])
        names = {c.get('name') for c in approved}
        require(isinstance(values, list) and all(isinstance(s, dict) for s in values)
            and len({s.get('name') for s in values}) == len(values), 'Malformed actual container statuses')
        for value in values:
            state = value.get('state')
            require(value.get('name') in names and isinstance(state, dict) and len(state) == 1
                and type(value.get('restartCount', 0)) is int and value.get('restartCount', 0) == 0
                and not value.get('lastState'), 'Container history prevents fresh gate wait')
            if key == 'initContainerStatuses' and value.get('name') == GATE and 'running' in state:
                require(isinstance(state['running'], dict), 'Malformed running gate state')
                gate_running = True
                continue  # Actual backend must resolve its CRI identity.
            require(set(state) == {'waiting'} and isinstance(state['waiting'], dict)
                and state['waiting'].get('reason') in ('PodInitializing', 'ContainerCreating')
                and not value.get('containerID') and value.get('ready', False) is False
                and value.get('started') in (None, False), 'Container already ran or failed before cap assignment')
    return not gate_running


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--qualification', action='store_true')
    parser.add_argument('--controller-module', type=Path)
    parser.add_argument('--manual-helper', type=Path)
    parser.add_argument('--node', default='k3s-wk-gpu2')
    parser.add_argument('--state-root', type=Path, default=Path('/proc/1/root/run/cps-native-gpu'))
    parser.add_argument('--service-account', type=Path, default=Path('/var/run/secrets/kubernetes.io/serviceaccount'))
    parser.add_argument('--crictl', type=Path, default=Path('/proc/1/root/var/lib/rancher/k3s/data/65415f7708224bbfc7865f032e84da4a5123a3acebef70c8ee40fa991aa68555/bin/crictl'))
    parser.add_argument('--cri-socket', default='unix:///proc/1/root/run/k3s/containerd/containerd.sock')
    parser.add_argument('--iterations', type=int, default=1)
    parser.add_argument('--interval', type=float, default=2)
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({'state': 'inert', 'gpu_calls': False, 'api_calls': False, 'production_qualified': False}))
        return
    require(args.qualification and os.geteuid() == 0, 'Explicit root qualification execution required')
    require(args.controller_module is not None and args.manual_helper is not None, 'Both pinned source paths required')
    require(1 <= args.iterations <= 10000 and 0.1 <= args.interval <= 30, 'Bounded qualification polling required')
    models = load_pinned('_cps_native_controller', args.controller_module, CORE_SHA256)
    manual = load_pinned('_cps_native_manual', args.manual_helper, MANUAL_SHA256)
    verifier = load_pinned('_cps_native_health', args.controller_module.with_name('native_gpu_health.py'), HEALTH_SHA256)
    state = private_directory(args.state_root)
    authority = private_directory(state / 'authority')
    enrolled = private_directory(state / 'intents')
    journal = models.PrivateJournal(state / 'journal')
    kube = Kubernetes(args.service_account)
    driver = manual.Nvml()
    seen = {}
    failures = []
    try:
        for iteration in range(args.iterations):
            intents = []
            for path in sorted(enrolled.glob('*.json')):
                raw = private_read(path)
                intent = models.CapIntent(**raw)
                require(path.stem == intent.pod_uid and intent.node == args.node, 'Exact enrolled UID/node file required')
                require(intent.pod_uid not in seen or seen[intent.pod_uid] == intent, 'Enrolled intent changed during polling')
                seen[intent.pod_uid] = intent
                intents.append(intent)
            with journal.locked():
                require({record.intent.pod_uid for record in journal.records() if record.state != 'cleaned'}.issubset(seen),
                        'Pending journal requires original root enrollment before restart')
            backend = QualificationNodeBackend(models, manual, intents=list(seen.values()), driver=driver,
                get_pod=kube.pod, get_node=kube.node, get_cri=cri_reader(args.crictl, args.cri_socket),
                delete_pod=kube.delete, gpu_clients=gpu_clients, health=lambda: health(driver, verifier, authority_directory=str(authority)), state_root=state)
            controller = models.NativeCapController(backend, journal, enabled=True)
            for intent in seen.values():
                try:
                    record = journal.read(intent.pod_uid)
                    if record is not None and record.state == 'cleaned':
                        # A completed UID is a durable tombstone, even when a
                        # different Pod now occupies its old Kubernetes name.
                        print(json.dumps({'pod_uid': intent.pod_uid, 'state': 'cleaned',
                            'iteration': iteration, 'production_qualified': False}), flush=True)
                        continue
                    pod = kube.pod(intent)
                    if record is None and pod is not None and awaiting_first_gate(pod, intent):
                        print(json.dumps({'pod_uid': intent.pod_uid, 'state': 'awaiting-gate',
                            'iteration': iteration, 'production_qualified': False}), flush=True)
                        continue
                    if pod is None or pod.get('status', {}).get('phase') in ('Succeeded', 'Failed'):
                        if journal.read(intent.pod_uid) is None:
                            require(pod is None, 'Enrolled Pod ended before any cap journal existed')
                            continue
                        stopped = backend.check_cleanup(journal.read(intent.pod_uid).identity)
                        if stopped.live_tasks or stopped.gpu_clients:
                            print(json.dumps({'pod_uid': intent.pod_uid, 'state': 'retained-awaiting-stop',
                                'iteration': iteration, 'production_qualified': False}), flush=True)
                            continue
                        record = controller.cleanup(intent)
                    else:
                        record = controller.reconcile(intent)
                    print(json.dumps({'pod_uid': intent.pod_uid, 'state': record.state,
                                      'iteration': iteration, 'production_qualified': False}), flush=True)
                except Exception as error:
                    # No automatic receipt release/reset on failure. The sealed
                    # controller path separately invokes conditional quarantine.
                    failures.append((intent.pod_uid, type(error).__name__))
                    print(json.dumps({'pod_uid': intent.pod_uid, 'state': 'blocked-error',
                        'error': type(error).__name__, 'detail': str(error), 'iteration': iteration,
                        'production_qualified': False}), flush=True)
            if iteration + 1 < args.iterations:
                time.sleep(args.interval)
    finally:
        driver.close()
    require(not failures, 'Qualification polling observed blocked errors; inspect complete receipts/logs')


if __name__ == '__main__':
    main()
