#!/usr/bin/env python3
"""Default-inert GPU2 node service for trusted immutable group enrollments.

Only --execute with an enabled root-selected config opens Kubernetes or NVML.
A lease, deadline or cancellation request is never evidence of native cleanup.
"""
from __future__ import annotations
import argparse
from dataclasses import fields
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HERE = Path(__file__).resolve().parent
NAMESPACES = {'cps': 'jupyterhub', 'cit': 'cit-jhub'}
LABEL = 'cps.compute/native-binding'
SOURCE_PINS = {
    'native_gpu_controller.py': 'f40ef40f71c9f1206f23fb7052fd69aafd103c0f03a24e6bf3987395dacfd179',
    'native_gpu_health.py': 'ac3ec5477c0d1f057e8973172a8aa97ffe37a5bd139b4b537b9f8d17caf50a20',
    'node_backend.py': 'fb5651ea10118de02ee2e9601a765f947d2ae61f1b2e8670d523912b594afda0',
    'poll.py': '6199b8960215f571f722c45a48bb534a9201f6c1e03b32f0f4aa8cb9f83cfce7',
    'pod_cap.py': '5c84ab668dd276b0216199a964f42886712af9225f9fc702740bfa9bb361a39f',
}
_NAME = re.compile(r'[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?')
_TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9:_.@/-]{0,255}')
_IMAGE = re.compile(r'[^\s@]+@sha256:[a-f0-9]{64}')


def require(condition, message):
    if not condition: raise ValueError(message)


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate JSON field')
        value[key] = item
    return value


def parse(raw):
    require(isinstance(raw, (str, bytes)) and len(raw) <= 1048576, 'Bounded JSON required')
    return json.loads(raw, object_pairs_hook=unique)


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def canonical_sha256(value):
    return 'sha256:' + hashlib.sha256(canonical_json(value).encode()).hexdigest()


def closed(value, keys, description):
    require(isinstance(value, dict) and set(value) == set(keys), description)


def canonical_uuid(value):
    try: return isinstance(value, str) and str(uuid.UUID(value)) == value
    except (ValueError, AttributeError, TypeError): return False


def token(value): return isinstance(value, str) and _TOKEN.fullmatch(value) is not None


def validate_config(config):
    closed(config, {'version', 'enabled', 'authority_namespace', 'policy_hash', 'pool', 'workspaces'},
           'Closed node authority configuration required')
    require(type(config['version']) is int and config['version'] == 1 and type(config['enabled']) is bool,
            'Versioned explicit node activation required')
    require(isinstance(config['authority_namespace'], str) and _NAME.fullmatch(config['authority_namespace'])
            and config['authority_namespace'] not in NAMESPACES.values(), 'Separate authority namespace required')
    require(isinstance(config['policy_hash'], str) and re.fullmatch(r'sha256:[a-f0-9]{64}', config['policy_hash']),
            'Pinned policy hash required')
    pool = config['pool']
    closed(pool, {'node', 'node_uid', 'gpu_uuid', 'max_workspaces'}, 'Closed operator-selected pool required')
    require(pool['node'] == 'k3s-wk-gpu2' and canonical_uuid(pool['node_uid'])
            and isinstance(pool['gpu_uuid'], str) and pool['gpu_uuid'].startswith('GPU-')
            and canonical_uuid(pool['gpu_uuid'][4:]) and type(pool['max_workspaces']) is int
            and pool['max_workspaces'] in (1, 2), 'Exact bounded GPU2 pool required')
    require(isinstance(config['workspaces'], dict) and len(config['workspaces']) <= 32,
            'Bounded trusted workspace allowlist required')
    for key, value in config['workspaces'].items():
        require(isinstance(key, str) and ':' in key and key.split(':', 1)[0] in NAMESPACES
                and token(key.split(':', 1)[1]), 'Exact CPS/CIT workspace allowlist required')
        closed(value, {'profile'}, 'Closed workspace profile required')
        require(token(value['profile']), 'Explicit workspace profile required')
    require(not config['enabled'] or bool(config['workspaces']), 'Enabled pool requires an allowlist')
    return config


def read_config(path, *, trusted_uid=0):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == trusted_uid and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o400 and info.st_size <= 32768,
                'Owned immutable root0400 operator config required')
        raw = os.read(fd, 32769)
        require(len(raw) <= 32768, 'Oversized node config')
        return validate_config(parse(raw))
    finally: os.close(fd)


def load_source(name, raw, expected, filename):
    require(hashlib.sha256(raw).hexdigest() == expected, 'Pinned source mismatch: ' + filename)
    spec = importlib.util.spec_from_loader(name, loader=None, origin=filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(raw, filename, 'exec'), module.__dict__)
    return module


def snapshot_sources():
    snapshot = parse((HERE / 'source-snapshot.json').read_bytes())
    closed(snapshot, {'version', 'sources'}, 'Closed source snapshot required')
    require(snapshot['version'] == 1, 'Source snapshot version mismatch')
    closed(snapshot['sources'], SOURCE_PINS, 'Exact source bundle required')
    for name, digest in SOURCE_PINS.items():
        require(isinstance(snapshot['sources'][name], str)
                and hashlib.sha256(snapshot['sources'][name].encode()).hexdigest() == digest,
                'Snapshot source hash mismatch: ' + name)
    return snapshot['sources']


def load_models_from_snapshot():
    sources = snapshot_sources()
    name = 'native_gpu_controller.py'
    return load_source('_native_group_test_models', sources[name].encode(), SOURCE_PINS[name], name)


def load_bundle(directory):
    directory = Path(directory)
    # All imported code executes from the exact bytes that passed source pins.
    backend = load_source('node_backend', (directory / 'node_backend.py').read_bytes(),
                          SOURCE_PINS['node_backend.py'], 'node_backend.py')
    poll = load_source('_native_group_poll', (directory / 'poll.py').read_bytes(),
                       SOURCE_PINS['poll.py'], 'poll.py')
    modules = {}
    for key, name in [('models', 'native_gpu_controller.py'), ('manual', 'pod_cap.py'), ('health', 'native_gpu_health.py')]:
        modules[key] = load_source('_native_group_' + key, (directory / name).read_bytes(), SOURCE_PINS[name], name)
    return backend, poll, modules


def validate_enrollment(cm, config, models):
    validate_config(config)
    require(isinstance(cm, dict) and cm.get('apiVersion') == 'v1' and cm.get('kind') == 'ConfigMap'
            and cm.get('immutable') is True and not cm.get('binaryData'), 'Immutable enrollment ConfigMap required')
    meta = cm.get('metadata', {})
    require(isinstance(meta, dict) and meta.get('namespace') == config['authority_namespace']
            and canonical_uuid(meta.get('uid')) and not meta.get('deletionTimestamp'),
            'Live enrollment from exact authority namespace required')
    closed(cm.get('data'), {'enrollment.json'}, 'Single enrollment record required')
    enrollment = parse(cm['data']['enrollment.json'])
    keys = {'version', 'binding_id', 'source', 'actor', 'workspace', 'principal', 'members', 'attempt',
            'profile', 'policy_hash', 'namespace', 'name', 'node', 'node_uid', 'gpu_uuid', 'cap_mib', 'intent'}
    closed(enrollment, keys, 'Closed trusted enrollment schema required')
    binding = enrollment['binding_id']
    require(type(enrollment['version']) is int and enrollment['version'] == 1
            and isinstance(binding, str) and re.fullmatch(r'[a-f0-9]{60}', binding),
            'Exact versioned binding identity required')
    require(meta.get('name') == 'cps-native-enrollment-' + binding[:40]
            and isinstance(meta.get('labels'), dict) and meta['labels'].get(LABEL) == binding,
            'Exact immutable binding ConfigMap identity required')
    source, workspace = enrollment['source'], enrollment['workspace']
    require(source in NAMESPACES and token(workspace) and token(enrollment['actor'])
            and enrollment['principal'] == 'workspace:' + source + ':' + workspace
            and enrollment['namespace'] == NAMESPACES[source], 'Trusted source/workspace principal required')
    members = enrollment['members']
    require(isinstance(members, list) and 1 <= len(members) <= 64 and all(token(v) for v in members)
            and members == sorted(set(members)), 'Canonical sorted group members required')
    require(token(enrollment['attempt']), 'Immutable start attempt required')
    approved = config['workspaces'].get(source + ':' + workspace)
    require(approved is not None and enrollment['profile'] == approved['profile']
            and enrollment['policy_hash'] == config['policy_hash'], 'Reviewed workspace/profile/policy required')
    pool = config['pool']
    require(all(enrollment[key] == pool[key] for key in ('node', 'node_uid', 'gpu_uuid'))
            and type(enrollment['cap_mib']) is int and enrollment['cap_mib'] == 5120,
            'Exact selected GPU2 pool and native5GiB cap required')
    closed(enrollment['intent'], {field.name for field in fields(models.CapIntent)}, 'Exact frozen cap intent required')
    intent = models.CapIntent(**enrollment['intent'])
    require(all(getattr(intent, key) == enrollment[key] for key in
                ('namespace', 'name', 'node', 'node_uid', 'gpu_uuid', 'cap_mib', 'policy_hash')),
            'Enrollment and frozen cap intent disagree')
    return {'configmap_uid': meta['uid'], 'configmap_name': meta['name'],
            'authority_namespace': meta['namespace'], 'enrollment': enrollment}


class EnrollmentStore:
    """Root0700/root0600 enrollment tombstones, independent of the gate mount."""
    def __init__(self, state, models, trusted_uid=0):
        self.state, self.models, self.uid = Path(state), models, trusted_uid
        # Importing the pinned adapter avoids inventing a second private-file protocol.
        source = snapshot_sources()['node_backend.py']
        self.backend = load_source('_native_store_backend', source.encode(), SOURCE_PINS['node_backend.py'], 'node_backend.py')
        self.backend.private_directory(self.state, self.uid)
        for name in ('intents', 'enrollments', 'authority', 'receipts', 'bootstrap', 'published-cleanup', 'pre-gate-aborts'):
            path = self.state / name
            path.mkdir(mode=0o700, exist_ok=True)
            self.backend.private_directory(path, self.uid)

    def synchronize(self, records):
        by_uid = {}
        bindings = set()
        for value in records:
            uid = value['enrollment']['intent']['pod_uid']
            binding = value['enrollment']['binding_id']
            require(uid not in by_uid and binding not in bindings, 'Replayed Pod UID or binding enrollment refused')
            by_uid[uid] = value; bindings.add(binding)
        old = {}
        for path in sorted((self.state / 'enrollments').glob('*.json')):
            value = self.backend.private_read(path, self.uid)
            require(value['enrollment']['intent']['pod_uid'] == path.stem, 'Enrollment mirror filename mismatch')
            old[path.stem] = value
        require(set(old).issubset(by_uid), 'Missing immutable source enrollment blocks node authority')
        require(all(by_uid[uid] == value for uid, value in old.items()), 'Changed/replaced immutable enrollment refused')
        for path in sorted((self.state / 'intents').glob('*.json')):
            require(path.stem in old and self.backend.private_read(path, self.uid) == old[path.stem]['enrollment']['intent'],
                    'Unenrolled or changed root intent blocks authority')
        for uid, value in by_uid.items():
            envelope = self.state / 'enrollments' / (uid + '.json')
            if uid not in old:
                self.backend.private_write(envelope, value, self.uid, create=True)
            intent_path = self.state / 'intents' / (uid + '.json')
            previous = self.backend.private_read(intent_path, self.uid)
            require(previous is None or previous == value['enrollment']['intent'], 'Root intent changed')
            if previous is None:
                self.backend.private_write(intent_path, value['enrollment']['intent'], self.uid, create=True)
        return by_uid


    def mark_cleanup_published(self, uid, envelope, cm, record=None):
        expected = cleanup_object(envelope, record)
        validate_cleanup(cm, expected)
        value = {'enrollment_uid': envelope['configmap_uid'], 'receipt_uid': cm['metadata']['uid'],
                 'receipt': parse(expected['data']['receipt.json'])}
        path = self.state / 'published-cleanup' / (uid + '.json')
        previous = self.backend.private_read(path, self.uid)
        require(previous is None or previous == value, 'Published cleanup tombstone changed')
        if previous is None: self.backend.private_write(path, value, self.uid, create=True)

    def cleanup_published(self, uid, envelope, record, cm):
        value = self.backend.private_read(self.state / 'published-cleanup' / (uid + '.json'), self.uid)
        if value is None: return False
        require(record is not None and record.state in ('cleaned', 'retired-inert-cap')
                and record.intent.to_dict() == envelope['enrollment']['intent'],
                'Published cleanup requires its original cleaned native journal')
        expected = cleanup_object(envelope, record)
        validate_cleanup(cm, expected)
        require(value == {'enrollment_uid': envelope['configmap_uid'], 'receipt_uid': cm['metadata']['uid'],
                 'receipt': parse(expected['data']['receipt.json'])}, 'Missing/replaced cleanup tombstone blocks authority')
        return True

    def mark_abort(self, uid, envelope, proof):
        require(proof['enrollment_uid'] == envelope['configmap_uid']
                and proof['payload']['intent'] == envelope['enrollment']['intent']
                and proof['payload']['intent']['pod_uid'] == uid,
                'Exact operator abort enrollment required')
        path = self.state / 'pre-gate-aborts' / (uid + '.json')
        previous = self.backend.private_read(path, self.uid)
        require(previous is None or previous == proof, 'Operator abort tombstone changed')
        if previous is None: self.backend.private_write(path, proof, self.uid, create=True)

    def abort_published(self, uid, envelope, proof):
        previous = self.abort_record(uid)
        if previous is None: return False
        require(proof is not None and previous == proof
                and proof['enrollment_uid'] == envelope['configmap_uid']
                and proof['payload']['intent'] == envelope['enrollment']['intent']
                and proof['payload']['intent']['pod_uid'] == uid,
                'Missing/replaced operator abort authority blocks node')
        return True

    def abort_record(self, uid):
        value = self.backend.private_read(self.state / 'pre-gate-aborts' / (uid + '.json'), self.uid)
        if value is not None:
            closed(value, {'enrollment_uid', 'abort_uid', 'abort_sha256', 'ledger_uid', 'payload'},
                   'Exact protected operator abort completion required')
        return value


def abort_ledger(cm, namespace):
    require(isinstance(cm, dict) and cm.get('apiVersion') == 'v1' and cm.get('kind') == 'ConfigMap'
            and not cm.get('binaryData'), 'Actual native allocation ledger ConfigMap required')
    meta = cm.get('metadata', {})
    require(isinstance(meta, dict) and meta.get('namespace') == namespace
            and meta.get('name') == 'cps-native-gpu-allocations' and canonical_uuid(meta.get('uid'))
            and token(meta.get('resourceVersion')) and not meta.get('deletionTimestamp'),
            'Live exact allocation ledger identity required')
    closed(cm.get('data'), {'state.json'}, 'Single native allocation ledger required')
    state = parse(cm['data']['state.json'])
    closed(state, {'version', 'allocations'}, 'Closed native allocation ledger required')
    require(type(state['version']) is int and state['version'] == 1
            and isinstance(state['allocations'], dict), 'Versioned native allocation ledger required')
    return state


def validate_abort(cm, envelope, ledger_cm, current_epoch, models):
    enrollment = envelope['enrollment']; binding = enrollment['binding_id']
    require(isinstance(cm, dict) and cm.get('apiVersion') == 'v1' and cm.get('kind') == 'ConfigMap'
            and cm.get('immutable') is True and not cm.get('binaryData'), 'Immutable root operator abort required')
    meta = cm.get('metadata', {})
    require(isinstance(meta, dict) and meta.get('namespace') == envelope['authority_namespace']
            and meta.get('name') == 'cps-native-abort-' + binding[:40]
            and meta.get('labels') == {LABEL: binding} and canonical_uuid(meta.get('uid'))
            and not meta.get('deletionTimestamp') and not meta.get('ownerReferences'),
            'Exact live root operator abort ConfigMap identity required')
    closed(cm.get('data'), {'abort.json'}, 'Single distinct operator abort record required')
    payload = parse(cm['data']['abort.json'])
    closed(payload, {'version', 'outcome', 'binding_id', 'attempt', 'intent', 'enrollment_sha256',
                     'audit_sha256', 'node_epoch'}, 'Closed pre-gate abort protocol required')
    require(cm['data']['abort.json'] == canonical_json(payload), 'Canonical operator abort payload required')
    require(type(payload['version']) is int and payload['version'] == 1
            and payload['outcome'] == 'pre-gate-aborted' and payload['binding_id'] == binding
            and payload['attempt'] == enrollment['attempt'] and payload['intent'] == enrollment['intent']
            and payload['enrollment_sha256'] == canonical_sha256(enrollment)
            and isinstance(payload['audit_sha256'], str)
            and re.fullmatch(r'sha256:[a-f0-9]{64}', payload['audit_sha256']),
            'Exact audited enrollment/attempt/intent abort required')
    closed(payload['node_epoch'], {'node_uid', 'boot_id', 'driver_generation', 'gpu_uuid'},
           'Closed operator abort node epoch required')
    require(type(current_epoch) is models.DriverEpoch
            and models.DriverEpoch(**payload['node_epoch']) == current_epoch
            and current_epoch.node_uid == enrollment['node_uid']
            and current_epoch.gpu_uuid == enrollment['gpu_uuid'], 'Unchanged healthy typed abort epoch required')
    state = abort_ledger(ledger_cm, envelope['authority_namespace'])
    record = state['allocations'].get(binding)
    require(isinstance(record, dict) and record.get('state') == 'released'
            and all(record.get(key) == value for key, value in enrollment.items()),
            'Exact released allocation required for operator abort')
    proof = record.get('pre_gate_abort')
    closed(proof, {'configmap', 'configmap_uid', 'sha256'}, 'Exact released operator abort proof required')
    digest = canonical_sha256(payload)
    require(proof == {'configmap': meta['name'], 'configmap_uid': meta['uid'], 'sha256': digest},
            'Released allocation and immutable operator abort proof disagree')
    return {'enrollment_uid': envelope['configmap_uid'], 'abort_uid': meta['uid'],
            'abort_sha256': digest, 'ledger_uid': ledger_cm['metadata']['uid'], 'payload': payload}


def recognize_aborts(store, journal, accepted, kube, current_epoch, models, *, epoch_reader=None):
    if not accepted: return set()
    namespace = next(iter(accepted.values()))['authority_namespace']
    ledger_cm = kube.configmap(namespace, 'cps-native-gpu-allocations')
    ledger = abort_ledger(ledger_cm, namespace) if ledger_cm is not None else {'allocations': {}}
    aborted = set()
    for uid, envelope in accepted.items():
        binding = envelope['enrollment']['binding_id']
        cm = kube.configmap(namespace, 'cps-native-abort-' + binding[:40])
        if cm is None:
            record = ledger['allocations'].get(binding)
            require(not isinstance(record, dict) or 'pre_gate_abort' not in record,
                    'Orphan released operator abort proof blocks node')
            store.abort_published(uid, envelope, None)
            continue
        require(journal.read(uid) is None, 'A native journal can never be treated as never-gated')
        completed = store.abort_record(uid)
        if completed is not None:
            # Completion is durable across driver maintenance. Revalidate the
            # original immutable authority and released ledger against the
            # protected proof, without observing a replacement Pod or treating
            # a new healthy driver as evidence for an old abort.
            closed(completed['payload']['node_epoch'], {'node_uid', 'boot_id', 'driver_generation', 'gpu_uuid'},
                   'Original completed operator abort epoch required')
            original_epoch = models.DriverEpoch(**completed['payload']['node_epoch'])
            if current_epoch is not None:
                require(type(current_epoch) is models.DriverEpoch
                        and current_epoch.node_uid == envelope['enrollment']['node_uid']
                        and current_epoch.gpu_uuid == envelope['enrollment']['gpu_uuid'],
                        'Current selected node/GPU identity changed')
            proof = validate_abort(cm, envelope, ledger_cm, original_epoch, models)
            require(store.abort_published(uid, envelope, proof), 'Original protected abort completion required')
            require(journal.read(uid) is None, 'Completed abort acquired a native journal; retain allocation')
            aborted.add(uid)
            continue
        if current_epoch is None:
            require(callable(epoch_reader), 'Fresh healthy operator abort epoch reader required')
            current_epoch = epoch_reader()
        proof = validate_abort(cm, envelope, ledger_cm, current_epoch, models)
        if not store.abort_published(uid, envelope, proof):
            intent = models.CapIntent(**envelope['enrollment']['intent'])
            require(kube.pod(intent) is None, 'Exact Pod absence required before accepting operator abort')
            require(epoch_reader is None or epoch_reader() == current_epoch,
                    'Native epoch changed during operator abort recognition')
            store.mark_abort(uid, envelope, proof)
        else:
            require(epoch_reader is None or epoch_reader() == current_epoch,
                    'Native epoch changed during operator abort recognition')
        aborted.add(uid)
    return aborted


def abort_current_epoch(config, state, driver, verifier, models):
    require(driver.version == '615.71.09', 'Exact native driver required for operator abort recognition')
    generation = verifier.validate_native_driver_health(authority_directory=str(state / 'authority'))
    boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    return models.DriverEpoch(config['pool']['node_uid'], boot_id, generation, config['pool']['gpu_uuid'])


def validate_actual_pod(pod, enrollment):
    intent = enrollment['intent']
    meta, spec = pod.get('metadata', {}), pod.get('spec', {})
    require(all(meta.get(k) == intent[k] for k in ('namespace', 'name')) and meta.get('uid') == intent['pod_uid']
            and spec.get('nodeName') == intent['node'], 'Exact live enrolled Pod identity required')
    require(hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            == intent['spec_sha256'], 'Actual final admitted Pod specification changed')
    init, containers = spec.get('initContainers'), spec.get('containers')
    require(isinstance(init, list) and init and init[0].get('name') == 'cps-native-cap-gate'
            and isinstance(containers, list) and containers and not spec.get('ephemeralContainers'),
            'CPU first gate and no ephemeral workload required')
    require(all(isinstance(c, dict) and isinstance(c.get('image'), str) and _IMAGE.fullmatch(c['image'])
                for c in init + containers), 'All final images must use immutable SHA256 digests')


def cleanup_receipt(envelope, record, backend, pod, models):
    enrollment = envelope['enrollment']
    intent = models.CapIntent(**enrollment['intent'])
    require(type(record) is models.CapRecord and record.state in ('cleaned', 'retired-inert-cap') and record.intent == intent
            and pod is None, 'Actual Pod absence and exact cleaned native journal required')
    stopped = backend.check_cleanup(record.identity)
    require(type(stopped) is models.CleanupObservation and stopped.pod_uid is None
            and stopped.live_tasks is False and stopped.healthy is True
            and stopped.epoch == record.identity.epoch, 'Fresh exact healthy Pod absence/zero original tasks required')
    require(backend.read_gate(record.identity) is None, 'Native user gate receipt must remain revoked')
    if record.state == 'retired-inert-cap':
        require(stopped.cgroup_exists is False, 'Retired original cgroup must remain absent')
        proof = backend.retired_inert_cap(record.identity, record.limit)
        require(type(proof) is models.RetiredInertCap and proof.identity == record.identity
                and proof.entry == record.retirement.entry and proof.gpu_id == record.retirement.gpu_id,
                'Fresh original retained inert cap inventory required')
    else:
        require(stopped.cgroup_exists is True and stopped.gpu_clients is False,
                'Cleared cap requires actual cgroup and zero GPU clients')
        value = backend._raw(record.identity)
        require(value is None or (isinstance(value, dict) and set(value) == {'soft', 'hard', 'used'}
                and value == {'soft': 0, 'hard': models.MAX_LIMIT, 'used': 0}),
                'Positive cleared/unlimited native cap readback required for release')
    return cleanup_object(envelope, record)


def cleanup_object(envelope, record=None):
    enrollment = envelope['enrollment']
    binding = enrollment['binding_id']
    receipt = {'version': 1, 'binding_id': binding, 'attempt': enrollment['attempt'],
               'intent': enrollment['intent'], 'cleanup_confirmed': True}
    if record is not None and record.state == 'retired-inert-cap':
        require(record.intent.to_dict() == enrollment['intent'] and record.retirement is not None,
                'Exact typed retired native journal required')
        receipt['retirement'] = {'proof': record.retirement.to_dict(),
            'enrollment_uid': envelope['configmap_uid'], 'enrollment_sha256': canonical_sha256(enrollment),
            'journal_sha256': canonical_sha256(record.to_dict())}
    return {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,
            'metadata': {'name': 'cps-native-cleanup-' + binding[:40],
                         'namespace': envelope['authority_namespace'], 'labels': {LABEL: binding}},
            'data': {'receipt.json': json.dumps(receipt, sort_keys=True, separators=(',', ':'))}}


class Conflict(ValueError): pass


def validate_cleanup(created, expected):
    require(isinstance(created, dict) and all(created.get(k) == expected[k] for k in
                ('apiVersion', 'kind', 'immutable', 'data')) and not created.get('binaryData')
            and not created.get('metadata', {}).get('deletionTimestamp')
            and canonical_uuid(created.get('metadata', {}).get('uid'))
            and all(created.get('metadata', {}).get(k) == expected['metadata'][k] for k in
                ('name', 'namespace', 'labels')), 'Conflicting/untrusted cleanup receipt retained; release refused')


def publish_cleanup(kube, expected):
    namespace, name = expected['metadata']['namespace'], expected['metadata']['name']
    try:
        created = kube.create_configmap(namespace, expected)
    except Conflict:
        created = kube.configmap(namespace, name)
    validate_cleanup(created, expected)
    return created


def api_class(qualification):
    class AuthorityAPI(qualification.Kubernetes):
        def call(self, method, path, value=None):
            raw = json.dumps(value).encode() if value is not None else None
            request = urllib.request.Request(self.base + path, data=raw, method=method,
                headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
            try:
                with self.opener.open(request, timeout=5) as response:
                    return parse(response.read(1048577))
            except urllib.error.HTTPError as error:
                if error.code == 404 and method == 'GET': return None
                if error.code == 409 and method == 'POST': raise Conflict('Immutable receipt already exists') from None
                raise ValueError('Authority API failed with HTTP ' + str(error.code)) from None

        @staticmethod
        def maps_path(namespace):
            return '/api/v1/namespaces/' + urllib.parse.quote(namespace, safe='') + '/configmaps'

        def enrollments(self, namespace):
            # Select authority records server-side; source/code ConfigMaps can be
            # larger than the response bound and are not enrollment inputs.
            selected = self.maps_path(namespace) + '?limit=200&labelSelector=' + urllib.parse.quote('cps.compute/native-binding', safe='')
            path = selected
            values = []
            for page in range(10):
                response = self.call('GET', path)
                require(isinstance(response, dict) and response.get('apiVersion') == 'v1'
                        and response.get('kind') == 'ConfigMapList'
                        and isinstance(response.get('metadata'), dict)
                        and isinstance(response.get('items'), list), 'Actual bounded enrollment ConfigMapList required')
                for cm in response['items']:
                    require(isinstance(cm, dict) and cm.get('apiVersion', 'v1') == 'v1'
                            and cm.get('kind', 'ConfigMap') == 'ConfigMap'
                            and isinstance(cm.get('metadata'), dict)
                            and cm['metadata'].get('namespace') == namespace,
                            'Exact namespaced ConfigMap list item required')
                    name = cm['metadata'].get('name')
                    require(isinstance(name, str) and _NAME.fullmatch(name), 'Actual ConfigMap list item name required')
                    if name.startswith('cps-native-enrollment-'):
                        # Core/v1 LIST items omit TypeMeta. Infer only absent
                        # fields from the validated typed endpoint/envelope;
                        # explicit conflicting types above remain rejected.
                        value = dict(cm)
                        value.setdefault('apiVersion', 'v1')
                        value.setdefault('kind', 'ConfigMap')
                        values.append(value)
                more = response['metadata'].get('continue')
                require(more is None or isinstance(more, str), 'Invalid enrollment continuation')
                if not more: return values
                path = selected + '&continue=' + urllib.parse.quote(more, safe='')
            raise ValueError('Enrollment namespace exceeded bounded list')

        def configmap(self, namespace, name):
            return self.call('GET', self.maps_path(namespace) + '/' + urllib.parse.quote(name, safe=''))

        def create_configmap(self, namespace, value):
            return self.call('POST', self.maps_path(namespace), value)
    return AuthorityAPI


def run(config, bundle, state, kube, driver, *, iterations, interval, crictl, cri_socket):
    adapter, qualification, modules = bundle
    models, manual, verifier = modules['models'], modules['manual'], modules['health']
    store = EnrollmentStore(state, models)
    journal = models.PrivateJournal(state / 'journal')
    failures = []
    for iteration in range(iterations):
        node = kube.node(config['pool']['node'])
        require(node is not None and node['metadata']['name'] == config['pool']['node']
                and node['metadata']['uid'] == config['pool']['node_uid'], 'Actual selected node UID changed')
        envelopes = [validate_enrollment(cm, config, models) for cm in kube.enrollments(config['authority_namespace'])]
        accepted = store.synchronize(envelopes)
        intents = [models.CapIntent(**item['enrollment']['intent']) for item in accepted.values()]
        with journal.locked():
            records = journal.records()
            require(all(record.intent.pod_uid in accepted and record.intent.to_dict() ==
                        accepted[record.intent.pod_uid]['enrollment']['intent'] for record in records),
                    'Original immutable enrollment required for every native journal')
            aborted = recognize_aborts(store, journal, accepted, kube, None, models,
                epoch_reader=lambda: abort_current_epoch(config, state, driver, verifier, models))
            active = sum(journal.read(intent.pod_uid) is None or journal.read(intent.pod_uid).state not in ('cleaned', 'retired-inert-cap')
                         for intent in intents if intent.pod_uid not in aborted)
            require(active <= config['pool']['max_workspaces'], 'Selected pool active enrollment capacity exceeded')
        backend = adapter.QualificationNodeBackend(models, manual, intents=intents, driver=driver,
            get_pod=kube.pod, get_node=kube.node, get_cri=qualification.cri_reader(crictl, cri_socket),
            delete_pod=kube.delete, gpu_clients=qualification.gpu_clients,
            health=lambda: qualification.health(driver, verifier, authority_directory=str(state / 'authority')),
            state_root=state)
        controller = models.NativeCapController(backend, journal, enabled=True)
        for intent in intents:
            try:
                if intent.pod_uid in aborted:
                    print(json.dumps({'pod_uid': intent.pod_uid, 'state': 'pre-gate-aborted',
                        'iteration': iteration, 'production_qualified': False}), flush=True)
                    continue
                record = journal.read(intent.pod_uid)
                pod = kube.pod(intent)
                old_cleanup = kube.configmap(config['authority_namespace'], 'cps-native-cleanup-' +
                    accepted[intent.pod_uid]['enrollment']['binding_id'][:40])
                if store.cleanup_published(intent.pod_uid, accepted[intent.pod_uid], record, old_cleanup):
                    # Durable tombstones do not reconsider a replacement Pod or
                    # require an already-cleared old UID to stop a new peer.
                    print(json.dumps({'pod_uid': intent.pod_uid, 'state': 'cleanup-confirmed',
                        'iteration': iteration, 'production_qualified': False}), flush=True)
                    continue
                if pod is not None: validate_actual_pod(pod, accepted[intent.pod_uid]['enrollment'])
                if record is not None and record.state in ('cleaned', 'retired-inert-cap'):
                    record = controller.cleanup(intent)  # legacy vanished records also need fresh inventory
                    receipt = cleanup_receipt(accepted[intent.pod_uid], record, backend, pod, models)
                    published = publish_cleanup(kube, receipt)
                    store.mark_cleanup_published(intent.pod_uid, accepted[intent.pod_uid], published, record)
                    result = 'cleanup-confirmed'
                elif record is None and pod is None:
                    result = 'blocked-absent-without-native-journal'  # No invented stop evidence.
                elif record is None and qualification.awaiting_first_gate(pod, intent):
                    result = 'awaiting-gate'
                elif pod is None or pod.get('status', {}).get('phase') in ('Succeeded', 'Failed'):
                    require(record is not None, 'Terminal Pod has no native cap transaction')
                    stopped = backend.check_cleanup(record.identity)
                    if stopped.live_tasks or (stopped.cgroup_exists and stopped.gpu_clients):
                        result = 'retained-awaiting-stop'
                    else:
                        record = controller.cleanup(intent)
                        # A terminal Pod still present cannot release the allocation.
                        fresh_pod = kube.pod(intent)
                        if fresh_pod is None:
                            published = publish_cleanup(kube, cleanup_receipt(accepted[intent.pod_uid], record, backend, fresh_pod, models))
                            store.mark_cleanup_published(intent.pod_uid, accepted[intent.pod_uid], published, record)
                            result = 'cleanup-confirmed'
                        else: result = 'cleaned-awaiting-pod-absence'
                else:
                    record = controller.reconcile(intent)
                    result = record.state
                print(json.dumps({'pod_uid': intent.pod_uid, 'state': result, 'iteration': iteration,
                    'production_qualified': False}), flush=True)
            except Exception as error:
                failures.append(type(error).__name__)
                print(json.dumps({'pod_uid': intent.pod_uid, 'state': 'blocked-error', 'error': type(error).__name__,
                    'detail': str(error), 'iteration': iteration, 'production_qualified': False}), flush=True)
        if iteration + 1 < iterations: time.sleep(interval)
    require(not failures, 'Node agent observed blocked errors; allocations and protection retained')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--bundle', type=Path, default=HERE)
    parser.add_argument('--state-root', type=Path, default=Path('/run/cps-native-gpu'))
    parser.add_argument('--service-account', type=Path, default=Path('/var/run/secrets/kubernetes.io/serviceaccount'))
    parser.add_argument('--crictl', type=Path, default=Path('/host/var/lib/rancher/k3s/data/current/bin/crictl'))
    parser.add_argument('--cri-socket', default='unix:///host/run/k3s/containerd/containerd.sock')
    parser.add_argument('--iterations', type=int, default=60)
    parser.add_argument('--interval', type=float, default=2)
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({'state': 'inert', 'api_calls': False, 'gpu_calls': False, 'production_qualified': False}))
        return
    require(os.geteuid() == 0 and args.config is not None, 'Explicit root execution/configuration required')
    config = read_config(args.config)
    require(config['enabled'], 'Node authority deployment is disabled')
    require(1 <= args.iterations <= 10000 and 0.1 <= args.interval <= 30, 'Bounded node iteration window required')
    bundle = load_bundle(args.bundle)
    adapter, qualification, modules = bundle
    state = adapter.private_directory(args.state_root)
    lock = os.open(state / '.node-agent.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    driver = None
    try:
        info = os.fstat(lock)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o600
                and info.st_nlink == 1, 'Owned private node writer lock required')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        kube = api_class(qualification)(args.service_account)
        driver = modules['manual'].Nvml()
        run(config, bundle, state, kube, driver, iterations=args.iterations, interval=args.interval,
            crictl=args.crictl, cri_socket=args.cri_socket)
    finally:
        if driver is not None: driver.close()
        os.close(lock)


if __name__ == '__main__': main()
