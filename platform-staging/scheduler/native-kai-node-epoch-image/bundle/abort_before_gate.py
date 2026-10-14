#!/usr/bin/env python3
"""Explicit root-reviewed qualification recovery. Default execution is inert.

This is a distinct terminal *never-gated* proof, not native cap cleanup. A root
RPC must keep the protected journal writer lock held for the entire transaction.
No SQL, device, cap, enrollment deletion, or general release API exists here.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import tempfile
import uuid

NAMESPACE = 'cps-native-system'
LEDGER = 'cps-native-gpu-allocations'
NODE = 'k3s-wk-gpu2'
NODE_UID = '3336cdd5-d245-436e-b57c-2f66c6dcaa41'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
LABEL = 'cps.compute/native-binding'
ENROLLMENT_KEYS = frozenset(('version', 'binding_id', 'source', 'actor', 'workspace',
    'principal', 'members', 'attempt', 'profile', 'policy_hash', 'namespace', 'name',
    'node', 'node_uid', 'gpu_uuid', 'cap_mib', 'intent'))
INTENT_KEYS = frozenset(('namespace', 'name', 'pod_uid', 'node', 'node_uid',
    'spec_sha256', 'gpu_uuid', 'cap_mib', 'policy_hash'))
BOOL_PROOF = ('journal_protected', 'journal_empty', 'gate_receipts_absent',
    'native_writers_quiesced', 'exclusive_lock', 'driver_healthy')
ZERO_PROOF = ('global_gpu_memory_mib', 'global_gpu_clients', 'global_compute_apps', 'pod_runtime_tasks')

class AbortError(ValueError):
    """Evidence or an actual observation does not prove this bounded recovery."""

def require(value, message):
    if not value:
        raise AbortError(message)

def closed(value, keys, message):
    require(isinstance(value, dict) and set(value) == set(keys), message)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

def sha256(value):
    return 'sha256:' + hashlib.sha256(canonical(value).encode()).hexdigest()

def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result

def parse(raw):
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(AbortError('Non-finite JSON')))
    except (TypeError, json.JSONDecodeError) as exc:
        raise AbortError('Invalid JSON') from exc

def valid_uuid(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except (ValueError, TypeError):
        return False

def hash_value(value):
    return isinstance(value, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', value) is not None

def epoch(value):
    closed(value, ('node_uid', 'boot_id', 'driver_generation', 'gpu_uuid'), 'Unexpected node epoch')
    require(value['node_uid'] == NODE_UID and value['gpu_uuid'] == GPU, 'Unreviewed physical pool')
    require(valid_uuid(value['boot_id']) and valid_uuid(value['driver_generation']), 'Invalid driver epoch')

def validate_proof(value):
    closed(value, ('node_epoch', 'journal_device', 'journal_inode', *BOOL_PROOF, *ZERO_PROOF), 'Unexpected fence proof')
    epoch(value['node_epoch'])
    for key in BOOL_PROOF:
        require(value[key] is True, 'Unproven ' + key)
    for key in ZERO_PROOF:
        require(type(value[key]) is int and value[key] == 0, 'Nonzero or invalid ' + key)
    for key in ('journal_device', 'journal_inode'):
        require(type(value[key]) is int and value[key] > 0, 'Invalid protected journal identity')

def validate_evidence(value, expected):
    require(hash_value(expected) and sha256(value) == expected, 'Reviewed evidence hash mismatch')
    closed(value, ('version', 'qualification_only', 'authority_namespace', 'binding_id', 'attempt',
        'ledger_uid', 'allocation_sha256', 'enrollment_uid', 'enrollment_sha256',
        'fence_command_sha256', 'proof', 'review'), 'Unexpected evidence schema')
    require(type(value['version']) is int and value['version'] == 1 and value['qualification_only'] is True,
        'Not an explicit qualification recovery')
    require(value['authority_namespace'] == NAMESPACE, 'Wrong authority namespace')
    require(isinstance(value['binding_id'], str) and re.fullmatch('[0-9a-f]{60}', value['binding_id']), 'Invalid binding identity')
    require(isinstance(value['attempt'], str) and 0 < len(value['attempt']) <= 128, 'Invalid attempt')
    for key in ('ledger_uid', 'enrollment_uid'):
        require(valid_uuid(value[key]), 'Invalid immutable API identity')
    for key in ('allocation_sha256', 'enrollment_sha256', 'fence_command_sha256'):
        require(hash_value(value[key]), 'Invalid evidence hash')
    validate_proof(value['proof'])
    review = value['review']
    closed(review, ('operator', 'reason', 'gate_only_pod_sha256', 'controller_source_sha256',
        'node_agent_source_sha256', 'parser_failure_sha256', 'native_transaction_never_started'), 'Unexpected root review')
    require(review['operator'] == 'root' and review['reason'] == 'node-agent-failed-before-native-transaction'
        and review['native_transaction_never_started'] is True, 'Missing root never-gated review')
    for key in ('gate_only_pod_sha256', 'controller_source_sha256', 'node_agent_source_sha256', 'parser_failure_sha256'):
        require(hash_value(review[key]), 'Missing reviewed artifact hash')

def cm_metadata(cm, name):
    require(isinstance(cm, dict) and cm.get('apiVersion') == 'v1' and cm.get('kind') == 'ConfigMap', 'Not a ConfigMap')
    meta = cm.get('metadata', {})
    require(meta.get('namespace') == NAMESPACE and meta.get('name') == name and valid_uuid(meta.get('uid')), 'ConfigMap identity mismatch')
    require(not cm.get('binaryData') and not meta.get('ownerReferences') and not meta.get('deletionTimestamp'), 'Unreviewed/deleting ConfigMap ownership/data')
    return meta

def ledger_state(cm, evidence):
    meta = cm_metadata(cm, LEDGER)
    require(meta['uid'] == evidence['ledger_uid'] and isinstance(meta.get('resourceVersion'), str)
        and bool(meta['resourceVersion']), 'Ledger UID/resourceVersion mismatch')
    closed(cm.get('data'), ('state.json',), 'Unexpected ledger data')
    state = parse(cm['data']['state.json'])
    closed(state, ('version', 'allocations'), 'Unexpected ledger schema')
    require(type(state['version']) is int and state['version'] == 1 and isinstance(state['allocations'], dict), 'Invalid ledger version')
    record = state['allocations'].get(evidence['binding_id'])
    require(isinstance(record, dict) and ENROLLMENT_KEYS <= set(record), 'Missing audited allocation')
    immutable = {k:v for k,v in record.items() if k not in ('state', 'pre_gate_abort')}
    require(sha256(immutable) == evidence['allocation_sha256'] and record['binding_id'] == evidence['binding_id']
        and record['attempt'] == evidence['attempt'], 'Changed immutable allocation/attempt')
    require(record.get('state') in ('enrolled', 'releasing', 'released'), 'Allocation has no registered intent')
    enrollment = {key:record[key] for key in ENROLLMENT_KEYS}
    validate_enrollment(enrollment)
    return state, record, enrollment

def validate_enrollment(value):
    closed(value, ENROLLMENT_KEYS, 'Unexpected enrollment schema')
    require(type(value['version']) is int and value['version'] == 1, 'Invalid enrollment version')
    source = value['source']
    require((source, value['workspace']) in (('cps', 'native-group-a'), ('cps', 'native-group-b'), ('cit', 'native-group-a')),
        'Outside closed qualification workspaces')
    require(value['actor'] == source and value['principal'] == 'workspace:' + source + ':' + value['workspace'], 'Wrong source/principal')
    require(value['namespace'] == {'cps':'jupyterhub', 'cit':'cit-jhub'}[source], 'Wrong source namespace')
    require(isinstance(value['members'], list) and value['members'] and all(isinstance(m, str) and m for m in value['members'])
        and len(set(value['members'])) == len(value['members']), 'Invalid immutable members')
    require(value['node'] == NODE and value['node_uid'] == NODE_UID and value['gpu_uuid'] == GPU
        and type(value['cap_mib']) is int and value['cap_mib'] == 5120, 'Wrong qualification pool/cap')
    require(hash_value(value['policy_hash']) and isinstance(value['profile'], str) and value['profile'], 'Unpinned trusted profile/policy')
    intent = value['intent']
    closed(intent, INTENT_KEYS, 'Unexpected registered intent')
    require(valid_uuid(intent['pod_uid']) and isinstance(intent['spec_sha256'], str)
        and re.fullmatch('[0-9a-f]{64}', intent['spec_sha256']), 'Invalid immutable Pod/spec identity')
    for key in INTENT_KEYS - {'pod_uid', 'spec_sha256'}:
        require(intent[key] == value[key], 'Intent/binding mismatch')

def trusted_enrollment(cm, evidence, expected):
    meta = cm_metadata(cm, 'cps-native-enrollment-' + evidence['binding_id'][:40])
    require(meta['uid'] == evidence['enrollment_uid'] and cm.get('immutable') is True
        and meta.get('labels') == {LABEL:evidence['binding_id']}, 'Changed enrollment identity')
    closed(cm.get('data'), ('enrollment.json',), 'Unexpected enrollment data')
    enrollment = parse(cm['data']['enrollment.json'])
    require(cm['data']['enrollment.json'] == canonical(enrollment) and enrollment == expected
        and sha256(enrollment) == evidence['enrollment_sha256'], 'Changed immutable enrollment content')

def abort_payload(evidence, enrollment):
    return {'version':1, 'outcome':'pre-gate-aborted', 'binding_id':evidence['binding_id'],
        'attempt':evidence['attempt'], 'intent':copy.deepcopy(enrollment['intent']),
        'enrollment_sha256':evidence['enrollment_sha256'], 'audit_sha256':sha256(evidence),
        'node_epoch':copy.deepcopy(evidence['proof']['node_epoch'])}

def abort_body(evidence, enrollment):
    return {'apiVersion':'v1', 'kind':'ConfigMap', 'immutable':True,
        'metadata':{'namespace':NAMESPACE, 'name':'cps-native-abort-' + evidence['binding_id'][:40],
            'labels':{LABEL:evidence['binding_id']}}, 'data':{'abort.json':canonical(abort_payload(evidence, enrollment))}}

def trusted_abort(cm, body):
    meta = cm_metadata(cm, body['metadata']['name'])
    require(cm.get('immutable') is True and meta.get('labels') == body['metadata']['labels']
        and cm.get('data') == body['data'], 'Forged or changed abort ConfigMap')
    return {'configmap':meta['name'], 'configmap_uid':meta['uid'], 'sha256':sha256(parse(body['data']['abort.json']))}

def observe(backend, evidence):
    snapshot = backend.get_ledger()
    state, record, enrollment = ledger_state(snapshot, evidence)
    trusted_enrollment(backend.get_enrollment(evidence['binding_id']), evidence, enrollment)
    node = backend.get_node(enrollment['node'])
    require(isinstance(node, dict) and node.get('metadata', {}).get('name') == NODE
        and node['metadata'].get('uid') == NODE_UID, 'Changed actual Node UID')
    require(backend.get_pod(enrollment['namespace'], enrollment['name']) is None, 'Actual Pod still exists or name reused')
    return snapshot, state, record, enrollment

def verify_fence(fence, evidence):
    actual = fence.verify()
    validate_proof(actual)
    require(actual == evidence['proof'], 'Changed live writer fence/epoch/journal proof')

def execute_abort(backend, evidence, *, expected_evidence_sha256):
    validate_evidence(evidence, expected_evidence_sha256)
    with backend.fence(evidence) as fence:
        verify_fence(fence, evidence)
        _, _, _, enrollment = observe(backend, evidence)
        body = abort_body(evidence, enrollment)
        verify_fence(fence, evidence)
        observe(backend, evidence)
        existing = backend.get_abort(evidence['binding_id'])
        if existing is None:
            backend.create_abort(body)
            existing = backend.get_abort(evidence['binding_id'])
        proof = trusted_abort(existing, body)
        verify_fence(fence, evidence)
        snapshot, state, record, _ = observe(backend, evidence)
        verify_fence(fence, evidence)
        # An orphan immutable proof never frees capacity. Only the exact ledger
        # CAS with the API-created UID makes it terminal; retries verify both.
        if record['state'] == 'released':
            require(record.get('pre_gate_abort') == proof, 'Released ledger lacks exact abort identity')
        else:
            require('pre_gate_abort' not in record, 'Unexpected partial abort proof')
            saved = copy.deepcopy(state)
            saved['allocations'][evidence['binding_id']]['state'] = 'released'
            saved['allocations'][evidence['binding_id']]['pre_gate_abort'] = proof
            response = backend.compare_and_swap(snapshot, saved)
            actual_state, _, _ = ledger_state(response, evidence)
            require(actual_state == saved, 'Ledger CAS readback differs')
        return {'state':'released', 'binding_id':evidence['binding_id'], 'attempt':evidence['attempt'],
            'audit_sha256':expected_evidence_sha256, 'abort':proof}

class RootFence:
    """Pinned root RPC owns flock; never substitute a supplied JSON assertion."""
    def __init__(self, command, evidence, timeout=30):
        require(isinstance(command, list) and command and all(isinstance(x, str) and x for x in command), 'Invalid root fence argv')
        require(sha256(command) == evidence['fence_command_sha256'], 'Root fence command hash mismatch')
        self.command, self.evidence, self.timeout = command, evidence, timeout
        self.process = None
        self.buffer = b''
    def line(self, expected):
        deadline = datetime.now(timezone.utc).timestamp() + self.timeout
        while b'\n' not in self.buffer:
            remaining = deadline - datetime.now(timezone.utc).timestamp()
            require(remaining > 0 and self.process.poll() is None, 'Root fence exited or timed out')
            ready, _, _ = select.select([self.process.stdout], [], [], remaining)
            require(ready, 'Root fence response timed out')
            chunk = os.read(self.process.stdout.fileno(), 4096)
            require(chunk and len(self.buffer) + len(chunk) <= 65536, 'Root fence EOF/oversized response')
            self.buffer += chunk
        raw, self.buffer = self.buffer.split(b'\n', 1)
        value = parse(raw)
        closed(value, ('event', 'observed_at', 'proof'), 'Unexpected root fence response')
        require(value['event'] == expected, 'Unexpected root fence event')
        try:
            stamp = datetime.fromisoformat(value['observed_at'].replace('Z', '+00:00'))
            require(value['observed_at'].endswith('Z') and stamp.tzinfo is not None, 'Fence timestamp is not UTC')
            age = (datetime.now(timezone.utc) - stamp).total_seconds()
        except (TypeError, AttributeError, ValueError) as exc:
            raise AbortError('Invalid fence timestamp') from exc
        require(-5 <= age <= 30, 'Stale root fence response')
        validate_proof(value['proof'])
        require(value['proof'] == self.evidence['proof'], 'Root live proof differs from reviewed evidence')
        return value['proof']
    def __enter__(self):
        self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            self.line('fence-acquired')
        except BaseException:
            self.close()
            raise
        return self
    def ensure_alive(self):
        require(self.process is not None and self.process.poll() is None, 'Root fence not alive')
    def verify(self):
        self.ensure_alive()
        try:
            self.process.stdin.write(b'{"op":"verify"}\n'); self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise AbortError('Root fence lost') from exc
        return self.line('fence-verified')
    def close(self):
        if self.process is None:
            return
        try:
            if self.process.poll() is None:
                self.process.stdin.write(b'{"op":"release"}\n'); self.process.stdin.flush()
                self.process.wait(timeout=5)
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
            self.process.kill(); self.process.wait(timeout=5)
        finally:
            for stream in (self.process.stdin, self.process.stdout):
                stream.close()
    def __exit__(self, exc_type, *_):
        self.close()
        if exc_type is None:
            require(self.process.returncode == 0, 'Root fence release failed; retain receipt and review')

class KubernetesBackend:
    """Root kubectl transport. JSONPatch tests both actual UID and RV."""
    def __init__(self, fence_command, *, kubeconfig=None, context=None):
        self.command = ['kubectl']
        if kubeconfig: self.command += ['--kubeconfig', kubeconfig]
        if context: self.command += ['--context', context]
        self.fence_command = fence_command
        self.live_fence = None
    def fence(self, evidence):
        self.live_fence = RootFence(self.fence_command, evidence)
        return self.live_fence
    def call(self, args, *, body=None, absent=False):
        if self.live_fence is not None: self.live_fence.ensure_alive()
        try:
            result = subprocess.run(self.command + args, input=canonical(body) if body is not None else None,
                text=True, capture_output=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AbortError('Kubernetes transport unavailable') from exc
        if self.live_fence is not None: self.live_fence.ensure_alive()
        require(result.returncode == 0, 'Kubernetes operation denied/conflicted/unavailable')
        if absent and not result.stdout.strip(): return None
        value = parse(result.stdout)
        require(isinstance(value, dict), 'Kubernetes response is not an actual object')
        return value
    def get_cm(self, name, absent=False):
        args = ['get', 'configmap', name, '-n', NAMESPACE, '-o', 'json']
        if absent: args += ['--ignore-not-found']
        return self.call(args, absent=absent)
    def get_ledger(self): return self.get_cm(LEDGER)
    def get_enrollment(self, bid): return self.get_cm('cps-native-enrollment-' + bid[:40])
    def get_abort(self, bid): return self.get_cm('cps-native-abort-' + bid[:40], absent=True)
    def get_node(self, name): return self.call(['get', 'node', name, '-o', 'json'])
    def get_pod(self, namespace, name):
        return self.call(['get', 'pod', name, '-n', namespace, '-o', 'json', '--ignore-not-found'], absent=True)
    def create_abort(self, body): return self.call(['create', '-f', '-', '-o', 'json'], body=body)
    def compare_and_swap(self, snapshot, state):
        patch = [{'op':'test', 'path':'/metadata/uid', 'value':snapshot['metadata']['uid']},
            {'op':'test', 'path':'/metadata/resourceVersion', 'value':snapshot['metadata']['resourceVersion']},
            {'op':'replace', 'path':'/data/state.json', 'value':canonical(state)}]
        # The allocation includes private members: keep patch out of argv/logs.
        with tempfile.NamedTemporaryFile(mode='w', prefix='native-abort-cas-', encoding='utf8') as file:
            file.write(canonical(patch)); file.flush()
            return self.call(['patch', 'configmap', LEDGER, '-n', NAMESPACE, '--type=json',
                '--patch-file', file.name, '-o', 'json'])

def private_output(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as file:
        file.write(canonical(value) + '\n'); file.flush(); os.fsync(file.fileno())

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--execute', action='store_true')
    action.add_argument('--propose', action='store_true', help='Offline API objects only; no root fence or API calls')
    parser.add_argument('--qualification-only', action='store_true')
    for flag in ('evidence', 'evidence-sha256', 'fence-command-file', 'ledger', 'enrollment', 'output', 'kubeconfig', 'context'):
        parser.add_argument('--' + flag)
    args = parser.parse_args(argv)
    if not args.execute and not args.propose:
        print(canonical({'state':'inert', 'api_calls':False, 'device_calls':False})); return 0
    require(args.qualification_only and args.evidence and args.evidence_sha256 and args.output, 'Explicit qualification evidence/hash/output required')
    evidence = parse(Path(args.evidence).read_text())
    validate_evidence(evidence, args.evidence_sha256)
    require(not Path(args.output).exists(), 'Output already exists; preserve previous receipt')
    if args.propose:
        require(args.ledger and args.enrollment, 'Offline captured ledger and enrollment required')
        snapshot = parse(Path(args.ledger).read_text())
        _, _, enrollment = ledger_state(snapshot, evidence)
        trusted_enrollment(parse(Path(args.enrollment).read_text()), evidence, enrollment)
        proposal = {'version':1, 'state':'offline-proposal', 'audit_sha256':args.evidence_sha256,
            'abort_configmap':abort_body(evidence, enrollment), 'ledger_cas':{'name':LEDGER,
                'namespace':NAMESPACE, 'uid':snapshot['metadata']['uid'], 'resourceVersion':snapshot['metadata']['resourceVersion'],
                'binding_id':evidence['binding_id'], 'state':'released',
                'pre_gate_abort':{'configmap':'cps-native-abort-' + evidence['binding_id'][:40],
                    'configmap_uid':'<ACTUAL_ABORT_CONFIGMAP_UID_FROM_CREATE_READBACK>',
                    'sha256':sha256(abort_payload(evidence, enrollment))}},
            'requires':'Live pinned root writer fence, independent Node/enrollment/Pod checks, actual immutable abort readback, UID/RV CAS; this template cannot be applied'}
        private_output(args.output, proposal)
        print(canonical({'state':'offline-proposal', 'audit_sha256':args.evidence_sha256})); return 0
    require(args.fence_command_file, 'Pinned live root fence command required')
    command = parse(Path(args.fence_command_file).read_text())
    # Pin before creating any API transport or executing the root command.
    RootFence(command, evidence)
    backend = KubernetesBackend(command, kubeconfig=args.kubeconfig, context=args.context)
    result = execute_abort(backend, evidence, expected_evidence_sha256=args.evidence_sha256)
    private_output(args.output, result)
    print(canonical(result)); return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (AbortError, OSError) as exc:
        print(str(exc), file=sys.stderr); sys.exit(1)
