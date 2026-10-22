import ast
import hashlib
import os
import stat
import sys
import copy
import importlib.util
import io
import json
import tempfile
import time
from types import SimpleNamespace
from pathlib import Path
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch
spec = importlib.util.spec_from_file_location('mps_engine', Path(__file__).with_name('engine.py'))
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

def fixtures():
    mps = [{'phase': 'mps-registered', 'monotonic_ns': 2000000000, 'run_id': 'cps-mps-fixture'}, {'phase': 'typed-oom', 'monotonic_ns': 4000000000, 'run_id': 'cps-mps-fixture', 'cuda_result': 2, 'held_mib': 4608, 'attempted_mib': 4864}, {'phase': 'recovery-passed', 'monotonic_ns': 5000000000, 'run_id': 'cps-mps-fixture', 'clients': 2}, {'phase': 'daemon-cleanup-confirmed', 'monotonic_ns': 6000000000, 'run_id': 'cps-mps-fixture', 'completed': True, 'client_exit_codes': [0, 0], 'cleanup_errors': [], 'private_mps_processes': []}, {'kind': 'qualification-mps', 'state': 'bounded-sequence-passed', 'case': 'oom', 'cap_mib': 5120, 'max_attempted_mib': 5376, 'source_sha256': w.PROBE_SHA, 'aggregate_sequence_passed': True, 'recovery_clients': 2, 'typed_oom': {'cuda_result': 2, 'held_mib': 4608, 'attempted_mib': 4864}, 'production_qualified': False}]
    peer = [{'phase': 'peer_tick', 'monotonic_ns': i * 1000000000, 'tick': i} for i in range(1, 8)]
    peer.append({'phase': 'receipt', 'case': 'peer', 'state': 'measurement-completed', 'peer_loop_passed': True, 'production_qualified': False, 'hardware': {'gpu_uuid': w.GPU, 'uid': 1000, 'gid': 100}})
    return (mps, peer)

class WrapperTests(unittest.TestCase):

    def test_bounded_typed_oom_recovery_and_opposite_peer_continuity(self):
        self.assertTrue(w.assess(*fixtures())['measurement_passed'])

    def test_false_oom_missing_cleanup_and_peer_failure_never_pass(self):
        for kind in ('generic', 'early', 'over', 'cleanup', 'nonzero-client', 'peer-gap', 'peer-before-only', 'false-final', 'duplicate'):
            mps, peer = fixtures()
            if kind == 'generic':
                mps[1]['cuda_result'] = 1
            elif kind == 'early':
                mps[1]['held_mib'] = 256
            elif kind == 'over':
                mps[1]['attempted_mib'] = 5632
            elif kind == 'cleanup':
                mps[3]['cleanup_errors'] = ['failed']
            elif kind == 'nonzero-client':
                mps[3]['client_exit_codes'] = [0, 1]
            elif kind == 'peer-gap':
                peer[4]['monotonic_ns'] = 20000000000
            elif kind == 'peer-before-only':
                peer = peer[:3] + [peer[-1]]
            elif kind == 'false-final':
                mps[-1]['aggregate_sequence_passed'] = False
            elif kind == 'duplicate':
                mps.append(copy.deepcopy(mps[1]))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                w.assess(mps, peer)

    def test_cleanup_attempts_every_session_even_after_first_failure(self):
        first = Mock()
        first.finish.side_effect = RuntimeError('failure')
        second = Mock()
        second.finish.return_value = []
        values, errors = w.finish_all([first, second])
        first.finish.assert_called_once()
        second.finish.assert_called_once()
        self.assertEqual(len(errors), 1)
        self.assertEqual(values, [None, []])

    def test_registration_requires_two_exact_nonroot_clients_and_daemons(self):

        def identity(pid):
            return {'uid': 1000, 'gid': 100, 'start_ticks': pid + 10, 'namespace_pids': [pid]}
        event = {'clients': [{'identity': identity(10)}, {'identity': identity(11)}], 'daemon_processes': [{**identity(12), 'executable': 'nvidia-cuda-mps-control'}, {**identity(13), 'executable': 'nvidia-cuda-mps-server'}], 'registered_clients': [10, 11], 'registered_server': 13}
        self.assertEqual(len(w.registration_processes(event)), 4)
        for fault in ('root', 'wrongserver', 'duplicated', 'unregistered', 'boolstart', 'missing'):
            changed = copy.deepcopy(event)
            if fault == 'root':
                changed['daemon_processes'][0]['uid'] = 0
            elif fault == 'wrongserver':
                changed['registered_server'] = 10
            elif fault == 'duplicated':
                changed['daemon_processes'][0]['namespace_pids'] = [10]
            elif fault == 'unregistered':
                changed['registered_clients'] = [20, 21]
            elif fault == 'boolstart':
                changed['clients'][0]['identity']['start_ticks'] = True
            else:
                changed['daemon_processes'].pop()
            with self.subTest(fault=fault), self.assertRaises((ValueError, KeyError)):
                w.registration_processes(changed)

    def test_source_transfer_is_bounded_and_constructor_failure_reaps_local_transport(self):
        for fault in ('none', 'hung', 'write-error', 'popen-error'):
            threads = []
            process = Mock()
            process.stdin = io.BytesIO()
            process.stdout = io.BytesIO(b'{"phase":"mps-launcher-complete","child_exit_code":0,"cancelled":false}\n')
            code = [None]
            process.poll.side_effect = lambda: code[0]
            process.wait.side_effect = lambda **kwargs: code[0] or 0

            def kill():
                code[0] = -9
            process.kill.side_effect = kill

            class Thread:

                def __init__(self, target, daemon):
                    self.target = target
                    self.writer = target.__name__ == 'send'
                    self.joins = []
                    threads.append(self)

                def start(self):
                    if self.writer and fault == 'hung':
                        return
                    if self.writer and fault == 'write-error':
                        process.stdin.close()
                    self.target()

                def join(self, timeout):
                    self.joins.append(timeout)

                def is_alive(self):
                    return self.writer and fault == 'hung' and (code[0] is None)
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp, patch.object(w.threading, 'Thread', Thread), patch.object(w.subprocess, 'Popen', side_effect=OSError('transport') if fault == 'popen-error' else None, return_value=process):
                if fault == 'none':
                    session = w.Session({'namespace': 'jupyterhub', 'name': 'pod'}, [], b'exact-source', Path(tmp), 'trial')
                    session.finish()
                    process.kill.assert_not_called()
                    self.assertEqual(threads[1].joins[0], 25)
                else:
                    with self.assertRaises((ValueError, OSError)):
                        w.Session({'namespace': 'jupyterhub', 'name': 'pod'}, [], b'exact-source', Path(tmp), 'trial')
                    if fault != 'popen-error':
                        process.kill.assert_called_once()
                        self.assertTrue(process.stdout.closed)
                    self.assertTrue(all((not t.is_alive() for t in threads)))
                for name in ('mps.jsonl', 'mps.stderr'):
                    self.assertEqual(Path(tmp, name).stat().st_mode & 511, 384)
