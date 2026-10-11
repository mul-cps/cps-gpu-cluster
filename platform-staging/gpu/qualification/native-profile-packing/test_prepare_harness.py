"""CPU tests only. Synthetic values never become hardware receipts."""
import copy
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).parent
SCRIPT = HERE / 'prepare_harness.py'
spec = importlib.util.spec_from_file_location('packing_harness', SCRIPT)
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)

def binding():
    return {'version': 1, 'state': 'Root-reviewed-controlled-plan',
        'policy_hash': 'sha256:' + 'a' * 64,
        'observer_uid': '00000000-0000-4000-8000-000000000003',
        'pool': {'node': 'k3s-wk-gpu2', 'node_uid': '3336cdd5-d245-436e-b57c-2f66c6dcaa41',
            'boot_id': '209f8bc9-a478-48e4-925a-6e07ffa56f7a',
            'gpu_uuid': 'GPU-16128952-b438-556a-00bb-93039ee24e56',
            'driver_generation': 'b10498fc-9153-4394-875a-ea7cfb498625',
            'budget_mib': 15360, 'measured_free_bytes': 20 * 1024 ** 3,
            'headroom_bytes': 4 * 1024 ** 3, 'measurement_sha256': '1' * 64},
        'retired_capture': {'path': '/private/actual-retired.json', 'sha256': '2' * 64},
        'pool_measurement': {'path': '/private/actual-nvml.json', 'sha256': '1' * 64},
        'targets': [dict(source=s, workspace=w, namespace=n, name=p, cap_mib=c,
            profile='interactive-native-qualification-' + str(c // 1024),
            pod_uid='00000000-0000-4000-8000-00000000000' + str(i + 1),
            spec_sha256=str(i + 3) * 64,
            pod_capture={'path': '/private/actual-pod-' + str(i) + '.json', 'sha256': str(i + 5) * 64})
            for i, (s, w, n, p, c) in enumerate(h.SCOPES)]}

class BindingTests(unittest.TestCase):
    def test_exact_pair_and_measured_budget_accepted_without_qualification(self):
        self.assertEqual(h.validate_binding(binding()), binding())

    def test_changed_cap_scope_policy_or_duplicate_uid_rejected(self):
        cases = []
        for key, value in [('cap_mib', 5120), ('source', 'cps'), ('workspace', 'native-group-b'),
                           ('namespace', 'jupyterhub'), ('pod_uid', binding()['targets'][0]['pod_uid']),
                           ('spec_sha256', 'missing')]:
            b = binding(); b['targets'][1][key] = value; cases.append(b)
        b = binding(); b['policy_hash'] = 'latest'; cases.append(b)
        b = binding(); b['enabled'] = True; cases.append(b)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError): h.validate_binding(value)

    def test_measured_budget_cannot_exceed_free_minus_headroom(self):
        b = binding(); b['pool']['measured_free_bytes'] = 18 * 1024 ** 3
        with self.assertRaises(ValueError): h.validate_binding(b)

    def test_booleans_cannot_substitute_for_cap_or_measured_bytes(self):
        for key in ['budget_mib', 'measured_free_bytes', 'headroom_bytes']:
            b = binding(); b['pool'][key] = True
            with self.subTest(key=key), self.assertRaises(ValueError): h.validate_binding(b)

class StopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('CPS_OCT9_PROBE_ROOT',
            '/home/bjoern/.local/state/cps-group-native-20261009/group-probes')) / \
            'activation-runtime-prepared/qualified-six-retired-preflight/retired-caps.json'
        if not path.exists(): raise unittest.SkipTest('Original CPU schema template unavailable')
        try: import cps_compute.native_gpu_control
        except ImportError: raise unittest.SkipTest('Pinned SDK controller models unavailable')
        cls.record = json.loads(path.read_text())['records'][0]['record']
        spec = importlib.util.spec_from_file_location('inspect_stop', HERE / 'inspect_stop.py')
        cls.stop = importlib.util.module_from_spec(spec)
        sys.modules['prepare_harness'] = h; spec.loader.exec_module(cls.stop)

    def fixture(self):
        b = binding(); before = {'host': {'targets': [], 'retired_caps': [{'pod_uid': 'prior-cpu-only', 'immutable': 'same'}]}}
        physical = {'kind': 'native-group-host-observation', **{k: b['pool'][k] for k in
            ('node', 'node_uid', 'boot_id', 'gpu_uuid', 'driver_generation')}, 'targets': [],
            'retired_caps': copy.deepcopy(before['host']['retired_caps'])}
        enrollments = []; cleanups = []; allocations = {}; self.journals = []
        for i, target in enumerate(b['targets']):
            original = copy.deepcopy(self.record); uid = target['pod_uid']; old_uid = original['identity']['pod_uid']
            intent = original['intent']; intent.update({k: target[k] for k in
                ('namespace', 'name', 'pod_uid', 'spec_sha256', 'cap_mib')}, policy_hash=b['policy_hash'])
            identity = original['identity']; identity.update(pod_uid=uid, spec_sha256=target['spec_sha256'])
            for k in ('cgroup_relative', 'cgroup_path'):
                identity[k] = identity[k].replace(old_uid, uid).replace(old_uid.replace('-', '_'), uid.replace('-', '_'))
            identity['cgroup_inode'] += i
            proof = original['retirement']; proof['identity'] = identity
            entry = proof['entry']; entry.update(cgroup_id=identity['cgroup_inode'], kernfs_id=identity['cgroup_inode'],
                inode=identity['cgroup_inode'], soft=target['cap_mib'] * 1048576, hard=target['cap_mib'] * 1048576)
            original['readback'] = {'soft': target['cap_mib'] * h.MIB, 'hard': target['cap_mib'] * h.MIB}
            native = {'pod_uid': uid, 'intent': intent, 'identity': identity, 'seal_id': original['seal_id']}
            before['host']['targets'].append(native)
            journal = (h.canonical(original) + '\n').encode(); self.journals.append(journal)
            binding_id = str(i + 7) * 60
            enrollment = {'version': 1, 'binding_id': binding_id, 'source': target['source'], 'actor': target['source'],
                'workspace': target['workspace'], 'profile': target['profile'], 'policy_hash': b['policy_hash'],
                'namespace': target['namespace'], 'name': target['name'], 'intent': intent, 'attempt': 'cpu-attempt-' + str(i)}
            def cm(prefix, key, doc, number):
                return {'apiVersion': 'v1', 'kind': 'ConfigMap', 'immutable': True,
                    'metadata': {'namespace': 'cps-native-system', 'name': prefix + binding_id[:40],
                        'uid': '00000000-0000-4000-8000-0000000000' + str(number),
                        'labels': {'cps.compute/native-binding': binding_id}}, 'data': {key: h.canonical(doc)}}
            enrollment_cm = cm('cps-native-enrollment-', 'enrollment.json', enrollment, 10 + i)
            retirement = {'proof': proof, 'enrollment_uid': enrollment_cm['metadata']['uid'],
                'enrollment_sha256': 'sha256:' + h.sha(h.canonical(enrollment).encode()),
                'journal_sha256': 'sha256:' + h.sha(h.canonical(original).encode())}
            cleanup = {'version': 1, 'binding_id': binding_id, 'attempt': enrollment['attempt'],
                'intent': intent, 'cleanup_confirmed': True, 'retirement': retirement}
            enrollments.append(enrollment_cm); cleanups.append(cm('cps-native-cleanup-', 'receipt.json', cleanup, 12 + i))
            allocations[binding_id] = {**enrollment, 'state': 'released'}
            physical['retired_caps'].append({'pod_uid': uid, 'journal_sha256': 'sha256:' + h.sha(journal),
                'identity': identity, 'retirement': proof, 'inventory_row': entry})
        ledger = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'namespace': 'cps-native-system',
            'name': 'cps-native-gpu-allocations', 'uid': '00000000-0000-4000-8000-000000000015'},
            'data': {'state.json': h.canonical({'version': 1, 'allocations': allocations})}}
        return [b, before, ledger, {'apiVersion': 'v1', 'kind': 'PodList', 'metadata': {}, 'items': []},
                physical, enrollments, cleanups, self.journals]

    def test_raw_journal_and_canonical_cleanup_are_distinct_valid_digests(self):
        args = self.fixture()
        for index, raw in enumerate(self.journals):
            cleanup = h.parse(args[6][index]['data']['receipt.json'])
            self.assertNotEqual('sha256:' + h.sha(raw), cleanup['retirement']['journal_sha256'])
        value = self.stop.validate(*args)
        self.assertEqual(len(value['terminal_lifetimes']), 2)
        self.assertFalse(value['hardware_qualification'])
        for index, row in enumerate(value['terminal_lifetimes']):
            self.assertEqual(row['journal_raw_sha256'], 'sha256:' + h.sha(args[7][index]))
            self.assertEqual(row['journal_canonical_sha256'],
                h.parse(args[6][index]['data']['receipt.json'])['retirement']['journal_sha256'])

    def test_both_independent_digest_chains_are_required(self):
        for kind in ('raw-bytes', 'physical-raw-pin', 'cleanup-canonical-pin', 'swapped-journals', 'missing-journals'):
            args = self.fixture()
            if kind == 'raw-bytes': args[7][0] += b'\n'
            elif kind == 'physical-raw-pin': args[4]['retired_caps'][1]['journal_sha256'] = 'sha256:' + '1' * 64
            elif kind == 'cleanup-canonical-pin':
                cleanup = h.parse(args[6][0]['data']['receipt.json'])
                cleanup['retirement']['journal_sha256'] = 'sha256:' + h.sha(args[7][0])
                args[6][0]['data']['receipt.json'] = h.canonical(cleanup)
            elif kind == 'swapped-journals': args[7].reverse()
            else: args[7] = None
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.stop.validate(*args)

    def test_rehashed_full_record_drift_cannot_replace_original_seal(self):
        changes = [('seal_id', '00000000-0000-4000-8000-000000000099'),
                   ('readback', None), ('schema', True), ('state', 'sealed'),
                   ('protocol', 'foreign'), ('extra_unreviewed', True)]
        for key, value in changes:
            args = self.fixture(); record = h.parse(args[7][0]); record[key] = value
            args[7][0] = (h.canonical(record) + '\n').encode()
            args[4]['retired_caps'][1]['journal_sha256'] = 'sha256:' + h.sha(args[7][0])
            cleanup = h.parse(args[6][0]['data']['receipt.json'])
            cleanup['retirement']['journal_sha256'] = 'sha256:' + h.sha(h.canonical(record).encode())
            args[6][0]['data']['receipt.json'] = h.canonical(cleanup)
            with self.subTest(key=key), self.assertRaises(ValueError): self.stop.validate(*args)

    def test_duplicate_record_keys_cannot_hide_behind_valid_raw_pin(self):
        args = self.fixture()
        args[7][0] = args[7][0].replace(b'{', b'{"state":"sealed",', 1)
        args[4]['retired_caps'][1]['journal_sha256'] = 'sha256:' + h.sha(args[7][0])
        with self.assertRaises(ValueError): self.stop.validate(*args)

    def test_cli_verifies_raw_journal_file_pin_and_closed_manifest(self):
        args = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o700)
            def write(name, value):
                raw = value if isinstance(value, bytes) else (h.canonical(value) + '\n').encode()
                path = root / name; path.write_bytes(raw); path.chmod(0o600)
                return {'path': str(path), 'sha256': h.sha(raw)}
            manifest = {key: write(key + '.json', value) for key, value in zip(
                ('binding', 'before', 'ledger', 'pods', 'physical'), args[:5])}
            for key, values in zip(('enrollments', 'cleanups', 'journals'), args[5:]):
                manifest[key] = [write(key + str(i) + '.json', value) for i, value in enumerate(values)]
            def run(value):
                pin = write('manifest.json', value)
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.stop.main(['--inspect', '--manifest', pin['path'], '--manifest-sha256', pin['sha256']])
                return json.loads(output.getvalue())
            self.assertFalse(run(manifest)['hardware_qualification'])
            legacy = copy.deepcopy(manifest); legacy.pop('journals')
            with self.assertRaises(ValueError): run(legacy)
            Path(manifest['journals'][0]['path']).write_bytes(args[7][0] + b'\n')
            with self.assertRaises(ValueError): run(manifest)

    def test_default_inert_does_not_read_manifest_or_journals(self):
        with patch.object(h, 'read_pinned', side_effect=AssertionError('Default must not read inputs')):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.stop.main(['--manifest', '/missing', '--manifest-sha256', '0' * 64])
        value = json.loads(output.getvalue())
        self.assertEqual(value['state'], 'inert')
        self.assertFalse(value['api_calls']); self.assertFalse(value['gpu_calls'])

    def test_exact_stop_witnesses_remain_unqualified(self):
        value = self.stop.validate(*self.fixture())
        self.assertFalse(value['hardware_qualification'])
        self.assertFalse(value['production_qualified'])

    def test_paginated_pod_absence_must_not_release_original_uid(self):
        args = self.fixture(); args[3]['metadata']['continue'] = 'next-page-with-old-uid'
        with self.assertRaises(ValueError): self.stop.validate(*args)

    def test_missing_changed_or_extra_prior_retirement_rejected(self):
        for kind in ('missing', 'changed', 'extra'):
            args = self.fixture()
            if kind == 'missing': args[4]['retired_caps'].pop(0)
            elif kind == 'changed': args[4]['retired_caps'][0]['immutable'] = 'changed'
            else: args[4]['retired_caps'].append({'pod_uid': 'extra-unbound'})
            with self.subTest(kind=kind), self.assertRaises(ValueError): self.stop.validate(*args)

    def test_cleanup_from_foreign_attempt_and_nonreleased_ledger_rejected(self):
        args = self.fixture(); row = json.loads(args[6][1]['data']['receipt.json']); row['attempt'] = 'foreign'
        args[6][1]['data']['receipt.json'] = h.canonical(row)
        with self.assertRaises(Exception): self.stop.validate(*args)
        args = self.fixture(); state = json.loads(args[2]['data']['state.json']); next(iter(state['allocations'].values()))['state'] = 'releasing'
        args[2]['data']['state.json'] = h.canonical(state)
        with self.assertRaises(ValueError): self.stop.validate(*args)

class ReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ.get('CPS_OCT9_PROBE_ROOT',
            '/home/bjoern/.local/state/cps-group-native-20261009/group-probes'))
        if not cls.root.exists(): raise unittest.SkipTest('Exact private Oct9 sources unavailable')

    def rendered(self):
        sources = {name: (self.root / name).read_bytes() for name in h.SOURCE_PINS}
        return h.render_sources(sources, binding(), {'records': []})

    def test_source_pin_mutation_rejected_before_rendering(self):
        sources = {name: (self.root / name).read_bytes() for name in h.SOURCE_PINS}
        sources['group_probe.py'] += b'\n# unreviewed\n'
        with self.assertRaises(ValueError): h.render_sources(sources, binding(), {'records': []})

    def test_rendered_default_helpers_are_inert_without_kubectl(self):
        with tempfile.TemporaryDirectory() as root:
            for name, raw in self.rendered().items():
                path = Path(root) / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
            for name in ['run_group_acceptance.py', 'group_probe.py', 'mps/run_mps.py',
                         'mps/mps_probe.py', 'imports/run_same_pod.py',
                         'imports-cross-pod/run_cross_pod.py', 'vmm-cross-parent-sgid-fix/run_vmm_cross_parent.py',
                         'vmm-owner-exit/run_owner_exit.py', 'run_kernel_controls.py', 'inspect_stop.py', 'run_retirement_witness.py']:
                result = subprocess.run([sys.executable, str(Path(root) / name)], capture_output=True,
                    text=True, env={**os.environ, 'PATH': '/nonexistent'}, timeout=5)
                self.assertEqual(result.returncode, 0, (name, result.stderr))
                value = json.loads(result.stdout); self.assertEqual(value['state'], 'inert')
                self.assertFalse(value.get('production_qualified', False))

    def test_kernel_collectors_and_original_input_binary_remain_exact(self):
        out = self.rendered()
        for name in h.SOURCE_PINS:
            if name.endswith(('kernel_witness_collector.py', 'kernel_witness_validator.py',
                              'kernel_witness_transport.py')) or name == 'native-imports':
                self.assertEqual(out[name], (self.root / name).read_bytes())

    def test_operator_argv_all_parse_inert_and_remain_unexecuted(self):
        with tempfile.TemporaryDirectory() as root:
            out = self.rendered(); output = Path(root)
            for name, raw in out.items():
                path = output / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
            recipe = h.operator_argv(output, binding(), out, 'f' * 64)
            self.assertFalse(recipe['execution_authorized_by_preparer'])
            for name, argv in recipe['commands'].items():
                argv.remove('--execute')
                result = subprocess.run(argv, capture_output=True, text=True,
                    env={**os.environ, 'PATH': '/nonexistent'}, timeout=5)
                self.assertEqual(result.returncode, 0, (name, result.stderr))
                self.assertEqual(json.loads(result.stdout)['state'], 'inert')

    def module(self, name):
        scope = {'__name__': 'cpu_test_only', '__file__': '/private/' + name}
        exec(compile(self.rendered()[name], name, 'exec'), scope)
        return scope

    def test_rendered_mps_oversized_request_reaches_cuda_without_touch(self):
        m = self.module('mps/mps_probe.py'); calls = []
        class Lib:
            def cuMemAlloc_v2(self, pointer, amount): calls.append(amount); return 2
            def cuMemsetD8_v2(self, *args): raise AssertionError('Oversized allocation touched')
        cuda = m['Cuda'].__new__(m['Cuda']); cuda.lib = Lib(); cuda.held = []
        result = cuda.allocate(10496, touch=False)
        self.assertEqual(calls, [10496 * h.MIB]); self.assertEqual(result['cuda_result'], 2)
        for amount, touch in [(10496, True), (10497, False), (10240, False), (True, False)]:
            with self.subTest(amount=amount, touch=touch), self.assertRaises(ValueError):
                cuda.allocate(amount, touch=touch)
        self.assertEqual(len(calls), 1)

    def test_rendered_mps_two_real_allocation_methods_reach_cap_oom_and_recover(self):
        m = self.module('mps/mps_probe.py'); allocated = {}; calls = []; touched = []; ticks = [0, 0]
        class Lib:
            def cuMemAlloc_v2(self, pointer, amount):
                calls.append(amount)
                if sum(allocated.values()) + amount > 10240 * h.MIB: return 2
                pointer._obj.value = len(calls); allocated[len(calls)] = amount; return 0
            def cuMemsetD8_v2(self, pointer, bias, amount): touched.append(amount); return 0
            def cuCtxSynchronize(self): return 0
            def cuMemFree_v2(self, pointer): del allocated[pointer.value]; return 0
        class Client:
            def __init__(self, index):
                self.index = index; self.cuda = m['Cuda'].__new__(m['Cuda'])
                self.cuda.lib = Lib(); self.cuda.held = []
            def request(self, operation, **kwargs):
                if operation == 'tick': ticks[self.index] += 1; return {'cuda_result': 0}
                return getattr(self.cuda, operation)(**kwargs)
        events = []
        with patch.object(m['time'], 'sleep'):
            value = m['aggregate_sequence']([Client(0), Client(1)], lambda p, x: events.append((p, x)))
        self.assertEqual(value['typed_oom'], {'cuda_result': 2, 'held_mib': 10240, 'attempted_mib': 10496})
        self.assertEqual(value['recovery_clients'], 2); self.assertEqual(allocated, {})
        self.assertIn(10496 * h.MIB, calls); self.assertNotIn(10496 * h.MIB, touched)
        self.assertEqual(calls.count(256 * h.MIB), 41); self.assertTrue(all(v >= 41 for v in ticks))

    def test_rendered_native_rows_execute_both_caps_and_reject_swaps(self):
        names = ['imports-cross-pod/ipc_endpoint.py', 'imports-cross-pod/ipc_host_pid.py',
            'vmm-cross-parent-sgid-fix/vmm_endpoint.py', 'vmm-cross-parent-sgid-fix/vmm_bridge.py',
            'vmm-owner-exit/owner_exit_probe.py', 'vmm-owner-exit/host_owner_observer.py']
        for name in names:
            m = self.module(name)
            for target in binding()['targets']:
                uid = target['pod_uid']; cap = target['cap_mib'] * h.MIB
                self.assertEqual(m['bind_cap'](uid), cap); self.assertEqual(m['CAP'], cap)
                row = dict(soft=cap, hard=cap, used=cap, offline=False, pinned=True, default_hierarchy=True)
                self.assertTrue(m['cap_row'](row, uid))
                for mutation in [dict(soft=15360*h.MIB), dict(hard=5120*h.MIB if cap>5120*h.MIB else 10240*h.MIB),
                                 dict(used=cap+1), dict(used=True), dict(offline=True)]:
                    with self.subTest(name=name, uid=uid, mutation=mutation), self.assertRaises(ValueError):
                        m['cap_row']({**row, **mutation}, uid)
            with self.assertRaises(ValueError): m['bind_cap']('foreign')

    def test_creator_exit_actual_inventory_uses_target_cap(self):
        m = self.module('vmm-owner-exit/host_owner_observer.py')
        for target in binding()['targets']:
            cap = target['cap_mib'] * h.MIB; identity = {'pod_uid': target['pod_uid'], 'cgroup_inode': 42}
            row = dict(cgroup_id=42, kernfs_id=42, inode=42, soft=cap, hard=cap, used=cap,
                       offline=False, pinned=True, default_hierarchy=True)
            value = dict(version=1, backend='misc-fallback', gpu_uuid=m['GPU'], gpu_id=1, entries=[row])
            self.assertEqual(m['inventory'](json.dumps(value), identity), row)
            value['entries'][0]['hard'] = 5120*h.MIB if cap>5120*h.MIB else 10240*h.MIB
            with self.assertRaises(ValueError): m['inventory'](json.dumps(value), identity)

    def test_vmm_bridge_binds_new_pair_and_fresh_private_stage(self):
        m = self.module('vmm-cross-parent-sgid-fix/vmm_bridge.py')
        w = self.module('vmm-cross-parent-sgid-fix/run_vmm_cross_parent.py')
        self.assertEqual(str(m['ROOT']), w['BRIDGE_ROOT'])
        self.assertNotIn('vmm-cross-parent-sgid-fix', str(m['ROOT']))
        def endpoint(t, role, expect):
            return dict(role=role, expect=expect, namespace_pid=51,
                identity=dict(pod_uid=t['pod_uid'], driver_generation=m['GENERATION']))
        request = dict(trial_id='00000000-0000-4000-8000-000000000009', transfer='cross',
            exporter=endpoint(binding()['targets'][0], 'exporter', 'allow'),
            importer=endpoint(binding()['targets'][1], 'importer', 'deny'))
        m['validate_request'](request)
        request['importer']['identity']['pod_uid'] = '879a4589-faee-4569-bdb8-f2e7c154ef19'
        with self.assertRaises(ValueError): m['validate_request'](request)

    def test_ipc_runtime_argv_and_host_attribution_bind_each_actual_uid(self):
        out = self.rendered(); wrapper = out['imports-cross-pod/run_cross_pod.py'].decode()
        self.assertIn("'--role', 'exporter', '--expected-pod-uid', exporter_target['pod_uid']", wrapper)
        self.assertIn("'--role', 'importer', '--expected-pod-uid', exporter_target['pod_uid']", wrapper)
        self.assertIn("'--role', 'importer', '--expected-pod-uid', importer_target['pod_uid']", wrapper)
        self.assertIn("(b'--expected-pod-uid', identity['pod_uid'].encode())", out['imports-cross-pod/ipc_host_pid.py'].decode())

    def test_actual_cpu_build_receipt_rejects_image_source_binary_and_live_recipe_changes(self):
        root = Path('/home/bjoern/.local/state/cps-platform-completion-20261011/packing-session-20261011T154440Z/native-import-cpu-build')
        if not root.exists(): self.skipTest('Actual Root offline CPU build unavailable')
        raw = (root/'native-imports-10').read_bytes(); receipt = h.parse((root/'build-receipt.json').read_bytes())
        self.assertEqual(h.sha(raw), '8776c4593144a3c8d87f2f08b8703826a1038fdebc35eb76f4779d0dfd6ff304')
        inputs = h.validate_native_build(receipt, raw, h.sha(raw), root/'native-imports-10')
        for key, pin in inputs.items():
            h.read_pinned(Path(pin['path']), pin['sha256'], allow_empty=key in ('stdout', 'stderr'))
        for key, value in [('sourceSha256', '0'*64), ('imageId', 'sha256:'+'0'*64),
                           ('hardwareQualified', True), ('compileExitCode', False), ('gpu_calls', True)]:
            changed = copy.deepcopy(receipt); changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                h.validate_native_build(changed, raw, h.sha(raw), root/'native-imports-10')
        changed = copy.deepcopy(receipt); changed['compileArgv'][4] = '--network=host'
        with self.assertRaises(ValueError): h.validate_native_build(changed, raw, h.sha(raw), root/'native-imports-10')
        with self.assertRaises(ValueError): h.validate_native_build(receipt, raw+b'changed', h.sha(raw), root/'native-imports-10')

    def test_rendered_same_parent_uses_ten_gib_native_argv_and_assessment(self):
        m = self.module('imports/same_pod_imports.py')
        self.assertEqual(m['CAP'], 10240 * h.MIB)
        captured = []
        class Child:
            def __init__(self, argv, label): captured.append(argv); raise RuntimeError('CPU argv capture')
        with tempfile.TemporaryDirectory() as root:
            binary = Path(root) / 'native-imports'; binary.write_bytes(self.rendered()['native-imports']); binary.chmod(0o700)
            with patch.object(m['os'], 'getuid', return_value=1000), patch.object(m['os'], 'getgid', return_value=100), \
                 patch.object(m['stat'], 'S_ISREG', return_value=True), patch.dict(m, Child=Child), \
                 patch.object(Path, 'mkdir'), \
                 patch.object(Path, 'lstat', return_value=type('S', (), {'st_mode':0o100700,'st_uid':1000,'st_nlink':1})()):
                with self.assertRaisesRegex(RuntimeError, 'CPU argv capture'):
                    m['run'](binary, Path('/tmp/cpu-closed-import'), 'vmm-direct')
        self.assertEqual(captured[0][-2:], ['--cap-mib', '10240'])

    def test_rendered_cap_lookup_binds_both_lifetimes_and_rejects_foreign_uid(self):
        for name in ['imports-cross-pod/ipc_endpoint.py', 'imports-cross-pod/ipc_host_pid.py',
                     'vmm-cross-parent-sgid-fix/vmm_endpoint.py', 'vmm-cross-parent-sgid-fix/vmm_bridge.py',
                     'vmm-owner-exit/owner_exit_probe.py', 'vmm-owner-exit/host_owner_observer.py',
                     'vmm-owner-exit/run_owner_exit.py']:
            m = self.module(name)
            for t in binding()['targets']:
                self.assertEqual(m['expected_cap'](t['pod_uid']), t['cap_mib'] * h.MIB)
            with self.subTest(name=name), self.assertRaises(ValueError): m['expected_cap']('foreign')

    def test_ten_gib_oversized_and_step_oom_then_recovery_really_call_new_amount(self):
        m = self.module('group_probe.py'); m['CAP_MIB'] = 10240
        torch = CpuTorch(10240); events = []
        with patch.object(m['time'], 'sleep'):
            value = m['run_steps'](torch, lambda p, x=None: events.append((p, x)), 9216)
        self.assertTrue(value['bounded_step_sequence_passed'])
        self.assertTrue(value['oversized_denied'])
        self.assertEqual(torch.attempts[1], 10496)
        self.assertEqual(value['held_before_oom_mib'], 9984)
        self.assertEqual(value['ordinary_byte'], 19)
        self.assertEqual(value['recovery_byte'], 37)
        self.assertEqual(torch.held, 0)
        self.assertIn(('held-native-observation-window', {'held_tensor_mib': 9216, 'hold_seconds': 30}), events)

    def test_successful_oversized_allocation_is_never_touched_and_released(self):
        m = self.module('group_probe.py'); m['CAP_MIB'] = 10240
        torch = CpuTorch(10240, allow_oversized=True)
        with self.assertRaises(RuntimeError): m['run_steps'](torch, lambda *a: None, 9216)
        self.assertEqual(torch.held, 0)
        self.assertNotIn(10496, torch.touched)

    def test_unrelated_cuda_error_cannot_be_called_oom(self):
        m = self.module('group_probe.py'); m['CAP_MIB'] = 10240
        torch = CpuTorch(10240, wrong_error=True)
        with self.assertRaises(ValueError): m['run_steps'](torch, lambda *a: None, 9216)
        self.assertEqual(torch.held, 0)

    def test_preflight_rejects_foreign_lifetime_before_any_api_call(self):
        m = self.module('run_group_acceptance.py')
        config = copy.deepcopy(m['BOUND_CONFIG']); config['targets'][1]['pod_uid'] = '00000000-0000-4000-8000-000000000009'
        m['get'] = lambda *a: self.fail('API call before rejecting foreign binding')
        with self.assertRaises(ValueError): m['preflight'](config)

    def test_replay_mps_five_gib_receipt_rejected_by_ten_gib_assessor(self):
        m = self.module('mps/run_mps.py')
        events = mps_events(m['PROBE_SHA'])
        peer = peer_events()
        self.assertTrue(m['assess'](events, peer)['measurement_passed'])
        for key, value in [('cap_mib', 5120), ('max_attempted_mib', 5376), ('source_sha256', 'f' * 64)]:
            changed = copy.deepcopy(events); changed[-1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): m['assess'](changed, peer)
        changed = copy.deepcopy(events); changed[1]['cuda_result'] = 1
        with self.assertRaises(ValueError): m['assess'](changed, peer)

    def test_mps_cleanup_and_peer_window_remain_required(self):
        m = self.module('mps/run_mps.py'); events = mps_events(m['PROBE_SHA']); peer = peer_events()
        changed = copy.deepcopy(events); changed[-2]['private_mps_processes'] = [123]
        with self.assertRaises(ValueError): m['assess'](changed, peer)
        changed = copy.deepcopy(peer); changed[0]['monotonic_ns'] = 4
        with self.assertRaises(ValueError): m['assess'](events, changed)

class CpuTorch:
    """Allocation boundary double; never imports Torch or executes CUDA."""
    class OutOfMemoryError(Exception): pass
    uint8 = 'uint8'
    def __init__(self, cap, allow_oversized=False, wrong_error=False):
        self.cap = cap; self.allow_oversized = allow_oversized; self.wrong_error = wrong_error
        self.held = 0; self.attempts = []; self.touched = []; self.cuda = self
    def empty(self, size, **kwargs):
        mib = size // 1048576; self.attempts.append(mib)
        if mib > self.cap and not self.allow_oversized:
            if self.wrong_error: raise ValueError('CPU synthetic unrelated CUDA failure')
            raise self.OutOfMemoryError()
        if mib <= self.cap and self.held + mib > self.cap - 256: raise self.OutOfMemoryError()
        self.held += mib; return CpuTensor(self, mib)
    def synchronize(self): pass
    def empty_cache(self): pass

class CpuTensor:
    def __init__(self, torch, mib): self.torch = torch; self.mib = mib; self.value = None
    def fill_(self, value): self.value = value; self.torch.touched.append(self.mib)
    def __getitem__(self, index): return self
    def item(self): return self.value
    def __del__(self): self.torch.held -= self.mib

def mps_events(probe_sha):
    run = 'cpu-only'
    values = [dict(phase='mps-registered', run_id=run, monotonic_ns=2),
        dict(phase='oversized-denial', cuda_result=2, attempted_mib=10496),
        dict(phase='typed-oom', run_id=run, monotonic_ns=3, cuda_result=2, held_mib=9984, attempted_mib=10240),
        dict(phase='recovery-passed', run_id=run, monotonic_ns=4, clients=2),
        dict(phase='daemon-cleanup-confirmed', run_id=run, monotonic_ns=5, completed=True,
             client_exit_codes=[0, 0], cleanup_errors=[], private_mps_processes=[]),
        dict(state='bounded-sequence-passed', case='oom', cap_mib=10240, max_attempted_mib=10496,
             source_sha256=probe_sha, aggregate_sequence_passed=True, recovery_clients=2,
             typed_oom={'cuda_result': 2, 'held_mib': 9984, 'attempted_mib': 10240}, production_qualified=False)]
    return values

def peer_events():
    return [dict(phase='peer_tick', monotonic_ns=n) for n in (1, 3, 6)] + [
        dict(phase='receipt', case='peer', state='measurement-completed', peer_loop_passed=True,
             production_qualified=False, hardware={'gpu_uuid': 'GPU-16128952-b438-556a-00bb-93039ee24e56',
             'uid': 1000, 'gid': 100})]

class InertTests(unittest.TestCase):
    def test_default_does_not_require_source_binding_or_call_external_tools(self):
        result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True,
                                env={**os.environ, 'PATH': '/nonexistent'}, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value['state'], 'inert')
        self.assertFalse(value['gpu_calls'])
        self.assertFalse(value['api_calls'])
        self.assertFalse(value['hardware_qualification'])

    def test_pinned_private_input_rejects_changed_bytes_and_symlink(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'input.json'; path.write_bytes(b'{"actual":"CPU-only"}'); path.chmod(0o600)
            pin = h.sha(path.read_bytes())
            self.assertEqual(h.read_pinned(path, pin, private=True), b'{"actual":"CPU-only"}')
            path.write_bytes(b'{"actual":"changed"}')
            with self.assertRaises(ValueError): h.read_pinned(path, pin, private=True)
            link = Path(root) / 'link'; link.symlink_to(path)
            with self.assertRaises(OSError): h.read_pinned(link, pin, private=True)

    def test_duplicate_or_nonfinite_capture_json_rejected(self):
        for raw in ['{"cap":5120,"cap":10240}', '{"used":NaN}']:
            with self.subTest(raw=raw), self.assertRaises(ValueError): h.parse(raw)

class NvmlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('cpu_nvml', HERE / 'capture_nvml.py')
        cls.nvml = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.nvml)

    def lib(self, *, mig=0, wrong_gpu=False, wrong_memory=False, error=False):
        module = self.nvml; calls = []
        def init(): calls.append('init'); return 0
        def shutdown(): calls.append('shutdown'); return 0
        def version(buf, size): buf.value = b'615.34.01'; return 0
        def handle(gpu, out): out._obj.value = 123; return 0
        def uuid(handle, buf, size): buf.value = (b'GPU-foreign' if wrong_gpu else module.GPU.encode()); return 0
        def memory(handle, out):
            out._obj.total = 40 * 1024 ** 3; out._obj.free = 30 * 1024 ** 3; out._obj.used = 10 * 1024 ** 3 + int(wrong_memory)
            return 1 if error else 0
        def modes(handle, current, pending): current._obj.value = mig; pending._obj.value = 0; return 0
        class Function:
            def __init__(self, fn): self.fn = fn
            def __call__(self, *a): return self.fn(*a)
        class Library: pass
        lib = Library()
        for name, fn in [('nvmlInit_v2', init), ('nvmlShutdown', shutdown),
            ('nvmlSystemGetDriverVersion', version), ('nvmlDeviceGetHandleByUUID', handle),
            ('nvmlDeviceGetUUID', uuid), ('nvmlDeviceGetMemoryInfo', memory), ('nvmlDeviceGetMigMode', modes)]:
            setattr(lib, name, Function(fn))
        return lib, calls

    def test_memory_abi_preserves_values_above_four_gib_and_read_only_result(self):
        lib, calls = self.lib(); value = self.nvml.capture(lib)
        self.assertEqual(value['free_bytes'], 32212254720)
        self.assertEqual(value['used_bytes'], 10737418240)
        self.assertTrue(value['read_only']); self.assertFalse(value['hardware_qualification'])
        self.assertFalse(value['driver_generation_verified_by_probe'])
        self.assertEqual(calls, ['init', 'shutdown'])

    def test_wrong_uuid_mig_memory_or_nvml_result_cannot_create_capture(self):
        for args in [dict(mig=1), dict(wrong_gpu=True), dict(wrong_memory=True), dict(error=True)]:
            lib, calls = self.lib(**args)
            with self.subTest(args=args), self.assertRaises(ValueError): self.nvml.capture(lib)
            self.assertEqual(calls, ['init', 'shutdown'])

    def test_nvml_default_is_inert_with_no_library_available(self):
        result = subprocess.run([sys.executable, str(HERE / 'capture_nvml.py')], capture_output=True, text=True,
            env={**os.environ, 'PATH': '/nonexistent'}, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['state'], 'inert')

if __name__ == '__main__': unittest.main()
