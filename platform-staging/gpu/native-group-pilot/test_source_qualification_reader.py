import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import source_qualification_reader as reader

ORIGINAL = Path('/home/bjoern/.local/state/cps-group-native-20261009/group-probes/profile-handover-factory-prepared/gateway_reader.py')
TARGET = '..2026_10_09_21_22_01.1234567890'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.directory = self.root / TARGET
        self.directory.mkdir()
        self.raw = b'{"state_directory":"/state"}'
        (self.directory / 'runtime.json').write_bytes(self.raw)
        (self.root / '..data').symlink_to(TARGET)
        (self.root / 'runtime.json').symlink_to('..data/runtime.json')
        real_open, real_stat = os.open, os.stat
        self.open = patch.object(reader.os, 'open', side_effect=lambda path, *a, **kw: real_open(str(self.root) if path == '/config' else path, *a, **kw))
        self.stat = patch.object(reader.os, 'stat', side_effect=lambda path, *a, **kw: real_stat(str(self.root) if path == '/config' else path, *a, **kw))
        self.open.start(); self.stat.start()
        self.addCleanup(self.open.stop); self.addCleanup(self.stat.stop); self.addCleanup(self.tmp.cleanup)
        self.vfs = patch.object(reader.os, 'fstatvfs', return_value=SimpleNamespace(f_flag=os.ST_RDONLY))
        self.vfs.start(); self.addCleanup(self.vfs.stop)

    def read(self, digest=None, path='/config/runtime.json'):
        return reader.projected_config_bytes(path, digest or sha(self.raw))

    def test_exact_projection_reads_expected_bytes(self):
        self.assertEqual(self.read(), self.raw)

    def test_only_exact_config_path_is_allowed(self):
        for path in ('/config/other.json', '/other/runtime.json', '/config/../config/runtime.json'):
            with self.subTest(path=path), self.assertRaises(ValueError): self.read(path=path)

    def test_checksum_required(self):
        with self.assertRaises(ValueError): self.read('0' * 64)

    def test_writable_filesystem_denied(self):
        with patch.object(reader.os, 'fstatvfs', return_value=SimpleNamespace(f_flag=0)), self.assertRaises(ValueError): self.read()

    def test_runtime_link_must_be_exact(self):
        (self.root / 'runtime.json').unlink()
        for target in (TARGET + '/runtime.json', '/outside/runtime.json', '../runtime.json'):
            (self.root / 'runtime.json').symlink_to(target)
            with self.subTest(target=target), self.assertRaises(ValueError): self.read()
            (self.root / 'runtime.json').unlink()

    def test_regular_runtime_entry_denied(self):
        (self.root / 'runtime.json').unlink(); (self.root / 'runtime.json').write_bytes(self.raw)
        with self.assertRaises(ValueError): self.read()

    def test_data_link_must_be_bounded_timestamp_component(self):
        (self.root / '..data').unlink()
        for target in ('../outside', '/outside', 'plain', TARGET + '/extra', '..2026_10_09_21_22_01.' + '1' * 100):
            (self.root / '..data').symlink_to(target)
            with self.subTest(target=target), self.assertRaises(ValueError): self.read()
            (self.root / '..data').unlink()

    def test_regular_data_entry_denied(self):
        (self.root / '..data').unlink(); (self.root / '..data').mkdir()
        with self.assertRaises(ValueError): self.read()

    def test_timestamp_directory_symlink_denied(self):
        self.directory.rename(self.root / 'elsewhere'); self.directory.symlink_to('elsewhere')
        with self.assertRaises(OSError): self.read()

    def test_real_file_symlink_denied(self):
        (self.directory / 'runtime.json').unlink(); (self.directory / 'elsewhere').write_bytes(self.raw)
        (self.directory / 'runtime.json').symlink_to('elsewhere')
        with self.assertRaises(OSError): self.read()

    def test_nonregular_real_file_is_opened_nonblocking_and_denied(self):
        file = self.directory / 'runtime.json'; file.unlink(); os.mkfifo(file)
        original = reader.os.open
        def check_flags(path, flags, **kwargs):
            if path == 'runtime.json': self.assertTrue(flags & os.O_NONBLOCK)
            return original(path, flags, **kwargs)
        with patch.object(reader.os, 'open', side_effect=check_flags), self.assertRaises(ValueError): self.read()

    def test_empty_and_oversize_file_denied(self):
        file = self.directory / 'runtime.json'; file.write_bytes(b'')
        with self.assertRaises(ValueError): self.read()
        file.write_bytes(self.raw)
        with patch.object(reader, 'MAX_BYTES', len(self.raw) - 1), self.assertRaises(ValueError): self.read()

    def test_data_rotation_during_read_denied(self):
        original = reader.os.read
        other = self.root / '..2026_10_09_21_22_02.1234567890'; other.mkdir(); (other / 'runtime.json').write_bytes(self.raw)
        def rotate(fd, size):
            raw = original(fd, size)
            if (self.root / '..data').readlink() == Path(TARGET):
                (self.root / '..data').unlink(); (self.root / '..data').symlink_to(other.name)
            return raw
        with patch.object(reader.os, 'read', side_effect=rotate), self.assertRaises(ValueError): self.read()

    def test_real_file_replacement_during_read_denied(self):
        original = reader.os.read; replaced = False
        def replace(fd, size):
            nonlocal replaced
            raw = original(fd, size)
            if not replaced:
                replaced = True
                file = self.directory / 'runtime.json'; file.unlink(); file.write_bytes(self.raw)
            return raw
        with patch.object(reader.os, 'read', side_effect=replace), self.assertRaises(ValueError): self.read()

    def test_regular_module_reader_still_denies_symlinks(self):
        real = self.root / 'module.py'; real.write_bytes(b'pass\n'); link = self.root / 'alias.py'; link.symlink_to('module.py')
        with self.assertRaises(OSError): reader.file_bytes(link, sha(real.read_bytes()))

    def test_genuine_configured_store_remains_readonly(self):
        from cps_compute.internal import ControlStore, ServiceIdentity
        from cps_compute.reservations import Reservations
        import cps_compute.internal as internal
        import cps_compute.runtime as runtime
        db = self.root / 'control.sqlite'; store = ControlStore(db); reservations = Reservations(self.root / 'reservations.sqlite')
        expected = {'workspace':'native-group-b','owner':'neutral','server':'rtc','members':['p'], 'principal':'workspace:cps:native-group-b','profiles':['interactive-native-pilot-5'],'policy_hash':'old','storage':{'path':'/unchanged','state':'active'}}
        store.put_workspace(expected, ServiceIdentity('cps','cps'), reservations)
        raw = json.dumps({'state_directory':str(self.root)}).encode(); (self.directory / 'runtime.json').write_bytes(raw)
        info = db.stat(); before = sha(db.read_bytes())
        request = {'source':'cps','workspace':'native-group-b','config_path':'/config/runtime.json','config_sha256':sha(raw),'internal_sha256':sha(Path(internal.__file__).read_bytes()),'runtime_sha256':sha(Path(runtime.__file__).read_bytes()),'database_path':str(db),'database_device':info.st_dev,'database_inode':info.st_ino,'database_uid':info.st_uid}
        with patch.dict(os.environ, {'CPS_COMPUTE_CONFIG':'/config/runtime.json'}): self.assertEqual(reader.read_registration(request), expected)
        self.assertEqual(sha(db.read_bytes()), before)
        with patch.dict(os.environ, {'CPS_COMPUTE_CONFIG':'/config/runtime.json'}), self.assertRaises(ValueError): reader.read_registration({**request, 'extra':True})
        self.assertEqual(sha(db.read_bytes()), before)


class ContractTests(unittest.TestCase):
    def test_closed_request_and_released_sql_logic_unchanged(self):
        original = ast.parse(ORIGINAL.read_bytes()); current = ast.parse(Path(reader.__file__).read_bytes())
        old = next(n for n in original.body if isinstance(n, ast.FunctionDef) and n.name == 'read_registration')
        new = next(n for n in current.body if isinstance(n, ast.FunctionDef) and n.name == 'read_registration')
        calls = [n for n in ast.walk(new) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'projected_config_bytes']
        self.assertEqual(len(calls), 1); calls[0].func.id = 'file_bytes'
        self.assertEqual(ast.dump(old), ast.dump(new))

    def test_default_entrypoint_is_inert(self):
        result = subprocess.run([sys.executable, reader.__file__], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0); self.assertIn('inert', result.stderr)


if __name__ == '__main__': unittest.main()
