"""Fresh CPU-to-qualification Source adapter; retains the frozen migration guards.

No Start, Stop, grants, storage changes or freeze release. The caller must load
and verify the genuine configured Source app and enforce the external freeze.
"""
import copy
import hashlib
from pathlib import Path
import re
from types import FunctionType
from uuid import UUID

import node_successor
import source_qualification_handover as legacy
from prospective_source_qualification_workspace import WORKLOAD_IMAGE

FROZEN_HANDOVER_SHA256='53c5ed41ad95729a6f4248cf9d3f384c4c5c834b0bbef92134fe25c9ede8f870'


def validate_review(review,contract):
    legacy.closed(review,legacy.REVIEW_FIELDS,'Closed fresh Source handover review required')
    scope=review['source']+':'+review['workspace']
    legacy.require(type(review['version']) is int and review['version']==1 and scope in contract['workspaces']
        and review['source']=='cps' and isinstance(review['actor'],str) and bool(review['actor'].strip())
        and legacy.identifier(review['freeze_id']), 'Exact Root-approved CPS operator scope and administrator required')
    expected=contract['workspaces'][scope]
    legacy.require(review['new_profile']==expected['profile'] and review['policy_hash']==contract['policy_hash']
        and review['members']==sorted(contract['operator_members'][scope])
        and review['target_ceiling']=={'cpu':'4','memory':'16Gi','gpuMemoryGiB':expected['cap_mib']//1024}
        and type(review['target_ceiling']['gpuMemoryGiB']) is int and legacy.sha(review['qualification_config_sha256']),
        'Exact Root profile, canonical members and fixed ceiling required')
    old=review['original_local'];original=review['original_registration'];course=review['original_course']
    legacy.require(isinstance(old,dict) and old.get('id')==review['workspace'] and old.get('source')=='local'
        and old.get('external_id') is None and old.get('profile')=='interactive-cpu' and old.get('state')=='stopped'
        and not old.get('archived') and not old.get('archive_pending'), 'Stopped fresh local CPU workspace required')
    legacy.require(isinstance(original,dict) and original.get('workspace')==review['workspace']
        and original.get('profiles')==['interactive-cpu'] and original.get('members')==review['members']
        and original.get('principal')=='workspace:'+scope and original.get('namespace')=='jupyterhub'
        and isinstance(original.get('owner'),str) and re.fullmatch('cps-ws-[a-f0-9]{32}',original['owner'])
        and original.get('server')=='rtc' and original.get('pod')=='jupyter-'+original['owner']+'--rtc'
        and old.get('hub_user')==original['owner'] and old.get('hub_server')=='rtc'
        and old.get('namespace')==original['namespace'] and old.get('pod')==original['pod']
        and isinstance(original.get('storage'),dict) and original['storage'].get('state')=='active',
        'Exact dedicated CPU registration, neutral owner and active storage required')
    legacy.require(isinstance(course,dict) and course.get('id')==old.get('course_id') and course.get('source')=='local'
        and course.get('external_id') is None and course.get('resource_ceiling')==old.get('course_ceiling')
        and not course.get('reconciliation_pending') and not course.get('membership_removal_pending'),
        'Unchanged owned local course and original CPU ceiling required')
    legacy.closed(review['stopped'],{'kind','ledger_uid','attempt'},'Actual never-enrolled proof required')
    legacy.require(review['stopped']['kind']=='never-enrolled' and review['stopped']['attempt'] is None
        and UUID(review['stopped']['ledger_uid']).int!=0,
        'Never-enrolled workspace must not invent an old GPU attempt')
    return copy.deepcopy(review)


async def verify_fresh_stopped(backend,review,groups):
    from cps_compute.native_gpu_control import LEDGER_NAME,MeasuredNativeAuthority
    legacy.require(backend.namespace==groups.authority_namespace,'Actual native authority namespace required')
    original=review['original_registration']
    legacy.require(await backend.pod(original['namespace'],original['pod']) is None,'Fresh operator Pod must be absent')
    cm=await backend._read(LEDGER_NAME);meta=cm.get('metadata',{}) if isinstance(cm,dict) else {}
    legacy.require(isinstance(cm,dict) and cm.get('apiVersion')=='v1' and cm.get('kind')=='ConfigMap'
        and meta.get('namespace')==backend.namespace and meta.get('name')==LEDGER_NAME
        and meta.get('uid')==review['stopped']['ledger_uid'] and meta.get('resourceVersion')
        and not meta.get('deletionTimestamp') and not cm.get('binaryData'),'Actual reviewed existing allocation ledger required')
    state=backend._document(cm,'state.json');legacy.closed(state,{'version','allocations'},'Full existing allocation ledger required')
    legacy.require(type(state['version']) is int and state['version']==1 and isinstance(state['allocations'],dict)
        and len(state['allocations'])<=128,'Bounded complete versioned allocation ledger required')
    verifier=object.__new__(MeasuredNativeAuthority);verifier.pool=groups.node_pool;verifier._validate_allocations(state['allocations'])
    legacy.require(all(row['state']=='released' for row in state['allocations'].values())
        and not any((row['source'],row['workspace'])==(review['source'],review['workspace']) for row in state['allocations'].values()),
        'All previous claims must be released and fresh target must have no prior native attempt')
    legacy.require(await backend.pod(original['namespace'],original['pod']) is None,'Fresh operator Pod appeared during proof')
    return {'kind':'never-enrolled','ledger_uid':meta['uid'],'attempt':None}


async def migrate_fresh(context,review,*,contract_raw,contract_sha256):
    legacy.require(hashlib.sha256(Path(legacy.__file__).read_bytes()).hexdigest()==FROZEN_HANDOVER_SHA256,
        'Exact frozen Source migration implementation required')
    contract=node_successor.validate_contract(contract_raw,contract_sha256)
    legacy.validate_context(context)
    mode=context['operator_qualification']
    legacy.require(mode.policy_hash==context['policy'].hash==contract['policy_hash'] and mode.workload_image==WORKLOAD_IMAGE
        and set(mode.workspaces)==set(contract['workspaces']) and mode.node_pool['memory_budget_mib']==25600
        and mode.node_pool['max_workspaces']==2 and mode.node_pool['headroom_mib']==1024,
        'Exact reviewed notebook531 CPS pair mode required')
    for scope,profile in contract['workspaces'].items():
        actual=mode.workspaces[scope]
        legacy.require(actual['profiles']==[profile['profile']] and actual['members']==sorted(contract['operator_members'][scope])
            and mode.cap_mib(profile['profile'])==profile['cap_mib'], 'Mode identities must match independent Root contract')
    validate_review(review,contract)
    namespace=dict(legacy.migrate.__globals__,OLD_PROFILE='interactive-cpu',
        validate_review=lambda value:validate_review(value,contract),verify_stopped=verify_fresh_stopped)
    migrate=FunctionType(legacy.migrate.__code__,namespace)
    return await migrate(context,review)
