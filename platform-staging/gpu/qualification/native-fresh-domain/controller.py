#!/usr/bin/env python3
"""Explicit Root-only standalone QA cap transaction. Default inert; no Source/Node service."""
import argparse
from dataclasses import fields
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import types
import uuid

SDK = Path('/home/bjoern/git/cps-compute-worktrees/native-health-147-build-pins-20261023/src')
PINS = {
    'native_gpu_controller.py': '61ce9fa1d04d4ca2b1af02ceee6985eba8a6c2f291b139599b15c9e75a667ae7',
    'native_gpu_health.py': 'fc9dd634b8a31c15939cf6ddf3b18e84b9fa5a60d21424831a410a5ba4322fe8',
    'native_node/backend.py': 'f544fc3266e710119651010e3fcc35696b3b096ebe7de0a7dc5da65f31ae250e',
    'native_node/identity.py': '9864e8df1406cce46bdc847e2d85619e7ca1d9723811e731ea93844f0c838dfd',
    'native_node/nvml.py': '0bedb1ea0a6301a2298da30d318dae2519ac0e05e0d35d05b7b5f2136a0d221c',
    'native_node/transport.py': '51c301067def92dbced90f5e1e7cba0e694850df88ed6d64189fbcc8a54743ba'}
NS = 'cps-native-qa147-20261022'
NS_UID = '1f7d941a-872d-4453-a1ba-fd489d8aff14'
ROOT = '/var/lib/cps-native-gpu/qualification/' + NS_UID
STATE = ROOT + '/state'
AUTHORITY = '/var/lib/cps-native-gpu/domains/100876ac-14e6-4292-bf52-7d129f7f08f0/custody/authority'
NODE = 'k3s-wk-gpu2'
NODE_UID = '3336cdd5-d245-436e-b57c-2f66c6dcaa41'
BOOT = 'a464df41-e391-4443-b8e8-ad7ecd052318'
GENERATION = '4ebffc96-e25e-4583-a3b8-0d853fd90efd'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'

def require(value, message):
    if not value: raise ValueError(message)

def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result

def document(raw):
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: require(False, 'Nonfinite JSON'))

def check_bundle(root):
    root = Path(root)
    require(root.is_dir() and not root.is_symlink(), 'Exact source bundle directory required')
    actual = set()
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'Symlink source denied')
        if path.is_file(): actual.add(str(path.relative_to(root)))
        else: require(path.is_dir(), 'Special source denied')
    require(actual == {'cps_compute/' + name for name in PINS}, 'Exact complete source bundle required')
    result = {}
    for name, pin in PINS.items():
        raw = (root / 'cps_compute' / name).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == pin, 'Exact reviewed source required: ' + name)
        result[name] = raw
    return result

def prepare_bundle(destination):
    raw = {}
    for name, pin in PINS.items():
        raw[name] = (SDK / 'cps_compute' / name).read_bytes()
        require(hashlib.sha256(raw[name]).hexdigest() == pin, 'Exact reviewed source required: ' + name)
    destination = Path(destination)
    destination.mkdir(mode=0o700)
    (destination / 'cps_compute/native_node').mkdir(parents=True, mode=0o700)
    for name, content in raw.items():
        fd = os.open(destination / 'cps_compute' / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream: stream.write(content)
    check_bundle(destination)
    return destination

def load_bundle(root):
    raw = check_bundle(root)  # Check EVERY dependency BEFORE executing ANY source.
    require(not any(k == 'cps_compute' or k.startswith('cps_compute.') for k in sys.modules),
            'Fresh isolated interpreter required; installed SDK must not be imported')
    for name in ('cps_compute', 'cps_compute.native_node'):
        module = types.ModuleType(name); module.__path__ = []
        sys.modules[name] = module
    result = {}
    for name in ('native_node/backend.py', 'native_node/identity.py', 'native_node/nvml.py',
                 'native_node/transport.py', 'native_gpu_health.py', 'native_gpu_controller.py'):
        key = 'cps_compute.' + name[:-3].replace('/', '.')
        module = types.ModuleType(key); module.__package__ = key.rpartition('.')[0]
        module.__file__ = str(Path(root) / 'cps_compute' / name)
        sys.modules[key] = module
        exec(compile(raw[name], module.__file__, 'exec'), module.__dict__)
        result[name] = module
    return result

def inventory(value, allowed, *, allow_offline=False, retired=None):
    retired = retired or {}
    require(type(value) is dict and set(value) == {'version', 'backend', 'gpu_uuid', 'gpu_id', 'entries'}
            and type(value['version']) is int and value['version'] == 1
            and value['backend'] == 'misc-fallback' and value['gpu_uuid'] == GPU
            and type(value['gpu_id']) is int and 0 <= value['gpu_id'] < 2**32
            and type(value['entries']) is list and len(value['entries']) <= 256,
            'Complete exact physical GPU inventory required')
    seen = set()
    for row in value['entries']:
        require(type(row) is dict and set(row) == {'cgroup_id','kernfs_id','inode','offline','pinned',
            'default_hierarchy','soft','hard','used'} and all(type(row[k]) is int and 0 <= row[k] < 2**64
            for k in ('cgroup_id','kernfs_id','inode','soft','hard','used'))
            and all(type(row[k]) is bool for k in ('offline','pinned','default_hierarchy')),
            'Typed exact inventory row required')
        require(row['cgroup_id'] == row['kernfs_id'] == row['inode'] and row['inode'] > 0
                and row['inode'] not in seen and row['pinned'] is True and row['default_hierarchy'] is True,
                'Pinned unique default hierarchy required')
        if row['inode'] in retired:
            require(row == retired[row['inode']], 'Reviewed retained native entry changed')
            seen.add(row['inode']);continue
        require(row['inode'] in allowed and (allow_offline is True or row['offline'] is False),
                'Unrelated or offline native inventory denied')
        require((row['soft'],row['hard']) in ((0,2**64-1),(5120*1048576,5120*1048576))
                and row['used'] == 0, 'Exact empty QA parent limit required')
        seen.add(row['inode'])
    require(set(retired).issubset(seen), 'Reviewed retained native entries disappeared')

def cohort_state(value):
    if value is None:return STATE
    require(type(value) is str and str(uuid.UUID(value))==value and uuid.UUID(value).int>0,
            'Reviewed canonical nonzero cohort UUID required')
    return ROOT+'/cohorts/'+value+'/state'

def verify_retirements(backend,journal,records):
    actual=journal.records()
    require(0<len(records)<=16 and len(actual)==len(records)
            and {r.intent.pod_uid:r for r in actual}=={r.intent.pod_uid:r for r in records},
            'Complete original protected retirement journals required')
    rows={}
    for record in records:
        require(record.state=='retired-inert-cap' and record.recovery is None
                and record.retirement is not None,'Only original fully retired-inert-cap journals are admissible')
        fresh=backend.retired_inert_cap(record.identity,record.limit)
        require(fresh.identity==record.retirement.identity and fresh.epoch==record.retirement.epoch
                and fresh.gpu_id==record.retirement.gpu_id and fresh.entry==record.retirement.entry
                and backend.read_gate(record.identity) is None,'Fresh original retirement entry/absence changed')
        fresh.require_limit(record.limit)
        require(fresh.entry.inode not in rows,'Duplicate retired native parent denied')
        rows[fresh.entry.inode]=asdict(fresh.entry)
    return rows

def retirement_inputs(args,models,back,make_backend,current_state):
    path=getattr(args,'retirement',None);pin=getattr(args,'retirement_sha256',None)
    if path is None:
        require(pin is None,'Retirement path and independent raw hash must be paired');return {}
    raw=path.read_bytes()
    require(pin is not None and len(raw)<=1024*1024 and hashlib.sha256(raw).hexdigest()==pin,
            'Reviewed complete retirement descriptor bytes required')
    value=document(raw)
    require(type(value) is dict and set(value)=={'version','state_root','records'}
            and type(value['version']) is int and value['version']==1
            and type(value['records']) is list and 0<len(value['records'])<=16,
            'Closed bounded original retirement descriptor required')
    old=value['state_root']
    require(type(old) is str and old!=current_state,'Distinct original protected QA state required')
    if old!=STATE:
        prefix=ROOT+'/cohorts/'
        require(old.startswith(prefix) and old.endswith('/state')
                and cohort_state(old[len(prefix):-len('/state')])==old,'Exact original QA state path required')
    for directory in (old,old+'/authority',old+'/bootstrap',old+'/receipts',old+'/journal'):
        back.private_directory(directory)
    records=[models.CapRecord.from_dict(item) for item in value['records']]
    require(all(r.intent.namespace==NS and r.intent.node==NODE and r.intent.node_uid==NODE_UID
                and r.intent.gpu_uuid==GPU and r.intent.cap_mib==5120
                and r.identity.boot_id==BOOT and r.identity.driver_generation==GENERATION for r in records),
            'Exact actual current-epoch QA retirements required')
    journal=models.PrivateJournal.__new__(models.PrivateJournal);journal.directory=Path(old)/'journal'
    return verify_retirements(make_backend([r.intent for r in records],old),journal,records)

def cleanup_records(controller, journal, intents):
    records = journal.records()
    wanted = {intent.pod_uid:intent for intent in intents}
    require(records and all(wanted.get(record.intent.pod_uid) == record.intent for record in records),
            'Only exact original QA journals may be cleaned; never reset or reconstruct')
    return [controller.cleanup(record.intent) for record in records]

def execute(args):
    require(os.geteuid() == 0 and args.approve_qa_hostpaths, 'Explicit Root QA hostPath approval required')
    state=cohort_state(getattr(args,'cohort_uid',None))
    require(args.state_root in (None,state), 'Only separately staged QA state may be changed')
    modules = load_bundle(args.bundle)
    models, back, manual, nvml, tr, health = [modules[name] for name in
        ('native_gpu_controller.py','native_node/backend.py','native_node/identity.py',
         'native_node/nvml.py','native_node/transport.py','native_gpu_health.py')]
    intents = []
    for path, pin in ((args.intent_a,args.intent_a_sha256),(args.intent_b,args.intent_b_sha256)):
        require(path is not None and pin is not None, 'Two actual bound intent paths and independent raw hashes required')
        raw = path.read_bytes(); require(hashlib.sha256(raw).hexdigest() == pin, 'Reviewed actual intent bytes changed')
        value = document(raw)
        require(type(value) is dict and set(value) == {f.name for f in fields(models.CapIntent)}, 'Closed intent required')
        intent = models.CapIntent(**value)
        require(intent.namespace == NS and intent.node == NODE and intent.node_uid == NODE_UID
                and intent.gpu_uuid == GPU and intent.cap_mib == 5120, 'Exact fresh QA cohort required')
        intents.append(intent)
    suffix='-'+args.cohort_uid[:8] if getattr(args,'cohort_uid',None) else ''
    require({i.name for i in intents} == {'native-qa147-a'+suffix,'native-qa147-b'+suffix}
            and len({i.pod_uid for i in intents}) == 2 and len({i.policy_hash for i in intents}) == 1,
            'Two independently bound fresh QA Pods required')
    for directory in (state, state+'/authority', state+'/bootstrap', state+'/receipts', state+'/journal'):
        back.private_directory(directory)
    require(back.private_read(Path(state)/'authority/driver-generation', raw=True) == GENERATION,
            'QA epoch must match independently verified actual driver generation')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT, 'Actual selected boot changed')
    kube = tr.Kubernetes(args.service_account)
    namespace = kube.call('GET', '/api/v1/namespaces/' + NS)
    require(namespace['metadata']['uid'] == NS_UID and not namespace['metadata'].get('deletionTimestamp'),
            'Actual fresh QA namespace UID changed')
    driver = nvml.Nvml()
    try:
        require(driver.version == '615.71.09', 'Exact driver/NVML version required')
        def healthy():
            require(health.validate_native_driver_health(authority_directory=AUTHORITY, boot_id=BOOT) == GENERATION,
                    'Fresh actual guarded147 health/generation required')
            return True
        def make_backend(enrolled,root):
            return back.QualificationNodeBackend(models, manual, intents=enrolled, driver=driver,
                get_pod=kube.pod,get_node=kube.node,get_cri=tr.cri_reader(args.crictl,args.cri_socket),
                delete_pod=kube.delete,gpu_clients=lambda gpu:tr.gpu_clients(gpu,binary=args.nvidia_smi),
                health=healthy,state_root=Path(root))
        backend=make_backend(intents,state)
        retired=retirement_inputs(args,models,back,make_backend,state)
        journal = models.PrivateJournal(Path(state)/'journal')
        controller = models.NativeCapController(backend,journal,enabled=True,qualification_only=True)
        if args.cleanup:
            original = journal.records()
            require(original and all(any(record.intent == intent for intent in intents) for record in original),
                    'Exact retained QA ownership required for cleanup')
            inventory(backend._inventory(original[0].identity),
                      {record.identity.cgroup_inode for record in original},allow_offline=True,retired=retired)
            records = cleanup_records(controller,journal,intents)
            print(json.dumps({'state':'cleanup-verified','records':[r.to_dict() for r in records],
                              'hardware_qualified':False,'production_qualified':False}),flush=True)
            return
        require(not journal.records(), 'Fresh cohort requires empty QA journal; never reset or adopt')
        identities = [backend.observe(intent).identity for intent in intents]
        allowed = {identity.cgroup_inode for identity in identities}
        require(len(allowed) == 2, 'Independent exact Pod parents required')
        require(not allowed.intersection(retired),'Original retired parent identity reused')
        inventory(backend._inventory(identities[0]), allowed,retired=retired)
        records = [controller.reconcile(intent) for intent in intents]
        require(retirement_inputs(args,models,back,make_backend,state)==retired,'Original retirements changed')
        inventory(backend._inventory(identities[0]), allowed,retired=retired)
        print(json.dumps({'state':'sealed','records':[r.to_dict() for r in records],
                          'hardware_qualified':False,'production_qualified':False}),flush=True)
    finally: driver.close()

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    action = p.add_mutually_exclusive_group()
    action.add_argument('--execute',action='store_true')
    action.add_argument('--prepare-bundle',type=Path)
    p.add_argument('--bundle',type=Path)
    p.add_argument('--intent-a',type=Path); p.add_argument('--intent-a-sha256')
    p.add_argument('--intent-b',type=Path); p.add_argument('--intent-b-sha256')
    p.add_argument('--state-root')
    p.add_argument('--cohort-uid')
    p.add_argument('--retirement',type=Path);p.add_argument('--retirement-sha256')
    p.add_argument('--service-account',type=Path,default=Path(ROOT)/'api')
    p.add_argument('--crictl',type=Path)
    p.add_argument('--cri-socket',default='unix:///run/k3s/containerd/containerd.sock')
    p.add_argument('--nvidia-smi',default='/usr/bin/nvidia-smi')
    p.add_argument('--approve-qa-hostpaths',action='store_true')
    p.add_argument('--cleanup',action='store_true',help='With --execute, retain exact journals and invoke original full cleanup proof')
    args = p.parse_args(argv)
    if args.prepare_bundle:
        prepare_bundle(args.prepare_bundle); print(json.dumps({'state':'bundle-prepared','source_pins':PINS})); return
    if not args.execute:
        print(json.dumps({'state':'inert','api_calls':False,'gpu_calls':False})); return
    require(args.bundle is not None and args.crictl is not None, 'Explicit source bundle/CRI binary required')
    execute(args)

if __name__ == '__main__': main()
