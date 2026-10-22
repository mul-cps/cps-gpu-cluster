import hashlib
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def kernel147_health_fixture():
    historical = json.loads((HERE / 'source-snapshot.json').read_text())['sources']['native_gpu_health.py'].encode()
    candidate = historical.replace(
        b'4fdcafcdf7f57b9de81f56e8e17db06a91e27680c6a711f3888fd0b76da46421',
        b'24b83a0ed1c676fccee3eb3d558d32b407a32f5ebd3e4a979bf468ac405e852c').replace(
        b'b2ae67722e9e21a70c319aeed2184f5b2d1f23b8e32dea00816cfd5cd2c3ee61',
        b'0ff0de040dc840fb3f08ce6d289de032b7952774827064dbabe050c01a70a39b')
    return historical, candidate


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
                self.loader.insmod_fd(fd, original, self.loader.CORE_PARAMETERS, runner=runner)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0][1], '/proc/self/fd/' + str(fd))
                self.assertEqual(calls[0][2:], ['NVreg_CpsNativeImportGuard=1', 'NVreg_GpuInitOnProbe=1'])
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
        _, candidate = kernel147_health_fixture()
        health = self.loader.load_source(candidate)
        identities = {name: {'sysfs_device': 1, 'sysfs_inode': 100 + i} for i, name in enumerate(health.MODULE_BUILDS)}
        manifest = self.loader.build_manifest(health, identities, boot_id='11111111-1111-4111-8111-111111111111',
            generation='22222222-2222-4222-8222-222222222222', kernel_release='test-kernel')
        health.validate_load_manifest(manifest, boot_id=manifest['boot_id'], driver_generation=manifest['driver_generation'], kernel_release='test-kernel')
        self.assertEqual(set(manifest), {'protocol', 'boot_id', 'driver_generation', 'kernel_release', 'driver_version', 'modules'})
        manifest['modules']['nvidia']['elf_sha256'] = '0' * 64
        with self.assertRaises(ValueError): health.validate_load_manifest(manifest, boot_id=manifest['boot_id'], driver_generation=manifest['driver_generation'], kernel_release='test-kernel')

    def test_147_health_source_is_accepted_and_historical_134_source_denied(self):
        historical, candidate = kernel147_health_fixture()
        with tempfile.TemporaryDirectory(dir=Path.home()) as temporary:
            path = Path(temporary) / 'health.py'; path.write_bytes(candidate); path.chmod(0o400)
            fd, _ = self.loader.protected_input(path, self.loader.HEALTH_SHA256, trusted_uid=os.getuid(), elf=False)
            try: health = self.loader.load_source(os.read(fd, 65536))
            finally: os.close(fd)
            for name, digest in (('nvidia', self.loader.CORE_SHA256), ('nvidia_uvm', self.loader.UVM_SHA256)):
                self.assertEqual(health.MODULE_BUILDS[name]['elf_sha256'], digest)
            path.chmod(0o600); path.write_bytes(historical); path.chmod(0o400)
            with self.assertRaises(ValueError):
                self.loader.protected_input(path, self.loader.HEALTH_SHA256, trusted_uid=os.getuid(), elf=False)

    def test_wrong_kernel_denied_before_any_authority_or_module_access(self):
        from types import SimpleNamespace
        with patch.object(self.loader.os, 'geteuid', return_value=0), \
             patch.object(self.loader.socket, 'gethostname', return_value='k3s-wk-gpu2'), \
             patch.object(self.loader.os, 'uname', return_value=SimpleNamespace(release='6.8.0-134-generic')), \
             patch.object(self.loader, 'protected_directory', side_effect=AssertionError('Accessed authority before kernel rejection')):
            with self.assertRaisesRegex(ValueError, 'kernel'):
                self.loader.main(["--execute", "--quiesced-gpu2", "--authority", "/unused"])

    def test_147_load_and_wrong_kernel_invalidation_reach_protected_preflight(self):
        from types import SimpleNamespace
        class ProtectedPreflight(Exception): pass
        for release, invalidate in [('6.8.0-147-generic', False), ('6.8.0-134-generic', True)]:
            with self.subTest(release=release, invalidate=invalidate), \
                 patch.object(self.loader.os, 'geteuid', return_value=0), \
                 patch.object(self.loader.socket, 'gethostname', return_value='k3s-wk-gpu2'), \
                 patch.object(self.loader.os, 'uname', return_value=SimpleNamespace(release=release)), \
                 patch.object(self.loader, 'protected_directory', side_effect=ProtectedPreflight):
                with self.assertRaises(ProtectedPreflight):
                    self.loader.main(['--execute', '--quiesced-gpu2', '--authority', '/unused'] + (['--invalidate'] if invalidate else []))

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
