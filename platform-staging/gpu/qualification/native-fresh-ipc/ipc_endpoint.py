#!/usr/bin/env python3
"""Inert unless explicitly executed after Root's current native-cap preflight."""
import argparse
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
BOOT = 'a464df41-e391-4443-b8e8-ad7ecd052318'
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
    print(json.dumps({'kind': 'controlled-ipc-endpoint', 'phase': phase,
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
        require(result == 0, name + ' failed')
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

def importer(native, trial, encoded, expected, wait_for_root=False):
    raw = handle_bytes(encoded); handle = Handle.from_buffer_copy(raw); pointer = C.c_uint64()
    own = native.allocate(); native.poke(own, 11)
    emit('importer-before-kernel', trial_id=trial, kernel_byte=11, own_buffer_bytes=BYTES)
    if wait_for_root:
        emit('importer-ready', trial_id=trial)
        ready, _, _ = select.select([sys.stdin.buffer], [], [], 15)
        require(ready, 'Root pre-import observation deadline exceeded')
        line = sys.stdin.buffer.readline(65537)
        require(line and len(line) <= 65536 and line.endswith(b'\n'), 'Bounded Root import command required')
        require(json.loads(line) == {'op': 'open', 'trial_id': trial}, 'Exact Root import command required')
    started = time.monotonic_ns(); wall = time.time_ns()
    result = native.lib.cuIpcOpenMemHandle_v2(C.byref(pointer), handle, 1)
    ended = time.monotonic_ns(); end_wall = time.time_ns(); name = C.c_char_p()
    name_result = native.lib.cuGetErrorName(result, C.byref(name))
    error_name = name.value.decode('ascii') if name_result == 0 and name.value else None
    emit('import-result', trial_id=trial, api='cuIpcOpenMemHandle_v2', cuda_result=result, cuda_name=error_name,
        expect=expected, handle_sha256=hashlib.sha256(raw).hexdigest(), call_started_monotonic_ns=started,
        call_ended_monotonic_ns=ended, call_started_time_ns=wall, call_ended_time_ns=end_wall,
        expected_kernel_status=27, expected_kernel_reason=6)
    if result == 0:
        native.imported.append(pointer.value)
        if expected == 'deny':
            # Never read/write an unexpectedly authorized cross-parent mapping.
            raise ValueError('Cross-parent IPC import unexpectedly succeeded')
        require(native.read(pointer.value) == 19, 'Same-parent positive control readback failed')
        emit('same-parent-positive', trial_id=trial, imported_byte=19)
    else:
        require(expected == 'deny' and name_result == 0 and isinstance(error_name, str)
            and error_name.startswith('CUDA_ERROR_'), 'IPC positive control or typed API result failed')
        emit('denial-observed-awaiting-kernel-witness', trial_id=trial, cuda_result=result, cuda_name=error_name,
             cross_parent_isolation_qualified=False)
    native.poke(own, 17); native.release(own)
    emit('importer-after-kernel', trial_id=trial, kernel_byte=17)

def exporter(native, trial):
    pointer = native.allocate(); native.poke(pointer, 19); handle = Handle()
    native.ok('cuIpcGetMemHandle', C.byref(handle), pointer)
    raw = bytes(handle)
    emit('handle-ready', trial_id=trial, handle_b64=base64.b64encode(raw).decode(),
         handle_sha256=hashlib.sha256(raw).hexdigest(), buffer_bytes=BYTES, kernel_byte=19)
    deadline = time.monotonic() + 105; ticks = 0; recovered = False
    while time.monotonic() < deadline:
        native.poke(pointer, 19); ticks += 1
        emit('exporter-tick', trial_id=trial, tick=ticks, kernel_byte=19)
        ready, _, _ = select.select([sys.stdin.buffer], [], [], 0.4)
        if not ready: continue
        raw = sys.stdin.buffer.readline(65537)
        require(raw and len(raw) <= 65536 and raw.endswith(b'\n'), 'Bounded live Root command required')
        command = json.loads(raw)
        require(isinstance(command, dict) and set(command) == {'op', 'trial_id'} and command['trial_id'] == trial,
                'Exact current Root IPC command required')
        if command['op'] == 'recover':
            require(not recovered, 'Only one bounded recovery request permitted')
            recovery = native.allocate()
            try: native.poke(recovery, 37)
            finally: native.release(recovery)
            require(native.read(pointer) == 19, 'Original exporter backing changed')
            recovered = True; emit('exporter-recovery', trial_id=trial, recovery_byte=37, original_byte=19)
        elif command['op'] == 'finish':
            require(recovered and ticks >= 2, 'Exporter continuity and post-denial recovery required')
            emit('exporter-finished', trial_id=trial, ticks=ticks); return
        else: raise ValueError('Unsupported Root command')
    raise TimeoutError('Root-controlled exporter deadline exceeded')

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true'); p.add_argument('--role', choices=('exporter', 'importer'))
    p.add_argument('--gpu-uuid'); p.add_argument('--trial-id'); p.add_argument('--handle-b64')
    p.add_argument('--expect', choices=('allow', 'deny'))
    p.add_argument('--wait-for-root', action='store_true')
    args = p.parse_args(argv)
    if not args.execute:
        emit('inert', gpu_calls=False); return
    require(args.gpu_uuid == GPU and args.role is not None, 'Explicit role and exact GPU required')
    canonical_uuid(args.trial_id)
    require((os.getuid(), os.getgid()) == (1000, 100) and not os.environ.get('LD_PRELOAD')
        and Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT, 'Exact notebook UID/GID/boot/no-preload required')
    if args.role == 'importer': require(args.expect is not None and handle_bytes(args.handle_b64), 'Exact import request required')
    watchdog = threading.Timer(115, lambda: os._exit(124)); watchdog.daemon = True; watchdog.start()
    native = None; failure = None
    try:
        native = Native()
        if args.role == 'exporter': exporter(native, args.trial_id)
        else: importer(native, args.trial_id, args.handle_b64, args.expect, args.wait_for_root)
    except Exception as error: failure = type(error).__name__
    finally:
        if native is not None:
            try: native.close()
            except Exception as error: failure = type(error).__name__
        watchdog.cancel()
    emit('receipt', trial_id=args.trial_id, role=args.role, state='measurement-completed' if failure is None else 'inconclusive',
        error_type=failure, explicit_native_cleanup_completed=failure is None, cross_parent_isolation_qualified=False)
    if failure is not None: raise SystemExit(1)

if __name__ == '__main__': main()
