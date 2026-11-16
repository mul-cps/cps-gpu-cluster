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
mode=sys.argv[1];mib=int(sys.argv[2]);role=sys.argv[3]
def emit(**values):print(json.dumps({'role':role,'mode':mode,**values}),flush=True)
def gate(name):
 emit(gate=name,waiting=True);deadline=time.monotonic()+120
 while not Path('/tmp/'+name).exists():
  if time.monotonic()>deadline:raise TimeoutError(name)
  time.sleep(.2)
gate('start')
check('init',init(0));dev=C.c_int();check('device',getdev(C.byref(dev),0));ctx=C.c_void_p();check('context',create(C.byref(ctx),0,dev))
p=C.c_uint64();n=mib*1024**2
try:
 if mode=='managed':
  managed=api('cuMemAllocManaged',[C.POINTER(C.c_uint64),C.c_size_t,C.c_uint]);rc=managed(C.byref(p),n,1)
 else:rc=alloc(C.byref(p),n)
 emit(step='allocation',result=rc,mib=mib)
 if rc:raise RuntimeError('allocation failed with CUDA error '+str(rc))
 if mode=='managed':
  prefetch=api('cuMemPrefetchAsync',[C.c_uint64,C.c_size_t,C.c_int,C.c_void_p]);check('prefetch',prefetch(p,n,dev,None));check('prefetch-sync',sync())
 check('fill',fill(p,1,n));check('sync',sync());emit(step='holding-filled-vram',mib=mib)
 deadline=time.monotonic()+120;last=time.monotonic()
 while not Path('/tmp/release').exists():
  if time.monotonic()>deadline:raise TimeoutError('release')
  rc=sync()
  if rc:
   emit(step='progress-error',result=rc);gate('release');break
  if time.monotonic()-last>2:
   check('live-gpu-fill',fill(p,1,4096));check('live-gpu-sync',sync());emit(step='progress',result=rc,timestamp=time.time());last=time.monotonic()
  time.sleep(.25)
finally:
 if p.value:report('free',free(p))
 report('destroy',destroy(ctx))
emit(step='process-finished')
