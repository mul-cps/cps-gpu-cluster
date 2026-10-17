"""Bounded one-shot Jupyter transport; callers own authentication and kernel lifecycle."""
import hashlib
import json
import math
import time
import uuid
from datetime import datetime, timezone


def probe_code(source, expected_sha, case, duration):
    if not isinstance(source, str) or len(source.encode()) > 1024 * 1024:
        raise ValueError('Bounded UTF-8 probe source required')
    if hashlib.sha256(source.encode()).hexdigest() != expected_sha:
        raise ValueError('Exact probe source SHA required')
    if case not in ('peer', 'oom', 'aggregate-peer', 'aggregate-oom'):
        raise ValueError('Reviewed probe case required')
    if type(duration) is not int or not 5 <= duration <= 180:
        raise ValueError('Integer duration between 5 and 180 required')
    return '_source = ' + repr(source) + '\n_expected_sha = ' + repr(expected_sha) + '\n_case = ' + repr(case) + '\n_duration = ' + repr(duration) + '\n' + _CHILD


_CHILD = '''import hashlib, os, selectors, subprocess, sys, tempfile, time
if hashlib.sha256(_source.encode()).hexdigest() != _expected_sha:
    raise ValueError("Exact probe source SHA required")
with tempfile.TemporaryDirectory(prefix="cps-peer-probe-") as _directory:
    _path = os.path.join(_directory, "peer_probe.py")
    with open(_path, "x", encoding="utf-8") as _file:
        _file.write(_source)
    _process = subprocess.Popen([sys.executable, "-I", "-u", _path, "--execute", "--case", _case,
        "--duration", str(_duration), "--expected-device-uuid", "GPU-16128952-b438-556a-00bb-93039ee24e56"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        _deadline = time.monotonic() + _duration + 5
        _sizes = {"stdout": 0, "stderr": 0}
        _pending = b""
        _stderr = bytearray()
        with selectors.DefaultSelector() as _selector:
            _selector.register(_process.stdout, selectors.EVENT_READ, "stdout")
            _selector.register(_process.stderr, selectors.EVENT_READ, "stderr")
            while _selector.get_map():
                _remaining = _deadline - time.monotonic()
                if _remaining <= 0:
                    raise TimeoutError("Bounded probe child timed out")
                for _key, _mask in _selector.select(min(.1, _remaining)):
                    _chunk = os.read(_key.fileobj.fileno(), 8192)
                    if not _chunk:
                        _selector.unregister(_key.fileobj)
                        continue
                    _name = _key.data
                    _sizes[_name] += len(_chunk)
                    if _sizes[_name] > (4 * 1024 * 1024 if _name == "stdout" else 65536):
                        raise ValueError("Bounded probe child output exceeded")
                    if _name == "stderr":
                        _stderr.extend(_chunk)  # Never print arbitrary child traceback.
                    else:
                        _pending += _chunk
                        while b"\\n" in _pending:
                            _line, _pending = _pending.split(b"\\n", 1)
                            if len(_line) > 65536:
                                raise ValueError("Bounded probe line exceeded")
                            print(_line.decode("utf-8"), flush=True)
                        if len(_pending) > 65536:
                            raise ValueError("Bounded probe line exceeded")
            _returncode = _process.wait(timeout=max(.001, _deadline-time.monotonic()))
        if _returncode != 0 or _pending:
            raise RuntimeError("Probe child failed or emitted incomplete output")
    finally:
        if _process.poll() is None:
            _process.kill()  # Only this exact child, never the kernel or a process group.
        _process.wait(timeout=5)
        _process.stdout.close()
        _process.stderr.close()
'''


def exchange(socket, code, session, consume, *, timeout):
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 240:
        raise ValueError('Finite transport deadline required')
    message_id = str(uuid.uuid4())
    request = {'header': {'msg_id': message_id, 'username': 'cps-qa', 'session': session,
                         'date': datetime.now(timezone.utc).isoformat(), 'msg_type': 'execute_request', 'version': '5.3'},
               'parent_header': {}, 'metadata': {}, 'channel': 'shell',
               'content': {'code': code, 'silent': False, 'store_history': False, 'user_expressions': {},
                           'allow_stdin': False, 'stop_on_error': True}, 'buffers': []}
    deadline = time.monotonic() + timeout
    socket.send(json.dumps(request))  # Exactly once; never automatically replay execution.
    reply, idle, buffer, total, reads = None, False, '', 0, 0
    while time.monotonic() < deadline:
        try:
            message = socket.recv(timeout=min(30, max(.001, deadline - time.monotonic())))
        except TimeoutError:
            continue
        reads += 1
        if reads > 100000 or not isinstance(message, str):
            raise ValueError('Bounded text kernel protocol required')
        total += len(message.encode())
        if total > 8 * 1024 * 1024:
            raise ValueError('Kernel output exceeds bound')
        value = json.loads(message)
        if value.get('parent_header', {}).get('msg_id') != message_id:
            continue
        kind = value.get('msg_type', value.get('header', {}).get('msg_type'))
        content = value.get('content', {})
        if kind == 'stream':
            if content.get('name', 'stdout') != 'stdout':
                continue  # Never expose kernel stderr traceback.
            buffer += content.get('text', '')
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if len(line.encode()) > 65536:
                    raise ValueError('Kernel line exceeds bound')
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError('Structured probe event required')
                consume(event)
            if len(buffer.encode()) > 65536:
                raise ValueError('Kernel line exceeds bound')
        elif kind == 'execute_reply' and value.get('channel') == 'shell':
            reply = content.get('status')
        elif kind == 'status' and value.get('channel') == 'iopub' and content.get('execution_state') == 'idle':
            idle = True
        if reply is not None and idle:
            if reply != 'ok' or buffer:
                raise RuntimeError('Kernel execution failed without exposing traceback')
            return
    raise TimeoutError('Bounded kernel execution timed out')
