#!/usr/bin/env python3
"""Bounded real-CUDA witnesses; JSONL is evidence, never simulated qualification."""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

MIB = 1024**2


def emit(step, **values):
    print(json.dumps(dict(step=step, pid=os.getpid(), time=time.time(), **values)), flush=True)


class Location(C.Structure):
    _fields_ = [('type', C.c_int), ('id', C.c_int)]


class AllocationFlags(C.Structure):
    _fields_ = [('compressionType', C.c_ubyte), ('gpuDirectRDMACapable', C.c_ubyte),
                ('usage', C.c_ushort), ('reserved', C.c_ubyte * 4)]


class AllocationProp(C.Structure):
    _fields_ = [('type', C.c_int), ('requestedHandleTypes', C.c_int),
                ('location', Location), ('win32HandleMetaData', C.c_void_p),
                ('allocFlags', AllocationFlags)]


class AccessDesc(C.Structure):
    _fields_ = [('location', Location), ('flags', C.c_int)]


class IpcHandle(C.Structure):
    _fields_ = [('reserved', C.c_ubyte * 64)]


class CUDA:
    def __init__(self, expected_uuid):
        self.lib = C.CDLL('libcuda.so.1')
        self.call('cuInit', [C.c_uint], 0)
        count = C.c_int()
        self.call('cuDeviceGetCount', [C.POINTER(C.c_int)], C.byref(count))
        if count.value != 1:
            raise RuntimeError('Exactly one visible GPU required')
        self.dev = C.c_int()
        self.call('cuDeviceGet', [C.POINTER(C.c_int), C.c_int], C.byref(self.dev), 0)
        raw = (C.c_ubyte * 16)()
        self.call('cuDeviceGetUuid_v2', [C.c_void_p, C.c_int], raw, self.dev)
        actual = 'GPU-' + str(uuid.UUID(bytes=bytes(raw)))
        emit('identity', gpu_uuid=actual, cgroup=Path('/proc/self/cgroup').read_text(),
             stat=Path('/proc/self/stat').read_text(), node=os.environ.get('EXPECTED_NODE'),
             pod_uid=os.environ.get('POD_UID'))
        if actual != expected_uuid:
            raise RuntimeError('Physical CUDA UUID differs from requested UUID')
        host_tables = C.c_int()
        # Official CUDA enum 100, not pageable-memory-access enum 88.
        self.call('cuDeviceGetAttribute', [C.POINTER(C.c_int), C.c_int, C.c_int],
                  C.byref(host_tables), 100, self.dev)
        emit('device-attribute', attribute=100,
             name='CU_DEVICE_ATTRIBUTE_PAGEABLE_MEMORY_ACCESS_USES_HOST_PAGE_TABLES',
             value=host_tables.value, gpu_uuid=actual)
        self.ctx = C.c_void_p()
        self.call('cuCtxCreate_v2', [C.POINTER(C.c_void_p), C.c_uint, C.c_int],
                  C.byref(self.ctx), 0, self.dev)

    def call(self, name, types, *args, expected=0):
        f = getattr(self.lib, name)
        f.argtypes, f.restype = types, C.c_int
        rc = f(*args)
        emit(name, result=rc, expected=expected)
        if rc != expected:
            raise RuntimeError(f'{name}: expected CUDA {expected}, got {rc}')
        return rc

    def fill(self, p, n):
        self.call('cuMemsetD8_v2', [C.c_uint64, C.c_ubyte, C.c_size_t], p, 0x5a, n)
        self.call('cuCtxSynchronize', [])
        time.sleep(2)  # bounded external physical-memory/process snapshot window

    def ordinary(self, mib, expected=0):
        p = C.c_uint64()
        self.call('cuMemAlloc_v2', [C.POINTER(C.c_uint64), C.c_size_t],
                  C.byref(p), mib*MIB, expected=expected)
        if expected == 0:
            try:
                self.fill(p, mib*MIB)
            finally:
                self.call('cuMemFree_v2', [C.c_uint64], p)

    def recover(self):
        """Bounded convergence after a reaped crash; retain every typed OOM."""
        deadline=time.monotonic()+20
        p=C.c_uint64()
        f=self.lib.cuMemAlloc_v2;f.argtypes=[C.POINTER(C.c_uint64),C.c_size_t];f.restype=C.c_int
        while True:
            rc=f(C.byref(p),4096*MIB)
            emit('recovery-allocation',result=rc,mib=4096)
            if rc==0:break
            if rc!=2 or time.monotonic()>deadline:raise RuntimeError('Capacity did not recover within 20 seconds')
            time.sleep(.25)
        try:self.fill(p,4096*MIB)
        finally:self.call('cuMemFree_v2',[C.c_uint64],p)

    def close(self):
        self.call('cuCtxDestroy_v2', [C.c_void_p], self.ctx)


def vmm(c):
    prop = AllocationProp(type=1, location=Location(1, c.dev.value))
    gran = C.c_size_t()
    c.call('cuMemGetAllocationGranularity', [C.POINTER(C.c_size_t), C.POINTER(AllocationProp), C.c_int],
           C.byref(gran), C.byref(prop), 0)
    for mib, expected in [(1024, 0), (6144, 2), (2048, 0)]:
        n = ((mib*MIB + gran.value-1)//gran.value)*gran.value
        h, p = C.c_uint64(), C.c_uint64()
        emit('vmm-case', mib=mib, bytes=n)
        c.call('cuMemCreate', [C.POINTER(C.c_uint64), C.c_size_t, C.POINTER(AllocationProp), C.c_ulonglong],
               C.byref(h), n, C.byref(prop), 0, expected=expected)
        if expected:
            continue
        reserved = mapped = False
        try:
            c.call('cuMemAddressReserve', [C.POINTER(C.c_uint64), C.c_size_t, C.c_size_t, C.c_uint64, C.c_ulonglong], C.byref(p), n, 0, 0, 0)
            reserved = True
            c.call('cuMemMap', [C.c_uint64, C.c_size_t, C.c_size_t, C.c_uint64, C.c_ulonglong], p, n, 0, h, 0)
            mapped = True
            access = AccessDesc(Location(1, c.dev.value), 3)
            c.call('cuMemSetAccess', [C.c_uint64, C.c_size_t, C.POINTER(AccessDesc), C.c_size_t], p, n, C.byref(access), 1)
            c.fill(p, n)
        finally:
            if mapped: c.call('cuMemUnmap', [C.c_uint64, C.c_size_t], p, n)
            if reserved: c.call('cuMemAddressFree', [C.c_uint64, C.c_size_t], p, n)
            c.call('cuMemRelease', [C.c_uint64], h)


def pool(c):
    stream, pool_handle = C.c_void_p(), C.c_void_p()
    c.call('cuStreamCreate', [C.POINTER(C.c_void_p), C.c_uint], C.byref(stream), 1)
    try:
        c.call('cuDeviceGetDefaultMemPool', [C.POINTER(C.c_void_p), C.c_int], C.byref(pool_handle), c.dev)
        threshold=C.c_ulonglong(5*1024*MIB)
        c.call('cuMemPoolSetAttribute',[C.c_void_p,C.c_int,C.c_void_p],pool_handle,4,C.byref(threshold))
        for mib, expected in [(1024, 0), (6144, 2), (2048, 0), (2048, 0)]:
            p = C.c_uint64()
            emit('pool-case', mib=mib)
            c.call('cuMemAllocFromPoolAsync', [C.POINTER(C.c_uint64), C.c_size_t, C.c_void_p, C.c_void_p], C.byref(p), mib*MIB, pool_handle, stream, expected=expected)
            if not expected:
                try:
                    c.call('cuStreamSynchronize', [C.c_void_p], stream)
                    c.fill(p, mib*MIB)
                finally:
                    c.call('cuMemFreeAsync', [C.c_uint64, C.c_void_p], p, stream)
                    c.call('cuStreamSynchronize', [C.c_void_p], stream)
            for attribute in (5,7):  # RESERVED_MEM_CURRENT and USED_MEM_CURRENT
                value=C.c_ulonglong()
                c.call('cuMemPoolGetAttribute',[C.c_void_p,C.c_int,C.c_void_p],pool_handle,attribute,C.byref(value))
                emit('pool-accounting',attribute=attribute,bytes=value.value)
        c.call('cuMemPoolTrimTo', [C.c_void_p, C.c_size_t], pool_handle, 0)
    finally:
        c.call('cuStreamDestroy_v2', [C.c_void_p], stream)


def ipc(c, args):
    p, handle = C.c_uint64(), IpcHandle()
    if args.handle:
        handle = IpcHandle.from_buffer_copy(bytes.fromhex(args.handle))
        c.call('cuIpcOpenMemHandle_v2', [C.POINTER(C.c_uint64), IpcHandle, C.c_uint], C.byref(p), handle, 1)
        try:
            value = C.c_ubyte()
            c.call('cuMemcpyDtoH_v2', [C.c_void_p, C.c_uint64, C.c_size_t], C.byref(value), p, 1)
            if value.value != 0x5a: raise RuntimeError('IPC content mismatch')
            c.ordinary(3072, 2)
            c.ordinary(1024)
        finally:
            c.call('cuIpcCloseMemHandle', [C.c_uint64], p)
    else:
        c.call('cuMemAlloc_v2', [C.POINTER(C.c_uint64), C.c_size_t], C.byref(p), 3072*MIB)
        try:
            c.fill(p, 3072*MIB)
            c.call('cuIpcGetMemHandle', [C.POINTER(IpcHandle), C.c_uint64], C.byref(handle), p)
            subprocess.run([sys.executable, __file__, 'ipc', '--gpu-uuid', args.gpu_uuid,
                            '--handle', bytes(handle).hex(), '--no-gates'], check=True, timeout=45)
        finally:
            c.call('cuMemFree_v2', [C.c_uint64], p)
        c.ordinary(4096)


def crash(args):
    for generation in range(3):
        marker = Path(f'/tmp/holder-{generation}')
        child = subprocess.Popen([sys.executable, __file__, 'holder', '--gpu-uuid', args.gpu_uuid,
                                  '--marker', str(marker), '--no-gates'])
        try:
            deadline = time.monotonic()+30
            while not marker.exists():
                if child.poll() is not None: raise RuntimeError('Holder exited before allocation')
                if time.monotonic()>deadline: raise TimeoutError('holder readiness')
                time.sleep(.1)
            emit('crash-holder-ready', child_pid=child.pid, generation=generation)
            time.sleep(3)
            child.kill()
            if child.wait(timeout=10) != -signal.SIGKILL: raise RuntimeError('Expected SIGKILL exit')
            emit('crash-holder-killed', child_pid=child.pid, generation=generation)
            # A separate new process must get its own context and recover capacity.
            subprocess.run([sys.executable, __file__, 'recovery', '--gpu-uuid', args.gpu_uuid,
                            '--no-gates'], check=True, timeout=35)
        finally:
            if child.poll() is None: child.kill(); child.wait(timeout=10)
            marker.unlink(missing_ok=True)


def race(args):
    children = []
    paths = [Path('/tmp/race-start'), Path('/tmp/race-release'),
             Path('/tmp/race-result-0'), Path('/tmp/race-result-1')]
    ready=[p.with_suffix('.ready') for p in paths[2:]]
    try:
        for index in range(2):
            children.append(subprocess.Popen([sys.executable,__file__,'race-child',
                '--gpu-uuid',args.gpu_uuid,'--marker',str(paths[index+2]),'--no-gates']))
        deadline=time.monotonic()+30
        while not all(p.exists() for p in ready):
            if time.monotonic()>deadline or any(c.poll() is not None for c in children):
                raise RuntimeError('Both CUDA contexts must reach the allocation barrier')
            time.sleep(.05)
        paths[0].touch()
        while not all(p.exists() for p in paths[2:]):
            if time.monotonic()>deadline or any(c.poll() is not None for c in children):
                raise RuntimeError('Concurrent allocation did not reach result barrier')
            time.sleep(.1)
        results=[json.loads(p.read_text()) for p in paths[2:]]
        emit('race-results', results=results)
        if sorted(r['result'] for r in results)!=[0,2]:
            raise RuntimeError('Expected one 3GiB allocation and one typed OOM within 5GiB aggregate')
        time.sleep(3)
        paths[1].touch()
        for child in children:
            if child.wait(timeout=15):raise RuntimeError('Race child cleanup failed')
        subprocess.run([sys.executable,__file__,'recovery','--gpu-uuid',args.gpu_uuid,
                        '--no-gates'],check=True,timeout=35)
    finally:
        for child in children:
            if child.poll() is None:child.kill();child.wait(timeout=10)
        for path in paths+ready:path.unlink(missing_ok=True)


def race_child(c, args):
    Path(args.marker).with_suffix('.ready').touch()
    gate('race-start')
    ptr=C.c_uint64()
    f=c.lib.cuMemAlloc_v2;f.argtypes=[C.POINTER(C.c_uint64),C.c_size_t];f.restype=C.c_int
    rc=f(C.byref(ptr),3072*MIB)
    emit('race-allocation',result=rc,mib=3072)
    try:
        if rc not in (0,2):raise RuntimeError('Unexpected race allocation result')
        if rc==0:c.fill(ptr,3072*MIB)
        # Atomic publication: parent never reads a partly written result.
        marker=Path(args.marker);temporary=marker.with_suffix('.tmp')
        temporary.write_text(json.dumps({'pid':os.getpid(),'result':rc}));temporary.replace(marker)
        gate('race-release')
    finally:
        if rc==0:c.call('cuMemFree_v2',[C.c_uint64],ptr)


def gate(name):
    emit('gate', name=name)
    deadline = time.monotonic()+60
    while not Path('/tmp/'+name).exists():
        if time.monotonic()>deadline: raise TimeoutError(name)
        time.sleep(.2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('case', choices=['vmm','pool','ipc','crash','race','race-child','recovery','holder'])
    p.add_argument('--gpu-uuid', required=True)
    p.add_argument('--handle')
    p.add_argument('--marker')
    p.add_argument('--no-gates', action='store_true')
    args = p.parse_args()
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('probe deadline')))
    signal.alarm(210)
    if not args.no_gates: gate('start')
    if args.case == 'crash':
        crash(args)
    elif args.case == 'race':
        race(args)
    else:
        c = CUDA(args.gpu_uuid)
        try:
            if args.case == 'vmm': vmm(c)
            elif args.case == 'pool': pool(c)
            elif args.case == 'ipc': ipc(c, args)
            elif args.case == 'race-child': race_child(c,args)
            elif args.case == 'holder':
                ptr = C.c_uint64()
                c.call('cuMemAlloc_v2', [C.POINTER(C.c_uint64), C.c_size_t], C.byref(ptr), 4096*MIB)
                c.fill(ptr,4096*MIB)
                Path(args.marker).write_text(str(os.getpid()))
                time.sleep(60)
                raise RuntimeError('Crash holder was not killed')
            else:
                c.ordinary(6144, 2)
                c.recover()
        finally: c.close()
    emit('case-passed', case=args.case)
    if not args.no_gates: gate('release')


if __name__ == '__main__':
    main()
