"""Synthetic CPU regressions for additive custody across a policy transition."""
import copy
import importlib
import json
from pathlib import Path
import tempfile
import unittest

import test_node_agent as legacy

HERE = Path(__file__).resolve().parent
OLD = 'sha256:4f1dff1a92aba5cd7376dfb897612b7e6f2e6f15a09515dbdf29efa4c522359d'
NEW = 'sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0'


class TerminalHistoryExtensionTest(unittest.TestCase):
    def load(self):
        self.assertTrue((HERE / 'terminal_history_extension.py').is_file(), 'Additive custody preparer required')
        return importlib.import_module('terminal_history_extension')

    def fixture(self, root):
        old = legacy.TerminalHistoryTest(); old.setUp()
        old.config['policy_hash'] = OLD
        old.config['workspaces'] = {'cps:native-group-b': {'profile': 'interactive-shared-5'}}
        old.enrollment.update(workspace='native-group-b', principal='workspace:cps:native-group-b',
            profile='interactive-shared-5', policy_hash=OLD)
        old.enrollment['intent']['policy_hash'] = OLD
        old.cm['data']['enrollment.json'] = legacy.canonical_json(old.enrollment)
        values = list(old.completed(root, retired=True))
        config = values[0]
        config['policy_hash'] = NEW
        config['workspaces'] = {'cps:native-group-b': {'profile': 'interactive-shared-5', 'cap_mib': 5120}}
        pool = json.loads((HERE / 'qualification/limited-group-20261012/native-groups.json').read_text())['node_pool']
        epoch = values[5][legacy.POD].identity.epoch
        pool.update(boot_id=epoch.boot_id, driver_generation=epoch.driver_generation)
        config.update(version=2, mode='qualified-group', pool=pool, terminal_history={})
        cleanup = values[4]['cps-native-cleanup-' + legacy.BINDING[:40]]
        ledger = values[4]['cps-native-gpu-allocations']
        journals = {legacy.POD: values[5][legacy.POD].to_dict()}
        return old, values, [old.cm], [cleanup], ledger, journals

    def test_missing_old_lifetime_fails_then_exact_addition_passes_existing_validator(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as temporary:
            old, values, enrollments, cleanups, ledger, journals = self.fixture(Path(temporary))
            original = copy.deepcopy(values[0]); original_journals = copy.deepcopy(journals)
            with self.assertRaisesRegex(ValueError, 'Reviewed workspace/profile/policy'):
                old.dispatch(values)
            updated = module.derive(values[0], enrollments, cleanups, ledger, journals, old.models)
            entry = updated['terminal_history'][legacy.POD]
            self.assertEqual(entry['policy_hash'], OLD)
            self.assertEqual(entry['cap_mib'], 5120)
            self.assertEqual(entry['journal_sha256'], old.agent.canonical_sha256(journals[legacy.POD]))
            restored = copy.deepcopy(updated); restored['terminal_history'] = original['terminal_history']
            self.assertEqual(restored, original)
            self.assertEqual(values[0], original); self.assertEqual(journals, original_journals)
            values[0] = updated
            envelopes, terminal = old.dispatch(values)
            self.assertEqual(terminal, {legacy.POD}); self.assertEqual(len(envelopes), 1)
            self.assertGreaterEqual(len(values[-1]), 2)

    def test_rejects_unreleased_wrong_policy_journal_and_cleanup_custody(self):
        module = self.load()
        for fault in ('active', 'policy', 'journal', 'cleanup', 'owner', 'missing'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temporary:
                old, values, enrollments, cleanups, ledger, journals = self.fixture(Path(temporary))
                if fault == 'active':
                    state = json.loads(ledger['data']['state.json']); state['allocations'][legacy.BINDING]['state'] = 'enrolled'
                    ledger['data']['state.json'] = legacy.canonical_json(state)
                elif fault == 'policy':
                    body = json.loads(enrollments[0]['data']['enrollment.json']); body['policy_hash'] = NEW
                    enrollments[0]['data']['enrollment.json'] = legacy.canonical_json(body)
                elif fault == 'journal': journals[legacy.POD]['state'] = 'sealed'
                elif fault == 'cleanup': cleanups[0]['data']['receipt.json'] = '{}'
                elif fault == 'owner': cleanups[0]['metadata']['ownerReferences'] = [{'uid': legacy.POD}]
                else: journals.clear()
                with self.assertRaises(ValueError):
                    module.derive(values[0], enrollments, cleanups, ledger, journals, old.models)

    def test_existing_entries_are_unchanged_and_new_entry_cannot_replace_one(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as temporary:
            old, values, enrollments, cleanups, ledger, journals = self.fixture(Path(temporary))
            updated = module.derive(values[0], enrollments, cleanups, ledger, journals, old.models)
            self.assertEqual(module.derive(updated, enrollments, [], ledger, {}, old.models), updated)
            # Runtime historical custody still detects tampering; config itself
            # cannot authorize an old payload to become a new current intent.
            updated['terminal_history'][legacy.POD]['completion_uid'] = legacy.NODE
            values[0] = updated
            with self.assertRaises(ValueError): old.dispatch(values)

    def test_complete_capture_checks_protected_mirrors_pod_absence_and_physical_cap(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as temporary:
            old, values, enrollments, cleanups, ledger, journals = self.fixture(Path(temporary))
            retirement = journals[legacy.POD]['retirement']
            capture = {'current_node_config': values[0], 'historical_entries_preserved': 0,
                'ledger': ledger, 'late': [{'pod_uid': legacy.POD, 'pod_absent': True,
                    'enrollment': enrollments[0], 'completion': cleanups[0]}],
                'protected': {'records': {legacy.POD: {'journal': journals[legacy.POD],
                    'enrollments': old.check(), 'intents': old.enrollment['intent']}},
                    'caps': {'gpu_uuid': legacy.GPU, 'gpu_id': retirement['gpu_id'],
                        'entries': [retirement['entry']]}}}
            self.assertEqual(module.from_capture(capture, old.models),
                module.derive(values[0], enrollments, cleanups, ledger, journals, old.models))
            for fault in ('pod', 'mirror', 'intent', 'used', 'gpu-id'):
                with self.subTest(fault=fault):
                    bad = copy.deepcopy(capture)
                    if fault == 'pod': bad['late'][0]['pod_absent'] = False
                    elif fault == 'mirror': bad['protected']['records'][legacy.POD]['enrollments']['configmap_uid'] = legacy.NODE
                    elif fault == 'intent': bad['protected']['records'][legacy.POD]['intents']['policy_hash'] = NEW
                    elif fault == 'used': bad['protected']['caps']['entries'][0]['used'] = 1
                    else: bad['protected']['caps']['gpu_id'] += 1
                    with self.assertRaises(ValueError): module.from_capture(bad, old.models)
