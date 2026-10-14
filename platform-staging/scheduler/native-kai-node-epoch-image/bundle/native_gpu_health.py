"""Shared fail-closed, CPU-only attestation of an exact native driver load.

ELF hashes are the trusted root loader's statements about its exact insmod
inputs, corroborated by loaded source versions, module directory identities,
boot, kernel and maintenance generation. This reader cannot hash a loaded ELF.
Root maintenance must invalidate the generation before unloading any module.
"""
from __future__ import annotations

import json
import os
from pathlib import PurePosixPath
import stat
from typing import Any
import uuid


PROTOCOL = 'cps-native-driver-load/v1'
DRIVER_VERSION = '615.71.09'
AUTHORITY = '/run/cps-native-gpu/authority'
MANIFEST_NAME = 'driver-load-manifest.json'
MODULE_BUILDS = {
    'nvidia': {
        'elf_sha256': '4fdcafcdf7f57b9de81f56e8e17db06a91e27680c6a711f3888fd0b76da46421',
        'srcversion': '2F87172C8F45C13DCB1A7BA'},
    'nvidia_uvm': {
        'elf_sha256': 'b2ae67722e9e21a70c319aeed2184f5b2d1f23b8e32dea00816cfd5cd2c3ee61',
        'srcversion': '9353E234906B1910373B07A'},
}
GUARD_PARAMETERS = {
    'nvidia/parameters/NVreg_CpsNativeImportGuard': '1',
    'nvidia/parameters/NVreg_GpuInitOnProbe': '1',
    'nvidia_uvm/parameters/uvm_deny_managed_mmap': 'Y',
    'nvidia_uvm/parameters/uvm_disable_hmm': 'Y',
    'nvidia_uvm/parameters/uvm_ats_mode': '0',
    'nvidia_uvm/parameters/uvm_enable_builtin_tests': '0',
    'nvidia_uvm/parameters/uvm_disable_sam_migration': 'Y',
}
_MAX_RECORD = 16384


def _require(condition: bool, description: str) -> None:
    if not condition:
        raise ValueError(description)


def _canonical_uuid(value: Any) -> None:
    try:
        _require(isinstance(value, str) and str(uuid.UUID(value)) == value,
                 'Canonical native health UUID required')
    except (AttributeError, TypeError, ValueError):
        raise ValueError('Canonical native health UUID required') from None


def _directory(path: str, *, private: bool = False, parent_fd: int | None = None) -> int:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    try:
        info = os.fstat(fd)
        _require(info.st_uid == 0 and not stat.S_IMODE(info.st_mode) & 0o022,
                 'Protected root native health directory required')
        if private:
            _require(stat.S_IMODE(info.st_mode) == 0o700, 'Private root0700 authority required')
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read_file(directory: str, filename: str, *, mode: int | None = None,
               private_directory: bool = False) -> bytes:
    parts = PurePosixPath(filename).parts
    _require(parts and all(part not in ('/', '.', '..') for part in parts),
             'Relative native health file required')
    directory_fd = _directory(directory, private=private_directory)
    try:
        for part in parts[:-1]:
            next_fd = _directory(part, parent_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
        try:
            info = os.fstat(fd)
            _require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
                     and not stat.S_IMODE(info.st_mode) & 0o022 and info.st_size <= _MAX_RECORD,
                     'Protected bounded root native health file required: ' + filename)
            if mode is not None:
                _require(stat.S_IMODE(info.st_mode) == mode,
                         'Exact native health file mode required: ' + filename)
            data = os.read(fd, _MAX_RECORD + 1)
            _require(len(data) <= _MAX_RECORD, 'Oversized native health record')
            after = os.fstat(fd)
            _require(all(getattr(info, key) == getattr(after, key) for key in
                         ('st_dev', 'st_ino', 'st_uid', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns')),
                     'Native health record changed while reading')
            return data
        finally:
            os.close(fd)
    finally:
        os.close(directory_fd)


def _closed(value: Any, keys: set[str], description: str) -> None:
    _require(isinstance(value, dict) and set(value) == keys, description)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        _require(key not in result, 'Duplicate native load manifest field')
        result[key] = value
    return result


def validate_load_manifest(manifest: Any, *, boot_id: str, driver_generation: str,
                           kernel_release: str) -> None:
    """Validate the loader's closed exact-build schema against current authority."""
    _canonical_uuid(boot_id)
    _canonical_uuid(driver_generation)
    _closed(manifest, {'protocol', 'boot_id', 'driver_generation', 'kernel_release',
                      'driver_version', 'modules'}, 'Closed native load manifest required')
    _require(manifest['protocol'] == PROTOCOL and manifest['boot_id'] == boot_id
             and manifest['driver_generation'] == driver_generation
             and manifest['kernel_release'] == kernel_release
             and manifest['driver_version'] == DRIVER_VERSION,
             'Native load manifest boot/kernel/driver/generation mismatch')
    _closed(manifest['modules'], set(MODULE_BUILDS), 'Exact core and UVM load records required')
    for name, expected in MODULE_BUILDS.items():
        record = manifest['modules'][name]
        _closed(record, {'elf_sha256', 'srcversion', 'sysfs_device', 'sysfs_inode'},
                'Closed native module load record required')
        _require(all(record[key] == value for key, value in expected.items()),
                 'Exact native loaded build required: ' + name)
        _require(type(record['sysfs_device']) is int and record['sysfs_device'] >= 0
                 and type(record['sysfs_inode']) is int and record['sysfs_inode'] > 0,
                 'Exact loaded module directory identity required')


def validate_native_driver_health(module_directory: str = '/sys/module', *,
                                  authority_directory: str = AUTHORITY,
                                  boot_id: str | None = None) -> str:
    """Verify protected load authority and current kernel state; return its epoch."""
    if boot_id is None:
        boot_id = _read_file('/proc/sys/kernel/random', 'boot_id').decode().strip()
    generation = _read_file(authority_directory, 'driver-generation', mode=0o600,
                            private_directory=True).decode().strip()
    raw = _read_file(authority_directory, MANIFEST_NAME, mode=0o400, private_directory=True)
    manifest = json.loads(raw, object_pairs_hook=_unique_object)
    validate_load_manifest(manifest, boot_id=boot_id, driver_generation=generation,
                           kernel_release=os.uname().release)
    expected_files = {'nvidia/version': DRIVER_VERSION, **GUARD_PARAMETERS,
                      **{name + '/srcversion': build['srcversion'] for name, build in MODULE_BUILDS.items()}}
    for name, value in expected_files.items():
        mode = 0o400 if name == 'nvidia/parameters/NVreg_CpsNativeImportGuard' else None
        _require(_read_file(module_directory, name, mode=mode).decode().strip() == value,
                 'Native GPU kernel guard/driver health mismatch: ' + name)
    root_fd = _directory(module_directory)
    try:
        for name in MODULE_BUILDS:
            fd = _directory(name, parent_fd=root_fd)
            try:
                info = os.fstat(fd)
                record = manifest['modules'][name]
                _require((info.st_dev, info.st_ino) == (record['sysfs_device'], record['sysfs_inode']),
                         'Native loaded module instance health mismatch: ' + name)
            finally:
                os.close(fd)
    finally:
        os.close(root_fd)
    _require(_read_file(authority_directory, 'driver-generation', mode=0o600,
                        private_directory=True).decode().strip() == generation,
             'Native driver generation changed while checking health')
    return generation
