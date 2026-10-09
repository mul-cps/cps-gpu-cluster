"""Bounded trusted CUDA session checks; never changes driver or native caps."""
import argparse
import ctypes as C
import json
import os
import time

from cuda_probe import Cuda, require


def emit(value):
    print(json.dumps(value, sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--gpu-uuid')
    parser.add_argument('--cap-mib', type=int, choices=(512, 5120))
    parser.add_argument('--mode', choices=('heartbeat', 'oom', 'managed'))
    parser.add_argument('--seconds', type=int, default=120)
    args = parser.parse_args()
    if not args.execute:
        emit({'state': 'inert', 'production_qualified': False})
        return
    require(args.gpu_uuid and args.cap_mib and args.mode, 'Exact trusted fixture arguments required')
    require(os.getuid() == 1000 and os.getgid() == 100 and not os.environ.get('LD_PRELOAD'),
            'Ordinary UID1000/GID100 without preload required')
    require(1 <= args.seconds <= 180, 'Bounded measurement interval required')
    driver = Cuda(args.gpu_uuid)
    try:
        info = driver.info()
        require(info['cuda_result'] == 0 and info['total_bytes'] == args.cap_mib * 1048576,
                'Actual process-visible native cap must match trusted fixture')
        driver.lib.cuDeviceGetAttribute.argtypes = [C.POINTER(C.c_int), C.c_int, C.c_int]
        attributes = {}
        for attribute in (88, 100):
            value = C.c_int()
            driver.check(driver.lib.cuDeviceGetAttribute(C.byref(value), attribute, driver.device))
            attributes[attribute] = value.value
        require(all(value == 0 for value in attributes.values()), 'Pageable/HMM access must be disabled')
        emit({'state': 'context-ready', 'pid': os.getpid(), 'mode': args.mode,
              'attributes': attributes, 'memory': info, 'observed_ns': time.time_ns()})
        if args.mode == 'heartbeat':
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline:
                tick = driver.tick()
                require(tick['cuda_result'] == 0, 'Peer CUDA heartbeat failed')
                emit({'state': 'peer-tick', 'tick': tick, 'observed_ns': time.time_ns()})
                time.sleep(0.2)
        elif args.mode == 'managed':
            result = driver.allocate(64, managed=True)
            emit({'state': 'managed-attempt', 'result': result, 'observed_ns': time.time_ns()})
            require(result['cuda_result'] != 0, 'Managed allocation escaped the guard')
            require(driver.tick()['cuda_result'] == 0, 'Ordinary CUDA failed after managed denial')
        else:
            first = driver.allocate(64)
            require(first['cuda_result'] == 0 and first['touch_result'] == 0, '64MiB ordinary allocation failed')
            driver.check(driver.free()['cuda_result'])
            pointer = C.c_ulonglong()
            code = driver.lib.cuMemAlloc_v2(C.byref(pointer), args.cap_mib * 1048576)
            # Unexpected success is released without mapping or touching the requested budget.
            if code == 0:
                driver.check(driver.lib.cuMemFree_v2(pointer))
            emit({'state': 'over-cap-attempt', 'cuda_result': code, 'observed_ns': time.time_ns()})
            require(code == 2, 'Only numeric CUDA OOM2 qualifies the over-cap attempt')
            recovery = driver.allocate(64)
            require(recovery['cuda_result'] == 0 and recovery['touch_result'] == 0,
                    '64MiB ordinary recovery failed')
            require(driver.tick()['cuda_result'] == 0, 'CUDA heartbeat failed after ordinary OOM')
        emit({'state': 'measurement-passed', 'mode': args.mode, 'observed_ns': time.time_ns(),
              'production_qualified': False})
    finally:
        driver.close()


if __name__ == '__main__':
    main()
