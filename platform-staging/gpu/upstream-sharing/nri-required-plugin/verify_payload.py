#!/usr/bin/env python3
"""Compare fresh candidate extraction with verified stock assets; fail closed."""
import hashlib
import json
import pathlib
import sys

stock, candidate, built = map(pathlib.Path, sys.argv[1:4])

def digest(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()

def inventory(root):
    result = {}
    for prefix in ('bin', 'etc'):
        for path in sorted((root / prefix).rglob('*')):
            name = str(path.relative_to(root))
            if path.is_symlink():
                result[name] = ['link', str(path.readlink())]
            elif path.is_file():
                result[name] = ['file', path.stat().st_mode & 0o7777, digest(path)]
            elif path.is_dir():
                result[name] = ['directory', path.stat().st_mode & 0o7777]
            else:
                raise AssertionError(f'Unexpected asset: {name}')
    return result

before, after = inventory(stock), inventory(candidate)
assert before.keys() == after.keys(), 'Asset inventory changed'
changed = [name for name in before if before[name] != after[name]]
assert set(changed) == {'bin/k3s', 'bin/.sha256sums'}, changed
assert digest(candidate / 'bin/k3s') == digest(built), 'Wrong rebuilt inner embedded'
for line in (candidate / 'bin/.sha256sums').read_text().splitlines():
    expected, name = line.split(maxsplit=1)
    path = pathlib.PurePosixPath(name)
    assert not path.is_absolute() and '..' not in path.parts
    assert digest(candidate / 'bin' / path) == expected, name
for line in (candidate / 'bin/.links').read_text().splitlines():
    name, target = line.split(maxsplit=1)
    assert str((candidate / 'bin' / name).readlink()) == target, name
print(json.dumps({'changed_assets': changed, 'asset_entries': len(before),
                  'inner_sha256': digest(built), 'stock_assets_preserved': True,
                  'checksums_and_links_valid': True}, indent=2))
