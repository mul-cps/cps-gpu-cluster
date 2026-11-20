#!/usr/bin/env python3
"""Inert R615 global-guard canary. Fixed 512MiB parent, allocations <=256MiB."""
import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

MIB=1048576
SUPPORT={'cuda_probe.py':'e0a3e28c00336d9dd5bc2c6267eb2b0792ef467940fd96c86aa11cd1c180e2eb',
         'pod_cap.py':'5c84ab668dd276b0216199a964f42886712af9225f9fc702740bfa9bb361a39f'}


def require(ok,message):
    if not ok:raise ValueError(message)


def emit(value):print(json.dumps(value,sort_keys=True),flush=True)


def validate_module_parameters(values):
    require(values.get('uvm_deny_managed_mmap') in ('Y','1'),'Guard must be actually enabled')
    require(values.get('uvm_disable_hmm') in ('Y','1'),'HMM must be actually disabled')
    require(values.get('uvm_ats_mode')=='0','ATS must be actually disabled')
    require(values.get('uvm_enable_builtin_tests')=='0','UVM built-in tests must be disabled')


def validate_attributes(values):
    require(values.get(88)==0 and values.get(100)==0,'Actual pageable/host-page-table access must both be off')


def run_sequence(driver,observe):
    before=observe();limits=before['limits']
    require(limits['hard']==512*MIB and 0<limits['used']<=512*MIB-64*MIB and limits['used']+256*MIB>limits['hard'],
            'Actual context baseline must allow64MiB and put256MiB above the cap')
    result={'production_qualified':False,'managed_allocation_denied':False,'before':before}
    try:
        result['ordinary_64']=driver.allocate(64);result['free_64']=driver.free()
        result['ordinary_256']=driver.allocate(256);result['free_256']=driver.free()
        result['ordinary_recovery_64']=driver.allocate(64);result['free_recovery']=driver.free()
        result['managed_64']=driver.allocate(64,managed=True)
        result['managed_allocation_denied']=result['managed_64']['cuda_result']!=0
        result['raw_sequence_passed']=(result['ordinary_64']['cuda_result']==0 and
            result['ordinary_64']['touch_result']==0 and result['ordinary_256']['cuda_result']==2 and
            result['ordinary_recovery_64']['cuda_result']==0 and result['ordinary_recovery_64']['touch_result']==0 and
            result['managed_allocation_denied'] and all(result[key]['cuda_result']==0
              for key in ('free_64','free_256','free_recovery')))
        result['after']=observe();result['heartbeat_after']=driver.tick()
        result['raw_sequence_passed']=result['raw_sequence_passed'] and result['heartbeat_after']['cuda_result']==0
        return result
    finally:require(driver.free()['cuda_result']==0,'Exact phase allocation cleanup failed')


def load_support(directory):
    for filename,expected in SUPPORT.items():
        require(hashlib.sha256((directory/filename).read_bytes()).hexdigest()==expected,'Pinned runtime support hash mismatch')
    modules={}
    for filename in SUPPORT:
        name=filename[:-3];spec=importlib.util.spec_from_file_location('_guard_'+name,directory/filename)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);modules[name]=module
    return modules


def attributes(driver):
    operation=driver.lib.cuDeviceGetAttribute
    operation.argtypes=[ctypes.POINTER(ctypes.c_int),ctypes.c_int,ctypes.c_int];operation.restype=ctypes.c_int
    values={}
    for attribute in (83,88,89,100):
        value=ctypes.c_int();driver.check(operation(ctypes.byref(value),attribute,driver.device));values[attribute]=value.value
    validate_attributes(values);return values


def measure(args):
    parameters={name:(args.module_parameters/name).read_text().strip() for name in
                ('uvm_deny_managed_mmap','uvm_disable_hmm','uvm_ats_mode','uvm_enable_builtin_tests')}
    validate_module_parameters(parameters)
    require(os.getuid()==1000 and os.getgid()==100,'Ordinary UID1000/GID100 fixture required')
    require(not os.environ.get('LD_PRELOAD'),'Raw driver measurement requires no preload')
    require(args.parent_cgroup.name.endswith('-pod'+str(uuid.UUID(args.pod_uid)).replace('-','_')+'.slice'),
            'Exact Pod parent cgroup name required')
    support=load_support(args.support_dir);driver=None;nvml=support['pod_cap'].Nvml()
    def observe():
        limits=nvml.get(args.device_uuid,str(args.parent_cgroup))
        require(limits is not None and limits['soft']==512*MIB and limits['hard']==512*MIB,'Actual parent cap must remain512MiB')
        return {'limits':limits,'parent_memory_current':int((args.parent_cgroup/'memory.current').read_text()),'observed_ns':time.time_ns()}
    receipt={'kind':'r615-global-guard-canary','mode':args.mode,'launch':args.launch,'pid':os.getpid(),
             'ppid':os.getppid(),'uid':os.getuid(),'gid':os.getgid(),'module_parameters':parameters,
             'started_ns':time.time_ns(),'production_qualified':False,'before_context':observe()}
    try:
        if args.mode=='torch':
            try:import torch
            except ImportError:
                receipt.update(status='torch-package-unavailable',torch_qualified=False);return receipt,2
            receipt['torch_version']=torch.__version__;receipt['torch_cuda_version']=torch.version.cuda
            library=ctypes.CDLL('libcuda.so.1');library.cuInit.argtypes=[ctypes.c_uint]
            require(library.cuInit(0)==0,'Torch raw driver initialization failed')
            library.cuDeviceGetUuid_v2.argtypes=[ctypes.c_void_p,ctypes.c_int]
            device_uuid=(ctypes.c_ubyte*16)()
            require(library.cuDeviceGetUuid_v2(device_uuid,0)==0 and
                    'GPU-'+str(uuid.UUID(bytes=bytes(device_uuid)))==args.device_uuid,'Torch exact physical GPU mismatch')
            torch.cuda.init();receipt['torch_device_name']=torch.cuda.get_device_name(0)
            # CUDA attributes are verified using the pinned raw ABI before Torch allocation.
            library=ctypes.CDLL('libcuda.so.1');library.cuDeviceGetAttribute.argtypes=[ctypes.POINTER(ctypes.c_int),ctypes.c_int,ctypes.c_int]
            values={}
            for attribute in (88,100):
                value=ctypes.c_int();require(library.cuDeviceGetAttribute(ctypes.byref(value),attribute,0)==0,'Torch CUDA attribute read failed');values[attribute]=value.value
            validate_attributes(values);receipt['attributes']=values
            ordinary=torch.empty(64*MIB,dtype=torch.uint8,device='cuda');ordinary.fill_(19);torch.cuda.synchronize()
            del ordinary;torch.cuda.empty_cache();denied=False
            try:
                over=torch.empty(256*MIB,dtype=torch.uint8,device='cuda');over.fill_(19);torch.cuda.synchronize();del over
            except torch.cuda.OutOfMemoryError:denied=True
            torch.cuda.empty_cache();recovery=torch.empty(64*MIB,dtype=torch.uint8,device='cuda');recovery.fill_(37);torch.cuda.synchronize()
            receipt['torch_256_denied']=denied;receipt['torch_recovery_byte']=int(recovery[0].item());del recovery;torch.cuda.empty_cache()
            receipt['torch_qualified']=False;receipt['bounded_torch_sequence_passed']=denied and receipt['torch_recovery_byte']==37
            receipt['status']='measurement-completed';return receipt,0 if receipt['bounded_torch_sequence_passed'] else 1
        driver=support['cuda_probe'].Cuda(args.device_uuid);receipt['attributes']=attributes(driver)
        receipt['driver_object']=driver.driver_object;receipt['driver_api_version']=driver.api_version
        receipt['after_context']=observe()
        if args.mode=='heartbeat':
            deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                tick=driver.tick();emit({'kind':'independent-guard-peer-heartbeat','pid':os.getpid(),'tick':tick,'parent':observe()})
                require(tick['cuda_result']==0,'Independent peer CUDA heartbeat failed');time.sleep(0.2)
            receipt['status']='peer-completed';return receipt,0
        if args.mode=='managed-only':
            receipt['managed_64']=driver.allocate(64,managed=True)
            receipt['managed_allocation_denied']=receipt['managed_64']['cuda_result']!=0
            receipt['heartbeat_after']=driver.tick();receipt['status']='measurement-completed'
            return receipt,0 if receipt['managed_allocation_denied'] and receipt['heartbeat_after']['cuda_result']==0 else 1
        receipt.update(run_sequence(driver,observe));receipt['status']='measurement-completed'
        return receipt,0 if receipt['raw_sequence_passed'] else 1
    except Exception as error:
        receipt.update(status='inconclusive',error_type=type(error).__name__,error=str(error));return receipt,1
    finally:
        if driver is not None:driver.close()
        nvml.close();receipt['finished_ns']=time.time_ns()


def run_bounded(command,timeout=60):
    process=subprocess.Popen(command,start_new_session=True)
    try:return process.wait(timeout=timeout)
    except BaseException:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait(timeout=5)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('raw','managed-only','heartbeat','torch','all'),default='raw')
    parser.add_argument('--launch',choices=('direct','fork-before-cuda'),default='direct')
    parser.add_argument('--device-uuid');parser.add_argument('--parent-cgroup',type=Path);parser.add_argument('--pod-uid')
    parser.add_argument('--module-parameters',type=Path,default=Path('/sys/module/nvidia_uvm/parameters'))
    here=Path(__file__).resolve().parent
    repo_support=here.parents[2]/'scheduler/qualification/r615-pod-cap' if len(here.parents)>=3 else here
    default_support=here if (here/'cuda_probe.py').is_file() else repo_support
    parser.add_argument('--support-dir',type=Path,default=default_support)
    parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if not args.execute:
        emit({'state':'inert','gpu_calls':False,'cap_mib':512,'ordinary_mib':[64,256,64],'managed_mib':64,
              'production_qualified':False,'mode':args.mode});return
    require(args.device_uuid and args.device_uuid.startswith('GPU-') and args.parent_cgroup and args.pod_uid,
            'Exact root-reviewed GPU/Pod parent identity required')
    if args.mode=='all':
        require(args.launch=='direct','Full matrix uses fresh subprocesses')
        reports=[]
        for mode,launch in (('raw','direct'),('managed-only','direct'),('managed-only','fork-before-cuda'),('torch','direct')):
            command=[sys.executable,str(Path(__file__).resolve()),'--execute','--mode',mode,'--launch',launch,
                     '--device-uuid',args.device_uuid,'--parent-cgroup',str(args.parent_cgroup),'--pod-uid',args.pod_uid,
                     '--module-parameters',str(args.module_parameters),'--support-dir',str(args.support_dir)]
            exit_code=run_bounded(command)
            reports.append({'mode':mode,'launch':launch,'exit_code':exit_code})
        emit({'kind':'fresh-process-matrix','results':reports,'production_qualified':False})
        raise SystemExit(0 if all(item['exit_code']==0 for item in reports) else 1)
    if args.launch=='fork-before-cuda':
        # This launcher has never initialized CUDA; inherited/shared CUDA VAspaces are unqualified.
        pid=os.fork()
        if pid==0:
            receipt,code=measure(args);receipt['fork_before_cuda']=True;emit(receipt);sys.stdout.flush();os._exit(code)
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            waited,status=os.waitpid(pid,os.WNOHANG)
            if waited:raise SystemExit(os.waitstatus_to_exitcode(status))
            time.sleep(0.05)
        os.kill(pid,signal.SIGKILL);os.waitpid(pid,0);raise TimeoutError('Bounded fork child deadline exceeded')
    receipt,code=measure(args);emit(receipt);raise SystemExit(code)


if __name__=='__main__':main()
