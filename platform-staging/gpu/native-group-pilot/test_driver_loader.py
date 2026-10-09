import hashlib
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


class LoaderTest(unittest.TestCase):
    def setUp(self):
        if not (HERE / 'driver_loader.py').exists(): self.fail('Exact driver loader implementation is missing')
        self.loader = importlib.import_module('driver_loader')

    def test_default_cli_has_no_module_path_or_process_access(self):
        with patch.object(self.loader, 'perform_load', side_effect=AssertionError('module operation')):
            self.loader.main([])

    def test_exact_open_fd_survives_path_replacement_and_insmod_inherits_fd(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as temporary:
            folder = Path(temporary) / 'inputs'; folder.mkdir(mode=0o700)
            path = folder / 'nvidia.ko'; path.write_bytes(b'\x7fELFexact-input'); path.chmod(0o400)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            fd, original = self.loader.protected_input(path, digest, trusted_uid=os.getuid())
            try:
                folder.rename(Path(temporary) / 'original-inputs')
                folder.mkdir(mode=0o700)
                path.write_bytes(b'\x7fELFsubstitution'); path.chmod(0o400)
                calls = []
                def runner(argv, **kwargs):
                    self.assertEqual(kwargs['pass_fds'], (fd,))
                    self.assertEqual(Path(argv[1]).read_bytes(), b'\x7fELFexact-input')
                    calls.append(argv)
                    return type('Result', (), {'returncode': 0})()
                self.loader.insmod_fd(fd, original, ['NVreg_CpsNativeImportGuard=1'], runner=runner)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0][1], '/proc/self/fd/' + str(fd))
            finally: os.close(fd)

    def test_wrong_hash_writable_nonelf_and_symlink_inputs_block(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as temporary:
            path = Path(temporary) / 'nvidia.ko'; path.write_bytes(b'\x7fELFinput'); path.chmod(0o400)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(ValueError): self.loader.protected_input(path, 'a' * 64, trusted_uid=os.getuid())
            path.chmod(0o666)
            with self.assertRaises(ValueError): self.loader.protected_input(path, digest, trusted_uid=os.getuid())
            path.chmod(0o400); link = path.with_suffix('.link'); link.symlink_to(path)
            with self.assertRaises((ValueError, OSError)): self.loader.protected_input(link, digest, trusted_uid=os.getuid())
            path.unlink(); path.write_bytes(b'not ELF'); path.chmod(0o400)
            with self.assertRaises(ValueError): self.loader.protected_input(path, hashlib.sha256(path.read_bytes()).hexdigest(), trusted_uid=os.getuid())

    def test_in_place_input_mutation_blocks_insmod(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as temporary:
            path = Path(temporary) / 'nvidia.ko'; path.write_bytes(b'\x7fELFinput'); path.chmod(0o400)
            fd, original = self.loader.protected_input(path, hashlib.sha256(path.read_bytes()).hexdigest(), trusted_uid=os.getuid())
            try:
                path.chmod(0o600); path.write_bytes(b'\x7fELFmutate')
                with self.assertRaises(ValueError): self.loader.insmod_fd(fd, original, [], runner=lambda *a, **k: self.fail('Executed changed ELF'))
            finally: os.close(fd)

    def test_existing_nvidia_module_blocks_load(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as temporary:
            path = Path(temporary); (path / 'nvidia').mkdir()
            with self.assertRaises(ValueError): self.loader.require_modules_absent(path, proc_modules='')
            (path / 'nvidia').rmdir()
            with self.assertRaises(ValueError): self.loader.require_modules_absent(path, proc_modules='nvidia_uvm 1 0 - Live 0x0\n')
            self.loader.require_modules_absent(path, proc_modules='other_module 1 0 - Live 0x0\n')

    def test_closed_manifest_matches_shared_health_schema(self):
        snapshot = json.loads((HERE / 'source-snapshot.json').read_text())['sources']['native_gpu_health.py']
        health = self.loader.load_source(snapshot.encode())
        identities = {name: {'sysfs_device': 1, 'sysfs_inode': 100 + i} for i, name in enumerate(health.MODULE_BUILDS)}
        manifest = self.loader.build_manifest(health, identities, boot_id='11111111-1111-4111-8111-111111111111',
            generation='22222222-2222-4222-8222-222222222222', kernel_release='test-kernel')
        health.validate_load_manifest(manifest, boot_id=manifest['boot_id'], driver_generation=manifest['driver_generation'], kernel_release='test-kernel')
        self.assertEqual(set(manifest), {'protocol', 'boot_id', 'driver_generation', 'kernel_release', 'driver_version', 'modules'})
        manifest['modules']['nvidia']['elf_sha256'] = '0' * 64
        with self.assertRaises(ValueError): health.validate_load_manifest(manifest, boot_id=manifest['boot_id'], driver_generation=manifest['driver_generation'], kernel_release='test-kernel')

    def test_authority_publication_modes_no_overwrite_and_invalidation(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as temporary:
            authority = Path(temporary); authority.chmod(0o700)
            self.loader.write_authority(authority, {'protocol': 'fixture'}, 'epoch', trusted_uid=os.getuid())
            self.assertEqual((authority / 'driver-generation').stat().st_mode & 0o777, 0o600)
            self.assertEqual((authority / 'driver-load-manifest.json').stat().st_mode & 0o777, 0o400)
            with self.assertRaises(FileExistsError): self.loader.write_authority(authority, {}, 'other', trusted_uid=os.getuid())
            self.loader.invalidate_authority(authority, trusted_uid=os.getuid())
            self.assertFalse((authority / 'driver-generation').exists())
            self.assertFalse((authority / 'driver-load-manifest.json').exists())

if __name__ == '__main__': unittest.main()
