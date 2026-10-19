#!/usr/bin/env python3
"""Build/test the disabled KAI staging patch in a new private upstream checkout."""
import argparse
import hashlib
import json
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent
UPSTREAM = 'https://github.com/kai-scheduler/KAI-Scheduler.git'
COMMIT = 'bdf434e5e9201cccf4e05fad04d814363653f692'
GO_VERSION = 'go1.26.8'
PATCH_SHA256 = 'ab6717f5af2a42f87923e19e220d1463dbe74b82520a1fbd59d8dca121f4b983'
TOOLCHAIN_SHA256 = 'd0f743b33e8d8945e6b1f432edd15785c70507121d6e2a723b21285eddf8b57b'
PACKAGES = ('./pkg/binder/binding', './pkg/binder/plugins/hamicore', './pkg/binder/binding/resourcereservation', './pkg/binder/controllers', './cmd/binder/app')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(arguments, directory):
    return subprocess.run(arguments, cwd=directory, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout


def load_manifest(*, patch=None):
    manifest = json.loads((ROOT / 'source-manifest.json').read_text())
    patch = ROOT / 'terminal-guard.patch' if patch is None else patch
    if (manifest['upstream_url'], manifest['upstream_commit'], manifest['go_version'],
        manifest['patch_sha256'], sha(patch)) != (UPSTREAM, COMMIT, GO_VERSION, PATCH_SHA256, PATCH_SHA256):
        raise ValueError('Frozen source/patch provenance differs')
    if len(manifest['files']) != 15 or len({r['path'] for r in manifest['files']}) != 15:
        raise ValueError('Exact fifteen source paths required')
    for row in manifest['files']:
        path = pathlib.PurePosixPath(row['path'])
        if path.is_absolute() or '..' in path.parts or str(path) != row['path']:
            raise ValueError('Canonical relative source path required')
    return manifest, patch


def verify_files(directory, manifest, *, patched=False):
    for row in manifest['files']:
        path = directory / row['path']
        expected = row['patched_sha256'] if patched else row['original_sha256']
        if expected is None:
            if path.exists() or path.is_symlink():
                raise ValueError('New patch file unexpectedly exists upstream')
        elif path.is_symlink() or not path.is_file() or sha(path) != expected:
            raise ValueError('Pinned source bytes differ: ' + row['path'])
        elif patched and path.stat().st_size != row['patched_bytes']:
            raise ValueError('Patched source size differs')
    for filename, key in (('go.mod', 'go_mod_sha256'), ('go.sum', 'go_sum_sha256')):
        if (directory / filename).is_symlink() or sha(directory / filename) != manifest[key]:
            raise ValueError('Pinned dependency files differ')


def verify_checkout(source, manifest):
    if run(['git', 'rev-parse', 'HEAD'], source).strip() != manifest['upstream_commit']:
        raise ValueError('Exact upstream HEAD required')
    if run(['git', 'status', '--porcelain', '--untracked-files=all', '--ignored'], source).strip():
        raise ValueError('Clean upstream checkout required, including ignored/untracked files')
    verify_files(source, manifest)


def prepare(source, directory, manifest, patch):
    source = source.resolve(strict=True)
    if source == directory.resolve() or source in directory.resolve().parents:
        raise ValueError('Output must remain outside the read-only source checkout')
    if directory.exists() or directory.is_symlink():
        raise ValueError('New output directory required; existing checkouts are never changed')
    verify_checkout(source, manifest)
    directory = directory.absolute()
    directory.parent.mkdir(parents=True, exist_ok=True)
    run(['git', 'clone', '--no-hardlinks', '--no-checkout', str(source), str(directory)], source)
    os.chmod(directory, 0o700)
    run(['git', 'checkout', '--detach', manifest['upstream_commit']], directory)
    verify_checkout(directory, manifest)
    # Whole-file preimage hashes eliminate offset/fuzz acceptance before git apply.
    run(['git', 'apply', '--check', '--index', '--whitespace=error-all', str(patch.resolve())], directory)
    run(['git', 'apply', '--index', '--whitespace=error-all', str(patch.resolve())], directory)
    verify_files(directory, manifest, patched=True)
    actual = set(run(['git', 'diff', '--name-only', 'HEAD'], directory).splitlines())
    if actual != {row['path'] for row in manifest['files']}:
        raise ValueError('Unexpected patched file set')
    verify_checkout(source, manifest)
    return directory


def verify_static_elf(path):
    """Require a Linux AMD64 ELF executable with no runtime interpreter."""
    import struct
    with path.open('rb') as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:7] != b'\x7fELF\x02\x01\x01':
            raise ValueError('ELF64 little-endian executable required')
        kind, machine = struct.unpack_from('<HH', header, 16)
        offset = struct.unpack_from('<Q', header, 32)[0]
        size, count = struct.unpack_from('<HH', header, 54)
        if kind not in (2, 3) or machine != 62 or size != 56 or not 1 <= count <= 128 or not struct.unpack_from('<Q', header, 24)[0]:
            raise ValueError('Bounded Linux AMD64 ELF executable headers required')
        if offset < 64 or offset + size * count > path.stat().st_size:
            raise ValueError('Truncated ELF program headers')
        stream.seek(offset)
        programs = stream.read(size * count)
    types = [struct.unpack_from('<I', programs, i * size)[0] for i in range(count)]
    if 3 in types:
        raise ValueError('Static ELF must have no PT_INTERP runtime interpreter')
    if 1 not in types:
        raise ValueError('ELF loadable segment required')
    return {'format':'ELF64-LSB-AMD64', 'program_headers':count, 'PT_INTERP':False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true', help='Explicit offline local test/static build')
    parser.add_argument('--source', type=pathlib.Path, help='Clean local upstream checkout, read only')
    parser.add_argument('--output', type=pathlib.Path, help='New private clone/build directory')
    parser.add_argument('--toolchain-archive', type=pathlib.Path, help='Pinned Go Linux AMD64 tar.gz')
    args = parser.parse_args(argv)
    if not args.build:
        print(json.dumps({'mode':'inert', 'upstream_commit':COMMIT, 'live_operations':False}))
        return 0
    if not all((args.source, args.output, args.toolchain_archive)):
        raise ValueError('Explicit source/output/toolchain archive required')
    manifest, patch = load_manifest()
    if sha(args.toolchain_archive) != TOOLCHAIN_SHA256:
        raise ValueError('Pinned toolchain archive differs')
    directory = prepare(args.source, args.output, manifest, patch)
    import tarfile
    toolchain = directory / '.toolchain'
    toolchain.mkdir(mode=0o700)
    with tarfile.open(args.toolchain_archive, 'r:gz') as archive:
        archive.extractall(toolchain, filter='data')
    go = toolchain / 'go/bin/go'
    if run([str(go), 'version'], directory).split()[2] != GO_VERSION:
        raise ValueError('Pinned Go toolchain version differs')
    env = dict(os.environ, GOMAXPROCS='4', CGO_ENABLED='0', GOTOOLCHAIN='local',
               GOPROXY='off', GOSUMDB='off', GOWORK='off', GOENV='off', GOFLAGS='-mod=readonly')
    # Ignore caller compiler/architecture flags; this recipe is Linux AMD64 only.
    for key in ('GOROOT', 'GOEXPERIMENT', 'GODEBUG', 'GOCACHEPROG', 'GOTOOLDIR', 'GO_EXTLINK_ENABLED'):
        env.pop(key, None)
    env.update(GOOS='linux', GOARCH='amd64', GOAMD64='v1')
    logs = []
    def go_run(arguments):
        result = subprocess.run([str(go), *arguments], cwd=directory, env=env,
            check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1200)
        logs.append(result.stdout)
        return result.stdout
    go_run(['test', '-p', '2', *PACKAGES, '-count=1'])
    outputs = []
    for name in ('binder', 'binder.rebuild'):
        output = directory / name
        go_run(['build', '-p', '2', '-trimpath', '-buildvcs=false', '-ldflags=-buildid=',
                '-o', str(output), './cmd/binder'])
        outputs.append(sha(output))
    if outputs[0] != outputs[1]:
        raise ValueError('Repeated static build is not byte identical')
    verify_files(directory, manifest, patched=True)
    verify_checkout(args.source.resolve(), manifest)
    metadata = go_run(['version', '-m', str(directory / 'binder')])
    if 'CGO_ENABLED=0' not in metadata or 'GOARCH=amd64' not in metadata:
        raise ValueError('Static Linux AMD64 build metadata required')
    elf = verify_static_elf(directory / 'binder')
    receipt = {'static_elf':elf, 'upstream_commit':COMMIT, 'patch_sha256':PATCH_SHA256,
        'toolchain_sha256':TOOLCHAIN_SHA256, 'go_version':GO_VERSION,
        'source_files':manifest['files'], 'dependency_diff':[],
        'recipe_sha256':sha(ROOT/'recipe.py'), 'manifest_sha256':sha(ROOT/'source-manifest.json'),
        'all_affected_packages_passed':list(PACKAGES), 'binary_sha256':outputs[0],
        'binary_bytes':(directory/'binder').stat().st_size, 'rebuild_identical':True,
        'binary_go_metadata':metadata, 'CGO_ENABLED':0, 'GOMAXPROCS':4, 'go_parallelism':2,
        'application_contract_commit':manifest['current_group_contract_commit'],
        'live_operations':False, 'published':False, 'production_qualified':False}
    for name, value in [('recipe.log', ''.join(logs)), ('recipe-receipt.json', json.dumps(receipt, indent=2, sort_keys=True)+'\n')]:
        fd = os.open(directory / name, os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(value)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('source_files','binary_go_metadata')}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
