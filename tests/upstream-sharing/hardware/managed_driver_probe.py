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
check('init',init(0));dev=C.c_int();check('device',getdev(C.byref(dev),0));ctx=C.c_void_p();check('context',create(C.byref(ctx),0,dev))

managed=api('cuMemAllocManaged',[C.POINTER(C.c_uint64),C.c_size_t,C.c_uint])
prefetch=api('cuMemPrefetchAsync',[C.c_uint64,C.c_size_t,C.c_int,C.c_void_p])
p=C.c_uint64();n=6144*1024**2
try:
 rc=managed(C.byref(p),n,1);report('managed-allocation',rc,mib=6144)
 if rc==2:print('MANAGED_REJECTED_AT_ALLOCATION',flush=True)
 elif rc:raise RuntimeError('managed allocation returned '+str(rc))
 else:
  rc=prefetch(p,n,dev,None);report('managed-prefetch',rc)
  if rc==0:rc=sync();report('managed-prefetch-sync',rc)
  if rc==0:rc=fill(p,1,n);report('managed-fill',rc)
  if rc==0:rc=sync();report('managed-fill-sync',rc)
  if rc==2:print('MANAGED_REJECTED_AT_GPU_USE',flush=True)
  elif rc:raise RuntimeError('managed GPU-use returned '+str(rc))
  else:
   import subprocess,time
   print(subprocess.run(['nvidia-smi','--query-gpu=uuid,memory.total,memory.free,memory.used','--format=csv'],capture_output=True,text=True).stdout,flush=True)
   print('MANAGED_6G_GPU_USE_SUCCEEDED_WITH_5G_LIMIT',flush=True)
   time.sleep(60)
   raise RuntimeError('managed allocation exceeded the fixed profile')
finally:
 if p.value:check('managed-free',free(p))
 check('destroy',destroy(ctx))
