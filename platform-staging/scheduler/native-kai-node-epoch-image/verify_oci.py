#!/usr/bin/env python3
"""Verify downloaded OCI closure and the one sixteen-file additive layer."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

BASE = 'sha256:5079458fe0fcb3c11231b21f1bbc1f4c12ad3ac578799932aa0bc9f46d5510c7'
CONFIG = 'sha256:88b67945c3f182cfc230c60463a08edf105e72ccc16902be1f6f637b0837e332'


def require(ok, text):
    if not ok:
        raise ValueError(text)


def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def closure(directory, expected):
    directory = Path(directory)
    index = json.loads((directory / 'index.json').read_bytes())
    require(len(index['manifests']) == 1, 'Exactly one immutable image required')
    descriptor = index['manifests'][0]
    require(descriptor['digest'] == expected, 'Registry manifest digest changed')
    receipts = []

    def blob(desc):
        require(not desc.get('urls') and desc['digest'].startswith('sha256:'), 'Local SHA256 blob required')
        raw = (directory / 'blobs' / 'sha256' / desc['digest'].split(':')[1]).read_bytes()
        require(len(raw) == desc['size'] and sha(raw) == desc['digest'], 'Blob size or SHA256 mismatch')
        receipts.append({'digest': desc['digest'], 'size': len(raw), 'mediaType': desc['mediaType']})
        return raw

    manifest = json.loads(blob(descriptor))
    require(manifest['schemaVersion'] == 2 and 'layers' in manifest and 'config' in manifest,
            'A single image manifest, not an unresolved index, is required')
    config = json.loads(blob(manifest['config']))
    require(config['os'] == 'linux' and config['architecture'] == 'amd64', 'Exact linux/amd64 required')
    require(len(config['rootfs']['diff_ids']) == len(manifest['layers']), 'Every layer needs a DiffID')
    last = None
    for desc, expected_diffid in zip(manifest['layers'], config['rootfs']['diff_ids']):
        raw = blob(desc)
        uncompressed = gzip.decompress(raw) if desc['mediaType'].endswith('+gzip') or desc['mediaType'].endswith('.gzip') else raw
        require(sha(uncompressed) == expected_diffid, 'Layer decompressed DiffID mismatch')
        receipts[-1]['diff_id'] = expected_diffid
        last = uncompressed
    return manifest, config, last, receipts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--digest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    bm, bc, _, br = closure(args.base, BASE)
    cm, cc, layer, cr = closure(args.candidate, args.digest)
    require(cm['config']['digest'] == CONFIG, 'Candidate config differs from tested local image')
    require(cm['layers'][:-1] == bm['layers'], 'Compressed base layer descriptors must remain exact')
    require(cc['rootfs']['diff_ids'][:-1] == bc['rootfs']['diff_ids'], 'All base DiffIDs must remain exact')
    require(len(cm['layers']) == len(bm['layers']) + 1, 'Exactly one additive COPY layer required')
    before, after = dict(bc['config']), dict(cc['config'])
    before.pop('Labels', None); after.pop('Labels', None)
    require(before == after, 'Runtime image configuration changed')
    root = Path(__file__).parent
    expected = {p.name: p.read_bytes() for p in (root / 'bundle').iterdir()}
    found = {}
    with tarfile.open(fileobj=io.BytesIO(layer)) as archive:
        for member in archive.getmembers():
            name = member.name.lstrip('./').rstrip('/')
            require(member.uid == 0 and member.gid == 0, 'Added layer ownership changed')
            if member.isdir():
                require(name in ('opt', 'opt/native'), 'Unexpected added directory')
                continue
            require(member.isfile() and name.startswith('opt/native/') and '/.wh.' not in name,
                    'Only regular /opt/native bundle files may be added')
            filename = name.removeprefix('opt/native/')
            require(filename in expected and filename not in found and member.mode == 0o644,
                    'Unexpected added file, duplicate or mode')
            data = archive.extractfile(member).read()
            require(data == expected[filename], 'Bundle byte mismatch')
            found[filename] = sha(data)
    require(set(found) == set(expected) and len(found) == 16, 'Exactly sixteen frozen files required')
    receipt = {'version': 1, 'base': BASE, 'candidate': args.digest,
               'base_config': bm['config']['digest'], 'candidate_config': cm['config']['digest'],
               'base_blob_closure': br, 'candidate_blob_closure': cr,
               'base_layer_count': len(bm['layers']), 'candidate_layer_count': len(cm['layers']),
               'added_files': found, 'runtime_config_unchanged_except_labels': True,
               'published_inert_only': True, 'live_applied': False, 'hardware_qualified': False}
    Path(args.output).write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'candidate': args.digest, 'verified_blobs': len(cr), 'base_layers_retained': len(bm['layers']),
                      'added_files_exact': len(found), 'candidate_config': cm['config']['digest']}))


if __name__ == '__main__':
    main()
