#!/usr/bin/env python3
"""Offline proposal from actual reviewed catalog and existing operator approvals.

No accounts/workspaces/PVCs are invented. No API client, images, GPU or passed
proofs. Root must separately review and apply through existing normal APIs.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path


def render(policy, operator):
    from cps_compute.policy import Policy
    from cps_compute.native_qualification import NativeGroupQualification
    from cps_compute.personal_native import CAPABILITY
    from cps_compute.personal_qualification_probe import candidate_profile,IMAGE
    prior=NativeGroupQualification.from_config(operator,policy)
    if prior.personal_candidate:
        raise ValueError('Do not rewrite an already admitted personal candidate')
    from cps_compute.native_scheduler_operator_contract import validate_operator_mode
    validate_operator_mode(prior,policy)
    names=[name for name,row in policy.catalog['profiles'].items()
           if row.get('personal',{}).get('capability')==CAPABILITY]
    if len(names)!=1:raise ValueError('Exactly one reviewed canonical personal artifact required')
    descriptor={'profile':names[0],'operator_profile':'interactive-native-qualification-10'}
    catalog=copy.deepcopy(policy.catalog);catalog.pop('policyHash',None)
    entry=candidate_profile(policy,descriptor)
    name=descriptor['operator_profile']
    if name in catalog['profiles'] and catalog['profiles'][name]!=entry:
        raise ValueError('Existing operator ten-GiB profile cannot be silently replaced')
    catalog['profiles'][name]=entry
    target=Policy(catalog);catalog['policyHash']=target.hash
    config=copy.deepcopy(operator)
    config.update(policy_hash=target.hash,policy_version=target.version,workloadImage=IMAGE,
                  profile_caps={name:10240},personal_candidate=descriptor)
    config['node_pool'].update(memory_budget_mib=20480,max_workspaces=2)
    for approval in config['workspaces'].values():
        approval.update(profiles=[name],ceiling={'cpu':entry['cpu'],'memory':entry['memory'],'gpuMemoryGiB':10})
    mode=NativeGroupQualification.from_config(config,target)
    return {'policy.json':catalog,'operator-qualification.json':json.loads(mode.document),
            'source-registration-updates.json':{scope:{'workspace':scope.split(':',1)[1],
                'policy_hash':target.hash,**copy.deepcopy(value)} for scope,value in mode.workspaces.items()},
            'review.json':{'live_applied':False,'hardware_qualified':False,
                'predecessor_policy_hash':policy.hash,
                'predecessor_operator_sha256':'sha256:'+hashlib.sha256(prior.document).hexdigest(),
                'normal_source_reconciliation_required':True}}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--render',action='store_true')
    for key in ('policy','policy-sha256','operator','operator-sha256','output'):p.add_argument('--'+key)
    args=p.parse_args()
    if not args.render:print('{"inert":true,"live_applied":false}');return
    if not all(vars(args).values()):raise ValueError('Exact pinned private inputs and fresh output required')
    values=[]
    for key in ('policy','operator'):
        raw=Path(getattr(args,key)).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=getattr(args,key+'_sha256'):raise ValueError('Input bytes changed')
        values.append(json.loads(raw))
    from cps_compute.policy import Policy
    result=render(Policy(values[0]),values[1]);output=Path(args.output);output.mkdir(mode=0o700)
    for name,value in result.items():(output/name).write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')


if __name__=='__main__':main()
