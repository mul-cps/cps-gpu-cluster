"""The central catalog configures the launcher without asserting qualification."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('jobset_policy_compiler', ROOT / 'scripts/compile_compute_policy.py')
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)
EXPECTED = {
    'namespace': 'cps-workflows', 'serviceAccountName': 'cps-workflow',
    'command': ['python'], 'maxWorkers': 8, 'maxRetries': 2,
    'ttlSecondsAfterFinished': 600, 'checkpointClaims': {},
}

class JobSetPolicyTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'compute-policy/catalog.json').read_text())
        self.schema = Draft202012Validator(json.loads((ROOT / 'compute-policy/catalog.schema.json').read_text()))

    def configured(self):
        value = copy.deepcopy(self.catalog)
        value['trusted']['jobsets'] = copy.deepcopy(EXPECTED)
        value['distributedQualification'] = {'qualified': False}
        return value

    def test_catalog_has_bounded_launcher_but_no_qualification_assertion(self):
        self.schema.validate(self.catalog)
        compiled = compiler.compile_catalog(self.catalog)
        self.assertEqual(compiled['trusted']['jobsets'], EXPECTED)
        self.assertEqual(compiled['distributedQualification'], {'qualified': False})
        self.assertTrue(all(not p['enabled'] for p in compiled['profiles'].values() if p['gpu']['mode'] != 'none'))

    def test_compiler_rejects_invalid_launcher_contract(self):
        changes = [
            ('namespace', 'default'), ('serviceAccountName', 'admin'),
            ('command', ['sh', '-c']), ('maxWorkers', 9), ('maxWorkers', True),
            ('maxWorkers', 0), ('maxRetries', 4), ('maxRetries', True),
            ('ttlSecondsAfterFinished', 59), ('ttlSecondsAfterFinished', 86401),
            ('ttlSecondsAfterFinished', False), ('checkpointClaims', []),
            ('unknownOverride', {}),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                candidate = self.configured()
                candidate['trusted']['jobsets'][key] = value
                with self.assertRaises(ValueError):
                    compiler.compile_catalog(candidate)
        for field in EXPECTED:
            with self.subTest(missing=field):
                candidate = self.configured()
                del candidate['trusted']['jobsets'][field]
                with self.assertRaises(ValueError):
                    compiler.compile_catalog(candidate)

    def test_legacy_catalog_remains_compilable_without_injecting_new_settings(self):
        candidate = copy.deepcopy(self.catalog)
        candidate['trusted'].pop('jobsets', None)
        candidate.pop('distributedQualification', None)
        compiled = compiler.compile_catalog(candidate)
        self.assertNotIn('jobsets', compiled['trusted'])
        self.assertNotIn('distributedQualification', compiled)

    def test_explicit_null_is_not_a_legacy_catalog(self):
        candidate = self.configured()
        candidate['trusted'].pop('jobsets')
        candidate['distributedQualification'] = None
        with self.assertRaises(ValueError):
            compiler.compile_catalog(candidate)

    def test_checkpoint_claims_reject_gateway_startup_failures(self):
        invalid = [{ 'test': {'claimName': 'INVALID/claim'} },
            {'test': ''}, {'test': 'a..b'}, {'test': 'a' * 64}, {' ': 'claim'},
            {'test': {'claimName': 'claim', 'subPath': '../other'}},
            {'test': {'claimName': 'claim', 'subPath': '/absolute'}},
            {'test': {'claimName': 'claim', 'subPath': 'a//b'}},
            {'test': {'claimName': 'claim', 'subPath': None}},
            {'test': {'claimName': 'claim', 'subPath': 'a/'}},
            {'test': {'claimName': 'claim', 'subPath': '.'}},
            {'test': {'claimName': 'claim', 'subPath': 'a\\b'}},
            {'test': {'claimName': 'claim', 'subPath': 'a\x00b'}},
            {'test': {'claimName': 'claim', 'unknown': True}}, {'test': {}},
            {'test': False}]
        for claims in invalid:
            with self.subTest(claims=claims):
                candidate = self.configured()
                candidate['trusted']['jobsets']['checkpointClaims'] = claims
                self.assertFalse(self.schema.is_valid(candidate))
                with self.assertRaises(ValueError):
                    compiler.compile_catalog(candidate)

    def test_reviewed_checkpoint_claim_forms_are_supported(self):
        for entry in ('reviewed-claim', {'claimName': 'reviewed.claim'},
                      {'claimName': 'reviewed-claim', 'subPath': 'groups/team-a'},
                      {'claimName': 'reviewed-claim', 'subPath': 'a'}):
            with self.subTest(entry=entry):
                candidate = self.configured()
                candidate['trusted']['jobsets']['checkpointClaims'] = {'project': entry}
                self.schema.validate(candidate)
                self.assertEqual(compiler.compile_catalog(candidate)['trusted']['jobsets']['checkpointClaims'],
                                 {'project': entry})

    def test_qualification_cannot_be_asserted_by_editing_the_catalog(self):
        for bad in ({'qualified': True}, {'qualified': 0}, {'qualified': 'false'},
                    {'qualified': False, 'evidence': ['unreviewed']}, None):
            with self.subTest(value=bad):
                candidate = self.configured()
                candidate['distributedQualification'] = bad
                with self.assertRaises(ValueError):
                    compiler.compile_catalog(candidate)
