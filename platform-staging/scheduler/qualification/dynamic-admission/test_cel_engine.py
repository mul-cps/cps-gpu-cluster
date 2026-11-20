"""Execute actual CEL; these tests do not mirror policy predicates in Python."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cel_evaluate as engine


def policy(*expressions, variables=None, matches=None):
    return {'apiVersion': 'admissionregistration.k8s.io/v1', 'kind': 'ValidatingAdmissionPolicy',
        'metadata': {'name': 'offline-cel-test'}, 'spec': {
            'variables': variables or [], 'matchConditions': matches or [],
            'validations': [{'expression': value} for value in expressions]}}


INPUTS = {'request': {'namespace': 'cps-workflows'}, 'object': {'spec': {'containers': [
    {'name': 'main', 'image': 'approved@sha256:' + '1' * 64}]}}, 'oldObject': None,
    'params': {'data': {'approved': ['approved@sha256:' + '1' * 64]}}}


class CelEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec('celpy') is None:
            raise RuntimeError('Run real CEL tests with the documented cached CEL venv; no mirror fallback')

    def test_true_and_false_are_real_boolean_results(self):
        for expression, expected in [('true', True), ('false', False),
                                     ('request.namespace == "cps-workflows"', True)]:
            with self.subTest(expression=expression):
                result = engine.evaluate_policy(policy(expression), INPUTS)
                self.assertTrue(result['compiled'])
                self.assertTrue(result['evaluated'])
                self.assertEqual(result['allExpressionsTrue'], expected)
                receipt = result['expressions'][0]
                self.assertEqual(receipt['resultType'], 'BoolType')
                self.assertEqual(receipt['resultBool'], expected)
                self.assertEqual(receipt['expressionSha256'], hashlib.sha256(expression.encode()).hexdigest())
                self.assertEqual(result['engine']['version'], '0.4.0')

    def test_missing_field_errors_fail_closed_but_has_macro_handles_absence(self):
        direct = engine.evaluate_policy(policy('object.spec.hostNetwork'), INPUTS)
        self.assertFalse(direct['allExpressionsTrue'])
        self.assertEqual(direct['expressions'][0]['failure'], 'evaluation-error')
        guarded = engine.evaluate_policy(policy('!has(object.spec.hostNetwork) || !object.spec.hostNetwork'), INPUTS)
        self.assertTrue(guarded['allExpressionsTrue'])

    def test_actual_all_exists_filter_macros_and_map_values(self):
        value = engine.evaluate_policy(policy(
            "object.spec.containers.all(c, c.image in params.data['approved'])",
            "object.spec.containers.exists(c, c.name == 'main')",
            "object.spec.containers.filter(c, c.name == 'wait').all(c, c.image in params.data['approved'])"), INPUTS)
        self.assertTrue(value['allExpressionsTrue'])
        untrusted = copy.deepcopy(INPUTS)
        untrusted['object']['spec']['containers'].append({'name': 'bad', 'image': 'unapproved'})
        value = engine.evaluate_policy(policy(
            "object.spec.containers.all(c, c.image in params.data['approved'])"), untrusted)
        self.assertFalse(value['allExpressionsTrue'])
        self.assertEqual(value['expressions'][0]['failure'], 'false')

    def test_variables_evaluate_in_declaration_order(self):
        value = engine.evaluate_policy(policy("variables.count == 1 && variables.approved",
            variables=[{'name': 'count', 'expression': 'size(object.spec.containers)'},
                {'name': 'approved', 'expression': "variables.count > 0 && object.spec.containers.all(c, c.image in params.data['approved'])"}]), INPUTS)
        self.assertTrue(value['allExpressionsTrue'])
        self.assertEqual([record['stage'] for record in value['expressions']], ['variable', 'variable', 'validation'])
        reversed_order = engine.evaluate_policy(policy('variables.first', variables=[
            {'name': 'first', 'expression': 'variables.later'}, {'name': 'later', 'expression': 'true'}]), INPUTS)
        self.assertFalse(reversed_order['allExpressionsTrue'])
        self.assertEqual(reversed_order['expressions'][0]['failure'], 'evaluation-error')

    def test_no_match_skipping_or_hidden_validation(self):
        value = engine.evaluate_policy(policy('object.spec.missing == 1',
            matches=[{'name': 'other-namespace', 'expression': 'request.namespace == "other"'}]), INPUTS)
        self.assertFalse(value['allExpressionsTrue'])
        self.assertEqual(value['expressions'][0]['failure'], 'false')
        self.assertEqual(value['expressions'][1]['failure'], 'evaluation-error')
        value = engine.evaluate_policy(policy('false', 'true'), INPUTS)
        self.assertEqual([record['resultBool'] for record in value['expressions']], [False, True])

    def test_parse_eval_and_nonboolean_errors_cannot_pass(self):
        for expression, failure in [('this is not CEL ???', 'parse-error'),
                                    ('1 / 0 == 0', 'evaluation-error'),
                                    ('42', 'nonboolean-result'),
                                    ('[true]', 'nonboolean-result'),
                                    ('undeclared == 1', 'evaluation-error')]:
            with self.subTest(expression=expression):
                result = engine.evaluate_policy(policy(expression), INPUTS)
                self.assertFalse(result['allExpressionsTrue'])
                self.assertEqual(result['expressions'][0]['failure'], failure)

    def test_unsupported_kubernetes_string_extension_is_not_emulated(self):
        value = engine.evaluate_policy(policy("'a,b'.split(',') == ['a','b']"), INPUTS)
        self.assertTrue(value['compiled'])
        self.assertFalse(value['evaluated'])
        self.assertFalse(value['allExpressionsTrue'])
        self.assertEqual(value['expressions'][0]['failure'], 'evaluation-error')

    def test_interpreter_missing_field_comparison_difference_is_disclosed(self):
        # Pin this measured limitation rather than silently claiming the
        # interpreter is interchangeable with Kubernetes' CEL engine.
        compared = engine.evaluate_policy(policy('object.spec.missing != false'), INPUTS)
        self.assertTrue(compared['allExpressionsTrue'])
        self.assertTrue(any('missing-map-field comparison' in value for value in compared['limitations']))
        guarded = engine.evaluate_policy(policy('has(object.spec.missing) && object.spec.missing != false'), INPUTS)
        self.assertFalse(guarded['allExpressionsTrue'])

    def test_error_receipts_do_not_disclose_activation_values(self):
        values = copy.deepcopy(INPUTS)
        values['params']['private'] = 'PRIVATE_ACTIVATION_DO_NOT_REPORT'
        result = engine.evaluate_policy(policy('undeclared == params.private'), values)
        self.assertFalse(result['allExpressionsTrue'])
        self.assertNotIn('PRIVATE_ACTIVATION_DO_NOT_REPORT', json.dumps(result))
        self.assertNotIn('error', result['expressions'][0])

    def test_input_injection_empty_validations_and_bad_variables_fail_closed(self):
        injected = {**INPUTS, 'variables': {'allowed': True}}
        result = engine.evaluate_policy(policy('variables.allowed'), injected)
        self.assertFalse(result['allExpressionsTrue'])
        for bad in [policy(), policy('true', variables=[{'name': 'bad.name', 'expression': 'true'}]),
                    policy('true', variables=[{'name': 'x', 'expression': 'true'}, {'name': 'x', 'expression': 'false'}])]:
            self.assertFalse(engine.evaluate_policy(bad, INPUTS)['allExpressionsTrue'])
        nan_values = copy.deepcopy(INPUTS)
        nan_values['params']['notJson'] = float('nan')
        self.assertFalse(engine.evaluate_policy(policy('true'), nan_values)['allExpressionsTrue'])

    def test_manifest_cli_loads_literal_yaml_and_seals_source_hashes(self):
        import yaml
        with tempfile.TemporaryDirectory(prefix='cps-cel-engine-') as directory:
            root = Path(directory)
            manifest = root / 'policy.yaml'
            manifest.write_text(yaml.safe_dump_all([policy('request.namespace == "cps-workflows"'),
                {'kind': 'ValidatingAdmissionPolicyBinding', 'spec': {'policyName': 'offline-cel-test'}}]))
            inputs = root / 'inputs.json'; inputs.write_text(json.dumps(INPUTS))
            output = root / 'result.json'
            self.assertEqual(engine.main(['--policy', str(manifest), '--inputs', str(inputs), '--output', str(output)]), 0)
            result = json.loads(output.read_text())
            self.assertEqual(result['policyFileSha256'], hashlib.sha256(manifest.read_bytes()).hexdigest())
            self.assertEqual(result['inputsFileSha256'], hashlib.sha256(inputs.read_bytes()).hexdigest())
            self.assertTrue(result['allExpressionsTrue'])
            with self.assertRaises(FileExistsError):
                engine.main(['--policy', str(manifest), '--inputs', str(inputs), '--output', str(output)])
            manifest.write_text(yaml.safe_dump_all([policy('true'), policy('true')]))
            with self.assertRaises(ValueError):
                engine.load_policy(manifest)


if __name__ == '__main__':
    unittest.main()
