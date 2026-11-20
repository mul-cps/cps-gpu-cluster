"""Default-inert four-fixture expiry cycle on the existing qualified runtime.

No Start, profile migration, native authority mutation, or hardware approval.
The trusted operator supplies fresh protected reviews and executes normal Source
membership and central grant PUTs. Existing historical receipts remain immutable.
"""
import argparse
import asyncio
import copy
import hashlib
import json
import os
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

QUALIFIED_SHA = '79216423877d8079499c13b8d4f6c5abb90077a9174fd9d3a6e2d295bd166990'
RENEWAL_SHA = '360887dcca0c5d44aa42cf8ba4d6b3e86a7a3c45e1c992ac063cda01c0bd9e93'
BASELINE_LEDGER_SHA = '7740a52ad0858249d60f07166c2405484f104ed4ce536bc37a3c5556b89e5059'
OLD_EXPIRY = '2026-10-11T11:27:43.168759+00:00'
SELECTED = {'cps': ('cpsgpumemberc', 'cpsgpumemberd'), 'cit': ('citgpumembera', 'citgpumemberb')}
ACTORS = {'cps': 'bjoern', 'cit': 'akadmin'}
BASELINE_PINS = {
 'cps': {'before': '7c84f22565eca958e7ecf342a03813aa5da5b70280d3bc7b0eeb08b5cad4724b', 'after': 'c6cb7cd85a7f4561a0e56f12b0278462c0ec4c86e1fac8d8f00392ead79f4e1f', 'receipt': '6ba1e3343edfc41fc88357604e0442c2a2f9307ffeab901cbf3b88c28b50c5c7'},
 'cit': {'before': 'd7f502f20f9d006b25750366a60f63ccb806fc9217b8bf935d0d8e347f8fd89a', 'after': '90db5f08ed98af80264927e2e4471b3cd3dab67297c0ec76f275d2c0a2c61ad4', 'receipt': '3c061198996d3c82c5c2cb48257da0781eafc39430477081774976529f08dd3b'}}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def closed(value, keys):
    require(type(value) is dict and set(value) == set(keys), 'Closed actual input required')


def raw_pin(value):
    require(type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value), 'Exact raw/canonical SHA256 required')


def utc(value):
    require(type(value) is str, 'Explicit UTC timestamp required')
    stamp = datetime.fromisoformat(value)
    require(stamp.tzinfo is not None and stamp.utcoffset().total_seconds() == 0, 'Explicit UTC timestamp required')
    return stamp.astimezone(timezone.utc)


def window(value, now):
    require(now.tzinfo is not None and now.utcoffset().total_seconds() == 0, 'Actual execution UTC clock required')
    stamp = utc(value)
    require(stamp.date() == now.date() and 0 < (stamp - now).total_seconds() <= 3600, 'Positive same-day window at most sixty minutes required')
    return stamp


def load_frozen(qualified_raw, renewal_raw, qualified_path='frozen-qualified-expiry.py'):
    require(hashlib.sha256(qualified_raw).hexdigest() == QUALIFIED_SHA and hashlib.sha256(renewal_raw).hexdigest() == RENEWAL_SHA, 'Exact frozen qualified foundations required')
    ns = {'__name__': 'frozen_qualified_expiry', '__file__': qualified_path}
    exec(compile(qualified_raw, qualified_path, 'exec'), ns)
    q = SimpleNamespace(**ns)
    q.install_base(renewal_raw)
    # install_base updates its original globals; keep the exported R in sync.
    q.R = ns['R']
    return q


def changed(source, full, expiry):
    require(source in SELECTED, 'Exact selected Source required')
    out = copy.deepcopy(full)
    ids = {'native-pilot-' + u for u in SELECTED[source]}
    rows = out['records']['memberships']
    require({x['id'] for x in rows if x['id'] in ids} == ids, 'Both exact existing selected memberships required')
    for kind in ('records', 'all_records'):
        for row in out[kind]['memberships']:
            if row.get('id') in ids:
                row['expires'] = expiry
    for username in SELECTED[source]:
        person = out['people'][username]
        rows = out['grants'][person]
        grant_id = 'native-pilot-' + source + '-' + username
        require(len(rows) == 1 and rows[0]['id'] == grant_id, 'One exact existing selected grant required')
        rows[0]['expires'] = expiry
    return out


def current_guard(source, baseline, current, expiry):
    closed(current, baseline.keys())
    normalized = copy.deepcopy(current)
    actor = current['actor_model']
    require(actor.get('name') == ACTORS[source] and actor.get('admin') is True, 'Actual owning Hub admin required')
    normalized['actor_model'] = baseline['actor_model']
    ids = {'native-pilot-' + u for u in SELECTED[source]}
    for kind in ('records', 'all_records'):
        for row in normalized[kind]['memberships']:
            if row.get('id') in ids:
                require(row.get('expires') in (OLD_EXPIRY, expiry), 'Only exact original or cycle expiry may be resumed')
                row['expires'] = OLD_EXPIRY
    for username in SELECTED[source]:
        person = baseline['people'][username]
        for row in normalized['grants'][person]:
            require(row.get('expires') in (OLD_EXPIRY, expiry), 'Only exact original or cycle grant expiry may be resumed')
            row['expires'] = OLD_EXPIRY
    require(normalized == baseline, 'Complete qualified Source/grants/aliases/remainder must remain unchanged')


def baseline_guard(source, before, after, receipt, history, state, q):
    require(source in SELECTED, 'Exact Source required')
    closed(history, {'original', 'renewal_after', 'renewal_receipt', 'grant_before', 'grant_receipt', 'handover_receipt', 'registration'})
    expected = q.bind_forward(history['original'], history['renewal_after'], history['renewal_receipt'], history['grant_before'], history['grant_receipt'], history['handover_receipt'], history['registration'], datetime.now(timezone.utc))
    q.current_guard(expected, before, history['renewal_receipt']['renewed_expires'])
    require(before == q.set_scoped(before, q.R.state_part(expected)), 'Actual completed qualified before rows required')
    require(after == q.expired(before), 'Actual qualified baseline must restore every original expiry only')
    closed(receipt, {'version', 'state', 'operation', 'source', 'actor', 'qualification', 'old5_runtime_restored', 'workspace_started', 'profiles_and_ceiling_preserved', 'original_raw_sha256', 'provenance_sha256', 'physical_retirement_review_sha256', 'changes', 'runtime_before', 'registration_sha256'})
    require(type(receipt['version']) is int and receipt['version'] == 1 and receipt['state'] == 'qualified-fixtures-stopped-expiry-revoked' and receipt['operation'] == 'expire-qualified-fixtures' and receipt['source'] == source and receipt['actor'] == ACTORS[source] and receipt['qualification'] is False and receipt['old5_runtime_restored'] is False and receipt['workspace_started'] is False and receipt['profiles_and_ceiling_preserved'] is True and receipt['original_raw_sha256'] == q.R.ORIGINAL_SHAS[source], 'Actual completed qualified expiry receipt required')
    require(sorted(receipt['changes'], key=lambda x: (x['kind'], x['id'])) == q.expected_changes(before, after), 'Complete original expiry-only readback chain required')
    require(receipt['registration_sha256'] == q.sha(history['registration']) and receipt['runtime_before']['ledger_state'] == state and receipt['runtime_before']['ledger_uid'] == q.R.BASE_LEDGER_UID and receipt['runtime_before']['policy_hash'] == q.POLICY and receipt['runtime_before']['pod_absent'] is True, 'Original released twenty-one and exact registration must bind completed expiry')
    closed(receipt['provenance_sha256'], q.PROVENANCE)
    for key in q.PROVENANCE:
        raw_pin(receipt['provenance_sha256'][key])
    require(type(state) is dict and set(state) == {'version', 'allocations'} and state['version'] == 1 and len(state['allocations']) == 21 and all(r['state'] == 'released' for r in state['allocations'].values()), 'Exact released twenty-one baseline required')


def ledger_guard(state, baseline, operation, review, q, *, original_guard=None):
    closed(state, {'version', 'allocations'})
    require(type(state['version']) is int and state['version'] == 1 and type(state['allocations']) is dict and type(review['expected_allocation_count']) is int and review['ledger_uid'] == q.R.BASE_LEDGER_UID and digest(state) == review['ledger_state_sha256'], 'Exact reviewed native ledger identity/count/body required')
    count = len(state['allocations'])
    require(count == review['expected_allocation_count'] and (count == 21 if operation == 'renew' else 21 <= count <= 32) and all(r.get('state') == 'released' for r in state['allocations'].values()), 'All actual native claims must be released within the reviewed bounded count')
    require(len(baseline['allocations']) == 21 and all(state['allocations'].get(k) == v for k, v in baseline['allocations'].items()), 'Every original twenty-one allocation body must remain unchanged')
    (original_guard or q.R.ledger_guard)(state, review, 'restore-expiry')
    # Run the genuine SDK's read-only record codec. No backend is constructed,
    # and no admission, enrollment, cleanup, or CAS operation is called here.
    from cps_compute.native_gpu_control import MeasuredNativeAuthority
    codec = object.__new__(MeasuredNativeAuthority)
    first = next(iter(baseline['allocations'].values()))
    codec.pool = {k: first[k] for k in ('node', 'node_uid', 'gpu_uuid')}
    codec.pool['memory_budget_mib'] = 1
    codec._validate_allocations(state['allocations'])


def request_guard(review, now, *, capture=False):
    closed(review, {'version', 'enabled', 'operation', 'source', 'actor', 'cycle_id', 'observed_at', 'source_writers_stopped', 'fixture_starts_excluded', 'source_token_custody', 'runtime_review_sha256', 'physical_retirement_review_sha256', 'current_full_sha256', 'renewed_expires', 'provenance_sha256', 'cycle_provenance_sha256'})
    source = review['source']
    require(type(review['version']) is int and review['version'] == 1 and review['enabled'] is True and source in SELECTED and review['actor'] == ACTORS[source] and review['operation'] in ('renew', 'restore-expiry') and review['source_writers_stopped'] is True and review['fixture_starts_excluded'] is True and review['source_token_custody'] == 'Root-exclusive', 'Explicit bounded Root freeze/custody/operation review required')
    require(str(uuid.UUID(review['cycle_id'])) == review['cycle_id'] and uuid.UUID(review['cycle_id']).int != 0, 'Exact nonzero cycle UUID required')
    require(0 <= (now - utc(review['observed_at'])).total_seconds() <= 600, 'Fresh actual Root review required')
    require(type(capture) is bool and (capture or review['current_full_sha256'] is not None), 'Actual reviewed full current state required for writes')
    closed(review['provenance_sha256'], {'renewal_after', 'renewal_receipt', 'grant_before', 'grant_receipt', 'handover_receipt', 'registration'})
    pins = [review['runtime_review_sha256'], review['physical_retirement_review_sha256'], *review['provenance_sha256'].values()]
    if review['current_full_sha256'] is not None:
        pins.append(review['current_full_sha256'])
    if review['operation'] == 'renew':
        require(review['cycle_provenance_sha256'] is None, 'New cycle may not fabricate prior renewal provenance')
        window(review['renewed_expires'], now)
    else:
        utc(review['renewed_expires'])
        closed(review['cycle_provenance_sha256'], {'before_full', 'after_full', 'receipt'})
        pins.extend(review['cycle_provenance_sha256'].values())
    for pin in pins:
        raw_pin(pin)


def changes(before, after):
    out = []
    for old, new in zip(before['records']['memberships'], after['records']['memberships']):
        if old != new:
            out.append({'kind': 'memberships', 'id': old['id'], 'before': old, 'after': new})
    for person, rows in before['grants'].items():
        for old, new in zip(rows, after['grants'][person]):
            if old != new:
                out.append({'kind': 'compute-grants', 'id': old['id'], 'before': old, 'after': new})
    return sorted(out, key=lambda x: (x['kind'], x['id']))


def cycle_guard(source, baseline, before, after, receipt, review, baseline_state, registration, q):
    closed(receipt, {'version', 'state', 'operation', 'source', 'actor', 'cycle_id', 'renewed_at', 'renewed_expires', 'before_full_sha256', 'after_full_sha256', 'changes', 'qualification', 'workspace_started', 'profiles_and_ceiling_preserved', 'runtime_before', 'registration_sha256'})
    require(type(receipt['version']) is int and receipt['version'] == 1 and receipt['state'] == 'selected-qualified-expiry-renewed-read-back' and receipt['operation'] == 'renew' and receipt['source'] == source and receipt['actor'] == ACTORS[source] and receipt['cycle_id'] == review['cycle_id'] and receipt['renewed_expires'] == review['renewed_expires'] and receipt['qualification'] is False and receipt['workspace_started'] is False and receipt['profiles_and_ceiling_preserved'] is True, 'Actual completed bounded four-fixture cycle receipt required')
    window(receipt['renewed_expires'], utc(receipt['renewed_at']))
    current_guard(source, baseline, before, receipt['renewed_expires'])
    current_guard(source, baseline, after, receipt['renewed_expires'])
    require(after == changed(source, before, receipt['renewed_expires']) and receipt['before_full_sha256'] == digest(before) and receipt['after_full_sha256'] == digest(after) and receipt['changes'] == changes(before, after), 'Own complete expiry-only cycle before/after chain required')
    runtime = receipt['runtime_before']
    closed(runtime, {'operator_uid', 'gateway_uid', 'hub_uids', 'node_uid', 'policy_hash', 'ledger_uid', 'ledger_resource_version', 'ledger_state', 'pod_absent'})
    require(runtime['ledger_state'] == baseline_state and runtime['ledger_uid'] == q.R.BASE_LEDGER_UID and runtime['policy_hash'] == q.POLICY and runtime['pod_absent'] is True and type(runtime['ledger_resource_version']) is str and runtime['ledger_resource_version'] and receipt['registration_sha256'] == q.sha(registration), 'Own initial renewal must bind complete original21, absence and exact qualified registration')
    ledger_guard(runtime['ledger_state'], baseline_state, 'renew', {'ledger_uid': runtime['ledger_uid'], 'ledger_state_sha256': digest(runtime['ledger_state']), 'expected_allocation_count': 21}, q)


async def apply(settings, baseline, review, output, fence, read_registration, q, *, clock=lambda: datetime.now(timezone.utc)):
    from e2x_course_hub.cps.audit import actor_context
    source = review['source']
    request_guard(review, clock())
    provider, compute = settings['course_provider'], settings['compute_policy']
    token = actor_context.set(ACTORS[source])
    expiry = review['renewed_expires'] if review['operation'] == 'renew' else OLD_EXPIRY
    receipt = {'version': 1, 'state': 'incomplete', 'operation': review['operation'], 'source': source, 'actor': ACTORS[source], 'cycle_id': review['cycle_id'], 'renewed_at': clock().isoformat(), 'renewed_expires': review['renewed_expires'], 'changes': [], 'qualification': False, 'workspace_started': False, 'profiles_and_ceiling_preserved': True}
    try:
        native = await fence()
        registration = await read_registration()
        first = await q.R.capture(settings, source)
        current_guard(source, baseline, first, review['renewed_expires'])
        require(digest(first) == review['current_full_sha256'], 'Actual Root-reviewed full current state required')
        evolving = copy.deepcopy(first)
        audit_before = provider.audit()
        q.R.write(output / 'before-full.json', first)
        q.R.write(output / 'request.json', review)

        async def guard():
            request_guard(review, clock())
            require(await fence() == native and await read_registration() == registration, 'Released ledger/writer/runtime/registration changed')
            fresh = await q.R.capture(settings, source)
            require(fresh == evolving, 'Full Source/grants/aliases/servers/admin state drift')
            require(provider.audit()[:len(audit_before)] == audit_before, 'Existing audit prefix changed')
            return fresh

        selected_ids = {'native-pilot-' + u for u in SELECTED[source]}
        for member in list(evolving['records']['memberships']):
            if member['id'] not in selected_ids:
                continue
            await guard()
            after = {**member, 'expires': expiry}
            if after == member:
                continue
            receipt['attempting'] = {'kind': 'memberships', 'id': member['id']}
            result = await provider.put('memberships', after, actor=ACTORS[source])
            require(result == after, 'Normal Source PUT must preserve every non-expiry field')
            part = q.R.state_part(evolving)
            part['records']['memberships'] = [after if x['id'] == member['id'] else x for x in part['records']['memberships']]
            evolving = q.set_scoped(evolving, part)
            await guard()
            receipt['changes'].append({'kind': 'memberships', 'id': member['id'], 'before': member, 'after': result})
            receipt.pop('attempting', None)
        for username in SELECTED[source]:
            person = evolving['people'][username]
            grant = evolving['grants'][person][0]
            await guard()
            after = {**grant, 'expires': expiry}
            if after == grant:
                continue
            receipt['attempting'] = {'kind': 'compute-grants', 'id': grant['id']}
            result = await compute.put_grant(after, actor=ACTORS[source])
            require(result == after, 'Normal grant PUT must preserve every non-expiry field')
            evolving['grants'][person] = [after]
            with provider.db:
                provider._audit(ACTORS[source], 'compute-grants', grant['id'], canonical(grant), canonical(result))
            await guard()
            receipt['changes'].append({'kind': 'compute-grants', 'id': grant['id'], 'before': grant, 'after': result})
            receipt.pop('attempting', None)
        final = await guard()
        require(final == changed(source, first, expiry), 'Only four selected expiry changes permitted')
        audits = provider.audit()[len(audit_before):]
        require(len(audits) == len(receipt['changes']) and all(x['actor'] == ACTORS[source] and x['outcome'] == 'success' for x in audits), 'Normal actual admin mutation audits required')
        q.R.write(output / 'after-full.json', final)
        q.R.write(output / 'audit-appended.json', audits)
        receipt.update(state='selected-qualified-expiry-renewed-read-back' if review['operation'] == 'renew' else 'selected-qualified-expiry-restored-read-back', before_full_sha256=digest(first), after_full_sha256=digest(final), changes=changes(first, final), runtime_before=native, registration_sha256=q.sha(registration))
        return receipt
    except BaseException as error:
        receipt['error_type'] = type(error).__name__
        raise
    finally:
        actor_context.reset(token)
        q.R.write(output / 'receipt.json', receipt)


async def build_context(args, review, baseline_state, q, historical_renewal):
    """Add the twenty-one fence inside the unchanged foundation's loader order.

    The adapter delegates to the original nineteen-record fence first. It only
    adds original21/count/schema constraints; it does not replace or relax any
    Pod, writer, registration, profile, cap, history, or credential validation.
    The foundation still checks every runtime object before loading Source.
    """
    foundation_globals = q.build_context.__globals__
    frozen_install = foundation_globals['install_base']

    def install_strengthened(raw):
        # Genuine792 constructs a NEW FrozenBase inside build_context. Install
        # the adapter on that actual class, never on its discarded export.
        frozen_install(raw)
        base = foundation_globals['R']
        q.R = base
        original_guard = base.ledger_guard

        def strengthened(state, runtime, operation):
            original_guard(state, runtime, operation)
            request_guard(review, datetime.now(timezone.utc), capture=args.capture)
            ledger_guard(state, baseline_state, review['operation'], runtime, q, original_guard=original_guard)

        base.ledger_guard = strengthened

    foundation_globals['install_base'] = install_strengthened
    q.install_base = install_strengthened
    legacy = {k: review[k] for k in ('version', 'enabled', 'source', 'actor', 'observed_at', 'source_writers_stopped', 'fixture_starts_excluded', 'source_token_custody', 'runtime_review_sha256', 'current_full_sha256', 'provenance_sha256', 'physical_retirement_review_sha256')}
    legacy.update(operation='expire-qualified-fixtures', renewed_expires=historical_renewal['renewed_expires'], original_raw_sha256=q.R.ORIGINAL_SHAS[args.source])
    foundation_args = SimpleNamespace(**vars(args))
    foundation_args.source_sha256 = QUALIFIED_SHA
    return await q.build_context(foundation_args, legacy)


def protected(path, expected):
    raw_pin(expected)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        st = os.fstat(fd)
        require(stat.S_ISREG(st.st_mode) and st.st_uid == 10001 and st.st_nlink == 1 and stat.S_IMODE(st.st_mode) in (0o400, 0o600) and 0 < st.st_size <= 8 * 1024 * 1024, 'Protected UID10001 single-link 400/600 file required')
        raw = os.read(fd, 8 * 1024 * 1024 + 1)
        end = os.fstat(fd)
        require(len(raw) == st.st_size and hashlib.sha256(raw).hexdigest() == expected and (st.st_size, st.st_mtime_ns, st.st_ctime_ns) == (end.st_size, end.st_mtime_ns, end.st_ctime_ns), 'Exact unchanged protected bytes required')
        return raw
    finally:
        os.close(fd)


def decode(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'Duplicate JSON field rejected')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON rejected')))


def load(path, expected):
    return decode(protected(path, expected))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--capture', action='store_true')
    names = ('source', 'source-sha256', 'qualified-expiry', 'renewal', 'handover', 'audit-helper', 'source-closure', 'source-closure-sha256', 'config', 'config-sha256', 'policy', 'policy-sha256', 'qualification-config', 'qualification-config-sha256', 'node-config', 'node-config-sha256', 'kubeconfig', 'kubeconfig-sha256', 'runtime-review', 'physical-retirement-review', 'normal-close-receipt', 'protected-retirement-capture', 'baseline-before', 'baseline-after', 'baseline-receipt', 'baseline-ledger', 'original', 'renewal-after', 'renewal-receipt', 'grant-before', 'grant-receipt', 'handover-receipt', 'registration', 'request', 'request-sha256', 'output')
    for name in names:
        parser.add_argument('--' + name)
    for name in ('cycle-before', 'cycle-after', 'cycle-receipt'):
        parser.add_argument('--' + name)
    args = parser.parse_args(argv)
    if not args.execute:
        print(canonical({'state': 'inert', 'api_calls': False, 'writes': False, 'workspace_started': False, 'qualification': False}))
        return 0
    require(os.geteuid() == 10001 and args.source in SELECTED and all(getattr(args, n.replace('-', '_')) for n in names), 'Trusted UID10001 and complete actual protected inputs required')
    protected(__file__, args.source_sha256)
    q = load_frozen(protected(args.qualified_expiry, QUALIFIED_SHA), protected(args.renewal, RENEWAL_SHA), args.qualified_expiry)
    review = load(args.request, args.request_sha256)
    request_guard(review, datetime.now(timezone.utc), capture=args.capture)
    require(review['source'] == args.source, 'Exact CLI Source binding required')
    before = load(args.baseline_before, BASELINE_PINS[args.source]['before'])
    baseline = load(args.baseline_after, BASELINE_PINS[args.source]['after'])
    baseline_receipt = load(args.baseline_receipt, BASELINE_PINS[args.source]['receipt'])
    ledger = load(args.baseline_ledger, BASELINE_LEDGER_SHA)
    require(ledger['metadata']['uid'] == q.R.BASE_LEDGER_UID, 'Exact original ledger UID required')
    baseline_state = decode(ledger['data']['state.json'])
    require(review['provenance_sha256'] == baseline_receipt['provenance_sha256'], 'Unchanged actual historical handover chain required')
    history = {'original': load(args.original, q.R.ORIGINAL_SHAS[args.source])}
    history.update({key: load(getattr(args, key), review['provenance_sha256'][key]) for key in q.PROVENANCE})
    baseline_guard(args.source, before, baseline, baseline_receipt, history, baseline_state, q)
    if review['operation'] == 'restore-expiry':
        require(all((args.cycle_before, args.cycle_after, args.cycle_receipt)), 'Own actual completed cycle receipt/before/after required')
        cycle = {key: load(getattr(args, 'cycle_' + {'before_full': 'before', 'after_full': 'after', 'receipt': 'receipt'}[key]), pin) for key, pin in review['cycle_provenance_sha256'].items()}
        cycle_guard(args.source, baseline, cycle['before_full'], cycle['after_full'], cycle['receipt'], review, baseline_state, history['registration'], q)
    out = Path(args.output)
    parent = out.parent.lstat()
    require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == 10001 and stat.S_IMODE(parent.st_mode) == 0o700 and not out.exists() and not out.is_symlink(), 'New private trusted output directory required')
    out.mkdir(mode=0o700)

    async def run():
        settings, fence, registration = await build_context(args, review, baseline_state, q, history['renewal_receipt'])
        try:
            if args.capture:
                native = await fence()
                reg = await registration()
                current = await q.R.capture(settings, args.source)
                current_guard(args.source, baseline, current, review['renewed_expires'])
                require(await fence() == native and await registration() == reg and await q.R.capture(settings, args.source) == current, 'Capture drifted')
                q.R.write(out / 'current-full.json', current)
                q.R.write(out / 'capture-review-needed.json', {'version': 1, 'state': 'current-qualified-selected-window-captured-root-review-required', 'current_full_sha256': digest(current), 'cycle_id': review['cycle_id'], 'root_review_required': True, 'qualification': False, 'workspace_started': False})
                return {'state': 'current-qualified-selected-window-captured-root-review-required'}
            return await apply(settings, baseline, review, out, fence, registration, q)
        finally:
            settings['course_provider'].db.close()

    result = asyncio.run(asyncio.wait_for(run(), timeout=300))
    print(canonical({'state': result['state'], 'source': args.source, 'workspace_started': False, 'qualification': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
