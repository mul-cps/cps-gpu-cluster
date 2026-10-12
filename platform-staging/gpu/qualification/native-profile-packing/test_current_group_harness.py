"""Self-contained CPU captures, never hardware evidence or Root's private sources."""
import copy
from dataclasses import replace
import io
import contextlib
import json
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
        pre = ('CONTROLLER_SHA = ' + repr(current.LEGACY_CONTROLLER_SHA256) + '\n').encode()
        protocol = b'kernel-witness-required\nexchange_timeout=120\npayload_mib=64\n'
        rendered = {'run_group_acceptance.py': pre, 'imports-cross-pod/kernel_witness_collector.py': protocol,
                    'vmm-cross-parent-sgid-fix/kernel_witness_transport.py': protocol,
                    'imports-cross-pod/run_cross_pod.py': protocol + old.sha(pre).encode()}
        with patch.object(old, '_render_validated_sources', return_value=copy.deepcopy(rendered)) as render:
            output = current.render_sources({}, b, {'records': []})
        self.assertEqual(render.call_args.args[1], b)
        new_pre = output['run_group_acceptance.py']
        self.assertIn(current.CONTROLLER_SHA256.encode(), new_pre)
        self.assertEqual(output['imports-cross-pod/kernel_witness_collector.py'], protocol)
        self.assertEqual(output['vmm-cross-parent-sgid-fix/kernel_witness_transport.py'], protocol)
        self.assertEqual(output['imports-cross-pod/run_cross_pod.py'], protocol + old.sha(new_pre).encode())
        with self.assertRaises(ValueError):
            with patch.object(old, '_render_validated_sources', return_value={'run_group_acceptance.py': b'changed model span'}):
                current.render_sources({}, b, {'records': []})


if __name__ == '__main__': unittest.main()
