"""Report boundaries plus actual retained-receipt checks, never live calls."""
import base64
import hashlib
import json
from pathlib import Path
import unittest


HERE = Path(__file__).parent
CROSS = Path('/home/bjoern/.local/state/cps-platform-completion-20261012/current-group-crosspod-20261012')
KEYS = {'kernel-controls', 'cap-peer-aggregate', 'same-parent-vmm-direct',
        'same-parent-ipc', 'same-parent-vmm', 'ipc-cps-to-cit', 'ipc-cit-to-cps',
        'vmm-cps-to-cit', 'vmm-cit-to-cps', 'mps-cit10'}


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Operator20ReportTests(unittest.TestCase):
    def setUp(self):
        self.report = read(HERE / 'operator20-measurement.json')

    def test_measurement_scope_does_not_claim_broader_qualification(self):
        self.assertEqual(set(self.report['phases']), KEYS)
        self.assertEqual(self.report['scope']['approved_workspace_slots'], 2)
        self.assertEqual(self.report['scope']['cit_cap_mib'], 20480)
        self.assertEqual(self.report['scope']['budget_mib'], 25600)
        self.assertEqual((self.report['scope']['mig_current'], self.report['scope']['mig_pending']), (0, 0))
        for key in ('complete_isolation_qualified', 'sm_compute_distribution_qualified',
                    'general_gpu_access_qualified', 'profile20_general_access_qualified',
                    'production_qualified', 'gitops_activation_authorized'):
            self.assertIs(self.report['qualification'][key], False, key)
        for phase in self.report['phases'].values():
            self.assertEqual(phase['exit_code'], 0)
            self.assertIs(phase['production_qualified'], False)

    def test_each_reported_phase_matches_actual_exit_receipt_and_zero_accounting(self):
        if not (CROSS / 'harness20-actual-v4/measurements').exists():
            self.skipTest('Private retained actual evidence is intentionally unavailable')
        for key, phase in self.report['phases'].items():
            with self.subTest(phase=key):
                packet = phase['packet']
                base = CROSS / ('harness20-actual-' + packet) / 'measurements'
                execution = 'phase-execution.json' if key in ('kernel-controls', 'cap-peer-aggregate', 'mps-cit10') else 'phase-import-execution.json'
                actual = read(base / execution)[key]
                self.assertEqual(actual['exit_code'], 0)
                self.assertEqual(actual['seconds'], phase['seconds'])
                folder = base / key
                receipt = read(folder / 'receipt.json')
                self.assertEqual(receipt['state'], phase['receipt_state'])
                self.assertEqual(sha(folder / 'receipt.json'), self.report['private_evidence_raw_sha256'][packet + '-' + key + '-receipt'])
                cases = [folder / case for case in ('cross-pod', 'same-pod-aggregate')] if key == 'cap-peer-aggregate' else [folder]
                for case in cases:
                    before = read(case / 'before.json')['host']
                    after = read(case / ('final-postflight.json' if key.startswith('vmm-') else 'after.json'))['host']
                    self.assertEqual(before['retired_caps'], after['retired_caps'])
                    self.assertEqual(len(after['retired_caps']), 25)
                    for a, b in zip(before['targets'], after['targets']):
                        for field in ('intent', 'identity', 'seal_id', 'journal_sha256', 'gate_sha256'):
                            self.assertEqual(a[field], b[field])
                        self.assertEqual(b['inventory_row']['used'], 0)
                if key == 'mps-cit10':
                    self.assertEqual(phase['measurement'], receipt['measurement'])
                    self.assertEqual(read(folder / 'host-cleaned.json')['processes'], [])
                if key.startswith(('ipc-', 'vmm-')):
                    witness = read(folder / 'kernel-witness-correlation.json')
                    capture = read(folder / 'kernel-witness-capture.json')
                    canonical = json.dumps(capture, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
                    self.assertEqual(witness['capture_sha256'], 'sha256:' + hashlib.sha256(canonical).hexdigest())
                    self.assertEqual(witness, receipt['kernel_witness_correlation'])
                    self.assertTrue(witness['begin_sequence'] < witness['kernel_sequence'] < witness['end_sequence'])
                    self.assertEqual((witness['kernel_status'], witness['kernel_reason']), (27, 6))

    def test_terminal_closure_matches_actual_stops_inventory_and_restoration(self):
        closure = self.report['terminal_closure']
        self.assertEqual(self.report['state'], 'operator20-ten-phase-evidence-and-terminal-closure-reviewed')
        for key in ('normal_stop_and_physical_retirement_reviewed',
                    'configuration_inverse_and_fixture_restoration_reviewed'):
            self.assertIs(self.report['qualification'][key], True)
        self.assertEqual(closure['state'], 'normal-stop-physical-retirement-and-restoration-reviewed')
        if not (CROSS / 'profile20-current-restored-terminal-capture-v1/host.json').exists():
            self.skipTest('Private retained actual evidence is intentionally unavailable')
        terminal = CROSS / 'profile20-current-restored-terminal-capture-v1'
        files = {
            'terminal-stop-execution': CROSS / 'profile20-current-source-call-v1/Root-normal-stop-execution.json',
            'terminal-fixture-restore-execution': CROSS / 'profile20-current-source-call-v1/Root-normal-restore-v3-execution.json',
            'terminal-root-restoration': CROSS / 'profile20-current-restored-readback-v1/Root-verified-restoration.json',
            'terminal-capture-receipt': terminal / 'capture-receipt.json',
            'terminal-cps-absence': terminal / 'jupyterhub-target-absence.json',
            'terminal-cit-absence': terminal / 'cit-jhub-target-absence.json',
            'terminal-ledger': terminal / 'ledger.json',
            'terminal-host': terminal / 'host.json',
            'terminal-pods': terminal / 'pods.json',
            'terminal-authorities': terminal / 'maps.json',
            'terminal-physical-witness': CROSS / 'profile20-current-stop-witness-v1/physical-observation/physical.json',
            'terminal-bounded-inspection': CROSS / 'profile20-current-source-preparation-v1/bounded-stop-inspect-v2/inspect.stdout',
        }
        for key, path in files.items():
            self.assertEqual(sha(path), self.report['private_evidence_raw_sha256'][key], key)
        for key, field in [('terminal-stop-execution', 'normal_source_stop_exit_codes'),
                           ('terminal-fixture-restore-execution', 'normal_source_fixture_restore_exit_codes')]:
            execution = read(files[key])
            self.assertEqual({owner: row['exit_code'] for owner, row in execution.items()}, closure[field])
            self.assertTrue(all(row['exit_code'] == 0 for row in execution.values()))
        root = read(files['terminal-root-restoration'])
        for field in ('exact_original_Source_records', 'full_config_readbacks_passed',
                      'actual_new_terminal_agent_confirmations'):
            self.assertIs(root[field], True)
            self.assertEqual(root[field], closure[field])
        for field in ('policy_hash', 'terminal_archive_count', 'retained_runtime_history_count'):
            self.assertEqual(root[field], closure[field])
        self.assertEqual(root['at'], closure['restoration_verified_at'])
        for field in ('MIG_change', 'driver_change', 'human_oauth', 'production_qualified'):
            self.assertIs(root[field], False)
        receipt = read(files['terminal-capture-receipt'])
        self.assertEqual(receipt['exit_code'], 0)
        self.assertIs(receipt['complete'], True)
        for owner in ('cps', 'cit'):
            self.assertEqual(read(files['terminal-' + owner + '-absence'])['status'], 404)
            self.assertEqual(closure['target_absence_statuses'][owner], 404)
        ledger = json.loads(read(files['terminal-ledger'])['data']['state.json'])['allocations']
        self.assertEqual(len(ledger), closure['released_allocation_count'])
        self.assertTrue(all(row['state'] == 'released' for row in ledger.values()))
        host = read(files['terminal-host'])
        inventory = host['finiteCaps']
        raw = base64.b64decode(host['finiteCapsRawBase64'], validate=True)
        self.assertEqual('sha256:' + hashlib.sha256(raw).hexdigest(), host['finiteCapsRawSha256'])
        self.assertEqual(json.loads(raw), inventory)
        rows = inventory['entries']
        self.assertEqual(len(rows), closure['physical_inventory_rows'])
        self.assertEqual(len({row['inode'] for row in rows}), len(rows))
        self.assertTrue(all(row['offline'] is True and row['used'] == 0 for row in rows))
        finite = [row for row in rows if row['hard'] < 2**64 - 1]
        cleared = [row for row in rows if row['hard'] == 2**64 - 1]
        self.assertEqual(len(finite), closure['physical_finite_rows'])
        self.assertEqual(len(cleared), closure['physical_cleared_rows'])
        self.assertTrue(all(row['soft'] == 0 and row['pinned'] is True and
                            row['default_hierarchy'] is True for row in cleared))
        self.assertEqual(host['gateReceipts'], {})
        self.assertEqual(closure['active_gate_receipt_count'], 0)
        self.assertIs(closure['all_physical_rows_offline'], True)
        self.assertIs(closure['all_physical_rows_zero_charge'], True)
        self.assertIs(host['healthPassed'], True)
        physical = read(files['terminal-physical-witness'])
        self.assertEqual(physical['targets'], [])
        self.assertEqual(physical['inventory_sha256'], host['finiteCapsRawSha256'])
        self.assertEqual(physical['boot_id'], host['bootId'])
        self.assertEqual(physical['driver_generation'], host['driverGeneration'])
        self.assertEqual(physical['gpu_uuid'], inventory['gpu_uuid'])
        self.assertEqual({row['inventory_row']['inode'] for row in physical['retired_caps']},
                         {row['inode'] for row in finite})
        self.assertTrue(all(row['inventory_row']['offline'] is True and
                            row['inventory_row']['used'] == 0 for row in physical['retired_caps']))
        inspection = read(files['terminal-bounded-inspection'])
        self.assertEqual(sorted(row['cap_mib'] for row in inspection['terminal_lifetimes']), [5120, 20480])
        self.assertIs(inspection['production_qualified'], False)


if __name__ == '__main__':
    unittest.main()
