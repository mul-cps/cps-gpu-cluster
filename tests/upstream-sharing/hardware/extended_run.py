#!/usr/bin/env python3
"""Render by default. --execute requires a fresh explicit parent idle release."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
import uuid

HERE = Path(__file__).resolve().parent
IMAGE = 'ghcr.io/mul-cps/cps-ubuntu-release-upgrade@sha256:5030556ecf8cd38fc9acc4676316bd0a3217d1ab10930b75b9dba7106e8f4004'


def run(args, *, data=None, timeout=30):
    return subprocess.check_output(args, input=data, text=True, timeout=timeout)


def manifest(a, name, case):
    return {'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':a.namespace,
        'labels':{'cps.unileoben.ac.at/extended-probe':a.run_id},
        'annotations':{'nvidia.com/container.main.gpu-memory.request':'5120Mi',
            'nvidia.com/container.main.gpu-memory.limit':'5120Mi',
            'nvidia.com/container.main.gpu-compute.mode':'time-slicing',
            'gpu-compute.mode':'time-slicing','gpu-fraction-container-name':'main',
            'nvidia.com/container.main.gpus.devices':'k8s.device-plugin.nvidia.com/gpu='+a.gpu_uuid,
            'required-plugins.noderesource.dev/container.main':'["gpu-fractioning"]'}},
        'spec':{'nodeName':a.node,'runtimeClassName':'nvidia','restartPolicy':'Never',
            'activeDeadlineSeconds':240,'terminationGracePeriodSeconds':15,
            'automountServiceAccountToken':False,
            'imagePullSecrets':[{'name':'cps-native-image-pull'}],
            'securityContext':{'runAsNonRoot':True,'runAsUser':1000,'runAsGroup':1000,'seccompProfile':{'type':'RuntimeDefault'}},
            'volumes':[{'name':'probe','configMap':{'name':name}}],
            'containers':[{'name':'main','image':IMAGE,
                'command':['python3','-u','/probe/probe.py',case,'--gpu-uuid',a.gpu_uuid],
                'env':[{'name':'NVIDIA_DRIVER_CAPABILITIES','value':'compute,utility'},
                       {'name':'EXPECTED_NODE','value':a.node},
                       {'name':'POD_UID','valueFrom':{'fieldRef':{'fieldPath':'metadata.uid'}}}],
                'resources':{'requests':{'cpu':'200m','memory':'128Mi'},'limits':{'cpu':'2','memory':'4Gi'}},
                'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},
                'volumeMounts':[{'name':'probe','mountPath':'/probe','readOnly':True}]}]}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--node', required=True)
    p.add_argument('--node-ip', required=True)
    p.add_argument('--gpu-uuid', required=True)
    p.add_argument('--namespace', default='gpu-operator')
    p.add_argument('--ssh-target', help='Explicit SSH destination for read-only sudo host observation')
    p.add_argument('--ssh-key', type=Path, help='Explicit existing SSH identity; never copied into evidence')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--run-id', default='extended-'+uuid.uuid4().hex[:10])
    p.add_argument('--cases', nargs='+', choices=['vmm','pool','ipc','crash','race','recovery'], default=['vmm','pool','ipc','crash','race','recovery','recovery'])
    p.add_argument('--execute', action='store_true')
    p.add_argument('--parent-idle-release', help='Parent message/reference explicitly releasing the pilot for this run')
    a = p.parse_args()
    if a.node != 'k3s-wk-gpu2' or not re.fullmatch(r'GPU-[0-9a-fA-F-]{36}',a.gpu_uuid):
        p.error('This fixture is limited to GPU2 and an explicit full GPU UUID')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,42}',a.run_id): p.error('Invalid bounded run-id')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,62}',a.namespace): p.error('Invalid namespace')
    if a.ssh_target and not re.fullmatch(r'(?:[a-zA-Z0-9_.-]+@)?[a-zA-Z0-9][a-zA-Z0-9.-]*',a.ssh_target):
        p.error('Explicit hostname or user@hostname SSH target required')
    a.output.mkdir(parents=True,exist_ok=False)
    name = a.run_id
    probe = (HERE/'extended_probe.py').read_text()
    cm = {'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':name,'namespace':a.namespace,
          'labels':{'cps.unileoben.ac.at/extended-probe':a.run_id}},'data':{'probe.py':probe}}
    (a.output/'configmap.json').write_text(json.dumps(cm,indent=2)+'\n')
    for i,case in enumerate(a.cases):
        (a.output/f'{i:02}-{case}.json').write_text(json.dumps(manifest(a,name,case),indent=2)+'\n')
    summary = dict(status='prepared-only',node=a.node,node_ip=a.node_ip,gpu_uuid=a.gpu_uuid,image=IMAGE,
                   cases=a.cases,probe_sha256=hashlib.sha256(probe.encode()).hexdigest(),parent_idle_release=a.parent_idle_release)
    (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    if not a.execute:
        print(f'Rendered {len(a.cases)} fixtures; no kubectl/SSH calls: {a.output}')
        return
    if not a.parent_idle_release or not a.ssh_target:
        p.error('--execute requires --parent-idle-release and --ssh-target')
    kube = ['kubectl','--request-timeout=15s']
    def get(*args): return json.loads(run(kube+list(args)+['-o','json']))
    def observe(container=None, retired=None):
        argv = ['sudo','-n','python3','-','--node',a.node,'--gpu-uuid',a.gpu_uuid]
        if container: argv += ['--container-id',container]
        if retired: argv += ['--retired-cgroup',retired]
        identity=['-i',str(a.ssh_key),'-o','IdentitiesOnly=yes'] if a.ssh_key else []
        return json.loads(run(['ssh',*identity,'-o','BatchMode=yes','-o','ConnectTimeout=8',a.ssh_target,
                              shlex.join(argv)],data=(HERE/'extended_host_observer.py').read_text(),timeout=25))
    def idle():
        pods = get('get','pods','-A','--field-selector','spec.nodeName='+a.node)['items']
        bad=[]
        for pod in pods:
            if pod['status'].get('phase') in ('Succeeded','Failed'): continue
            annotations=pod['metadata'].get('annotations',{})
            # Includes pending fractional work; never allow a fixture to race the real pilot.
            shared=any(k.startswith(('gpu-memory','gpu-fraction','required-plugins.noderesource.dev/')) or
                       k.startswith('nvidia.com/container.') for k in annotations)
            requests=any(any(k.startswith('nvidia.com/') for k in c.get('resources',{}).get(t,{}))
                         for c in pod['spec'].get('containers',[]) for t in ('requests','limits'))
            if shared or requests: bad.append(pod['metadata']['namespace']+'/'+pod['metadata']['name'])
        if bad: raise RuntimeError('Active GPU consumers or pending work: '+','.join(bad))
        state=observe()
        if state['compute_processes'].strip(): raise RuntimeError('Physical GPU compute processes still active')
        if int(state['gpu'].split(',')[2].strip())>64: raise RuntimeError('Idle physical-memory baseline exceeds 64 MiB')
        return state
    node=get('get','node',a.node)
    if not any(x['type']=='InternalIP' and x['address']==a.node_ip for x in node['status']['addresses']): raise RuntimeError('Node IP mismatch')
    if not any(x['type']=='Ready' and x['status']=='True' for x in node['status']['conditions']): raise RuntimeError('Node not Ready')
    summary['node_uid']=node['metadata']['uid']
    baseline=idle(); (a.output/'baseline.json').write_text(json.dumps(baseline,indent=2)+'\n')
    cm_uid=None
    own_uid=None
    identities=[]
    def delete_own():
        nonlocal own_uid
        if own_uid is None:return
        # UID/resourceVersion preconditions: an unexpected same-name replacement is retained.
        pod=get('get','pod',name,'-n',a.namespace)
        if pod['metadata']['uid']!=own_uid:raise RuntimeError('Replacement Pod retained; refusing cleanup')
        options=json.dumps({'apiVersion':'v1','kind':'DeleteOptions','gracePeriodSeconds':15,
            'preconditions':{'uid':own_uid,'resourceVersion':pod['metadata']['resourceVersion']}})
        run(kube+['delete','--raw',f'/api/v1/namespaces/{a.namespace}/pods/{name}','-f','-'],data=options)
        run(kube+['wait','--for=delete','pod/'+name,'-n',a.namespace,'--timeout=45s'],timeout=50)
        own_uid=None
    try:
        # CREATE only: never adopt or overwrite an existing object's name.
        result=json.loads(run(kube+['create','-f','-','-o','json'],data=json.dumps(cm)))
        cm_uid=result['metadata']['uid']
        for i,case in enumerate(a.cases):
            idle()
            pod=get('create','-f',str(a.output/f'{i:02}-{case}.json'))
            own_uid=pod['metadata']['uid']
            folder=a.output/f'{i:02}-{case}';folder.mkdir()
            deadline=time.monotonic()+90
            while True:
                pod=get('get','pod',name,'-n',a.namespace)
                if pod['metadata']['uid']!=own_uid or pod['spec']['nodeName']!=a.node: raise RuntimeError('Pod identity changed')
                statuses=pod['status'].get('containerStatuses',[])
                if statuses and statuses[0].get('state',{}).get('running'):break
                if pod['status'].get('phase')=='Failed' or time.monotonic()>deadline:raise RuntimeError('Probe failed to start')
                time.sleep(1)
            if pod['status'].get('hostIP')!=a.node_ip:raise RuntimeError('Actual Pod hostIP mismatch')
            cid=statuses[0]['containerID'].removeprefix('containerd://')
            identity=observe(cid);identity['pod_uid']=own_uid;identities.append(identity)
            (folder/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
            run(kube+['exec','-n',a.namespace,name,'--','touch','/tmp/start'])
            deadline=time.monotonic()+180
            with (folder/'host-samples.jsonl').open('w') as samples:
                while True:
                    logs=run(kube+['logs','-n',a.namespace,name],timeout=20)
                    (folder/'probe.jsonl').write_text(logs)
                    events=[json.loads(line) for line in logs.splitlines() if line.startswith('{')]
                    if any(e.get('step')=='case-passed' and e.get('case')==case and e.get('pid')==1 for e in events):break
                    pod=get('get','pod',name,'-n',a.namespace)
                    if pod['status'].get('phase') in ('Succeeded','Failed') or time.monotonic()>deadline:raise RuntimeError('Probe did not pass')
                    samples.write(json.dumps(observe(cid))+'\n');samples.flush();time.sleep(1)
            run(kube+['exec','-n',a.namespace,name,'--','touch','/tmp/release'])
            deadline=time.monotonic()+30
            while True:
                pod=get('get','pod',name,'-n',a.namespace)
                if pod['status'].get('phase') in ('Succeeded','Failed'):break
                if time.monotonic()>deadline:raise TimeoutError('Probe completion')
                time.sleep(1)
            (folder/'final-pod.json').write_text(json.dumps(pod,indent=2)+'\n')
            if pod['status']['phase']!='Succeeded':raise RuntimeError('Nonzero probe exit')
            delete_own()
            deadline=time.monotonic()+30
            retired=next(line.split(':',2)[2] for line in identity['cgroup'].splitlines() if line.startswith('0::'))
            while True:
                after=observe(retired=retired)
                if (not after['retired_cgroup_exists'] and not after['compute_processes'].strip()
                        and int(after['gpu'].split(',')[2])<=int(baseline['gpu'].split(',')[2])+16):break
                if time.monotonic()>deadline:raise RuntimeError('Physical capacity not returned')
                time.sleep(1)
            (folder/'after.json').write_text(json.dumps(after,indent=2)+'\n')
        if len({r['pod_uid'] for r in identities})!=len(identities):raise RuntimeError('Pod UID reuse')
        if len({r['container_id'] for r in identities})!=len(identities):raise RuntimeError('Container identity reuse')
        if len({r['cgroup'] for r in identities})!=len(identities):raise RuntimeError('Cgroup path reuse; inspect generation fence')
        summary['status']='hardware-cases-passed'
    except BaseException as e:
        summary.update(status='failed-or-ambiguous',error=str(e))
        raise
    finally:
        try:
            delete_own()
            if cm_uid:
                options=json.dumps({'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':cm_uid}})
                run(kube+['delete','--raw',f'/api/v1/namespaces/{a.namespace}/configmaps/{name}','-f','-'],data=options)
        except BaseException as cleanup_error:
            summary.update(status='cleanup-ambiguous',cleanup_error=str(cleanup_error))
            raise
        finally:
            (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(a.output/'summary.json')


if __name__=='__main__':main()
