#!/usr/bin/env python3
"""Inert unless explicitly executed after Root's current native-cap preflight."""
import argparse
import array
import socket
import struct
import base64
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import select
import sys
import threading
import time
import uuid

GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
BOOT = '209f8bc9-a478-48e4-925a-6e07ffa56f7a'
CAP = 5368709120
BYTES = 64 * 1024 * 1024
PTX = b'''.version 7.0
.target sm_80
.address_size 64
.visible .entry poke(.param .u64 address,.param .u32 value){
 .reg .b64 p; .reg .b32 v;
 ld.param.u64 p,[address]; ld.param.u32 v,[value];
 st.global.u8 [p],v; ret;
}\n'''

def require(ok, message):
    if not ok: raise ValueError(message)

def handle_bytes(value):
    require(isinstance(value, str) and len(value) == 88, 'Exact opaque64-byte IPC handle required')
    raw = base64.b64decode(value, validate=True)
    require(len(raw) == 64 and base64.b64encode(raw).decode() == value, 'Canonical opaque IPC handle required')
    return raw

def canonical_uuid(value):
    require(isinstance(value, str) and str(uuid.UUID(value)) == value and uuid.UUID(value).int != 0, 'Canonical nonzero trial UUID required')

def emit(phase, **data):
    print(json.dumps({'kind': 'controlled-vmm-endpoint', 'phase': phase,
        'time_ns': time.time_ns(), 'monotonic_ns': time.monotonic_ns(), 'namespace_pid': os.getpid(),
        'production_qualified': False, **data}, sort_keys=True, allow_nan=False), flush=True)

class Handle(C.Structure):
    _fields_ = [('reserved', C.c_ubyte * 64)]

class Native:
    def __init__(self):
        self.lib = C.CDLL('libcuda.so.1')
        self.context, self.module, self.function = C.c_void_p(), C.c_void_p(), C.c_void_p()
        self.allocations, self.imported = [], []
        definitions = {
            'cuInit': [C.c_uint], 'cuDriverGetVersion': [C.POINTER(C.c_int)],
            'cuDeviceGetCount': [C.POINTER(C.c_int)], 'cuDeviceGetUuid_v2': [C.c_void_p, C.c_int],
            'cuCtxCreate_v2': [C.POINTER(C.c_void_p), C.c_uint, C.c_int], 'cuCtxDestroy_v2': [C.c_void_p],
            'cuMemGetInfo_v2': [C.POINTER(C.c_size_t), C.POINTER(C.c_size_t)],
            'cuMemAlloc_v2': [C.POINTER(C.c_uint64), C.c_size_t], 'cuMemFree_v2': [C.c_uint64],
            'cuIpcGetMemHandle': [C.POINTER(Handle), C.c_uint64],
            'cuIpcOpenMemHandle_v2': [C.POINTER(C.c_uint64), Handle, C.c_uint], 'cuIpcCloseMemHandle': [C.c_uint64],
            'cuMemcpyDtoH_v2': [C.c_void_p, C.c_uint64, C.c_size_t], 'cuCtxSynchronize': [],
            'cuModuleLoadData': [C.POINTER(C.c_void_p), C.c_void_p],
            'cuModuleGetFunction': [C.POINTER(C.c_void_p), C.c_void_p, C.c_char_p], 'cuModuleUnload': [C.c_void_p],
            'cuLaunchKernel': [C.c_void_p, *([C.c_uint] * 7), C.c_void_p, C.POINTER(C.c_void_p), C.POINTER(C.c_void_p)],
            'cuGetErrorName': [C.c_int, C.POINTER(C.c_char_p)],
        }
        for name, types in definitions.items():
            f = getattr(self.lib, name); f.argtypes = types; f.restype = C.c_int
        try:
            self.ok('cuInit', 0)
            version, count = C.c_int(), C.c_int()
            self.ok('cuDriverGetVersion', C.byref(version)); self.ok('cuDeviceGetCount', C.byref(count))
            require(version.value >= 13040 and count.value == 1, 'Driver13.4+ and one actual GPU required')
            actual = (C.c_ubyte * 16)(); self.ok('cuDeviceGetUuid_v2', actual, 0)
            require('GPU-' + str(uuid.UUID(bytes=bytes(actual))) == GPU, 'Exact physical GPU required')
            self.ok('cuCtxCreate_v2', C.byref(self.context), 0, 0)
            free, total = C.c_size_t(), C.c_size_t(); self.ok('cuMemGetInfo_v2', C.byref(free), C.byref(total))
            require(total.value == CAP and 0 <= free.value < CAP, 'Exact finite5GiB capped CUDA client required')
            emit('identity', gpu_uuid=GPU, uid=os.getuid(), gid=os.getgid(), driver_api_version=version.value,
                 cap_bytes=total.value, free_bytes=free.value)
        except BaseException:
            self.close(); raise
    def ok(self, name, *args):
        result = getattr(self.lib, name)(*args)
        require(result == 0, name + ' failed with CUDA result ' + str(result))
    def allocate(self):
        pointer = C.c_uint64(); self.ok('cuMemAlloc_v2', C.byref(pointer), BYTES)
        self.allocations.append(pointer.value); return pointer.value
    def release(self, pointer):
        self.ok('cuMemFree_v2', pointer); self.allocations.remove(pointer)
    def read(self, pointer):
        value = C.c_ubyte(); self.ok('cuMemcpyDtoH_v2', C.byref(value), pointer, 1); return value.value
    def poke(self, pointer, value):
        if not self.module.value:
            self.ok('cuModuleLoadData', C.byref(self.module), C.c_char_p(PTX))
            self.ok('cuModuleGetFunction', C.byref(self.function), self.module, b'poke')
        p, v = C.c_uint64(pointer), C.c_uint(value)
        params = (C.c_void_p * 2)(C.addressof(p), C.addressof(v))
        self.ok('cuLaunchKernel', self.function, 1, 1, 1, 1, 1, 1, 0, None, params, None)
        self.ok('cuCtxSynchronize'); require(self.read(pointer) == value, 'Exporter GPU kernel/readback failed')
    def close(self):
        errors = []
        for name, arguments in [('cuIpcCloseMemHandle', (p,)) for p in self.imported] + \
                [('cuMemFree_v2', (p,)) for p in self.allocations] + \
                ([('cuModuleUnload', (self.module,))] if self.module.value else []) + \
                ([('cuCtxDestroy_v2', (self.context,))] if self.context.value else []):
            try: self.ok(name, *arguments)
            except Exception: errors.append(name)
        self.imported.clear(); self.allocations.clear(); self.module, self.context = C.c_void_p(), C.c_void_p()
        require(not errors, 'Explicit native cleanup failed')

# CUDA13.4 x86_64 layouts match native-imports/native_imports.c static assertions.
class Location(C.Structure):
    _fields_=[('type',C.c_int),('id',C.c_int)]
class AllocationProp(C.Structure):
    _fields_=[('type',C.c_int),('requestedHandleTypes',C.c_int),('location',Location),
              ('win32HandleMetaData',C.c_void_p),('allocFlags',C.c_ubyte*8)]
class AccessDesc(C.Structure):
    _fields_=[('location',Location),('flags',C.c_uint)]
require(C.sizeof(AllocationProp)==32 and C.sizeof(AccessDesc)==12,'Reviewed CUDA13.4 ABI required')

class VmmNative(Native):
    def __init__(self):
        self.vmm=[]
        super().__init__()
        signatures={
            'cuMemGetAllocationGranularity':[C.POINTER(C.c_size_t),C.POINTER(AllocationProp),C.c_int],
            'cuMemCreate':[C.POINTER(C.c_uint64),C.c_size_t,C.POINTER(AllocationProp),C.c_ulonglong],
            'cuMemRelease':[C.c_uint64],
            'cuMemAddressReserve':[C.POINTER(C.c_uint64),C.c_size_t,C.c_size_t,C.c_uint64,C.c_ulonglong],
            'cuMemAddressFree':[C.c_uint64,C.c_size_t],
            'cuMemMap':[C.c_uint64,C.c_size_t,C.c_size_t,C.c_uint64,C.c_ulonglong],
            'cuMemUnmap':[C.c_uint64,C.c_size_t],
            'cuMemSetAccess':[C.c_uint64,C.c_size_t,C.POINTER(AccessDesc),C.c_size_t],
            'cuMemExportToShareableHandle':[C.c_void_p,C.c_uint64,C.c_int,C.c_ulonglong],
            'cuMemImportFromShareableHandle':[C.POINTER(C.c_uint64),C.c_void_p,C.c_int]}
        try:
            for name,types in signatures.items():
                function=getattr(self.lib,name);function.argtypes=types;function.restype=C.c_int
        except BaseException:
            self.close();raise
    def map(self,value):
        address=C.c_uint64();self.ok('cuMemAddressReserve',C.byref(address),BYTES,0,0,0)
        value['address']=address.value;self.ok('cuMemMap',address.value,BYTES,0,value['handle'],0);value['mapped']=True
        access=AccessDesc(Location(1,0),3);self.ok('cuMemSetAccess',address.value,BYTES,C.byref(access),1)
        return address.value
    def create(self):
        prop=AllocationProp();prop.type=1;prop.requestedHandleTypes=1;prop.location=Location(1,0)
        granularity=C.c_size_t();self.ok('cuMemGetAllocationGranularity',C.byref(granularity),C.byref(prop),0)
        require(granularity.value>0 and BYTES%granularity.value==0,'Exact64MiB granularity required')
        handle=C.c_uint64();self.ok('cuMemCreate',C.byref(handle),BYTES,C.byref(prop),0)
        value={'handle':handle.value,'address':0,'mapped':False,'fd':None};self.vmm.append(value)
        self.map(value);self.poke(value['address'],19)
        fd=C.c_int(-1);self.ok('cuMemExportToShareableHandle',C.byref(fd),handle.value,1,0)
        require(fd.value>=0,'Actual POSIX GPU descriptor required');value['fd']=fd.value;return value
    def import_fd(self,fd):
        handle=C.c_uint64();result=self.lib.cuMemImportFromShareableHandle(C.byref(handle),C.c_void_p(fd),1)
        if result==0:self.vmm.append({'handle':handle.value,'address':0,'mapped':False,'fd':None})
        return result,self.vmm[-1] if result==0 else None
    def close(self):
        errors=[]
        for value in reversed(self.vmm):
            for name,arguments in ([('cuMemUnmap',(value['address'],BYTES))] if value['mapped'] else [])+\
                    ([('cuMemRelease',(value['handle'],))] if value['handle'] else [])+\
                    ([('cuMemAddressFree',(value['address'],BYTES))] if value['address'] else []):
                try:self.ok(name,*arguments)
                except Exception:errors.append(name)
            if value['fd'] is not None:
                try:os.close(value['fd'])
                except OSError:errors.append('close-export-fd')
        self.vmm.clear()
        try:super().close()
        except Exception:errors.append('base-context-cleanup')
        require(not errors,'Explicit VMM/context/FD cleanup failed')

def receive_descriptor(connection,trial,exporter_pod_uid):
    credentials=struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
    require(credentials[1:]==(1000,100),'Exact ordinary UID1000/GID100 descriptor sender required')
    data,control,flags,_=connection.recvmsg(4096,socket.CMSG_SPACE(array.array('i').itemsize),socket.MSG_CMSG_CLOEXEC)
    fds=[]
    try:
        unknown=False
        for level,kind,value in control:
            if level==socket.SOL_SOCKET and kind==socket.SCM_RIGHTS:
                values=array.array('i');values.frombytes(value);fds.extend(values)
            else:unknown=True
        require(not unknown,'Only POSIX descriptor ancillary data permitted')
        allowed=socket.MSG_CMSG_CLOEXEC|socket.MSG_EOR
        require(not flags&~allowed and len(fds)==1,'Exactly one complete nontruncated descriptor required')
        require(json.loads(data)==dict(trial_id=trial,exporter_pod_uid=exporter_pod_uid,bytes=BYTES),
                'Exact current trial/exporter/64MiB descriptor header required')
        return fds.pop()
    finally:
        for fd in fds:os.close(fd)

def export(native,args):
    value=native.create();fd=value['fd'];st=os.fstat(fd)
    emit('handle-ready',trial_id=args.trial_id,export_fd=fd,buffer_bytes=BYTES,kernel_byte=19,
         fd_stat={k:getattr(st,'st_'+k) for k in ('dev','ino','mode','rdev')})
    deadline=time.monotonic()+105;ticks=0;recovered=False
    while time.monotonic()<deadline:
        native.poke(value['address'],19);ticks+=1;emit('exporter-tick',trial_id=args.trial_id,tick=ticks,kernel_byte=19)
        if not select.select([sys.stdin.buffer],[],[],.4)[0]:continue
        line=sys.stdin.buffer.readline(65537);require(line and len(line)<=65536,'Bounded Root command required')
        command=json.loads(line);require(set(command)=={'op','trial_id'} and command['trial_id']==args.trial_id,'Exact Root trial required')
        if command['op']=='recover':
            require(not recovered,'Only one recovery allowed');own=native.allocate();native.poke(own,37);native.release(own)
            require(native.read(value['address'])==19,'Exporter backing changed');recovered=True
            emit('exporter-recovery',trial_id=args.trial_id,recovery_byte=37,original_byte=19)
        elif command['op']=='finish':
            require(recovered and ticks>=2,'Recovery and continuous exporter required');emit('exporter-finished',trial_id=args.trial_id,ticks=ticks);return
        else:raise ValueError('Unknown Root command')
    raise TimeoutError('Bounded exporter deadline exceeded')

def import_descriptor(native,args):
    own=native.allocate();native.poke(own,11);emit('importer-before-kernel',trial_id=args.trial_id,kernel_byte=11)
    address='\0cps-qa-vmm-'+args.trial_id
    with socket.socket(socket.AF_UNIX,socket.SOCK_SEQPACKET) as listener:
        listener.bind(address);listener.listen(1);listener.settimeout(15)
        emit('importer-ready',trial_id=args.trial_id)
        connection,_=listener.accept()
        with connection:fd=receive_descriptor(connection,args.trial_id,args.exporter_pod_uid)
    try:
        emit('importer-fd-ready',trial_id=args.trial_id)
        require(select.select([sys.stdin.buffer],[],[],15)[0],'Bounded Root open deadline required')
        line=sys.stdin.buffer.readline(65537);require(line and len(line)<=65536,'Bounded Root open command required')
        require(json.loads(line)=={'op':'open','trial_id':args.trial_id},'Exact Root import command required')
        start=time.monotonic_ns();wall=time.time_ns();result,value=native.import_fd(fd)
        end=time.monotonic_ns();endwall=time.time_ns();name=C.c_char_p();status=native.lib.cuGetErrorName(result,C.byref(name))
        emit('import-result',trial_id=args.trial_id,api='cuMemImportFromShareableHandle',cuda_result=result,
             cuda_name=name.value.decode() if status==0 and name.value else None,expect=args.expect,
             call_started_monotonic_ns=start,call_ended_monotonic_ns=end,call_started_time_ns=wall,
             call_ended_time_ns=endwall,expected_kernel_status=27,expected_kernel_reason=6)
        if result==0:
            require(args.expect=='allow','Unexpected cross-parent success; object never mapped or touched')
            native.map(value);require(native.read(value['address'])==19,'Same-parent VMM readback required')
            emit('same-parent-positive',trial_id=args.trial_id,imported_byte=19)
        else:require(args.expect=='deny' and status==0,'Typed expected VMM import denial required')
        native.poke(own,17);native.release(own);emit('importer-after-kernel',trial_id=args.trial_id,kernel_byte=17)
    finally:os.close(fd)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--role',choices=('exporter','importer'))
    parser.add_argument('--gpu-uuid');parser.add_argument('--trial-id');parser.add_argument('--expect',choices=('allow','deny'))
    parser.add_argument('--cap-mib',type=int,choices=(5120,20480),default=5120);parser.add_argument('--exporter-pod-uid')
    args=parser.parse_args(argv)
    if not args.execute:emit('inert',gpu_calls=False,api_calls=False,payload_bytes=BYTES);return
    canonical_uuid(args.trial_id);require(args.gpu_uuid==GPU and args.role is not None,'Exact physical GPU and role required')
    require((os.getuid(),os.getgid())==(1000,100) and not os.environ.get('LD_PRELOAD') and not os.environ.get('LD_AUDIT')
            and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'Ordinary capped reviewed notebook required')
    if args.role=='importer':canonical_uuid(args.exporter_pod_uid);require(args.expect is not None,'Explicit expected outcome required')
    global CAP
    CAP=args.cap_mib*1048576
    watchdog=threading.Timer(115,lambda:os._exit(124));watchdog.daemon=True;watchdog.start();native=None;failure=None
    try:
        native=VmmNative()
        if args.role=='exporter':export(native,args)
        else:import_descriptor(native,args)
    except Exception as error:failure=type(error).__name__+': '+str(error)
    finally:
        if native is not None:
            try:native.close()
            except Exception as error:failure=type(error).__name__+': '+str(error)
        watchdog.cancel()
    emit('receipt',trial_id=args.trial_id,role=args.role,state='measurement-completed' if failure is None else 'inconclusive',
         error=failure,explicit_native_cleanup_completed=failure is None,production_qualified=False)
    if failure is not None:raise SystemExit(1)

if __name__=='__main__':main()
