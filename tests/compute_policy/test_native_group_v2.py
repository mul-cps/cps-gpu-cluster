"""Measured group policy compilation; every receipt here is synthetic CPU data."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import test_native_group as legacy

compiler = legacy.compiler


class MeasuredNativeGroupTests(unittest.TestCase):
    def fixture(self, root, sizes=(5, 10)):
        catalog, proof, paths = legacy.NativeGroupTests().fixture(root)
        proof.update(version=2, profile_caps={f'interactive-shared-{s}': s * 1024 for s in sizes})
        proof['node_pool'].update(total_memory_mib=40960, free_memory_mib=40470,
            headroom_mib=1024, memory_budget_mib=30720,
            boot_id='209f8bc9-a478-48e4-925a-6e07ffa56f7a',
            driver_generation='b10498fc-9153-4394-875a-ea7cfb498625')
        for size in sizes:
            p = copy.deepcopy(catalog['profiles']['interactive-shared-5'])
            p['gpu']['nominalMemoryGiB'] = size
            p['gpu']['qualification']['evidence'] = ['native-groups-v2']
            catalog['profiles'][f'interactive-shared-{size}'] = p
        self.rebind(catalog, proof, paths, root)
        return catalog, proof, paths

    def rebind(self, catalog, proof, paths, root):
        digest = 'sha256:' + hashlib.sha256(compiler.canonical(catalog)).hexdigest()
        proof['policy_hash'] = digest
        for gate in (*compiler.NATIVE_GROUP_GATES, 'capacity'):
            path = Path(root) / (gate + '.json')
            path.write_text(json.dumps({'gate': gate, 'passed': True, 'policy_hash': digest,
                'policy_version': catalog['version'], 'synthetic_cpu_test_only': True}))
            path.chmod(0o600)
            paths[gate] = path
            checksum = 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
            if gate == 'capacity':
                proof['capacity_evidence_sha256'] = checksum
            else:
                proof['gates'][gate]['evidence_sha256'] = checksum

    def compile(self, c, p, a):
        return compiler.compile_catalog(c, native_group_evidence=p, native_group_artifacts=a)

    def test_measured_5_10_and_20_profiles_compile_without_changing_inputs(self):
        for sizes in [(5, 10), (5, 10, 20), (10,), (20,)]:
            with self.subTest(sizes=sizes), tempfile.TemporaryDirectory() as root:
                c, p, a = self.fixture(root, sizes)
                # Do not enable a profile that is absent from the proof.
                if 5 not in sizes:
                    c['profiles']['interactive-shared-5']['enabled'] = False
                    c['profiles']['interactive-shared-5']['gpu']['fraction'] = '0.125'
                    self.rebind(c, p, a, root)
                original = copy.deepcopy(c)
                result = self.compile(c, p, a)
                self.assertEqual(result['policyHash'], p['policy_hash'])
                self.assertEqual(c, original)

    def test_pool_and_caps_must_match_the_measured_budget(self):
        changes = [
            ('headroom_mib', 0), ('memory_budget_mib', 40470),
            ('free_memory_mib', 40961), ('max_workspaces', True),
            ('max_workspaces', 33), ('boot_id', 'invalid'),
            ('driver_generation', '00000000-0000-0000-0000-000000000000'),
            ('node', 'k3s-wk-gpu1'), ('total_memory_mib', 81920),
        ]
        for key, value in changes:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as root:
                c, p, a = self.fixture(root)
                p['node_pool'][key] = value
                with self.assertRaises(ValueError):
                    self.compile(c, p, a)
        for caps in [{}, {'interactive-shared-10': 5120}, {'interactive-shared-40': 40960},
                     {'interactive-shared-5': True}, {'interactive-shared-20': 20480}]:
            with self.subTest(caps=caps), tempfile.TemporaryDirectory() as root:
                c, p, a = self.fixture(root)
                p['node_pool']['memory_budget_mib'] = 15360
                p['profile_caps'] = caps
                with self.assertRaises(ValueError):
                    self.compile(c, p, a)

    def test_profiles_outside_the_exact_proof_stay_disabled(self):
        with tempfile.TemporaryDirectory() as root:
            c, p, a = self.fixture(root)
            c['profiles']['interactive-shared-20']['enabled'] = True
            self.rebind(c, p, a, root)
            with self.assertRaises(ValueError):
                self.compile(c, p, a)

    def test_capacity_requires_a_private_checksummed_target_policy_receipt(self):
        for fault in ['missing', 'tampered', 'public', 'wrong-target', 'wrong-version', 'zero', 'extra']:
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as root:
                c, p, a = self.fixture(root)
                path = a['capacity']
                if fault == 'missing': a.pop('capacity')
                elif fault == 'tampered': path.write_text('{}')
                elif fault == 'public': path.chmod(0o644)
                elif fault == 'zero': p['capacity_evidence_sha256'] = 'sha256:' + '0' * 64
                elif fault == 'extra': a['unreviewed'] = path
                else:
                    report = json.loads(path.read_text())
                    report['policy_hash' if fault == 'wrong-target' else 'policy_version'] = 'wrong'
                    path.write_text(json.dumps(report))
                    p['capacity_evidence_sha256'] = 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
                with self.assertRaises(ValueError):
                    self.compile(c, p, a)
