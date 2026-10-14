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
PACKAGES = ('./pkg/binder/binding', './pkg/binder/binding/resourcereservation', './pkg/binder/controllers', './cmd/binder/app')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(arguments, directory):
    return subprocess.run(arguments, cwd=directory, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', type=pathlib.Path, help='NEW private upstream checkout directory')
    parser.add_argument('--go-bin', type=pathlib.Path)
    parser.add_argument('--test', action='store_true')
    parser.add_argument('--build', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'source-manifest.json').read_text())
    patch = ROOT / 'terminal-guard.patch'
    if (manifest['upstream_url'], manifest['upstream_commit'], manifest['go_version'], manifest['patch_sha256']) != (UPSTREAM, COMMIT, GO_VERSION, sha(patch)):
        raise ValueError('Frozen source/patch provenance differs')
    if args.prepare is None:
        if args.test or args.build or args.go_bin:
            raise ValueError('Testing/building requires a new preparation directory')
        print(json.dumps({'mode': 'inert', 'upstream_commit': COMMIT,
            'patch_sha256': sha(patch), 'coordinator_installed': False,
            'live_operations': False}, sort_keys=True))
        return
    if args.prepare.exists() or args.prepare.is_symlink():
        raise ValueError('New output directory required; existing checkouts are never changed')
    if (args.test or args.build) and not args.go_bin:
        raise ValueError('Explicit verified Go toolchain path required')
    if args.go_bin:
        version = subprocess.check_output([str(args.go_bin), 'version'], text=True).split()
        if version[2] != GO_VERSION:
            raise ValueError('Exact upstream Go1.26.8 toolchain required')
    directory = args.prepare.resolve()
    directory.mkdir(mode=0o700)
    logs = []
    logs.append(run(['git', 'init'], directory))
    run(['git', 'remote', 'add', 'origin', UPSTREAM], directory)
    logs.append(run(['git', 'fetch', '--depth=1', 'origin', COMMIT], directory))
    logs.append(run(['git', 'checkout', '--detach', COMMIT], directory))
    if run(['git', 'rev-parse', 'HEAD'], directory).strip() != COMMIT:
        raise ValueError('Upstream Git pin differs')
    for row in manifest['files']:
        path = directory / row['path']
        if row['original_sha256'] is None:
            if path.exists():
                raise ValueError('New patch file unexpectedly exists upstream')
        elif sha(path) != row['original_sha256']:
            raise ValueError('Pinned upstream source bytes differ')
    if sha(directory / 'go.mod') != manifest['go_mod_sha256'] or sha(directory / 'go.sum') != manifest['go_sum_sha256']:
        raise ValueError('Pinned dependency files differ')
    run(['git', 'apply', '--check', '--whitespace=error-all', str(patch)], directory)
    run(['git', 'apply', '--whitespace=error-all', str(patch)], directory)
    for row in manifest['files']:
        if sha(directory / row['path']) != row['patched_sha256']:
            raise ValueError('Applied patch source bytes differ')
    receipt = {'upstream_commit': COMMIT, 'patch_sha256': sha(patch),
        'sdk_contract_commit': manifest['sdk_commit'], 'dependency_diff': [],
        'live_operations': False, 'coordinator_installed': False, 'route_qualified': False}
    if 'coordinator_source_commit' in manifest:
        receipt['coordinator_source_commit'] = manifest['coordinator_source_commit']
        receipt['sdk_profile_correction_commit'] = manifest['sdk_profile_correction_commit']
    if args.test:
        logs.append(run([str(args.go_bin), 'test', '-p', '2', *PACKAGES, '-count=1'], directory))
        receipt['all_affected_packages_passed'] = list(PACKAGES)
    if args.build:
        output = directory / 'binder'
        logs.append(run([str(args.go_bin), 'build', '-p', '2', '-o', str(output), './cmd/binder'], directory))
        receipt['binary_sha256'] = sha(output)
        receipt['binary_bytes'] = output.stat().st_size
        receipt['binary_go_metadata'] = run([str(args.go_bin), 'version', '-m', str(output)], directory)
    if sha(directory / 'go.mod') != manifest['go_mod_sha256'] or sha(directory / 'go.sum') != manifest['go_sum_sha256']:
        raise ValueError('Build/test changed pinned dependency files')
    for name, value in (('recipe-receipt.json', json.dumps(receipt, sort_keys=True, indent=2) + '\n'),
                        ('recipe.log', ''.join(logs))):
        path = directory / name
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(value)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
