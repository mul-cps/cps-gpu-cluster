"""Raw-driver rejection/recovery witness; no CUDA library interception."""
import argparse
import ctypes as C
import json
import uuid

parser = argparse.ArgumentParser()
parser.add_argument('--expect-rejected', action='store_true')
args = parser.parse_args()
lib = C.CDLL('libcuda.so.1')


def api(name, types):
    fn = getattr(lib, name)
    fn.argtypes = types
    fn.restype = C.c_int
    return fn


get_name = api('cuGetErrorName', [C.c_int, C.POINTER(C.c_char_p)])


def result(step, code, **extra):
    name = C.c_char_p()
    get_name(code, C.byref(name))
    print(json.dumps({'step': step, 'code': code,
                      'error_name': name.value.decode() if name.value else None, **extra}), flush=True)
    return code


def check(step, code):
    if result(step, code):
        raise RuntimeError(step + ' failed')


init = api('cuInit', [C.c_uint])
get_device = api('cuDeviceGet', [C.POINTER(C.c_int), C.c_int])
get_attribute = api('cuDeviceGetAttribute', [C.POINTER(C.c_int), C.c_int, C.c_int])
get_uuid = api('cuDeviceGetUuid_v2', [C.c_void_p, C.c_int])
create = api('cuCtxCreate_v2', [C.POINTER(C.c_void_p), C.c_uint, C.c_int])
destroy = api('cuCtxDestroy_v2', [C.c_void_p])
managed = api('cuMemAllocManaged', [C.POINTER(C.c_uint64), C.c_size_t, C.c_uint])
allocate = api('cuMemAlloc_v2', [C.POINTER(C.c_uint64), C.c_size_t])
free = api('cuMemFree_v2', [C.c_uint64])
fill = api('cuMemsetD8_v2', [C.c_uint64, C.c_ubyte, C.c_size_t])
sync = api('cuCtxSynchronize', [])
check('init', init(0))
device = C.c_int()
check('device', get_device(C.byref(device), 0))
identifier = (C.c_ubyte * 16)()
check('uuid', get_uuid(identifier, device))
print(json.dumps({'gpu_uuid': 'GPU-' + str(uuid.UUID(bytes=bytes(identifier)))}), flush=True)
for key, attribute in [('pageable_memory_access', 88), ('uses_host_page_tables', 100)]:
    value = C.c_int()
    check('attribute-' + key, get_attribute(C.byref(value), attribute, device))
    print(json.dumps({'attribute': key, 'value': value.value}), flush=True)
    if key == 'uses_host_page_tables' and value.value:
        raise RuntimeError('ATS path is outside this policy qualification')
    if args.expect_rejected and key == 'pageable_memory_access' and value.value:
        raise RuntimeError('HMM/pageable access remains advertised')
context = C.c_void_p()
check('context', create(C.byref(context), 0, device))
try:
    for iteration in range(3 if args.expect_rejected else 1):
        for flags in (1, 2):
            for mib in ((1, 5120, 24576) if args.expect_rejected else (1,)):
                ptr = C.c_uint64()
                code = managed(C.byref(ptr), mib * 1024**2, flags)
                result('managed-allocation', code, mib=mib, flags=flags, iteration=iteration)
                if code == 0:
                    check('managed-free', free(ptr))
                if (code == 0) == args.expect_rejected:
                    raise RuntimeError('managed allocation violates expected policy')
                # Every rejection must leave ordinary CUDA and this context usable.
                ordinary = C.c_uint64()
                check('ordinary-recovery-allocation', allocate(C.byref(ordinary), 1024**2))
                try:
                    check('ordinary-recovery-fill', fill(ordinary, 7, 1024**2))
                    check('ordinary-recovery-sync', sync())
                finally:
                    check('ordinary-recovery-free', free(ordinary))
finally:
    check('destroy', destroy(context))
print('MANAGED_POLICY_REJECTION_AND_RECOVERY_PASSED' if args.expect_rejected else 'STOCK_MANAGED_BASELINE_PASSED', flush=True)
