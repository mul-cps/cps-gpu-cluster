"""Pair the reviewed private normal-Source harness; no lifecycle bypasses."""
import argparse
import asyncio
import hashlib
import json
import re
import sys
import traceback
import types
from datetime import datetime, timezone

BASELINE_SHA256 = '8152fa84fff04e0dfc2cd1543fc2175fc7d84024cd4b1fd0732bdc53d7cce780'
REVISION = 'sha256:832e841b6e7b5885a80de27e8850e8e25087b7a26a08a8270f38869f10bf71ca'
TARGETS = {'native-group-a': 'cpsnativegroupa', 'native-group-b': 'cpsnativegroupb'}
HOLD_SECONDS = 180
POOL = {'node': 'k3s-wk-gpu2', 'node_uid': '3336cdd5-d245-436e-b57c-2f66c6dcaa41',
    'gpu_uuid': 'GPU-16128952-b438-556a-00bb-93039ee24e56', 'max_workspaces': 2,
    'memory_budget_mib': 15360, 'headroom_mib': 1024}


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def check_pair(snapshots, capacity):
    require(set(snapshots) == set(TARGETS), 'exact-two-CPS-workspaces-required')
    require(all(capacity['pool'].get(k) == v for k, v in POOL.items()), 'exact-reviewed-pool-required')
    require(capacity.get('active_native_entries') == 0 and capacity.get('native_used_bytes') == 0,
            'empty-native-capacity-required')
    member_sets = []
    for name, before in snapshots.items():
        require(before['workspace'].get('id') == name and before['workspace'].get('state') == 'stopped'
                and before['workspace'].get('profile') == 'interactive-shared-5', 'stopped-five-GiB-workspaces-required')
        require(before['approval'].get('ready') is True and before['approval'].get('revision') == REVISION,
                'exact-current-ready-approval-required')
        require(before['approval'].get('policy_hash') == capacity['policy_hash'], 'policy-and-pool-differ')
        require(before['reservation'].get('active') is False and before['reservation'].get('attempt') is None,
                'inactive-reservations-required')
        require(before['members'] and len(set(before['members'])) == len(before['members']), 'canonical-members-required')
        member_sets.append(set(before['members']))
    require(not member_sets[0].intersection(member_sets[1]), 'canonical-member-overlap-concurrency-forbidden')
    require(2 * 5120 <= capacity['pool']['memory_budget_mib'], 'pair-exceeds-reviewed-budget')
    return True


def load_baseline(code, workspace, hold):
    require(hashlib.sha256(code.encode()).hexdigest() == BASELINE_SHA256, 'reviewed-baseline-source-changed')
    # Reuse capture, Start/Close, window edits, private evidence and exact restore.
    # A fresh per-run parent avoids reusing historical directories whose mode
    # can be widened by a later Kubernetes fsGroup volume ownership pass.
    # Existing paths retain the original strict guards and are never repaired.
    replacements = {
        'parent_name = "normal-source-gpu-acceptance"':
            'parent_name = "normal-source-gpu-acceptance-" + run_id',
        'await asyncio.sleep(60)': 'await pair_hold(WORKSPACE, running)',
        'timedelta(seconds=60)': 'timedelta(seconds=180)',
        '"hold_seconds": 60': '"hold_seconds": 180',
        'plan.get("hold_seconds") == 60': 'plan.get("hold_seconds") == 180',
        '                    await restore_record(provider, service, kind, old, target)':
            '                    require(not start_attempted or result["confirmed_shutdown"], "permission-restoration-requires-confirmed-shutdown")\n                    await restore_record(provider, service, kind, old, target)'}
    for old, new in replacements.items():
        expected = 2 if old == '"hold_seconds": 60' else 1
        require(code.count(old) == expected, 'baseline-adaptation-anchor-changed')
        code = code.replace(old, new)
    module = types.ModuleType('reviewed_normal_source_' + workspace[-1])
    exec(compile(code, 'reviewed-normal-source.py', 'exec'), module.__dict__)
    module.WORKSPACE, module.OWNER = workspace, TARGETS[workspace]
    module.pair_hold = hold
    return module


def failure_diagnostic(workspace, module, error):
    reason = str(error)
    known = isinstance(error, module.AcceptanceFailure) and re.fullmatch(r'[a-z0-9-]{1,120}', reason)
    return {'stage': 'workspace-exception', 'workspace': workspace,
        'failure_type': type(error).__name__,
        'failure_code': reason if known else 'unexpected-see-private-diagnostic',
        'private_diagnostic': ''.join(traceback.format_exception(type(error), error, error.__traceback__))}


class PairHold:
    def __init__(self, seconds=HOLD_SECONDS, ready_timeout=240):
        self.seconds, self.ready_timeout = seconds, ready_timeout
        self.ready = {}
        self.gate, self.abort = asyncio.Event(), asyncio.Event()
        self.started = None

    async def __call__(self, workspace, running):
        require(workspace in TARGETS and workspace not in self.ready, 'duplicate-or-foreign-ready-workspace')
        self.ready[workspace] = running
        if set(self.ready) == set(TARGETS):
            self.started = asyncio.get_running_loop().time()
            self.gate.set()
            print(json.dumps({'stage': 'both-ready-for-root-hardware-readback', 'hold_seconds': self.seconds,
                              'hardware_cap_qualified': False}), flush=True)
        gate = asyncio.create_task(self.gate.wait())
        abort = asyncio.create_task(self.abort.wait())
        try:
            done, _ = await asyncio.wait((gate, abort), timeout=self.ready_timeout, return_when=asyncio.FIRST_COMPLETED)
            require(done and not self.abort.is_set() and self.gate.is_set(), 'peer-start-failed-or-ready-timeout')
            remaining = self.seconds - (asyncio.get_running_loop().time() - self.started)
            if remaining > 0:
                try:
                    await asyncio.wait_for(self.abort.wait(), remaining)
                except asyncio.TimeoutError:
                    return
                raise RuntimeError('peer-failed-during-common-hold')
        finally:
            for task in (gate, abort):
                task.cancel()
            await asyncio.gather(gate, abort, return_exceptions=True)


async def prepare(modules, provider, service, capacity):
    plans = {name: await module.prepare(provider, service) for name, module in modules.items()}
    check_pair({name: plan['before'] for name, plan in plans.items()}, capacity)
    first = next(iter(plans.values()))
    return {'version': 1, 'actor': 'bjoern', 'workspaces': list(TARGETS), 'run_id': first['run_id'],
        'execute_before': min(p['execute_before'] for p in plans.values()), 'hold_seconds': HOLD_SECONDS,
        'capacity': capacity, 'plans': plans, 'before': {
            'memberships': [r for p in plans.values() for r in p['before']['memberships']],
            'grants': [r for p in plans.values() for r in p['before']['grants']]},
        'human_oauth': False, 'production_qualified': False, 'kai_placement_qualified': False}


async def execute(modules, provider, service, plan, expected_sha, capacity, hold):
    base = next(iter(modules.values()))
    require(base.digest(plan) == expected_sha, 'reviewed-pair-plan-changed')
    require(plan.get('actor') == 'bjoern' and plan.get('workspaces') == list(TARGETS)
            and plan.get('version') == 1 and plan.get('hold_seconds') == HOLD_SECONDS, 'closed-pair-plan-required')
    require(datetime.now(timezone.utc) < datetime.fromisoformat(plan['execute_before']), 'reviewed-pair-plan-expired')
    require(capacity == plan['capacity'], 'reviewed-capacity-or-component-custody-changed')
    check_pair({name: p['before'] for name, p in plan['plans'].items()}, capacity)
    # Verify BOTH preimages before allowing either invocation to mutate windows.
    for name, module in modules.items():
        require(await module.capture(provider, service) == plan['plans'][name]['before'], 'reviewed-pair-preimage-changed')
    async def run_one(name):
        module = modules[name]
        try:
            p = plan['plans'][name]
            return await module.execute(provider, service, p, module.digest(p))
        except BaseException as error:
            # Full traceback stays in the host wrapper's mode0600 JSONL. Only
            # bounded known guard codes may be selected for ordinary output.
            print(json.dumps(failure_diagnostic(name, module, error)), flush=True)
            raise
        finally:
            if not hold.gate.is_set():
                hold.abort.set()
    results = await asyncio.gather(*(run_one(name) for name in TARGETS), return_exceptions=True)
    passed = all(type(result) is int and result == 0 for result in results) and hold.gate.is_set()
    print(json.dumps({'stage': 'pair-result', 'lifecycle_passed': passed, 'both_ready': hold.gate.is_set(),
        'workspace_results': [r if type(r) is int else type(r).__name__ for r in results],
        'workspace_failure_codes': [failure_diagnostic(name, modules[name], result)['failure_code']
            if isinstance(result, BaseException) else None for name, result in zip(TARGETS, results)],
        'hardware_cap_qualified': False, 'production_qualified': False, 'kai_placement_qualified': False}), flush=True)
    return 0 if passed else 1


async def main(args):
    hold = PairHold()
    modules = {name: load_baseline(BASELINE_CODE, name, hold) for name in TARGETS}
    base = next(iter(modules.values()))
    _, provider, service = base.initialize()
    from e2x_course_hub.cps.audit import actor_context
    token = actor_context.set('bjoern')
    try:
        if args.mode == 'plan':
            plan = await prepare(modules, provider, service, CAPACITY)
            print(json.dumps({'plan': plan, 'plan_sha256': base.digest(plan)}, sort_keys=True))
            return 0
        return await execute(modules, provider, service, json.load(sys.stdin), args.plan_sha256, CAPACITY, hold)
    finally:
        actor_context.reset(token)
        provider.db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('plan', 'execute'))
    parser.add_argument('--plan-sha256')
    try:
        raise SystemExit(asyncio.run(main(parser.parse_args())))
    except Exception as error:
        # No provider/HTTP body or canonical identities leave the private stdout.
        print(json.dumps({'failed': True, 'failure_type': type(error).__name__}), file=sys.stderr)
        raise SystemExit(1)
