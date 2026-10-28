"""CPU-only installed-image exec probe; synthetic fixture confers no authority."""
import json,os,sys,time,subprocess,uuid,signal
from pathlib import Path
from cps_compute.native_gpu_runtime import PLACEMENT_SELECTION,PLACEMENT_SELECTION_PROTOCOL
uid=lambda:str(uuid.uuid4())
expected={'placement_id':'placement-'+'a'*60,'source':'cps','workspace':'fixture','attempt':uid(),'namespace':'fixture','name':'fixture','node':'fixture','node_uid':uid(),'cap_mib':5120,'policy_hash':'sha256:'+'b'*64}
pod_uid=uid();spec='c'*64
ref={'namespace':'fixture','name':'fixture','uid':uid(),'resourceVersion':'1','data_sha256':'sha256:'+'d'*64,'key':'config.json'}
selected={'node':'fixture','node_uid':expected['node_uid'],'boot_id':uid(),'driver_generation':uid(),'gpu_uuid':'GPU-'+uid(),'qualification_ref':ref}
doc={**expected,'protocol':PLACEMENT_SELECTION_PROTOCOL,'pod_uid':pod_uid,'spec_sha256':spec,'gpu_uuid':selected['gpu_uuid'],'selected_placement':selected}
path=Path(PLACEMENT_SELECTION);path.parent.mkdir(parents=True)
assert not Path('/dev/nvidiactl').exists() and not Path('/run/cps-native-gpu/authority').exists()
env=dict(os.environ,CPS_NATIVE_POD_UID=pod_uid,CPS_NATIVE_SPEC_SHA256=spec,NVIDIA_VISIBLE_DEVICES='void',CUDA_VISIBLE_DEVICES='')
argv=[sys.executable,'-m','cps_compute.native_gpu_runtime','wait-for-selected-cap']
for k,v in expected.items():argv.extend(['--'+k.replace('_','-'),str(v)])
argv.extend(['--timeout-seconds','10'])
p=subprocess.Popen(argv,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
def observe():
 stat=Path(f'/proc/{p.pid}/stat').read_text();ticks=int(stat[stat.rfind(')')+2:].split()[19]);cmd=Path(f'/proc/{p.pid}/cmdline').read_bytes().split(b'\0')
 return ticks,cmd
try:
 deadline=time.monotonic()+5
 while True:
  assert p.poll() is None,'gate exited before fixture selection'
  before,cmd=observe()
  if b'wait-for-selected-cap' in cmd:break
  assert time.monotonic()<deadline
  time.sleep(.02)
 # A real projected selection appears after the first process is observable.
 path.write_text(json.dumps(doc,sort_keys=True,separators=(',',':')))
 while True:
  assert p.poll() is None,'gate exited during same-PID exec'
  after,cmd=observe()
  if b'wait-for-cap' in cmd:break
  assert time.monotonic()<deadline,'exec handoff not observed'
  time.sleep(.02)
 assert before==after
 print(json.dumps({'result':'PASS','scope':'CPU-only actual installed os.execv; synthetic fixture, no authority or GPU devices','same_pid':p.pid,'same_pid_start_ticks':before,'selected_wrapper_to_original_gate':True,'hardware_cap_assignment':False}),flush=True)
finally:
 if p.poll() is None:p.terminate()
 p.communicate(timeout=5)
