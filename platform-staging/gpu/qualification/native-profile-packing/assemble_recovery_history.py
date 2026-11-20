#!/usr/bin/env python3
"""Default-inert local assembly of real Root captures; never create recovery proof."""
import argparse
from dataclasses import asdict
import os
from pathlib import Path
import stat

import recovery_history as r
import recovery_source_loader as loader
import prepare_recovery_harness as prepare

def assemble(host, original_raw, plan_raw, review_raw, marker_raw, enrollment, audit, cleanup, validators):
    directory=host['directories']['journal']
    r.closed(directory,{'ownerUid','mode','records'})
    r.require(type(directory['ownerUid'])is int and directory['ownerUid']==0
        and type(directory['mode'])is int and directory['mode']==0o700
        and type(directory['records'])is dict,'Actual protected complete journal directory required')
    records=[]
    for name,row in directory['records'].items():
        r.closed(row,{'uid','mode','nlink','rawSha256','value'})
        r.require(type(name)is str and name.endswith('.json')and r.uuid_value(name[:-5])
            and type(row['uid'])is int and row['uid']==0 and type(row['mode'])is int and row['mode']==0o600
            and type(row['nlink'])is int and row['nlink']==1,
            'Root0600 single-link exact journal capture required')
        records.append({'pod_uid':name[:-5],'journal_sha256':row['rawSha256'],'record':row['value']})
    loaded=loader.load_sources(validators)
    original=loaded.models.CapRecord.from_dict(r.parse(original_raw))
    pool={'node':original.intent.node,**asdict(original.identity.epoch)}
    r.require(host['bootId']==pool['boot_id']and host['driverGeneration']==pool['driver_generation'],
        'Captured protected history epoch changed')
    history={'version':2,'protocol':'native-packing-terminal-history/v2',**pool,
        'controller_sha256':r.MODEL_SHA,'records':sorted(records,key=lambda x:x['pod_uid']),
        'recovery':{'original_raw':original_raw.decode(),'plan':r.parse(plan_raw),'review':r.parse(review_raw),
            'marker':r.parse(marker_raw),'enrollment':enrollment,'audit':audit,'cleanup':cleanup,
            'protected_raw_sha256':{'plan':r.raw_sha(plan_raw),'review':r.raw_sha(review_raw),'marker':r.raw_sha(marker_raw)}}}
    loader.validate(loaded,history,{'pool':pool,'targets':[]})
    return history

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',action='store_true')
    captures=('host-capture','original-archive','plan','review','marker','enrollment','audit','cleanup')
    for name in captures:
        parser.add_argument('--'+name,type=Path);parser.add_argument('--'+name+'-sha256')
    for name in ('model-source','control-source','node-source','recovery-source','source-root','output'):parser.add_argument('--'+name,type=Path)
    for name in ('health-sha256','core-sha256','uvm-sha256'):parser.add_argument('--'+name)
    args=parser.parse_args(argv)
    if not args.prepare:
        print(r.canonical({'state':'inert','api_calls':False,'gpu_calls':False,'hardware_qualification':False}));return 0
    r.require(all(vars(args).values()),'Every actual captured input and raw pin required')
    validators=prepare.bundle(args.model_source,args.control_source,args.node_source,
        '05a6ca95eaaaf79cdbbdffec8172c804676d982a4154a422188639cd6b24f09b',args.recovery_source,
        '25c9514fee19c478d82aa891f2d67a8018b1e799abbedd1d1397ea13b80bd25b')
    values={name.replace('-','_'):prepare.p.read_pinned(getattr(args,name.replace('-','_')),getattr(args,name.replace('-','_')+'_sha256'),private=True)for name in captures}
    result=assemble(r.parse(values['host_capture']),values['original_archive'],values['plan'],values['review'],values['marker'],
        r.parse(values['enrollment']),r.parse(values['audit']),r.parse(values['cleanup']),validators)
    parent=args.output.parent.lstat()
    r.require(stat.S_ISDIR(parent.st_mode)and parent.st_uid==os.getuid()and stat.S_IMODE(parent.st_mode)==0o700
        and not args.output.exists()and not args.output.is_symlink(),'New private owned output required')
    args.output.mkdir(mode=0o700)
    path=args.output/'terminal-history-v2.json';path.write_text(r.canonical(result)+'\n');path.chmod(0o600)
    key='activation-runtime-prepared/qualified-six-retired-preflight/run_qualified_preflight.py'
    host_source=prepare.historical_host_source(prepare.p.read_pinned(args.source_root/key,prepare.p.SOURCE_PINS[key]),validators)
    target=args.output/'historical-observer-source.py';target.write_bytes(host_source);target.chmod(0o600)
    import re
    r.require(all(type(getattr(args,k))is str and re.fullmatch('[a-f0-9]{64}',getattr(args,k))for k in ('health_sha256','core_sha256','uvm_sha256')),'Explicit Root-reviewed health/module pins required')
    request={k:result[k]for k in ('node','node_uid','boot_id','gpu_uuid','driver_generation')}
    request.update(targets=[],terminal_history=result,health_sha256=args.health_sha256,core_sha256=args.core_sha256,uvm_sha256=args.uvm_sha256)
    target=args.output/'historical-host-request.json';target.write_text(r.canonical(request)+'\n');target.chmod(0o600)
    receipt={'version':1,'state':'actual-history-assembled-awaiting-Root-review','history_raw_sha256':prepare.p.sha(path.read_bytes()),
        'journal_count':len(result['records']),'historical_exception_count':1,
        'normal_stop_passed':False,'hardware_qualification':False,
        'host_source_raw_sha256':prepare.p.sha(host_source),
        'host_request_raw_sha256':prepare.p.sha((args.output/'historical-host-request.json').read_bytes()),
        'validator_source_pins':{key:value['sha256']for key,value in validators.items()},
        'input_raw_sha256':{name:getattr(args,name.replace('-','_')+'_sha256')for name in captures}}
    target=args.output/'preparation-receipt.json';target.write_text(r.canonical(receipt)+'\n');target.chmod(0o600)
    print(r.canonical({'state':receipt['state'],'normal_stop_passed':False,'hardware_qualification':False}));return 0

if __name__=='__main__':main()
