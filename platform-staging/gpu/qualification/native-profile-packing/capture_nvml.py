#!/usr/bin/env python3
"""Read-only selected-device NVML capture; default inert. No pynvml dependency."""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import socket
import time

GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
NODE = 'k3s-wk-gpu2'
BOOT = '209f8bc9-a478-48e4-925a-6e07ffa56f7a'
HEADER_SHA = 'c9b494b7c8015b6ae7aca62b2ce98e6b13f3277a2bec80de528371e725d54012'

class Memory(C.Structure):
    # Exact primary nvml.h253-260 v1 ABI, not the differently versioned v2 ABI.
    _fields_ = [('total', C.c_ulonglong), ('free', C.c_ulonglong), ('used', C.c_ulonglong)]

def check(code):
    if code != 0: raise ValueError('NVML read failed with code ' + str(code))

def capture(lib):
    signatures = {'nvmlInit_v2': [], 'nvmlShutdown': [],
        'nvmlSystemGetDriverVersion': [C.c_char_p, C.c_uint],
        'nvmlDeviceGetHandleByUUID': [C.c_char_p, C.POINTER(C.c_void_p)],
        'nvmlDeviceGetUUID': [C.c_void_p, C.c_char_p, C.c_uint],
        'nvmlDeviceGetMemoryInfo': [C.c_void_p, C.POINTER(Memory)],
        'nvmlDeviceGetMigMode': [C.c_void_p, C.POINTER(C.c_uint), C.POINTER(C.c_uint)]}
    for name, args in signatures.items():
        function = getattr(lib, name); function.argtypes = args; function.restype = C.c_int
    check(lib.nvmlInit_v2())
    try:
        version = C.create_string_buffer(80); check(lib.nvmlSystemGetDriverVersion(version, len(version)))
        driver = version.value.decode('ascii')
        if not driver.startswith('615.'): raise ValueError('Reviewed R615 driver required')
        handle = C.c_void_p(); check(lib.nvmlDeviceGetHandleByUUID(GPU.encode(), C.byref(handle)))
        actual = C.create_string_buffer(80); check(lib.nvmlDeviceGetUUID(handle, actual, len(actual)))
        if actual.value.decode('ascii') != GPU: raise ValueError('Wrong actual selected GPU')
        memory = Memory(); check(lib.nvmlDeviceGetMemoryInfo(handle, C.byref(memory)))
        current, pending = C.c_uint(), C.c_uint()
        check(lib.nvmlDeviceGetMigMode(handle, C.byref(current), C.byref(pending)))
        if (current.value, pending.value) != (0, 0): raise ValueError('Selected A100 current/pending MIG must both be disabled')
        if not memory.total > 0 or memory.total != memory.free + memory.used:
            raise ValueError('Typed coherent selected-device memory required')
        return {'kind': 'selected-device-nvml-memory-mig-observation', 'observed_at_ns': time.time_ns(),
            'node': NODE, 'boot_id': BOOT, 'gpu_uuid': GPU, 'driver_version': driver,
            'total_bytes': memory.total, 'free_bytes': memory.free, 'used_bytes': memory.used,
            'mig_current': current.value, 'mig_pending': pending.value, 'nvml_header_sha256': HEADER_SHA,
            'read_only': True, 'hardware_qualification': False, 'driver_generation_verified_by_probe': False}
    finally: check(lib.nvmlShutdown())

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--capture', action='store_true')
    parser.add_argument('--source-sha256'); args = parser.parse_args(argv)
    if not args.capture:
        print(json.dumps({'state': 'inert', 'api_calls': False, 'gpu_calls': False, 'hardware_qualification': False})); return
    # stdin execution has no stable __file__; Root pins the streamed bytes in
    # its transport receipt. File execution verifies the same supplied pin.
    if '__file__' in globals() and Path(__file__).is_file():
        if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != args.source_sha256:
            raise ValueError('Exact reviewed capture source required')
    if not args.source_sha256 or len(args.source_sha256) != 64 or os.geteuid() != 0 or socket.gethostname() != NODE:
        raise ValueError('Exact Root host read-only observer required')
    if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != BOOT or os.environ.get('LD_PRELOAD') or os.environ.get('LD_AUDIT'):
        raise ValueError('Reviewed host boot and raw NVML loader required')
    print(json.dumps(capture(C.CDLL('libnvidia-ml.so.1')), sort_keys=True))

if __name__ == '__main__': main()
