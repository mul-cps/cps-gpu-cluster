#!/usr/bin/env python3
"""Execute literal admission CEL using an installed, reported CEL interpreter.

This is not a Kubernetes admission/type-check implementation. Every expression
is parsed and evaluated; match conditions do not skip validations. No expression
is translated into a Python policy predicate or given custom policy functions.
Use the cached CEL venv, or expose its site-packages with PYTHONPATH. Installing
dependencies and contacting a cluster are deliberately outside this program.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re

ENGINE = 'cel-python'
ENGINE_VERSION = '0.4.0'
INPUT_NAMES = {'request', 'object', 'oldObject', 'params'}
LIMITATIONS = [
    'CEL parser/interpreter evaluation only; Kubernetes static schema/type-checking was not run',
    'No API-server defaulting, mutation, authorizer, cost budget, binding, or admission propagation was tested',
    'Every match condition and validation is evaluated; a false match condition does not skip validations',
    'Only interpreter built-ins are available; missing Kubernetes CEL extensions fail closed',
    'Observed cel-python difference: missing-map-field comparison to false produces false for == and true for !=; this is not Kubernetes CEL conformance proof',
]


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def _engine():
    import celpy
    from celpy.adapter import json_to_cel
    version = importlib.metadata.version(ENGINE)
    if version != ENGINE_VERSION:
        raise RuntimeError('Unreviewed CEL interpreter version')
    return celpy, json_to_cel, {
        'name': ENGINE, 'version': version, 'pythonVersion': platform.python_version(),
        'dependencies': {name: importlib.metadata.version(name) for name in
            ('lark', 'google-re2', 'jmespath', 'pendulum', 'PyYAML')},
        'compilePhase': 'CEL source parsed to AST; no Kubernetes static type check',
    }


def load_policy(path):
    """Select exactly one real VAP document from a YAML manifest."""
    import yaml
    raw = Path(path).read_bytes()
    policies = [document for document in yaml.safe_load_all(raw)
                if isinstance(document, dict) and document.get('kind') == 'ValidatingAdmissionPolicy']
    if len(policies) != 1:
        raise ValueError('Exactly one ValidatingAdmissionPolicy document required')
    return policies[0], sha256(raw)


def _expressions(policy):
    if not isinstance(policy, dict) or policy.get('kind') != 'ValidatingAdmissionPolicy':
        raise ValueError('ValidatingAdmissionPolicy object required')
    spec = policy.get('spec')
    if not isinstance(spec, dict):
        raise ValueError('Policy spec required')
    records = []
    variable_names = set()
    for stage, field in (('variable', 'variables'), ('matchCondition', 'matchConditions'),
                         ('validation', 'validations')):
        values = spec.get(field, [])
        if not isinstance(values, list) or (stage == 'validation' and not values):
            raise ValueError('Nonempty validations and expression lists required')
        for index, entry in enumerate(values):
            if not isinstance(entry, dict) or not isinstance(entry.get('expression'), str) or not entry['expression'].strip():
                raise ValueError('Literal nonempty CEL expression required')
            name = entry.get('name', str(index))
            if stage == 'variable':
                if (not isinstance(name, str) or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*', name)
                        or name in variable_names):
                    raise ValueError('Distinct CEL variable identifiers required')
                variable_names.add(name)
            records.append({'stage': stage, 'index': index, 'name': name,
                            'expression': entry['expression']})
    return records


def evaluate_policy(policy, inputs):
    """Run source expressions with JSON bindings and declaration-order variables.

    Reports omit raw inputs and exception strings: interpreter errors may include
    the entire activation, which can contain private admission data.
    """
    report = {'status': 'failed', 'engine': None, 'compiled': False, 'evaluated': False,
              'allExpressionsTrue': False, 'expressions': [], 'limitations': list(LIMITATIONS)}
    try:
        celpy, json_to_cel, metadata = _engine()
        report['engine'] = metadata
        expressions = _expressions(policy)
        if (not isinstance(inputs, dict) or not {'request', 'object', 'params'} <= set(inputs)
                or not set(inputs) <= INPUT_NAMES):
            raise ValueError('Only request/object/oldObject/params JSON inputs are accepted')
        # Reject NaN, infinities and arbitrary Python objects before conversion.
        json.dumps(inputs, allow_nan=False)
        values = {name: json_to_cel(inputs.get(name)) for name in INPUT_NAMES}
        values['variables'] = celpy.celtypes.MapType({})
        environment = celpy.Environment()
        programs = []
        for expression in expressions:
            receipt = {key: expression[key] for key in ('stage', 'index', 'name')}
            receipt.update(expressionSha256=sha256(expression['expression'].encode()),
                           compiled=False, evaluated=False)
            report['expressions'].append(receipt)
            try:
                tree = environment.compile(expression['expression'])
                program = environment.program(tree)
                receipt['compiled'] = True
                programs.append((expression, receipt, program))
            except Exception as error:
                receipt.update(failure='parse-error', errorType=type(error).__name__)
                programs.append((expression, receipt, None))
        report['compiled'] = all(receipt['compiled'] for receipt in report['expressions'])
        # Keep evaluating independent entries after a failure, so a false match
        # condition or earlier parse error cannot hide untested validations.
        for expression, receipt, program in programs:
            if program is None:
                continue
            try:
                result = program.evaluate(values)
                if isinstance(result, celpy.CELEvalError):
                    raise result
                receipt.update(evaluated=True, resultType=type(result).__name__)
                if expression['stage'] == 'variable':
                    values['variables'][celpy.celtypes.StringType(expression['name'])] = result
                elif isinstance(result, celpy.celtypes.BoolType):
                    receipt['resultBool'] = bool(result)
                    if not result:
                        receipt['failure'] = 'false'
                else:
                    receipt['failure'] = 'nonboolean-result'
            except Exception as error:
                receipt.update(failure='evaluation-error', errorType=type(error).__name__)
        report['evaluated'] = all(receipt['evaluated'] for receipt in report['expressions'])
        successful = report['compiled'] and report['evaluated'] and all(
            'failure' not in receipt for receipt in report['expressions'])
        report.update(allExpressionsTrue=successful,
                      status='all-expressions-true' if successful else 'failed')
    except Exception as error:
        report.update(failure='engine-or-input-error', errorType=type(error).__name__)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        policy, policy_sha = load_policy(args.policy)
        raw = args.inputs.read_bytes()
        value = evaluate_policy(policy, json.loads(raw))
        value.update(policyFileSha256=policy_sha, inputsFileSha256=sha256(raw))
    except Exception as error:
        value = {'status': 'failed', 'compiled': False, 'evaluated': False,
                 'allExpressionsTrue': False, 'failure': 'manifest-or-input-error',
                 'errorType': type(error).__name__, 'limitations': list(LIMITATIONS)}
    encoded = json.dumps(value, indent=2, allow_nan=False) + '\n'
    if args.output:
        # Preserve prior evidence instead of silently overwriting a receipt.
        with args.output.open('x') as output:
            output.write(encoded)
    else:
        print(encoded, end='')
    return 0 if value['allExpressionsTrue'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
