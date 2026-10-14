"""Inert-by-default transaction core for a single physical GPU per Pod.

This module has no Kubernetes, CRI or NVML implementation and cannot qualify
hardware. All backend operations must authenticate their supplied identity and
fail on uncertain continuity. See docs/native-gpu-controller.md before wiring a
privileged backend. A journal is exclusive mutation authority, never a lease.
"""
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields, replace
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
from typing import Protocol
import uuid


PROTOCOL = 'cps-native-gpu/v1'
MAX_LIMIT = (1 << 64) - 1
_STATES = {'prepared', 'applied', 'sealed', 'cleanup-prepared', 'cleaned', 'retired-inert-cap',
           'recovered-cleared-offline-cap'}
_SHA = re.compile(r'[a-f0-9]{64}')
_NAME = re.compile(r'[a-z0-9][a-z0-9.-]{0,252}')


class ControllerError(ValueError):
    """Protection remains in place; callers must not release a waiting gate."""


class ControllerDisabled(ControllerError):
    pass


class ControllerBusy(ControllerError):
    """Another process owns this journal's sole mutation lock; retry later."""


def _require(condition, message):
    if not condition:
        raise ControllerError(message)


def _uuid(value):
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _positive(value):
    return type(value) is int and value > 0


def _decode(cls, value):
    _require(isinstance(value, dict) and set(value) == {f.name for f in fields(cls)},
             'Exact ' + cls.__name__ + ' fields required')
    return cls(**value)


@dataclass(frozen=True)
class CapIntent:
    namespace: str
    name: str
    pod_uid: str
    node: str
    node_uid: str
    spec_sha256: str
    gpu_uuid: str
    cap_mib: int
    policy_hash: str

    def __post_init__(self):
        _require(all(isinstance(v, str) and _NAME.fullmatch(v) for v in
                     (self.namespace, self.name, self.node)), 'Exact Kubernetes references required')
        _require(_uuid(self.pod_uid) and _uuid(self.node_uid), 'Canonical Pod and node UUIDs required')
        _require(isinstance(self.spec_sha256, str) and _SHA.fullmatch(self.spec_sha256),
                 'Reviewed full Pod spec SHA256 required')
        _require(isinstance(self.gpu_uuid, str) and self.gpu_uuid.startswith('GPU-')
                 and _uuid(self.gpu_uuid[4:]), 'Exact physical GPU UUID required')
        _require(type(self.cap_mib) is int and self.cap_mib in (64, 128, 512, 5120, 10240, 20480),
                 'Reviewed integer MiB cap required')
        _require(isinstance(self.policy_hash, str) and self.policy_hash.startswith('sha256:')
                 and _SHA.fullmatch(self.policy_hash[7:]), 'Versioned policy SHA256 required')

    @property
    def cap_bytes(self):
        return self.cap_mib * 1048576

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class DriverEpoch:
    node_uid: str
    boot_id: str
    driver_generation: str
    gpu_uuid: str

    def __post_init__(self):
        _require(all(_uuid(v) for v in (self.node_uid, self.boot_id, self.driver_generation)),
                 'Trusted current node, boot and driver-maintenance epoch UUIDs required')
        _require(isinstance(self.gpu_uuid, str) and self.gpu_uuid.startswith('GPU-')
                 and _uuid(self.gpu_uuid[4:]), 'Exact physical GPU UUID required')


@dataclass(frozen=True)
class CapIdentity:
    pod_uid: str
    spec_sha256: str
    node_uid: str
    gpu_uuid: str
    container_id: str
    host_pid: int
    pid_start_ticks: int
    boot_id: str
    cgroup_relative: str
    cgroup_path: str
    cgroup_device: int
    cgroup_inode: int
    driver_generation: str

    def __post_init__(self):
        _require(_uuid(self.pod_uid), 'Canonical observed Pod UID required')
        _require(isinstance(self.spec_sha256, str) and _SHA.fullmatch(self.spec_sha256),
                 'Actual Pod spec SHA256 required')
        _require(isinstance(self.container_id, str) and _SHA.fullmatch(self.container_id),
                 'Exact first-init CRI container ID required')
        _require(_positive(self.host_pid) and _positive(self.pid_start_ticks),
                 'Actual first-init host PID and start ticks required')
        relative = self.cgroup_relative
        _require(isinstance(relative, str) and relative.startswith('/')
                 and not relative.startswith('//') and '..' not in relative.split('/')
                 and str(PurePosixPath(relative)) == relative, 'Canonical Pod cgroup path required')
        pattern = r'kubepods(?:-(?:besteffort|burstable))?-pod' + re.escape(self.pod_uid.replace('-', '_')) + r'\.slice'
        _require(re.fullmatch(pattern, PurePosixPath(relative).name), 'Actual Pod-parent UID required')
        _require(self.cgroup_path == '/sys/fs/cgroup' + relative, 'Actual host cgroup root required')
        _require(type(self.cgroup_device) is int and self.cgroup_device >= 0
                 and _positive(self.cgroup_inode), 'Actual cgroup device and inode required')
        self.epoch  # validate the maintenance epoch even for deserialized identities

    @property
    def epoch(self):
        return DriverEpoch(self.node_uid, self.boot_id, self.driver_generation, self.gpu_uuid)

    def require_intent(self, intent):
        _require(all(getattr(self, k) == getattr(intent, k) for k in
                     ('pod_uid', 'spec_sha256', 'node_uid', 'gpu_uuid')),
                 'Observed identity differs from reviewed intent')

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class CapLimit:
    soft: int
    hard: int

    def __post_init__(self):
        _require(type(self.soft) is int and type(self.hard) is int
                 and 0 <= self.soft <= self.hard <= MAX_LIMIT, 'Exact native integer limits required')

    @property
    def unlimited(self):
        return self.soft == 0 and self.hard == MAX_LIMIT


@dataclass(frozen=True)
class RetiredCapEntry:
    cgroup_id: int
    kernfs_id: int
    inode: int
    offline: bool
    pinned: bool
    default_hierarchy: bool
    soft: int
    hard: int
    used: int

    def __post_init__(self):
        _require(all(type(getattr(self, key)) is int and 0 <= getattr(self, key) <= MAX_LIMIT
                     for key in ('cgroup_id', 'kernfs_id', 'inode', 'soft', 'hard', 'used')),
                 'Exact uint64 inventory values required')
        _require(self.cgroup_id == self.kernfs_id == self.inode and self.inode > 0,
                 'Pinned cgroup/kernfs/inode identity required')
        _require(self.offline is True and self.pinned is True and self.default_hierarchy is True
                 and self.used == 0, 'Only offline pinned default-hierarchy zero-charge caps retire')
        CapLimit(self.soft, self.hard)


@dataclass(frozen=True)
class RetiredInertCap:
    identity: CapIdentity
    epoch: DriverEpoch
    gpu_id: int
    inventory_sha256: str
    entry: RetiredCapEntry

    def __post_init__(self):
        _require(type(self.identity) is CapIdentity and type(self.epoch) is DriverEpoch
                 and self.epoch == self.identity.epoch, 'Same typed driver epoch required for retirement')
        _require(type(self.gpu_id) is int and 0 <= self.gpu_id < (1 << 32), 'Exact uint32 GPU ID required')
        _require(isinstance(self.inventory_sha256, str)
                 and re.fullmatch(r'sha256:[a-f0-9]{64}', self.inventory_sha256),
                 'Fresh complete inventory SHA256 required')
        _require(type(self.entry) is RetiredCapEntry and self.entry.inode == self.identity.cgroup_inode,
                 'Original tracked cgroup inventory entry required')
        _require(not CapLimit(self.entry.soft, self.entry.hard).unlimited,
                 'Retirement retains a finite native cap; it never asserts unlimited')

    def require_limit(self, limit):
        _require(type(limit) is CapLimit and (self.entry.soft, self.entry.hard) == (limit.soft, limit.hard),
                 'Retired entry must retain the original exact finite cap')

    def to_dict(self):
        return {'protocol': 'cps-native-retired-inert-cap/v1', 'state': 'retired-inert-cap',
                **asdict(self)}

    @classmethod
    def from_dict(cls, value):
        _require(isinstance(value, dict) and set(value) ==
                 {'protocol', 'state', 'identity', 'epoch', 'gpu_id', 'inventory_sha256', 'entry'}
                 and value['protocol'] == 'cps-native-retired-inert-cap/v1'
                 and value['state'] == 'retired-inert-cap', 'Exact typed retirement proof required')
        return cls(_decode(CapIdentity, value['identity']), _decode(DriverEpoch, value['epoch']),
                   value['gpu_id'], value['inventory_sha256'], _decode(RetiredCapEntry, value['entry']))


def validate_retired_inventory(document, identity, limit):
    """Validate the complete guarded map; the host adapter supplies fresh epoch fences."""
    _require(type(identity) is CapIdentity and type(limit) is CapLimit, 'Typed original ownership required')
    _require(isinstance(document, dict) and set(document) ==
             {'version', 'backend', 'gpu_uuid', 'gpu_id', 'entries'}
             and type(document['version']) is int and document['version'] == 1
             and document['backend'] == 'misc-fallback' and document['gpu_uuid'] == identity.gpu_uuid,
             'Exact guarded physical GPU inventory required')
    _require(type(document['gpu_id']) is int and 0 <= document['gpu_id'] < (1 << 32)
             and isinstance(document['entries'], list) and len(document['entries']) <= 256,
             'Complete bounded GPU inventory required')
    seen, target = set(), None
    keys = {f.name for f in fields(RetiredCapEntry)}
    for row in document['entries']:
        _require(isinstance(row, dict) and set(row) == keys, 'Exact inventory row required')
        _require(all(type(row[k]) is int and 0 <= row[k] <= MAX_LIMIT
                     for k in ('cgroup_id', 'kernfs_id', 'inode', 'soft', 'hard', 'used'))
                 and all(type(row[k]) is bool for k in ('offline', 'pinned', 'default_hierarchy')),
                 'Typed inventory row required')
        _require(row['cgroup_id'] == row['kernfs_id'] == row['inode'] and row['inode'] > 0
                 and row['inode'] not in seen and row['pinned'] is True
                 and row['default_hierarchy'] is True, 'Consistent unique pinned hierarchy inventory required')
        CapLimit(row['soft'], row['hard'])
        seen.add(row['inode'])
        if row['inode'] == identity.cgroup_inode:
            target = _decode(RetiredCapEntry, row)
    _require(target is not None, 'Exact retained native cap entry missing')
    digest = 'sha256:' + hashlib.sha256(json.dumps(document, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    proof = RetiredInertCap(identity, identity.epoch, document['gpu_id'], digest, target)
    proof.require_limit(limit)
    return proof


@dataclass(frozen=True)
class CapObservation:
    identity: CapIdentity
    gate_blocked: bool
    user_started: bool
    healthy: bool
    descendants_unlimited: bool


@dataclass(frozen=True)
class OwnerObservation:
    epoch: DriverEpoch
    pod_uid: str | None
    spec_sha256: str | None
    cgroup_path: str
    cgroup_device: int | None
    cgroup_inode: int | None
    cgroup_exists: bool
    healthy: bool
    descendants_unlimited: bool


@dataclass(frozen=True)
class CleanupObservation:
    epoch: DriverEpoch
    pod_uid: str | None
    pod_terminal: bool
    cgroup_path: str
    cgroup_device: int | None
    cgroup_inode: int | None
    cgroup_exists: bool
    live_tasks: bool
    gpu_clients: bool
    healthy: bool


class NativeCapBackend(Protocol):
    """Privileged, conditional operations; errors or unknown state must raise.

    ``None`` from read_limit means positively established native UNSET, never
    unsupported NVML, a vanished generation, a permission error or a timeout.
    First-init observation validates the full Pod/CRI/proc/cgroup chain. Owner
    observation validates its surviving Pod-parent independently after PID1
    exits. Every mutation must revalidate ownership at its own boundary.
    """
    def observe(self, intent: CapIntent) -> CapObservation: ...
    def check_owner(self, identity: CapIdentity) -> OwnerObservation: ...
    def check_cleanup(self, identity: CapIdentity) -> CleanupObservation: ...
    def retired_inert_cap(self, identity: CapIdentity, limit: CapLimit) -> RetiredInertCap: ...
    def read_limit(self, identity: CapIdentity) -> CapLimit | None: ...
    def set_limit(self, identity: CapIdentity, limit: CapLimit) -> None: ...
    def read_gate(self, identity: CapIdentity) -> dict | None: ...
    def seal_gate(self, identity: CapIdentity, receipt: dict) -> None: ...
    def revoke_gate(self, identity: CapIdentity, expected: dict) -> None: ...
    def quarantine(self, identity: CapIdentity, reason: str) -> None: ...
    def recovery_fence(self, proof: 'ClearedOfflineRecovery'): ...
    def cleared_offline_recovery(self, identity: CapIdentity, original: 'CapRecord',
                                proof: 'ClearedOfflineRecovery') -> 'ClearedOfflineRecovery': ...


@dataclass(frozen=True)
class CapRecord:
    intent: CapIntent
    identity: CapIdentity
    state: str
    seal_id: str
    readback: CapLimit | None = None
    retirement: RetiredInertCap | None = None
    recovery: 'ClearedOfflineRecovery | None' = None

    def __post_init__(self):
        _require(type(self.intent) is CapIntent and type(self.identity) is CapIdentity,
                 'Typed durable intent and identity required')
        self.identity.require_intent(self.intent)
        _require(self.state in _STATES and _uuid(self.seal_id), 'Known journal state and seal UUID required')
        _require(self.readback is None or self.readback == self.limit, 'Exact journal cap readback required')
        _require(self.state not in ('applied', 'sealed') or self.readback == self.limit,
                 'Applied and sealed states require native readback')
        _require((self.state == 'retired-inert-cap') == (self.retirement is not None),
                 'Retired journal requires explicit typed inert-cap evidence')
        if self.retirement is not None:
            _require(type(self.retirement) is RetiredInertCap and self.retirement.identity == self.identity,
                     'Exact original retirement identity required')
            self.retirement.require_limit(self.limit)
        _require((self.state == 'recovered-cleared-offline-cap') == (self.recovery is not None),
                 'Recovered journal requires distinct operator evidence')
        if self.recovery is not None:
            _require(type(self.recovery) is ClearedOfflineRecovery
                     and self.recovery.original.intent == self.intent
                     and self.recovery.identity == self.identity
                     and self.recovery.original.seal_id == self.seal_id
                     and self.readback == self.recovery.original.readback,
                     'Exact original recovery transaction required')

    @property
    def limit(self):
        return CapLimit(self.intent.cap_bytes, self.intent.cap_bytes)

    def receipt(self):
        _require(self.recovery is None, 'Operator recovery can never authorize a user gate')
        _require(self.readback == self.limit, 'An unapplied cap cannot authorize a gate')
        return {'protocol': PROTOCOL, 'state': 'sealed-before-user-init', 'seal_id': self.seal_id,
                'intent': self.intent.to_dict(), 'identity': self.identity.to_dict(),
                'readback': asdict(self.readback)}

    def to_dict(self):
        value = {'schema': 1, 'protocol': PROTOCOL, 'state': self.state, 'seal_id': self.seal_id,
                'intent': self.intent.to_dict(), 'identity': self.identity.to_dict(),
                'readback': asdict(self.readback) if self.readback is not None else None}
        if self.retirement is not None:
            value['retirement'] = self.retirement.to_dict()
        if self.recovery is not None:
            value['recovery'] = self.recovery.to_dict()
        return value

    @classmethod
    def from_dict(cls, value):
        keys = {'schema', 'protocol', 'state', 'seal_id', 'intent', 'identity', 'readback'}
        _require(isinstance(value, dict) and set(value) in
                 (keys, keys | {'retirement'}, keys | {'recovery'}),
                 'Exact versioned private journal record required')
        _require(type(value['schema']) is int and value['schema'] == 1 and value['protocol'] == PROTOCOL,
                 'Unknown journal schema or native protocol')
        return cls(_decode(CapIntent, value['intent']), _decode(CapIdentity, value['identity']),
                   value['state'], value['seal_id'],
                   _decode(CapLimit, value['readback']) if value['readback'] is not None else None,
                   RetiredInertCap.from_dict(value['retirement']) if 'retirement' in value else None,
                   ClearedOfflineRecovery.from_dict(value['recovery']) if 'recovery' in value else None)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ClearedOfflineRecovery:
    """Operator exception evidence, never proof of normal finite retirement.

    The host operator supplies the complete fresh map and separate reviewed
    plan. This pure codec does not observe a host or authorize recovery alone.
    """
    original: CapRecord
    epoch: DriverEpoch
    gpu_id: int
    inventory_sha256: str
    entry: RetiredCapEntry
    binding_id: str
    attempt: str
    enrollment_uid: str
    enrollment_sha256: str
    journal_raw_sha256: str
    journal_sha256: str
    operation_id: str
    plan_sha256: str
    review_sha256: str

    def __post_init__(self):
        original = self.original
        _require(type(original) is CapRecord and original.state in ('cleanup-prepared', 'cleaned')
                 and original.readback == original.limit and not original.limit.unlimited
                 and original.retirement is None and original.recovery is None,
                 'Original finite applied cleanup transaction required')
        _require(type(self.epoch) is DriverEpoch and self.epoch == original.identity.epoch,
                 'Original current recovery epoch required')
        _require(type(self.gpu_id) is int and 0 <= self.gpu_id < (1 << 32), 'Exact recovery GPU ID required')
        _require(type(self.entry) is RetiredCapEntry and self.entry.inode == original.identity.cgroup_inode
                 and CapLimit(self.entry.soft, self.entry.hard).unlimited,
                 'Exact original offline zero-charge unlimited inventory entry required')
        for key in ('inventory_sha256', 'enrollment_sha256', 'journal_raw_sha256',
                    'journal_sha256', 'plan_sha256', 'review_sha256'):
            value = getattr(self, key)
            _require(isinstance(value, str) and re.fullmatch(r'sha256:[a-f0-9]{64}', value),
                     'Pinned recovery provenance required: ' + key)
        _require(isinstance(self.binding_id, str) and re.fullmatch(r'[a-f0-9]{60}', self.binding_id)
                 and isinstance(self.attempt, str) and 1 <= len(self.attempt) <= 256
                 and all(32 < ord(c) < 127 for c in self.attempt), 'Exact binding and attempt required')
        _require(all(_uuid(v) and uuid.UUID(v).int != 0 for v in
                     (self.enrollment_uid, self.operation_id)), 'Actual enrollment and recovery operation UUIDs required')
        raw = _canonical(original.to_dict())
        _require(self.journal_sha256 == _digest(raw)
                 and self.journal_raw_sha256 == _digest(raw + b'\n'),
                 'Original canonical and protected raw journal hashes required')

    @property
    def identity(self):
        return self.original.identity

    def to_dict(self):
        value = asdict(self)
        value['original'] = self.original.to_dict()
        return {'protocol': 'recovered-cleared-offline-cap/v1',
                'state': 'recovered-cleared-offline-cap', **value}

    @classmethod
    def from_dict(cls, value):
        keys = {f.name for f in fields(cls)}
        _require(isinstance(value, dict) and set(value) == keys | {'protocol', 'state'}
                 and value['protocol'] == 'recovered-cleared-offline-cap/v1'
                 and value['state'] == 'recovered-cleared-offline-cap',
                 'Exact distinct operator recovery proof required')
        original = value['original']
        _require(isinstance(original, dict) and 'recovery' not in original and 'retirement' not in original,
                 'Recovery must preserve a non-recovered original journal')
        data = {k: value[k] for k in keys}
        data.update(original=CapRecord.from_dict(original), epoch=_decode(DriverEpoch, value['epoch']),
                    entry=_decode(RetiredCapEntry, value['entry']))
        return cls(**data)


def validate_cleared_offline_inventory(document, original, *, binding_id, attempt,
        enrollment_uid, enrollment_sha256, journal_raw, operation_id, plan_sha256, review_sha256):
    """Pure complete-map codec; the backend must bind this map to Root's plan."""
    _require(type(original) is CapRecord and type(journal_raw) is bytes and len(journal_raw) <= 32768,
             'Bounded actual original journal bytes required')
    raw = _canonical(original.to_dict())
    _require(journal_raw == raw + b'\n', 'Exact protected original writer bytes required')
    _require(isinstance(document, dict) and set(document) ==
             {'version', 'backend', 'gpu_uuid', 'gpu_id', 'entries'}
             and type(document['version']) is int and document['version'] == 1
             and document['backend'] == 'misc-fallback'
             and document['gpu_uuid'] == original.identity.gpu_uuid
             and type(document['gpu_id']) is int and 0 <= document['gpu_id'] < (1 << 32)
             and isinstance(document['entries'], list) and 1 <= len(document['entries']) <= 256,
             'Complete bounded current physical GPU map required')
    target, seen = None, set()
    for row in document['entries']:
        entry = _decode(RetiredCapEntry, row)
        _require(entry.inode not in seen, 'Duplicate physical inventory entry denied')
        seen.add(entry.inode)
        if entry.inode == original.identity.cgroup_inode:
            target = entry
    _require(target is not None, 'Original orphan entry missing from complete map')
    return ClearedOfflineRecovery(original, original.identity.epoch, document['gpu_id'],
        _digest(_canonical(document)), target, binding_id, attempt, enrollment_uid, enrollment_sha256,
        _digest(journal_raw), _digest(raw), operation_id, plan_sha256, review_sha256)


def _unique_json(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value, 'Duplicate private journal JSON key')
        value[key] = item
    return value


class PrivateJournal:
    """Durable operator-owned0700 directory,0600 files and node-wide flock.

    All controller transactions hold this lock across backend mutations. The
    directory is independent of the gate's read-only receipt mount. Never put
    it in a user home, notebook image, shared workspace or network filesystem.
    """
    def __init__(self, directory: str | Path):
        self.directory = Path(directory).absolute()
        try:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._directory_safe()
        except OSError as error:
            raise ControllerError('Cannot initialize private native journal') from error

    def _directory_safe(self):
        value = self.directory.lstat()
        _require(stat.S_ISDIR(value.st_mode) and value.st_uid == os.geteuid()
                 and stat.S_IMODE(value.st_mode) == 0o700, 'Owned private0700 journal directory required')

    def path(self, pod_uid):
        _require(_uuid(pod_uid), 'Exact Pod UID journal key required')
        return self.directory / (pod_uid + '.json')

    @staticmethod
    def _fd_safe(fd):
        value = os.fstat(fd)
        _require(stat.S_ISREG(value.st_mode) and value.st_uid == os.geteuid()
                 and stat.S_IMODE(value.st_mode) == 0o600 and value.st_nlink == 1,
                 'Owned private0600 regular journal file required')

    @contextmanager
    def locked(self):
        self._directory_safe()
        fd = None
        try:
            fd = os.open(self.directory / '.writer.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            self._fd_safe(fd)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ControllerBusy('Native cap journal writer already active') from error
            yield
        except OSError as error:
            raise ControllerError('Unsafe or unavailable private journal lock') from error
        finally:
            if fd is not None:
                os.close(fd)

    def read(self, pod_uid):
        self._directory_safe()
        fd = None
        try:
            fd = os.open(self.path(pod_uid), os.O_RDONLY | os.O_NOFOLLOW)
            self._fd_safe(fd)
            with os.fdopen(fd, 'rb') as stream:
                fd = None
                raw = stream.read(32769)
            _require(len(raw) <= 32768, 'Private journal record exceeds bounded size')
            record = CapRecord.from_dict(json.loads(raw, object_pairs_hook=_unique_json))
            _require(record.intent.pod_uid == pod_uid, 'Journal filename/Pod UID mismatch')
            return record
        except FileNotFoundError:
            return None
        except (OSError, TypeError, KeyError, UnicodeError, json.JSONDecodeError) as error:
            raise ControllerError('Unsafe or invalid private native journal') from error
        finally:
            if fd is not None:
                os.close(fd)

    def write(self, record: CapRecord):
        self._directory_safe()
        _require(type(record) is CapRecord, 'Typed cap transaction required')
        # Validate any previous file before replacing it; reject links/foreign modes.
        self.read(record.intent.pod_uid)
        raw = (json.dumps(record.to_dict(), sort_keys=True, separators=(',', ':')) + '\n').encode()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.directory, prefix='.transaction-', delete=False) as stream:
                temporary = Path(stream.name)
                os.fchmod(stream.fileno(), 0o600)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path(record.intent.pod_uid))
            temporary = None
            fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError as error:
            raise ControllerError('Native journal durability failed; retain protection') from error
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def records(self):
        return tuple(self.read(path.stem) for path in sorted(self.directory.glob('*.json')))

    def recovery_original_path(self, proof):
        _require(type(proof) is ClearedOfflineRecovery, 'Typed recovery archive key required')
        return self.directory / 'recovery-originals' / (proof.original.intent.pod_uid + '.' + proof.operation_id + '.json')

    def _recovery_directory(self, *, create=False):
        self._directory_safe()
        path = self.directory / 'recovery-originals'
        if create:
            path.mkdir(mode=0o700, exist_ok=True)
        info = path.lstat()
        _require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
                 and stat.S_IMODE(info.st_mode) == 0o700, 'Private owned0700 recovery archive required')
        return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def _recovery_raw(self, fd, proof):
        with os.fdopen(fd, 'rb') as stream:
            self._fd_safe(stream.fileno())
            raw = stream.read(32769)
        _require(raw == _canonical(proof.original.to_dict()) + b'\n'
                 and _digest(raw) == proof.journal_raw_sha256,
                 'Exact preserved failed journal bytes required')
        return raw

    def read_recovery_original(self, proof):
        directory = self._recovery_directory()
        try:
            fd = os.open(self.recovery_original_path(proof).name,
                         os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            return self._recovery_raw(fd, proof)
        finally:
            os.close(directory)

    def preserve_recovery_original(self, proof):
        """Create once and fsync the exact original; never replace failure evidence."""
        fd = os.open(self.path(proof.original.intent.pod_uid), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        raw = self._recovery_raw(fd, proof)
        directory = self._recovery_directory(create=True)
        try:
            try:
                fd = os.open(self.recovery_original_path(proof).name,
                             os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
            except FileExistsError:
                _require(self.read_recovery_original(proof) == raw, 'Existing recovery archive changed')
            else:
                with os.fdopen(fd, 'wb') as stream:
                    self._fd_safe(stream.fileno())
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            os.fsync(directory)
            root = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(root)
            finally:
                os.close(root)
        finally:
            os.close(directory)
        return self.read_recovery_original(proof)


class NativeCapController:
    production_qualified = False

    def __init__(self, backend: NativeCapBackend, journal: PrivateJournal, *,
                 enabled: bool = False, qualification_only: bool = True):
        _require(type(enabled) is bool and type(qualification_only) is bool,
                 'Explicit boolean native controller settings required')
        _require(qualification_only, 'Native controller is qualification-only')
        self.backend, self.journal, self.enabled = backend, journal, enabled

    def _enabled(self):
        if not self.enabled:
            raise ControllerDisabled('Native GPU cap controller is disabled')

    @staticmethod
    def _healthy(observation):
        _require(observation.healthy is True, 'Current native driver/guard health required')

    def _fresh(self, intent, identity=None):
        observation = self.backend.observe(intent)
        _require(type(observation) is CapObservation and type(observation.identity) is CapIdentity,
                 'Typed current first-init identity required')
        observation.identity.require_intent(intent)
        if identity is not None:
            _require(observation.identity == identity, 'Pod/PID/cgroup/driver identity changed')
        self._healthy(observation)
        _require(observation.gate_blocked is True and observation.user_started is False,
                 'Trusted first init must remain blocked before any user init or main starts')
        _require(observation.descendants_unlimited is True, 'Descendant native overrides denied')
        return observation.identity

    def _read_limit(self, identity):
        value = self.backend.read_limit(identity)
        _require(value is None or type(value) is CapLimit, 'Unknown native readback denied')
        return value

    @staticmethod
    def _unlimited(value):
        return value is None or value.unlimited

    def _exact_limit(self, record):
        value = self._read_limit(record.identity)
        _require(value == record.limit, 'Native cap drift; retain protection and quarantine')
        return value

    @staticmethod
    def _epoch_and_group(identity, observation):
        _require(type(observation.epoch) is DriverEpoch and observation.epoch == identity.epoch,
                 'Driver/node/boot maintenance epoch changed or missing')
        _require(observation.cgroup_path == identity.cgroup_path, 'Tracked cgroup path changed')
        _require(type(observation.cgroup_exists) is bool, 'Actual cgroup existence required')
        if observation.cgroup_exists:
            _require(type(observation.cgroup_device) is int and type(observation.cgroup_inode) is int
                     and observation.cgroup_device == identity.cgroup_device
                     and observation.cgroup_inode == identity.cgroup_inode,
                     'Tracked cgroup inode/device changed')

    def _owner(self, record):
        observation = self.backend.check_owner(record.identity)
        _require(type(observation) is OwnerObservation, 'Typed lifetime ownership proof required')
        self._epoch_and_group(record.identity, observation)
        self._healthy(observation)
        _require(observation.cgroup_exists and observation.pod_uid == record.intent.pod_uid
                 and observation.spec_sha256 == record.intent.spec_sha256,
                 'Exact surviving Pod-parent/spec ownership required')
        _require(observation.descendants_unlimited is True, 'Descendant native override detected')

    def _deliver(self, record):
        # The private sealed journal records an authorized delivery before the
        # public gate can advance. A crash at either side of publication resumes.
        _require(self.backend.read_gate(record.identity) is None, 'Unexpected existing gate receipt')
        self._fresh(record.intent, record.identity)
        self._exact_limit(record)  # last operation before conditional atomic seal
        self.backend.seal_gate(record.identity, record.receipt())

    def reconcile(self, intent: CapIntent) -> CapRecord:
        """Apply before user init, or verify a sealed live workload on every call.

        This never changes a sealed cap. Any uncertain sealed state invokes the
        backend's quarantine callback; the callback must block/stop the expected
        Pod, invalidate access and preserve driver limits until confirmed stop.
        """
        self._enabled()
        _require(type(intent) is CapIntent, 'Trusted typed cap intent required')
        with self.journal.locked():
            record = self.journal.read(intent.pod_uid)
            try:
                if record is not None:
                    _require(record.intent == intent, 'Existing journal intent differs')
                    _require(record.state not in ('cleanup-prepared', 'cleaned', 'retired-inert-cap',
                                                  'recovered-cleared-offline-cap'),
                             'Cleaning/cleaned Pod cannot be released again')
                if record is not None and record.state == 'sealed':
                    self._owner(record)
                    self._exact_limit(record)
                    receipt = self.backend.read_gate(record.identity)
                    if receipt is not None:
                        _require(receipt == record.receipt(), 'Foreign or stale gate receipt')
                    else:
                        self._deliver(record)
                    return record
                identity = self._fresh(intent, record.identity if record else None)
                _require(self.backend.read_gate(identity) is None, 'Unowned or stale gate receipt')
                value = self._read_limit(identity)
                if record is None:
                    _require(self._unlimited(value), 'Existing unowned native cap must not be adopted')
                    record = CapRecord(intent, identity, 'prepared', str(uuid.uuid4()))
                    self.journal.write(record)  # durable authority before any possible set
                if record.state == 'prepared':
                    _require(self._unlimited(value) or value == record.limit,
                             'Prepared native cap drift; foreign limit must not be reset')
                    if self._unlimited(value):
                        self.backend.set_limit(identity, record.limit)
                    self._fresh(intent, identity)
                    readback = self._exact_limit(record)
                    record = replace(record, state='applied', readback=readback)
                    self.journal.write(record)
                else:
                    self._exact_limit(record)
                record = replace(record, state='sealed')
                self.journal.write(record)
                self._deliver(record)
                return record
            except Exception as error:
                if record is not None and record.state == 'sealed':
                    try:
                        self.backend.quarantine(record.identity, str(error))
                    except Exception as quarantine_error:
                        raise ControllerError('Native quarantine failed; protection retained: ' + str(error)) from quarantine_error
                raise

    def _cleanup_proof(self, record):
        observation = self.backend.check_cleanup(record.identity)
        _require(type(observation) is CleanupObservation, 'Typed confirmed-stop proof required')
        self._epoch_and_group(record.identity, observation)
        self._healthy(observation)
        _require(observation.pod_uid is None or
                 (observation.pod_uid == record.intent.pod_uid and observation.pod_terminal is True),
                 'Cleanup requires expected Pod gone or terminal; replacements denied')
        _require(observation.live_tasks is False, 'Original cgroup tasks remain; retain native protection')
        if not observation.cgroup_exists:
            _require(observation.pod_uid is None, 'Retirement requires actual Pod absence')
            self._retired_proof(record)  # exact pinned zero-charge entry, even with unrelated peers
        else:
            _require(observation.gpu_clients is False,
                     'Live GPU/import/MPS clients remain; retain native protection')
        return observation

    def _retired_proof(self, record):
        proof = self.backend.retired_inert_cap(record.identity, record.limit)
        _require(type(proof) is RetiredInertCap and proof.identity == record.identity,
                 'Fresh typed original retained-cap proof required')
        proof.require_limit(record.limit)
        return proof

    def _cleanup_limit(self, record, observation):
        if not observation.cgroup_exists:
            return self._retired_proof(record)
        value = self._read_limit(record.identity)
        _require(self._unlimited(value) or value == record.limit,
                 'Cleanup native cap drift; foreign limit must not be reset')
        return value

    def _owned_receipt(self, record):
        receipt = self.backend.read_gate(record.identity)
        if receipt is not None:
            _require(record.state in ('sealed', 'cleanup-prepared')
                     and record.readback is not None and receipt == record.receipt(),
                     'Foreign cleanup gate receipt must not be removed')
        return receipt

    def cleanup(self, intent: CapIntent) -> CapRecord:
        """Revoke, then clear or retire only after exact fresh accounting proof.

        No deadline, receipt age, lease expiry or cancellation request is stop
        evidence. A removed cgroup is retired without resetting a path which
        might later name a replacement. Cleared and retired journals remain as
        distinct tombstones; retirement preserves the original finite cap.
        """
        self._enabled()
        _require(type(intent) is CapIntent, 'Trusted typed cap intent required')
        with self.journal.locked():
            record = self.journal.read(intent.pod_uid)
            _require(record is not None and record.intent == intent, 'Exact durable cap ownership required')
            _require(record.recovery is None, 'Recovered exception requires explicit operator revalidation')
            if record.state in ('cleaned', 'retired-inert-cap'):
                observation = self._cleanup_proof(record)
                self._cleanup_limit(record, observation)
                _require(self.backend.read_gate(record.identity) is None, 'Terminal cleanup gate must remain absent')
                if observation.cgroup_exists:
                    _require(record.state == 'cleaned', 'Retired cgroup path has been replaced')
                    return record
                if record.state == 'retired-inert-cap':
                    return record  # immutable original provenance; fresh proof above is mandatory
                record = replace(record, state='retired-inert-cap', retirement=self._retired_proof(record))
                self.journal.write(record)
                return record
            observation = self._cleanup_proof(record)
            self._cleanup_limit(record, observation)
            self._owned_receipt(record)
            record = replace(record, state='cleanup-prepared')
            self.journal.write(record)  # prohibit any subsequent user-gate release
            observation = self._cleanup_proof(record)
            self._cleanup_limit(record, observation)
            receipt = self._owned_receipt(record)
            if receipt is not None:
                self.backend.revoke_gate(record.identity, receipt)
            observation = self._cleanup_proof(record)
            value = self._cleanup_limit(record, observation)
            if observation.cgroup_exists and not self._unlimited(value):
                self.backend.set_limit(record.identity, CapLimit(0, MAX_LIMIT))
                _require(self._unlimited(self._read_limit(record.identity)), 'Native cleanup readback failed')
                self._cleanup_proof(record)
            observation = self._cleanup_proof(record)
            value = self._cleanup_limit(record, observation)
            if not observation.cgroup_exists:
                record = replace(record, state='retired-inert-cap', retirement=value)
            else:
                _require(self._unlimited(value), 'Fresh positive native unlimited readback required')
                record = replace(record, state='cleaned')
            self.journal.write(record)
            return record

    def _recovery_observation(self, proof):
        original = proof.original
        observed = self.backend.check_cleanup(original.identity)
        _require(type(observed) is CleanupObservation, 'Typed operator absence observation required')
        self._epoch_and_group(original.identity, observed)
        self._healthy(observed)
        _require(observed.pod_uid is None and observed.cgroup_exists is False
                 and observed.live_tasks is False and observed.gpu_clients is False,
                 'Operator recovery requires actual Pod/cgroup absence and no live tasks/clients')
        _require(self.backend.read_gate(original.identity) is None, 'Recovery gate must remain revoked')

    def recover_cleared_offline(self, intent, proof, *, operator_approved=False):
        """Explicit exception only; never SET a limit, recreate a path or release a gate.

        The required backend fence holds driver/maintenance locks plus reviewed
        writer/allocation-release exclusion for the entire transaction. Each
        backend proof must freshly revalidate Root's exact complete-map plan,
        immutable enrollment/ledger and operation/review provenance. A boolean
        or a pure deserialized proof alone cannot substitute for these checks.
        Successful fence exit must publish the immutable recovery audit and
        cleanup/tombstone while all three locks and release exclusion remain held.
        """
        self._enabled()
        _require(operator_approved is True, 'Explicit operator recovery approval required')
        _require(type(intent) is CapIntent and type(proof) is ClearedOfflineRecovery
                 and proof.original.intent == intent, 'Exact typed recovery ownership required')
        with self.journal.locked(), self.backend.recovery_fence(proof):
            current = self.journal.read(intent.pod_uid)
            terminal = replace(proof.original, state='recovered-cleared-offline-cap', recovery=proof)
            _require(current == proof.original or current == terminal,
                     'Current protected journal differs from reviewed original recovery')
            if current == terminal:
                self.journal.read_recovery_original(proof)
            for iteration in range(2):
                self._recovery_observation(proof)
                fresh = self.backend.cleared_offline_recovery(proof.identity, proof.original, proof)
                _require(type(fresh) is ClearedOfflineRecovery and fresh == proof,
                         'Fresh complete recovery proof changed or was not authenticated')
                self._recovery_observation(proof)
                if iteration == 0 and current == proof.original:
                    self.journal.preserve_recovery_original(proof)
            _require(self.journal.read(intent.pod_uid) == current, 'Original recovery journal changed during fences')
            self.journal.read_recovery_original(proof)
            if current != terminal:
                self.journal.write(terminal)
            return terminal

    def tracked(self) -> tuple[CapIntent, ...]:
        """Pending journals for a host loop; iteration has no GPU/receipt effects."""
        with self.journal.locked():
            return tuple(record.intent for record in self.journal.records()
                         if record.state not in ('cleaned', 'retired-inert-cap', 'recovered-cleared-offline-cap'))
