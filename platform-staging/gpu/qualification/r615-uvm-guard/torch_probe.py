#!/usr/bin/env python3
"""Inert separately staged Torch-only 512MiB/5GiB canary; no cap mutation."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import time
import uuid
import runtime_probe as support

MIB=1048576


def plan(cap,mode='torch'):
    support.require(type(cap) is int and cap in (512,5120) and (mode=='torch' or cap==512),
                    'Only Torch may use the reviewed5GiB cap')
    return {'cap_mib':cap,'ordinary_mib':64,'over_mib':cap,'mode':mode,'production_qualified':False}


def oom_proof(error,torch):
    oom=getattr(torch,'OutOfMemoryError',torch.cuda.OutOfMemoryError)
    if isinstance(error,oom):return {'kind':'torch.OutOfMemoryError','cuda_error_code':None}
    accelerator=getattr(torch,'AcceleratorError',None);code=getattr(error,'error_code',None)
    if accelerator is not None and isinstance(error,accelerator) and type(code) is int and code==2:
        return {'kind':'torch.AcceleratorError','cuda_error_code':code}
    return None


def require_over_margin(snapshot,cap):
    limits=snapshot['limits']
    support.require(limits.get('soft')==cap*MIB and limits.get('hard')==cap*MIB and limits.get('used',0)>0,
                    'Exact native cap and positive current baseline required before over-attempt')


def run_sequence(torch,cap,observe,mark):
    ordinary=recovery=over=None
    result={'production_qualified':False,'over_allocation_mib':cap,'over_denied':False}
    try:
        mark('before-allocate64');ordinary=torch.empty(64*MIB,dtype=torch.uint8,device='cuda');mark('after-allocate64')
        mark('before-touch64');ordinary.fill_(19);torch.cuda.synchronize();mark('after-touch64')
        result['ordinary_byte']=int(ordinary[0].item());ordinary=None;torch.cuda.empty_cache();mark('after-free64')
        require_over_margin(observe(),cap);mark('before-over-allocation')
        try:
            over=torch.empty(cap*MIB,dtype=torch.uint8,device='cuda')
            # Unexpected success is NEVER touched. Release it and fail the measurement.
            mark('unexpected-over-allocation-success');over=None;torch.cuda.empty_cache()
        except Exception as error:
            proof=oom_proof(error,torch)
            mark('over-allocation-error',{'error_type':type(error).__name__,'cuda_error_code':getattr(error,'error_code',None),
                                         'typed_oom':proof is not None})
            if proof is None:raise
            result['over_denied']=True;result['over_error']=proof
        torch.cuda.empty_cache();mark('after-over-cleanup')
        mark('before-recovery64');recovery=torch.empty(64*MIB,dtype=torch.uint8,device='cuda');mark('after-recovery-allocate64')
        recovery.fill_(37);torch.cuda.synchronize();mark('after-recovery-touch64')
        result['recovery_byte']=int(recovery[0].item());recovery=None;torch.cuda.empty_cache();mark('after-recovery-free64')
        result['bounded_torch_sequence_passed']=(result['ordinary_byte']==19 and result['recovery_byte']==37 and result['over_denied'])
        return result
    finally:
        ordinary=recovery=over=None
        torch.cuda.empty_cache()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('torch',),default='torch');parser.add_argument('--cap-mib',type=int,choices=(512,5120),default=512)
    parser.add_argument('--device-uuid');parser.add_argument('--parent-cgroup',type=Path);parser.add_argument('--pod-uid')
    parser.add_argument('--module-parameters',type=Path,default=Path('/sys/module/nvidia_uvm/parameters'))
    parser.add_argument('--support-dir',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--execute',action='store_true');args=parser.parse_args();parameters=plan(args.cap_mib,args.mode)
    if not args.execute:support.emit(dict(parameters,state='inert',gpu_calls=False));return
    support.require(args.parent_cgroup and args.device_uuid and args.pod_uid,'Exact root-reviewed identity required')
    support.require(os.getuid()==1000 and os.getgid()==100 and not os.environ.get('LD_PRELOAD'),'Ordinary raw UID1000/GID100 fixture required')
    support.require(args.parent_cgroup.name.endswith('-pod'+str(uuid.UUID(args.pod_uid)).replace('-','_')+'.slice'),'Exact Pod-parent identity required')
    flags={name:(args.module_parameters/name).read_text().strip() for name in
           ('uvm_deny_managed_mmap','uvm_disable_hmm','uvm_ats_mode','uvm_enable_builtin_tests')}
    support.validate_module_parameters(flags)
    modules=support.load_support(args.support_dir);nvml=modules['pod_cap'].Nvml();torch=None
    receipt=dict(parameters,kind='r615-guard-torch-only',started_ns=time.time_ns(),pid=os.getpid(),uid=os.getuid(),gid=os.getgid(),module_parameters=flags)
    def observe():
        limits=nvml.get(args.device_uuid,str(args.parent_cgroup))
        support.require(limits is not None and limits.get('soft')==args.cap_mib*MIB and limits.get('hard')==args.cap_mib*MIB,'Exact current native parent cap required')
        return {'limits':limits,'parent_memory_current':int((args.parent_cgroup/'memory.current').read_text()),'observed_ns':time.time_ns()}
    def mark(phase,extra=None):
        receipt['last_phase']=phase
        event={'kind':'torch-phase','phase':phase,'parent':observe(),'pid':os.getpid()}
        if torch is not None and torch.cuda.is_initialized():
            event['torch_allocated_bytes']=torch.cuda.memory_allocated();event['torch_reserved_bytes']=torch.cuda.memory_reserved()
        if extra:event.update(extra)
        support.emit(event)
    try:
        import torch as torch_package
        torch=torch_package;receipt.update(torch_version=torch.__version__,torch_cuda_version=torch.version.cuda)
        mark('before-initialize')
        library=ctypes.CDLL('libcuda.so.1');library.cuInit.argtypes=[ctypes.c_uint]
        support.require(library.cuInit(0)==0,'Raw driver initialization failed')
        library.cuDeviceGetUuid_v2.argtypes=[ctypes.c_void_p,ctypes.c_int];actual=(ctypes.c_ubyte*16)()
        support.require(library.cuDeviceGetUuid_v2(actual,0)==0 and 'GPU-'+str(uuid.UUID(bytes=bytes(actual)))==args.device_uuid,'Exact physical GPU mismatch')
        torch.cuda.init();receipt['torch_device_name']=torch.cuda.get_device_name(0)
        library.cuDeviceGetAttribute.argtypes=[ctypes.POINTER(ctypes.c_int),ctypes.c_int,ctypes.c_int]
        values={}
        for attribute in (88,100):
            value=ctypes.c_int();support.require(library.cuDeviceGetAttribute(ctypes.byref(value),attribute,0)==0,'Attribute read failed');values[attribute]=value.value
        support.validate_attributes(values);receipt['attributes']=values;mark('after-initialize')
        receipt.update(run_sequence(torch,args.cap_mib,observe,mark));receipt['status']='measurement-completed'
    except Exception as error:
        receipt.update(status='inconclusive',error_type=type(error).__name__,cuda_error_code=getattr(error,'error_code',None),error=str(error).splitlines()[0])
    finally:
        if torch is not None and torch.cuda.is_initialized():torch.cuda.empty_cache()
        nvml.close();receipt['finished_ns']=time.time_ns();support.emit(receipt)
    raise SystemExit(0 if receipt.get('bounded_torch_sequence_passed') else 1)


if __name__=='__main__':main()
