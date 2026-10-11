#!/usr/bin/env python3
"""Default-inert audited expiry cycle over the exact released23 recovery baseline.

Frozen Source CRUD, identity, storage, runtime and finite Stop validators remain
unchanged. A later allocation/history growth needs a separately reviewed input.
"""
import argparse
import copy
import hashlib
import json
import os
import re
from types import ModuleType
from datetime import datetime, timezone
from pathlib import Path

import qualified_restart_window as w
import qualified_recovery_expiry_adapter as a

WINDOW_SHA = a.WINDOW_SHA
INVERSE_SHA = 'b70a544dbbeb4508f9e7d8a571d0a70729068136dc97c8eec7f3131ad0749efa'
MODEL_SHA = '630d43cc115b5bddf3e5d110a25cc891e0941953bbabd833f0a77a3773ad7880'
CONTROL_SHA = 'babeb6eea18821a678b06ce6cc4e6d7ad1bafbc3c543b20522af09d5276fb7dc'
READER_SHA = 'e5be91b7b70cc3c69cba77190d212028508d4eaa19d444c96a475870b09f3bed'
LOADER_SHA = 'b3fd57f64f1dc7e4fe3b09c563b9a347f2767cfecb5de8e444d27668d735d3b9'
PREPARE_SHA = '533131979cd12eb03a6a56084fceb9f61652cc50382510619fd22ea281722f3a'
HARNESS_SHA = 'f656ece163800f2161bea3b067b3c71676e1bda67d21b4a43b9474946a1e84d7'
protected = a.protected
physical_review = a.validate_physical_review


def current_ledger(document, state, *, expected=None):
    """Only the exact23 preimage; no CAS, release, admission or growth approval."""
    expected = document if expected is None else expected
    for value in (document, expected):
        metadata = value.get('metadata', {})
        w.require(value.get('apiVersion') == 'v1' and value.get('kind') == 'ConfigMap'
                  and metadata.get('name') == 'cps-native-gpu-allocations'
                  and metadata.get('namespace') == 'cps-native-system'
                  and type(metadata.get('uid')) is str and metadata['uid']
                  and type(metadata.get('resourceVersion')) is str and metadata['resourceVersion']
                  and not metadata.get('deletionTimestamp'), 'Complete actual native ledger identity required')
    w.closed(state, {'version', 'allocations'})
    w.require(type(state['version']) is int and state['version'] == 1
              and type(state['allocations']) is dict and len(state['allocations']) == 23
              and all(row.get('state') == 'released' for row in state['allocations'].values()),
              'Exact released23 baseline required; future history growth needs a separate review')
    w.require(json.loads(document['data']['state.json']) == state
              and document['data'] == expected['data']
              and all(document['metadata'].get(k) == expected['metadata'].get(k)
                      for k in ('name', 'namespace', 'uid', 'resourceVersion')),
              'Actual native ledger preimage UID/RV/full body changed')
    from cps_compute.native_gpu_control import MeasuredNativeAuthority
    codec = object.__new__(MeasuredNativeAuthority)
    row = next(iter(state['allocations'].values()))
    codec.pool = {k: row[k] for k in ('node', 'node_uid', 'gpu_uuid')}
    codec.pool['memory_budget_mib'] = 1
    codec._validate_allocations(state['allocations'])


def expired_baseline(source, historical, actual):
    w.require(source in w.SELECTED, 'Exact owning Source required')
    w.current_guard(source, historical, actual, w.OLD_EXPIRY)


def binding(source, baseline, ledger, history_pin):
    w.raw_pin(history_pin)
    expired_baseline(source, baseline, baseline)
    state = json.loads(ledger['data']['state.json'])
    current_ledger(ledger, state)
    return {'source': source, 'baseline': copy.deepcopy(baseline),
            'ledger': copy.deepcopy(ledger), 'state': state,
            'history_raw_sha256': history_pin,
            'baseline_full_sha256': w.digest(baseline),
            'baseline_ledger_state_sha256': w.digest(state)}


def runtime_guard(bound, native):
    w.closed(native, {'operator_uid', 'gateway_uid', 'hub_uids', 'node_uid', 'policy_hash',
                     'ledger_uid', 'ledger_resource_version', 'ledger_state', 'pod_absent'})
    w.require(native['ledger_uid'] == bound['ledger']['metadata']['uid']
              and native['ledger_resource_version'] == bound['ledger']['metadata']['resourceVersion']
              and native['ledger_state'] == bound['state'] and native['policy_hash'] == a.POLICY
              and native['pod_absent'] is True,
              'Exact released23 runtime preimage/absence required; growth is not admitted')


def inverse_baseline(source, historical, before, after, receipt, state, registration, ledger_uid):
    """Authenticate the actual completed inverse, not a self-declared baseline."""
    expired_baseline(source, historical, after)
    w.closed(receipt, {'version', 'state', 'operation', 'source', 'actor', 'cycle_id',
        'renewed_at', 'renewed_expires', 'changes', 'qualification', 'workspace_started',
        'profiles_and_ceiling_preserved', 'before_full_sha256', 'after_full_sha256',
        'runtime_before', 'registration_sha256'})
    w.require(type(receipt['version']) is int and receipt['version'] == 1
        and receipt['state'] == 'selected-qualified-expiry-restored-read-back'
        and receipt['operation'] == 'restore-expiry' and receipt['source'] == source
        and receipt['actor'] == w.ACTORS[source] and receipt['qualification'] is False
        and receipt['workspace_started'] is False and receipt['profiles_and_ceiling_preserved'] is True,
        'Actual completed owning Source expiry inverse required')
    w.utc(receipt['renewed_at']); w.utc(receipt['renewed_expires'])
    w.current_guard(source, historical, before, receipt['renewed_expires'])
    w.require(after == w.changed(source, before, w.OLD_EXPIRY)
        and receipt['before_full_sha256'] == w.digest(before)
        and receipt['after_full_sha256'] == w.digest(after)
        and receipt['changes'] == w.changes(before, after)
        and receipt['registration_sha256'] == 'sha256:' + w.digest(registration),
        'Complete actual inverse before/after/expiry/registration chain required')
    native = receipt['runtime_before']
    w.closed(native, {'operator_uid', 'gateway_uid', 'hub_uids', 'node_uid', 'policy_hash',
                     'ledger_uid', 'ledger_resource_version', 'ledger_state', 'pod_absent'})
    w.require(native['ledger_uid'] == ledger_uid and native['ledger_state'] == state
        and native['policy_hash'] == a.POLICY and native['pod_absent'] is True
        and type(native['ledger_resource_version']) is str and native['ledger_resource_version'],
        'Actual inverse must retain the complete released23 preimage and absence')


def ledger_guard(win, bound, state, historical, operation, review, q, *, original_guard=None, original=None):
    original = win.ledger_guard if original is None else original
    # The unchanged original21 body/SDK codec and original19 guard run first.
    # The new operation does not turn their historical preimage into23.
    original(state, historical, 'restore-expiry', review, q, original_guard=original_guard)
    w.require(operation in ('renew', 'restore-expiry') and state == bound['state']
        and review['expected_allocation_count'] == 23
        and review['ledger_uid'] == bound['ledger']['metadata']['uid'],
        'Only the exact released23 current preimage is admitted; history growth needs a new reviewed input')


def add_authority_preimage(q, bound):
    """Refresh the named ledger after all three genuine recovery authorities.

    This hook lives in the genuine frozen context's globals and is reached
    before configured Source construction and on every returned fence.
    """
    ns = q.build_context.__globals__
    original = ns['_recovery_actual_authorities']
    async def actual(backend, state):
        await original(backend, state)
        metadata = bound['ledger']['metadata']
        current = await backend._call(backend.core.read_namespaced_config_map,
                                     metadata['name'], metadata['namespace'])
        current_ledger(current, bound['state'], expected=bound['ledger'])
    ns['_recovery_actual_authorities'] = actual


async def apply(win, bound, settings, review, output, fence, registration, q, *,
                clock=lambda: datetime.now(timezone.utc), original=None):
    w.require(review['source'] == bound['source'], 'Exact bridge Source required')
    original = win.apply if original is None else original
    async def guarded():
        result = await fence()
        runtime_guard(bound, result)
        return result
    result = await original(settings, bound['baseline'], review, output, guarded, registration, q, clock=clock)
    result.update(version=2,
        state='recovery-history-selected-expiry-renewed-read-back' if review['operation'] == 'renew'
              else 'recovery-history-selected-expiry-restored-read-back',
        baseline_full_sha256=bound['baseline_full_sha256'],
        baseline_ledger_state_sha256=bound['baseline_ledger_state_sha256'],
        history_raw_sha256=bound['history_raw_sha256'])
    # Preserve the frozen loop's exact receipt and append a distinct own-cycle
    # receipt. Both writes are exclusive; an interrupted wrapper never upgrades
    # the legacy receipt into inverse authority.
    q.R.write(output / 'cycle-receipt.json', result)
    return result


def cycle_guard(win, bound, before, after, receipt, review, registration):
    w.closed(receipt, {'version', 'state', 'operation', 'source', 'actor', 'cycle_id',
        'renewed_at', 'renewed_expires', 'before_full_sha256', 'after_full_sha256',
        'changes', 'qualification', 'workspace_started', 'profiles_and_ceiling_preserved',
        'runtime_before', 'registration_sha256', 'baseline_full_sha256',
        'baseline_ledger_state_sha256', 'history_raw_sha256'})
    source = bound['source']
    w.require(type(receipt['version']) is int and receipt['version'] == 2
        and receipt['state'] == 'recovery-history-selected-expiry-renewed-read-back'
        and receipt['operation'] == 'renew' and receipt['source'] == source
        and review['source'] == source and receipt['actor'] == w.ACTORS[source]
        and receipt['cycle_id'] == review['cycle_id']
        and receipt['renewed_expires'] == review['renewed_expires']
        and receipt['qualification'] is False and receipt['workspace_started'] is False
        and receipt['profiles_and_ceiling_preserved'] is True
        and all(receipt[k] == bound[k] for k in ('baseline_full_sha256',
            'baseline_ledger_state_sha256', 'history_raw_sha256')),
        'Only this completed recovery-aware own cycle can authorize its inverse')
    win.window(receipt['renewed_expires'], win.utc(receipt['renewed_at']))
    win.current_guard(source, bound['baseline'], before, receipt['renewed_expires'])
    win.current_guard(source, bound['baseline'], after, receipt['renewed_expires'])
    w.require(after == win.changed(source, before, receipt['renewed_expires'])
        and receipt['before_full_sha256'] == win.digest(before)
        and receipt['after_full_sha256'] == win.digest(after)
        and receipt['changes'] == win.changes(before, after)
        and receipt['registration_sha256'] == 'sha256:' + win.digest(registration),
        'Own full rows, exact expiry-only readbacks and registration must match')
    runtime_guard(bound, receipt['runtime_before'])


def verify_sdk():
    from cps_compute import native_gpu_controller, native_gpu_control
    protected(native_gpu_controller.__file__, MODEL_SHA)
    protected(native_gpu_control.__file__, CONTROL_SHA)


def install(win, bound, approval, history, loaded, inverse_before, inverse_receipt):
    """Compose the pinned historical context and genuine Source loop locally."""
    original_load = win.load_frozen
    original_baseline = win.baseline_guard
    original_ledger = win.ledger_guard
    original_context = win.build_context
    original_apply = win.apply

    def load(qualified_raw, renewal_raw, path):
        q = a.adapt_foundation(original_load(qualified_raw, renewal_raw, path),
            qualified_raw, history, loaded, bound['history_raw_sha256'], approval['gateway_image'])
        add_authority_preimage(q, bound)
        return q

    def baseline(source, before, after, receipt, provenance, state, q):
        original_baseline(source, before, after, receipt, provenance, state, q)
        w.require(source == bound['source'] and bound['ledger']['metadata']['uid'] == q.R.BASE_LEDGER_UID,
                  'Current baseline must belong to the original Source/ledger')
        inverse_baseline(source, after, inverse_before, bound['baseline'], inverse_receipt,
                         bound['state'], provenance['registration'], q.R.BASE_LEDGER_UID)

    def ledger(state, historical, operation, review, q, **kw):
        return ledger_guard(win, bound, state, historical, operation, review, q,
                            original=original_ledger, **kw)

    async def context(args, review, *rest):
        w.require(args.source == bound['source'] == approval['source']
                  and review['operation'] == approval['operation'],
                  'Exact Source and explicitly approved bridge operation required')
        return await original_context(args, review, *rest)

    async def write(settings, unused_baseline, review, output, fence, registration, q, **kw):
        return await apply(win, bound, settings, review, output, fence, registration, q,
                           original=original_apply, **kw)

    def cycle(source, unused_baseline, before, after, receipt, review, state, registration, q):
        w.require(source == bound['source'], 'Exact own-cycle Source required')
        return cycle_guard(win, bound, before, after, receipt, review, registration)

    win.load_frozen = load
    win.baseline_guard = baseline
    win.ledger_guard = ledger
    win.build_context = context
    win.apply = write
    win.cycle_guard = cycle
    return win


def main(argv=None):
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--execute', action='store_true')
    names = ('bridge-sha256', 'bridge-review', 'bridge-review-sha256', 'history', 'history-sha256',
        'window-source', 'post-inverse-before', 'post-inverse-before-sha256',
        'post-inverse-after', 'post-inverse-after-sha256', 'post-inverse-receipt',
        'post-inverse-receipt-sha256', 'current-baseline-ledger', 'current-baseline-ledger-sha256',
        'model-source', 'control-source', 'node-source', 'recovery-source')
    for name in names:
        parser.add_argument('--' + name)
    args, rest = parser.parse_known_args(argv)
    if not args.execute:
        print(w.canonical({'state': 'inert', 'api_calls': False, 'writes': False,
                           'workspace_started': False, 'qualification': False}))
        return 0
    w.require(os.geteuid() == 10001 and all(vars(args).values()),
              'Trusted UID10001 and complete protected bridge inputs required')
    protected(__file__, args.bridge_sha256)
    protected(w.__file__, WINDOW_SHA)
    protected(a.__file__, INVERSE_SHA)
    protected(a.r.__file__, READER_SHA)
    protected(a.loader.__file__, LOADER_SHA)
    protected(a.prepare.__file__, PREPARE_SHA)
    protected(a.prepare.p.__file__, HARNESS_SHA)
    approval = a.r.parse(protected(args.bridge_review, args.bridge_review_sha256))
    w.closed(approval, {'version', 'enabled', 'operation', 'source', 'gateway_image',
        'history_raw_sha256', 'adapter_sha256', 'reader_sha256', 'loader_sha256',
        'node_source_sha256', 'historical_node_source_sha256', 'recovery_source_sha256',
        'window_source_sha256', 'inverse_source_sha256', 'baseline_after_raw_sha256',
        'baseline_before_raw_sha256', 'baseline_inverse_receipt_raw_sha256',
        'baseline_ledger_raw_sha256', 'baseline_full_sha256', 'baseline_state_sha256'})
    expected = {'history_raw_sha256': args.history_sha256, 'adapter_sha256': args.bridge_sha256,
        'reader_sha256': READER_SHA, 'loader_sha256': LOADER_SHA,
        'node_source_sha256': a.ACTIVE_AGENT_SHA, 'historical_node_source_sha256': a.HISTORICAL_AGENT_SHA,
        'recovery_source_sha256': a.RECOVERY_SHA, 'window_source_sha256': WINDOW_SHA,
        'inverse_source_sha256': INVERSE_SHA, 'baseline_after_raw_sha256': args.post_inverse_after_sha256,
        'baseline_before_raw_sha256': args.post_inverse_before_sha256,
        'baseline_inverse_receipt_raw_sha256': args.post_inverse_receipt_sha256,
        'baseline_ledger_raw_sha256': args.current_baseline_ledger_sha256}
    w.require(type(approval['version']) is int and approval['version'] == 1
        and approval['enabled'] is True and approval['source'] in w.SELECTED
        and approval['operation'] in ('renew', 'restore-expiry')
        and all(approval[k] == value for k, value in expected.items()),
        'Closed explicit Root bridge review/source/operation/pin binding required')
    for key in ('baseline_full_sha256', 'baseline_state_sha256'):
        w.raw_pin(approval[key])
    baseline = a.r.parse(protected(args.post_inverse_after, args.post_inverse_after_sha256))
    before = a.r.parse(protected(args.post_inverse_before, args.post_inverse_before_sha256))
    receipt = a.r.parse(protected(args.post_inverse_receipt, args.post_inverse_receipt_sha256))
    ledger = a.r.parse(protected(args.current_baseline_ledger, args.current_baseline_ledger_sha256))
    bound = binding(approval['source'], baseline, ledger, args.history_sha256)
    w.require(bound['baseline_full_sha256'] == approval['baseline_full_sha256']
        and bound['baseline_ledger_state_sha256'] == approval['baseline_state_sha256'],
        'Fresh actual full Source and native ledger canonical digests required')
    history = a.r.parse(protected(args.history, args.history_sha256))
    validators = a.prepare.bundle(args.model_source, args.control_source, args.node_source,
                                 a.HISTORICAL_AGENT_SHA, args.recovery_source, a.RECOVERY_SHA)
    loaded = a.loader.load_sources(validators)
    verify_sdk()
    win = ModuleType('pinned_recovery_restart_foundation')
    win.__file__ = args.window_source
    exec(compile(protected(args.window_source, WINDOW_SHA), args.window_source, 'exec'), win.__dict__)
    install(win, bound, approval, history, loaded, before, receipt)
    return win.main(['--execute', *rest])


if __name__ == '__main__':
    main()
