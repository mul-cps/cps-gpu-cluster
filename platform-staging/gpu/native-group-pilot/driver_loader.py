#!/usr/bin/env python3
"""Default-inert exact R615 loader; root manually quiesces GPU2 first.

Never unloads modules, resets a GPU, changes MIG, drains a node or reboots.
The firmware-r615-canary directory is retained for the stock R580 rollback.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import uuid

HEALTH_SHA256 = '52fdbdae3d5e2f66fd4653d94ef5a62f734e185fabec30450f4a1b70cfee7d67'
CORE_SHA256 = '4fdcafcdf7f57b9de81f56e8e17db06a91e27680c6a711f3888fd0b76da46421'
UVM_SHA256 = 'b2ae67722e9e21a70c319aeed2184f5b2d1f23b8e32dea00816cfd5cd2c3ee61'
MANIFEST = 'driver-load-manifest.json'
GENERATION = 'driver-generation'
CORE_PARAMETERS = ['NVreg_CpsNativeImportGuard=1', 'NVreg_GpuInitOnProbe=1']
UVM_PARAMETERS = ['uvm_deny_managed_mmap=1', 'uvm_disable_hmm=1', 'uvm_ats_mode=0',
                  'uvm_enable_builtin_tests=0', 'uvm_disable_sam_migration=1']
IDENTITY_FIELDS = ('st_dev', 'st_ino', 'st_uid', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns')


def require(condition, description):
    if not condition: raise ValueError(description)


def protected_directory(path, *, trusted_uid=0, private=False):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'Absolute protected path required')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd); fd = next_fd
            value = os.fstat(fd)
            require(value.st_uid in (0, trusted_uid) and not stat.S_IMODE(value.st_mode) & 0o022,
                    'Root protected directory chain required')
        value = os.fstat(fd)
        require(value.st_uid == trusted_uid and (not private or stat.S_IMODE(value.st_mode) == 0o700),
                'Owned root0700 authority required' if private else 'Owned protected directory required')
        return fd
    except BaseException:
        os.close(fd); raise


def protected_input(path, expected_sha256, *, trusted_uid=0, elf=True):
    """Hash one held root-protected FD; never resolve/reopen the module path."""
    path = Path(path)
    parent = protected_directory(path.parent, trusted_uid=trusted_uid)
    fd = None
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        value = os.fstat(fd)
        require(stat.S_ISREG(value.st_mode) and value.st_uid == trusted_uid and value.st_nlink == 1
                and not stat.S_IMODE(value.st_mode) & 0o022 and 0 < value.st_size <= 134217728,
                'Bounded single-link root-protected insmod input required')
        digest = hashlib.sha256(); total = 0; magic = b''
        while True:
            data = os.read(fd, 1048576)
            if not data: break
            if not magic: magic = data[:4]
            digest.update(data); total += len(data)
            require(total <= 134217728, 'Oversized exact module input')
        require(total == value.st_size and digest.hexdigest() == expected_sha256
                and (not elf or magic == b'\x7fELF'), 'Exact pinned ELF/source input required')
        require(all(getattr(value, field) == getattr(os.fstat(fd), field) for field in IDENTITY_FIELDS),
                'Module input changed while hashing')
        os.lseek(fd, 0, os.SEEK_SET)
        result = fd; fd = None
        return result, value
    finally:
        if fd is not None: os.close(fd)
        os.close(parent)


def insmod_fd(fd, original, parameters, *, runner=subprocess.run, binary='/usr/sbin/insmod'):
    require(all(getattr(original, field) == getattr(os.fstat(fd), field) for field in IDENTITY_FIELDS),
            'Pinned module input changed before insmod')
    result = runner([str(binary), '/proc/self/fd/' + str(fd), *parameters], pass_fds=(fd,),
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    check=False, timeout=60)
    require(result.returncode == 0, 'Pinned insmod failed; retain loaded modules for root recovery')
    require(all(getattr(original, field) == getattr(os.fstat(fd), field) for field in IDENTITY_FIELDS),
            'Pinned module input changed during insmod')


def load_source(raw):
    require(hashlib.sha256(raw).hexdigest() == HEALTH_SHA256, 'Shared health verifier source pin mismatch')
    spec = importlib.util.spec_from_loader('_native_loader_health', loader=None)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    exec(compile(raw, 'native_gpu_health.py', 'exec'), module.__dict__)
    return module


def load_health(path):
    fd, info = protected_input(path, HEALTH_SHA256, elf=False)
    try:
        raw = os.read(fd, info.st_size + 1)
        require(len(raw) == info.st_size, 'Exact health source required')
        return load_source(raw)
    finally: os.close(fd)


def require_modules_absent(module_directory='/sys/module', *, proc_modules=None):
    require(not any(name.startswith('nvidia') or name == 'nv_peer_mem' for name in os.listdir(module_directory)),
            'Every NVIDIA module must be absent before an exact load')
    if proc_modules is None:
        with open('/proc/modules') as stream: proc_modules = stream.read(1048577)
    require(len(proc_modules) <= 1048576 and not any(line.split()[0].startswith('nvidia')
            or line.split()[0] == 'nv_peer_mem' for line in proc_modules.splitlines() if line.split()),
            'Actual proc module state must contain no NVIDIA modules')


def inspect_loaded(health, module_directory='/sys/module'):
    expected = {'nvidia/version': health.DRIVER_VERSION, **health.GUARD_PARAMETERS,
                **{name + '/srcversion': build['srcversion'] for name, build in health.MODULE_BUILDS.items()}}
    for filename, value in expected.items():
        mode = 0o400 if filename == 'nvidia/parameters/NVreg_CpsNativeImportGuard' else None
        require(health._read_file(module_directory, filename, mode=mode).decode().strip() == value,
                'Exact loaded driver identity/guard flag required: ' + filename)
    root = health._directory(module_directory)
    identities = {}
    try:
        for name in health.MODULE_BUILDS:
            fd = health._directory(name, parent_fd=root)
            try:
                info = os.fstat(fd)
                identities[name] = {'sysfs_device': info.st_dev, 'sysfs_inode': info.st_ino}
            finally: os.close(fd)
    finally: os.close(root)
    return identities


def build_manifest(health, identities, *, boot_id, generation, kernel_release):
    manifest = {'protocol': health.PROTOCOL, 'boot_id': boot_id, 'driver_generation': generation,
                'kernel_release': kernel_release, 'driver_version': health.DRIVER_VERSION,
                'modules': {name: {**value, **identities[name]} for name, value in health.MODULE_BUILDS.items()}}
    health.validate_load_manifest(manifest, boot_id=boot_id, driver_generation=generation, kernel_release=kernel_release)
    return manifest


def write_authority(authority, manifest, generation, *, trusted_uid=0):
    fd = protected_directory(authority, trusted_uid=trusted_uid, private=True)
    try:
        # Manifest is inert until the final generation file is published.
        for name, data, mode in [(MANIFEST, (json.dumps(manifest, sort_keys=True, separators=(',', ':')) + '\n').encode(), 0o400),
                                 (GENERATION, (generation + '\n').encode(), 0o600)]:
            file_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=fd)
            try:
                os.fchmod(file_fd, mode)
                with os.fdopen(file_fd, 'wb', closefd=False) as stream:
                    stream.write(data); stream.flush(); os.fsync(file_fd)
            finally: os.close(file_fd)
        os.fsync(fd)
    finally: os.close(fd)


def invalidate_authority(authority, *, trusted_uid=0):
    fd = protected_directory(authority, trusted_uid=trusted_uid, private=True)
    try:
        # Remove the epoch first: gates fail closed before any maintenance begins.
        for name, mode in [(GENERATION, 0o600), (MANIFEST, 0o400)]:
            try:
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError: continue
            require(stat.S_ISREG(info.st_mode) and info.st_uid == trusted_uid and info.st_nlink == 1
                    and stat.S_IMODE(info.st_mode) == mode, 'Unsafe old load authority retained for root inspection')
            os.unlink(name, dir_fd=fd)
            os.fsync(fd)
    finally: os.close(fd)


def perform_load(args):
    require(os.geteuid() == 0 and args.quiesced_gpu2 and socket.gethostname() == 'k3s-wk-gpu2',
            'Explicit root manually quiesced GPU2 execution required')
    authority_fd = protected_directory(args.authority, private=True)
    lock = None; inputs = []
    try:
        lock = os.open('.driver-loader.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=authority_fd)
        info = os.fstat(lock)
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o600, 'Private root driver writer lock required')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.invalidate:
            invalidate_authority(args.authority)
            return {'state': 'load-authority-invalidated', 'gpu_calls': False, 'production_qualified': False}
        require_modules_absent()
        # Required for both the canary's firmware and the stock R580 rollback.
        firmware_fd = protected_directory(Path('/run/nvidia/firmware-r615-canary'))
        os.close(firmware_fd)
        health = load_health(args.health_module)
        for path, digest in [(args.core, CORE_SHA256), (args.uvm, UVM_SHA256)]:
            inputs.append(protected_input(path, digest))
        require_modules_absent()  # No driver owner may have raced preflight.
        invalidate_authority(args.authority)
        try:
            insmod_fd(*inputs[0], CORE_PARAMETERS)
            insmod_fd(*inputs[1], UVM_PARAMETERS)
            identities = inspect_loaded(health)
            boot_id = health._read_file('/proc/sys/kernel/random', 'boot_id').decode().strip()
            generation = str(uuid.uuid4())
            manifest = build_manifest(health, identities, boot_id=boot_id, generation=generation,
                                      kernel_release=os.uname().release)
            write_authority(args.authority, manifest, generation)
            require(health.validate_native_driver_health(authority_directory=str(args.authority)) == generation,
                    'Fresh shared-verifier load attestation failed')
        except BaseException:
            invalidate_authority(args.authority)
            raise
        return {'state': 'exact-driver-load-attested', 'driver_generation': generation,
                'manifest': manifest, 'production_qualified': False}
    finally:
        for fd, _ in inputs: os.close(fd)
        if lock is not None: os.close(lock)
        os.close(authority_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--quiesced-gpu2', action='store_true')
    parser.add_argument('--invalidate', action='store_true', help='Invalidate authority before root performs any maintenance')
    parser.add_argument('--authority', type=Path, default=Path('/run/cps-native-gpu/authority'))
    parser.add_argument('--core', type=Path, default=Path('/run/cps-native-gpu/driver-inputs/nvidia.ko'))
    parser.add_argument('--uvm', type=Path, default=Path('/run/cps-native-gpu/driver-inputs/nvidia-uvm.ko'))
    parser.add_argument('--health-module', type=Path, default=Path('/run/cps-native-gpu/driver-inputs/native_gpu_health.py'))
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({'state': 'inert', 'module_calls': False, 'gpu_calls': False, 'production_qualified': False}))
        return
    print(json.dumps(perform_load(args), sort_keys=True))


if __name__ == '__main__': main()
