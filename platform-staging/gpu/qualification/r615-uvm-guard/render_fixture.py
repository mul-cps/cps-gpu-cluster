#!/usr/bin/env python3
"""Render a byte-pinned private QA proposal; never apply, set caps or release gates."""
import copy
import hashlib
import json
from pathlib import Path
import runtime_probe

NAMESPACE='cps-r615-uvm-guard-20261008'
GPU='GPU-16128952-b438-556a-00bb-93039ee24e56'
TORCH_IMAGE='ghcr.io/mul-cps/cps-jupyter-notebook@sha256:6b6a8d6a225df1b938fe98bcdad9e547aef249347392ce8f29adb3fedda512ae'
GATE_SHA='136e47051ae2c00a63016047d0c462f80724be3f19c55815efca5c88de83c3a1'


def render():
    here=Path(__file__).resolve().parent;support=here.parents[2]/'scheduler/qualification/r615-pod-cap'
    baseline=json.loads((support/'qa-fixture.json').read_text())
    data={'runtime_probe.py':(here/'runtime_probe.py').read_text()}
    for filename,expected in dict(runtime_probe.SUPPORT,**{'gate_wait.py':GATE_SHA}).items():
        raw=(support/filename).read_bytes()
        runtime_probe.require(hashlib.sha256(raw).hexdigest()==expected,'Pinned fixture support mismatch')
        data[filename]=raw.decode()
    data_sha=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    configmap_name='r615-uvm-guard-'+data_sha[:12]
    namespace={'apiVersion':'v1','kind':'Namespace','metadata':{'name':NAMESPACE,
               'labels':{'compute.cps.unileoben.ac.at/qualification':'trusted-r615-uvm-guard'}}}
    configmap={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':configmap_name,'namespace':NAMESPACE,
               'annotations':{'source.data.sha256':data_sha,'qualification.production':'false'}},'immutable':True,'data':data}
    items=[namespace,configmap]
    for original in (item for item in baseline['items'] if item['kind']=='Pod'):
        pod=copy.deepcopy(original);peer=pod['metadata']['name']=='r615-peer';name='uvm-guard-peer' if peer else 'uvm-guard-main'
        pod['metadata']['name']=name;pod['metadata']['namespace']=NAMESPACE
        pod['metadata']['annotations']={'source.data.sha256':data_sha,'source.support.commit':'fd90fc289207d295bb1907dd2beb52f0dfdce5cb',
          'qualification.production':'false','qualification.hostile-isolation':'false',
          'qualification.cap-controller':'manual-root-unqualified','qualification.expected-gpu':GPU}
        main=pod['spec']['containers'][0]
        if not peer:main['image']=TORCH_IMAGE;main['imagePullPolicy']='Never';main['resources']['limits']['memory']='2Gi'
        main['env'] += [{'name':'LD_PRELOAD','value':''},{'name':'CUDA_VISIBLE_DEVICES','value':'0'},
                        {'name':'HOME','value':'/tmp'},{'name':'XDG_CACHE_HOME','value':'/tmp/.cache'}]
        main['volumeMounts']=[mount for mount in main['volumeMounts'] if mount['name']!='driver']
        pod['spec']['volumes']=[volume for volume in pod['spec']['volumes'] if volume['name']!='driver']
        pod['spec'].pop('imagePullSecrets',None)
        for container in pod['spec']['initContainers']+pod['spec']['containers']:container['imagePullPolicy']='Never'
        for volume in pod['spec']['volumes']:
            if volume['name']=='scratch':volume['emptyDir']['sizeLimit']='128Mi'
        mode='heartbeat' if peer else 'all'
        main['command']=['python','-u','-c',"import json,os,runpy,sys;sys.path.insert(0,'/qualification'); from pathlib import Path; "
          "v=json.loads(Path('/phase/parent.json').read_text()); "
          "assert v.get('pod_uid')==os.environ['POD_UID'], 'Exact current phase Pod UID required'; "
          f"sys.argv=['runtime_probe.py','--execute','--mode','{mode}','--device-uuid','{GPU}',"
          "'--parent-cgroup',v['parent_cgroup'],'--pod-uid',os.environ['POD_UID'],"
          "'--module-parameters','/host/uvm-parameters','--support-dir','/qualification']; "
          "runpy.run_path('/qualification/runtime_probe.py',run_name='__main__')"]
        main['volumeMounts'].append({'name':'uvm-parameters','mountPath':'/host/uvm-parameters','readOnly':True})
        for volume in pod['spec']['volumes']:
            if volume['name']=='source':volume['configMap']['name']=configmap_name
        pod['spec']['volumes'].append({'name':'uvm-parameters','hostPath':{'path':'/sys/module/nvidia_uvm/parameters','type':'Directory'}})
        items.append(pod)
    return {'apiVersion':'v1','kind':'List','items':items}


if __name__=='__main__':print(json.dumps(render(),indent=2))
