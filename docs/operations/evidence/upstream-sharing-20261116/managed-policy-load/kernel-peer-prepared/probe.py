#!/usr/bin/env python3
"""Actual PTX execution and directional peer mapping, 2048 device bytes/card."""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

PTX = b'''.version 7.0
.target sm_70
.address_size 64
.visible .entry affine(.param .u64 input, .param .u64 output) {
 .reg .b32 %r<4>;
 .reg .b64 %rd<6>;
 ld.param.u64 %rd1, [input];
 ld.param.u64 %rd2, [output];
 mov.u32 %r1, %tid.x;
 mul.wide.u32 %rd3, %r1, 4;
 add.u64 %rd4, %rd1, %rd3;
 add.u64 %rd5, %rd2, %rd3;
 ld.global.u32 %r2, [%rd4];
 mad.lo.u32 %r3, %r2, 3, 7;
 st.global.u32 [%rd5], %r3;
 ret;
}
'''
EXPECTED = {'GPU-16128952-b438-556a-00bb-93039ee24e56', 'GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6'}
N = 256
SIZE = N * 4
lib = C.CDLL('libcuda.so.1')

def emit(step, **values):
    print(json.dumps(dict(step=step, time=time.time(), pid=os.getpid(), **values)), flush=True)

def call(name, types, *args):
    f = getattr(lib, name)
    f.argtypes, f.restype = types, C.c_int
    result = f(*args)
    emit(name, result=result)
    if result != 0:
        raise RuntimeError(f'{name} returned CUDA {result}')

def current(card):
    call('cuCtxSetCurrent', [C.c_void_p], card['ctx'])

def read(card, pointer):
    current(card)
    host = (C.c_uint32 * N)()
    call('cuMemcpyDtoH_v2', [C.c_void_p, C.c_uint64, C.c_size_t], host, pointer, SIZE)
    return list(host)

def launch(card, source, target):
    current(card)
    args = (C.c_void_p * 2)(C.addressof(source), C.addressof(target))
    call('cuLaunchKernel', [C.c_void_p] + [C.c_uint] * 7 + [C.c_void_p, C.POINTER(C.c_void_p), C.c_void_p],
         card['function'], 1, 1, 1, N, 1, 1, 0, None, args, None)
    call('cuCtxSynchronize', [])

def main():
    emit('process', stat=Path('/proc/self/stat').read_text(), cgroup=Path('/proc/self/cgroup').read_text(),
         profile=Path('/proc/self/attr/current').read_text(), ptx_sha256=hashlib.sha256(PTX).hexdigest())
    call('cuInit', [C.c_uint], 0)
    count = C.c_int()
    call('cuDeviceGetCount', [C.POINTER(C.c_int)], C.byref(count))
    assert count.value == 2, count.value
    cards = []
    for ordinal in range(2):
        dev = C.c_int()
        call('cuDeviceGet', [C.POINTER(C.c_int), C.c_int], C.byref(dev), ordinal)
        raw = (C.c_ubyte * 16)()
        call('cuDeviceGetUuid_v2', [C.c_void_p, C.c_int], raw, dev)
        cards.append(dict(dev=dev, uuid='GPU-' + str(uuid.UUID(bytes=bytes(raw))), pointers=[]))
    assert {x['uuid'] for x in cards} == EXPECTED
    try:
        for index, card in enumerate(cards):
            current_uuid = card['uuid']
            emit('identity', ordinal=index, gpu_uuid=current_uuid)
            ctx = C.c_void_p()
            call('cuCtxCreate_v2', [C.POINTER(C.c_void_p), C.c_uint, C.c_int], C.byref(ctx), 0, card['dev'])
            card['ctx'] = ctx
            module = C.c_void_p()
            call('cuModuleLoadData', [C.POINTER(C.c_void_p), C.c_void_p], C.byref(module), C.c_char_p(PTX))
            card['module'] = module
            function = C.c_void_p()
            call('cuModuleGetFunction', [C.POINTER(C.c_void_p), C.c_void_p, C.c_char_p], C.byref(function), module, b'affine')
            card['function'] = function
            for _ in range(2):
                ptr = C.c_uint64()
                call('cuMemAlloc_v2', [C.POINTER(C.c_uint64), C.c_size_t], C.byref(ptr), SIZE)
                card['pointers'].append(ptr)
            values = [i + index * 1000 for i in range(N)]
            card['reference'] = [x * 3 + 7 for x in values]
            host = (C.c_uint32 * N)(*values)
            call('cuMemcpyHtoD_v2', [C.c_uint64, C.c_void_p, C.c_size_t], card['pointers'][0], host, SIZE)
            launch(card, *card['pointers'])
            assert read(card, card['pointers'][1]) == card['reference']
            emit('kernel-reference-pass', gpu_uuid=current_uuid, values=N, explicit_device_bytes=2*SIZE)
        for dst, src in [(cards[0], cards[1]), (cards[1], cards[0])]:
            current(dst)
            capable = C.c_int()
            call('cuDeviceCanAccessPeer', [C.POINTER(C.c_int), C.c_int, C.c_int], C.byref(capable), dst['dev'], src['dev'])
            assert capable.value in (0, 1)
            emit('peer-capability', destination=dst['uuid'], source=src['uuid'], supported=bool(capable.value))
            if capable.value:
                call('cuCtxEnablePeerAccess', [C.c_void_p, C.c_uint], src['ctx'], 0)
                try:
                    call('cuMemcpyPeer', [C.c_uint64, C.c_void_p, C.c_uint64, C.c_void_p, C.c_size_t],
                         dst['pointers'][0], dst['ctx'], src['pointers'][1], src['ctx'], SIZE)
                    assert read(dst, dst['pointers'][0]) == src['reference']
                    # The executing kernel reads the OTHER GPU's pointer directly.
                    launch(dst, src['pointers'][1], dst['pointers'][0])
                    assert read(dst, dst['pointers'][0]) == [x*3+7 for x in src['reference']]
                    emit('direct-peer-copy-and-kernel-mapping-pass', source=src['uuid'], destination=dst['uuid'])
                finally:
                    current(dst)
                    call('cuCtxDisablePeerAccess', [C.c_void_p], src['ctx'])
            else:
                emit('direct-peer-UNSUPPORTED', source=src['uuid'], destination=dst['uuid'])
                host = (C.c_uint32 * N)(*read(src, src['pointers'][1]))
                current(dst)
                call('cuMemcpyHtoD_v2', [C.c_uint64, C.c_void_p, C.c_size_t], dst['pointers'][0], host, SIZE)
                assert read(dst, dst['pointers'][0]) == src['reference']
                emit('host-staged-copy-pass', source=src['uuid'], destination=dst['uuid'])
    finally:
        for card in reversed(cards):
            if 'ctx' not in card:
                continue
            current(card)
            for ptr in card['pointers']:
                call('cuMemFree_v2', [C.c_uint64], ptr)
            if 'module' in card:
                call('cuModuleUnload', [C.c_void_p], card['module'])
            call('cuCtxDestroy_v2', [C.c_void_p], card['ctx'])
    emit('all-passed')

if __name__ == '__main__':
    main()
