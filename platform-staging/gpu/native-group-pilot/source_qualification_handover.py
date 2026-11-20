"""Bounded operator qualification Source handover; default inert.

Derivative of frozen10001 handover00a91, preserving every old stop/freeze guard.
CPS5 and CIT10 only; no passed proof, grants, Start, or automatic freeze release.
"""
import argparse
import asyncio
import copy
import hashlib
import importlib
import inspect
import json
import os
import re
import stat
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

PROFILE = 'interactive-native-qualification-5'
PROFILES = {'cps': PROFILE, 'cit': 'interactive-native-qualification-10'}
OLD_PROFILE = 'interactive-shared-5'
SCOPES = frozenset({'cps:native-group-b', 'cit:native-group-a'})
MAX_BYTES = 1048576
ENROLLMENT_FIELDS = {'version','binding_id','source','actor','workspace','principal','members','attempt',
    'profile','policy_hash','namespace','name','node','node_uid','gpu_uuid','cap_mib','intent'}
REVIEW_FIELDS = {'version','source','workspace','actor','new_profile','original_local',
    'original_registration','members','policy_hash','qualification_config_sha256','freeze_id','stopped','original_course','target_ceiling'}
STOP_FIELDS = {'binding_id','attempt','intent','ledger_uid','enrollment_uid','enrollment_sha256',
    'cleanup_uid','cleanup_sha256'}


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return 'sha256:' + hashlib.sha256(canonical(value).encode()).hexdigest()


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def closed(value, keys, message):
    require(type(value) is dict and set(value) == keys, message)


def sha(value):
    return isinstance(value, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', value) is not None


def identifier(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except (ValueError, TypeError):
        return False


def private_bytes(path, expected, *, root=False):
    require(isinstance(expected, str) and re.fullmatch(r'[0-9a-f]{64}', expected), 'Exact raw file SHA required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) in (0o400, 0o600)
            and info.st_uid == 10001 and info.st_nlink == 1 and 0 < info.st_size <= MAX_BYTES,
            'Protected bounded operator file required')
        raw = os.read(fd, MAX_BYTES + 1)
        require(len(raw) == info.st_size and len(raw) <= MAX_BYTES, 'Operator file changed or oversized')
        require(hashlib.sha256(raw).hexdigest() == expected, 'Operator file SHA mismatch')
        after = os.fstat(fd)
        require((info.st_size, info.st_mtime_ns, info.st_ctime_ns) ==
            (after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Operator file changed during read')
        return raw
    finally:
        os.close(fd)


def validate_review(review):
    closed(review, REVIEW_FIELDS, 'Closed reviewed handover required')
    require(type(review['version']) is int and review['version'] == 1, 'Handover version mismatch')
    require(review['source'] + ':' + review['workspace'] in SCOPES, 'Unapproved handover scope')
    require(review['new_profile'] == PROFILES[review['source']] and identifier(review['freeze_id']), 'Exact profile and freeze ID required')
    require(isinstance(review['actor'], str) and review['actor'].strip() == review['actor'] and review['actor'], 'Administrator actor required')
    require(sha(review['policy_hash']) and sha(review['qualification_config_sha256']), 'Qualified configuration pins required')
    require(type(review['members']) is list and review['members'] and review['members'] == sorted(set(review['members']))
        and all(identifier(member) for member in review['members']), 'Reviewed canonical members required')
    for field in ('original_local', 'original_registration'):
        require(type(review[field]) is dict, 'Full original source and registration records required')
    old = review['original_local']
    require(old.get('id') == review['workspace'] and old.get('state') == 'stopped'
        and old.get('source') == 'local' and old.get('external_id') is None
        and old.get('profile') == OLD_PROFILE, 'Exact stopped local pilot record required')
    original = review['original_registration']
    require(original.get('workspace') == review['workspace'] and original.get('profiles') == [OLD_PROFILE]
        and original.get('principal') == 'workspace:' + review['source'] + ':' + review['workspace']
        and original.get('members') == review['members'] and type(original.get('storage')) is dict
        and original['storage'].get('state') == 'active', 'Exact original registration and active storage required')
    course = review['original_course']
    require(type(course) is dict and course.get('id') == old['course_id']
        and course.get('source') == 'local' and course.get('external_id') is None
        and course.get('resource_ceiling') == old.get('course_ceiling')
        and not course.get('reconciliation_pending') and not course.get('membership_removal_pending'),
        'Exact source-owned original course and ceiling required')
    expected = {'cpu':'4','memory':'16Gi','gpuMemoryGiB':5 if review['source']=='cps' else 10}
    require(review['target_ceiling'] == expected and type(review['target_ceiling'].get('gpuMemoryGiB')) is int,
        'Exact operator qualification course ceiling required')
    stopped = review['stopped']
    closed(stopped, STOP_FIELDS, 'Exact cleanup provenance required')
    require(isinstance(stopped['binding_id'], str) and re.fullmatch(r'[0-9a-f]{60}', stopped['binding_id'])
        and isinstance(stopped['attempt'], str) and stopped['attempt'], 'Exact binding and attempt required')
    require(all(identifier(stopped[key]) for key in ('ledger_uid','enrollment_uid','cleanup_uid'))
        and all(sha(stopped[key]) for key in ('enrollment_sha256','cleanup_sha256')), 'Actual immutable UID/hash proof required')
    from cps_compute.native_gpu_controller import CapIntent
    intent = CapIntent(**stopped['intent'])
    require(intent.namespace == original.get('namespace') and intent.name == original.get('pod')
        and intent.cap_mib == 5120, 'Original exact Pod intent and 5GiB cap required')
    return copy.deepcopy(review)


def validate_context(context):
    closed(context, {'service','policy','operator_qualification','authority_backend','verify_external_freeze','read_registration'},
        'Configured application context required')
    from e2x_course_hub.cps.compute import ComputePolicyClient
    from e2x_course_hub.cps.providers import LocalCourseProvider
    from e2x_course_hub.cps.workspaces import WorkspaceService, HubWorkspaceAdapter
    from cps_compute.policy import Policy
    from cps_compute.native_qualification import NativeGroupQualification
    from cps_compute.native_gpu_control import KubernetesNativeAuthorityBackend
    service = context['service']
    require(type(service) is WorkspaceService and type(service.provider) is LocalCourseProvider
        and type(service.compute) is ComputePolicyClient and type(service.hub) is HubWorkspaceAdapter,
        'Released configured WorkspaceService/provider/compute/Hub adapter required')
    require(type(context['policy']) is Policy and type(context['operator_qualification']) is NativeGroupQualification
        and type(context['authority_backend']) is KubernetesNativeAuthorityBackend
        and inspect.iscoroutinefunction(context['verify_external_freeze'])
        and inspect.iscoroutinefunction(context['read_registration']), 'Released qualified configuration and fresh Root verifiers required')
    return context


def load_configured_service(config_path, config_sha256, *, source, database_path, server_config_path):
    """Root factory utility: construct the real app, without listen/start.

    Root must supply its exact existing configuration and mounted environment.
    The actual database/server-config files must already exist. This does not
    acquire or replace Root's external freeze.
    """
    from e2x_course_hub.course_service.app import CourseServiceApp
    require(source in ('cps','cit'), 'Explicit console source required')
    private_bytes(config_path,config_sha256,root=True)
    for path in (database_path,server_config_path):
        info = os.lstat(path)
        require(stat.S_ISREG(info.st_mode) and info.st_size > 0, 'Existing regular application data/config required')
    app = CourseServiceApp()
    # Read traits before constructing providers: a mismatched configuration
    # must not initialize a second/wrong database or a new server-config file.
    app.load_config_file(str(config_path))
    require(app.console_owner == source and os.path.realpath(app.database_path) == os.path.realpath(database_path)
        and os.path.realpath(app.server_config_file) == os.path.realpath(server_config_path),
        'Configured application source/data paths disagree with Root capture')
    private_bytes(config_path,config_sha256,root=True)
    app.init_tornado_settings()
    service = app.tornado_settings['workspace_service']
    require(service is not None and service.provider is app.tornado_settings['course_provider']
        and service.compute is app.tornado_settings['compute_policy'], 'Actual configured application service required')
    return app, service


async def verify_stopped(backend, review, groups):
    """Only actual readonly GETs; snapshot() is excluded because it can create."""
    from cps_compute.native_gpu_control import LEDGER_NAME, NativeGpuAuthority, validate_cleanup_record
    stopped = review['stopped']; binding = stopped['binding_id']
    require(backend.namespace == groups.authority_namespace, 'Authority namespace mismatch')
    intent = stopped['intent']
    require(await backend.pod(intent['namespace'], intent['name']) is None, 'Registered Pod must be absent, including replacements')
    ledger = await backend._read(LEDGER_NAME)
    meta = ledger.get('metadata', {}) if isinstance(ledger, dict) else {}
    require(ledger is not None and ledger.get('apiVersion') == 'v1' and ledger.get('kind') == 'ConfigMap'
        and meta.get('namespace') == backend.namespace and meta.get('name') == LEDGER_NAME
        and meta.get('uid') == stopped['ledger_uid'] and meta.get('resourceVersion') and not meta.get('deletionTimestamp')
        and not ledger.get('binaryData'), 'Actual existing ledger identity required')
    state = backend._document(ledger, 'state.json')
    closed(state, {'version','allocations'}, 'Closed allocation ledger required')
    require(type(state['version']) is int and state['version'] == 1 and type(state['allocations']) is dict, 'Versioned allocation ledger required')
    record = state['allocations'].get(binding)
    require(type(record) is dict and record.get('state') == 'released'
        and record.get('source') == review['source'] and record.get('workspace') == review['workspace']
        and record.get('attempt') == stopped['attempt'] and record.get('intent') == intent,
        'Exact old native attempt must already be released')
    require(all(type(row) is dict and row.get('state') == 'released'
        for row in state['allocations'].values()
        if type(row) is not dict or (row.get('source'),row.get('workspace')) == (review['source'],review['workspace'])),
        'Competing or malformed native allocation remains held')
    enrollment_name = 'cps-native-enrollment-' + binding[:40]
    enrollment_cm = await backend._read(enrollment_name)
    enrollment = backend._immutable_document(enrollment_cm, 'enrollment.json', enrollment_name, binding)
    closed(enrollment, ENROLLMENT_FIELDS, 'Closed original enrollment required')
    require(enrollment_cm['metadata']['uid'] == stopped['enrollment_uid']
        and digest(enrollment) == stopped['enrollment_sha256']
        and NativeGpuAuthority._enrollment_record(record) == enrollment
        and enrollment['members'] == review['members'] and enrollment['principal'] == review['original_registration']['principal']
        and enrollment['profile'] == OLD_PROFILE, 'Frozen enrollment provenance changed')
    require(all(enrollment[key] == groups.node_pool[key] for key in ('node','node_uid','gpu_uuid')),
        'Released enrollment selected pool changed')
    cleanup_name = 'cps-native-cleanup-' + binding[:40]
    cleanup_cm = await backend._read(cleanup_name)
    cleanup = backend._immutable_document(cleanup_cm, 'receipt.json', cleanup_name, binding)
    require(cleanup_cm['metadata']['uid'] == stopped['cleanup_uid'] and digest(cleanup) == stopped['cleanup_sha256'],
        'Immutable cleanup identity changed')
    expected = {'version':1,'binding_id':binding,'attempt':stopped['attempt'],'intent':intent,'cleanup_confirmed':True}
    validate_cleanup_record(cleanup, expected)
    require(await backend.cleanup_receipt(binding) == cleanup, 'Fresh typed cleanup and enrollment provenance changed')
    require(await backend.pod(intent['namespace'], intent['name']) is None, 'Registered Pod appeared during cleanup proof')
    return {'binding_id':binding,'attempt':stopped['attempt'],'ledger_uid':meta['uid'],
        'enrollment_uid':enrollment_cm['metadata']['uid'],'cleanup_uid':cleanup_cm['metadata']['uid']}


async def migrate(context, review):
    """No start, stop, grants, storage mutation, release or freeze-release calls."""
    validate_context(context)
    review = validate_review(review)
    service = context['service']; groups = context['operator_qualification']; policy = context['policy']
    PROFILE = review['new_profile']
    require(service.provider.console == service.compute.console == review['source'], 'Configured source mismatch')
    require(groups.policy_hash == policy.hash == review['policy_hash']
        and digest(json.loads(groups.document)) == review['qualification_config_sha256'], 'Current reviewed group configuration mismatch')
    groups.validate_policy(policy, PROFILE)
    original = review['original_local']; old_registration = review['original_registration']
    candidate = {**original, 'profile':PROFILE, 'course_ceiling':review['target_ceiling']}
    original_course = review['original_course']
    target_course = {**original_course, 'resource_ceiling':review['target_ceiling']}
    target = None
    phase = 'validation'
    try:
        async with service.course_locks.setdefault(original['course_id'], asyncio.Lock()):
            async with service.locks.setdefault(review['workspace'], asyncio.Lock()):
                async def guard():
                    freeze = await context['verify_external_freeze']()
                    closed(freeze, {'version','freeze_id','active','sources','writer_pods','external_starts_excluded','observed_at'},
                        'Fresh externally enforced writer freeze required')
                    observed = datetime.fromisoformat(freeze['observed_at'].replace('Z','+00:00'))
                    require(type(freeze['version']) is int and freeze['version'] == 1
                        and freeze['freeze_id'] == review['freeze_id'] and freeze['active'] is True
                        and freeze['sources'] == ['cit','cps'] and freeze['writer_pods'] == []
                        and freeze['external_starts_excluded'] is True and observed.tzinfo is not None
                        and 0 <= (datetime.now(timezone.utc)-observed).total_seconds() <= 30,
                        'External freeze absent, stale or changed; local locks are insufficient')
                    actor = await service.hub.hub.get_user(review['actor'])
                    require(type(actor) is dict and actor.get('name') == review['actor'] and actor.get('admin') is True,
                        'Fresh actual Hub administrator identity required')
                    local = await service.get(review['workspace'])
                    require(local in (original,candidate) and local.get('state') == 'stopped'
                        and not local.get('archived') and not local.get('archive_pending'), 'Source record changed or writer is unresolved')
                    course = next((c for c in await service.provider.courses() if c['id'] == original['course_id']), None)
                    require(course in (original_course,target_course) and not course.get('reconciliation_pending')
                        and not course.get('membership_removal_pending'), 'Owned course reconciliation barrier unresolved')
                    bindings = [b for b in course.get('workspace_bindings',[]) if all(b.get(k) == original.get(k)
                        for k in ('group_id','hub_user','hub_server'))]
                    require(len(bindings) == 1 and course.get('resource_ceiling') in (original['course_ceiling'],review['target_ceiling'])
                        and bindings[0].get('namespace') == original.get('namespace')
                        and bindings[0].get('pod') == original.get('pod'), 'Source-owned binding or course ceiling changed')
                    siblings = await service.provider.list('workspaces', original['course_id'])
                    if review['target_ceiling'] != original['course_ceiling']:
                        course_groups=await service.provider.groups(original['course_id'])
                        require(len(course_groups)==1 and course_groups[0].get('id')==original['group_id']
                            and len(course.get('workspace_bindings',[])) == 1
                            and len(siblings) == 1 and siblings[0]['id'] == review['workspace'],
                            'A raised qualification ceiling requires the exact dedicated single-workspace course')
                    require(all(w.get('state') == 'stopped' and not w.get('archive_pending') and not w.get('archived')
                        for w in siblings if w.get('group_id') == original['group_id']), 'Shared group writer unresolved')
                    group = next((g for g in await service.provider.groups(original['course_id']) if g['id'] == original['group_id']), None)
                    require(group is not None, 'Owned group missing')
                    assignment_id = original.get('assignment_id') or group.get('assignment_id')
                    if assignment_id:
                        assignment = next((a for a in await service.provider.list('assignments') if a['id'] == assignment_id), None)
                        require(assignment is not None and assignment.get('state','open') == 'open'
                            and not assignment.get('archive_pending') and not assignment.get('archived'), 'Assignment is closed or archiving')
                    require(await service.members(candidate) == review['members'], 'Canonical membership changed')
                    await service.hub.assert_stopped(candidate)
                    reservation = await service.compute.reservation_state(review['workspace'])
                    require(type(reservation) is dict and reservation.get('active') is False
                        and reservation.get('attempt') in (None,review['stopped']['attempt']), 'Generic reservation remains active or changed')
                    await verify_stopped(context['authority_backend'],review,groups)
                    # The normal GET rejects historical policy hashes. This
                    # pinned Root callback reads the actual configured gateway
                    # ControlStore.workspace(source,id) application method.
                    # No fallback accepts a 409/timeout or cached snapshot.
                    current = await context['read_registration'](review['source'],review['workspace'])
                    require(current == old_registration or (target is not None and current == target), 'Central registration/storage changed')
                    if target is not None and current == target:
                        fresh = await service.compute._request('workspaces/' + quote(review['workspace'], safe=''))
                        require(fresh == current, 'Normal source-owned registration GET disagrees with Root application read')
                    return local, current

                _, current = await guard()
                validation = await service.compute.validate_workspace(review['workspace'], review['members'], PROFILE, review['target_ceiling'])
                require(type(validation) is dict and validation.get('policy_hash') == policy.hash
                    and validation.get('profile') == PROFILE and validation.get('members') == review['members']
                    and type(validation.get('selected_gpu_memory_gib')) is int and validation['selected_gpu_memory_gib'] == review['target_ceiling']['gpuMemoryGiB'],
                    'Current member grants/profile/ceiling preview failed')
                # Predict only the normal registration fields; preserve every
                # stored path/identity and any gateway-owned label/hash.
                target = {**old_registration,'profiles':[PROFILE],'policy_hash':policy.hash,
                    'course_id':original['course_id'],'term_id':original['term_id'],'ceiling':review['target_ceiling']}
                groups.authorize(review['source'], {**target,'profile':PROFILE}, PROFILE)
                await guard()
                if target_course != original_course:
                    phase = 'course-ceiling-commit'
                    saved_course = await service.provider.put('courses',target_course,actor=review['actor'])
                    require(saved_course == target_course, 'Source course ceiling commit changed other fields')
                    await guard()
                phase = 'central-registration'
                registered = await service.compute.register_workspace(candidate, review['members'], validation)
                require(registered == target, 'Normal source-owned registration readback changed identities or storage')
                await guard()
                phase = 'fresh-storage-validation'
                final = await service.compute.validate_workspace(review['workspace'], review['members'], PROFILE,
                    review['target_ceiling'], registration=registered)
                require(type(final) is dict and final.get('policy_hash') == policy.hash and final.get('profile') == PROFILE
                    and final.get('members') == review['members'] and type(final.get('selected_gpu_memory_gib')) is int
                    and final['selected_gpu_memory_gib'] == review['target_ceiling']['gpuMemoryGiB'], 'Fresh registered storage/member policy validation failed')
                _, current = await guard()
                require(current == target and current['storage'] == old_registration['storage'], 'Fresh storage must be unchanged')
                groups.authorize(review['source'], {**current,'profile':PROFILE}, PROFILE)
                phase = 'local-profile-commit'
                saved = await service.provider.put('workspaces', candidate, actor=review['actor'])
                require(saved == candidate, 'Local profile-only commit changed other fields')
                phase = 'final-readback'
                local, current = await guard()
                require(local == candidate and current == target, 'Final application handover readback failed')
                # provider.put must supply the real before/new application audit.
                require(any(row['actor'] == review['actor'] and row['kind'] == 'workspaces'
                    and row['target'] == review['workspace'] and row['outcome'] == 'success'
                    and decode(row['previous']) in (original,candidate) and decode(row['current']) == candidate
                    for row in service.provider.audit() if row.get('previous') and row.get('current')),
                    'Audited provider handover missing')
                return {'version':1,'state':'handover-complete-stopped','source':review['source'],'workspace':review['workspace'],
                    'profile':PROFILE,'previous_profile':OLD_PROFILE,'target_ceiling':review['target_ceiling'],
                    'course_sha256':digest(target_course),'hardware_qualified':False,'local_sha256':digest(local),
                    'registration_sha256':digest(current),'storage_sha256':digest(current['storage']),
                    'freeze_id':review['freeze_id'],'freeze_release_performed':False,'start_performed':False}
    except BaseException as error:
        # These are application audit calls, never direct SQL or record repair.
        service.provider.denial(review['actor'],'profile-handover',review['workspace'],
            {'profile':PROFILE,'phase':phase,'review_sha256':digest(review),'freeze_id':review['freeze_id']}, 'failure')
        raise HandoverIncomplete(phase) from error


class HandoverIncomplete(RuntimeError):
    def __init__(self, phase):
        self.phase = phase
        super().__init__('Handover incomplete; retain external writer freeze and keep stopped (phase=' + phase + ')')


def verify_source_closure(closure):
    closed(closure, {'version','modules'}, 'Closed runtime source closure required')
    require(type(closure['version']) is int and closure['version'] == 1 and type(closure['modules']) is dict,
        'Source closure version required')
    modules = {'e2x_course_hub.course_service.app','e2x_course_hub.cps.compute','e2x_course_hub.cps.workspaces',
        'e2x_course_hub.cps.providers','e2x_course_hub.cps.validation','e2x_course_hub.cps.identity','e2x_course_hub.cps.expiry',
        'cps_compute.native_groups','cps_compute.native_pool','cps_compute.native_qualification','cps_compute.policy','cps_compute.internal','cps_compute.identity','cps_compute.reservations','cps_compute.native_gpu_control',
        'cps_compute.native_gpu_controller'}
    require(set(closure['modules']) == modules, 'Exact application/service source closure required')
    for name, expected in closure['modules'].items():
        require(isinstance(expected,str) and re.fullmatch(r'[0-9a-f]{64}',expected) is not None, 'Source module SHA required')
        raw = Path(importlib.import_module(name).__file__).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, 'Installed application source mismatch: ' + name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    for key in ('review','factory','source-closure'):
        parser.add_argument('--'+key)
        parser.add_argument('--'+key+'-sha256')
    parser.add_argument('--publisher-sha256')
    args = parser.parse_args(argv)
    if not args.execute:
        print(canonical({'version':1,'state':'inert','freeze_release_performed':False,'start_performed':False}))
        return 0
    require(os.geteuid() == 10001, 'Trusted operator UID10001 execute required')
    require(all(getattr(args,key.replace('-','_')) for key in
        ('review','review-sha256','factory','factory-sha256','source-closure','source-closure-sha256','publisher-sha256')),
        'All explicit reviewed artifact pins required')
    require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == args.publisher_sha256, 'Publisher source pin mismatch')
    review = decode(private_bytes(args.review,args.review_sha256,root=True))
    closure = decode(private_bytes(args.source_closure,args.source_closure_sha256,root=True))
    verify_source_closure(closure)
    source = private_bytes(args.factory,args.factory_sha256,root=True)
    namespace = {'__name__':'root_handover_factory','__file__':args.factory}
    exec(compile(source,args.factory,'exec'),namespace)
    require(inspect.iscoroutinefunction(namespace.get('build_context')), 'Pinned async configured factory required')
    async def run():
        context = await namespace['build_context']()
        return await migrate(context,review)
    try:
        result = asyncio.run(asyncio.wait_for(run(),240))
        print(canonical(result)); return 0
    except BaseException as error:
        print(canonical({'version':1,'state':'incomplete-retain-freeze','phase':getattr(error,'phase','context-or-deadline'),
            'freeze_release_performed':False,'start_performed':False}),file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
