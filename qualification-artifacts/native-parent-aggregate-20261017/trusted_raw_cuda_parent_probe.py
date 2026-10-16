"""Trusted qualification ONLY: two raw-CUDA children under one pre-capped 5GiB Pod.

Parent does no GPU calls. No limit setters, env changes, files, or runtime changes.
Run only after independent actual PodUID/parent-cgroup/finite cap verification.
This tests ordinary driver allocation accounting, NOT VMM/UVM/cross-Pod isolation.
Root must independently witness global physical free VRAM >6GiB before and
during both OOM held windows; without this witness physical OOM is not excluded.
"""
import argparse
import json
import os
import selectors
import subprocess
import sys
import time
import uuid

MIB=1024*1024
CHUNK=256*MIB
CAP=5120*MIB
WORKER=r'''
import ctypes as C,json,os,select,sys,time,uuid
cfg=json.loads(sys.argv[1]);buffers=[];ctx=C.c_void_p();lib=None
CHUNK=256*1024*1024
class DlInfo(C.Structure):
 _fields_=[('filename',C.c_char_p),('base',C.c_void_p),('symbol',C.c_char_p),('address',C.c_void_p)]
def emit(event,**values):
 print(json.dumps(dict(event=event,lane=cfg['lane'],pid=os.getpid(),time_ns=time.time_ns(),monotonic_ns=time.monotonic_ns(),allocated_bytes=len(buffers)*CHUNK,**values)),flush=True)
def check(code):
 if code:raise RuntimeError('CUDA driver result '+str(code))
def free():
 while buffers:check(lib.cuMemFree_v2(buffers.pop()))
def heartbeat():
 if buffers:
  check(lib.cuMemsetD8_v2(buffers[0],37,1));check(lib.cuCtxSynchronize())
  value=C.c_ubyte();check(lib.cuMemcpyDtoH_v2(C.byref(value),buffers[0],1));assert value.value==37
  emit('heartbeat',readback=value.value)
try:
 assert (os.getuid(),os.getgid())==(1000,100),'Actual notebook UID1000/GID100 required'
 lib=C.CDLL('libcuda.so.1')
 for name,types in {
  'cuInit':[C.c_uint],'cuDriverGetVersion':[C.POINTER(C.c_int)],'cuDeviceGetCount':[C.POINTER(C.c_int)],
  'cuDeviceGetUuid_v2':[C.c_void_p,C.c_int],'cuCtxCreate_v2':[C.POINTER(C.c_void_p),C.c_uint,C.c_int],
  'cuCtxDestroy_v2':[C.c_void_p],'cuMemAlloc_v2':[C.POINTER(C.c_uint64),C.c_size_t],
  'cuMemFree_v2':[C.c_uint64],'cuMemsetD8_v2':[C.c_uint64,C.c_ubyte,C.c_size_t],
  'cuMemcpyDtoH_v2':[C.c_void_p,C.c_uint64,C.c_size_t],'cuCtxSynchronize':[],
  'cuMemGetInfo_v2':[C.POINTER(C.c_size_t),C.POINTER(C.c_size_t)]}.items():
  fn=getattr(lib,name);fn.argtypes=types;fn.restype=C.c_int
 dl=C.CDLL(None);dl.dladdr.argtypes=[C.c_void_p,C.POINTER(DlInfo)];dl.dladdr.restype=C.c_int
 info=DlInfo();assert dl.dladdr(C.cast(lib.cuMemAlloc_v2,C.c_void_p),C.byref(info))!=0
 driver_object=info.filename.decode();assert os.path.basename(driver_object).startswith('libcuda.so'),'Actual raw driver symbol required'
 check(lib.cuInit(0));version=C.c_int();check(lib.cuDriverGetVersion(C.byref(version)));assert version.value>=13040
 count=C.c_int();check(lib.cuDeviceGetCount(C.byref(count)));matches=[]
 for device in range(count.value):
  identity=(C.c_ubyte*16)();check(lib.cuDeviceGetUuid_v2(identity,device))
  if 'GPU-'+str(uuid.UUID(bytes=bytes(identity)))==cfg['gpu_uuid']:matches.append(device)
 assert len(matches)==1,'Exact physical GPU must resolve once'
 check(lib.cuCtxCreate_v2(C.byref(ctx),0,matches[0]))
 free_bytes,total=C.c_size_t(),C.c_size_t();check(lib.cuMemGetInfo_v2(C.byref(free_bytes),C.byref(total)))
 assert total.value==5120*1024*1024,'Process-visible total must match independently verified5GiB parent'
 with open('/proc/self/cgroup') as stream:cgroup=stream.read().strip()
 emit('ready',driver_object=driver_object,driver_api=version.value,gpu_uuid=cfg['gpu_uuid'],cgroup=cgroup,
      uid=os.getuid(),gid=os.getgid(),visible_total_bytes=total.value,visible_free_bytes=free_bytes.value,
      ld_preload=os.environ.get('LD_PRELOAD'))
 deadline=time.monotonic()+110;last=0
 while time.monotonic()<deadline:
  if time.monotonic()-last>=0.25:heartbeat();last=time.monotonic()
  readable,_,_=select.select([sys.stdin],[],[],0.1)
  if not readable:continue
  line=sys.stdin.readline()
  if not line:break
  command=json.loads(line);op=command['op'];seq=command['seq']
  if op=='alloc':
   assert len(buffers)<24,'Bounded per-child allocation count'
   address=C.c_uint64();code=lib.cuMemAlloc_v2(C.byref(address),CHUNK)
   if code==2:emit('oom',seq=seq,cuda_result=2,api='cuMemAlloc_v2');continue
   check(code);buffers.append(address.value)
   check(lib.cuMemsetD8_v2(address.value,37,CHUNK));check(lib.cuCtxSynchronize())
   byte=C.c_ubyte();check(lib.cuMemcpyDtoH_v2(C.byref(byte),address.value,1));assert byte.value==37
   emit('allocated',seq=seq,readback=byte.value)
  elif op=='free':free();emit('freed',seq=seq)
  elif op=='stop':free();emit('stopped',seq=seq);break
  else:raise ValueError('Closed worker command required')
 else:raise TimeoutError('Worker bounded lifetime exceeded')
except BaseException as error:
 emit('error',error_type=type(error).__name__,detail=str(error))
 raise
finally:
 if lib is not None and ctx.value:
  try:free()
  finally:check(lib.cuCtxDestroy_v2(ctx))
'''


def emit(event,**values):
 print(json.dumps(dict(event=event,time_ns=time.time_ns(),monotonic_ns=time.monotonic_ns(),**values)),flush=True)


def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--execute',action='store_true');parser.add_argument('--gpu-uuid');parser.add_argument('--pod-uid')
 parser.add_argument('--hold-seconds',type=int,default=8)
 args=parser.parse_args(argv)
 if not args.execute:
  emit('inert',gpu_calls=False,api_calls=False,scope='same-Pod ordinary CUDA allocation accounting',
       cap_bytes=CAP,chunk_bytes=CHUNK,maximum_logical_live_bytes=CAP+CHUNK,production_qualified=False)
  return 0
 assert args.pod_uid and str(uuid.UUID(args.pod_uid))==args.pod_uid
 assert args.gpu_uuid and args.gpu_uuid=='GPU-'+str(uuid.UUID(args.gpu_uuid.removeprefix('GPU-')))
 assert 2<=args.hold_seconds<=10,'Bounded operator sample windows2..10seconds'
 assert (os.getuid(),os.getgid())==(1000,100)
 start=time.monotonic();selector=selectors.DefaultSelector();children={};events=[];sizes={'a':0,'b':0};seq=0
 def drain(timeout):
  assert time.monotonic()-start<100,'Parent execution deadline exceeded'
  for key,_ in selector.select(timeout):
   line=key.fileobj.readline()
   if not line:raise RuntimeError('Worker exited before orderly cleanup: '+key.data)
   value=json.loads(line);assert value['lane']==key.data
   events.append(value);emit('worker',record=value,pod_uid=args.pod_uid)
   if value['event']=='error':raise RuntimeError('Worker failed: '+value['detail'])
 def wait(predicate,timeout=8):
  until=time.monotonic()+timeout
  while time.monotonic()<until:
   for value in events:
    if predicate(value):return value
   drain(min(0.2,until-time.monotonic()))
  raise TimeoutError('Bounded worker response timeout')
 def command(lane,op):
  nonlocal seq
  seq+=1;own=seq
  child=children[lane];assert child.poll() is None
  child.stdin.write(json.dumps({'op':op,'seq':own})+'\n');child.stdin.flush()
  value=wait(lambda x:x.get('seq')==own and x['lane']==lane)
  if value['event'] in {'allocated','oom','freed','stopped'}:sizes[lane]=value['allocated_bytes']
  assert sum(sizes.values())<=CAP+CHUNK,'Unexpectedly accepted aggregate crossed bounded5.25GiB ceiling'
  if value['event']=='stopped':selector.unregister(child.stdout)
  return value
 def allocate(lane):
  value=command(lane,'alloc');assert value['event'] in {'allocated','oom'};return value
 def checkpoint(label):
  emit('held-checkpoint-start',checkpoint=label,pod_uid=args.pod_uid,allocated_by_lane=dict(sizes),hold_seconds=args.hold_seconds)
  until=time.monotonic()+args.hold_seconds
  while time.monotonic()<until:drain(min(0.2,until-time.monotonic()))
  emit('held-checkpoint-end',checkpoint=label,allocated_by_lane=dict(sizes))
 try:
  for lane in ('a','b'):
   child=subprocess.Popen([sys.executable,'-I','-S','-u','-c',WORKER,json.dumps({'lane':lane,'gpu_uuid':args.gpu_uuid})],
       stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=None,text=True,bufsize=1)
   children[lane]=child;selector.register(child.stdout,selectors.EVENT_READ,lane)
   wait(lambda v:v['lane']==lane and v['event']=='ready',timeout=15)
  ready=[v for v in events if v['event']=='ready'];assert len(ready)==2 and ready[0]['pid']!=ready[1]['pid']
  assert ready[0]['cgroup']==ready[1]['cgroup'],'Two children must share the actual notebook container cgroup'
  assert allocate('b')['event']=='allocated'
  for _ in range(8):assert allocate('a')['event']=='allocated'
  checkpoint('a2GiB-b256MiB')
  while True:
   value=allocate('b')
   if value['event']=='oom':break
   if sum(sizes.values())>=CAP:raise AssertionError('Aggregate reached cap without context overhead/OOM; inspect charge before more allocation')
  first_oom=value;first_b_peak=sizes['b']
  assert 4096*MIB<=sum(sizes.values())<=CAP,'First OOM must occur near the finite5GiB cap (4..5GiB aggregate)'
  checkpoint('aggregate-driver-OOM-both-held');first_oom_hold_end=time.monotonic_ns()
  assert command('b','free')['event']=='freed';assert allocate('b')['event']=='allocated'
  recovery=time.monotonic_ns();checkpoint('b-free-recovery-a-still2GiB')
  assert command('a','free')['event']=='freed';assert allocate('a')['event']=='allocated'
  while True:
   value=allocate('b')
   if value['event']=='oom':break
   if sum(sizes.values())>=CAP:raise AssertionError('Aggregate reached cap without expected nativeOOM')
  assert sizes['b']>first_b_peak,'Releasing sibling budget did not restore aggregate headroom'
  second_oom=value
  assert 4096*MIB<=sum(sizes.values())<=CAP,'Second OOM must occur near the finite5GiB cap (4..5GiB aggregate)'
  checkpoint('a256MiB-b-larger-second-OOM');second_oom_hold_end=time.monotonic_ns()
  ticks=[v for v in events if v['lane']=='a' and v['event']=='heartbeat']
  assert any(v['monotonic_ns']<first_oom['monotonic_ns'] for v in ticks)
  assert any(first_oom['monotonic_ns']<=v['monotonic_ns']<=first_oom_hold_end for v in ticks),'Sibling stalled throughout first OOM held window'
  assert any(second_oom['monotonic_ns']<=v['monotonic_ns']<=second_oom_hold_end for v in ticks),'Sibling stalled throughout second OOM held window'
  assert any(v['monotonic_ns']>recovery for v in ticks),'Sibling failed to progress acrossOOM/free/recovery'
  emit('probe-passed',pod_uid=args.pod_uid,first_b_peak_bytes=first_b_peak,second_b_peak_bytes=sizes['b'],
       typed_driver_oom_results=[first_oom['cuda_result'],second_oom['cuda_result']],sibling_progress=True,
       elapsed_seconds=time.monotonic()-start,scope='same-Pod ordinary CUDA allocation accounting',
       independent_physical_free_gt6GiB_witness_required=True,
       vmm_qualified=False,managed_qualified=False,cross_pod_qualified=False,production_qualified=False)
 finally:
  cleanup_failures=[]
  for lane,child in children.items():
   try:
    if child.poll() is None:
     try:command(lane,'stop')
     except BaseException:child.terminate()
    try:child.wait(timeout=3)
    except subprocess.TimeoutExpired:
     child.kill()
     child.wait(timeout=3)
   except BaseException as error:
    # One stuck or reaped child must never prevent attempting the sibling.
    cleanup_failures.append({'lane':lane,'error_type':type(error).__name__})
    try:
     if child.poll() is None:child.kill()
    except BaseException:pass
  selector.close()
  emit('children-cleaned',returncodes={k:c.returncode for k,c in children.items()},
       cleanup_failures=cleanup_failures,elapsed_seconds=time.monotonic()-start)
 assert not cleanup_failures and all(c.returncode==0 for c in children.values()),'Worker cleanup failed'

 return 0


if __name__=='__main__':raise SystemExit(main())
