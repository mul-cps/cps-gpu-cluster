"""Self-contained CPU captures, never hardware evidence or Root's private sources."""
import copy
import ast
from dataclasses import replace
import io
import contextlib
import json
import stat
import os
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cps_compute.native_gpu_controller import CapIdentity, CapIntent, CapLimit, CapRecord, RetiredCapEntry, RetiredInertCap
from cps_compute.native_gpu_runtime import SPEC_ANNOTATION, native_spec_sha256
from cps_compute.native_groups import canonical_sha256
from cps_compute.policy import Policy
import prepare_harness as old
import prepare_current_group_harness as current
from test_prepare_harness import binding

HERE = Path(__file__).parent
PUBLISHED = HERE.parents[1] / 'native-group-pilot/qualification/limited-group-20261012/native-groups.json'


class CurrentGroupTests(unittest.TestCase):
    def test_vmm_stage_check_precedes_endpoints_and_rejects_missing_or_changed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); root.chmod(0o700)
            bridge = root / 'vmm_bridge.py'; endpoint = root / 'vmm_endpoint.py'
            bridge.write_bytes(b'trusted bridge'); endpoint.write_bytes(b'trusted endpoint')
            bridge.chmod(0o400); endpoint.chmod(0o400)
            sessions = root / 'bridge-sessions'; sessions.mkdir(mode=0o700)
            pins = {'vmm_bridge.py': old.sha(bridge.read_bytes()), 'vmm_endpoint.py': old.sha(endpoint.read_bytes())}
            source = current.vmm_stage_source(str(root), pins, binding()['pool'])
            tree = ast.parse(source); tree.body = [n for n in tree.body if not isinstance(n, ast.Expr)]
            scope = {}; exec(compile(tree, 'read-only-staging-check', 'exec'), scope)
            actual_fstat, actual_stat = os.fstat, os.stat
            def root_metadata(info):
                return SimpleNamespace(**{k: (0 if k in ('st_uid', 'st_gid') else getattr(info, k))
                    for k in ('st_uid', 'st_gid', 'st_mode', 'st_nlink', 'st_size', 'st_dev', 'st_ino', 'st_mtime_ns', 'st_ctime_ns')})
            def check():
                with patch.object(os, 'fstat', side_effect=lambda fd: root_metadata(actual_fstat(fd))), \
                     patch.object(os, 'stat', side_effect=lambda *a, **kw: root_metadata(actual_stat(*a, **kw))):
                    return scope['verify_staged']()
            self.assertEqual(check()['state'], 'exact-vmm-bridge-staged')
            for target in (bridge, endpoint):
                target.unlink()
                with self.assertRaises(FileNotFoundError): check()
                target.write_bytes(b'trusted bridge' if target == bridge else b'trusted endpoint'); target.chmod(0o400)
                target.chmod(0o600)
                with self.assertRaises(ValueError): check()
                target.chmod(0o400); target.chmod(0o600); target.write_bytes(b'changed'); target.chmod(0o400)
                with self.assertRaises(ValueError): check()
                target.chmod(0o600); target.write_bytes(b'trusted bridge' if target == bridge else b'trusted endpoint'); target.chmod(0o400)
            sessions.chmod(0o755)
            with self.assertRaises(ValueError): check()
            root.chmod(0o755)
            with self.assertRaises(ValueError): check()

    def test_cleared_guard_rechecks_exact_inventory_and_bounded_live_inode_absence(self):
        row = {'cgroup_id': 1390814, 'kernfs_id': 1390814, 'inode': 1390814, 'offline': True,
               'pinned': True, 'default_hierarchy': True, 'soft': 0, 'hard': 2**64-1, 'used': 0}
        code = current.cleared_guard([row], 9, 0) + "\nrequire(set(rows)==bound,'Unbound/orphan native inventory entry blocks probes')"
        def observe(actual, *, live_inode=999, directories=1, gpu_id=0, device=9, link=False, slow=False):
            def require(ok, message):
                if not ok: raise ValueError(message)
            fake_os = SimpleNamespace(stat=lambda path, **kw: SimpleNamespace(
                st_mode=stat.S_IFLNK if path.endswith('/link') else stat.S_IFDIR,
                st_dev=device, st_ino=live_inode), path=SimpleNamespace(join=lambda *p: '/'.join(p)),
                walk=lambda *a, **kw: iter([('/sys/fs/cgroup', ['link'] if link else [], [])] * directories))
            ticks = iter([0, 11]) if slow else None
            namespace = {'rows': copy.deepcopy(actual), 'bound': set(), 'inventory': {'gpu_id': gpu_id},
                         'os': fake_os, 'stat': stat, 'time': SimpleNamespace(monotonic=lambda: next(ticks) if ticks else 0),
                         'require': require}
            exec(compile(code, 'strict-cleared-guard', 'exec'), namespace)
            return namespace['bound']
        self.assertEqual(observe({row['inode']: row}), {row['inode']})
        for field, value in [('soft', 5120*1048576), ('hard', 5120*1048576), ('used', 1),
                             ('offline', False), ('pinned', False), ('default_hierarchy', False)]:
            bad = dict(row); bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): observe({row['inode']: bad})
        for kwargs in ({'live_inode': row['inode']}, {'directories': 4097}, {'gpu_id': 1},
                       {'device': 10}, {'link': True}, {'slow': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): observe({row['inode']: row}, **kwargs)
        unknown = dict(row, inode=123, cgroup_id=123, kernfs_id=123)
        with self.assertRaises(ValueError): observe({row['inode']: row, 123: unknown})
        with self.assertRaises(ValueError): observe({})

    def test_real_thirteen_cleared_rows_require_exact_offline_zero_unbounded_form(self):
        inodes = [1403936, 1404312, 1404391, 1403778, 1403857, 1404075, 1404154,
                  1404549, 1404470, 1404233, 1405847, 1405768, 1390814]
        rows = [{'cgroup_id': n, 'kernfs_id': n, 'inode': n, 'offline': True,
                 'pinned': True, 'default_hierarchy': True, 'soft': 0, 'hard': 2**64-1, 'used': 0}
                for n in inodes]
        pool = binding()['pool']
        inventory = {'version': 1, 'backend': 'misc-fallback', 'gpu_uuid': pool['gpu_uuid'],
                     'gpu_id': 0, 'entries': rows}
        self.assertEqual(current.validate_cleared_inventory(inventory, pool, set()), sorted(rows, key=lambda r: r['inode']))
        for field, value in [('soft', 5120*1048576), ('hard', 5120*1048576), ('used', 1),
                             ('offline', False), ('pinned', False), ('default_hierarchy', False),
                             ('inode', rows[1]['inode']), ('cgroup_id', 1)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                bad = copy.deepcopy(inventory); bad['entries'][0][field] = value
                current.validate_cleared_inventory(bad, pool, set())

    def fixture(self, root):
        root.chmod(0o700)
        def pin(name, value):
            path = root / name
            raw = (old.canonical(value) + '\n').encode()
            path.write_bytes(raw); path.chmod(0o600)
            return {'path': str(path), 'sha256': old.sha(raw)}
        config = json.loads(PUBLISHED.read_text())
        catalog = {'version': '0.1.1', 'labels': {}, 'workloadScheduling': {
            'interactive': {'queue': 'cps-interactive', 'priorityClassName': 'cps-homework'},
            'batch': {'queue': 'cps-batch', 'priorityClassName': 'cps-batch'}},
            'priorities': {'homework': 40}, 'profiles': {}}
        for profile, cap in config['evidence']['profile_caps'].items():
            catalog['profiles'][profile] = {'enabled': True, 'kind': 'interactive', 'queue': 'interactive',
                'cpu': '4', 'memory': '16Gi', 'images': [config['workloadImage']],
                'gpu': {'mode': 'shared', 'nominalMemoryGiB': cap // 1024, 'qualification': {
                    'mechanism': 'r615-native-cgroup-managed-deny', 'status': 'qualified-group',
                    'policyVersion': catalog['version'], 'evidence': ['native-groups-v2']}}}
        policy = Policy(catalog)
        config['policy_hash'] = config['evidence']['policy_hash'] = policy.hash
        config['evidence_sha256'] = canonical_sha256(config['evidence'])
        b = binding(); b['policy_hash'] = policy.hash
        journals = []
        for i, target in enumerate(b['targets']):
            target['profile'] = 'interactive-shared-' + str(target['cap_mib'] // 1024)
            pod = {'metadata': {k: target[k] for k in ('namespace', 'name')},
                'spec': {'nodeName': b['pool']['node'], 'containers': [{'name': 'notebook',
                    'image': config['workloadImage']}]}}
            pod['metadata']['uid'] = target['pod_uid']
            target['spec_sha256'] = native_spec_sha256(pod)
            pod['metadata']['annotations'] = {SPEC_ANNOTATION: target['spec_sha256']}
            target['pod_capture'] = pin('pod-' + str(i) + '.json', pod)
            intent = CapIntent(**{k: target[k] for k in ('namespace', 'name', 'pod_uid',
                'spec_sha256', 'cap_mib')}, **{k: b['pool'][k] for k in ('node', 'node_uid', 'gpu_uuid')},
                policy_hash=policy.hash)
            relative = '/kubepods.slice/kubepods-pod' + target['pod_uid'].replace('-', '_') + '.slice'
            identity = CapIdentity(target['pod_uid'], target['spec_sha256'], b['pool']['node_uid'],
                b['pool']['gpu_uuid'], str(i + 4) * 64, 100 + i, 200 + i, b['pool']['boot_id'],
                relative, '/sys/fs/cgroup' + relative, 1, 300 + i, b['pool']['driver_generation'])
            record = CapRecord(intent, identity, 'sealed', '00000000-0000-4000-8000-00000000000' + str(i + 4),
                CapLimit(intent.cap_bytes, intent.cap_bytes))
            journals.append({'pod_uid': target['pod_uid'], 'journal': pin('journal-' + str(i) + '.json', record.to_dict()),
                'gate_receipt': pin('gate-' + str(i) + '.json', record.receipt())})
        manifest = {'version': 1, 'state': 'Root-reviewed-current-group-plan',
            'binding': pin('binding.json', b), 'policy': pin('policy.json', catalog),
            'native_groups': pin('groups.json', config), 'sealed_targets': journals}
        return manifest, b, config, pin

    def test_exact_current_groups_require_policy_deployment_pods_and_both_seals(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, b, _, _ = self.fixture(Path(tmp))
            actual, inputs = current.validate_inputs(manifest)
            self.assertEqual(actual, b)
            self.assertEqual(inputs['preparation_mode'], 'current-approved-groups')
            self.assertFalse(inputs['fresh_cross_pod_hardware_qualified'])
            with self.assertRaises(ValueError): old.validate_binding(b)

    def test_retired_qualification_mode_keeps_its_original_profile_contract(self):
        self.assertEqual(old.validate_binding(binding()), binding())
        with tempfile.TemporaryDirectory() as tmp:
            manifest, b, _, pin = self.fixture(Path(tmp))
            b['targets'][0]['profile'] = 'interactive-native-qualification-5'
            manifest['binding'] = pin('retired-profile.json', b)
            with self.assertRaises(ValueError): current.validate_inputs(manifest)

    def test_disabled_missing_rehashed_broadened_or_wrong_approval_is_rejected(self):
        for change in ('disabled', 'no-gates', 'foreign-workspace', 'more-profiles', 'member', 'pod', 'budget', 'slots'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                manifest, _, config, pin = self.fixture(Path(tmp))
                if change == 'disabled': config = {'enabled': False}
                elif change == 'no-gates': config['evidence']['gates']['memory-import']['passed'] = False
                elif change == 'foreign-workspace': config['workspaces']['cps:foreign'] = copy.deepcopy(config['workspaces']['cps:native-group-b'])
                elif change == 'more-profiles': config['evidence']['profile_caps']['interactive-shared-20'] = 20480
                elif change == 'member': config['workspaces']['cps:native-group-b']['members'][0] = 'another-person'
                elif change == 'pod': config['workspaces']['cps:native-group-b']['pod'] = 'forged-pod'
                elif change == 'budget': config['node_pool']['memory_budget_mib'] = 20480
                elif change == 'slots': config['node_pool']['max_workspaces'] = 3
                if 'evidence' in config:
                    config['evidence']['node_pool'] = copy.deepcopy(config['node_pool'])
                    config['evidence_sha256'] = canonical_sha256(config['evidence'])
                manifest['native_groups'] = pin('changed-groups.json', config)
                with self.assertRaises(ValueError): current.validate_inputs(manifest)

    def test_forged_profile_scope_caps_or_swapped_actual_pod_rejected(self):
        for field, value in [('profile', 'interactive-shared-20'), ('cap_mib', 20480),
                             ('profile', 'interactive-shared-10'), ('workspace', 'another-group')]:
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as tmp:
                manifest, b, _, pin = self.fixture(Path(tmp))
                b['targets'][0][field] = value
                manifest['binding'] = pin('changed-binding.json', b)
                with self.assertRaises(ValueError): current.validate_inputs(manifest)

    def test_unsealed_wrong_epoch_foreign_uid_cap_or_gate_rejected_even_rehashed(self):
        for change in ('missing', 'unsealed', 'cap', 'policy', 'epoch', 'uid', 'gate', 'pod-spec'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                manifest, b, _, pin = self.fixture(Path(tmp))
                entry = manifest['sealed_targets'][0]
                record = CapRecord.from_dict(json.loads(Path(entry['journal']['path']).read_text()))
                if change == 'missing': manifest['sealed_targets'].pop()
                elif change == 'unsealed': record = replace(record, state='applied')
                elif change == 'cap':
                    intent = replace(record.intent, cap_mib=10240)
                    record = replace(record, intent=intent, readback=CapLimit(intent.cap_bytes, intent.cap_bytes))
                elif change == 'policy': record = replace(record, intent=replace(record.intent, policy_hash='sha256:' + 'c' * 64))
                elif change == 'epoch': record = replace(record, identity=replace(record.identity, driver_generation='00000000-0000-4000-8000-000000000008'))
                elif change == 'uid': entry['pod_uid'] = b['targets'][1]['pod_uid']
                elif change == 'gate': entry['gate_receipt'] = manifest['sealed_targets'][1]['gate_receipt']
                elif change == 'pod-spec':
                    pod = json.loads(Path(b['targets'][0]['pod_capture']['path']).read_text())
                    pod['spec']['containers'][0]['image'] = 'forged'
                    b['targets'][0]['pod_capture'] = pin('changed-pod.json', pod)
                    manifest['binding'] = pin('changed-binding.json', b)
                if change in ('unsealed', 'cap', 'policy', 'epoch'):
                    entry['journal'] = pin('changed-journal.json', record.to_dict())
                    entry['gate_receipt'] = pin('changed-gate.json', record.receipt())
                with self.assertRaises(ValueError): current.validate_inputs(manifest)

    def test_default_is_inert_and_prepare_forwards_canonical_bindings_without_relabeling(self):
        with patch.object(current, 'validate_inputs', side_effect=AssertionError('unexpected input read')):
            with contextlib.redirect_stdout(io.StringIO()) as stream: current.main([])
            self.assertEqual(json.loads(stream.getvalue())['state'], 'inert')
        with tempfile.TemporaryDirectory() as tmp:
            manifest, b, _, pin = self.fixture(Path(tmp))
            manifest_pin = pin('manifest.json', manifest)
            with patch.object(old, '_prepare_validated_binding', return_value={'state': 'prepared'}) as prepare:
                current.prepare(Path(manifest_pin['path']), manifest_pin['sha256'], Path(tmp), Path(tmp) / 'out')
            self.assertEqual(prepare.call_args.args[0], b)
            self.assertEqual(prepare.call_args.kwargs['receipt_context']['preparation_mode'], 'current-approved-groups')

    def test_current_retirement_requires_current_model_and_exact_original_finite_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, b, _, _ = self.fixture(Path(tmp))
            record = CapRecord.from_dict(json.loads(Path(manifest['sealed_targets'][0]['journal']['path']).read_text()))
            uid = '00000000-0000-4000-8000-000000000009'
            relative = '/kubepods.slice/kubepods-pod' + uid.replace('-', '_') + '.slice'
            identity = replace(record.identity, pod_uid=uid, cgroup_relative=relative,
                cgroup_path='/sys/fs/cgroup' + relative, cgroup_inode=401)
            entry = RetiredCapEntry(401, 401, 401, True, True, True, record.limit.soft, record.limit.hard, 0)
            proof = RetiredInertCap(identity, identity.epoch, 0, 'sha256:' + '9' * 64, entry)
            retired = replace(record, intent=replace(record.intent, pod_uid=uid), identity=identity,
                              state='retired-inert-cap', retirement=proof)
            capture = {'version': 1, **{k: b['pool'][k] for k in
                ('node', 'node_uid', 'boot_id', 'gpu_uuid', 'driver_generation')},
                'controller_sha256': current.CONTROLLER_SHA256,
                'records': [{'pod_uid': uid, 'journal_sha256': 'sha256:' + old.sha(old.canonical(retired.to_dict()).encode()),
                             'record': retired.to_dict()}]}
            self.assertEqual(current.validate_retired(capture, b), capture)
            with self.assertRaises(ValueError): old.validate_retired(capture, b)
            capture['controller_sha256'] = current.LEGACY_CONTROLLER_SHA256
            with self.assertRaises(ValueError): current.validate_retired(capture, b)

    def test_render_adapter_keeps_protocol_witness_and_deadline_bytes_and_repins_preflight(self):
        b = binding()
        for target in b['targets']: target['profile'] = 'interactive-shared-' + str(target['cap_mib'] // 1024)
        legacy_path = '/run/cps-native-gpu/driver-inputs-optional-stack/native_gpu_controller.py'
        current_path = '/run/cps-native-gpu/qualification-current-controller-630d43cc/native_gpu_controller.py'
        host = ("source=read(" + repr(legacy_path) + ",0o400)\n"
                "require(hashlib.sha256(source).hexdigest()==c['controller_sha256']==" +
                repr(current.LEGACY_CONTROLLER_SHA256) + ", 'Current production journal validator required')\n")
        pre = ('CONTROLLER_SHA = ' + repr(current.LEGACY_CONTROLLER_SHA256) + '\nHOST_SOURCE = ' + repr(host) + '\n').encode()
        protocol = b'kernel-witness-required\nexchange_timeout=120\npayload_mib=64\n'
        rendered = {'run_group_acceptance.py': pre, 'imports-cross-pod/kernel_witness_collector.py': protocol,
                    'vmm-cross-parent-sgid-fix/kernel_witness_transport.py': protocol,
                    'imports-cross-pod/run_cross_pod.py': protocol + old.sha(pre).encode() + b'\n' + old.sha(host.encode()).encode(),
                    'vmm-cross-parent-sgid-fix/run_vmm_cross_parent.py': b"BRIDGE_ROOT='/run/cps-native-gpu/operator/reviewed-vmm-test'\ndef main(argv=None):\n    transport=load_witness()\n    exporter=Session()\n",
                    'vmm-cross-parent-sgid-fix/vmm_bridge.py': b'trusted-bridge',
                    'vmm-cross-parent-sgid-fix/vmm_endpoint.py': b'trusted-endpoint'}
        with patch.object(old, '_render_validated_sources', return_value=copy.deepcopy(rendered)) as render:
            output = current.render_sources({}, b, {'records': []})
        self.assertEqual(render.call_args.args[1], b)
        new_pre = output['run_group_acceptance.py']
        self.assertIn(current.CONTROLLER_SHA256.encode(), new_pre)
        new_host = ast.literal_eval(next(n.value for n in ast.parse(new_pre).body
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'HOST_SOURCE' for t in n.targets)))
        self.assertEqual(new_host, host.replace(legacy_path, current_path).replace(
            current.LEGACY_CONTROLLER_SHA256, current.CONTROLLER_SHA256))
        self.assertNotIn(legacy_path, new_host)
        self.assertNotIn(current.LEGACY_CONTROLLER_SHA256, new_host)
        self.assertIn("0o400", new_host)
        self.assertEqual(rendered['run_group_acceptance.py'], pre)
        self.assertEqual(output['imports-cross-pod/kernel_witness_collector.py'], protocol)
        self.assertEqual(output['vmm-cross-parent-sgid-fix/kernel_witness_transport.py'], protocol)
        self.assertEqual(output['imports-cross-pod/run_cross_pod.py'],
            protocol + old.sha(new_pre).encode() + b'\n' + old.sha(new_host.encode()).encode())
        wrapper = output['vmm-cross-parent-sgid-fix/run_vmm_cross_parent.py'].decode()
        self.assertLess(wrapper.index('    check_vmm_staging(h,args)'), wrapper.index('    exporter=Session()'))
        prerequisite = json.loads(output['vmm-cross-parent-sgid-fix/bridge-prerequisite.json'])
        self.assertTrue(prerequisite['required_before_endpoint_launch'])
        self.assertEqual(prerequisite['files']['vmm_bridge.py']['sha256'], old.sha(b'trusted-bridge'))
        self.assertEqual(prerequisite['files']['vmm_endpoint.py']['sha256'], old.sha(b'trusted-endpoint'))
        self.assertEqual(output['vmm-cross-parent-sgid-fix/vmm_bridge.py'], b'trusted-bridge')
        with self.assertRaises(ValueError):
            with patch.object(old, '_render_validated_sources', return_value={'run_group_acceptance.py': b'changed model span'}):
                current.render_sources({}, b, {'records': []})
        for changed in (host.replace(legacy_path, '/unreviewed/controller.py'),
                        host.replace(current.LEGACY_CONTROLLER_SHA256, '0' * 64)):
            with self.subTest(unreviewed_host=changed), self.assertRaises(ValueError):
                bad_pre = ('CONTROLLER_SHA = ' + repr(current.LEGACY_CONTROLLER_SHA256) +
                           '\nHOST_SOURCE = ' + repr(changed) + '\n').encode()
                with patch.object(old, '_render_validated_sources', return_value={'run_group_acceptance.py': bad_pre}):
                    current.render_sources({}, b, {'records': []})


if __name__ == '__main__': unittest.main()
