#!/usr/bin/env python3
"""Default-inert own-cycle expiry inverse with authenticated historical recovery.

The frozen 3c807/792/360 Source, actor, cycle, registration and ledger guards
remain in force. This sibling replaces only the reviewed runtime image pins
and the historical physical-review predicate. It cannot renew or Start.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import stat

import recovery_history as r
import recovery_source_loader as loader
import prepare_recovery_harness as prepare

WINDOW_SHA = '3c807348b85139ac90ae83d253019a242da344febcfe106e1ca32eb9a83697c3'
QUALIFIED_SHA = '79216423877d8079499c13b8d4f6c5abb90077a9174fd9d3a6e2d295bd166990'
HISTORICAL_AGENT_SHA = '05a6ca95eaaaf79cdbbdffec8172c804676d982a4154a422188639cd6b24f09b'
ACTIVE_AGENT_SHA = '34ce5b9bb8d48aa3459c151acc19464772e498a8946c7f621fed73abc5b0ba5a'
RECOVERY_SHA = '25c9514fee19c478d82aa891f2d67a8018b1e799abbedd1d1397ea13b80bd25b'
POLICY = 'sha256:02316f90f705f5550ab54d1d514ed48f73aa6a13324eea7d4aeaaef959af2fd5'

def protected(path,pin):
    r.require(type(pin) is str and re.fullmatch('[a-f0-9]{64}',pin), 'Explicit protected raw source pin required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        before=os.fstat(fd)
        r.require(stat.S_ISREG(before.st_mode)and before.st_uid==10001 and before.st_nlink==1
            and stat.S_IMODE(before.st_mode)in(0o400,0o600)and 0<before.st_size<=8*1024*1024,
            'Protected UID10001 single-link regular source/input required')
        raw=os.read(fd,8*1024*1024+1);after=os.fstat(fd)
        r.require(len(raw)==before.st_size and hashlib.sha256(raw).hexdigest()==pin
            and all(getattr(before,k)==getattr(after,k)for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')),
            'Exact stable protected source/input bytes required')
        return raw
    finally:os.close(fd)

def validate_physical_review(review, capture, history, runtime, source, history_pin):
    r.closed(review, {'version','state','source','observed_at','policy_hash','ledger_uid',
        'ledger_state_sha256','normal_close_receipt_sha256','protected_retirement_capture_sha256',
        'history_raw_sha256','all_native_released','physical_inert_history_verified',
        'historical_recovery_uid','normal_stop_passed','hardware_qualification'})
    observed = datetime.fromisoformat(review['observed_at'].replace('Z','+00:00'))
    r.require(type(review['version']) is int and review['version'] == 2
        and review['state'] == 'source-close-and-physical-inert-history-root-reviewed'
        and review['source'] == source and review['policy_hash'] == POLICY
        and review['ledger_uid'] == runtime['ledger_uid']
        and review['ledger_state_sha256'] == runtime['ledger_state_sha256']
        and review['history_raw_sha256'] == history_pin
        and review['all_native_released'] is True and review['physical_inert_history_verified'] is True
        and review['historical_recovery_uid'] == r.POD
        and review['normal_stop_passed'] is False and review['hardware_qualification'] is False
        and observed.utcoffset().total_seconds() == 0
        and 0 <= (datetime.now(timezone.utc)-observed).total_seconds() <= 600,
        'Fresh distinct Source-close and inert-history review required; never a normal Stop claim')
    for key in ('normal_close_receipt_sha256','protected_retirement_capture_sha256','history_raw_sha256'):
        r.require(type(review[key]) is str and re.fullmatch('[a-f0-9]{64}', review[key]), 'Exact protected raw review pin required')
    r.require(capture.get('kind') == 'native-group-host-observation' and capture.get('targets') == []
        and all(capture.get(k) == history[k] for k in ('node','node_uid','boot_id','gpu_uuid','driver_generation')),
        'Complete no-active-target current-epoch physical observation required')
    r.validate_observed(history, capture.get('retired_caps'))
    return review

async def actual_authorities(backend, history, state):
    """Actual exact named GETs; raw snapshots never substitute for live authority."""
    closure = history['recovery']
    allocation = state.get('allocations',{}).get(r.BINDING)
    enrollment = r.parse(closure['enrollment']['data']['enrollment.json'])
    r.require(type(allocation) is dict and allocation.get('state') == 'released'
        and allocation.get('binding_id') == r.BINDING and allocation.get('attempt') == r.ATTEMPT
        and all(allocation.get(key)==value for key,value in enrollment.items()),
        'The exact historical recovered allocation must actually be released')
    for key,prefix,data in (('enrollment','cps-native-enrollment-','enrollment.json'),
            ('audit','cps-native-recovery-','recovery.json'),('cleanup','cps-native-cleanup-','receipt.json')):
        expected = closure[key]
        actual = await backend._call(backend.core.read_namespaced_config_map,
            expected['metadata']['name'], expected['metadata']['namespace'])
        r.immutable(actual,prefix,data)
        # ResourceVersion may change on an otherwise immutable object. Its UID,
        # full data and complete semantic metadata must match the Root capture.
        for value in (actual,expected):
            r.require(not value.get('metadata',{}).get('ownerReferences') and not value.get('metadata',{}).get('deletionTimestamp'), 'Recovery authority must remain unowned and present')
        r.require(actual['metadata']['uid'] == expected['metadata']['uid']
            and actual['data'] == expected['data']
            and actual['metadata'].get('labels') == expected['metadata'].get('labels')
            and actual.get('immutable') is True, 'Actual recovery authority UID/body changed')
    r.require(await backend.cleanup_receipt(r.BINDING) == closure['marker']['receipt'],
        'Installed SDK must authenticate the distinct actual enrollment/audit/cleanup chain')

def adapt_foundation(q, qualified_raw, history, loaded, history_pin, gateway_image):
    r.require(hashlib.sha256(qualified_raw).hexdigest() == QUALIFIED_SHA, 'Exact unchanged qualified foundation required')
    r.require(type(gateway_image) is str and re.fullmatch(r'ghcr\.io/mul-cps/cps-compute@sha256:[a-f0-9]{64}',gateway_image), 'Explicit reviewed immutable gateway image required')
    binding = {'pool':{k:history[k]for k in ('node','node_uid','boot_id','gpu_uuid','driver_generation')},'targets':[]}
    loader.validate(loaded,history,binding)
    ns = q.build_context.__globals__
    tree = ast.parse(qualified_raw)
    function = next(node for node in tree.body if isinstance(node,ast.AsyncFunctionDef) and node.name == 'build_context')
    lines = qualified_raw.decode().splitlines(keepends=True)
    source = ''.join(lines[function.lineno-1:function.end_lineno])
    start = source.index(' retirement=R.load(')
    end = source.index(' protected(a.kubeconfig',start)
    source = source[:start] + ' retirement=_recovery_physical_review(a,review,runtime)\n' + source[end:]
    needle = "authority._validate_allocations(snapshot.state['allocations'])"
    r.require(source.count(needle) == 1, 'Exact frozen fence insertion point required')
    source = source.replace(needle,needle+';await _recovery_actual_authorities(backend,snapshot.state)')
    def physical(a,review,runtime):
        retirement = ns['R'].load(a.physical_retirement_review,review['physical_retirement_review_sha256'])
        ns['protected'](a.normal_close_receipt,retirement['normal_close_receipt_sha256'])
        capture = r.parse(ns['protected'](a.protected_retirement_capture,retirement['protected_retirement_capture_sha256']))
        return validate_physical_review(retirement,capture,history,runtime,a.source,history_pin)
    async def authority(backend,state):
        await actual_authorities(backend,history,state)
    ns.update(GATEWAY_IMAGE=gateway_image,NODE_SOURCE_SHA=ACTIVE_AGENT_SHA,
        _recovery_physical_review=physical,_recovery_actual_authorities=authority)
    exec(compile(source,'pinned-historical-recovery-expiry-context','exec'),ns)
    q.build_context = ns['build_context']
    return q

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('--execute',action='store_true')
    for name in ('adapter-sha256','adapter-review','adapter-review-sha256','history','history-sha256','window-source','model-source','control-source','node-source','recovery-source'):
        parser.add_argument('--'+name)
    args,window_args=parser.parse_known_args(argv)
    if not args.execute:
        print(r.canonical({'state':'inert','writes':False,'api_calls':False,'workspace_started':False,'normal_stop_passed':False}));return 0
    r.require(os.geteuid()==10001 and all(vars(args).values()), 'Trusted UID10001 and complete explicit adapter inputs required')
    spec=importlib.util.spec_from_file_location('pinned_own_cycle_window',args.window_source)
    window=importlib.util.module_from_spec(spec)
    # Use the same protected stat/hash reader before executing the frozen window.
    raw=protected(args.window_source,WINDOW_SHA)
    protected(__file__,args.adapter_sha256)
    exec(compile(raw,args.window_source,'exec'),window.__dict__)
    approval=r.parse(protected(args.adapter_review,args.adapter_review_sha256))
    r.closed(approval,{'version','enabled','operation','source','gateway_image','history_raw_sha256','reader_sha256','loader_sha256','adapter_sha256','node_source_sha256','historical_node_source_sha256','recovery_source_sha256'})
    r.require(type(approval['version']) is int and approval['version']==2 and approval['enabled'] is True
        and approval['operation']=='restore-expiry' and approval['source'] in ('cps','cit')
        and approval['history_raw_sha256']==args.history_sha256 and approval['adapter_sha256']==args.adapter_sha256
        and approval['node_source_sha256']==ACTIVE_AGENT_SHA
        and approval['historical_node_source_sha256']==HISTORICAL_AGENT_SHA
        and approval['recovery_source_sha256']==RECOVERY_SHA
        and approval['reader_sha256']==hashlib.sha256(Path(r.__file__).read_bytes()).hexdigest()
        and approval['loader_sha256']==hashlib.sha256(Path(loader.__file__).read_bytes()).hexdigest(),
        'Explicit disabled-by-default Root historical adapter review required')
    history=r.parse(protected(args.history,args.history_sha256))
    validators=prepare.bundle(args.model_source,args.control_source,args.node_source,HISTORICAL_AGENT_SHA,args.recovery_source,RECOVERY_SHA)
    loaded=loader.load_sources(validators)
    original=window.load_frozen
    def adapted(qualified_raw,renewal_raw,path):
        return adapt_foundation(original(qualified_raw,renewal_raw,path),qualified_raw,history,loaded,args.history_sha256,approval['gateway_image'])
    window.load_frozen=adapted
    original_context=window.build_context
    async def only_inverse(a,review,*rest):
        r.require(a.source==approval['source'] and review['operation']=='restore-expiry', 'Only the actual own-cycle expiry inverse is admitted')
        return await original_context(a,review,*rest)
    window.build_context=only_inverse
    return window.main(['--execute',*window_args])

if __name__=='__main__':main()
