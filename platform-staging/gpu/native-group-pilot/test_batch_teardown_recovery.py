"""CPU-only two-plan recovery fixtures; fake hardware/API, real private files."""
import copy
from contextlib import ExitStack, redirect_stdout
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import fcntl
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import uuid

import batch_teardown_recovery as b
import teardown_recovery as r
from test_teardown_recovery import Fixture


class BatchFixture:
    def __init__(self, root):
        self.base = Fixture(root, state='sealed', gate=True)
        self.root, self.fds, self.calls = self.base.root, self.base.fds, []
        self.held, self.fail_local, self.local_count = False, False, 0
        old = r._models().CapRecord.from_dict(self.base.plan['journal']['record'])
        self.plans, self.before, self.after, self.items, self.cms = [], [], [], [], {}
        allocations = {}
        for i, uid in enumerate(b.UIDS):
            ns, name = b.TARGETS[uid]; source = 'cit' if ns == 'cit-jhub' else 'cps'
            binding = ('a' if source == 'cit' else 'b') * 60
            workspace = 'native-group-a' if source == 'cit' else 'native-group-b'
            intent = replace(old.intent, namespace=ns, name=name, pod_uid=uid)
            relative = '/kubepods.slice/kubepods-burstable-pod' + uid.replace('-', '_') + '.slice'
            identity = replace(old.identity, pod_uid=uid, driver_generation=b.GENERATION,
                cgroup_relative=relative, cgroup_path='/sys/fs/cgroup' + relative, cgroup_inode=71 + i)
            record = replace(old, intent=intent, identity=identity, seal_id=str(uuid.uuid4()))
            raw = (r.canonical(record.to_dict()) + '\n').encode()
            gate_raw = (r.canonical(record.receipt()) + '\n').encode()
            for kind, data in (('journal', raw), ('receipts', gate_raw)):
                path = self.root / kind / (uid + '.json'); path.write_bytes(data); path.chmod(0o600)
            enrollment = json.loads(self.base.enrollment['data']['enrollment.json'])
            enrollment.update(binding_id=binding, source=source, actor=source, workspace=workspace,
                principal='workspace:' + source + ':' + workspace, namespace=ns, name=name,
                attempt='attempt-' + uid, intent=intent.to_dict())
            allocations[binding] = {**enrollment, 'state': 'enrolled'}
            actual = copy.deepcopy(self.base.enrollment)
            actual['metadata'].update(name='cps-native-enrollment-' + binding[:40], uid=str(uuid.uuid4()), labels={r.LABEL: binding})
            actual['data']['enrollment.json'] = r.canonical(enrollment)
            self.cms[actual['metadata']['name']] = actual
            plan = copy.deepcopy(self.base.plan)
            plan.update(operation_id=str(uuid.uuid4()), binding_id=binding, attempt=enrollment['attempt'],
                enrollment_uid=actual['metadata']['uid'], allocation_sha256=r.sha256(enrollment), enrollment_sha256=r.sha256(enrollment),
                journal={'record': record.to_dict(), 'sha256': r.raw_sha256(raw)})
            plan['scope'].update(driver_generation=b.GENERATION,
                module_sha256={key: 'sha256:' + value for key, value in b.MODULES.items()})
            plan['review']['old_module_source_sha256'] = 'sha256:' + b.HEALTH_SHA
            self.plans.append(plan)
            before = copy.deepcopy(self.base.before)
            before.update(operation_id=plan['operation_id'], journal_sha256=plan['journal']['sha256'], gate_sha256=r.raw_sha256(gate_raw))
            self.before.append(before)
            after = copy.deepcopy(self.base.after)
            after.update(operation_id=plan['operation_id'], old_driver_generation=b.GENERATION,
                journal_sha256=plan['journal']['sha256'], gate_sha256=before['gate_sha256'])
            self.after.append(after)
        pods = sorted([{key: p['journal']['record']['intent'][key] for key in ('namespace', 'name', 'pod_uid')}
                       for p in self.plans], key=lambda value: (value['namespace'], value['name'], value['pod_uid']))
        for p, before, after in zip(self.plans, self.before, self.after):
            p['scope']['pilot_pods'] = pods
            before.update(scope=copy.deepcopy(p['scope']), plan_sha256=r.sha256(p)); after['plan_sha256'] = r.sha256(p)
        self.ledger = copy.deepcopy(self.base.ledger)
        self.ledger['data']['state.json'] = r.canonical({'version': 1, 'allocations': allocations})
        self.cms[r.LEDGER] = self.ledger
        self.node, self.pod = self.base.node, None

    def close(self): self.base.close()

    def get_node(self, name): self.calls.append('node-get'); return copy.deepcopy(self.node)
    def get_pod(self, namespace, name): self.calls.append(('pod-get', namespace, name)); return copy.deepcopy(self.pod)
    def get_cm(self, name, absent=False): self.calls.append(('cm-get', name)); return copy.deepcopy(self.cms.get(name))

    def create_cm(self, value):
        if not self.held: raise AssertionError('No mutation outside shared fence')
        actual = copy.deepcopy(value); actual['metadata']['uid'] = str(uuid.uuid4())
        self.cms[actual['metadata']['name']] = actual
        self.calls.append(('create', actual['metadata']['name']))
        return copy.deepcopy(actual)

    def batch_fence(self, plans, batch_id, digest):
        self.calls.append('acquire-batch'); return self
    def assert_release_frozen(self):
        self.calls.append('release-freeze-get'); return {'frozen': True}
    def __enter__(self): self.held = True; return self
    def __exit__(self, *args): self.calls.append('release-batch'); self.held = False

    def verify(self): self.calls.append('verify-batch'); return copy.deepcopy(self.after)

    def publish(self, items):
        self.calls.append('publish-batch'); self.items = copy.deepcopy(items)
        for i, (p, item) in enumerate(zip(self.plans, items)):
            self.local_count += 1
            if self.fail_local and i == 1: raise ValueError('second local publication failed')
            if not self.held: raise AssertionError('Shared fence lost')
            r.complete_local(self.root, p, item['audit'], item['cleanup'], before=self.before[i],
                teardown=self.after[i], lock_fds=self.fds, trusted_uid=os.getuid())
        return self.verify_completion()

    def verify_completion(self):
        self.calls.append('verify-completion')
        result = []
        for p, before, after, item in zip(self.plans, self.before, self.after, self.items):
            local = r.read_local_completion(self.root, p, item['audit'], item['cleanup'], trusted_uid=os.getuid())
            fresh = {**after, 'journal_sha256': local['journal_raw_sha256'], 'gate_sha256': None}
            result.append({'stage': 'complete', 'operation_id': p['operation_id'], 'plan_sha256': r.sha256(p),
                           'teardown': fresh, **local})
        return result


class BatchTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        fixture = BatchFixture(temporary.name); self.addCleanup(fixture.close); return fixture

    def execute(self, fixture):
        return b.execute_batch(fixture, fixture.plans, str(uuid.uuid4()), expected_sha256=b.sha(fixture.plans), r=r)

    def test_default_does_not_load_publisher_or_root_inputs_or_make_commands(self):
        from contextlib import redirect_stdout
        with patch.object(b, 'publisher', side_effect=AssertionError('import')), \
             patch.object(b, 'root_read', side_effect=AssertionError('Root read')), \
             patch.object(b.subprocess, 'run', side_effect=AssertionError('command')), \
             redirect_stdout(io.StringIO()) as output:
            b.main([])
        value = json.loads(output.getvalue())
        self.assertEqual(value['state'], 'inert'); self.assertFalse(value['api_calls']); self.assertFalse(value['device_calls'])

    def test_two_genuine_v1_plans_publish_matching_receipts_and_keep_ledger_held(self):
        f = self.fixture(); original_state = f.ledger['data']['state.json']
        result = self.execute(f)
        self.assertEqual(result['state'], 'batch-teardown-cleanup-published')
        self.assertFalse(result['allocation_released']); self.assertFalse(result['production_qualified'])
        self.assertEqual(f.ledger['data']['state.json'], original_state)
        self.assertEqual(f.calls[0], 'release-freeze-get')
        self.assertEqual(f.calls[-1], 'release-batch')
        self.assertEqual(f.calls.count('acquire-batch'), 1)
        self.assertEqual(f.calls.count('verify-batch'), 3)
        self.assertEqual(f.calls.count('verify-completion'), 3)
        for p in f.plans:
            uid = p['journal']['record']['intent']['pod_uid']
            self.assertEqual(json.loads((f.root / 'journal' / (uid + '.json')).read_text())['state'], 'cleaned')
            self.assertFalse((f.root / 'receipts' / (uid + '.json')).exists())
            self.assertTrue((f.root / 'published-cleanup' / (uid + '.json')).exists())

    def test_wrong_uid_epoch_source_unshared_scope_duplicate_binding_or_cap_fails_before_fence(self):
        for kind in ('uid', 'epoch', 'source', 'scope', 'binding', 'cap'):
            f = self.fixture()
            if kind == 'uid': f.plans[0]['journal']['record']['intent']['pod_uid'] = str(uuid.uuid4())
            elif kind == 'epoch': f.plans[0]['scope']['driver_generation'] = str(uuid.uuid4())
            elif kind == 'source': f.plans[0]['tool_sha256'] = 'sha256:' + '0' * 64
            elif kind == 'scope': f.plans[0]['scope']['pilot_pods'].pop()
            elif kind == 'binding': f.plans[0]['binding_id'] = f.plans[1]['binding_id']
            elif kind == 'cap': f.plans[0]['journal']['record']['intent']['cap_mib'] = 10240
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.execute(f)
            self.assertNotIn('acquire-batch', f.calls)

    def test_live_pod_wrong_actual_node_or_existing_audit_is_rejected_before_fence(self):
        for kind in ('pod', 'node', 'audit'):
            f = self.fixture()
            if kind == 'pod': f.pod = {'metadata': {'uid': str(uuid.uuid4())}}
            elif kind == 'node': f.node['metadata']['uid'] = str(uuid.uuid4())
            elif kind == 'audit': f.cms[r.names(f.plans[0])[0]] = {'existing': True}
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.execute(f)
            self.assertNotIn('acquire-batch', f.calls)

    def test_one_invalid_before_or_foreign_lock_tuple_creates_no_audit(self):
        for kind in ('memory', 'lock'):
            f = self.fixture()
            if kind == 'memory': f.before[1]['gpu_fd_clients'] = 1
            else: f.before[1]['locks']['journal']['inode'] += 1
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.execute(f)
            self.assertFalse(any(isinstance(c, tuple) and c[0] == 'create' for c in f.calls))

    def test_frozen_ledger_change_or_second_teardown_failure_stops_cleanup_publication(self):
        for kind in ('ledger', 'physical'):
            f = self.fixture(); real_verify = f.verify
            count = 0
            def verify():
                nonlocal count
                count += 1; result = real_verify()
                if kind == 'ledger':
                    f.ledger['metadata']['resourceVersion'] = '2'; f.cms[r.LEDGER] = f.ledger
                elif count == 2: result[1]['proc_modules'] = ['nvidia_uvm']
                return result
            f.verify = verify
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.execute(f)
            self.assertFalse(any(name.startswith('cps-native-cleanup-') for name in f.cms))

    def test_second_local_failure_does_not_mutate_or_release_any_allocation(self):
        f = self.fixture(); frozen = f.ledger['data']['state.json']; f.fail_local = True
        with self.assertRaisesRegex(ValueError, 'second local'): self.execute(f)
        self.assertEqual(f.ledger['data']['state.json'], frozen)
        self.assertEqual(f.local_count, 2)
        self.assertEqual(f.calls[-1], 'release-batch')
        self.assertFalse(any('patch' in str(c) or 'delete' in str(c) for c in f.calls))

    def test_final_actual_cleanup_uid_replacement_is_rejected(self):
        f = self.fixture(); real_publish = f.publish
        def publish(items):
            result = real_publish(items)
            f.cms[r.names(f.plans[1])[1]]['metadata']['uid'] = str(uuid.uuid4())
            return result
        f.publish = publish
        with self.assertRaisesRegex(ValueError, 'authority replaced'): self.execute(f)

    def test_release_freeze_loss_before_second_cleanup_prevents_its_publication(self):
        f = self.fixture(); count = 0
        def freeze():
            nonlocal count
            count += 1
            if count == 5: raise ValueError('Gateway unexpectedly resumed')
        f.assert_release_frozen = freeze
        with self.assertRaisesRegex(ValueError, 'unexpectedly resumed'): self.execute(f)
        self.assertTrue(r.names(f.plans[0])[1] in f.cms)
        self.assertFalse(r.names(f.plans[1])[1] in f.cms)
        self.assertNotIn('publish-batch', f.calls)

    def test_review_requires_exact_two_uids_current_sources_and_explicit_external_release_freeze(self):
        review = {'version': 1, 'qualification_only': True, 'allowed_pod_uids': b.UIDS,
            'node': b.NODE, 'node_uid': b.NODE_UID, 'boot_id': b.BOOT, 'driver_generation': b.GENERATION,
            'core_path': '/run/cps-native-gpu/driver-inputs-next/nvidia.ko',
            'uvm_path': '/run/cps-native-gpu/driver-inputs-next/nvidia-uvm.ko',
            'health_path': '/run/cps-native-gpu/driver-inputs-next/native_gpu_health.py',
            'health_sha256': 'sha256:' + b.HEALTH_SHA, 'publisher_sha256': 'sha256:' + b.PUBLISHER_SHA,
            'observation_source_sha256': 'sha256:' + b.OBSERVATIONS_SHA,
            'dependency_manifest_sha256': 'sha256:' + 'a' * 64, 'release_writers_paused': True,
            'release_freeze_evidence_sha256': 'sha256:' + 'b' * 64}
        b.validate_review(review, r)
        for key, value in (('release_writers_paused', False), ('allowed_pod_uids', [b.UIDS[0]]),
                           ('core_path', '/tmp/unapproved.ko'), ('health_sha256', 'sha256:' + '0' * 64)):
            candidate = {**review, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError): b.validate_review(candidate, r)

    def root_transaction(self, *, bad_second_before=False, premature=False, bad_dependency=False,
                         changed_teardown=False, short_final=False):
        f = self.fixture(); timeline = []; acquired = {}; phase = {'invalidated': False}
        # The fixture originally owns these locks. Release them so root_main
        # must acquire exactly the existing inode tuple itself.
        for fd in f.base.fds.values(): os.close(fd)
        f.base.fds = {}; f.fds = {}
        root = f.root
        def assert_locks():
            self.assertEqual(len(acquired), 3)
            for path, fd in acquired.items():
                self.assertEqual(os.fstat(fd).st_ino, path.stat().st_ino)
                competitor = os.open(path, os.O_RDWR)
                try:
                    with self.assertRaises(BlockingIOError): fcntl.flock(competitor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                finally: os.close(competitor)
        def acquire(path):
            fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); acquired[path] = fd; return fd
        uid_index = {p['journal']['record']['intent']['pod_uid']: i for i, p in enumerate(f.plans)}
        class Host:
            def __init__(self, *_): pass
            def before(self, plan):
                assert_locks(); self_index = uid_index[plan['journal']['record']['intent']['pod_uid']]
                timeline.append(('before', self_index)); self_phase = phase['invalidated']
                if self_phase: raise AssertionError('Before cannot be invented after authority invalidation')
                value = copy.deepcopy(f.before[self_index])
                if bad_second_before and self_index == 1: value['gpu_fd_clients'] = 1
                return value
            def teardown(self, plan, before, final=False):
                assert_locks(); index = uid_index[plan['journal']['record']['intent']['pod_uid']]
                if not phase['invalidated']: raise AssertionError('Teardown before external unload')
                timeline.append(('teardown', index, final)); value = copy.deepcopy(f.after[index])
                if changed_teardown and index == 1: value['proc_modules'] = ['nvidia_uvm']
                if final:
                    value['journal_sha256'] = r.raw_sha256((root / 'journal' / (b.UIDS[index] + '.json')).read_bytes())
                    value['gate_sha256'] = None
                r.validate_teardown(value, plan, b.sha(plan), before,
                    **({'journal_sha256': value['journal_sha256'], 'gate_sha256': None} if final else {}))
                return value
        def invalidate(*_):
            assert_locks(); self.assertEqual(timeline[:4], [('before', 0), ('before', 1)] * 2)
            timeline.append('invalidate-current'); phase['invalidated'] = True
        items = []
        for p, before, after in zip(f.plans, f.before, f.after):
            audit = r.audit_body(p, before, after); audit['metadata']['uid'] = str(uuid.uuid4())
            cleanup = r.cleanup_body(p, audit); cleanup['metadata']['uid'] = str(uuid.uuid4())
            items.append({'audit': audit, 'cleanup': cleanup})
        nonce, batch_id = str(uuid.uuid4()), str(uuid.uuid4())
        requests = [{'op': 'acquire-batch', 'nonce': nonce, 'plans': f.plans, 'batch_id': batch_id, 'batch_sha256': b.sha(f.plans)}]
        publication = {'op': 'publish-batch', 'nonce': nonce, 'batch_sha256': b.sha(f.plans), 'items': items}
        if not premature:
            requests += [{'op': 'verify-batch', 'nonce': nonce}] * 2
        requests += [publication, {'op': 'verify-batch-completion', 'nonce': nonce}]
        if not short_final: requests.append({'op': 'verify-batch-completion', 'nonce': nonce})
        requests.append({'op': 'release', 'nonce': nonce})
        observations = SimpleNamespace(read_rpc=Mock(side_effect=requests), acquire_lock=acquire,
            modules=Mock(return_value=([], [])))
        def local_complete(*args, **kwargs):
            assert_locks(); timeline.append(('complete', args[1]['journal']['record']['intent']['pod_uid']))
            self.assertEqual(kwargs['trusted_uid'], 0); kwargs['trusted_uid'] = os.getuid()
            with patch.object(r.os, 'geteuid', return_value=os.getuid()):
                return r.complete_local(*args, **kwargs)
        def local_read(*args, **kwargs):
            assert_locks(); kwargs['trusted_uid'] = os.getuid()
            with patch.object(r.os, 'geteuid', return_value=os.getuid()):
                return r.read_local_completion(*args, **kwargs)
        recovery = SimpleNamespace(**{name: getattr(r, name) for name in dir(r) if not name.startswith('__')})
        recovery.complete_local = Mock(side_effect=local_complete)
        recovery.read_local_completion = Mock(side_effect=local_read)
        recovery._mkdir_private = lambda path, uid, **kw: r._mkdir_private(path, os.getuid(), **kw)
        recovery._write = lambda path, raw, uid, **kw: r._write(path, raw, os.getuid(), **kw)
        rawmap = {Path(b.__file__): Path(b.__file__).read_bytes()}
        dependencies = {}
        for name in ('node_agent.py', 'abort_before_gate.py', 'source-snapshot.json'):
            data = ('inert fixture ' + name).encode(); rawmap[root / 'operator' / name] = data
            dependencies[name] = hashlib.sha256(data).hexdigest()
        depraw = b.canonical(dependencies).encode(); rawmap[root / 'operator/dependencies.json'] = depraw
        if bad_dependency: rawmap[root / 'operator/node_agent.py'] = b'changed'
        freezeraw = b.canonical({'actual_gateway_paused': True}).encode()
        rawmap[root / 'operator/batch-release-freeze.json'] = freezeraw
        review = {'version': 1, 'qualification_only': True, 'allowed_pod_uids': b.UIDS,
            'node': b.NODE, 'node_uid': b.NODE_UID, 'boot_id': b.BOOT, 'driver_generation': b.GENERATION,
            'core_path': '/run/cps-native-gpu/driver-inputs-next/nvidia.ko',
            'uvm_path': '/run/cps-native-gpu/driver-inputs-next/nvidia-uvm.ko',
            'health_path': '/run/cps-native-gpu/driver-inputs-next/native_gpu_health.py',
            'health_sha256': 'sha256:' + b.HEALTH_SHA, 'publisher_sha256': 'sha256:' + b.PUBLISHER_SHA,
            'observation_source_sha256': 'sha256:' + b.OBSERVATIONS_SHA,
            'dependency_manifest_sha256': b.raw_sha(depraw), 'release_writers_paused': True,
            'release_freeze_evidence_sha256': b.raw_sha(freezeraw)}
        reviewraw = b.canonical(review).encode(); rawmap[root / 'operator/batch-review.json'] = reviewraw
        def loading(path, digest, name):
            if name == 'batch_observations': return observations
            if name == 'teardown_recovery': return recovery
            return SimpleNamespace()
        failure = None
        with ExitStack() as stack, redirect_stdout(io.StringIO()) as output:
            stack.enter_context(patch.object(b, 'ROOT', root))
            stack.enter_context(patch.object(b.os, 'geteuid', return_value=0))
            stack.enter_context(patch.object(b, 'root_read', side_effect=lambda p: rawmap[p]))
            stack.enter_context(patch.object(b, 'load_root', side_effect=loading))
            stack.enter_context(patch.object(b, 'HostBatch', Host))
            stack.enter_context(patch.object(b, 'invalidate_current_authority', side_effect=invalidate))
            stack.enter_context(patch.object(b.subprocess, 'run', side_effect=AssertionError('No hardware/API')))
            try:
                b.root_main(SimpleNamespace(qualification=True, batch_source_sha256=b.raw_sha(rawmap[Path(b.__file__)]),
                                            review_sha256=b.raw_sha(reviewraw)))
            except ValueError as error: failure = error
        for fd in acquired.values():
            with self.assertRaises(OSError): os.fstat(fd)
        return failure, timeline, [json.loads(line) for line in output.getvalue().splitlines()], recovery

    def test_root_rpc_collects_both_genuine_before_proofs_and_holds_same_three_locks_through_completion(self):
        failure, timeline, events, recovery = self.root_transaction()
        self.assertIsNone(failure)
        self.assertEqual(timeline[:5], [('before', 0), ('before', 1)] * 2 + ['invalidate-current'])
        self.assertEqual(recovery.complete_local.call_count, 2)
        self.assertEqual(recovery.read_local_completion.call_count, 6)
        self.assertEqual([e['event'] for e in events], ['batch-acquired', 'batch-teardown-verified',
            'batch-teardown-verified', 'batch-local-published', 'batch-completion-verified', 'batch-completion-verified'])
        self.assertEqual(events[-3]['proof'], events[-2]['proof']); self.assertEqual(events[-2]['proof'], events[-1]['proof'])

    def test_root_rpc_bad_second_before_or_changed_dependency_never_invalidates_or_publishes(self):
        for kwargs in ({'bad_second_before': True}, {'bad_dependency': True}, {'premature': True}):
            with self.subTest(kwargs=kwargs):
                failure, timeline, _, recovery = self.root_transaction(**kwargs)
                self.assertIsNotNone(failure); self.assertNotIn('invalidate-current', timeline)
                recovery.complete_local.assert_not_called()

    def test_root_rpc_changed_second_teardown_or_short_final_verification_refuses_success(self):
        for kwargs in ({'changed_teardown': True}, {'short_final': True}):
            with self.subTest(kwargs=kwargs):
                failure, _, _, recovery = self.root_transaction(**kwargs)
                self.assertIsNotNone(failure)
                if kwargs.get('changed_teardown'): recovery.complete_local.assert_not_called()
                else: self.assertEqual(recovery.complete_local.call_count, 2)

    def test_actual_release_freeze_requires_pinned_paused_deployment_service_pod_absence_and_no_ready_endpoint(self):
        scope = {'version': 1, 'namespace': 'cps-compute', 'deployment': 'compute-gateway',
            'deployment_uid': str(uuid.uuid4()), 'service': 'compute-gateway', 'service_uid': str(uuid.uuid4()),
            'pod_selector': 'app=compute-gateway', 'images': ['ghcr.io/example/gateway@sha256:' + '1' * 64]}
        deployment = {'apiVersion': 'apps/v1', 'kind': 'Deployment',
            'metadata': {'namespace': scope['namespace'], 'name': scope['deployment'], 'uid': scope['deployment_uid'],
                         'generation': 3, 'resourceVersion': '4'},
            'spec': {'replicas': 0, 'selector': {'matchLabels': {'app': 'compute-gateway'}},
                     'template': {'spec': {'containers': [{'image': scope['images'][0]}]}}},
            'status': {'observedGeneration': 3}}
        service = {'apiVersion': 'v1', 'kind': 'Service',
            'metadata': {'namespace': scope['namespace'], 'name': scope['service'], 'uid': scope['service_uid']},
            'spec': {'selector': {'app': 'compute-gateway'}}}
        pods = {'apiVersion': 'v1', 'kind': 'PodList', 'metadata': {'resourceVersion': '5'}, 'items': []}
        slices = {'apiVersion': 'discovery.k8s.io/v1', 'kind': 'EndpointSliceList',
            'metadata': {'resourceVersion': '6'}, 'items': [{'metadata': {'namespace': scope['namespace'],
                'labels': {'kubernetes.io/service-name': scope['service']},
                'ownerReferences': [{'kind': 'Service', 'name': scope['service'], 'uid': scope['service_uid']}]},
                'endpoints': []}]}
        for kind in ('valid', 'null-endpoints', 'missing-endpoints', 'printer-pods', 'printer-slices',
                     'replicas', 'unobserved', 'uid', 'image', 'service', 'selector', 'pod', 'ready', 'unknown', 'terminating', 'slice-owner'):
            values = copy.deepcopy([deployment, service, pods, slices])
            d, s, p, e = values
            if kind == 'replicas': d['spec']['replicas'] = 1
            elif kind == 'unobserved': d['status']['observedGeneration'] = 2
            elif kind == 'uid': d['metadata']['uid'] = str(uuid.uuid4())
            elif kind == 'image': d['spec']['template']['spec']['containers'][0]['image'] += '-changed'
            elif kind == 'service': s['metadata']['uid'] = str(uuid.uuid4())
            elif kind == 'selector': s['spec']['selector']['app'] = 'wrong'
            elif kind == 'pod': p['items'] = [{'metadata': {'deletionTimestamp': '2026-10-09T00:00:00Z'}}]
            elif kind in ('ready', 'unknown', 'terminating'):
                e['items'][0]['endpoints'] = [{'addresses': ['10.1.1.1'], 'conditions': {'ready': True} if kind == 'ready'
                    else {'ready': False, 'serving': True, 'terminating': True} if kind == 'terminating' else {}}]
            elif kind == 'slice-owner': e['items'][0]['metadata']['ownerReferences'][0]['uid'] = str(uuid.uuid4())
            elif kind == 'null-endpoints': e['items'][0]['endpoints'] = None
            elif kind == 'missing-endpoints': e['items'][0].pop('endpoints')
            elif kind == 'printer-pods': p['kind'] = 'List'
            elif kind == 'printer-slices': e.update(apiVersion='v1', kind='List')
            backend = SimpleNamespace(call=Mock(side_effect=values))
            with self.subTest(kind=kind):
                if kind in ('valid', 'null-endpoints', 'missing-endpoints'):
                    proof = b.release_freeze(backend, scope, r)
                    self.assertEqual(proof['service_uid'], scope['service_uid'])
                    self.assertEqual(proof['pods_resource_version'], '5')
                    self.assertEqual(proof['endpoints_resource_version'], '6')
                    self.assertEqual(backend.call.call_args_list[2].args[0], ['get', '--raw',
                        '/api/v1/namespaces/cps-compute/pods?labelSelector=app%3Dcompute-gateway'])
                    self.assertEqual(backend.call.call_args_list[3].args[0], ['get', '--raw',
                        '/apis/discovery.k8s.io/v1/namespaces/cps-compute/endpointslices?labelSelector=kubernetes.io%2Fservice-name%3Dcompute-gateway'])
                else:
                    with self.assertRaises(ValueError): b.release_freeze(backend, scope, r)

    def test_host_before_and_teardown_use_real_validators_and_never_query_nvidia_after_unload(self):
        f = self.fixture(); plan, before, after = f.plans[0], f.before[0], f.after[0]
        observations = SimpleNamespace(modules=Mock(return_value=(sorted(b.MODULES), sorted(b.MODULES))),
            read_protected=Mock(return_value=b'manifest'), protected_module_sha=lambda path: b.MODULES['nvidia_uvm' if 'uvm' in path.name else 'nvidia'],
            gpu_fd_clients=Mock(return_value=0), pci_inventory=lambda: [g['pci_bdf'] for g in plan['scope']['nvidia_gpus']])
        plan['review']['load_manifest_sha256'] = b.raw_sha(b'manifest')
        before['plan_sha256'] = b.sha(plan); after['plan_sha256'] = b.sha(plan)
        review = {'core_path': '/run/cps-native-gpu/driver-inputs-next/nvidia.ko',
                  'uvm_path': '/run/cps-native-gpu/driver-inputs-next/nvidia-uvm.ko'}
        host = b.HostBatch(observations, r, SimpleNamespace(validate_native_driver_health=lambda: b.GENERATION), review, f.plans, f.fds)
        base = (plan['journal']['sha256'], before['gate_sha256'], True, 0, before['locks'])
        memory = '\n'.join(g['gpu_uuid'] + ', ' + g['pci_bdf'] + ', 0' for g in plan['scope']['nvidia_gpus'])
        with patch.object(host, 'base', return_value=base), \
             patch.object(b.subprocess, 'run', side_effect=[SimpleNamespace(stdout=memory), SimpleNamespace(stdout='')]):
            actual = host.before(plan)
        self.assertEqual(actual, before)
        observations.modules.return_value = ([], [])
        with patch.object(host, 'base', return_value=base), patch.object(b.os.path, 'lexists', return_value=False), \
             patch.object(b.subprocess, 'run', side_effect=AssertionError('No post-unload hardware command')):
            self.assertEqual(host.teardown(plan, actual), after)
            for kind in ('bound', 'module', 'fd'):
                observations.modules.return_value = (['nvidia'], []) if kind == 'module' else ([], [])
                observations.gpu_fd_clients.return_value = 1 if kind == 'fd' else 0
                with self.subTest(kind=kind), patch.object(b.os.path, 'lexists',
                    side_effect=lambda p: kind == 'bound' and str(p).endswith('/driver')):
                    with self.assertRaises(ValueError): host.teardown(plan, actual)

    def test_current_authority_invalidation_checks_exact_generation_manifest_before_any_unlink(self):
        for kind in ('valid', 'generation', 'manifest'):
            f = self.fixture(); root = f.root
            generation = root / 'authority/driver-generation'; manifest = root / 'authority/driver-load-manifest.json'
            generation.write_text((b.GENERATION if kind != 'generation' else str(uuid.uuid4())) + '\n')
            generation.chmod(0o600); manifest.write_bytes(b'actual manifest'); manifest.chmod(0o400)
            f.plans[0]['review']['load_manifest_sha256'] = b.raw_sha(b'actual manifest' if kind != 'manifest' else b'wrong')
            observations = SimpleNamespace(directory=lambda path: path.lstat(), read_protected=lambda path, **_: path.read_bytes())
            with patch.object(b, 'ROOT', root), patch.object(b.subprocess, 'run', side_effect=AssertionError('No module action')):
                if kind == 'valid':
                    b.invalidate_current_authority(observations, r, f.plans[0])
                    self.assertFalse(generation.exists()); self.assertFalse(manifest.exists())
                else:
                    with self.assertRaisesRegex(ValueError, 'authority changed'): b.invalidate_current_authority(observations, r, f.plans[0])
                    self.assertTrue(generation.exists()); self.assertTrue(manifest.exists())


if __name__ == '__main__': unittest.main()
