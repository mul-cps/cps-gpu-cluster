#!/usr/bin/env python3
"""Trusted, bounded HAMi or combined HAMi/MPS runtime probe on a quiescent GPU node.

Never invoked by public PR CI. Does not change MPS server settings, user pods,
policy or grants. A negative result is qualification evidence, not approval.
"""
import argparse
import datetime
import json
import re
from pathlib import Path
import subprocess
import time
import uuid

NAMESPACE = 'cps-gpu-qualification'
CUDA = r'''
import ctypes,json,os,time,subprocess,sys

def probe():
 cuda=ctypes.CDLL('libcuda.so.1')
 cuda.cuInit.argtypes=[ctypes.c_uint]
 cuda.cuDeviceGet.argtypes=[ctypes.POINTER(ctypes.c_int),ctypes.c_int]
 cuda.cuCtxCreate_v2.argtypes=[ctypes.POINTER(ctypes.c_void_p),ctypes.c_uint,ctypes.c_int]
 cuda.cuMemAlloc_v2.argtypes=[ctypes.POINTER(ctypes.c_uint64),ctypes.c_size_t]
 cuda.cuMemFree_v2.argtypes=[ctypes.c_uint64]
 cuda.cuMemGetInfo_v2.argtypes=[ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
 cuda.cuMemsetD8_v2.argtypes=[ctypes.c_uint64,ctypes.c_ubyte,ctypes.c_size_t]
 assert cuda.cuInit(0)==0
 device=ctypes.c_int();assert cuda.cuDeviceGet(ctypes.byref(device),0)==0
 context=ctypes.c_void_p();assert cuda.cuCtxCreate_v2(ctypes.byref(context),0,device)==0
 uid=(ctypes.c_byte*16)();assert cuda.cuDeviceGetUuid(ctypes.byref(uid),device)==0
 free,total=ctypes.c_size_t(),ctypes.c_size_t();assert cuda.cuMemGetInfo_v2(ctypes.byref(free),ctypes.byref(total))==0
 ptr=ctypes.c_uint64();size=int(os.getenv('PROBE_MIB','256'))*1024**2
 result=cuda.cuMemAlloc_v2(ctypes.byref(ptr),size)
 if result==0:
  assert cuda.cuMemsetD8_v2(ptr,17,min(size,1024**2))==0
  if os.environ['PROBE_MODE']=='peer':
   print(json.dumps({'event':'ready','gpu':bytes(uid).hex(),'total':total.value}),flush=True)
   for i in range(60):
    assert cuda.cuMemsetD8_v2(ptr,i,1024**2)==0
    print(json.dumps({'event':'alive','tick':i}),flush=True);time.sleep(1)
  assert cuda.cuMemFree_v2(ptr)==0
 print(json.dumps({'event':'result','gpu':bytes(uid).hex(),'total':total.value,'free_before':free.value,'allocation_mib':size//1024**2,'cuda_result':result}),flush=True)

if os.environ['PROBE_MODE']=='attacker':
 cases=[('ordinary',{}),('unset-preload',{'LD_PRELOAD':''}),('larger-environment-limit',{'CUDA_DEVICE_MEMORY_LIMIT':'40g'}),('disable-control',{'CUDA_DISABLE_CONTROL':'true'}),('larger-limit-fresh-cache',{'CUDA_DEVICE_MEMORY_LIMIT':'40g'})]
 if os.getenv('PROBE_MPS')=='1':
  cases.append(('disable-mps-fresh-cache',{'CUDA_DEVICE_MEMORY_LIMIT':'40g','CUDA_MPS_PIPE_DIRECTORY':'/tmp/no-such-mps-path'}))
 for name,changes in cases:
  if name in ('larger-limit-fresh-cache','disable-mps-fresh-cache'):
   import stat
   cache='/tmp/cudevshr.cache'
   if os.path.exists(cache):
    assert stat.S_ISREG(os.lstat(cache).st_mode), 'Refuse nonregular local cache'
    os.unlink(cache)
  env=dict(os.environ,PROBE_MODE='child',PROBE_MIB='6144');env.update(changes)
  p=subprocess.run([sys.executable,'-u','-c',os.environ['PROBE_SOURCE']],env=env,capture_output=True,text=True,timeout=20)
  events=[json.loads(l) for l in p.stdout.splitlines() if l.startswith('{')]
  print(json.dumps({'event':'attempt','case':name,'returncode':p.returncode,'results':events,'stderr':p.stderr[-1200:]}),flush=True)
else:probe()
'''


def kubectl(*args, data=None, check=True):
    return subprocess.run(['kubectl', *args], input=data, text=True, capture_output=True, check=check)


def events(name):
    result = kubectl('logs', '-n', NAMESPACE, name, check=False)
    return [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]


def run(node, output, *, mps=False):
    if output.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError('Store qualification evidence outside Git')
    namespace = json.loads(kubectl('get','namespace',NAMESPACE,'-o','json').stdout)
    if namespace['metadata'].get('labels',{}).get('compute.cps.unileoben.ac.at/isolation') != 'required':
        raise ValueError('Required scoped isolation namespace is absent')
    pods = json.loads(kubectl('get','pods','-A','-o','json').stdout)['items']
    for p in pods:
        if p['spec'].get('nodeName') != node or p['status'].get('phase') in ('Succeeded','Failed'):
            continue
        annotations = p['metadata'].get('annotations',{})
        gpu = any('nvidia.com/gpu' in {**c.get('resources',{}).get('requests',{}),**c.get('resources',{}).get('limits',{})} for c in p['spec'].get('containers',[]))
        if gpu or {'gpu-memory','gpu-fraction'} & set(annotations):
            raise ValueError('Node has an active GPU workload/reservation; refuse probe')
    daemon = None
    if mps:
        daemons = [p for p in pods if p['spec'].get('nodeName') == node
                   and p['metadata'].get('namespace') == 'gpu-operator'
                   and p['metadata'].get('labels',{}).get('app') == 'mps-control-daemon-standalone'
                   and any(c.get('type') == 'Ready' and c.get('status') == 'True'
                           for c in p['status'].get('conditions',[]))
                   and any(c['name'] == 'mps-control-daemon-ctr' for c in p['spec'].get('containers',[]))]
        if len(daemons) != 1:
            raise ValueError('Exactly one Ready MPS daemon on the target node required')
        daemon = daemons[0]['metadata']['name']
    base = json.loads(kubectl('get','pod','hami-20g-peer','-n',NAMESPACE,'-o','json').stdout)
    base = json.loads(base['metadata']['annotations']['kubectl.kubernetes.io/last-applied-configuration'])
    if not re.fullmatch(r'[^@ ]+@sha256:[a-f0-9]{64}',base['spec']['containers'][0]['image']):
        raise ValueError('Trusted qualification fixture must use an immutable image digest')
    names = []
    report = {'createdAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'node':node,'namespace':NAMESPACE,'nominalGiB':5,'attemptMiB':6144,'image':base['spec']['containers'][0]['image'],'status':'incomplete','limitations':['Bounded same-node HAMi probe; no MPS compute, burst, reclaim or release qualification.']}
    report['scope'] = 'combined HAMi/MPS' if mps else 'HAMi only'
    if mps:
        report['mpsDaemon'] = daemon
        report['limitations'] = ['Bounded combined probe; no compute-share, profile matrix, burst, reclaim or release qualification.']
    try:
        for mode in ('peer','attacker'):
            p = json.loads(json.dumps(base));name='runtime-'+mode+'-'+uuid.uuid4().hex[:10]
            p['metadata']['name']=name
            p['metadata']['annotations']={'gpu-fraction-container-name':'main','gpu-memory':'5120'}
            p['spec']['nodeSelector']={'kubernetes.io/hostname':node}
            p['spec']['activeDeadlineSeconds']=180
            c=p['spec']['containers'][0]
            c['command']=['python','-u','-c',CUDA]
            c['env']=[{'name':'PROBE_MODE','value':mode},{'name':'PROBE_SOURCE','value':CUDA},{'name':'NVIDIA_DRIVER_CAPABILITIES','value':'compute,utility'}]
            if mps:
                c['env'].extend([{'name':'CUDA_MPS_PIPE_DIRECTORY','value':'/mps/pipe'},
                                 {'name':'PROBE_MPS','value':'1'}])
                p['spec']['volumes'] = [
                    {'name':'qualification-mps-pipe','hostPath':{'path':'/run/nvidia/mps/nvidia.com/gpu/pipe','type':'Directory'}},
                    {'name':'qualification-mps-shm','hostPath':{'path':'/run/nvidia/mps/shm','type':'Directory'}}]
                c['volumeMounts'] = [{'name':'qualification-mps-pipe','mountPath':'/mps/pipe'},
                                     {'name':'qualification-mps-shm','mountPath':'/dev/shm'}]
            kubectl('create','-f','-',data=json.dumps(p));names.append(name)
            deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                log=events(name)
                if mode=='peer' and any(e.get('event')=='ready' for e in log):
                    if mps:
                        control = ['exec','-n','gpu-operator',daemon,'-c','mps-control-daemon-ctr','--','sh','-c']
                        servers = kubectl(*control, "printf 'get_server_list\n' | CUDA_MPS_PIPE_DIRECTORY=/mps/nvidia.com/gpu/pipe nvidia-cuda-mps-control").stdout.split()
                        if any(not server.isdecimal() for server in servers):
                            raise ValueError('Invalid MPS server response')
                        clients = {}
                        for server in servers:
                            values = kubectl(*control, "printf 'get_client_list %s\n' \"$1\" | CUDA_MPS_PIPE_DIRECTORY=/mps/nvidia.com/gpu/pipe nvidia-cuda-mps-control", 'sh', server).stdout.split()
                            if any(not client.isdecimal() for client in values):
                                raise ValueError('Invalid MPS client response')
                            clients[server] = values
                        report['mpsClientsObserved'] = clients
                        if not any(clients.values()):
                            raise ValueError('No MPS client observed while the peer is ready')
                    break
                if mode=='attacker' and len([e for e in log if e.get('event')=='attempt'])==(6 if mps else 5):break
                state=json.loads(kubectl('get','pod',name,'-n',NAMESPACE,'-o','json').stdout)
                if state['status'].get('phase') in ('Failed','Succeeded'):raise RuntimeError('Probe terminated before required events')
                time.sleep(2)
            else:raise TimeoutError('Probe event barrier timed out')
        deadline=time.monotonic()+100
        while time.monotonic()<deadline:
            if any(e.get('event')=='result' for e in events(names[0])):break
            time.sleep(2)
        else:raise TimeoutError('Peer did not finish')
        peer,attack=events(names[0]),events(names[1]);report.update(peer=peer,attempts=attack)
        identity=next(e['gpu'] for e in peer if e.get('event')=='ready')
        attempts=[e for e in attack if e.get('event')=='attempt']
        report['sameGpu']=all(e['results'] and all(r.get('gpu')==identity for r in e['results']) for e in attempts)
        report['ordinaryOomDenied']=attempts[0]['returncode']==0 and attempts[0]['results'][0]['cuda_result']==2
        report['runtimeOverridesDenied']=all(e['returncode']==0 and e['results'] and all(r['cuda_result']==2 for r in e['results']) for e in attempts)
        report['peerContinued']=len([e for e in peer if e.get('event')=='alive'])==60 and peer[-1].get('cuda_result')==0
        report['status']='passed' if all(report[k] for k in ('sameGpu','ordinaryOomDenied','runtimeOverridesDenied','peerContinued')) else 'failed'
    finally:
        for name in names:kubectl('delete','pod',name,'-n',NAMESPACE,'--wait=false',check=False)
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node',required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mps',action='store_true',help='Mount existing MPS sockets and verify client participation; never change daemon settings')
    args=parser.parse_args();result=run(args.node,args.output,mps=args.mps)
    print(json.dumps({k:v for k,v in result.items() if k not in ('peer','attempts')},indent=2))
    raise SystemExit(0 if result['status']=='passed' else 1)
