#!/usr/bin/env python3
"""Two owned CPU processes: absent marker blocks exec; existing marker permits NVML reads."""
import json
from pathlib import Path
import subprocess
import time

OUT=Path(__file__).resolve().parent
SSH=['ssh','-i','/home/bjoern/.ssh/id_ed25519','-o','IdentitiesOnly=yes','-o','BatchMode=yes','ubuntu@10.21.0.43']
BOOT='ebcc5553-3251-43f7-95f2-236e5e3e6b70'
MISSING='/run/nvidia/validations/cps-metrics-gate-missing-20261116'
MARKER='/run/nvidia/validations/driver-ready'
OWNED={}
CODE='''import ctypes as C,json
lib=C.CDLL('libnvidia-ml.so.1')
def call(name,types,*args):
 f=getattr(lib,name);f.argtypes=types;f.restype=C.c_int;rc=f(*args);assert rc==0,(name,rc)
call('nvmlInit_v2',[])
try:
 count=C.c_uint();call('nvmlDeviceGetCount_v2',[C.POINTER(C.c_uint)],C.byref(count));assert count.value==2
 uuids=[]
 for index in range(count.value):
  device=C.c_void_p();call('nvmlDeviceGetHandleByIndex_v2',[C.c_uint,C.POINTER(C.c_void_p)],index,C.byref(device))
  value=C.create_string_buffer(96);call('nvmlDeviceGetUUID',[C.c_void_p,C.c_char_p,C.c_uint],device,value,len(value));uuids.append(value.value.decode())
 assert set(uuids)=={'GPU-16128952-b438-556a-00bb-93039ee24e56','GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6'}
 print(json.dumps({'cpu_started':True,'readonly_nvml_init':True,'gpu_uuids':uuids,'cuda_calls':0}),flush=True)
finally:call('nvmlShutdown',[])
'''

def run(args,body=None):return subprocess.check_output(args,input=body,text=True,timeout=25)
def save(name,value):(OUT/name).write_text(value if isinstance(value,str) else json.dumps(value,indent=2)+'\n')
def get(name):return json.loads(run(['kubectl','get','pod','-n','gpu-operator',name,'-o','json']))
def create(name,path):
 body={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'gpu-operator','labels':{'cps.unileoben.ac.at/metrics-gate-probe':'20261116'}},
 'spec':{'nodeName':'k3s-wk-gpu2','runtimeClassName':'nvidia','restartPolicy':'Never','activeDeadlineSeconds':90,'terminationGracePeriodSeconds':10,'automountServiceAccountToken':False,
 'imagePullSecrets':[{'name':'cps-native-image-pull'}],
 'securityContext':{'runAsNonRoot':True,'runAsUser':1000,'runAsGroup':1000,'seccompProfile':{'type':'RuntimeDefault'}},
 'volumes':[{'name':'gpu-operator-driver-ready','hostPath':{'path':path,'type':'File'}}],
 'containers':[{'name':'main','image':'ghcr.io/mul-cps/cps-ubuntu-release-upgrade@sha256:5030556ecf8cd38fc9acc4676316bd0a3217d1ab10930b75b9dba7106e8f4004',
 'command':['python3','-u','-c',CODE],'env':[{'name':'NVIDIA_VISIBLE_DEVICES','value':'all'},{'name':'NVIDIA_DRIVER_CAPABILITIES','value':'utility'}],
 'resources':{'requests':{'cpu':'100m','memory':'64Mi'},'limits':{'cpu':'1','memory':'256Mi'}},
 'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']}},
 'volumeMounts':[{'name':'gpu-operator-driver-ready','mountPath':'/run/nvidia/validations/driver-ready','readOnly':True}]}]}}
 save(name+'-input.json',body)
 created=json.loads(run(['kubectl','create','-f','-','-o','json'],json.dumps(body)));OWNED[name]=created['metadata']['uid'];save(name+'-created.json',created)

def main():
 assert not (OUT/'gate-fixture-summary.json').exists(),'Do not overwrite completed fixture'
 boot=run(SSH+['cat /proc/sys/kernel/random/boot_id']).strip();assert boot==BOOT
 node=json.loads(run(['kubectl','get','node','k3s-wk-gpu2','-o','json']))
 assert node['spec']['unschedulable'] and node['metadata']['labels']['accelerator']=='r615-canary-maintenance'
 assert 'cps.unileoben.ac.at/upstream-gpu-sharing' not in node['metadata']['labels']
 marker_before=run(SSH+['sudo stat -c "%i %s %Y %u %a" '+MARKER]);save('marker-stat-before.txt',marker_before)
 run(SSH+['sudo test ! -e '+MISSING])
 summary={'status':'RUNNING','boot_id':boot,'cuda_calls':0}
 try:
  negative='cps-metrics-gate-absent';positive='cps-metrics-gate-present'
  create(negative,MISSING);deadline=time.monotonic()+35;blocked=False
  while time.monotonic()<deadline:
   pod=get(negative);save('absent-latest.json',pod)
   assert not any(c.get('containerID') or c.get('state',{}).get('running') or c.get('state',{}).get('terminated') for c in pod['status'].get('containerStatuses',[]))
   events=json.loads(run(['kubectl','get','events','-n','gpu-operator','--field-selector','involvedObject.uid='+OWNED[negative],'-o','json']));save('absent-events.json',events)
   if any(MISSING in e.get('message','') and 'is not a file' in e.get('message','') for e in events['items']):blocked=True;break
   time.sleep(1)
  assert blocked,'No missing-file kubelet admission witness'
  create(positive,MARKER);deadline=time.monotonic()+50
  while time.monotonic()<deadline:
   pod=get(positive);save('present-latest.json',pod)
   if pod['status']['phase']=='Succeeded':break
   assert pod['status']['phase']!='Failed',pod['status']
   time.sleep(.5)
  assert pod['status']['phase']=='Succeeded'
  logs=run(['kubectl','logs','-n','gpu-operator',positive]);save('present.log',logs)
  evidence=json.loads(logs);assert evidence['cpu_started'] and evidence['readonly_nvml_init'] and evidence['cuda_calls']==0
  negative_final=get(negative);save('absent-final.json',negative_final)
  assert not any(c.get('containerID') for c in negative_final['status'].get('containerStatuses',[]))
  summary.update(status='PASS',missing_marker_blocks_before_container_exec=True,existing_marker_allows_cpu_and_readonly_nvml=True)
 finally:
  for name,uid in list(OWNED.items()):
   options={'apiVersion':'v1','kind':'DeleteOptions','preconditions':{'uid':uid}}
   save(name+'-delete.json',run(['kubectl','delete','--raw','/api/v1/namespaces/gpu-operator/pods/'+name,'-f','-'],json.dumps(options)))
  marker_after=run(SSH+['sudo stat -c "%i %s %Y %u %a" '+MARKER]);save('marker-stat-after.txt',marker_after);assert marker_after==marker_before
  run(SSH+['sudo test ! -e '+MISSING]);summary['production_marker_unchanged']=True
  save('gate-fixture-summary.json',summary)

if __name__=='__main__':main()
