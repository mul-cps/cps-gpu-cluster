"""Strict, injected host adapter for the bounded no-MIG controller experiment.

No import-time NVML, API, process or filesystem writes. Instantiate only after
root has enrolled exact intents and loaded/verified the experimental guard.
"""
from dataclasses import fields
import ctypes
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import uuid


GATE = 'cps-native-cap-gate'
BOOTSTRAP_PROTOCOL = 'cps-native-gpu/bootstrap-v1'


def rename_no_replace(source, target):
    """Linux atomic publication with no transient extra hard link or overwrite."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(target), 1) != 0:  # RENAME_NOREPLACE
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_uuid(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except ValueError:
        return False


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate private JSON key')
        result[key] = value
    return result


def private_directory(path, uid=0):
    path = Path(path)
    value = path.lstat()
    require(stat.S_ISDIR(value.st_mode) and value.st_uid == uid and stat.S_IMODE(value.st_mode) == 0o700,
            'Owned private0700 directory required: ' + str(path))
    return path


def private_read(path, uid=0, *, raw=False):
    path = Path(path)
    private_directory(path.parent, uid)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, 'rb') as stream:
        value = os.fstat(stream.fileno())
        require(stat.S_ISREG(value.st_mode) and value.st_uid == uid
                and stat.S_IMODE(value.st_mode) == 0o600 and value.st_nlink == 1,
                'Owned private0600 regular file required: ' + str(path))
        content = stream.read(32769)
    require(len(content) <= 32768, 'Private record exceeds size limit')
    return content.decode().strip() if raw else json.loads(content, object_pairs_hook=unique_json)


def private_write(path, value, uid=0, *, create=False):
    path = Path(path)
    private_directory(path.parent, uid)
    if not create:
        require(private_read(path, uid) is not None, 'Existing owned private record required')
    content = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.native-', delete=False) as stream:
            temporary = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if create:
            rename_no_replace(temporary, path)
        else:
            os.replace(temporary, path)
        temporary = None
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def spec_hash(pod):
    return hashlib.sha256(json.dumps(pod['spec'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class QualificationNodeBackend:
    def __init__(self, models, manual, *, intents, driver, get_pod, get_node, get_cri,
                 delete_pod, gpu_clients, health, proc_root=Path('/proc'),
                 cgroup_root=Path('/sys/fs/cgroup'), state_root=Path('/run/cps-native-gpu'),
                 trusted_uid=0):
        self.m, self.manual, self.driver = models, manual, driver
        self.intents = {intent.pod_uid: intent for intent in intents}
        require(len(self.intents) == len(intents), 'One immutable GPU intent per Pod UID required')
        require(all(type(intent) is models.CapIntent for intent in intents), 'Typed trusted intents required')
        self.get_pod, self.get_node, self.get_cri = get_pod, get_node, get_cri
        self.delete_pod, self.gpu_clients, self.health = delete_pod, gpu_clients, health
        self.proc, self.cg, self.state = Path(proc_root), Path(cgroup_root), Path(state_root)
        self.uid = trusted_uid
        for path in (self.state, self.state / 'authority', self.state / 'receipts',
                     self.state / 'authority/bootstrap'):
            private_directory(path, self.uid)
        require(int(self.driver.version.split('.')[0]) >= 615, 'R615 or newer required')
        self.manual.GATE = GATE  # imported isolated helper module, never edit its source

    def _intent(self, identity):
        require(identity.pod_uid in self.intents, 'Unenrolled Pod UID refused')
        intent = self.intents[identity.pod_uid]
        identity.require_intent(intent)
        return intent

    def _epoch(self, intent):
        node = self.get_node(intent.node)
        require(node['metadata']['uid'] == intent.node_uid and node['metadata']['name'] == intent.node,
                'Live selected node UID changed')
        generation = private_read(self.state / 'authority/driver-generation', self.uid, raw=True)
        require(canonical_uuid(generation), 'Trusted driver maintenance epoch missing or invalid')
        boot = (self.proc / 'sys/kernel/random/boot_id').read_text().strip()
        return self.m.DriverEpoch(intent.node_uid, boot, generation, intent.gpu_uuid)

    def _health(self):
        require(self.health() is True and int(self.driver.version.split('.')[0]) >= 615,
                'Current exact non-MIG driver/UVM guard health required')
        return True

    def _pod(self, intent, *, absent=False):
        pod = self.get_pod(intent)
        if pod is None and absent:
            return None
        require(pod is not None, 'Expected Pod missing')
        meta = pod['metadata']
        require(all(meta.get(key) == getattr(intent, field) for key, field in
                    [('uid', 'pod_uid'), ('namespace', 'namespace'), ('name', 'name')]),
                'Actual exact enrolled Pod identity required')
        require(pod['spec'].get('nodeName') == intent.node and spec_hash(pod) == intent.spec_sha256,
                'Actual full admitted Pod spec changed')
        return pod

    def _group(self, identity, *, absent=False):
        relative = identity.cgroup_relative
        candidate = self.cg / relative.lstrip('/')
        if not candidate.exists() and not candidate.is_symlink() and absent:
            return None
        group = self.manual.safe_path(self.cg, relative)
        value = group.stat()
        require(value.st_dev == identity.cgroup_device and value.st_ino == identity.cgroup_inode,
                'Actual Pod cgroup inode/device changed')
        return group

    def _current(self, identity, *, absent=False):
        intent = self._intent(identity)
        require(self._epoch(intent) == identity.epoch, 'Driver/node/boot epoch changed')
        self._health()
        group = self._group(identity, absent=absent)
        return intent, group

    @staticmethod
    def _no_started_user_init(pod):
        for entry in pod.get('status', {}).get('initContainerStatuses', []):
            if entry['name'] == GATE:
                continue
            require(not entry.get('containerID') and not entry.get('restartCount', 0)
                    and not entry.get('lastState') and not any(key in entry.get('state', {})
                    for key in ('running', 'terminated')), 'User init or sidecar already started')

    def _raw(self, identity, path=None):
        value = self.driver.get(identity.gpu_uuid, str(path or self.cg / identity.cgroup_relative.lstrip('/')))
        if value is None:
            return None  # positive NVML_ERROR_NOT_FOUND, never code3
        if value == {'nvml_result': 3, 'state': 'unset-or-unsupported'}:
            return value
        require(isinstance(value, dict) and set(value) == {'soft', 'hard', 'used'}
                and all(type(value[key]) is int and value[key] >= 0 for key in value),
                'Unknown native driver readback')
        self.m.CapLimit(value['soft'], value['hard'])
        return value

    @staticmethod
    def _ambiguous(value):
        return value == {'nvml_result': 3, 'state': 'unset-or-unsupported'}

    def _descendants(self, identity, group):
        parent = self._raw(identity, group)
        for candidate in sorted(group.rglob('*')):
            if candidate.is_symlink():
                raise ValueError('Symlink inside Pod cgroup rejected')
            if not candidate.is_dir():
                continue
            self.manual.safe_path(self.cg, '/' + str(candidate.relative_to(self.cg)))
            value = self._raw(identity, candidate)
            if value is None or self._ambiguous(value):
                continue  # only reviewed code3; later parent bootstrap proves support
            same = (isinstance(parent, dict) and 'soft' in parent
                    and (value['soft'], value['hard']) == (parent['soft'], parent['hard']))
            require((value['soft'] == 0 and value['hard'] == self.m.MAX_LIMIT) or same,
                    'Foreign descendant native limit detected')
        return True

    def observe(self, intent):
        require(self.intents.get(intent.pod_uid) == intent, 'Exact root-enrolled intent required')
        before = self._epoch(intent)
        self._health()
        pod = self._pod(intent)
        self._no_started_user_init(pod)
        reduced = {key: getattr(intent, key) for key in
                   ('pod_uid', 'namespace', 'name', 'node', 'gpu_uuid', 'cap_mib', 'spec_sha256')}
        proof = self.manual.discover(reduced, pod, self.get_cri(intent), self.proc, self.cg)
        values = {field.name: proof[field.name] for field in fields(self.m.CapIdentity)
                  if field.name not in ('node_uid', 'driver_generation')}
        values.update(node_uid=intent.node_uid, driver_generation=before.driver_generation,
                      cgroup_path='/sys/fs/cgroup' + proof['cgroup_relative'])
        identity = self.m.CapIdentity(**values)
        require(identity.epoch == before and self._epoch(intent) == before,
                'Concurrent driver epoch/boot changed during discovery')
        descendants = self._descendants(identity, self._group(identity))
        return self.m.CapObservation(identity, True, False, True, descendants)

    def check_owner(self, identity):
        intent, group = self._current(identity)
        pod = self._pod(intent)
        value = group.stat()
        return self.m.OwnerObservation(identity.epoch, pod['metadata']['uid'], spec_hash(pod),
            identity.cgroup_path, value.st_dev, value.st_ino, True, True,
            self._descendants(identity, group))

    def _bootstrap(self, identity):
        # Only a still-blocked first gate on a virgin Pod parent is eligible.
        intent = self._intent(identity)
        require(self.observe(intent).identity == identity, 'Bootstrap requires exact blocked gate identity')
        require(self.read_gate(identity) is None, 'Bootstrap cannot follow public gate release')
        group = self._group(identity)
        for pid in self.gpu_clients(identity.gpu_uuid):
            require(type(pid) is int and pid > 0, 'Unknown GPU client identity')
            cgroups = (self.proc / str(pid) / 'cgroup').read_text().splitlines()
            require(not any(line.startswith('0::' + identity.cgroup_relative + '/')
                            or line == '0::' + identity.cgroup_relative for line in cgroups),
                    'CUDA client already present in virgin Pod')
        path = self.state / 'authority/bootstrap' / (identity.pod_uid + '.json')
        expected = {'protocol': BOOTSTRAP_PROTOCOL, 'intent': intent.to_dict(),
                    'identity': identity.to_dict(), 'state': 'prepared',
                    'readback': None, 'production_qualified': False}
        previous = private_read(path, self.uid)
        if previous is None:
            private_write(path, expected, self.uid, create=True)  # before any driver write
        else:
            require(previous == expected, 'Bootstrap ownership changed or unsupported readback recurred')
        require(self.observe(intent).identity == identity, 'Bootstrap identity changed before set')
        value = self._raw(identity, group)
        require(value is None or self._ambiguous(value) or
                (value['soft'] == 0 and value['hard'] == self.m.MAX_LIMIT and value['used'] == 0),
                'Virgin bootstrap must never reset an existing limited or used parent')
        self._write_driver(identity, group, 0, self.m.MAX_LIMIT)
        require(self.observe(intent).identity == identity, 'Bootstrap identity changed after set')
        readback = self._raw(identity, group)
        require(isinstance(readback, dict) and set(readback) == {'soft', 'hard', 'used'}
                and readback == {'soft': 0, 'hard': self.m.MAX_LIMIT, 'used': 0},
                'Supported unlimited bootstrap requires exact successful native readback')
        private_write(path, dict(expected, state='applied', readback=readback), self.uid)
        return self.m.CapLimit(0, self.m.MAX_LIMIT)

    def read_limit(self, identity):
        _, group = self._current(identity)
        value = self._raw(identity, group)
        if self._ambiguous(value):
            return self._bootstrap(identity)
        if value is None:
            return None
        bootstrap = private_read(self.state / 'authority/bootstrap' / (identity.pod_uid + '.json'), self.uid)
        if (bootstrap is not None and bootstrap.get('state') == 'prepared'
                and value == {'soft': 0, 'hard': self.m.MAX_LIMIT, 'used': 0}):
            return self._bootstrap(identity)  # crash after unlimited set, before bootstrap commit
        return self.m.CapLimit(value['soft'], value['hard'])

    def set_limit(self, identity, limit):
        intent, group = self._current(identity)
        raw = self._raw(identity, group)
        if limit.unlimited:
            proof = self.check_cleanup(identity)
            require((proof.pod_uid is None or proof.pod_terminal)
                    and not proof.live_tasks and not proof.gpu_clients,
                    'Limit reset requires confirmed stop and no GPU clients')
        else:
            require(self.observe(intent).identity == identity, 'Cap mutation requires exact blocked gate')
        require(not self._ambiguous(raw), 'Ambiguous native limit must bootstrap before cap/reset')
        self._write_driver(identity, group, limit.soft, limit.hard)

    def _write_driver(self, identity, group, soft, hard):
        # Keep a cgroup FD alive and compare its identity at both sides of NVML.
        fd = os.open(group, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            value = os.fstat(fd)
            require((value.st_dev, value.st_ino) == (identity.cgroup_device, identity.cgroup_inode),
                    'Cgroup changed before NVML mutation')
            self._current(identity)
            self.driver.set(identity.gpu_uuid, str(group), soft, hard)
            self._current(identity)
            after = os.stat(group)
            require((after.st_dev, after.st_ino) == (value.st_dev, value.st_ino),
                    'Cgroup changed during NVML mutation')
        finally:
            os.close(fd)

    def check_cleanup(self, identity):
        intent, group = self._current(identity, absent=True)
        pod = self.get_pod(intent)
        uid = pod['metadata']['uid'] if pod else None
        if uid == intent.pod_uid:
            self._pod(intent)  # spec and namespace still bound for a terminal Pod
        terminal = pod is not None and pod.get('status', {}).get('phase') in ('Succeeded', 'Failed')
        live = False
        used = False
        device = inode = None
        if group is not None:
            value = group.stat(); device, inode = value.st_dev, value.st_ino
            for candidate in [group, *(path for path in group.rglob('*') if path.is_dir())]:
                self.manual.safe_path(self.cg, '/' + str(candidate.relative_to(self.cg)))
                for file in ('cgroup.procs', 'cgroup.threads'):
                    live = live or bool((candidate / file).read_text().strip())
            events = dict(line.split() for line in (group / 'cgroup.events').read_text().splitlines())
            require(events.get('populated') in ('0', '1'), 'Actual recursive populated state required')
            live = live or events['populated'] == '1'
            value = self._raw(identity, group)
            require(not self._ambiguous(value), 'Unknown native usage cannot prove stop')
            used = value is not None and value['used'] != 0
        # Conservative qualification: any client on this GPU might retain an
        # imported allocation. Never infer ownership from NVML's PID alone.
        clients = bool(self.gpu_clients(identity.gpu_uuid)) or used
        return self.m.CleanupObservation(identity.epoch, uid, terminal, identity.cgroup_path,
            device, inode, group is not None, live, clients, True)

    def _receipt_path(self, identity):
        self._intent(identity)
        return self.state / 'receipts' / (identity.pod_uid + '.json')

    def read_gate(self, identity):
        return private_read(self._receipt_path(identity), self.uid)

    def seal_gate(self, identity, receipt):
        intent = self._intent(identity)
        require(self.observe(intent).identity == identity, 'Seal requires current blocked identity')
        require(receipt.get('protocol') == self.m.PROTOCOL and receipt.get('intent') == intent.to_dict()
                and receipt.get('identity') == identity.to_dict()
                and receipt.get('state') == 'sealed-before-user-init'
                and receipt.get('readback') == {'soft': intent.cap_bytes, 'hard': intent.cap_bytes},
                'Exact core sealed receipt required')
        require(self.read_limit(identity) == self.m.CapLimit(intent.cap_bytes, intent.cap_bytes),
                'Fresh exact native cap required at publication')
        self._current(identity)
        private_write(self._receipt_path(identity), receipt, self.uid, create=True)

    def revoke_gate(self, identity, expected):
        self._current(identity, absent=True)
        path = self._receipt_path(identity)
        require(private_read(path, self.uid) == expected, 'Foreign receipt must not be revoked')
        path.unlink()
        self._fsync_receipts()

    def _fsync_receipts(self):
        fd = os.open(self.state / 'receipts', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)

    def quarantine(self, identity, reason):
        # Health or epoch failure must not prevent UID-conditional stopping.
        intent = self._intent(identity)
        receipt = self.read_gate(identity)
        if receipt is not None:
            require(receipt.get('protocol') == self.m.PROTOCOL and receipt.get('intent') == intent.to_dict()
                    and receipt.get('identity') == identity.to_dict(), 'Foreign quarantine receipt retained')
            self._receipt_path(identity).unlink()
            self._fsync_receipts()
        pod = self.get_pod(intent)
        if pod is not None:
            require(pod['metadata']['uid'] == intent.pod_uid, 'Quarantine never deletes a replacement Pod')
            self.delete_pod(intent)  # API precondition must carry exact UID
        # No native limit mutation here, even if stop failed or is asynchronous.
