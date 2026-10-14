#!/usr/bin/env python3
"""Retain official base blob encodings after Podman exports one inherited tar."""
import argparse
import json
from pathlib import Path
import shutil
from verify_oci import BASE, CONFIG, closure, require, sha


def main():
    p = argparse.ArgumentParser(); p.add_argument('--base', required=True)
    p.add_argument('--candidate', required=True); p.add_argument('--digest', required=True)
    p.add_argument('--output', required=True); a = p.parse_args()
    bm, bc, _, _ = closure(a.base, BASE)
    cm, cc, _, _ = closure(a.candidate, a.digest)
    require(cm['config']['digest'] == CONFIG and len(cm['layers']) == len(bm['layers']) + 1
            and cc['rootfs']['diff_ids'][:-1] == bc['rootfs']['diff_ids'], 'Tested exact additive image required')
    before, after = dict(bc['config']), dict(cc['config'])
    before.pop('Labels', None); after.pop('Labels', None)
    require(before == after, 'Runtime config changed')
    out = Path(a.output); require(not out.exists(), 'New owned archive directory required')
    blobs = out / 'blobs' / 'sha256'; blobs.mkdir(parents=True)
    for desc, src in [(bm['config'], a.base), *[(x, a.base) for x in bm['layers']],
                      (cm['config'], a.candidate), (cm['layers'][-1], a.candidate)]:
        filename = desc['digest'].split(':')[1]
        shutil.copyfile(Path(src) / 'blobs' / 'sha256' / filename, blobs / filename)
    cm['layers'] = bm['layers'] + [cm['layers'][-1]]
    raw = json.dumps(cm, separators=(',', ':')).encode(); digest = sha(raw)
    (blobs / digest.split(':')[1]).write_bytes(raw)
    (out / 'oci-layout').write_text('{"imageLayoutVersion":"1.0.0"}')
    (out / 'index.json').write_text(json.dumps({'schemaVersion':2,'manifests':[
        {'mediaType':'application/vnd.oci.image.manifest.v1+json','digest':digest,'size':len(raw),
         'annotations':{'org.opencontainers.image.ref.name':'qualified'}}]},separators=(',',':')))
    print(digest)


if __name__ == '__main__':
    main()
