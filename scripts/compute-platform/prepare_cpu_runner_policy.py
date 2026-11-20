#!/usr/bin/env python3
"""Prepare a pinned CPU-runner policy revision offline; never activate or deploy."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / 'platform-staging/gpu/native-group-pilot/qualification/cpu-runner-policy-20261012/record.json'
spec = importlib.util.spec_from_file_location('compute_policy_compiler', ROOT / 'scripts/compile_compute_policy.py')
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)
GATES = sorted(compiler.NATIVE_GROUP_GATES | {'capacity'})
INPUTS = {'catalog.json', 'native-group-evidence.json', 'native-groups.json',
    'cps-settings.json', 'cit-settings.json', 'node-config.json',
    'cps-workspace-registration.json', 'cit-workspace-registration.json'} | {
        'attestation-' + gate + '.json' for gate in GATES}


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def checksum(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pinned(path, expected):
    raw = Path(path).read_bytes()
    require(checksum(raw) == expected, 'changed reviewed source bytes: ' + Path(path).name)
    return compiler._decode_json(raw)


def validate_cpu_receipt(receipt, image):
    require(receipt.get('schema') == 'cps-cpu-runner-local-qualification-v1'
        and receipt.get('image') == image and type(receipt.get('uid')) is int
        and receipt['uid'] == 10001 and receipt.get('gid') == 100
        and receipt.get('working_directory') == '/tmp'
        and all(receipt.get(key) is True for key in ('input_immutable', 'outputs_stripped', 'fresh_kernel'))
        and receipt.get('gpu_calls') is False and receipt.get('network') == 'none',
        'exact locally qualified CPU runner environment required')
    success, failure = receipt.get('success', {}), receipt.get('failure', {})
    require(type(success.get('exit_code')) is int and success['exit_code'] == 0
        and type(failure.get('exit_code')) is int and failure['exit_code'] != 0
        and success.get('executed_notebook_retained') is True
        and failure.get('executed_notebook_retained') is True
        and success.get('selected_local_import_passed') is True
        and success.get('parameters') == {'count': 3, 'fail': False}
        and failure.get('parameters') == {'count': 3, 'fail': True},
        'successful and failed immutable typed-parameter notebook receipts required')


def admission_parameters(current, image):
    require(isinstance(current, dict) and isinstance(current.get('approved-images'), str)
        and isinstance(current.get('executor-image'), str), 'explicit current admission data required')
    images = current['approved-images'].split(',')
    require(current['executor-image'] in images, 'current executor must remain explicitly approved')
    updated = copy.deepcopy(current)
    if image not in images:
        updated['approved-images'] += ',' + image
    return updated


def render(ready, current_node, cpu_receipt, record_path=RECORD, admission_data=None):
    record = compiler._decode_json(Path(record_path).read_bytes())
    require(record.get('schema') == 'cps-cpu-runner-policy-revision-v1'
        and set(record['inputs']) == INPUTS and record['version'] == '0.1.2',
        'exact CPU-only revision input contract required')
    inputs = {name: pinned(Path(ready) / name, digest) for name, digest in record['inputs'].items()}
    receipt = pinned(cpu_receipt, record['cpu_receipt_sha256'])
    validate_cpu_receipt(receipt, record['runner_image'])
    current = pinned(current_node, record['current_node_config_sha256'])
    require(set(current) == {'config.json'} and isinstance(current['config.json'], str),
        'current sanitized ConfigMap data wrapper required')
    current = compiler._decode_json(current['config.json'])
    baseline_node = inputs['node-config.json']
    require({k: v for k, v in current.items() if k != 'terminal_history'}
        == {k: v for k, v in baseline_node.items() if k != 'terminal_history'},
        'current node authority must equal the frozen authority except historical custody')
    require(isinstance(current.get('terminal_history'), dict), 'preserved current terminal history required')
    old_catalog, old_proof = inputs['catalog.json'], inputs['native-group-evidence.json']
    old_hash = record['baseline_policy_hash']
    old_artifacts = {gate: str(Path(ready) / ('attestation-' + gate + '.json')) for gate in GATES}
    baseline = compiler.compile_catalog(old_catalog, native_group_evidence=old_proof,
        native_group_artifacts=old_artifacts)
    require(baseline['policyHash'] == old_hash == current['policy_hash'], 'exact baseline policy required')
    require(set(old_proof['profile_caps']) == {'interactive-shared-5', 'interactive-shared-10'},
        'only the existing two limited GPU profile approvals may be preserved')
    groups = inputs['native-groups.json']
    require(groups['policy_hash'] == old_hash and groups['evidence'] == old_proof
        and groups['evidence_sha256'] == 'sha256:' + checksum(compiler.canonical(old_proof))
        and groups['node_pool'] == old_proof['node_pool']
        and set(groups['workspaces']) == {'cps:native-group-b', 'cit:native-group-a'},
        'exact unchanged limited group deployment required')
    catalog = copy.deepcopy(old_catalog)
    require(catalog['profiles']['batch-cpu']['images'] == []
        and record['runner_image'] not in catalog['approvedImages'], 'empty baseline CPU image binding required')
    catalog['version'] = record['version']
    catalog['approvedImages'].append(record['runner_image'])
    catalog['profiles']['batch-cpu']['images'] = [record['runner_image']]
    for name in old_proof['profile_caps']:
        catalog['profiles'][name]['gpu']['qualification']['policyVersion'] = record['version']
    new_hash = 'sha256:' + checksum(compiler.canonical(catalog))
    if 'target_policy_hash' in record:
        require(new_hash == record['target_policy_hash'], 'exact reviewed target policy required')
    proof = copy.deepcopy(old_proof)
    proof.update(policy_hash=new_hash, policy_version=record['version'])
    reports = {}
    for gate in GATES:
        report = {'gate': gate, 'passed': True, 'policy_hash': new_hash,
            'policy_version': record['version'], 'qualification_kind': 'cpu-runner-policy-compatibility',
            'hardware_test_performed': False, 'production_qualified': False, 'full_fleet_qualified': False,
            'qualified_scope': 'existing-cps-5-cit-10-only', 'original_policy_hash': old_hash,
            'original_policy_version': old_catalog['version'],
            'original_report_sha256': record['inputs']['attestation-' + gate + '.json'],
            'review_basis': 'Only batch-cpu image approval and policy version metadata change; '
                'GPU resources, workload/gate images, driver pins, pool, members and storage are unchanged.',
            'cpu_local_receipt_sha256': record['cpu_receipt_sha256']}
        reports[gate] = report
        digest = 'sha256:' + checksum(encoded(report))
        if gate == 'capacity': proof['capacity_evidence_sha256'] = digest
        else: proof['gates'][gate]['evidence_sha256'] = digest
    # Run the unchanged compiler over the explicit compatibility attestations.
    # These attestations preserve historical reviewed scope, not new GPU measurements.
    with tempfile.TemporaryDirectory(prefix='cps-cpu-policy-') as temporary:
        paths = {}
        for gate, report in reports.items():
            path = Path(temporary) / (gate + '.json')
            path.write_bytes(encoded(report)); path.chmod(0o600); paths[gate] = str(path)
        policy = compiler.compile_catalog(catalog, native_group_evidence=proof, native_group_artifacts=paths)
    groups = copy.deepcopy(groups)
    groups.update(policy_hash=new_hash, evidence=proof,
        evidence_sha256='sha256:' + checksum(compiler.canonical(proof)))
    node = copy.deepcopy(current); node['policy_hash'] = new_hash
    documents = {'catalog.json': catalog, 'native-group-evidence.json': proof,
        'native-groups.json': groups, 'node-config.json': node, 'cpu-local-qualification.json': receipt,
        'gateway-runtime-overlay.json': {'policy_hash': new_hash, 'nativeGpuGroups': groups},
        'compiled/policy.json': policy, 'compiled/native-group-evidence.json': proof,
        'compiled/queues-priorities.json': compiler.manifests(policy),
        'compiled/release-lock.json': {'policyVersion': record['version'], 'policyHash': new_hash,
            'status': 'unqualified', 'compatibility': policy['compatibility']},
        'acceptance.json': {'status': 'offline-cpu-only-policy-revision', 'target_policy_hash': new_hash,
            'baseline_policy_hash': old_hash, 'activationPerformed': False, 'hardwareAcceptancePerformed': False,
            'cpu_runner_locally_qualified': True, 'cluster_notebook_execution_qualified': False,
            'production_qualified': False, 'full_fleet_qualified': False,
            'current_node_config_sha256': record['current_node_config_sha256'],
            'terminal_history_entries_preserved': len(current['terminal_history']),
            'scope': 'batch-cpu runner image plus unchanged limited CPS5/CIT10 GPU groups'}}
    for source in ('cps', 'cit'):
        settings = copy.deepcopy(inputs[source + '-settings.json'])
        require(settings['source'] == source and settings['groupDeployment'] == inputs['native-groups.json'],
            'exact source-owned baseline Hub settings required')
        settings['groupDeployment'] = groups
        documents[source + '-settings.json'] = settings
        registration = copy.deepcopy(inputs[source + '-workspace-registration.json'])
        require(registration['policy_hash'] == old_hash
            and registration['workspace'] == 'native-group-' + ('b' if source == 'cps' else 'a'),
            'exact source-owned baseline audited registration required')
        registration['policy_hash'] = new_hash
        documents[source + '-workspace-registration.json'] = registration
    documents.update({'compatibility/attestation-' + gate + '.json': report for gate, report in reports.items()})
    if 'admission_data_sha256' in record:
        require(admission_data is not None, 'pinned current ComputeAdmissionPolicy data required')
        admission = pinned(admission_data, record['admission_data_sha256'])
        documents['admission-data.json'] = admission_parameters(admission, record['runner_image'])
        documents['admission-requirements.json'] = {
            'apiVersion': 'compute.cps.unileoben.ac.at/v1alpha1', 'kind': 'ComputeAdmissionPolicy',
            'namespace': 'cps-compute', 'name': 'cps-admission-policy',
            'current_data_sha256': record['admission_data_sha256'],
            'changed_keys': ['approved-images'] if admission != documents['admission-data.json'] else [],
            'executor_unchanged': True, 'parameterNotFoundAction': 'Deny',
            'source': 'platform-staging/admission.yaml:103',
            'policy_hash_binding_required_by_image_validation': False,
            'activationPerformed': False, 'server_dry_run_required': True}
    return documents


def prepare(ready, current_node, cpu_receipt, output, record_path=RECORD, admission_data=None):
    output = Path(output)
    require(not output.exists() and not output.is_symlink(), 'a new output directory is required')
    documents = render(ready, current_node, cpu_receipt, record_path, admission_data)
    documents['native-group-artifacts.json'] = {gate: str(output.resolve() / 'compatibility' /
        ('attestation-' + gate + '.json')) for gate in GATES}
    output.mkdir(mode=0o700)
    for name, value in documents.items():
        path = output / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(encoded(value))
        path.chmod(0o600)
    return {'rendered': True, 'activationPerformed': False,
        'target_policy_hash': documents['compiled/policy.json']['policyHash'], 'files': sorted(documents)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render', action='store_true')
    parser.add_argument('--ready', type=Path)
    parser.add_argument('--current-node-config', type=Path)
    parser.add_argument('--cpu-receipt', type=Path)
    parser.add_argument('--admission-data', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if not args.render:
        print(json.dumps({'rendered': False, 'activationPerformed': False})); return
    if any(value is None for value in (args.ready, args.current_node_config, args.cpu_receipt, args.output)):
        parser.error('--render requires --ready, --current-node-config, --cpu-receipt and --output')
    print(json.dumps(prepare(args.ready, args.current_node_config, args.cpu_receipt, args.output,
        admission_data=args.admission_data)))


if __name__ == '__main__':
    main()
