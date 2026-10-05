import copy
import importlib.util
import json
from pathlib import Path
import unittest
import tempfile
import hashlib

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('policy', ROOT / 'scripts/compile_compute_policy.py')
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)

class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'compute-policy/catalog.json').read_text())

    def test_workload_scheduling_matches_generated_queues_and_priorities(self):
        compiled=policy.compile_catalog(self.catalog)
        objects=policy.manifests(compiled)['items']
        queues={o['metadata']['name'] for o in objects if o['kind']=='Queue'}
        priorities={o['metadata']['name']:o['value'] for o in objects if o['kind']=='PriorityClass'}
        expected={'interactive':('cps-interactive','cps-homework',40),'batch':('cps-batch','cps-batch',10)}
        for kind,(queue,priority,value) in expected.items():
            self.assertEqual(compiled['workloadScheduling'][kind],{'queue':queue,'priorityClassName':priority})
            self.assertIn(queue,queues);self.assertEqual(priorities[priority],value)
            self.assertTrue(all(p['queue']==kind for p in compiled['profiles'].values() if p['kind']==kind))

    def test_reject_missing_unknown_or_elevated_workload_scheduling(self):
        for mutation in ('absent','unknown','elevated','queue','profile-kind','profile-queue'):
            with self.subTest(mutation=mutation):
                c=copy.deepcopy(self.catalog)
                if mutation=='absent':c.pop('workloadScheduling')
                elif mutation=='unknown':c['workloadScheduling']['interactive']['queue']='other'
                elif mutation=='elevated':c['workloadScheduling']['interactive']['priorityClassName']='cps-exam'
                elif mutation=='queue':c['queues']['other']=copy.deepcopy(c['queues']['batch'])
                elif mutation=='profile-kind':c['profiles']['interactive-cpu']['kind']='batch'
                else:c['profiles']['interactive-cpu']['queue']='other'
                with self.assertRaises(ValueError):policy.compile_catalog(c)

    def test_determinism_and_hash(self):
        first = policy.compile_catalog(self.catalog)
        self.assertEqual(first, policy.compile_catalog(copy.deepcopy(self.catalog)))
        changed = copy.deepcopy(self.catalog)
        changed['version'] = '0.1.1'
        self.assertNotEqual(first['policyHash'], policy.compile_catalog(changed)['policyHash'])

    def test_reject_unknown_profile_grant(self):
        self.catalog['entitlements']['student']['profiles'].append('invented')
        with self.assertRaises(ValueError): policy.compile_catalog(self.catalog)

    def test_reject_mutable_images(self):
        self.catalog['approvedImages'] = ['registry/notebook:latest']
        with self.assertRaises(ValueError): policy.compile_catalog(self.catalog)

    def test_gpu_profiles_require_qualification(self):
        result = policy.compile_catalog(self.catalog)
        self.assertFalse(result['gpuQualification']['qualified'])
        self.assertEqual(result['approvedImages'], [])
        self.assertTrue(all(not p['enabled'] for p in result['profiles'].values() if p['gpu']['mode'] != 'none'))

    def test_qualification_hash_and_artifact_gate(self):
        evidence = {'policyHash': 'wrong', 'passed': True, 'artifacts': []}
        with self.assertRaises(ValueError): policy.validate_evidence(evidence, policy.compile_catalog(self.catalog)['policyHash'])

    def test_shared_gpu_fractions_use_inventoried_40gib(self):
        self.assertEqual(self.catalog["gpuQualification"]["nominalDeviceMemoryGiB"], 40)
        self.assertEqual(self.catalog["profiles"]["interactive-shared-20"]["gpu"]["fraction"], "0.5")

    def test_queue_units_follow_kai_crd(self):
        queue = policy.manifests(policy.compile_catalog(self.catalog))['items'][0]
        self.assertEqual(queue['spec']['resources']['cpu']['limit'], 256000)
        self.assertEqual(queue['spec']['resources']['memory']['limit'], 1048576 * 1.048576)

    def test_evidence_artifacts_detect_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.txt'
            path.write_text('reviewed results')
            evidence = {'policyHash': 'sha256:test', 'passed': True,
                        'scenarios': ['identity-storage', 'authorization', 'permissions', 'collaboration', 'pooling', 'notebook-jobs', 'isolation', 'scheduling', 'startup', 'defragmentation', 'recovery', 'moodle-scaffold'],
                        'artifacts': [{'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}]}
            policy.validate_evidence(evidence, 'sha256:test')
            path.write_text('tampered')
            with self.assertRaises(ValueError): policy.validate_evidence(evidence, 'sha256:test')

    def test_reject_moodle_activation(self):
        self.catalog['courseProviders']['moodle']['enabled'] = True
        with self.assertRaisesRegex(ValueError, 'planned'): policy.compile_catalog(self.catalog)

    def test_reject_queue_capacity_drift(self):
        self.catalog['queues']['interactive']['gpu']['limit'] = 9
        with self.assertRaises(ValueError): policy.compile_catalog(self.catalog)

if __name__ == '__main__': unittest.main()
