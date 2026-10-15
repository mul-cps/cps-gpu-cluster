#!/usr/bin/env python3
"""Emit an inert operator command plan; execute no subprocess or GPU call."""
import argparse,json,re,uuid
from pathlib import PurePosixPath
def plan(gpu,pipe,server,server_cgroup,clients):
 if not gpu.startswith('GPU-') or str(uuid.UUID(gpu[4:]))!=gpu[4:]:raise ValueError('Canonical physical GPU UUID required')
 if not re.fullmatch('[a-z0-9_]{1,64}',server):raise ValueError('Exact named canary server required')
 if not PurePosixPath(pipe).is_absolute() or '..' in PurePosixPath(pipe).parts:raise ValueError('Reviewed absolute private pipe required')
 if len(clients)!=2 or len({c[0] for c in clients})!=2:raise ValueError('Two distinct actual host client PIDs required')
 observers=[]
 for role,pid,cgroup,cap in [('server',None,server_cgroup,None)]+[(f'client_{i}',*c) for i,c in enumerate(clients)]:
  if pid is not None and (type(pid)!=int or not 0<pid<2**31 or cap not in (512,5120)):raise ValueError('Bounded PID/cap required')
  if not cgroup.startswith('/sys/fs/cgroup/') or '..' in PurePosixPath(cgroup).parts:raise ValueError('Reviewed host cgroup required')
  observers.append({'role':role,'hostPid':pid,'cgroup':cgroup,'capMiB':cap,'argv':['nvidia-smi','memory-limits','--get','--namespace',cgroup,'-i',gpu]})
 env={'CUDA_MPS_PROTOCOL_VERSION':'3','CUDA_MPS_PIPE_DIRECTORY':pipe};commands=[]
 for fields in (['--version'],['server','list',server,'--format=csv,noheader'],['device','list','--server='+server,'--format=csv,noheader'],['client','list','--server='+server,'--format=csv,noheader'],['feature','describe'],['memacct','describe']):commands.append({'env':env,'argv':['nvidia-cuda-mps-control',*fields]})
 for pid,_,_ in clients:
  for field in ('server','device','linux-ns','maws-ns'):commands.append({'env':env,'argv':['nvidia-cuda-mps-control','client','get',str(pid),field]})
 return {'state':'inert','gpu_calls':False,'mpsQualified':False,'setupRequiresRootReviewedCanary':True,'clientEnv':{**env,'CUDA_MPS_PIPE_DIRECTORY':pipe+'/'+server+'/default'},'readOnlyCommands':commands,'chargeObservers':observers,
 'requiredEvidence':['Actual615serverandclientregistration; rejectsilentnonMPSfallback','ExacthostPIDstart/boot/PodUID/cgroupfenceforbothclientsandserver','NativecapreadbackbeforeeachclientCUDAinitandthroughoutordinary/OOM/recovery','ConcurrentpeerGPUticksbracketeachphase; recordclientA/clientB/serverchargedeltas','Recordserverallocationcharge; serverownedclientallocationsmustnotescapeperworkspacecaps','SafeclientterminatewithhostPIDandsuccessbeforenormalPodrestart; norestartsharedserverforisolatedworkspace','PhysicalmemoryandCPUmemcgobservations; manageddenialparametersandfreshVAspacesremainrequired']}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--gpu-uuid',required=True);p.add_argument('--pipe',required=True);p.add_argument('--server',default='cps_canary');p.add_argument('--server-cgroup',required=True);p.add_argument('--client',action='append',required=True,help='ActualHostPID,ActualHostCgroup,CapMiB; exactly twice');a=p.parse_args();clients=[]
 for value in a.client:
  pid,path,cap=value.split(',');clients.append((int(pid),path,int(cap)))
 print(json.dumps(plan(a.gpu_uuid,a.pipe,a.server,a.server_cgroup,clients),indent=2))
if __name__=='__main__':main()
