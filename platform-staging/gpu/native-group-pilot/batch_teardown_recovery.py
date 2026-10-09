#!/usr/bin/env python3
"""Inert qualification-only two-journal recovery after one external teardown.

This tool performs no module/device action and never releases an allocation.
Read batch-teardown-recovery-contract.md before the explicit operator modes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path('/run/cps-native-gpu')
PUBLISHER_SHA = '930bb1ad283526779da3e5c868b9e701b4d1d2df1cc2aac36a3ee5321e992eb0'
OBSERVATIONS_SHA = 'd2fa70fba12428a35fc0665981fb4d33136e7ee75625f8de417a15bde80afeb0'
HEALTH_SHA = 'e326581c158ff192fed55cc62012c22179cece2216a500c4ed59499296643376'
MODULES = {'nvidia': '194a10d24c64eea9240b86845659936f1051b184c63c471f8ebeda2c5bf4495c',
           'nvidia_uvm': 'b2ae67722e9e21a70c319aeed2184f5b2d1f23b8e32dea00816cfd5cd2c3ee61'}
GENERATION = '35423d5e-5a08-4bc8-a555-1a3be83c3038'
NODE, NODE_UID = 'k3s-wk-gpu2', '3336cdd5-d245-436e-b57c-2f66c6dcaa41'
BOOT = '209f8bc9-a478-48e4-925a-6e07ffa56f7a'
GPU = 'GPU-16128952-b438-556a-00bb-93039ee24e56'
TARGETS = {'cf045797-f4d4-4d17-9c1a-82a8837a2bc5': ('jupyterhub', 'jupyter-cpsnativegroupb--rtc'),
           '9c4c2743-60ce-4ccc-81e7-4e7dbadeaf2c': ('cit-jhub', 'jupyter-citnativegroupa--rtc')}
UIDS = sorted(TARGETS)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def sha(value):
    return 'sha256:' + hashlib.sha256(canonical(value).encode()).hexdigest()


def raw_sha(value):
    return 'sha256:' + hashlib.sha256(value).hexdigest()


def publisher():
    import teardown_recovery
    require(hashlib.sha256(Path(teardown_recovery.__file__).read_bytes()).hexdigest() == PUBLISHER_SHA,
            'Exact reviewed v1 publisher required')
    return teardown_recovery


def validate_batch(plans, digest, r):
    require(isinstance(plans, list) and len(plans) == 2 and sha(plans) == digest, 'Exact two-plan batch/hash required')
    require([p['journal']['record']['intent']['pod_uid'] for p in plans] == UIDS,
            'Only the two explicitly reviewed failed pilot UIDs qualify')
    require(len({p['binding_id'] for p in plans}) == len({p['operation_id'] for p in plans}) == 2,
            'Distinct binding/operation identities required')
    for p in plans:
        r.validate_plan(p, sha(p))
        record, scope = p['journal']['record'], p['scope']
        uid = record['intent']['pod_uid']
        require(record['state'] == 'sealed' and record['intent']['cap_mib'] == 5120
                and (record['intent']['namespace'], record['intent']['name']) == TARGETS[uid],
                'Exact original sealed 5GiB workspace journal required')
        require(scope['node'] == NODE and scope['node_uid'] == NODE_UID and scope['boot_id'] == BOOT
                and scope['driver_generation'] == GENERATION and record['intent']['gpu_uuid'] == GPU,
                'Only the reviewed current GPU2 epoch qualifies')
        require(scope['loaded_modules'] == sorted(MODULES)
                and scope['module_sha256'] == {k: 'sha256:' + v for k, v in MODULES.items()}
                and p['review']['old_module_source_sha256'] == 'sha256:' + HEALTH_SHA,
                'Exact current module/health source pins required')
    require(plans[0]['scope'] == plans[1]['scope']
            and plans[0]['ledger_uid'] == plans[1]['ledger_uid']
            and plans[0]['fence_command_sha256'] == plans[1]['fence_command_sha256'],
            'One shared node scope, ledger and Root command required')


def observe_all(backend, plans, r, frozen=None):
    for p in plans:
        r.observe(backend, p)
    ledger = backend.get_cm(r.LEDGER)
    snapshot = {'uid': ledger['metadata']['uid'], 'resourceVersion': ledger['metadata']['resourceVersion'],
                'state': ledger['data']['state.json']}
    require(frozen is None or snapshot == frozen, 'Frozen allocation ledger changed; keep both reservations held')
    return snapshot


def release_freeze(backend, expected, r):
    """Read actual paused gateway ownership; never change replicas or endpoints."""
    r.closed(expected, ('version', 'namespace', 'deployment', 'deployment_uid', 'service',
        'service_uid', 'pod_selector', 'images'), 'Closed explicit gateway release-freeze scope required')
    require(type(expected['version']) is int and expected['version'] == 1
        and expected['namespace'] == 'cps-compute' and expected['deployment'] == 'compute-gateway'
        and expected['service'] == 'compute-gateway' and r.prior.valid_uuid(expected['deployment_uid'])
        and r.prior.valid_uuid(expected['service_uid'])
        and isinstance(expected['pod_selector'], str) and expected['pod_selector']
        and isinstance(expected['images'], list) and len(expected['images']) == 1
        and all(isinstance(v, str) and '@sha256:' in v for v in expected['images']),
        'Exact shared gateway UID, selector and immutable image required')
    ns = expected['namespace']
    deploy = backend.call(['get', 'deployment', expected['deployment'], '-n', ns, '-o', 'json'])
    require(deploy.get('apiVersion') == 'apps/v1' and deploy.get('kind') == 'Deployment'
        and deploy['metadata']['namespace'] == ns and deploy['metadata']['name'] == expected['deployment']
        and deploy['metadata']['uid'] == expected['deployment_uid']
        and type(deploy['spec']['replicas']) is int and deploy['spec']['replicas'] == 0
        and deploy['status'].get('observedGeneration', -1) >= deploy['metadata']['generation']
        and all(type(deploy['status'].get(k, 0)) is int and deploy['status'].get(k, 0) == 0
                for k in ('replicas', 'readyReplicas', 'availableReplicas', 'updatedReplicas'))
        and sorted(c['image'] for c in deploy['spec']['template']['spec']['containers']) == expected['images'],
        'Actual shared gateway not fully paused at the pinned deployment/image')
    selector = ','.join(k + '=' + v for k, v in sorted(deploy['spec']['selector']['matchLabels'].items()))
    require(selector == expected['pod_selector'] and not deploy['spec']['selector'].get('matchExpressions'),
        'Exact complete gateway selector required')
    service = backend.call(['get', 'service', expected['service'], '-n', ns, '-o', 'json'])
    require(service.get('apiVersion') == 'v1' and service.get('kind') == 'Service'
        and service['metadata']['namespace'] == ns and service['metadata']['name'] == expected['service']
        and service['metadata']['uid'] == expected['service_uid']
        and service['spec']['selector'] == deploy['spec']['selector']['matchLabels']
        and not service['spec'].get('publishNotReadyAddresses', False), 'Actual pinned gateway Service selector changed')
    pods = backend.call(['get', 'pods', '-n', ns, '-l', selector, '-o', 'json'])
    slices = backend.call(['get', 'endpointslices.discovery.k8s.io', '-n', ns, '-l',
        'kubernetes.io/service-name=' + expected['service'], '-o', 'json'])
    require(pods.get('apiVersion') == 'v1' and pods.get('kind') == 'PodList'
        and isinstance(pods.get('items'), list) and not pods['items'], 'Gateway-owned Pods still exist')
    require(slices.get('apiVersion') == 'discovery.k8s.io/v1' and slices.get('kind') == 'EndpointSliceList'
        and isinstance(slices.get('items'), list), 'Actual EndpointSliceList required')
    for item in slices['items']:
        require(item['metadata']['namespace'] == ns
            and item['metadata']['labels']['kubernetes.io/service-name'] == expected['service']
            and any(ref.get('kind') == 'Service' and ref.get('name') == expected['service']
                    and ref.get('uid') == expected['service_uid'] for ref in item['metadata'].get('ownerReferences', []))
            and isinstance(item.get('endpoints'), list) and not item['endpoints'],
            'Gateway still has an endpoint backend')
    return {'scope': expected, 'deployment_uid': deploy['metadata']['uid'],
            'service_uid': service['metadata']['uid'],
            'deployment_resource_version': deploy['metadata']['resourceVersion'],
            'pods_resource_version': pods['metadata']['resourceVersion'],
            'endpoints_resource_version': slices['metadata']['resourceVersion']}


def validate_group(values, plans, r, before=None, completion=False):
    require(isinstance(values, list) and len(values) == 2, 'Both fresh Root proofs required')
    for i, (p, value) in enumerate(zip(plans, values)):
        if before is None:
            r.validate_before(value, p, sha(p))
        elif completion:
            r.validate_completion(value, p, sha(p), before[i])
        else:
            r.validate_teardown(value, p, sha(p), before[i])
    locks = [v['locks'] if before is None else v['teardown']['locks'] if completion else v['locks'] for v in values]
    require(locks[0] == locks[1], 'Both proofs must retain the same three Root lock inodes')


class BatchFence:
    def __init__(self, command, plans, batch_id, digest, r, *, diagnostics_dir=None):
        self.r, self.plans, self.batch_id, self.digest = r, plans, batch_id, digest
        self.rpc = r.RootFence(command, plans[0], diagnostics_dir=diagnostics_dir)

    def ensure_alive(self):
        self.rpc.ensure_alive()

    def __enter__(self):
        rpc = self.rpc
        if rpc.diagnostics_dir is not None:
            info = Path(rpc.diagnostics_dir).lstat()
            require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
                    and stat.S_IMODE(info.st_mode) == 0o700, 'Private diagnostics0700 required')
        with tempfile.NamedTemporaryFile(prefix='batch-teardown-', suffix='.stderr.log', dir=rpc.diagnostics_dir,
                                         delete=False) as log:
            os.fchmod(log.fileno(), 0o600); rpc.stderr_path = str(Path(log.name).absolute())
            rpc.process = subprocess.Popen(rpc.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        try:
            rpc.send('acquire-batch', plans=self.plans, batch_id=self.batch_id, batch_sha256=self.digest)
            self.before = self.response('batch-acquired', 'batch-before')
            validate_group(self.before, self.plans, self.r)
        except BaseException:
            rpc.close(); raise
        return self

    def response(self, event, stage):
        proof = self.rpc.line(event)
        require(isinstance(proof, dict) and set(proof) == {'stage', 'batch_id', 'batch_sha256', 'observations'}
                and proof['stage'] == stage and proof['batch_id'] == self.batch_id
                and proof['batch_sha256'] == self.digest, 'Exact live batch response required')
        return proof['observations']

    def verify(self):
        self.rpc.send('verify-batch')
        return self.response('batch-teardown-verified', 'batch-teardown')

    def publish(self, items):
        self.rpc.send('publish-batch', batch_sha256=self.digest, items=items)
        return self.response('batch-local-published', 'batch-complete')

    def verify_completion(self):
        self.rpc.send('verify-batch-completion')
        return self.response('batch-completion-verified', 'batch-complete')

    def __exit__(self, *args):
        return self.rpc.__exit__(*args)


def execute_batch(backend, plans, batch_id, *, expected_sha256, r):
    validate_batch(plans, expected_sha256, r)
    require(str(uuid.UUID(batch_id)) == batch_id and uuid.UUID(batch_id).int != 0, 'Fresh canonical batch UUID required')
    require(callable(getattr(backend, 'assert_release_frozen', None)), 'Mandatory actual API release-freeze observer required')
    backend.assert_release_frozen()
    frozen = observe_all(backend, plans, r)
    for p in plans:
        require(all(backend.get_cm(name, absent=True) is None for name in r.names(p)),
                'Existing audit/cleanup requires Root review; batch replay forbidden')
    with backend.batch_fence(plans, batch_id, expected_sha256) as fence:
        before = fence.before; validate_group(before, plans, r)
        observe_all(backend, plans, r, frozen)
        teardown = fence.verify(); validate_group(teardown, plans, r, before)
        observe_all(backend, plans, r, frozen)
        items = []
        for i, p in enumerate(plans):
            backend.assert_release_frozen()
            expected = r.audit_body(p, before[i], teardown[i]); created = backend.create_cm(expected)
            r.immutable_cm(created, expected); actual = backend.get_cm(r.names(p)[0]); r.immutable_cm(actual, expected)
            require(actual['metadata']['uid'] == created['metadata']['uid'], 'Batch audit replaced after create')
            items.append({'audit': actual})
        validate_group(fence.verify(), plans, r, before)
        observe_all(backend, plans, r, frozen)
        for p, item in zip(plans, items):
            backend.assert_release_frozen()
            observe_all(backend, plans, r, frozen)
            expected = r.cleanup_body(p, item['audit']); created = backend.create_cm(expected)
            r.immutable_cm(created, expected); actual = backend.get_cm(r.names(p)[1]); r.immutable_cm(actual, expected)
            require(actual['metadata']['uid'] == created['metadata']['uid'], 'Batch cleanup replaced after create')
            item['cleanup'] = actual
        validate_group(fence.verify(), plans, r, before)
        observe_all(backend, plans, r, frozen)
        backend.assert_release_frozen()
        complete = fence.publish(items); validate_group(complete, plans, r, before, completion=True)
        for p, item, value in zip(plans, items, complete):
            require(value['tombstone'] == r.tombstone(p, item['cleanup']), 'Actual immutable completion UIDs lost')
        # Two independent complete API/host readback rounds, still under locks.
        for _ in range(2):
            backend.assert_release_frozen()
            observe_all(backend, plans, r, frozen)
            for i, (p, item) in enumerate(zip(plans, items)):
                for key, expected in (('audit', r.audit_body(p, before[i], teardown[i])),
                                      ('cleanup', r.cleanup_body(p, item['audit']))):
                    name = r.names(p)[0 if key == 'audit' else 1]
                    actual = backend.get_cm(name); r.immutable_cm(actual, expected)
                    require(actual['metadata']['uid'] == item[key]['metadata']['uid'], 'Immutable batch authority replaced')
            final = fence.verify_completion(); validate_group(final, plans, r, before, completion=True)
            require(final == complete, 'Protected batch completion changed')
    return {'version': 1, 'state': 'batch-teardown-cleanup-published', 'batch_id': batch_id,
            'batch_sha256': expected_sha256, 'binding_ids': [p['binding_id'] for p in plans],
            'allocation_released': False, 'device_calls': False, 'production_qualified': False}


def root_read(path, mode=0o400):
    path = Path(path); parent = path.parent.lstat()
    require(stat.S_ISDIR(parent.st_mode) and parent.st_uid == 0 and stat.S_IMODE(parent.st_mode) == 0o700,
            'Root0700 source parent required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        require(stat.S_ISREG(a.st_mode) and a.st_uid == 0 and a.st_nlink == 1
                and stat.S_IMODE(a.st_mode) == mode, 'Protected Root exact-mode input required')
        raw = os.read(fd, 262145); b = os.fstat(fd)
        require(len(raw) <= 262144 and all(getattr(a, k) == getattr(b, k)
            for k in ('st_dev', 'st_ino', 'st_mtime_ns', 'st_ctime_ns', 'st_size')), 'Stable bounded Root input required')
        return raw
    finally:
        os.close(fd)


def load_root(path, expected, name):
    raw = root_read(path); require(raw_sha(raw) == expected, 'Exact protected dependency SHA required')
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    module.__file__ = str(path); sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def validate_review(review, r):
    r.closed(review, ('version', 'qualification_only', 'allowed_pod_uids', 'node', 'node_uid', 'boot_id',
        'driver_generation', 'core_path', 'uvm_path', 'health_path', 'health_sha256', 'publisher_sha256',
        'observation_source_sha256', 'dependency_manifest_sha256', 'release_writers_paused',
        'release_freeze_evidence_sha256'), 'Closed exact Root batch review required')
    require(type(review['version']) is int and review['version'] == 1 and review['qualification_only'] is True
        and review['allowed_pod_uids'] == UIDS and review['node'] == NODE and review['node_uid'] == NODE_UID
        and review['boot_id'] == BOOT and review['driver_generation'] == GENERATION,
        'Only the reviewed two-journal current epoch qualifies')
    require(review['health_sha256'] == 'sha256:' + HEALTH_SHA and review['publisher_sha256'] == 'sha256:' + PUBLISHER_SHA
        and review['observation_source_sha256'] == 'sha256:' + OBSERVATIONS_SHA
        and review['release_writers_paused'] is True and r.prior.hash_value(review['release_freeze_evidence_sha256'])
        and r.prior.hash_value(review['dependency_manifest_sha256']),
        'Pinned dependencies and external allocation-release freeze required')
    for key in ('core_path', 'uvm_path', 'health_path'):
        require(isinstance(review[key], str) and review[key].startswith('/run/cps-native-gpu/')
                and '..' not in review[key].split('/'), 'Protected explicit reviewed driver input path required')


class HostBatch:
    def __init__(self, f, r, health, review, plans, fds):
        self.f, self.r, self.health, self.review, self.plans, self.fds = f, r, health, review, plans, fds

    def base(self, plan):
        f, scope = self.f, plan['scope']
        require(socket.gethostname() == NODE and Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT,
                'Actual selected host/boot changed')
        info = f.directory(ROOT / 'journal')
        require(scope['journal_directory'] == {'device': info.st_dev, 'inode': info.st_ino}
            and f.pci_inventory() == [g['pci_bdf'] for g in scope['nvidia_gpus']], 'Complete actual PCI/journal scope changed')
        uid = plan['journal']['record']['intent']['pod_uid']
        journal = f.read_protected(ROOT / 'journal' / (uid + '.json'), mode=0o600)
        gate = f.read_protected(ROOT / 'receipts' / (uid + '.json'), mode=0o600, optional=True)
        quiet, tasks = f.quiescence(scope)
        return raw_sha(journal), None if gate is None else raw_sha(gate), quiet, tasks, f.lock_proof(self.fds)

    def before(self, plan):
        f, r = self.f, self.r
        journal, gate, quiet, tasks, locks = self.base(plan)
        require(journal == plan['journal']['sha256'] and self.health.validate_native_driver_health() == GENERATION,
                'Current original journal/healthy driver epoch required')
        require(f.modules() == (sorted(MODULES), sorted(MODULES))
            and raw_sha(f.read_protected(ROOT / 'authority/driver-load-manifest.json')) == plan['review']['load_manifest_sha256'],
            'Complete current original module/load authority required')
        for key, name in (('core_path', 'nvidia'), ('uvm_path', 'nvidia_uvm')):
            require(f.protected_module_sha(Path(self.review[key])) == MODULES[name], 'Actual protected original module bytes changed')
        env = dict(os.environ); env['LD_LIBRARY_PATH'] = '/run/nvidia/driver/usr/lib/x86_64-linux-gnu'
        def query(values):
            return subprocess.run(['/run/nvidia/driver/usr/bin/nvidia-smi', *values], env=env,
                capture_output=True, text=True, timeout=15, check=True).stdout.strip()
        memory, gpus = {}, []
        for line in query(['--query-gpu=uuid,pci.bus_id,memory.used', '--format=csv,noheader,nounits']).splitlines():
            gpu, bdf, used = [value.strip() for value in line.split(',')]
            gpus.append({'gpu_uuid': gpu, 'pci_bdf': bdf.lower()[-12:]}); memory[gpu] = int(used) * 1048576
        require(sorted(gpus, key=lambda x: x['pci_bdf']) == plan['scope']['nvidia_gpus'], 'Complete physical GPU UUID inventory required')
        apps = query(['--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader,nounits'])
        proof = {'stage': 'before', 'operation_id': plan['operation_id'], 'plan_sha256': sha(plan),
            'scope': plan['scope'], 'journal_sha256': journal, 'locks': locks, 'native_writers_quiesced': quiet,
            'locks_held': True, 'driver_healthy': True, 'gpu_memory_bytes': memory,
            'gpu_fd_clients': f.gpu_fd_clients(), 'compute_apps': len(apps.splitlines()) if apps else 0,
            'pod_runtime_tasks': tasks, 'gate_sha256': gate}
        r.validate_before(proof, plan, sha(plan)); return proof

    def teardown(self, plan, before, *, final=False):
        f, r = self.f, self.r
        journal, gate, quiet, tasks, locks = self.base(plan)
        sysfs, proc = f.modules(); bdfs = f.pci_inventory()
        require(not sysfs and not proc and not os.path.lexists(ROOT / 'authority/driver-generation')
            and not os.path.lexists(ROOT / 'authority/driver-load-manifest.json'), 'Positive all-module/old authority absence required')
        require(all(not os.path.lexists(Path('/sys/bus/pci/devices') / bdf / 'driver') for bdf in bdfs),
                'Every prior GPU BDF must remain unbound')
        proof = {'stage': 'teardown', 'operation_id': plan['operation_id'], 'plan_sha256': sha(plan),
            'node_uid': NODE_UID, 'boot_id': BOOT, 'old_driver_generation': GENERATION,
            'old_generation_invalidated': True, 'sysfs_modules': sysfs, 'proc_modules': proc,
            'pci_unbound': bdfs, 'gpu_fd_clients': f.gpu_fd_clients(), 'pod_runtime_tasks': tasks,
            'locks': locks, 'journal_sha256': journal, 'gate_sha256': gate,
            'native_writers_quiesced': quiet, 'locks_held': True, 'new_load_absent': True}
        r.validate_teardown(proof, plan, sha(plan), before,
            **({'journal_sha256': journal, 'gate_sha256': None} if final else {}))
        return proof


def invalidate_current_authority(f, r, plan):
    """The old observation helper's invalidator pins an earlier generation."""
    f.directory(ROOT / 'authority')
    require(f.read_protected(ROOT / 'authority/driver-generation', mode=0o600).decode().strip() == GENERATION
        and raw_sha(f.read_protected(ROOT / 'authority/driver-load-manifest.json')) == plan['review']['load_manifest_sha256'],
        'Original current authority changed before invalidation')
    for name, mode in (('driver-generation', 0o600), ('driver-load-manifest.json', 0o400)):
        f.read_protected(ROOT / 'authority' / name, mode=mode)
        (ROOT / 'authority' / name).unlink()
        fd = os.open(ROOT / 'authority', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)


def root_main(args):
    require(os.geteuid() == 0 and args.qualification, 'Explicit Root qualification required')
    require(raw_sha(root_read(Path(__file__))) == args.batch_source_sha256, 'Exact protected batch source required')
    f = load_root(ROOT / 'operator/teardown_fence.py', 'sha256:' + OBSERVATIONS_SHA, 'batch_observations')
    raw_review = root_read(ROOT / 'operator/batch-review.json')
    require(raw_sha(raw_review) == args.review_sha256, 'Pinned explicit Root review required')
    # JSON is re-parsed strictly by the reviewed publisher after its closure loads.
    review = json.loads(raw_review)
    dependencies_raw = root_read(ROOT / 'operator/dependencies.json')
    require(raw_sha(dependencies_raw) == review['dependency_manifest_sha256'], 'Pinned dependency manifest required')
    dependencies = json.loads(dependencies_raw)
    require(isinstance(dependencies, dict) and set(dependencies) == {'node_agent.py', 'abort_before_gate.py', 'source-snapshot.json'},
            'Exact recovery dependency closure required')
    for name, digest in dependencies.items():
        require(hashlib.sha256(root_read(ROOT / 'operator' / name)).hexdigest() == digest, 'Changed protected recovery dependency')
    for name in ('node_agent.py', 'abort_before_gate.py'):
        load_root(ROOT / 'operator' / name, 'sha256:' + dependencies[name], name[:-3])
    r = load_root(ROOT / 'operator/teardown_recovery.py', 'sha256:' + PUBLISHER_SHA, 'teardown_recovery')
    review = r.parse(raw_review); validate_review(review, r)
    freeze_raw = root_read(ROOT / 'operator/batch-release-freeze.json')
    require(raw_sha(freeze_raw) == review['release_freeze_evidence_sha256'], 'Actual pinned Root release-freeze evidence required')
    health = load_root(Path(review['health_path']), 'sha256:' + HEALTH_SHA, 'batch_native_health')
    request = f.read_rpc()
    r.closed(request, ('op', 'nonce', 'plans', 'batch_id', 'batch_sha256'), 'Closed acquire-batch request required')
    require(request['op'] == 'acquire-batch' and r.prior.valid_uuid(request['nonce'])
            and r.prior.valid_uuid(request['batch_id']), 'Canonical batch operation/nonce required')
    plans, digest, nonce, batch_id = request['plans'], request['batch_sha256'], request['nonce'], request['batch_id']
    validate_batch(plans, digest, r)
    fds = {}
    try:
        for name, path in [('journal', 'journal/.writer.lock'), ('driver', 'authority/.driver-loader.lock'),
                           ('maintenance', 'operator/.teardown.lock')]:
            fds[name] = f.acquire_lock(ROOT / path)
        host = HostBatch(f, r, health, review, plans, fds)
        before = [host.before(p) for p in plans]; validate_group(before, plans, r)
        evidence_root = ROOT / 'operator/batch-teardown'
        r._mkdir_private(evidence_root, 0, exist_ok=True); evidence_root = evidence_root / batch_id
        r._mkdir_private(evidence_root, 0)
        r._write(evidence_root / 'before.json', (canonical({'plans': plans, 'before': before,
            'review_sha256': args.review_sha256, 'batch_sha256': digest}) + '\n').encode(), 0, mode=0o400)
        def emit(event, stage, observations):
            print(canonical({'event': event, 'nonce': nonce,
                'observed_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'proof': {'stage': stage, 'batch_id': batch_id, 'batch_sha256': digest, 'observations': observations}}), flush=True)
        emit('batch-acquired', 'batch-before', before)
        require(f.read_rpc() == {'op': 'verify-batch', 'nonce': nonce}, 'Explicit batch teardown request required')
        require([host.before(p) for p in plans] == before, 'Both genuine before observations must remain exact')
        invalidate_current_authority(f, r, plans[0])
        deadline = time.monotonic() + 120
        while any(f.modules()):
            require(time.monotonic() < deadline and f.gpu_fd_clients() == 0
                and f.quiescence(plans[0]['scope']) == (True, 0), 'External teardown timed out or new client/writer appeared')
            time.sleep(0.2)
        original_teardown = [host.teardown(p, b) for p, b in zip(plans, before)]
        def verify():
            current = [host.teardown(p, b) for p, b in zip(plans, before)]
            require(current == original_teardown, 'Positive batch teardown changed'); return current
        emit('batch-teardown-verified', 'batch-teardown', original_teardown)
        while True:
            request = f.read_rpc()
            if request != {'op': 'verify-batch', 'nonce': nonce}: break
            emit('batch-teardown-verified', 'batch-teardown', verify())
        r.closed(request, ('op', 'nonce', 'batch_sha256', 'items'), 'Closed batch publication required')
        require(request['op'] == 'publish-batch' and request['nonce'] == nonce and request['batch_sha256'] == digest
                and isinstance(request['items'], list) and len(request['items']) == 2, 'Exact two-item batch publication required')
        items = request['items']; fresh = verify()
        for i, (p, item) in enumerate(zip(plans, items)):
            r.closed(item, ('audit', 'cleanup'), 'Actual batch API receipts required')
            expected = r.audit_body(p, before[i], original_teardown[i])
            r.immutable_cm(item['audit'], expected); r.immutable_cm(item['cleanup'], r.cleanup_body(p, item['audit']))
        for i, (p, item) in enumerate(zip(plans, items)):
            r.complete_local(ROOT, p, item['audit'], item['cleanup'], before=before[i], teardown=fresh[i], lock_fds=fds, trusted_uid=0)
        def completion():
            values = []
            for p, b, item in zip(plans, before, items):
                values.append({'stage': 'complete', 'operation_id': p['operation_id'], 'plan_sha256': sha(p),
                    'teardown': host.teardown(p, b, final=True),
                    **r.read_local_completion(ROOT, p, item['audit'], item['cleanup'], trusted_uid=0)})
            return values
        completed = completion(); validate_group(completed, plans, r, before, completion=True)
        emit('batch-local-published', 'batch-complete', completed)
        verifications = 0
        while True:
            request = f.read_rpc()
            if request != {'op': 'verify-batch-completion', 'nonce': nonce}: break
            current = completion(); require(current == completed, 'Protected batch completion changed')
            emit('batch-completion-verified', 'batch-complete', current); verifications += 1
        require(verifications >= 2 and request == {'op': 'release', 'nonce': nonce}, 'Double verified batch release required')
    finally:
        for fd in reversed(list(fds.values())): os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--root-fence', action='store_true')
    parser.add_argument('--qualification', action='store_true'); parser.add_argument('--batch-source-sha256')
    parser.add_argument('--review-sha256'); parser.add_argument('--plans', type=Path); parser.add_argument('--plans-sha256')
    parser.add_argument('--batch-id'); parser.add_argument('--fence-command', type=Path)
    parser.add_argument('--kubeconfig'); parser.add_argument('--context'); parser.add_argument('--diagnostics-dir')
    parser.add_argument('--release-freeze-config', type=Path)
    args = parser.parse_args(argv)
    if not args.execute:
        print(canonical({'state': 'inert', 'api_calls': False, 'module_actions': False, 'device_calls': False,
                         'allocation_released': False, 'production_qualified': False})); return
    require(args.qualification, 'Explicit qualification required')
    if args.root_fence:
        root_main(args); return
    require(args.plans is not None and args.fence_command is not None and args.release_freeze_config is not None,
            'Explicit plans, pinned Root command and release-freeze scope required')
    r = publisher(); plans = r.parse(args.plans.read_bytes()); command = r.parse(args.fence_command.read_bytes())
    validate_batch(plans, args.plans_sha256, r)
    backend = r.KubernetesBackend(command, kubeconfig=args.kubeconfig, context=args.context,
                                  diagnostics_dir=args.diagnostics_dir)
    freeze = r.parse(args.release_freeze_config.read_bytes())
    backend.assert_release_frozen = lambda: release_freeze(backend, freeze, r)
    def batch_fence(values, batch_id, digest):
        backend.live_fence = BatchFence(command, values, batch_id, digest, r, diagnostics_dir=args.diagnostics_dir)
        return backend.live_fence
    backend.batch_fence = batch_fence
    print(canonical(execute_batch(backend, plans, args.batch_id, expected_sha256=args.plans_sha256, r=r)))


if __name__ == '__main__': main()
