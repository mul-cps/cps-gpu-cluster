#!/usr/bin/env python3
"""Inert fixed64/128MiB driver probe; run heartbeat in a separate capped Pod."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time
import uuid


def require(ok, message):
    if not ok: raise ValueError(message)


def plan(cap):
    require(type(cap) is int and cap in (64,128), 'Only fixed64/128MiB scientific probes supported')
    return {'cap_mib':cap, 'allocation_mib_each':cap*3//5, 'managed_mib':cap+16}


def ordinary(a, b, cap):
    amount = plan(cap)['allocation_mib_each']
    result = {'allocation_mib_each':amount, 'hostile_isolation_qualified':False}
    try:
        result['a_hold'] = a.request('allocate',mib=amount)
        result['b_denied'] = b.request('allocate',mib=amount)
        result['a_continued'] = a.request('tick')
        b.request('free')  # also free an unexpected successful B allocation
        result['a_free'] = a.request('free')
        result['b_after_free'] = b.request('allocate',mib=amount)
        result['b_continued'] = b.request('tick')
        result['standard_allocations_bounded'] = (
            result['a_hold']['cuda_result'] == 0 and result['a_hold']['touch_result'] == 0
            and result['b_denied']['cuda_result'] == 2
            and result['a_continued']['cuda_result'] == 0 and result['a_free']['cuda_result'] == 0
            and result['b_after_free']['cuda_result'] == 0 and result['b_after_free']['touch_result'] == 0
            and result['b_continued']['cuda_result'] == 0)
        return result
    finally:
        a.request('free'); b.request('free')


def managed(worker, cap, *, observe=lambda: None):
    amount = plan(cap)['managed_mib']
    try:
        before = observe()
        value = worker.request('allocate',mib=amount,managed=True)
        return {'managed_mib':amount, 'managed':value, 'managed_memory_qualified':False,
                'before':before, 'after_gpu_touch':observe(),
                'managed_prefetch_above_cap_succeeded':all(value.get(k) == 0 for k in
                    ('cuda_result','prefetch_result','touch_result'))}
    finally: worker.request('free')


class Location(C.Structure):
    _fields_ = [('type',C.c_int), ('id',C.c_int)]


class DlInfo(C.Structure):
    _fields_ = [('filename',C.c_char_p), ('base',C.c_void_p), ('symbol',C.c_char_p), ('address',C.c_void_p)]


class Cuda:
    def __init__(self, gpu):
        self.lib = C.CDLL('libcuda.so.1')
        for name, args in {
            'cuInit':[C.c_uint], 'cuDriverGetVersion':[C.POINTER(C.c_int)],
            'cuDeviceGetCount':[C.POINTER(C.c_int)], 'cuDeviceGetUuid_v2':[C.c_void_p,C.c_int],
            'cuCtxCreate_v2':[C.POINTER(C.c_void_p),C.c_uint,C.c_int],
            'cuCtxDestroy_v2':[C.c_void_p], 'cuMemAlloc_v2':[C.POINTER(C.c_ulonglong),C.c_size_t],
            'cuMemAllocManaged':[C.POINTER(C.c_ulonglong),C.c_size_t,C.c_uint],
            'cuMemFree_v2':[C.c_ulonglong], 'cuMemsetD8_v2':[C.c_ulonglong,C.c_ubyte,C.c_size_t],
            'cuMemcpyDtoH_v2':[C.c_void_p,C.c_ulonglong,C.c_size_t],
            'cuMemPrefetchAsync_v2':[C.c_ulonglong,C.c_size_t,Location,C.c_uint,C.c_void_p],
            'cuMemGetInfo_v2':[C.POINTER(C.c_size_t),C.POINTER(C.c_size_t)],
            'cuCtxSynchronize':[]}.items():
            getattr(self.lib,name).argtypes=args; getattr(self.lib,name).restype=C.c_int
        self.check(self.lib.cuInit(0))
        # dlsym on the actual libcuda handle bypasses HAMi's LD_PRELOAD wrappers.
        dl=C.CDLL(None);dl.dladdr.argtypes=[C.c_void_p,C.POINTER(DlInfo)]
        info=DlInfo();require(dl.dladdr(C.cast(self.lib.cuMemAlloc_v2,C.c_void_p),C.byref(info)) != 0,'Actual driver symbol object required')
        self.driver_object=info.filename.decode()
        require(Path(self.driver_object).name.startswith('libcuda.so'),'Raw host driver object required')
        version=C.c_int();self.check(self.lib.cuDriverGetVersion(C.byref(version)))
        require(version.value >= 13040,'Host CUDA13.4 driver API required')
        self.api_version=version.value
        count=C.c_int();self.check(self.lib.cuDeviceGetCount(C.byref(count)))
        matches=[]
        for device in range(count.value):
            value=(C.c_ubyte*16)();self.check(self.lib.cuDeviceGetUuid_v2(value,device))
            if 'GPU-'+str(uuid.UUID(bytes=bytes(value))) == gpu:matches.append(device)
        require(len(matches)==1,'Exact physical GPU UUID must resolve once')
        self.device=matches[0];self.context=C.c_void_p()
        self.check(self.lib.cuCtxCreate_v2(C.byref(self.context),0,self.device))
        self.pointer=None;self.heartbeat=C.c_ulonglong()
        try: self.check(self.lib.cuMemAlloc_v2(C.byref(self.heartbeat),4))
        except Exception:
            self.lib.cuCtxDestroy_v2(self.context)
            raise

    @staticmethod
    def check(code):
        require(code==0,'CUDA operation failed with code '+str(code))

    def info(self):
        free,total=C.c_size_t(),C.c_size_t()
        code=self.lib.cuMemGetInfo_v2(C.byref(free),C.byref(total))
        return {'cuda_result':code,'free_bytes':free.value,'total_bytes':total.value}

    def allocate(self,mib,*,managed=False):
        require(type(mib) is int and 0<mib<=144 and self.pointer is None,'One bounded allocation per context')
        size=mib*1048576;pointer=C.c_ulonglong()
        code=(self.lib.cuMemAllocManaged(C.byref(pointer),size,1) if managed
              else self.lib.cuMemAlloc_v2(C.byref(pointer),size))
        result={'cuda_result':code,'allocation_mib':mib,'prefetch_result':None,'touch_result':None}
        if code==0:
            self.pointer=pointer
            if managed:
                result['prefetch_result']=self.lib.cuMemPrefetchAsync_v2(pointer,size,Location(1,self.device),0,None)
                if result['prefetch_result']==0:result['prefetch_sync_result']=self.lib.cuCtxSynchronize()
            result['touch_result']=self.lib.cuMemsetD8_v2(pointer,19,size)
            if result['touch_result']==0:result['touch_result']=self.lib.cuCtxSynchronize()
        result['memory']=self.info();return result

    def free(self):
        code=0
        if self.pointer is not None:
            code=self.lib.cuMemFree_v2(self.pointer)
            if code==0:self.pointer=None
        return {'cuda_result':code,'memory':self.info()}

    def tick(self):
        code=self.lib.cuMemsetD8_v2(self.heartbeat,37,4)
        if code==0:code=self.lib.cuCtxSynchronize()
        value=(C.c_ubyte*4)()
        if code==0:code=self.lib.cuMemcpyDtoH_v2(value,self.heartbeat,4)
        require(code!=0 or bytes(value)==b'%%%%','Device heartbeat byte verification failed')
        return {'cuda_result':code,'monotonic_ns':time.monotonic_ns(),'memory':self.info()}

    def close(self):
        allocation=self.free()
        heartbeat=self.lib.cuMemFree_v2(self.heartbeat)
        context=self.lib.cuCtxDestroy_v2(self.context)
        require(all(code==0 for code in (allocation['cuda_result'],heartbeat,context)),
                'Explicit CUDA allocation/context cleanup failed; worker termination required')


def emit(value): print(json.dumps(value,sort_keys=True),flush=True)


def worker(gpu):
    driver=None
    try:
        driver=Cuda(gpu);emit({'ready':True,'pid':os.getpid(),'driver_api_version':driver.api_version,
                              'raw_driver_object':driver.driver_object,'memory':driver.info()})
        for line in sys.stdin:
            value=json.loads(line);operation=value['operation']
            if operation=='close':break
            require(operation in ('allocate','free','tick'),'Bounded probe operation required')
            args={k:value[k] for k in ('mib','managed') if k in value}
            emit(getattr(driver,operation)(**args))
    except Exception as error:emit({'error_type':type(error).__name__,'error':str(error)})
    finally:
        if driver is not None:driver.close()


class Child:
    def __init__(self,gpu):
        self.process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker','--execute','--device-uuid',gpu],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        try:
            self.ready=self.receive();require(self.ready.get('ready') is True,'Context initialization inconclusive; small cap may be below driver overhead')
        except Exception:self.close();raise

    def receive(self):
        require(select.select([self.process.stdout],[],[],8)[0],'Bounded CUDA probe response timed out')
        value=json.loads(self.process.stdout.readline());require('error_type' not in value,'CUDA worker failed; hardware case inconclusive')
        return value

    def request(self,operation,**value):
        self.process.stdin.write(json.dumps(dict(value,operation=operation))+'\n');self.process.stdin.flush()
        return self.receive()

    def close(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.write('{"operation":"close"}\n');self.process.stdin.flush();self.process.wait(timeout=3)
            except (BrokenPipeError,subprocess.TimeoutExpired):self.process.kill();self.process.wait(timeout=3)
        for stream in (self.process.stdin,self.process.stdout,self.process.stderr):
            if stream is not None:stream.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('ordinary','managed','all','heartbeat'),default='all')
    parser.add_argument('--cap-mib',type=int,choices=(64,128),default=64)
    parser.add_argument('--device-uuid')
    parser.add_argument('--heartbeat-seconds',type=int,default=120)
    parser.add_argument('--parent-cgroup',type=Path,help='Actual read-only host Pod-parent cgroup path from cap receipt')
    parser.add_argument('--pod-uid',help='Exact reviewed Pod UID belonging to that parent')
    parser.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();parameters=plan(args.cap_mib)
    require(0<args.heartbeat_seconds<=120,'Bounded heartbeat duration required')
    if not args.execute:
        emit(dict(parameters,state='inert',gpu_calls=False,managed_memory_qualified=False));return
    require(isinstance(args.device_uuid,str) and args.device_uuid.startswith('GPU-'),'Exact physical GPU UUID required')
    if args.worker:worker(args.device_uuid);return
    require(args.parent_cgroup is not None and args.pod_uid is not None,'Actual reviewed Pod-parent memory observer required')
    require(args.parent_cgroup.name.endswith('-pod'+str(uuid.UUID(args.pod_uid)).replace('-','_')+'.slice'), 'Exact Pod-parent memory path required')
    from pod_cap import Nvml
    nvml=Nvml()
    def observe():
        limits=nvml.get(args.device_uuid,str(args.parent_cgroup))
        require(limits is not None and limits['soft']==args.cap_mib*1048576 and limits['hard']==args.cap_mib*1048576,'Actual parent driver cap must remain exact')
        return {'parent_memory_current':int((args.parent_cgroup/'memory.current').read_text()),'nvml_limits':limits,'observed_ns':time.time_ns()}
    if args.mode=='heartbeat':
        driver=None
        signal.signal(signal.SIGTERM,lambda *_: sys.exit(0))
        try:
            driver=Cuda(args.device_uuid)
            end=time.monotonic()+args.heartbeat_seconds
            while time.monotonic()<end:emit(dict(driver.tick(),kind='independent-pod-heartbeat',parent=observe()));time.sleep(0.2)
        finally:
            try:
                if driver is not None:driver.close()
            finally:nvml.close()
        return
    children=[];report=dict(parameters,hostile_isolation_qualified=False,managed_memory_qualified=False,
                           started_ns=time.time_ns(),peer_heartbeat_qualification='separate-cgroup-log-coverage-required')
    try:
        report['before_contexts']=observe()
        a=Child(args.device_uuid);children.append(a)
        if args.mode in ('ordinary','all'):
            b=Child(args.device_uuid);children.append(b)
            require(a.ready['pid']!=b.ready['pid'],'Two distinct CUDA processes required')
            report['context_startups']=[a.ready,b.ready];report['ordinary']=ordinary(a,b,args.cap_mib)
            b.close()
        if args.mode in ('managed','all'):report['managed']=managed(a,args.cap_mib,observe=observe)
        report['after_phases']=observe()
        report['status']='bounded-measurement-completed'
    except Exception as error:report.update(status='hardware-inconclusive',error_type=type(error).__name__,error=str(error))
    finally:
        for child in children:child.close()
        nvml.close();report['finished_ns']=time.time_ns()
        emit(report)
    if report['status']!='bounded-measurement-completed':raise SystemExit(1)
    if 'ordinary' in report and not report['ordinary']['standard_allocations_bounded']:raise SystemExit(1)


if __name__=='__main__':main()
