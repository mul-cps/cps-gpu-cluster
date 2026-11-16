import ctypes as C, json, os, sys
lib=C.CDLL('libcuda.so.1')
def api(name,args):
 f=getattr(lib,name);f.argtypes=args;f.restype=C.c_int;return f
init=api('cuInit',[C.c_uint]);getdev=api('cuDeviceGet',[C.POINTER(C.c_int),C.c_int]);create=api('cuCtxCreate_v2',[C.POINTER(C.c_void_p),C.c_uint,C.c_int]);destroy=api('cuCtxDestroy_v2',[C.c_void_p]);alloc=api('cuMemAlloc_v2',[C.POINTER(C.c_uint64),C.c_size_t]);free=api('cuMemFree_v2',[C.c_uint64]);fill=api('cuMemsetD8_v2',[C.c_uint64,C.c_ubyte,C.c_size_t]);sync=api('cuCtxSynchronize',[])
def report(step,rc,**extra): print(json.dumps({'step':step,'result':rc,**extra}),flush=True)
def check(step,rc):
 report(step,rc)
 if rc:raise RuntimeError(step+' CUDA error '+str(rc))
print(json.dumps({'env':{k:os.environ.get(k) for k in ['NVIDIA_VISIBLE_DEVICES','NVIDIA_GPU_MEMORY_REQUEST','NVIDIA_GPU_MEMORY_LIMIT','CUDA_MPS_PIPE_DIRECTORY']}}),flush=True)

import time
from pathlib import Path
def gate(name):
 print(json.dumps({'gate':name,'waiting':True}),flush=True)
 deadline=time.monotonic()+90
 while not Path('/tmp/'+name).exists():
  if time.monotonic()>deadline:raise TimeoutError(name)
  time.sleep(0.2)
gate('start')
check('init',init(0));dev=C.c_int();check('device',getdev(C.byref(dev),0));ctx=C.c_void_p();check('context',create(C.byref(ctx),0,dev))
managed=api('cuMemAllocManaged',[C.POINTER(C.c_uint64),C.c_size_t,C.c_uint])
prefetch=api('cuMemPrefetchAsync',[C.c_uint64,C.c_size_t,C.c_int,C.c_void_p])
p=C.c_uint64()
try:
 for mib,expected in [(2048,0),(6144,2)]:
  ptr=C.c_uint64();rc=alloc(C.byref(ptr),mib*1024**2);report('ordinary-allocation',rc,mib=mib,expected=expected)
  try:
   if rc!=expected:raise RuntimeError('ordinary allocation does not match confirmed hard limit')
   if rc==0:check('ordinary-fill',fill(ptr,1,mib*1024**2));check('ordinary-sync',sync())
  finally:
   if ptr.value:check('ordinary-free',free(ptr))
 n=6144*1024**2;rc=managed(C.byref(p),n,1);report('managed-allocation',rc,mib=6144)
 if rc==0:
  rc=prefetch(p,n,dev,None);report('managed-prefetch',rc)
  if rc==0:rc=sync();report('managed-prefetch-sync',rc)
  if rc==0:rc=fill(p,1,n);report('managed-fill',rc)
  if rc==0:rc=sync();report('managed-fill-sync',rc)
  if rc==0:print('MANAGED_GPU_USE_COMPLETED_ABOVE_HARD_LIMIT',flush=True)
 else:print('MANAGED_ALLOCATION_REJECTED',flush=True)
 gate('release')
finally:
 if p.value:check('managed-free',free(p))
 check('destroy',destroy(ctx))
