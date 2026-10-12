"""Offline checks of completed restart/retention evidence; no live calls."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).parent
CROSS = Path('/home/bjoern/.local/state/cps-platform-completion-20261012/current-group-crosspod-20261012')
PACKET = CROSS / 'harness20-restart-actual-v1'
PHASES = {'kernel-controls', 'same-parent-vmm', 'vmm-creator-exit'}


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Operator20RestartReportTests(unittest.TestCase):
    def setUp(self):
        self.report = read(HERE / 'operator20-restart-measurement.json')

    def test_scope_retains_operator_only_and_prior_report_boundaries(self):
        self.assertEqual(set(self.report['phases']), PHASES)
        self.assertEqual(self.report['scope']['approved_workspace_slots'], 2)
        self.assertEqual(self.report['scope']['cit_cap_mib'], 20480)
        self.assertEqual(self.report['scope']['budget_mib'], 25600)
        self.assertEqual(self.report['scope']['prior_full_archive_count'], 36)
        self.assertEqual(self.report['scope']['prior_released_allocation_count'], 39)
        self.assertEqual(self.report['scope']['prior_runtime_history_count'], 34)
        self.assertEqual(sha(HERE / 'operator20-measurement.json'), self.report['prior_operator20_report_raw_sha256'])
        for name in ('renewed_normal_lifetimes_measured', 'vmm_creator_exit_retention_measured'):
            self.assertIs(self.report['qualification'][name], True)
        for name in ('complete_isolation_qualified', 'sm_compute_distribution_qualified',
                     'general_gpu_access_qualified', 'profile20_general_access_qualified',
                     'production_qualified', 'gitops_activation_authorized'):
            self.assertIs(self.report['qualification'][name], False)

    def test_actual_pins_exit_receipts_and_seals_remain_exact(self):
        if not (PACKET / 'measurements/vmm-creator-exit/receipt.json').exists():
            self.skipTest('Private actual evidence is intentionally unavailable')
        for name, evidence in self.report['private_evidence'].items():
            path = Path(evidence['relative_path'])
            self.assertFalse(path.is_absolute())
            self.assertNotIn('..', path.parts)
            self.assertEqual(sha(CROSS / path), evidence['raw_sha256'], name)
        execution = read(PACKET / 'Root-actual-phase-execution-v2.json')
        execution['vmm-creator-exit'] = read(PACKET / 'Root-vmm-creator-exit-execution.json')
        for name in PHASES:
            phase = self.report['phases'][name]
            self.assertEqual(execution[name]['exit_code'], 0)
            self.assertEqual(phase['seconds'], execution[name]['seconds'])
            folder = PACKET / 'measurements' / name
            receipt = read(folder / 'receipt.json')
            self.assertEqual(phase['receipt_state'], receipt['state'])
            self.assertIs(receipt['production_qualified'], False)
            before, after = read(folder / 'before.json'), read(folder / 'after.json')
            self.assertEqual(before['pods'], after['pods'])
            self.assertEqual(before['host']['retired_caps'], after['host']['retired_caps'])
            self.assertEqual(len(after['host']['retired_caps']), 27)
            for old, new in zip(before['host']['targets'], after['host']['targets']):
                for field in ('identity', 'intent', 'seal_id', 'journal_sha256', 'gate_sha256'):
                    self.assertEqual(old[field], new[field], (name, field))
                self.assertEqual(new['inventory_row']['used'], 0)
        starts = read(CROSS / 'profile20-restart-source-call-v1/Root-start-execution.json')
        self.assertTrue(all(row['exit_code'] == 0 for row in starts.values()))
        prior = read(CROSS / 'harness20-actual-v4/measurements/vmm-cit-to-cps/final-postflight.json')
        renewed = read(PACKET / 'measurements/kernel-controls/before.json')
        self.assertTrue(set(row['pod_uid'] for row in prior['pods']).isdisjoint(
                        row['pod_uid'] for row in renewed['pods']))
        baseline = CROSS / 'profile20-restart-actual-singleuser-baseline-v3'
        result = read(baseline / 'execution-receipt.json')
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(result['request_size'], 72428)
        self.assertEqual(result['request_sha256'], sha(baseline / 'request.json'))
        self.assertEqual(result['stdout_sha256'], sha(baseline / 'actual-baseline.json'))
        self.assertEqual(result['source_sha256'], sha(CROSS / 'profile20-restart-singleuser-collector-v2/capture_singleuser.py'))
        self.assertEqual(result['transport_kind'], 'exact-argv-through-stdin-to-avoid-exec-URL-size')

    def test_original_retention_validators_match_actual_typed_backing_proof(self):
        if not (PACKET / 'measurements/vmm-creator-exit/receipt.json').exists():
            self.skipTest('Private actual evidence is intentionally unavailable')
        source = PACKET / 'vmm-owner-exit/run_owner_exit.py'
        self.assertEqual(sha(source), self.report['source_pins']['creator_exit_wrapper_raw_sha256'])
        spec = importlib.util.spec_from_file_location('retention_report_validator', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        folder = PACKET / 'measurements/vmm-creator-exit'
        receipt = read(folder / 'receipt.json')
        events = [json.loads(line) for line in (folder / 'endpoint.jsonl').read_bytes().splitlines()]
        execution = read(PACKET / 'Root-vmm-creator-exit-execution.json')
        measured = module.assess(events, execution['exit_code'], receipt['trial_id'])
        self.assertEqual(measured, receipt['measurement'])
        self.assertEqual(measured, self.report['creator_exit']['measurement'])
        retained = [read(folder / name) for name in ('retained-1.json', 'retained-12.json')]
        released = read(folder / 'backing-released-context-live.json')
        backing = module.validate_backing_charge(retained, released)
        self.assertEqual(backing, receipt['backing_charge'])
        self.assertEqual(backing, self.report['creator_exit']['backing_charge'])
        self.assertEqual(backing['vmm_backing_charge_drop_bytes'], 67108864)
        module.unchanged(read(folder / 'before.json'), read(folder / 'after.json'), 1)
        self.assertEqual(receipt['singleuser_baseline_sha256'], execution['baseline_raw_sha256'])
        self.assertEqual(receipt['root_retained_charge_samples'], 2)
        final = read(folder / 'participants-final.json')
        self.assertEqual(final['inventory_row']['used'], 0)
        self.assertTrue(all(row['actual_original_pid_absent'] is True for row in final['participants'].values()))
        changed = copy.deepcopy(released)
        changed['inventory_row']['used'] += 1
        with self.assertRaises(ValueError):
            module.validate_backing_charge(retained, changed)
        with self.assertRaises(ValueError):
            module.assess(events, 1, receipt['trial_id'])


if __name__ == '__main__':
    unittest.main()
