#!/usr/bin/env python3
"""Default-inert observer: historical exception + NEW finite current pair."""
import argparse,json,os,stat
from pathlib import Path
import prepare_harness as p
from run_kernel_controls import load

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    for key in ('source-sha256','preflight-sha256','binding-sha256','history-sha256'):
        parser.add_argument('--'+key)
    for key in ('binding','history','output'):parser.add_argument('--'+key,type=Path)
    a=parser.parse_args(argv)
    if not a.execute:
        print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False,'hardware_qualification':False}));return 0
    p.require(all(vars(a).values()) and p.sha(Path(__file__).read_bytes())==a.source_sha256,'Exact reviewed new observer inputs required')
    binding=p.validate_binding(p.parse(p.read_pinned(a.binding,a.binding_sha256,private=True)))
    history=p.parse(p.read_pinned(a.history,a.history_sha256,private=True))
    h,_=load(Path(__file__).with_name('run_group_acceptance.py'),a.preflight_sha256,'recovery_physical_readonly')
    targets=[{k:t[k]for k in('namespace','name','pod_uid')}for t in binding['targets']]
    p.require(h['BOUND_CONFIG']=={'observer_uid':binding['observer_uid'],'driver_generation':binding['pool']['driver_generation'],'targets':targets},'Exact actual new controlled lifetimes required')
    loaded=h['_validate_history'](history,targets,allow_current=True)
    parent=a.output.parent.lstat();p.require(stat.S_ISDIR(parent.st_mode)and parent.st_uid==os.getuid()and stat.S_IMODE(parent.st_mode)==0o700,'Private owned output required');a.output.mkdir(mode=0o700)
    request={k:binding['pool'][k]for k in('node','node_uid','boot_id','gpu_uuid','driver_generation')}
    request.update(core_sha256=h['CORE'],uvm_sha256=h['UVM'],health_sha256=h['HEALTH_SHA'],controller_sha256=h['CONTROLLER_SHA'],cap_bytes=h['CAP'],budget_bytes=h['BUDGET_BYTES'],targets=[],terminal_history=history)
    observed=h['checked_run'](h['OBSERVER_ARGV'],source=h['python_stdin_source'](h['HOST_SOURCE'],request))
    p.require(observed.get('kind')=='native-group-host-observation'and observed.get('targets')==[] and all(observed.get(k)==request[k]for k in('node','node_uid','boot_id','gpu_uuid','driver_generation')),'Exact actual complete physical observation required')
    loaded.reader.validate_observed(history,observed.get('retired_caps'))
    h['write_json'](a.output/'physical.json',observed)
    h['write_json'](a.output/'receipt.json',{'state':'physical-history-measured-awaiting-Root-review','hardware_qualification':False,'normal_stop_passed':False,'historical_exception_count':1,'source_sha256':a.source_sha256,'binding_raw_sha256':a.binding_sha256,'history_raw_sha256':a.history_sha256,'physical_raw_sha256':p.sha((a.output/'physical.json').read_bytes())})
    print(json.dumps({'state':'physical-history-measured-awaiting-Root-review','hardware_qualification':False}));return 0

if __name__=='__main__':main()
