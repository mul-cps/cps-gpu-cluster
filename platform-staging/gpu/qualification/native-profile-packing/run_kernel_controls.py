#!/usr/bin/env python3
"""Default-inert actual64MiB kernel/managed controls; rendered private sources only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import uuid

def require(ok, message):
    if not ok: raise ValueError(message)

def load(path, pin, name):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd); raw = os.read(fd, 2097153); after = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid() and before.st_nlink == 1
            and stat.S_IMODE(before.st_mode) == 0o600 and 0 < len(raw) <= 2097152
            and all(getattr(before, k) == getattr(after, k) for k in
                    ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))
            and hashlib.sha256(raw).hexdigest() == pin, 'Stable private reviewed source required')
    finally: os.close(fd)
    scope = {'__file__': str(path), '__name__': name}
    exec(compile(raw, str(path), 'exec'), scope)
    return scope, raw

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--execute', action='store_true')
    for n in ('source-sha256', 'preflight-sha256', 'managed-wrapper-sha256', 'probe-sha256'): p.add_argument('--' + n)
    p.add_argument('--output', type=Path); args = p.parse_args(argv)
    if not args.execute:
        print(json.dumps({'state': 'inert', 'api_calls': False, 'gpu_calls': False,
                          'hardware_qualification': False, 'production_qualified': False})); return
    require(args.source_sha256 == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        and args.output is not None, 'Exact reviewed wrapper and private output required')
    base = Path(__file__).parent
    h, _ = load(base / 'run_group_acceptance.py', args.preflight_sha256, 'controlled_preflight')
    m, _ = load(base / 'managed/run_managed.py', args.managed_wrapper_sha256, 'managed_library')
    _, probe = load(base / 'managed/managed_probe.py', args.probe_sha256, 'managed_probe_library')
    require(m['PROBE_SHA'] == args.probe_sha256 and m['GPU'] == h['GPU'] and m['GENERATION'] == h['GENERATION'],
            'Exact raw CUDA kernel-control closure required')
    parent = args.output.parent.lstat()
    require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid()
        and stat.S_IMODE(parent.st_mode) == 0o700, 'Private owned output parent required')
    args.output.mkdir(mode=0o700); before = None; error = None
    receipt = {'state': 'inconclusive', 'production_qualified': False, 'hardware_qualification': False,
        'source_sha256': args.source_sha256, 'preflight_sha256': args.preflight_sha256,
        'probe_sha256': args.probe_sha256, 'measurements': []}
    try:
        before = h['preflight'](h['BOUND_CONFIG']); h['write_json'](args.output / 'before.json', before)
        require(all(t['inventory_row']['used'] == 0 for t in before['host']['targets']), 'Actual baseline zero charge required')
        for bound, target in zip(h['BOUND_TARGETS'], before['pods']):
            argv = ['--execute', '--expected-gpu-uuid', h['GPU'], '--expected-pod-uid', target['pod_uid'],
                '--expected-driver-generation', h['GENERATION'], '--source-sha256', args.probe_sha256]
            packet = h['checked_run'](['kubectl', '-n', target['namespace'], 'exec', '-i', target['name'],
                '-c', 'notebook', '--', 'python', '-I', '-S', '-u', '-c', m['LOADER'], args.probe_sha256,
                str(uuid.uuid4()), *argv], source=probe, timeout=55)
            h['write_json'](args.output / ('probe-' + bound['source'] + '.json'), packet)
            receipt['measurements'].append({'source': bound['source'], 'workspace': bound['workspace'],
                'pod_uid': target['pod_uid'], 'cap_mib': target['cap_mib'],
                'measurement': m['assess'](packet, target['pod_uid'])})
    except Exception as caught: error = caught; receipt['error_type'] = type(caught).__name__
    finally:
        if before is not None:
            try:
                after = h['preflight'](h['BOUND_CONFIG']); h['write_json'](args.output / 'after.json', after)
                h['compare_observations'](before, after)
                require(all(t['inventory_row']['used'] == 0 for t in after['host']['targets']), 'Actual final zero charge required')
                receipt['exact_seals_retirements_unchanged_and_final_zero'] = True
            except Exception as caught: error = error or caught; receipt['postflight_error_type'] = type(caught).__name__
        if error is None and len(receipt['measurements']) == 2:
            receipt['state'] = 'both-controlled-parents-kernel-controls-measured-awaiting-Root-review'
        h['write_json'](args.output / 'receipt.json', receipt)
    print(json.dumps({'state': receipt['state'], 'production_qualified': False, 'hardware_qualification': False}))
    if error is not None: raise SystemExit(1)

if __name__ == '__main__': main()
