#!/usr/bin/env python3
"""Default-inert read-only physical retirement observer after Root normal Stop."""
import argparse
import json
import os
from pathlib import Path
import stat
import prepare_harness as p
from run_kernel_controls import load

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--execute', action='store_true')
    for flag in ('source-sha256', 'preflight-sha256', 'binding-sha256', 'retired-sha256'):
        parser.add_argument('--' + flag)
    parser.add_argument('--binding', type=Path); parser.add_argument('--retired', type=Path)
    parser.add_argument('--output', type=Path); args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({'state': 'inert', 'api_calls': False, 'gpu_calls': False, 'hardware_qualification': False})); return
    p.require(p.sha(Path(__file__).read_bytes()) == args.source_sha256 and args.output is not None,
        'Exact reviewed physical observer and private output required')
    binding = p.validate_binding(p.parse(p.read_pinned(args.binding, args.binding_sha256, private=True)))
    retired = p.validate_retired(p.parse(p.read_pinned(args.retired, args.retired_sha256, private=True)),
                                binding, allow_current=True)
    h, _ = load(Path(__file__).with_name('run_group_acceptance.py'), args.preflight_sha256, 'physical_readonly')
    p.require(h['BOUND_CONFIG'] == {'observer_uid': binding['observer_uid'],
        'driver_generation': binding['pool']['driver_generation'], 'targets': [
        {k: t[k] for k in ('namespace', 'name', 'pod_uid')} for t in binding['targets']]},
        'Exact prepared original binding required')
    parent = args.output.parent.lstat()
    p.require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid() and
        stat.S_IMODE(parent.st_mode) == 0o700, 'Private owned output parent required')
    args.output.mkdir(mode=0o700)
    # The exact host source reads every row, proves both original cgroups/gates
    # absent, every retired row zero, and rejects any unbound inventory entry.
    request = {k: binding['pool'][k] for k in ('node', 'node_uid', 'boot_id', 'gpu_uuid', 'driver_generation')}
    request.update(core_sha256=h['CORE'], uvm_sha256=h['UVM'], health_sha256=h['HEALTH_SHA'],
        controller_sha256=h['CONTROLLER_SHA'], cap_bytes=h['CAP'], budget_bytes=h['BUDGET_BYTES'],
        targets=[], retired_caps=retired['records'])
    source = h['HOST_SOURCE'].replace('len(approved)==' + str(len(h['retired_whitelist'](h['GENERATION']))),
                                     'len(approved)==' + str(len(retired['records'])))
    p.require(source.count('len(approved)==' + str(len(retired['records']))) == 1,
              'Exact newly pinned retirement count required')
    observed = h['checked_run'](h['OBSERVER_ARGV'], source=h['python_stdin_source'](source, request))
    p.require(observed.get('kind') == 'native-group-host-observation' and observed.get('targets') == []
        and all(observed.get(k) == request[k] for k in ('node', 'node_uid', 'boot_id', 'gpu_uuid', 'driver_generation'))
        and len(observed.get('retired_caps', [])) == len(retired['records']), 'Exact actual full physical observations required')
    h['write_json'](args.output / 'physical.json', observed)
    h['write_json'](args.output / 'receipt.json', {'state': 'physical-retirement-measured-awaiting-Root-review',
        'hardware_qualification': False, 'production_qualified': False, 'source_sha256': args.source_sha256,
        'host_source_sha256': p.sha(source.encode()), 'original_preflight_sha256': args.preflight_sha256,
        'binding_raw_sha256': args.binding_sha256, 'retired_raw_sha256': args.retired_sha256,
        'physical_raw_sha256': p.sha((args.output / 'physical.json').read_bytes()),
        'orphan_scope': 'original Pod UID/cgroup only'})
    print(json.dumps({'state': 'physical-retirement-measured-awaiting-Root-review', 'hardware_qualification': False}))

if __name__ == '__main__': main()
