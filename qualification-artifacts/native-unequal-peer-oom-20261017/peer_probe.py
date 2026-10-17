#!/usr/bin/env python3
"""Inert-by-default, bounded trusted 5/10GiB group probes; never sets a cap."""
import argparse
import ctypes
from datetime import datetime, timezone
import json
import os
import platform
import re
import threading
import time
import uuid

MIB=1048576
CAP_MIB=5120
STEP_MIB=256

# Verbatim typed-OOM classifier from the reviewed r615-uvm-guard/torch_probe.py.
def oom_proof(error,torch):
    oom=getattr(torch,'OutOfMemoryError',torch.cuda.OutOfMemoryError)
    if isinstance(error,oom):return {'kind':'torch.OutOfMemoryError','cuda_error_code':None}
    accelerator=getattr(torch,'AcceleratorError',None);code=getattr(error,'error_code',None)
    if accelerator is not None and isinstance(error,accelerator) and type(code) is int and code==2:
        return {'kind':'torch.AcceleratorError','cuda_error_code':code}
    return None

def run_steps(torch,mark,minimum_held_mib=None):
    if minimum_held_mib is None:minimum_held_mib=CAP_MIB-1024
    held=[];candidate=ordinary=recovery=None
    result={'production_qualified':False,'over_denied':False,
            'maximum_attempted_tensor_mib':CAP_MIB+STEP_MIB,'held_before_oom_mib':None}
    try:
        mark('before-ordinary64')
        ordinary=torch.empty(64*MIB,dtype=torch.uint8,device='cuda')
        ordinary.fill_(19);torch.cuda.synchronize()
        result['ordinary_byte']=int(ordinary[0].item())
        ordinary=None;torch.cuda.empty_cache();mark('after-ordinary-free64')
        for step in range(1,CAP_MIB//STEP_MIB+2):
            requested=step*STEP_MIB
            mark('before-step-allocation',{'attempted_total_tensor_mib':requested,'held_tensor_mib':len(held)*STEP_MIB})
            try:
                candidate=torch.empty(STEP_MIB*MIB,dtype=torch.uint8,device='cuda')
            except Exception as error:
                proof=oom_proof(error,torch)
                mark('over-allocation-error',{'error_type':type(error).__name__,
                    'cuda_error_code':getattr(error,'error_code',None) if type(getattr(error,'error_code',None)) is int else None,
                    'typed_oom':proof is not None,'attempted_total_tensor_mib':requested})
                if proof is None:raise
                result.update(over_denied=True,over_error=proof,held_before_oom_mib=len(held)*STEP_MIB,
                              oom_attempted_total_tensor_mib=requested)
                break
            if requested>CAP_MIB:
                # Never touch an unexpected allocation beyond the reviewed cap.
                mark('unexpected-over-allocation-success',{'attempted_total_tensor_mib':requested})
                candidate=None
                break
            candidate.fill_(step);torch.cuda.synchronize()
            held.append(candidate);candidate=None
            mark('after-step-touch',{'held_tensor_mib':len(held)*STEP_MIB})
        if result['over_denied'] and (result['held_before_oom_mib'] or 0)>=minimum_held_mib:
            mark('oom-held-start',{'held_tensor_mib':len(held)*STEP_MIB,'hold_seconds':8})
            time.sleep(8)
            mark('oom-held-end',{'held_tensor_mib':len(held)*STEP_MIB,'hold_seconds':8})
        held.clear();candidate=None;torch.cuda.empty_cache();mark('after-over-cleanup')
        mark('before-recovery64')
        recovery=torch.empty(64*MIB,dtype=torch.uint8,device='cuda')
        recovery.fill_(37);torch.cuda.synchronize()
        result['recovery_byte']=int(recovery[0].item())
        recovery=None;torch.cuda.empty_cache();mark('after-recovery-free64')
        result['bounded_step_sequence_passed']=(result['over_denied'] and
            (result['held_before_oom_mib'] or 0)>=minimum_held_mib and
            result['ordinary_byte']==19 and result['recovery_byte']==37)
        return result
    finally:
        held.clear();candidate=ordinary=recovery=None;torch.cuda.empty_cache()

def run_peer(torch,mark,deadline,*,aggregate=False):
    holder=working=None;ticks=0
    try:
        if aggregate:
            holder=torch.empty(2048*MIB,dtype=torch.uint8,device='cuda')
            holder.fill_(11);torch.cuda.synchronize()
            mark('aggregate-holder-ready',{'held_tensor_mib':2048})
        working=torch.empty(64*MIB,dtype=torch.uint8,device='cuda')
        while time.monotonic()<deadline:
            value=(ticks%200)+1
            working.fill_(value);torch.cuda.synchronize()
            actual=int(working[0].item())
            if actual!=value:raise RuntimeError('Peer kernel verification failed')
            ticks+=1
            mark('peer_tick',{'tick':ticks,'kernel_byte':actual,'holder_tensor_mib':2048 if aggregate else 0})
            time.sleep(min(0.5,max(0,deadline-time.monotonic())))
        return {'peer_loop_passed':ticks>=2,'ticks':ticks,'production_qualified':False}
    finally:
        holder=working=None;torch.cuda.empty_cache();mark('peer-freed')

def hardware(torch,expected_uuid):
    if not re.match(r'^2\.11\.',str(torch.__version__)):
        raise RuntimeError('Trusted Torch 2.11 runtime required')
    if torch.cuda.device_count()!=1:
        raise RuntimeError('Exactly one visible physical GPU required')
    library=ctypes.CDLL('libcuda.so.1')
    library.cuInit.argtypes=[ctypes.c_uint]
    if library.cuInit(0)!=0:raise RuntimeError('CUDA driver initialization failed')
    library.cuDeviceGetUuid_v2.argtypes=[ctypes.c_void_p,ctypes.c_int]
    actual=(ctypes.c_ubyte*16)()
    if library.cuDeviceGetUuid_v2(actual,0)!=0:raise RuntimeError('CUDA device UUID unavailable')
    actual_uuid='GPU-'+str(uuid.UUID(bytes=bytes(actual)))
    if actual_uuid!=expected_uuid:raise RuntimeError('Root-reviewed physical GPU mismatch')
    driver_version=ctypes.c_int()
    library.cuDriverGetVersion.argtypes=[ctypes.POINTER(ctypes.c_int)]
    if library.cuDriverGetVersion(ctypes.byref(driver_version))!=0:raise RuntimeError('CUDA driver version unavailable')
    torch.cuda.init()
    properties=torch.cuda.get_device_properties(0)
    return {'torch_version':str(torch.__version__),'torch_cuda_version':torch.version.cuda,
            'cuda_driver_version':driver_version.value,'gpu_uuid':actual_uuid,
            'gpu_name':properties.name,'physical_reported_total_bytes':properties.total_memory,
            'os_platform':platform.platform(),'uid':os.getuid(),'gid':os.getgid()}

def main():
    global CAP_MIB
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('peer','oom'),default='oom')
    parser.add_argument('--duration',type=int,default=120)
    parser.add_argument('--cap-mib',type=int,choices=(5120,10240))
    parser.add_argument('--expected-device-uuid')
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if args.execute and args.cap_mib is None:parser.error('Exact manifest-bound cap required')
    if args.cap_mib is not None:CAP_MIB=args.cap_mib
    if not 5<=args.duration<=180:parser.error('Duration must be between 5 and 180 seconds')
    if args.execute and not (args.expected_device_uuid and re.fullmatch(
            r'GPU-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',args.expected_device_uuid)):
        parser.error('Exact root-reviewed expected physical GPU UUID required')
    plan={'kind':'trusted-group-probe','case':args.case,'cap_mib':CAP_MIB,'step_mib':STEP_MIB,
          'max_duration_seconds':args.duration,'production_qualified':False,'native_cap_verified_by_probe':False}
    if not args.execute:
        print(json.dumps({**plan,'state':'inert','gpu_calls':False},sort_keys=True));return
    started=time.monotonic();run_id=str(uuid.uuid4());torch=None
    def mark(phase,extra=None):
        event={'kind':'group-probe-event','case':args.case,'run_id':run_id,'phase':phase,
               'utc':datetime.now(timezone.utc).isoformat(),'wall_ns':time.time_ns(),
               'monotonic_ns':time.monotonic_ns(),'elapsed_seconds':time.monotonic()-started,'pid':os.getpid()}
        if torch is not None and torch.cuda.is_initialized():
            event.update(torch_allocated_bytes=torch.cuda.memory_allocated(),torch_reserved_bytes=torch.cuda.memory_reserved())
        if extra:event.update(extra)
        print(json.dumps(event,sort_keys=True),flush=True)
    def timed_out():
        # A hung CUDA call must not turn a bounded controlled probe into a long job.
        print(json.dumps({'kind':'group-probe-deadline','run_id':run_id,'case':args.case,
            'utc':datetime.now(timezone.utc).isoformat(),'monotonic_ns':time.monotonic_ns(),
            'production_qualified':False},sort_keys=True),flush=True)
        os._exit(124)
    watchdog=threading.Timer(args.duration,timed_out);watchdog.daemon=True;watchdog.start()
    result={**plan,'run_id':run_id,'state':'inconclusive','gpu_calls':True}
    try:
        if os.getuid()!=1000 or os.getgid()!=100 or os.environ.get('LD_PRELOAD'):
            raise RuntimeError('Ordinary UID1000/GID100 raw CUDA path required')
        import torch as package
        torch=package
        result['hardware']=hardware(torch,args.expected_device_uuid)
        mark('hardware-verified',result['hardware'])
        if args.case in ('peer','aggregate-peer'):
            result.update(run_peer(torch,mark,started+args.duration-2,aggregate=args.case=='aggregate-peer'))
            passed=result['peer_loop_passed']
        else:
            result.update(run_steps(torch,mark))
            passed=result['bounded_step_sequence_passed']
        result['state']='measurement-completed' if passed else 'measurement-failed'
    except Exception as error:
        result.update(error_type=type(error).__name__,
            cuda_error_code=getattr(error,'error_code',None) if type(getattr(error,'error_code',None)) is int else None)
    finally:
        watchdog.cancel()
        mark('receipt',result)
    raise SystemExit(0 if result['state']=='measurement-completed' else 1)

if __name__=='__main__':main()
