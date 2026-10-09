#!/usr/bin/env python3
"""Root-reviewed qualification recovery after positively observed driver teardown.

Default invocation is inert. Module, device, SQL and allocation-ledger mutations
are deliberately outside this tool. Read teardown-recovery-contract.md first.
"""
import argparse
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import select
import stat
import subprocess
import tempfile
import time
import uuid

import abort_before_gate as prior

NAMESPACE, LEDGER, LABEL = prior.NAMESPACE, prior.LEDGER, prior.LABEL
PROTOCOL = 'cps-native-driver-teardown/v1'
ANNOTATIONS = ('cps.compute/teardown-audit', 'cps.compute/teardown-audit-uid',
               'cps.compute/teardown-audit-sha256')
LOCK_NAMES = ('journal', 'driver', 'maintenance')
_ORIGINAL_GATE = object()


class RecoveryError(ValueError):
    """The reviewed plan or a fresh trusted observation is insufficient."""


def require(value, message):
    if not value:
        raise RecoveryError(message)


def closed(value, keys, message):
    require(isinstance(value, dict) and set(value) == set(keys), message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha256(value):
    return raw_sha256(canonical(value).encode())


def raw_sha256(value):
    return 'sha256:' + hashlib.sha256(value).hexdigest()


def parse(raw):
    try:
        return prior.parse(raw)
    except ValueError as exc:
        raise RecoveryError(str(exc)) from exc


def _models():
    # Embedded, hash-pinned SDK source; importing it does not touch GPU or API.
    import node_agent
    return node_agent.load_models_from_snapshot()


def final_record(plan):
    value = copy.deepcopy(plan['journal']['record'])
    value['state'] = 'cleaned'
    return value


def final_journal_sha256(plan):
    if plan['journal']['record']['state'] == 'cleaned':
        return plan['journal']['sha256']
    return raw_sha256((canonical(final_record(plan)) + '\n').encode())


def validate_plan(plan, expected_sha256):
    require(prior.hash_value(expected_sha256) and sha256(plan) == expected_sha256,
            'Reviewed plan hash mismatch')
    closed(plan, ('version', 'qualification_only', 'operation_id', 'authority_namespace',
        'binding_id', 'attempt', 'ledger_uid', 'allocation_sha256', 'enrollment_uid',
        'enrollment_sha256', 'fence_command_sha256', 'tool_sha256', 'journal', 'scope', 'review'),
        'Unexpected reviewed plan schema')
    require(type(plan['version']) is int and plan['version'] == 1 and plan['qualification_only'] is True,
            'Explicit qualification plan required')
    require(plan['authority_namespace'] == NAMESPACE and prior.valid_uuid(plan['operation_id']),
            'Wrong authority/operation identity')
    require(isinstance(plan['binding_id'], str) and re.fullmatch('[0-9a-f]{60}', plan['binding_id'])
            and isinstance(plan['attempt'], str) and 0 < len(plan['attempt']) <= 128, 'Invalid binding/attempt')
    for key in ('ledger_uid', 'enrollment_uid'):
        require(prior.valid_uuid(plan[key]), 'Invalid actual API UID')
    for key in ('allocation_sha256', 'enrollment_sha256', 'fence_command_sha256', 'tool_sha256'):
        require(prior.hash_value(plan[key]), 'Missing reviewed SHA')
    require(plan['tool_sha256'] == raw_sha256(Path(__file__).read_bytes()), 'Recovery tool source changed')
    closed(plan['journal'], ('record', 'sha256'), 'Unexpected original journal schema')
    require(prior.hash_value(plan['journal']['sha256']), 'Invalid original raw journal SHA')
    m = _models()
    try:
        record = m.CapRecord.from_dict(plan['journal']['record'])
    except (TypeError, ValueError, KeyError) as exc:
        raise RecoveryError('Invalid typed original journal') from exc
    require(record.to_dict() == plan['journal']['record'] and record.state in ('sealed', 'cleaned')
            and record.retirement is None and record.readback == m.CapLimit(record.intent.cap_bytes, record.intent.cap_bytes),
            'Exact finite sealed/legacy-cleaned original journal required')
    scope = plan['scope']
    closed(scope, ('node', 'node_uid', 'boot_id', 'driver_generation', 'loaded_modules',
        'module_sha256', 'nvidia_gpus', 'pilot_pods', 'journal_directory'), 'Unexpected node-wide scope')
    require(scope['node'] == prior.NODE and scope['node_uid'] == prior.NODE_UID
            and prior.valid_uuid(scope['boot_id']) and prior.valid_uuid(scope['driver_generation']),
            'Wrong selected node/boot/old generation')
    require(record.identity.epoch == m.DriverEpoch(scope['node_uid'], scope['boot_id'],
        scope['driver_generation'], prior.GPU), 'Journal old epoch disagrees with selected node')
    loaded = scope['loaded_modules']
    require(isinstance(loaded, list) and loaded == sorted(set(loaded))
            and {'nvidia', 'nvidia_uvm'} <= set(loaded)
            and all(isinstance(n, str) and re.fullmatch('nvidia(?:_[a-z0-9_]+)?', n) for n in loaded),
            'Complete sorted NVIDIA module scope required')
    require(isinstance(scope['module_sha256'], dict) and set(scope['module_sha256']) == set(loaded)
            and all(prior.hash_value(v) for v in scope['module_sha256'].values()), 'Unpinned loaded module')
    gpus = scope['nvidia_gpus']
    require(isinstance(gpus, list) and 1 <= len(gpus) <= 64, 'Complete node-wide GPU scope required')
    for gpu in gpus:
        closed(gpu, ('gpu_uuid', 'pci_bdf'), 'Unexpected GPU scope')
        require(isinstance(gpu['gpu_uuid'], str) and gpu['gpu_uuid'].startswith('GPU-')
                and prior.valid_uuid(gpu['gpu_uuid'][4:]) and isinstance(gpu['pci_bdf'], str)
                and re.fullmatch('[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\\.[0-7]', gpu['pci_bdf']), 'Invalid GPU/BDF')
    require(gpus == sorted(gpus, key=lambda g: g['pci_bdf'])
            and len({g['pci_bdf'] for g in gpus}) == len(gpus)
            and len({g['gpu_uuid'] for g in gpus}) == len(gpus)
            and prior.GPU in {g['gpu_uuid'] for g in gpus}, 'Duplicate/foreign/unsorted physical GPU scope')
    pods = scope['pilot_pods']
    require(isinstance(pods, list) and 1 <= len(pods) <= 256, 'Complete registered pilot Pod scope required')
    for pod in pods:
        closed(pod, ('namespace', 'name', 'pod_uid'), 'Unexpected pilot Pod scope')
        require(pod['namespace'] in ('jupyterhub', 'cit-jhub') and isinstance(pod['name'], str)
                and re.fullmatch('[a-z0-9][a-z0-9.-]{0,252}', pod['name'])
                and prior.valid_uuid(pod['pod_uid']), 'Invalid scoped Pod identity')
    require(pods == sorted(pods, key=lambda p: (p['namespace'], p['name'], p['pod_uid']))
            and len({p['pod_uid'] for p in pods}) == len(pods), 'Duplicate/unsorted Pod scope')
    _file_identity(scope['journal_directory'])
    review = plan['review']
    closed(review, ('operator', 'reason', 'old_module_source_sha256', 'load_manifest_sha256'), 'Unexpected Root review')
    require(review['operator'] == 'root' and review['reason'] == 'legacy-cap-after-confirmed-driver-teardown'
            and prior.hash_value(review['old_module_source_sha256'])
            and prior.hash_value(review['load_manifest_sha256']), 'Missing pinned Root teardown review')


def _file_identity(value):
    closed(value, ('device', 'inode'), 'Unexpected protected filesystem identity')
    require(all(type(v) is int and v > 0 for v in value.values()), 'Invalid protected filesystem identity')


def _locks(value):
    closed(value, LOCK_NAMES, 'Exact journal/driver/maintenance locks required')
    for item in value.values():
        _file_identity(item)
    require(len({(v['device'], v['inode']) for v in value.values()}) == 3, 'Locks are not independent')


def _identity(proof, stage, plan, digest):
    require(proof['stage'] == stage and proof['operation_id'] == plan['operation_id']
            and proof['plan_sha256'] == digest, 'Foreign/stale operation proof')


def _zeros(proof, names):
    require(all(type(proof[n]) is int and proof[n] == 0 for n in names), 'Nonzero/invalid quiescence proof')


def validate_before(proof, plan, plan_sha256):
    closed(proof, ('stage', 'operation_id', 'plan_sha256', 'scope', 'journal_sha256', 'locks',
        'native_writers_quiesced', 'locks_held', 'driver_healthy', 'gpu_memory_bytes',
        'gpu_fd_clients', 'compute_apps', 'pod_runtime_tasks', 'gate_sha256'), 'Unexpected before proof')
    _identity(proof, 'before', plan, plan_sha256)
    require(proof['scope'] == plan['scope'] and proof['journal_sha256'] == plan['journal']['sha256'],
            'Fresh original scope/journal differs from reviewed plan')
    _locks(proof['locks'])
    require(all(proof[n] is True for n in ('native_writers_quiesced', 'locks_held', 'driver_healthy')),
            'Unproven Root writer fence/old driver health')
    require(isinstance(proof['gpu_memory_bytes'], dict)
            and set(proof['gpu_memory_bytes']) == {g['gpu_uuid'] for g in plan['scope']['nvidia_gpus']}
            and all(type(v) is int and v == 0 for v in proof['gpu_memory_bytes'].values()),
            'Every NVIDIA GPU must have positively observed zero physical usage')
    _zeros(proof, ('gpu_fd_clients', 'compute_apps', 'pod_runtime_tasks'))
    require(proof['gate_sha256'] is None or prior.hash_value(proof['gate_sha256']), 'Invalid owned gate SHA')


def validate_teardown(proof, plan, plan_sha256, before, *, journal_sha256=None, gate_sha256=_ORIGINAL_GATE):
    closed(proof, ('stage', 'operation_id', 'plan_sha256', 'node_uid', 'boot_id',
        'old_driver_generation', 'old_generation_invalidated', 'sysfs_modules', 'proc_modules',
        'pci_unbound', 'gpu_fd_clients', 'pod_runtime_tasks', 'locks', 'journal_sha256',
        'gate_sha256', 'native_writers_quiesced', 'locks_held', 'new_load_absent'), 'Unexpected teardown proof')
    _identity(proof, 'teardown', plan, plan_sha256)
    require(proof['node_uid'] == plan['scope']['node_uid'] and proof['boot_id'] == plan['scope']['boot_id']
            and proof['old_driver_generation'] == plan['scope']['driver_generation'], 'Node/boot/old epoch changed')
    require(all(proof[n] is True for n in ('old_generation_invalidated', 'native_writers_quiesced',
        'locks_held', 'new_load_absent')), 'Unproven physical teardown or writer fence')
    require(proof['sysfs_modules'] == [] and proof['proc_modules'] == []
            and proof['pci_unbound'] == [g['pci_bdf'] for g in plan['scope']['nvidia_gpus']],
            'Old NVIDIA modules/devices still present or scope incomplete')
    _zeros(proof, ('gpu_fd_clients', 'pod_runtime_tasks'))
    require(proof['locks'] == before['locks'], 'Root lock identity changed')
    require(proof['journal_sha256'] == (journal_sha256 or plan['journal']['sha256']), 'Protected journal changed')
    gate = before['gate_sha256'] if gate_sha256 is _ORIGINAL_GATE else gate_sha256
    require(proof['gate_sha256'] == gate, 'Owned gate changed')


def names(plan):
    suffix = plan['binding_id'][:40]
    return 'cps-native-teardown-' + suffix, 'cps-native-cleanup-' + suffix


def receipt(plan):
    return {'version': 1, 'binding_id': plan['binding_id'], 'attempt': plan['attempt'],
            'intent': plan['journal']['record']['intent'], 'cleanup_confirmed': True}


def audit_body(plan, before, teardown):
    payload = {'protocol': PROTOCOL, 'plan_sha256': sha256(plan), 'plan': plan,
               'before': before, 'teardown': teardown}
    return {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,
        'metadata': {'name': names(plan)[0], 'namespace': NAMESPACE, 'labels': {LABEL: plan['binding_id']}},
        'data': {'teardown.json': canonical(payload)}}


def cleanup_body(plan, actual_audit):
    ann = dict(zip(ANNOTATIONS, (names(plan)[0], actual_audit['metadata']['uid'],
                                sha256(parse(actual_audit['data']['teardown.json'])))))
    return {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,
        'metadata': {'name': names(plan)[1], 'namespace': NAMESPACE,
                     'labels': {LABEL: plan['binding_id']}, 'annotations': ann},
        'data': {'receipt.json': canonical(receipt(plan))}}


def immutable_cm(actual, expected):
    require(isinstance(actual, dict) and actual.get('apiVersion') == 'v1' and actual.get('kind') == 'ConfigMap'
            and actual.get('immutable') is True and actual.get('data') == expected['data']
            and not actual.get('binaryData'), 'Actual immutable authority document differs')
    meta = actual.get('metadata', {})
    require(prior.valid_uuid(meta.get('uid')) and meta.get('name') == expected['metadata']['name']
            and meta.get('namespace') == NAMESPACE and meta.get('labels') == expected['metadata']['labels']
            and meta.get('annotations', {}) == expected['metadata'].get('annotations', {})
            and not meta.get('deletionTimestamp') and not meta.get('ownerReferences'),
            'Actual authority UID/ownership/provenance differs')


def tombstone(plan, actual_cleanup):
    return {'enrollment_uid': plan['enrollment_uid'], 'receipt_uid': actual_cleanup['metadata']['uid'],
            'receipt': receipt(plan)}


def observe(backend, plan):
    node = backend.get_node(plan['scope']['node'])
    require(isinstance(node, dict) and node.get('apiVersion') == 'v1' and node.get('kind') == 'Node'
            and node.get('metadata', {}).get('uid') == plan['scope']['node_uid']
            and node['metadata'].get('name') == plan['scope']['node'], 'Fresh actual Kubernetes node UID changed')
    ledger = backend.get_cm(LEDGER)
    try:
        state, allocation, enrollment = prior.ledger_state(ledger, plan)
        prior.trusted_enrollment(backend.get_cm('cps-native-enrollment-' + plan['binding_id'][:40]), plan, enrollment)
    except ValueError as exc:
        raise RecoveryError(str(exc)) from exc
    require(allocation['state'] in ('enrolled', 'releasing'), 'Already released/foreign allocation cannot be recovered')
    require(enrollment['intent'] == plan['journal']['record']['intent'], 'Journal differs from frozen enrollment')
    pods = []
    pod_names = set()
    for binding_id, row in state['allocations'].items():
        require(isinstance(row, dict), 'Malformed global allocation row')
        if row.get('node_uid') != plan['scope']['node_uid']:
            continue
        intent = row.get('intent')
        if intent is None:
            require(row.get('state') == 'released', 'Unregistered live allocation prevents maintenance')
            pod_names.add((row.get('namespace'), row.get('name')))
            continue
        require(isinstance(binding_id, str) and re.fullmatch('[0-9a-f]{60}', binding_id)
                and row.get('binding_id') == binding_id, 'Foreign peer binding identity')
        try:
            prior.validate_enrollment({key: row[key] for key in prior.ENROLLMENT_KEYS})
        except (KeyError, ValueError) as exc:
            raise RecoveryError('Malformed/mismatched registered peer intent') from exc
        # Query exactly the validated intent's name. An absent outer alias must
        # never stand in for absence of a live peer's actual registered Pod.
        pod_names.add((intent['namespace'], intent['name']))
        pods.append({key: intent[key] for key in ('namespace', 'name', 'pod_uid')})
    require(sorted(pods, key=lambda p: (p['namespace'], p['name'], p['pod_uid'])) == plan['scope']['pilot_pods'],
            'Plan omits/changes registered selected-node Pod scope')
    for namespace, name in sorted(pod_names):
        require(namespace in ('jupyterhub', 'cit-jhub') and isinstance(name, str) and name,
                'Foreign pilot source namespace/name')
        require(backend.get_pod(namespace, name) is None, 'Fresh actual Pod absence not confirmed')


def validate_completion(proof, plan, digest, before):
    closed(proof, ('stage', 'operation_id', 'plan_sha256', 'teardown', 'journal_record',
        'journal_raw_sha256', 'archive_sha256', 'tombstone', 'gate_absent'), 'Unexpected completion proof')
    _identity(proof, 'complete', plan, digest)
    require(proof['journal_record'] == final_record(plan)
            and proof['journal_raw_sha256'] == final_journal_sha256(plan)
            and proof['archive_sha256'] == plan['journal']['sha256'] and proof['gate_absent'] is True,
            'Local journal/archive/gate completion differs')
    validate_teardown(proof['teardown'], plan, digest, before,
        journal_sha256=proof['journal_raw_sha256'], gate_sha256=None)


def execute_recovery(backend, plan, *, expected_plan_sha256):
    validate_plan(plan, expected_plan_sha256)
    with backend.fence(plan) as fence:
        before = fence.before
        validate_before(before, plan, expected_plan_sha256)
        observe(backend, plan)
        audit_name, cleanup_name = names(plan)
        require(backend.get_cm(audit_name, absent=True) is None
                and backend.get_cm(cleanup_name, absent=True) is None, 'Existing completion/audit requires review; replay forbidden')
        teardown = fence.verify_teardown()
        validate_teardown(teardown, plan, expected_plan_sha256, before)
        observe(backend, plan)
        expected = audit_body(plan, before, teardown)
        created = backend.create_cm(expected)
        immutable_cm(created, expected)
        audit = backend.get_cm(audit_name)
        immutable_cm(audit, expected)
        require(audit['metadata']['uid'] == created['metadata']['uid'], 'Audit replaced after create')
        # Recheck physical teardown before publishing a consumable cleanup.
        validate_teardown(fence.verify_teardown(), plan, expected_plan_sha256, before)
        observe(backend, plan)
        expected_cleanup = cleanup_body(plan, audit)
        created = backend.create_cm(expected_cleanup)
        immutable_cm(created, expected_cleanup)
        cleanup = backend.get_cm(cleanup_name)
        immutable_cm(cleanup, expected_cleanup)
        require(cleanup['metadata']['uid'] == created['metadata']['uid'], 'Cleanup replaced after create')
        completion = fence.publish_local(audit, cleanup)
        validate_completion(completion, plan, expected_plan_sha256, before)
        require(completion['tombstone'] == tombstone(plan, cleanup), 'Local completion lost actual immutable UIDs')
        observe(backend, plan)
        actual_audit = backend.get_cm(audit_name)
        immutable_cm(actual_audit, expected)
        require(actual_audit['metadata']['uid'] == audit['metadata']['uid'], 'Audit authority replaced')
        actual_cleanup = backend.get_cm(cleanup_name)
        immutable_cm(actual_cleanup, expected_cleanup)
        require(actual_cleanup['metadata']['uid'] == cleanup['metadata']['uid'], 'Cleanup authority replaced')
        final = fence.verify_completion()
        validate_completion(final, plan, expected_plan_sha256, before)
        require(final == completion, 'Completed protected evidence changed')
        return {'version': 1, 'state': 'teardown-cleanup-published', 'plan_sha256': expected_plan_sha256,
                'audit_uid': audit['metadata']['uid'], 'cleanup_uid': cleanup['metadata']['uid'],
                'binding_id': plan['binding_id'], 'attempt': plan['attempt'],
                'allocation_released': False, 'device_calls': False}


class RootFence:
    """A pinned Root process holds writer locks until all readbacks finish."""
    def __init__(self, command, plan, timeout=120):
        require(isinstance(command, list) and command and all(isinstance(x, str) and x for x in command)
                and sha256(command) == plan['fence_command_sha256'], 'Pinned Root command mismatch')
        self.command, self.plan, self.timeout = command, plan, timeout
        self.nonce, self.process, self.buffer = str(uuid.uuid4()), None, b''

    def ensure_alive(self):
        require(self.process is not None and self.process.poll() is None, 'Root fence exited; retain evidence')

    def send(self, op, **values):
        self.ensure_alive()
        require(not self.buffer and not select.select([self.process.stdout], [], [], 0)[0],
                'Unsolicited/prequeued Root response')
        try:
            self.process.stdin.write((canonical({'op': op, 'nonce': self.nonce, **values}) + '\n').encode())
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise RecoveryError('Root fence lost') from exc

    def line(self, event):
        deadline = time.monotonic() + self.timeout
        while b'\n' not in self.buffer:
            self.ensure_alive()
            remaining = deadline - time.monotonic()
            require(remaining > 0, 'Root proof timed out')
            ready, _, _ = select.select([self.process.stdout], [], [], remaining)
            require(ready, 'Root proof timed out')
            chunk = os.read(self.process.stdout.fileno(), 65536)
            require(chunk and len(self.buffer) + len(chunk) <= 262144, 'Root proof EOF/oversized')
            self.buffer += chunk
        raw, self.buffer = self.buffer.split(b'\n', 1)
        require(not self.buffer, 'Unsolicited/prequeued Root response')
        value = parse(raw)
        closed(value, ('event', 'nonce', 'observed_at', 'proof'), 'Unexpected Root response')
        require(value['event'] == event and value['nonce'] == self.nonce, 'Foreign/replayed Root response')
        try:
            stamp = datetime.fromisoformat(value['observed_at'].replace('Z', '+00:00'))
            age = (datetime.now(timezone.utc) - stamp).total_seconds()
            require(value['observed_at'].endswith('Z') and stamp.tzinfo is not None and -5 <= age <= 30,
                    'Stale Root response')
        except (AttributeError, TypeError, ValueError) as exc:
            raise RecoveryError('Invalid/stale Root timestamp') from exc
        return value['proof']

    def __enter__(self):
        self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            self.send('acquire', plan=self.plan, plan_sha256=sha256(self.plan))
            self.before = self.line('fence-acquired')
            validate_before(self.before, self.plan, sha256(self.plan))
        except BaseException:
            self.close()
            raise
        return self

    def verify_teardown(self):
        self.send('verify-teardown')
        return self.line('fence-teardown-verified')

    def publish_local(self, audit, cleanup):
        self.send('publish-local', plan_sha256=sha256(self.plan), audit=audit, cleanup=cleanup)
        return self.line('fence-local-published')

    def verify_completion(self):
        self.send('verify-completion')
        return self.line('fence-completion-verified')

    def close(self):
        if self.process is None:
            return False
        release_requested = False
        try:
            if self.process.poll() is None:
                self.send('release')
                release_requested = True
                self.process.wait(timeout=5)
        except (OSError, RecoveryError, subprocess.TimeoutExpired):
            self.process.kill(); self.process.wait(timeout=5)
        finally:
            for stream in (self.process.stdin, self.process.stdout):
                stream.close()
        return release_requested

    def __exit__(self, exc_type, *_):
        release_requested = self.close()
        if exc_type is None:
            require(release_requested and self.process.returncode == 0,
                    'Root fence exited before requested release or did not release cleanly; retain evidence')


class KubernetesBackend:
    """Only actual GET and immutable ConfigMap CREATE; no patch/delete/release."""
    def __init__(self, command, *, kubeconfig=None, context=None):
        self.command = ['kubectl']
        if kubeconfig: self.command += ['--kubeconfig', kubeconfig]
        if context: self.command += ['--context', context]
        self.fence_command, self.live_fence = command, None

    def fence(self, plan):
        self.live_fence = RootFence(self.fence_command, plan)
        return self.live_fence

    def call(self, args, *, body=None, absent=False):
        self.live_fence.ensure_alive()
        result = subprocess.run(self.command + args, input=canonical(body) if body is not None else None,
            text=True, capture_output=True, timeout=30)
        self.live_fence.ensure_alive()
        require(result.returncode == 0, 'Kubernetes transport denied/conflicted/unavailable')
        if absent and not result.stdout.strip(): return None
        value = parse(result.stdout)
        require(isinstance(value, dict), 'Kubernetes response is not an actual object')
        return value

    def get_cm(self, name, absent=False):
        return self.call(['get', 'configmap', name, '-n', NAMESPACE, '-o', 'json']
            + (['--ignore-not-found'] if absent else []), absent=absent)

    def get_node(self, name):
        return self.call(['get', 'node', name, '-o', 'json'])

    def get_pod(self, namespace, name):
        return self.call(['get', 'pod', name, '-n', namespace, '-o', 'json', '--ignore-not-found'], absent=True)

    def create_cm(self, body):
        return self.call(['create', '-f', '-', '-o', 'json'], body=body)


def _directory(path, uid):
    info = Path(path).lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == uid and stat.S_IMODE(info.st_mode) == 0o700,
            'Protected Root0700 directory required')
    return info


def _read(path, uid, mode=0o600):
    _directory(Path(path).parent, uid)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_uid == uid and stat.S_IMODE(info.st_mode) == mode
                and info.st_nlink == 1, 'Protected Root regular file required')
        raw = stream.read(262145)
    require(len(raw) <= 262144, 'Protected record oversized')
    return raw


def _write(path, raw, uid, *, mode=0o600, create=True):
    path = Path(path)
    _directory(path.parent, uid)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.teardown-', delete=False) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), mode)
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        if create:
            # Atomic no-overwrite publication, then remove the temporary link.
            os.link(temporary, path, follow_symlinks=False)
            temporary.unlink(); temporary = None
        else:
            require(_read(path, uid) is not None, 'Original protected journal missing')
            os.replace(temporary, path); temporary = None
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)


def _mkdir_private(path, uid, *, exist_ok=False):
    path = Path(path)
    _directory(path.parent, uid)
    path.mkdir(mode=0o700, exist_ok=exist_ok)
    _directory(path, uid)
    # The containing directory entry must survive before any old journal/gate
    # is changed. fsyncing files and their immediate new directory is not enough.
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def _lock_check(fd, path, expected, uid):
    info, current = os.fstat(fd), Path(path).lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == uid and stat.S_IMODE(info.st_mode) == 0o600
            and info.st_nlink == 1 and (info.st_dev, info.st_ino) == (current.st_dev, current.st_ino)
            and expected == {'device': info.st_dev, 'inode': info.st_ino}, 'Root lock fd/path changed')
    key = (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino)
    owned = False
    for line in Path('/proc/locks').read_text().splitlines():
        fields = line.split()
        if len(fields) != 8 or fields[1:4] != ['FLOCK', 'ADVISORY', 'WRITE'] or fields[4] != str(os.getpid()):
            continue
        parts = fields[5].split(':')
        if len(parts) == 3 and (int(parts[0], 16), int(parts[1], 16), int(parts[2])) == key:
            owned = True
    require(owned, 'This Root helper does not own the exclusive lock')


def complete_local(state_root, plan, audit_cm, cleanup_cm, *, before, teardown, lock_fds, trusted_uid=0):
    """Called by the pinned host helper under its still-held real writer locks."""
    require(os.geteuid() == trusted_uid, 'Root helper identity required')
    digest = sha256(plan)
    validate_plan(plan, digest); validate_before(before, plan, digest)
    validate_teardown(teardown, plan, digest, before)
    expected_audit = audit_body(plan, before, teardown)
    immutable_cm(audit_cm, expected_audit)
    immutable_cm(cleanup_cm, cleanup_body(plan, audit_cm))
    state = Path(state_root)
    _directory(state, trusted_uid)
    for directory in ('journal', 'authority', 'operator', 'receipts'):
        _directory(state / directory, trusted_uid)
    info = _directory(state / 'journal', trusted_uid)
    require(plan['scope']['journal_directory'] == {'device': info.st_dev, 'inode': info.st_ino},
            'Original protected journal directory changed')
    closed(lock_fds, LOCK_NAMES, 'All Root lock fds required')
    paths = {'journal': state / 'journal/.writer.lock', 'driver': state / 'authority/.driver-loader.lock',
             'maintenance': state / 'operator/.teardown.lock'}
    for key in LOCK_NAMES:
        _lock_check(lock_fds[key], paths[key], before['locks'][key], trusted_uid)
    pod_uid = plan['journal']['record']['intent']['pod_uid']
    journal_path, gate_path = state / 'journal' / (pod_uid + '.json'), state / 'receipts' / (pod_uid + '.json')
    original = _read(journal_path, trusted_uid)
    require(original is not None and raw_sha256(original) == plan['journal']['sha256']
            and parse(original) == plan['journal']['record'], 'Original journal bytes changed')
    gate = _read(gate_path, trusted_uid)
    require((None if gate is None else raw_sha256(gate)) == before['gate_sha256'], 'Owned gate bytes changed')
    if gate is not None:
        m = _models()
        from dataclasses import replace
        expected_gate = replace(m.CapRecord.from_dict(plan['journal']['record']), state='sealed').receipt()
        require(parse(gate) == expected_gate, 'Foreign gate must be retained')
    archive_dir = state / 'operator' / 'teardown-recovery'
    _mkdir_private(archive_dir, trusted_uid, exist_ok=True)
    archive_dir = archive_dir / plan['operation_id']
    _mkdir_private(archive_dir, trusted_uid)
    _write(archive_dir / 'original-journal.json', original, trusted_uid, mode=0o400)
    _write(archive_dir / 'audit.json', (canonical(audit_cm) + '\n').encode(), trusted_uid, mode=0o400)
    _write(archive_dir / 'cleanup.json', (canonical(cleanup_cm) + '\n').encode(), trusted_uid, mode=0o400)
    if gate is not None:
        _write(archive_dir / 'original-gate.json', gate, trusted_uid, mode=0o400)
        gate_path.unlink()
        directory = os.open(gate_path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(directory)
        finally: os.close(directory)
    if plan['journal']['record']['state'] == 'sealed':
        _write(journal_path, (canonical(final_record(plan)) + '\n').encode(), trusted_uid, create=False)
    published = state / 'published-cleanup'
    _mkdir_private(published, trusted_uid, exist_ok=True)
    mark = tombstone(plan, cleanup_cm)
    _write(published / (pod_uid + '.json'), (canonical(mark) + '\n').encode(), trusted_uid)
    for key in LOCK_NAMES:
        _lock_check(lock_fds[key], paths[key], before['locks'][key], trusted_uid)
    return read_local_completion(state, plan, audit_cm, cleanup_cm, trusted_uid=trusted_uid)


def read_local_completion(state_root, plan, audit_cm, cleanup_cm, *, trusted_uid=0):
    """Fresh protected readback; host helper independently re-probes teardown/locks."""
    require(os.geteuid() == trusted_uid, 'Root helper identity required')
    validate_plan(plan, sha256(plan))
    audit = parse(audit_cm['data']['teardown.json'])
    closed(audit, ('protocol', 'plan_sha256', 'plan', 'before', 'teardown'), 'Invalid retained audit')
    require(audit['protocol'] == PROTOCOL and audit['plan'] == plan
            and audit['plan_sha256'] == sha256(plan), 'Foreign retained audit')
    validate_before(audit['before'], plan, sha256(plan))
    validate_teardown(audit['teardown'], plan, sha256(plan), audit['before'])
    immutable_cm(audit_cm, audit_body(plan, audit['before'], audit['teardown']))
    immutable_cm(cleanup_cm, cleanup_body(plan, audit_cm))
    state = Path(state_root)
    _directory(state, trusted_uid)
    for part in ('journal', 'receipts', 'published-cleanup', 'operator', 'operator/teardown-recovery',
                 'operator/teardown-recovery/' + plan['operation_id']):
        _directory(state / part, trusted_uid)
    info = _directory(state / 'journal', trusted_uid)
    require(plan['scope']['journal_directory'] == {'device': info.st_dev, 'inode': info.st_ino},
            'Protected journal directory replaced')
    uid = plan['journal']['record']['intent']['pod_uid']
    archive = state / 'operator/teardown-recovery' / plan['operation_id']
    original = _read(archive / 'original-journal.json', trusted_uid, mode=0o400)
    current = _read(state / 'journal' / (uid + '.json'), trusted_uid)
    require(original is not None and raw_sha256(original) == plan['journal']['sha256']
            and parse(original) == plan['journal']['record'], 'Original archive bytes changed')
    require(current is not None and raw_sha256(current) == final_journal_sha256(plan)
            and parse(current) == final_record(plan), 'Terminal journal bytes changed')
    require(parse(_read(archive / 'audit.json', trusted_uid, mode=0o400)) == audit_cm
            and parse(_read(archive / 'cleanup.json', trusted_uid, mode=0o400)) == cleanup_cm,
            'Retained actual authority UID/provenance changed')
    mark = parse(_read(state / 'published-cleanup' / (uid + '.json'), trusted_uid))
    require(mark == tombstone(plan, cleanup_cm) and _read(state / 'receipts' / (uid + '.json'), trusted_uid) is None,
            'Protected completion/gate changed')
    return {'journal_record': parse(current), 'journal_raw_sha256': raw_sha256(current),
            'archive_sha256': raw_sha256(original), 'tombstone': mark, 'gate_absent': True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--qualification', action='store_true')
    for flag in ('plan', 'plan-sha256', 'fence-command-file', 'output', 'kubeconfig', 'context'):
        parser.add_argument('--' + flag)
    args = parser.parse_args(argv)
    if not args.execute:
        print(canonical({'state': 'inert', 'api_calls': False, 'module_calls': False, 'device_calls': False})); return 0
    require(args.qualification and args.plan and args.plan_sha256 and args.fence_command_file and args.output,
            'Explicit --execute --qualification, reviewed plan SHA, pinned Root argv and private output required')
    plan = parse(Path(args.plan).read_bytes())
    validate_plan(plan, args.plan_sha256)
    require(not Path(args.output).exists(), 'Preserve existing receipt')
    command = parse(Path(args.fence_command_file).read_bytes())
    RootFence(command, plan)  # Pin before transport or process creation.
    result = execute_recovery(KubernetesBackend(command, kubeconfig=args.kubeconfig, context=args.context),
        plan, expected_plan_sha256=args.plan_sha256)
    prior.private_output(args.output, result)
    print(canonical(result)); return 0


if __name__ == '__main__':
    main()
