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
try:
 for mib,expected in [(1024,0),(6144,2),(2048,0)]:
  ptr=C.c_uint64();rc=alloc(C.byref(ptr),mib*1024**2);report('allocation',rc,mib=mib,expected=expected)
  try:
   if rc!=expected:raise RuntimeError('unexpected allocation result')
   if rc==0:check('fill',fill(ptr,1,mib*1024**2));check('sync',sync())
  finally:
   if ptr.value:check('free',free(ptr))
finally:check('destroy',destroy(ctx))
print('RAW_DRIVER_LIMIT_AND_RECOVERY_PASSED',flush=True)
