"""CPU-only policy revision; all GPU receipts in these tests are synthetic."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_native_group_v2 as native

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'scripts/compute-platform/prepare_cpu_runner_policy.py'
SOURCE = ROOT / 'platform-staging/gpu/native-group-pilot/qualification/limited-group-20261012'
IMAGE = 'ghcr.io/mul-cps/cps-jupyter-notebook@sha256:1fab06639346f69e96cda6c8f551d761cc51c47de85cdc0ec42ef31bf2ef2c7f'


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


class CpuRunnerPolicyTests(unittest.TestCase):
    def load(self):
        self.assertTrue(MODULE.is_file(), 'CPU-only policy preparer must exist')
        spec = importlib.util.spec_from_file_location('cpu_runner_policy', MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def fixture(self, directory):
        ready = directory / 'ready'; ready.mkdir()
        catalog, proof, paths = native.MeasuredNativeGroupTests().fixture(ready)
        groups = json.loads((SOURCE / 'native-groups.json').read_text())
        groups.update(policy_hash=proof['policy_hash'], evidence=proof, node_pool=proof['node_pool'])
        groups['evidence_sha256'] = 'sha256:' + hashlib.sha256(native.compiler.canonical(proof)).hexdigest()
        inputs = {'catalog.json': catalog, 'native-group-evidence.json': proof, 'native-groups.json': groups}
        for source in ('cps', 'cit'):
            settings = json.loads((SOURCE / (source + '-settings.json')).read_text())
            settings['groupDeployment'] = groups
            inputs[source + '-settings.json'] = settings
            key = next(k for k in groups['workspaces'] if k.startswith(source + ':'))
            registration = copy.deepcopy(groups['workspaces'][key]); registration.pop('storage')
            registration.update(workspace=key.split(':', 1)[1], policy_hash=proof['policy_hash'])
            inputs[source + '-workspace-registration.json'] = registration
        node = {'policy_hash': proof['policy_hash'], 'pool': proof['node_pool'],
            'workspaces': {}, 'terminal_history': {'original': {'policy_hash': 'old-policy'}}}
        inputs['node-config.json'] = node
        for gate, path in paths.items():
            inputs['attestation-' + gate + '.json'] = json.loads(path.read_text())
            digest = 'sha256:' + hashlib.sha256(encoded(inputs['attestation-' + gate + '.json'])).hexdigest()
            if gate == 'capacity': proof['capacity_evidence_sha256'] = digest
            else: proof['gates'][gate]['evidence_sha256'] = digest
        groups['evidence_sha256'] = 'sha256:' + hashlib.sha256(native.compiler.canonical(proof)).hexdigest()
        for name, value in inputs.items():
            (ready / name).write_bytes(encoded(value)); (ready / name).chmod(0o600)
        current = copy.deepcopy(node)
        current['terminal_history']['later'] = {'policy_hash': 'historical-policy', 'state': 'released'}
        node_path = directory / 'current.json'; node_path.write_bytes(encoded({'config.json': encoded(current).decode()}))
        receipt = {'schema': 'cps-cpu-runner-local-qualification-v1', 'image': IMAGE,
            'uid': 10001, 'gid': 100, 'working_directory': '/tmp', 'input_immutable': True,
            'outputs_stripped': True, 'gpu_calls': False, 'network': 'none', 'fresh_kernel': True,
            'success': {'exit_code': 0, 'executed_notebook_retained': True,
                'selected_local_import_passed': True, 'parameters': {'count': 3, 'fail': False}},
            'failure': {'exit_code': 1, 'executed_notebook_retained': True,
                'parameters': {'count': 3, 'fail': True}}}
        receipt_path = directory / 'cpu.json'; receipt_path.write_bytes(encoded(receipt))
        record = {'schema': 'cps-cpu-runner-policy-revision-v1', 'version': '0.1.2', 'runner_image': IMAGE,
            'baseline_policy_hash': proof['policy_hash'],
            'inputs': {name: hashlib.sha256((ready / name).read_bytes()).hexdigest() for name in inputs},
            'cpu_receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
            'current_node_config_sha256': hashlib.sha256(node_path.read_bytes()).hexdigest()}
        record_path = directory / 'record.json'; record_path.write_bytes(encoded(record))
        return ready, node_path, receipt_path, record_path, inputs, current

    def test_default_cli_is_inert(self):
        self.load()
        result = subprocess.run([sys.executable, str(MODULE)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'rendered': False, 'activationPerformed': False})

    def test_revision_enables_only_cpu_runner_and_preserves_all_current_history(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            ready, node, receipt, record, before, current = self.fixture(directory)
            original_bytes = {p.name: p.read_bytes() for p in ready.iterdir()}
            output = directory / 'revision'
            result = module.prepare(ready, node, receipt, output, record)
            self.assertFalse(result['activationPerformed'])
            catalog = json.loads((output / 'catalog.json').read_text())
            policy = json.loads((output / 'compiled/policy.json').read_text())
            self.assertEqual(catalog['version'], '0.1.2')
            self.assertEqual(catalog['profiles']['batch-cpu']['images'], [IMAGE])
            self.assertFalse(catalog['gpuQualification']['qualified'])
            normalized = copy.deepcopy(catalog)
            normalized['version'] = before['catalog.json']['version']
            normalized['approvedImages'].remove(IMAGE)
            normalized['profiles']['batch-cpu']['images'] = []
            for name in before['native-group-evidence.json']['profile_caps']:
                normalized['profiles'][name]['gpu']['qualification']['policyVersion'] = before['catalog.json']['version']
            self.assertEqual(normalized, before['catalog.json'])
            updated_node = json.loads((output / 'node-config.json').read_text())
            self.assertEqual(updated_node['terminal_history'], current['terminal_history'])
            updated_node['policy_hash'] = current['policy_hash']
            self.assertEqual(updated_node, current)
            for source in ('cps', 'cit'):
                registration = json.loads((output / (source + '-workspace-registration.json')).read_text())
                registration['policy_hash'] = before[source + '-workspace-registration.json']['policy_hash']
                self.assertEqual(registration, before[source + '-workspace-registration.json'])
            self.assertEqual({p.name: p.read_bytes() for p in ready.iterdir()}, original_bytes)
            for gate in (*native.compiler.NATIVE_GROUP_GATES, 'capacity'):
                derived = json.loads((output / ('compatibility/attestation-' + gate + '.json')).read_text())
                self.assertFalse(derived['hardware_test_performed'])
                self.assertEqual(derived['qualification_kind'], 'cpu-runner-policy-compatibility')
                self.assertEqual(derived['policy_hash'], policy['policyHash'])
                self.assertEqual(derived['original_report_sha256'],
                    hashlib.sha256(original_bytes['attestation-' + gate + '.json']).hexdigest())
            acceptance = json.loads((output / 'acceptance.json').read_text())
            self.assertTrue(acceptance['cpu_runner_locally_qualified'])
            self.assertFalse(acceptance['cluster_notebook_execution_qualified'])
            self.assertFalse(acceptance['production_qualified'])
            self.assertEqual(json.loads((output / 'compiled/release-lock.json').read_text())['status'], 'unqualified')
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in output.rglob('*') if p.is_file()))

    def test_changed_sources_fail_before_output_creation(self):
        module = self.load()
        for name in ('catalog.json', 'attestation-capacity.json', 'cps-settings.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                ready, node, receipt, record, _, _ = self.fixture(directory)
                (ready / name).write_bytes((ready / name).read_bytes() + b' ')
                output = directory / 'revision'
                with self.assertRaisesRegex(ValueError, 'changed reviewed source bytes'):
                    module.prepare(ready, node, receipt, output, record)
                self.assertFalse(output.exists())

    def test_rejects_wrong_uid_receipt_and_changed_current_authority(self):
        module = self.load()
        for fault in ('uid', 'authority', 'receipt-pin'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                ready, node, receipt, record, _, _ = self.fixture(directory)
                pins = json.loads(record.read_text())
                if fault.startswith('receipt') or fault == 'uid':
                    value = json.loads(receipt.read_text()); value['uid'] = 1000
                    receipt.write_bytes(encoded(value))
                    if fault == 'uid': pins['cpu_receipt_sha256'] = hashlib.sha256(receipt.read_bytes()).hexdigest()
                else:
                    value = json.loads(node.read_text()); config = json.loads(value['config.json'])
                    config['pool']['memory_budget_mib'] += 1024
                    value['config.json'] = encoded(config).decode(); node.write_bytes(encoded(value))
                    pins['current_node_config_sha256'] = hashlib.sha256(node.read_bytes()).hexdigest()
                record.write_bytes(encoded(pins)); output = directory / 'revision'
                with self.assertRaises(ValueError):
                    module.prepare(ready, node, receipt, output, record)
                self.assertFalse(output.exists())

    def test_admission_delta_preserves_every_existing_parameter_and_executor(self):
        module = self.load()
        executor = 'registry.invalid/executor@sha256:' + '2' * 64
        existing = {'approved-images': executor, 'executor-image': executor,
            'artifact-secret': 'artifact-ref', 'artifact-ca-secret': 'ca-ref', 'opaque': 'keep'}
        original = copy.deepcopy(existing)
        updated = module.admission_parameters(existing, IMAGE)
        self.assertEqual(updated['approved-images'], executor + ',' + IMAGE)
        updated['approved-images'] = executor
        self.assertEqual(updated, original)
        self.assertEqual(existing, original)
        allowed = copy.deepcopy(original); allowed['approved-images'] += ',' + IMAGE
        self.assertEqual(module.admission_parameters(allowed, IMAGE), allowed)
        with self.assertRaisesRegex(ValueError, 'executor'):
            module.admission_parameters({'approved-images': '', 'executor-image': executor}, IMAGE)

    def test_preparation_binds_pinned_admission_snapshot(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            ready, node, receipt, record, _, _ = self.fixture(directory)
            executor = 'registry.invalid/executor@sha256:' + '2' * 64
            admission = directory / 'admission.json'
            admission.write_bytes(encoded({'approved-images': executor, 'executor-image': executor,
                'artifact-secret': 'existing-artifact', 'artifact-ca-secret': 'existing-ca'}))
            pins = json.loads(record.read_text())
            pins['admission_data_sha256'] = hashlib.sha256(admission.read_bytes()).hexdigest()
            record.write_bytes(encoded(pins)); output = directory / 'revision'
            with self.assertRaisesRegex(ValueError, 'pinned current ComputeAdmissionPolicy'):
                module.prepare(ready, node, receipt, output, record)
            self.assertFalse(output.exists())
            module.prepare(ready, node, receipt, output, record, admission)
            requirements = json.loads((output / 'admission-requirements.json').read_text())
            self.assertEqual(requirements['kind'], 'ComputeAdmissionPolicy')
            self.assertEqual(requirements['changed_keys'], ['approved-images'])
            self.assertTrue(requirements['server_dry_run_required'])
            expected = json.loads(admission.read_text()); expected['approved-images'] += ',' + IMAGE
            self.assertEqual(json.loads((output / 'admission-data.json').read_text()), expected)
