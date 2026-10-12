#!/usr/bin/env python3
"""Bind the unchanged trusted probes to the two current approved 5/10 GiB groups.

Local preparation only. Root supplies current private captures and still owns
normal Start/Stop, fresh host preflight, hardware execution and witness review.
"""
import argparse
import ast
import base64
import json
from pathlib import Path

import prepare_harness as h

PROFILE_CAPS = {'interactive-shared-5': 5120, 'interactive-shared-10': 10240}
# Canonical reviewed approval subtree at 079b2b6; changing membership, storage,
# owner, course or scope requires another review rather than self-rehashing it.
APPROVALS_SHA256 = '3449819d393ed8026353effa57e9b4b0265779e0ef547179dc6c8e1cf72c74c5'
GATE_IMAGE = 'ghcr.io/mul-cps/cps-compute@sha256:bc5b128f582641eae8395e1121d1fb248eddc39a56c9e863b7c564badd94b167'
CONTROLLER_SHA256 = '630d43cc115b5bddf3e5d110a25cc891e0941953bbabd833f0a77a3773ad7880'
LEGACY_CONTROLLER_SHA256 = 'f40ef40f71c9f1206f23fb7052fd69aafd103c0f03a24e6bf3987395dacfd179'
INVENTORY_CAPTURE_SOURCE_SHA256 = 'e36b9cd5630c4ca9a02440258b58bc7f79d92d5fe0eb7ad72c6afe1fc7c086c1'


def validate_cleared_inventory(inventory, pool, bound):
    h.require(isinstance(inventory, dict) and set(inventory) == {'version', 'backend', 'gpu_uuid', 'gpu_id', 'entries'}
        and type(inventory['version']) is int and inventory['version'] == 1
        and inventory['backend'] == 'misc-fallback' and inventory['gpu_uuid'] == pool['gpu_uuid']
        and type(inventory['gpu_id']) is int and 0 <= inventory['gpu_id'] < 2**32
        and isinstance(inventory['entries'], list) and len(inventory['entries']) <= 256,
        'Closed complete selected-device inventory required')
    rows = {}
    for row in inventory['entries']:
        h.require(isinstance(row, dict) and set(row) == {'cgroup_id', 'kernfs_id', 'inode', 'offline',
            'pinned', 'default_hierarchy', 'soft', 'hard', 'used'}
            and all(type(row[k]) is int and 0 <= row[k] < 2**64 for k in
                ('cgroup_id', 'kernfs_id', 'inode', 'soft', 'hard', 'used'))
            and all(type(row[k]) is bool for k in ('offline', 'pinned', 'default_hierarchy'))
            and row['cgroup_id'] == row['kernfs_id'] == row['inode'] > 0
            and row['inode'] not in rows and row['pinned'] is True and row['default_hierarchy'] is True
            and row['soft'] <= row['hard'], 'Unique typed pinned default inventory rows required')
        rows[row['inode']] = row
    h.require(bound <= set(rows), 'All explicit active and retired lifetimes must be present')
    cleared = [rows[n] for n in sorted(set(rows) - bound)]
    h.require(all(r['offline'] is True and r['used'] == r['soft'] == 0 and r['hard'] == 2**64-1
        for r in cleared), 'Unbound rows require exact offline zero-charge cleared limits')
    return cleared


def read_input(pin):
    h.file_pin(pin)
    return h.parse(h.read_pinned(Path(pin['path']), pin['sha256'], private=True))


def validate_inputs(manifest):
    """Current group mode, actual Pod intent and both exact durable gate seals."""
    from cps_compute import native_gpu_controller as controller
    from cps_compute.native_groups import NativeGroupDeployment, canonical_sha256
    from cps_compute.native_gpu_runtime import validate_native_pod_intent, validate_native_cap_receipt
    from cps_compute.policy import Policy

    fields = {'version', 'state', 'binding', 'policy', 'native_groups', 'sealed_targets'}
    h.require(isinstance(manifest, dict) and set(manifest) in (fields, fields | {'inventory_capture'}) and type(manifest['version']) is int
        and manifest['version'] == 1 and manifest['state'] == 'Root-reviewed-current-group-plan',
        'Closed explicit current-group preparation manifest required')
    h.require(h.sha(Path(controller.__file__).read_bytes()) == CONTROLLER_SHA256,
              'Exact reviewed native controller models required')
    binding = h._validate_binding(read_input(manifest['binding']), 'interactive-shared-')
    policy = Policy(read_input(manifest['policy']))
    config = read_input(manifest['native_groups'])
    deployment = NativeGroupDeployment.from_config(config, policy)
    h.require(deployment is not None and deployment.policy_hash == binding['policy_hash'] == policy.hash,
              'Actual enabled group-mode deployment and current policy required')
    h.require(config['evidence']['version'] == 2 and config['evidence']['profile_caps'] == PROFILE_CAPS
        and deployment.gate_image == GATE_IMAGE
        and canonical_sha256(deployment.workspaces) == 'sha256:' + APPROVALS_SHA256,
        'Only the exact reviewed CPS B5 and CIT A10 group approvals allowed')
    pool = deployment.node_pool
    h.require(all(pool[k] == binding['pool'][k] for k in
        ('node', 'node_uid', 'boot_id', 'gpu_uuid', 'driver_generation'))
        and type(pool['max_workspaces']) is int and pool['max_workspaces'] == 2
        and type(pool['memory_budget_mib']) is int and pool['memory_budget_mib'] == 15360,
        'Current group placement, epoch, two slots and 15GiB budget required')
    seals = manifest['sealed_targets']
    h.require(isinstance(seals, list) and len(seals) == 2, 'Both actual Pod lifetime seals required')
    identities = set()
    active_records = []
    for target, row in zip(binding['targets'], seals):
        h.require(isinstance(row, dict) and set(row) == {'pod_uid', 'journal', 'gate_receipt'}
            and row['pod_uid'] == target['pod_uid'], 'Ordered actual CPS5/CIT10 PodUID seals required')
        approval = deployment.approval(target['source'], target['workspace'])
        h.require(approval is not None and approval['profiles'] == [target['profile']]
            and approval['namespace'] == target['namespace'] and approval['pod'] == target['name']
            and deployment.cap_mib(target['profile']) == target['cap_mib'],
            'Actual group approval differs from requested profile or Pod')
        record = controller.CapRecord.from_dict(read_input(row['journal']))
        expected_intent = {k: target[k] for k in ('namespace', 'name', 'pod_uid', 'spec_sha256', 'cap_mib')}
        expected_intent.update({k: binding['pool'][k] for k in ('node', 'node_uid', 'gpu_uuid')},
                               policy_hash=binding['policy_hash'])
        h.require(record.state == 'sealed' and record.intent.to_dict() == expected_intent
            and record.identity.epoch == controller.DriverEpoch(pool['node_uid'], pool['boot_id'],
                pool['driver_generation'], pool['gpu_uuid']),
            'Exact current sealed native journal intent, cap and epoch required')
        key = (record.identity.cgroup_device, record.identity.cgroup_inode)
        h.require(key not in identities, 'Distinct actual native Pod-parent lifetimes required')
        identities.add(key)
        active_records.append(record)
        gate = read_input(row['gate_receipt'])
        h.require(gate == record.receipt(), 'Actual public gate must equal the protected durable seal')
        validate_native_cap_receipt(gate, expected_intent, boot_id=pool['boot_id'],
            pid_start_ticks=record.identity.pid_start_ticks, driver_generation=pool['driver_generation'])
        validate_native_pod_intent(read_input(target['pod_capture']), expected_intent)
    context = {'preparation_mode': 'current-approved-groups',
        'fresh_cross_pod_hardware_qualified': False,
        'group_evidence_sha256': config['evidence_sha256'],
        'current_controller_sha256': CONTROLLER_SHA256,
        'approved_workspaces_sha256': 'sha256:' + APPROVALS_SHA256,
        'current_group_inputs': [manifest['binding'], manifest['policy'], manifest['native_groups'],
            *(pin for row in seals for pin in (row['journal'], row['gate_receipt']))]}
    if 'inventory_capture' in manifest:
        capture = manifest['inventory_capture']
        h.require(isinstance(capture, dict) and set(capture) == {'inventory', 'host_records', 'host_snapshot'},
                  'Exact full inventory and protected capture provenance required')
        inventory = read_input(capture['inventory'])
        host = read_input(capture['host_records'])
        snapshot = read_input(capture['host_snapshot'])
        source = snapshot['captureSource']
        h.file_pin(source)
        h.require(source['sha256'] == INVENTORY_CAPTURE_SOURCE_SHA256,
                  'Exact reviewed read-only current-group capture source required')
        h.read_pinned(Path(source['path']), source['sha256'], private=True)
        h.require(type(snapshot['version']) is int and snapshot['version'] == 1 and snapshot['observerPodUid'] == binding['observer_uid']
            and all(snapshot[k] == pool[v] for k, v in [('node', 'node'), ('nodeUid', 'node_uid'),
                ('bootId', 'boot_id'), ('driverGeneration', 'driver_generation')])
            and host['bootId'] == pool['boot_id'] and host['driverGeneration'] == pool['driver_generation']
            and host['healthPassed'] is True and host['sourceSha256'] == snapshot['healthSourceSha256']
            == '52fdbdae3d5e2f66fd4653d94ef5a62f734e185fabec30450f4a1b70cfee7d67'
            and host['finiteCaps'] == inventory
            and host['finiteCapsRawSha256'] == 'sha256:' + capture['inventory']['sha256']
            and h.sha(base64.b64decode(host['finiteCapsRawBase64'], validate=True)) == capture['inventory']['sha256'],
            'Actual complete raw inventory must bind reviewed capture source and current healthy pool epoch')
        retired = validate_retired(read_input(binding['retired_capture']), binding)
        retired_records = [controller.CapRecord.from_dict(r['record']) for r in retired['records']]
        bound = {r.identity.cgroup_inode for r in active_records + retired_records}
        h.require(len(bound) == len(active_records) + len(retired_records), 'Distinct complete native lifetimes required')
        cleared = validate_cleared_inventory(inventory, pool, bound)
        rows = {r['inode']: r for r in inventory['entries']}
        for r in active_records:
            row = rows[r.identity.cgroup_inode]
            h.require(row['offline'] is False and row['soft'] == row['hard'] == r.intent.cap_bytes
                and row['used'] <= row['hard'], 'Actual sealed finite active cap required')
        for r in retired_records:
            proof = controller.validate_retired_inventory(inventory, r.identity, r.limit)
            h.require(proof.entry == r.retirement.entry and proof.gpu_id == r.retirement.gpu_id,
                      'Actual original retired finite proof must match complete inventory')
        devices = {r.identity.cgroup_device for r in active_records + retired_records}
        h.require(len(devices) == 1, 'One exact selected native cgroup2 device required')
        context['cleared_inventory_baseline'] = {'rows': cleared, 'cgroup_device': devices.pop(),
            'gpu_id': inventory['gpu_id'], 'inventory_capture': capture, 'capture_source': source}
        context['current_group_inputs'].extend(capture.values())
    return binding, context


def validate_retired(retired, binding):
    return h._validate_retired(retired, binding, controller_sha=CONTROLLER_SHA256)


def cleared_guard(rows, device, gpu_id):
    """Exact captured rows; inspect cgroup2 read-only at every host observation."""
    return '''
require(inventory['gpu_id']==GPU_ID,'Captured selected GPU identity changed')
cleared_expected=CLEARED_ROWS
cleared_inodes={r['inode'] for r in cleared_expected}
require(len(cleared_inodes)==len(cleared_expected),'Distinct explicit cleared baseline required')
for expected in cleared_expected:
 require(expected['offline'] is True and expected['pinned'] is True and expected['default_hierarchy'] is True and expected['used']==expected['soft']==0 and expected['hard']==2**64-1,'Strict cleared baseline form required')
 require(expected['inode'] not in bound and rows.get(expected['inode'])==expected,'Exact offline cleared row changed or reused');bound.add(expected['inode'])
root_info=os.stat('/sys/fs/cgroup',follow_symlinks=False)
require(stat.S_ISDIR(root_info.st_mode) and root_info.st_dev==CGROUP_DEVICE,'Exact selected cgroup2 mount device required')
deadline=time.monotonic()+10;visited=0
def walk_error(error):raise error
for path,children,files in os.walk('/sys/fs/cgroup',topdown=True,onerror=walk_error,followlinks=False):
 visited+=1
 require(visited<=4096 and visited+len(children)<=4096 and time.monotonic()<=deadline,'Bounded complete cgroup2 absence walk required')
 info=os.stat(path,follow_symlinks=False)
 require(stat.S_ISDIR(info.st_mode) and info.st_dev==CGROUP_DEVICE and info.st_ino not in cleared_inodes,'Cleared native inode is present or reused in live cgroup2')
 for name in children:
  child=os.stat(os.path.join(path,name),follow_symlinks=False)
  require(stat.S_ISDIR(child.st_mode) and child.st_dev==CGROUP_DEVICE,'No followed links or foreign cgroup mount allowed')
end_info=os.stat('/sys/fs/cgroup',follow_symlinks=False)
require((root_info.st_dev,root_info.st_ino)==(end_info.st_dev,end_info.st_ino),'Selected cgroup2 mount changed during absence walk')
'''.replace('CLEARED_ROWS', repr(rows)).replace('CGROUP_DEVICE', str(device)).replace('GPU_ID', str(gpu_id))


def vmm_stage_source(root, pins, pool):
    """Read bytes/metadata only, before any ordinary endpoint CUDA context."""
    return '''import hashlib,json,os,socket,stat
from pathlib import Path
ROOT=ROOT_VALUE
PINS=FILE_PINS
def require(ok,message):
 if not ok:raise ValueError(message)
def verify_staged():
 parent=os.open(ROOT,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
 try:
  info=os.fstat(parent)
  require(stat.S_ISDIR(info.st_mode) and info.st_uid==info.st_gid==0 and stat.S_IMODE(info.st_mode)==0o700,'Exact Root700 VMM staging directory required before endpoint launch')
  for name,digest in PINS.items():
   fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC,dir_fd=parent)
   try:
    a=os.fstat(fd);raw=os.read(fd,100001);b=os.fstat(fd)
    require(stat.S_ISREG(a.st_mode) and a.st_uid==a.st_gid==0 and a.st_nlink==1 and stat.S_IMODE(a.st_mode)==0o400
     and 0<len(raw)<=100000 and len(raw)==a.st_size
     and all(getattr(a,k)==getattr(b,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
     and hashlib.sha256(raw).hexdigest()==digest,'Exact immutable Root400 VMM source required before endpoint launch')
   finally:os.close(fd)
  sessions=os.stat('bridge-sessions',dir_fd=parent,follow_symlinks=False)
  require(stat.S_ISDIR(sessions.st_mode) and sessions.st_uid==sessions.st_gid==0 and stat.S_IMODE(sessions.st_mode)==0o700,'Exact Root700 VMM bridge sessions required before endpoint launch')
  return {'version':1,'state':'exact-vmm-bridge-staged','read_only':True,'root':ROOT,'files':PINS}
 finally:os.close(parent)
require(os.getuid()==os.geteuid()==os.getgid()==os.getegid()==0 and socket.gethostname()==NODE_VALUE
 and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT_VALUE,'Exact reviewed Root host/boot required for VMM staging observation')
print(json.dumps(verify_staged(),sort_keys=True),flush=True)
'''.replace('ROOT_VALUE', repr(root)).replace('FILE_PINS', repr(pins)).replace(
        'NODE_VALUE', repr(pool['node'])).replace('BOOT_VALUE', repr(pool['boot_id']))


def render_sources(sources, binding, retired, *, native_binary=None, cleared_baseline=None):
    h._validate_binding(binding, 'interactive-shared-')
    out = h._render_validated_sources(sources, binding, retired, native_binary=native_binary)
    old_pre = out['run_group_acceptance.py']
    pre = h.replace(old_pre.decode(), 'CONTROLLER_SHA = ' + repr(LEGACY_CONTROLLER_SHA256),
                    'CONTROLLER_SHA = ' + repr(CONTROLLER_SHA256))
    host_node = next(n.value for n in ast.parse(pre).body
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'HOST_SOURCE' for t in n.targets))
    old_host = ast.literal_eval(host_node)
    new_host = h.replace(old_host,
        '/run/cps-native-gpu/driver-inputs-optional-stack/native_gpu_controller.py',
        '/run/cps-native-gpu/qualification-current-controller-630d43cc/native_gpu_controller.py')
    new_host = h.replace(new_host, repr(LEGACY_CONTROLLER_SHA256), repr(CONTROLLER_SHA256))
    if cleared_baseline is not None:
        orphan_guard = "require(set(rows)==bound,'Unbound/orphan native inventory entry blocks probes')"
        new_host = h.replace(new_host, orphan_guard, cleared_guard(cleared_baseline['rows'],
            cleared_baseline['cgroup_device'], cleared_baseline['gpu_id']) + orphan_guard)
    pre = h.replace(pre, ast.get_source_segment(pre, host_node), repr(new_host)).encode()
    compile(pre, 'current-group-preflight', 'exec')
    out['run_group_acceptance.py'] = pre
    # Every trusted wrapper still pins the exact rendered preflight. Source
    # protocol bodies, kernel witnesses, caps and deadlines are unchanged.
    for name, raw in list(out.items()):
        if name != 'run_group_acceptance.py' and name.endswith('.py'):
            out[name] = raw.replace(h.sha(old_pre).encode(), h.sha(pre).encode()).replace(
                h.sha(old_host.encode()).encode(), h.sha(new_host.encode()).encode())
    wrapper_name = 'vmm-cross-parent-sgid-fix/run_vmm_cross_parent.py'
    if wrapper_name in out:
        wrapper = out[wrapper_name].decode()
        root = ast.literal_eval(next(n.value for n in ast.parse(wrapper).body
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'BRIDGE_ROOT' for t in n.targets)))
        pins = {name: h.sha(out['vmm-cross-parent-sgid-fix/' + name])
                for name in ('vmm_bridge.py', 'vmm_endpoint.py')}
        stage = vmm_stage_source(root, pins, binding['pool'])
        expected = {'version': 1, 'state': 'exact-vmm-bridge-staged', 'read_only': True, 'root': root, 'files': pins}
        helper = '\nVMM_STAGE_SOURCE = ' + repr(stage) + '''
def check_vmm_staging(h,args):
    proof=diagnostic_run(h.OBSERVER_ARGV,VMM_STAGE_SOURCE.encode(),args.output,'bridge-staging',timeout=10)
    require(proof==''' + repr(expected) + ''','Exact read-only VMM staging proof required before endpoint launch')
    write(args.output/'bridge-staging.json',proof)
\n'''
        wrapper = h.replace(wrapper, 'def main(argv=None):', helper + 'def main(argv=None):')
        wrapper = h.replace(wrapper, '    transport=load_witness()',
                            '    check_vmm_staging(h,args)\n    transport=load_witness()')
        compile(wrapper, 'current-vmm-staging-guard', 'exec')
        out[wrapper_name] = wrapper.encode()
        out['vmm-cross-parent-sgid-fix/bridge-prerequisite.json'] = (h.canonical({
            'version': 1, 'read_only_check': True, 'required_before_endpoint_launch': True,
            'root': root, 'uid': 0, 'gid': 0, 'directory_mode': 0o700,
            'files': {name: {'sha256': digest, 'mode': 0o400, 'nlink': 1} for name, digest in pins.items()},
            'session_directory': {'name': 'bridge-sessions', 'mode': 0o700},
            'stage_check_source_sha256': h.sha(stage.encode())}) + '\n').encode()
    return out


def prepare(manifest_path, manifest_sha, source_root, output, *, native_binary_path=None,
            native_binary_sha=None, native_build_path=None, native_build_sha=None):
    manifest = read_input({'path': str(manifest_path), 'sha256': manifest_sha})
    binding, context = validate_inputs(manifest)
    context['current_group_manifest'] = {'path': str(manifest_path), 'sha256': manifest_sha}
    # Keep canonical profile strings throughout. The original preparer still
    # validates fresh NVML, complete retirement history, exact source pins,
    # admitted Ready Pod/gate/image guards and the actual offline native ELF.
    return h._prepare_validated_binding(binding, manifest['binding']['sha256'], source_root, output,
        native_binary_path=native_binary_path, native_binary_sha=native_binary_sha,
        native_build_path=native_build_path, native_build_sha=native_build_sha, receipt_context=context,
        retirement_validator=validate_retired, source_renderer=lambda *a, **kw: render_sources(*a, **kw,
            cleared_baseline=context.get('cleared_inventory_baseline')))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--output', type=Path)
    for field in ('native-import-binary', 'native-import-build-receipt'):
        parser.add_argument('--' + field, type=Path)
        parser.add_argument('--' + field + '-sha256')
    args = parser.parse_args(argv)
    if not args.prepare:
        print(json.dumps({'state': 'inert', 'gpu_calls': False, 'api_calls': False,
                          'hardware_qualification': False, 'production_qualified': False}))
        return
    h.require(args.manifest is not None and args.manifest_sha256 and args.source_root is not None
        and args.output is not None, 'Actual pinned private current-group manifest, sources and fresh output required')
    receipt = prepare(args.manifest, args.manifest_sha256, args.source_root, args.output,
        native_binary_path=args.native_import_binary, native_binary_sha=args.native_import_binary_sha256,
        native_build_path=args.native_import_build_receipt, native_build_sha=args.native_import_build_receipt_sha256)
    print(json.dumps({'state': receipt['state'], 'api_calls': False, 'gpu_calls': False,
        'hardware_qualification': False, 'output': str(args.output)}))


if __name__ == '__main__': main()
