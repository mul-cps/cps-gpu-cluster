"""Read-only current paired caps and optional prior-lifetime retirement checks."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import host


def validate(observed, targets, pool, previous=None):
    host.pair.require(set(targets)==set(host.pair.TARGETS) and len(set(targets.values()))==2,'two-distinct-actual-Pod-UIDs-required')
    host.pair.require(set(observed['records'])==set(targets),'complete-two-parent-journals-required')
    entries=observed['inventory']['entries']
    active=[e for e in entries if not e['offline']]
    host.pair.require(len(active)==2 and all(e['used']==0 for e in entries if e['offline']), 'foreign-or-charged-retired-native-entry')
    inodes=[]
    for name,uid in targets.items():
        r=observed['records'][name]
        host.pair.require(r['state']=='sealed' and r['intent']['pod_uid']==uid
            and r['identity']['pod_uid']==uid and r['intent']['cap_mib']==5120
            and r['readback']=={'hard':5120*1024*1024,'soft':5120*1024*1024},'exact-sealed-five-GiB-parent-required')
        host.pair.require(all(r['identity'][k]==pool[k] for k in ('node_uid','gpu_uuid','boot_id','driver_generation')), 'actual-native-epoch-differs')
        inode=r['identity']['cgroup_inode'];inodes.append(inode)
        found=[e for e in active if e['inode']==inode]
        host.pair.require(len(found)==1 and found[0]['hard']==found[0]['soft']==5120*1024*1024
            and found[0]['pinned'] is True and found[0]['default_hierarchy'] is True
            and 0<=found[0]['used']<=found[0]['hard'], 'actual-driver-five-GiB-cap-differs')
    host.pair.require(len(set(inodes))==2 and {e['inode'] for e in active}==set(inodes), 'native-parents-not-distinct')
    host.pair.require(sum(e['used'] for e in entries)<=pool['memory_budget_mib']*1024*1024,'aggregate-native-budget-exceeded')
    if previous:
        host.pair.require(set(previous['targets'])==set(targets) and previous['pool']==pool,'prior-pair-scope-or-epoch-differs')
        for name,uid in previous['targets'].items():
            host.pair.require(uid!=targets[name],'restart-reused-original-Pod-UID')
            r=observed['previous'][name]
            host.pair.require(r['state']=='retired-inert-cap' and r['intent']['pod_uid']==uid
                and r['identity']==previous['observed']['records'][name]['identity'], 'original-restart-parent-not-retired')
    return True


def probe_argv(targets, pool):
    result={}
    for name,uid in targets.items():
        gpu=pool['gpu_uuid']
        result[name]={'namespace':'jupyterhub','pod':'jupyter-cpsnativegroup'+name[-1]+'--rtc','pod_uid':uid,
            'same_parent_vmm_direct':['<verified-native-imports>','--execute','--mode','vmm-direct','--gpu-uuid',gpu,'--cap-mib','5120'],
            'same_parent_imports':['python','<verified-same_pod_imports.py>','--execute','--gpu-uuid',gpu,
                '--binary','<verified-native-imports>','--directory','<fresh-UID1000-owned-0700-directory>','--mode','ipc'],
            'same_parent_mps':['python','<verified-mps_probe.py>','--execute','--case','oom','--duration','120',
                '--source-sha256','<actual-probe-SHA>','--control-sha256','<actual-control-ELF-SHA>',
                '--server-sha256','<actual-server-ELF-SHA>','--expected-gpu-uuid',gpu,
                '--expected-pod-uid',uid,'--expected-driver-generation',pool['driver_generation']]}
    return result


def main(args):
    host.private_root();wrapper=host.original_host()
    plan=host.read_private(Path(args.plan))
    host.pair.require(hashlib.sha256(wrapper.canonical(plan)).hexdigest()==args.plan_sha256,'reviewed-plan-changed')
    pool=plan['capacity']['pool'];targets={};pods={}
    for name in host.pair.TARGETS:
        pod=host.get('pod','jupyter-cpsnativegroup'+name[-1]+'--rtc','jupyterhub')
        host.pair.require(pod['spec'].get('nodeName')==pool['node'] and pod['status']['phase']=='Running'
            and any(c['type']=='Ready' and c['status']=='True' for c in pod['status'].get('conditions',[])), 'both-actual-Pods-must-be-Ready')
        targets[name]=pod['metadata']['uid']
        pods[name]={'uid':pod['metadata']['uid'],'images':[{'name':c['name'],'imageID':c.get('imageID'),
            'restartCount':c.get('restartCount')} for c in pod['status'].get('containerStatuses',[])],
            'init':pod['status'].get('initContainerStatuses',[])}
    previous=host.read_private(Path(args.previous)) if args.previous else None
    if previous:
        host.pair.require(bool(args.previous_sha256) and hashlib.sha256(wrapper.canonical(previous)).hexdigest()==args.previous_sha256,
                          'exact-previous-readback-hash-required')
    observed=host.native_read(pool,targets,previous['targets'] if previous else None)
    validate(observed,targets,pool,previous)
    for name,uid in targets.items():
        pod=host.get('pod','jupyter-cpsnativegroup'+name[-1]+'--rtc','jupyterhub')
        host.pair.require(pod['metadata']['uid']==uid and pod['status']['phase']=='Running'
            and any(c['type']=='Ready' and c['status']=='True' for c in pod['status'].get('conditions',[])), 'Pod-replaced-or-not-Ready-during-native-capture')
    receipt={'version':1,'targets':targets,'pool':pool,'observed':observed,'pods':pods,
        'plan_sha256':args.plan_sha256,'created_at_ns':time.time_ns(),'restart_observed':bool(previous),
        'exact_current_caps_observed':True,'hardware_cap_qualified':False,
        'probe_argv':probe_argv(targets,pool),'imports_qualified':False,'mps_qualified':False,
        'production_qualified':False,'kai_placement_qualified':False}
    path=host.PRIVATE/('pair-readback-'+str(time.time_ns())+'.json')
    wrapper.write(path,wrapper.canonical(receipt))
    print(json.dumps({'private_readback':str(path),'sha256':hashlib.sha256(wrapper.canonical(receipt)).hexdigest(),
        'exact_current_caps_observed':True,'restart_observed':bool(previous),'hardware_cap_qualified':False}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--plan-sha256',required=True)
    p.add_argument('--previous');p.add_argument('--previous-sha256')
    try:main(p.parse_args())
    except Exception as error:
        print(json.dumps({'failed':True,'failure_type':type(error).__name__,
            'failure_code':str(error) if type(error) is RuntimeError else 'private-readback-failed'}),file=sys.stderr)
        raise SystemExit(1)
