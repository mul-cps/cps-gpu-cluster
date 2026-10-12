#!/usr/bin/env python3
"""Bind the unchanged trusted probes to the two current approved 5/10 GiB groups.

Local preparation only. Root supplies current private captures and still owns
normal Start/Stop, fresh host preflight, hardware execution and witness review.
"""
import argparse
import json
from pathlib import Path

import prepare_harness as h

PROFILE_CAPS = {'interactive-shared-5': 5120, 'interactive-shared-10': 10240}
# Canonical reviewed approval subtree at 079b2b6; changing membership, storage,
# owner, course or scope requires another review rather than self-rehashing it.
APPROVALS_SHA256 = '3449819d393ed8026353effa57e9b4b0265779e0ef547179dc6c8e1cf72c74c5'
GATE_IMAGE = 'ghcr.io/mul-cps/cps-compute@sha256:bc5b128f582641eae8395e1121d1fb248eddc39a56c9e863b7c564badd94b167'
CONTROLLER_SHA256 = '630d43cc115b5bddf3e5d110a25cc891e0941953bbabd833f0a77a3773ad7880'
LEGACY_CONTROLLER_SHA256 = 'f40ef40f71c9f1206f23fb7052fd69aafd103c0f03a24e6bf3987395dacfd179'


def read_input(pin):
    h.file_pin(pin)
    return h.parse(h.read_pinned(Path(pin['path']), pin['sha256'], private=True))


def validate_inputs(manifest):
    """Current group mode, actual Pod intent and both exact durable gate seals."""
    from cps_compute import native_gpu_controller as controller
    from cps_compute.native_groups import NativeGroupDeployment, canonical_sha256
    from cps_compute.native_gpu_runtime import validate_native_pod_intent, validate_native_cap_receipt
    from cps_compute.policy import Policy

    h.require(isinstance(manifest, dict) and set(manifest) == {'version', 'state', 'binding',
        'policy', 'native_groups', 'sealed_targets'} and type(manifest['version']) is int
        and manifest['version'] == 1 and manifest['state'] == 'Root-reviewed-current-group-plan',
        'Closed explicit current-group preparation manifest required')
    h.require(h.sha(Path(controller.__file__).read_bytes()) == CONTROLLER_SHA256,
              'Exact reviewed native controller models required')
    binding = h._validate_binding(read_input(manifest['binding']), 'interactive-shared-')
    policy = Policy(read_input(manifest['policy']))
    config = read_input(manifest['native_groups'])
    deployment = NativeGroupDeployment.from_config(config, policy)
    h.require(deployment is not None and deployment.policy_hash == binding['policy_hash'] == policy.hash,
              'Actual enabled group-mode deployment and current policy required')
    h.require(config['evidence']['version'] == 2 and config['evidence']['profile_caps'] == PROFILE_CAPS
        and deployment.gate_image == GATE_IMAGE
        and canonical_sha256(deployment.workspaces) == 'sha256:' + APPROVALS_SHA256,
        'Only the exact reviewed CPS B5 and CIT A10 group approvals allowed')
    pool = deployment.node_pool
    h.require(all(pool[k] == binding['pool'][k] for k in
        ('node', 'node_uid', 'boot_id', 'gpu_uuid', 'driver_generation'))
        and type(pool['max_workspaces']) is int and pool['max_workspaces'] == 2
        and type(pool['memory_budget_mib']) is int and pool['memory_budget_mib'] == 15360,
        'Current group placement, epoch, two slots and 15GiB budget required')
    seals = manifest['sealed_targets']
    h.require(isinstance(seals, list) and len(seals) == 2, 'Both actual Pod lifetime seals required')
    identities = set()
    for target, row in zip(binding['targets'], seals):
        h.require(isinstance(row, dict) and set(row) == {'pod_uid', 'journal', 'gate_receipt'}
            and row['pod_uid'] == target['pod_uid'], 'Ordered actual CPS5/CIT10 PodUID seals required')
        approval = deployment.approval(target['source'], target['workspace'])
        h.require(approval is not None and approval['profiles'] == [target['profile']]
            and approval['namespace'] == target['namespace'] and approval['pod'] == target['name']
            and deployment.cap_mib(target['profile']) == target['cap_mib'],
            'Actual group approval differs from requested profile or Pod')
        record = controller.CapRecord.from_dict(read_input(row['journal']))
        expected_intent = {k: target[k] for k in ('namespace', 'name', 'pod_uid', 'spec_sha256', 'cap_mib')}
        expected_intent.update({k: binding['pool'][k] for k in ('node', 'node_uid', 'gpu_uuid')},
                               policy_hash=binding['policy_hash'])
        h.require(record.state == 'sealed' and record.intent.to_dict() == expected_intent
            and record.identity.epoch == controller.DriverEpoch(pool['node_uid'], pool['boot_id'],
                pool['driver_generation'], pool['gpu_uuid']),
            'Exact current sealed native journal intent, cap and epoch required')
        key = (record.identity.cgroup_device, record.identity.cgroup_inode)
        h.require(key not in identities, 'Distinct actual native Pod-parent lifetimes required')
        identities.add(key)
        gate = read_input(row['gate_receipt'])
        h.require(gate == record.receipt(), 'Actual public gate must equal the protected durable seal')
        validate_native_cap_receipt(gate, expected_intent, boot_id=pool['boot_id'],
            pid_start_ticks=record.identity.pid_start_ticks, driver_generation=pool['driver_generation'])
        validate_native_pod_intent(read_input(target['pod_capture']), expected_intent)
    return binding, {'preparation_mode': 'current-approved-groups',
        'fresh_cross_pod_hardware_qualified': False,
        'group_evidence_sha256': config['evidence_sha256'],
        'current_controller_sha256': CONTROLLER_SHA256,
        'approved_workspaces_sha256': 'sha256:' + APPROVALS_SHA256,
        'current_group_inputs': [manifest['binding'], manifest['policy'], manifest['native_groups'],
            *(pin for row in seals for pin in (row['journal'], row['gate_receipt']))]}


def validate_retired(retired, binding):
    return h._validate_retired(retired, binding, controller_sha=CONTROLLER_SHA256)


def render_sources(sources, binding, retired, *, native_binary=None):
    h._validate_binding(binding, 'interactive-shared-')
    out = h._render_validated_sources(sources, binding, retired, native_binary=native_binary)
    old_pre = out['run_group_acceptance.py']
    pre = h.replace(old_pre.decode(), 'CONTROLLER_SHA = ' + repr(LEGACY_CONTROLLER_SHA256),
                    'CONTROLLER_SHA = ' + repr(CONTROLLER_SHA256)).encode()
    out['run_group_acceptance.py'] = pre
    # Every trusted wrapper still pins the exact rendered preflight. Source
    # protocol bodies, kernel witnesses, caps and deadlines are unchanged.
    for name, raw in list(out.items()):
        if name != 'run_group_acceptance.py' and name.endswith('.py'):
            out[name] = raw.replace(h.sha(old_pre).encode(), h.sha(pre).encode())
    return out


def prepare(manifest_path, manifest_sha, source_root, output, *, native_binary_path=None,
            native_binary_sha=None, native_build_path=None, native_build_sha=None):
    manifest = read_input({'path': str(manifest_path), 'sha256': manifest_sha})
    binding, context = validate_inputs(manifest)
    context['current_group_manifest'] = {'path': str(manifest_path), 'sha256': manifest_sha}
    # Keep canonical profile strings throughout. The original preparer still
    # validates fresh NVML, complete retirement history, exact source pins,
    # admitted Ready Pod/gate/image guards and the actual offline native ELF.
    return h._prepare_validated_binding(binding, manifest['binding']['sha256'], source_root, output,
        native_binary_path=native_binary_path, native_binary_sha=native_binary_sha,
        native_build_path=native_build_path, native_build_sha=native_build_sha, receipt_context=context,
        retirement_validator=validate_retired, source_renderer=render_sources)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--output', type=Path)
    for field in ('native-import-binary', 'native-import-build-receipt'):
        parser.add_argument('--' + field, type=Path)
        parser.add_argument('--' + field + '-sha256')
    args = parser.parse_args(argv)
    if not args.prepare:
        print(json.dumps({'state': 'inert', 'gpu_calls': False, 'api_calls': False,
                          'hardware_qualification': False, 'production_qualified': False}))
        return
    h.require(args.manifest is not None and args.manifest_sha256 and args.source_root is not None
        and args.output is not None, 'Actual pinned private current-group manifest, sources and fresh output required')
    receipt = prepare(args.manifest, args.manifest_sha256, args.source_root, args.output,
        native_binary_path=args.native_import_binary, native_binary_sha=args.native_import_binary_sha256,
        native_build_path=args.native_import_build_receipt, native_build_sha=args.native_import_build_receipt_sha256)
    print(json.dumps({'state': receipt['state'], 'api_calls': False, 'gpu_calls': False,
        'hardware_qualification': False, 'output': str(args.output)}))


if __name__ == '__main__': main()
