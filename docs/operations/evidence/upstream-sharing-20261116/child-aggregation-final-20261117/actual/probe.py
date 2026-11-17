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

import subprocess,errno
p=C.c_uint64()
try:
 if len(sys.argv)>1:
  mib=int(sys.argv[1]);expected=int(sys.argv[2]);rc=alloc(C.byref(p),mib*1024**2);report('child-allocation',rc,mib=mib,expected=expected)
  if rc!=expected:raise RuntimeError('child aggregate result mismatch')
  if rc==0:check('child-fill',fill(p,1,mib*1024**2));check('child-sync',sync())
 else:
  check('parent-allocation-3072MiB',alloc(C.byref(p),3072*1024**2));check('parent-fill',fill(p,1,3072*1024**2));check('parent-sync',sync())
  env=dict(os.environ,NVIDIA_GPU_MEMORY_LIMIT='999999',NVIDIA_GPU_MEMORY_REQUEST='0',CUDA_MPS_PIPE_DIRECTORY='/tmp/cps-no-mps-daemon')
  for mib,expected in [(3072,2),(1024,0)]:
   r=subprocess.run([sys.executable,__file__,str(mib),str(expected)],env=env,capture_output=True,text=True,timeout=30)
   print(r.stdout,flush=True);print(r.stderr,flush=True)
   if r.returncode:raise RuntimeError('child probe failed')
  try:
   os.mkdir('/sys/fs/cgroup/cps-escape-probe')
  except OSError as e:
   report('nested-cgroup-creation-rejected',e.errno)
   if e.errno not in [errno.EROFS,errno.EACCES,errno.EPERM]:raise
  else:
   os.rmdir('/sys/fs/cgroup/cps-escape-probe');raise RuntimeError('tenant could create cgroup')
finally:
 if p.value:check('free',free(p))
 check('destroy',destroy(ctx))
print('CHILD_AGGREGATION_AND_ENV_BYPASS_PROBE_PASSED',flush=True)
