"""Audited CPU restoration after an externally frozen operator qualification.

Gateway must already serve the original policy. Physical release is independently
measured by the trusted Root executor; this module also checks the actual native
ledger, immutable cleanup receipts and absence of replacement Pods. No Stop,
release, grant, filesystem or freeze-release operation is performed here.
"""
import asyncio
import copy
import hashlib
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import source_handover as forward
import source_qualification_handover as h
import node_successor


def fresh_time(value):
    observed=datetime.fromisoformat(value.replace('Z','+00:00'))
    h.require(observed.tzinfo is not None and 0 <= (datetime.now(timezone.utc)-observed).total_seconds() <= 30,
        'Fresh independent observation required')


async def restore(context,review,*,contract_raw,contract_sha256,verify_physical_release):
    h.require(hashlib.sha256(Path(h.__file__).read_bytes()).hexdigest()==forward.FROZEN_HANDOVER_SHA256,
        'Exact frozen Source migration implementation required')
    contract=node_successor.validate_contract(contract_raw,contract_sha256)
    forward.validate_review(review,contract);h.validate_context(context)
    h.require(inspect.iscoroutinefunction(verify_physical_release),'Trusted asynchronous physical release verifier required')
    service=context['service'];policy=context['policy'];groups=context['operator_qualification']
    original=review['original_local'];registration=review['original_registration'];course=review['original_course']
    h.require(service.provider.console==service.compute.console==review['source']
        and policy.hash==registration['policy_hash'] and policy.hash!=contract['policy_hash']
        and groups.policy_hash==contract['policy_hash'] and groups.workload_image==forward.WORKLOAD_IMAGE
        and h.digest(json.loads(groups.document))==review['qualification_config_sha256'],
        'Original policy and exact previous qualification mode required')
    candidate={**original,'profile':review['new_profile'],'course_ceiling':review['target_ceiling']}
    stopped_candidate={**candidate,'notice':None,'archive_pending':False}
    target_course={**course,'resource_ceiling':review['target_ceiling']}
    qualified={**registration,'profiles':[review['new_profile']],'policy_hash':contract['policy_hash'],
        'course_id':original['course_id'],'term_id':original['term_id'],'ceiling':review['target_ceiling']}
    restored={**original,'archive_pending':False}
    phase='validation'

    async def guard():
        freeze=await context['verify_external_freeze']()
        h.closed(freeze,{'version','freeze_id','active','sources','writer_pods','external_starts_excluded','observed_at'},
            'Closed externally enforced freeze required')
        h.require(type(freeze['version']) is int and freeze['version']==1 and freeze['freeze_id']==review['freeze_id']
            and freeze['active'] is True and freeze['sources']==['cit','cps'] and freeze['writer_pods']==[]
            and freeze['external_starts_excluded'] is True,'External writers or Starts are not excluded')
        fresh_time(freeze['observed_at'])
        actor=await service.hub.hub.get_user(review['actor'])
        h.require(type(actor) is dict and actor.get('name')==review['actor'] and actor.get('admin') is True,
            'Current actual Hub administrator required')
        local=await service.get(review['workspace'])
        h.require(local in (original,restored,candidate,stopped_candidate),'Unrelated local record change')
        actual_course=next((c for c in await service.provider.courses() if c['id']==course['id']),None)
        h.require(actual_course in (course,target_course),'Unrelated course change')
        siblings=await service.provider.list('workspaces',original['course_id'])
        course_groups=await service.provider.groups(original['course_id'])
        h.require(len(siblings)==1 and siblings[0]==local and len(course_groups)==1
            and course_groups[0]['id']==original['group_id'] and len(actual_course.get('workspace_bindings',[]))==1,
            'Dedicated qualification course changed')
        group=course_groups[0];assignment_id=original.get('assignment_id') or group.get('assignment_id')
        if assignment_id:
            assignment=next((a for a in await service.provider.list('assignments') if a['id']==assignment_id),None)
            h.require(assignment is not None and assignment.get('state','open')=='open'
                and not assignment.get('archived') and not assignment.get('archive_pending'),'Assignment closed or archiving')
        h.require(await service.members(original)==review['members'],'Canonical membership changed')
        await service.hub.assert_stopped(local)
        reservation=await service.compute.reservation_state(review['workspace'])
        h.require(type(reservation) is dict and reservation.get('active') is False and reservation.get('attempt') is None,
            'Reservations remain held or unresolved')
        await released(context,review,verify_physical_release)
        current=await context['read_registration'](review['source'],review['workspace'])
        h.require(current in (registration,qualified),'Central registration or storage changed')
        if current==registration:
            h.require(await service.compute._request('workspaces/'+quote(review['workspace'],safe=''))==current,
                'Original-policy normal registration GET disagrees')
        return local,current

    try:
        async with service.course_locks.setdefault(original['course_id'],asyncio.Lock()):
            async with service.locks.setdefault(review['workspace'],asyncio.Lock()):
                await guard()
                validation=await service.compute.validate_workspace(review['workspace'],review['members'],'interactive-cpu',original['course_ceiling'])
                h.require(validation.get('policy_hash')==policy.hash and validation.get('profile')=='interactive-cpu'
                    and validation.get('members')==review['members'] and type(validation.get('selected_gpu_count')) is int
                    and validation['selected_gpu_count']==0,'Fresh CPU grant and ceiling preview required')
                await guard();phase='central-registration'
                saved=await service.compute.register_workspace(original,review['members'],validation)
                h.require(saved==registration,'CPU registration changed original identity or storage')
                await guard();phase='course-restoration'
                h.require(await service.provider.put('courses',copy.deepcopy(course),actor=review['actor'])==course,
                    'Original course restoration mismatch')
                await guard();phase='local-restoration'
                h.require(await service.provider.put('workspaces',copy.deepcopy(restored),actor=review['actor'])==restored,
                    'Original local restoration mismatch')
                local,current=await guard()
                h.require(local==restored and current==registration,'Final original records not restored')
                h.require(any(row['actor']==review['actor'] and row['kind']=='workspaces' and row['target']==review['workspace']
                    and row['outcome']=='success' and row.get('current') and h.decode(row['current'])==restored
                    for row in service.provider.audit()),'Audited Source restoration missing')
                return dict(version=1,state='restored-cpu-stopped',source=review['source'],workspace=review['workspace'],
                    local_sha256=h.digest(local),registration_sha256=h.digest(current),storage_sha256=h.digest(current['storage']),
                    hardware_qualified=False,start_performed=False,freeze_release_performed=False)
    except BaseException as error:
        service.provider.denial(review['actor'],'profile-restoration',review['workspace'],
            {'phase':phase,'review_sha256':h.digest(review),'freeze_id':review['freeze_id']},'failure')
        raise h.HandoverIncomplete(phase) from error


async def released(context,review,verify_physical_release):
    from cps_compute.native_gpu_control import LEDGER_NAME,MeasuredNativeAuthority,NativeGpuAuthority,validate_cleanup_record
    backend=context['authority_backend'];groups=context['operator_qualification']
    h.require(backend.namespace==groups.authority_namespace,'Authority namespace changed')
    pod=review['original_registration']
    h.require(await backend.pod(pod['namespace'],pod['pod']) is None,'Actual or replacement Pod remains')
    ledger=await backend._read(LEDGER_NAME);meta=ledger.get('metadata',{}) if isinstance(ledger,dict) else {}
    h.require(ledger is not None and ledger.get('apiVersion')=='v1' and ledger.get('kind')=='ConfigMap'
        and meta.get('namespace')==backend.namespace and meta.get('name')==LEDGER_NAME
        and meta.get('uid')==review['stopped']['ledger_uid'] and meta.get('resourceVersion')
        and not meta.get('deletionTimestamp') and not ledger.get('binaryData'),'Actual original ledger required')
    state=backend._document(ledger,'state.json');h.closed(state,{'version','allocations'},'Closed allocation ledger required')
    h.require(type(state['version']) is int and state['version']==1 and type(state['allocations']) is dict
        and len(state['allocations'])<=128,'Bounded complete allocation history required')
    verifier=object.__new__(MeasuredNativeAuthority);verifier.pool=groups.node_pool
    verifier._validate_allocations(state['allocations'])
    h.require(all(row['state']=='released' for row in state['allocations'].values()),'Native allocation still active')
    for binding,row in state['allocations'].items():
        if (row['source'],row['workspace'])!=(review['source'],review['workspace']):continue
        h.require(row['members']==review['members'] and row['principal']==pod['principal']
            and row['profile']==review['new_profile'] and row['policy_hash']==review['policy_hash'],
            'Unexpected qualification lifetime')
        if row.get('intent') is not None:
            name='cps-native-enrollment-'+binding[:40]
            enrollment_cm=await backend._read(name)
            enrollment=backend._immutable_document(enrollment_cm,'enrollment.json',name,binding)
            h.require(enrollment==NativeGpuAuthority._enrollment_record(row),'Immutable enrollment differs from actual lifetime')
            receipt=await backend.cleanup_receipt(binding)
            h.require(receipt is not None and receipt.get('cleanup_confirmed') is True
                and receipt.get('binding_id')==binding and receipt.get('attempt')==row['attempt']
                and receipt.get('intent')==row['intent'],'Immutable typed cleanup receipt required')
            validate_cleanup_record(receipt,dict(version=1,binding_id=binding,attempt=row['attempt'],intent=row['intent'],cleanup_confirmed=True))
    proof=await verify_physical_release()
    h.closed(proof,{'version','policy_hash','ledger_uid','node_pool','zero_charge','observed_at'},'Independent physical release proof required')
    h.require(type(proof['version']) is int and proof['version']==1 and proof['policy_hash']==review['policy_hash']
        and proof['ledger_uid']==meta['uid'] and proof['zero_charge'] is True
        and proof['node_pool']=={k:groups.node_pool[k] for k in ('node','node_uid','gpu_uuid','boot_id','driver_generation')},
        'Current physical charge or driver epoch unresolved')
    fresh_time(proof['observed_at'])
    h.require(await backend.pod(pod['namespace'],pod['pod']) is None,'Pod appeared during release verification')
