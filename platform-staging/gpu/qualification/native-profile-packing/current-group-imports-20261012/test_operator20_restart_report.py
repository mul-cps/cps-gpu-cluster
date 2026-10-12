"""Offline checks of completed restart/retention evidence; no live calls."""
import copy
import base64
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
                     'dynamic_ordinary_course_groups_qualified',
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

    def test_actual_terminal_closure_preserves_full_custody_and_restoration(self):
        self.assertEqual(self.report['state'], 'operator20-renewed-lifetimes-creator-exit-and-terminal-closure-reviewed')
        for name in ('physical_retirement_reviewed', 'configuration_inverse_and_fixture_restoration_reviewed'):
            self.assertIs(self.report['qualification'][name], True)
        closure = self.report['terminal_closure']
        path = CROSS / 'profile20-restart-restored-readback-v1/Root-verified-restoration.json'
        if not path.exists():
            self.skipTest('Private actual terminal evidence is intentionally unavailable')
        root = read(path)
        self.assertEqual(root, closure['sanitized_root_restoration'])
        for name in ('exact_original_Source_records', 'full_config_readbacks_passed',
                     'actual_new_terminal_agent_confirmations', 'physical_all_offline_zero'):
            self.assertIs(root[name], True, name)
        for name in ('MIG_change', 'driver_change', 'human_oauth', 'production_qualified'):
            self.assertIs(root[name], False, name)
        self.assertEqual(root['retained_agent_sha256'], self.report['source_pins']['node_agent_raw_sha256'])
        self.assertEqual((root['terminal_archive_count'], root['retained_runtime_history_count']), (38, 36))
        terminal = CROSS / 'profile20-restart-restored-terminal-capture-v1'
        capture = read(terminal / 'capture-receipt.json')
        self.assertEqual(capture['exit_code'], 0)
        self.assertIs(capture['complete'], True)
        for owner in ('jupyterhub', 'cit-jhub'):
            self.assertEqual(read(terminal / (owner + '-target-absence.json'))['status'], 404)
        ledger = json.loads(read(terminal / 'ledger.json')['data']['state.json'])['allocations']
        self.assertEqual(len(ledger), root['ledger_released_count'])
        self.assertEqual(len(ledger), 41)
        self.assertTrue(all(row['state'] == 'released' for row in ledger.values()))
        host = read(terminal / 'host.json')
        inventory_raw = base64.b64decode(host['finiteCapsRawBase64'], validate=True)
        self.assertEqual('sha256:' + hashlib.sha256(inventory_raw).hexdigest(), host['finiteCapsRawSha256'])
        self.assertEqual(json.loads(inventory_raw), host['finiteCaps'])
        rows = host['finiteCaps']['entries']
        self.assertEqual(len(rows), root['physical_inventory_count'])
        self.assertEqual(len(rows), 42)
        self.assertEqual(len({row['inode'] for row in rows}), len(rows))
        self.assertTrue(all(row['offline'] is True and row['used'] == 0 for row in rows))
        finite = [row for row in rows if row['hard'] < 2**64 - 1]
        cleared = [row for row in rows if row['hard'] == 2**64 - 1]
        self.assertEqual((len(finite), len(cleared)), (29, 13))
        self.assertTrue(all(row['soft'] == 0 and row['pinned'] is True and
                            row['default_hierarchy'] is True for row in cleared))
        self.assertEqual(host['gateReceipts'], {})
        self.assertIs(host['healthPassed'], True)
        witness = CROSS / 'profile20-restart-stop-witness-v1'
        for name in ('Root-physical-observer-execution.json', 'Root-inspect-execution.json'):
            self.assertEqual(read(witness / name)['exit_code'], 0)
        physical = read(witness / 'physical-observation/physical.json')
        self.assertEqual(physical['targets'], [])
        self.assertEqual(physical['inventory_sha256'], host['finiteCapsRawSha256'])
        self.assertEqual(physical['boot_id'], host['bootId'])
        self.assertEqual(physical['driver_generation'], host['driverGeneration'])
        self.assertEqual({row['inventory_row']['inode'] for row in physical['retired_caps']},
                         {row['inode'] for row in finite})
        self.assertTrue(all(row['inventory_row']['offline'] is True and row['inventory_row']['used'] == 0
                            for row in physical['retired_caps']))
        inspection = read(witness / 'Root-inspect.stdout')
        self.assertEqual(sorted(row['cap_mib'] for row in inspection['terminal_lifetimes']), [5120, 20480])
        self.assertIs(inspection['production_qualified'], False)
        restore = read(CROSS / 'profile20-restart-source-call-v1/Root-restore-v3-execution.json')
        self.assertEqual({owner: row['exit_code'] for owner, row in restore.items()}, {'cps': 0, 'cit': 0})


if __name__ == '__main__':
    unittest.main()
