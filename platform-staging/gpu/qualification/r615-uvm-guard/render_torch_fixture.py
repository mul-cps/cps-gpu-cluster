#!/usr/bin/env python3
"""Render separate Torch-only5GiB proposal; retain original actual59cf fixtures."""
import copy
import hashlib
import json
from pathlib import Path
import render_fixture


def render():
    here=Path(__file__).resolve().parent
    original=json.loads((here/'fixture-proposal.json').read_text())
    cm=copy.deepcopy(next(o for o in original['items'] if o['kind']=='ConfigMap'))
    cm['data']['torch_probe.py']=(here/'torch_probe.py').read_text()
    digest=hashlib.sha256(json.dumps(cm['data'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    cm['metadata']['name']='r615-uvm-torch-'+digest[:12];cm['metadata']['annotations']['source.data.sha256']=digest
    items=[cm]
    for old in (o for o in original['items'] if o['kind']=='Pod'):
        pod=copy.deepcopy(old);peer=old['metadata']['name']=='uvm-guard-peer'
        pod['metadata']['name']='uvm-guard-torch-peer' if peer else 'uvm-guard-torch'
        pod['metadata']['annotations']['source.data.sha256']=digest
        for volume in pod['spec']['volumes']:
            if volume['name']=='source':volume['configMap']['name']=cm['metadata']['name']
        if not peer:
            gate=pod['spec']['initContainers'][0];gate['command'][-1]='5120'
            main=pod['spec']['containers'][0]
            main['command']=['python','-u','-c',"import json,os,runpy,sys;sys.path.insert(0,'/qualification'); from pathlib import Path; "
              "v=json.loads(Path('/phase/parent.json').read_text()); "
              "assert v.get('pod_uid')==os.environ['POD_UID'], 'Exact current phase Pod UID required'; "
              f"sys.argv=['torch_probe.py','--execute','--mode','torch','--cap-mib','5120','--device-uuid','{render_fixture.GPU}',"
              "'--parent-cgroup',v['parent_cgroup'],'--pod-uid',os.environ['POD_UID'],"
              "'--module-parameters','/host/uvm-parameters','--support-dir','/qualification']; "
              "runpy.run_path('/qualification/torch_probe.py',run_name='__main__')"]
        items.append(pod)
    return {'apiVersion':'v1','kind':'List','items':items}


if __name__=='__main__':print(json.dumps(render(),indent=2))
