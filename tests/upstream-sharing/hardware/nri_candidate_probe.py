#!/usr/bin/env python3
"""Ordinary CUDA survivor with repeated quota rejection and live device work."""
import ctypes as C
import json
from pathlib import Path
import time

def emit(step, **data):
    print(json.dumps(dict(step=step, time=time.time(), **data)), flush=True)

def gate(name):
    deadline = time.monotonic()+180
    while not Path('/tmp/'+name).exists():
        if time.monotonic()>deadline:
            raise TimeoutError(name)
        time.sleep(.1)

lib = C.CDLL('libcuda.so.1')
def call(name, types, *args, expected=0):
    f = getattr(lib,name);f.argtypes=types;f.restype=C.c_int
    rc=f(*args)
    emit(name,result=rc,expected=expected)
    if rc!=expected:
        raise RuntimeError(f'{name} expected {expected}, got {rc}')

gate('start')
call('cuInit',[C.c_uint],0)
dev=C.c_int();call('cuDeviceGet',[C.POINTER(C.c_int),C.c_int],C.byref(dev),0)
ctx=C.c_void_p();call('cuCtxCreate_v2',[C.POINTER(C.c_void_p),C.c_uint,C.c_int],C.byref(ctx),0,dev)
ptr=C.c_uint64()
try:
    call('cuMemAlloc_v2',[C.POINTER(C.c_uint64),C.c_size_t],C.byref(ptr),1024**3)
    call('cuMemsetD8_v2',[C.c_uint64,C.c_ubyte,C.c_size_t],ptr,0x5a,1024**3)
    deadline=time.monotonic()+180
    while not Path('/tmp/release').exists():
        if time.monotonic()>deadline:
            raise TimeoutError('release')
        too_big=C.c_uint64()
        call('cuMemAlloc_v2',[C.POINTER(C.c_uint64),C.c_size_t],C.byref(too_big),6*1024**3,expected=2)
        call('cuMemsetD8_v2',[C.c_uint64,C.c_ubyte,C.c_size_t],ptr,0x5a,4096)
        call('cuCtxSynchronize',[])
        emit('progress-and-quota-pass')
        time.sleep(2)
finally:
    if ptr.value:call('cuMemFree_v2',[C.c_uint64],ptr)
    call('cuCtxDestroy_v2',[C.c_void_p],ctx)
emit('passed')
