#!/usr/bin/env python3
"""Bounded same-container signal and parent-child ptrace probe; no CUDA."""
import ctypes
import json
import os
import signal
import time

def emit(**data):
    print(json.dumps(data), flush=True)

emit(event='identity', pid=os.getpid(), uid=os.getuid(), profile=open('/proc/self/attr/current').read().strip(), cgroup=open('/proc/self/cgroup').read().strip())
ready_r, ready_w = os.pipe()
child = os.fork()
if child == 0:
    os.close(ready_r)
    signal.signal(signal.SIGUSR1, lambda *_: emit(event='signal_received', pid=os.getpid()))
    os.write(ready_w, b'R')
    # Natural bounded exit also works when AppArmor denies every parent signal.
    time.sleep(8)
    os._exit(0)
os.close(ready_w)
assert os.read(ready_r, 1) == b'R'
failed = False
try:
    os.kill(child, signal.SIGUSR1)
    emit(event='signal_send', result='pass', child=child)
except OSError as exc:
    failed = True
    emit(event='signal_send', result='fail', errno=exc.errno, child=child)
time.sleep(.2)
libc = ctypes.CDLL(None, use_errno=True)
libc.ptrace.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
libc.ptrace.restype = ctypes.c_long
rc = libc.ptrace(16, child, None, None)  # PTRACE_ATTACH, parent owns child
if rc == -1:
    failed = True
    emit(event='ptrace_attach', result='fail', errno=ctypes.get_errno())
else:
    waited, status = os.waitpid(child, os.WUNTRACED)
    assert waited == child and os.WIFSTOPPED(status)
    assert libc.ptrace(17, child, None, None) == 0  # PTRACE_DETACH
    emit(event='ptrace_attach_detach', result='pass')
try:
    os.kill(child, signal.SIGKILL)
    emit(event='sigkill', result='pass')
except OSError as exc:
    failed = True
    emit(event='sigkill', result='fail', errno=exc.errno)
_, status = os.waitpid(child, 0)
emit(event='reaped', status=status, result='fail' if failed else 'pass')
raise SystemExit(int(failed))
