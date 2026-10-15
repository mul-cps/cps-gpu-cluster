"""Closed, offline contracts for a future 5/10/20 GiB qualification matrix."""
import datetime as dt
import hashlib
import json
import re

SOURCE = '40b9525097776e0d5927242ca625a27dadbd797c'
IMAGE = ('ghcr.io/mul-cps/cps-compute:qualification-40b9525@sha256:'
         'b3802a7f70077ff56adbc060d1177409eeff76c8b3cf8ccf9f39047c1e6716bf')
WHEEL_SHA = '8321127b7db5f6554ddde60f9bb916a7414d570a3405c209632dd142210fe0f4'
MODULE_SHA = '93f4e01c3682e52192d43c130073b3daf50c59ea7bd06342971f5f4add0a2b68'
UID, GID = 1000, 100
DAEMON_UID = '4cb8c92b-95a7-4a30-9d62-bc17bb542941'
DAEMON_IMAGE = 'nvcr.io/nvidia/k8s-device-plugin@sha256:2d16df5f3f12081b4bd6b317cf697e5c7a195c53cec7e0bab756db02a06b985c'
ROLES = {'peer5': 5, 'workspace10': 10, 'workspace20': 20}
QUOTAS = {5: {'globalMiB': 5324, 'portion': '0.13'},
          10: {'globalMiB': 10240, 'portion': '0.25'},
          20: {'globalMiB': 20480, 'portion': '0.5'}}
ALLOCATIONS = {5: 3072, 10: 6144, 20: 12288}
HOLD_ALLOCATIONS = {5: [4096], 10: [9216, 64], 20: [19456, 64]}
HOLD_SECONDS, ROUNDS = 20, 16


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def sha(value):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) is not None


def instant(value):
    value = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(value.tzinfo is not None, 'Timezone-aware receipt required')
    return value


def validate_reference(reference, preflight, *, now=None):
    """A fresh UID1000 server must be observed, never inferred from old UID10001."""
    now = now or dt.datetime.now(dt.timezone.utc)
    require(set(reference) == {'schemaVersion','observedAt','nodeUid','daemon','controller','server',
                              'defaults','uidCompatibilityEvidenceSha256'}, 'Closed MPS reference schema required')
    require(reference['schemaVersion'] == 1 and 0 <= (now-instant(reference['observedAt'])).total_seconds() <= 900,
            'Fresh MPS reference within 15 minutes required')
    require(reference['nodeUid'] == preflight['node']['uid'], 'MPS reference node identity differs')
    require(preflight['node'].get('ready') is True, 'Observed node Ready condition required')
    daemon = reference['daemon']
    require(set(daemon) == {'namespace','name','uid','resourceVersion','image'}, 'Closed daemon identity required')
    require(daemon['namespace'] == 'gpu-operator' and daemon['name'] == 'mps-control-daemon-standalone-m2587'
            and daemon['uid'] == DAEMON_UID and daemon['image'] == DAEMON_IMAGE
            and isinstance(daemon['resourceVersion'],str) and daemon['resourceVersion'], 'Reviewed daemon identity required')
    controller = reference['controller']
    require(set(controller) == {'pid','uid','command'} and type(controller['pid']) is int and controller['pid'] > 0
            and controller['uid'] == 0 and controller['command'] == ['nvidia-cuda-mps-control','-d'],
            'Existing root controller without multiuser mode required')
    server = reference['server']
    require(set(server) == {'pid','startTimeTicks','uid','status','clients','deviceMemoryLimitsMiB','activeThreadPercentage'},
            'Closed observed server identity/settings required')
    require(all(type(server[k]) is int and server[k] > 0 for k in ('pid','startTimeTicks')) and server['uid'] == UID
            and server['status'] == 'ACTIVE' and server['clients'] == [],
            'Fresh idle ACTIVE UID1000 server required; historical UID10001 is unsupported')
    observations = preflight['mpsServers']
    require(len(observations) == len(preflight['gpus']) and
            {s.get('gpuUuid') for s in observations} == {g['uuid'] for g in preflight['gpus']} and
            all(s.get('pid') == server['pid'] and s.get('ready') is True for s in observations),
            'Both physical-card inventory receipts must bind the same fresh UID1000 server PID')
    gpu_ids = {g['uuid'] for g in preflight['gpus']}
    require(server['deviceMemoryLimitsMiB'] == dict.fromkeys(gpu_ids,5120) and server['activeThreadPercentage'] == 12,
            'Observed original active 5GiB/thread12 settings required')
    require(reference['defaults'] == {'deviceMemoryLimitsMiB': {'0':5120,'1':5120}, 'activeThreadPercentage':12},
            'Original daemon defaults must remain 5GiB/thread12')
    require(sha(reference['uidCompatibilityEvidenceSha256']), 'Separate reviewed UID1000 compatibility evidence required')
    return reference


def validate_maintenance_review(value, reference, preflight):
    """Bind approvals to a separately reviewed candidate; this performs no writes."""
    fields = {'status','candidateSha256','reviewSha256','server','daemonUid','daemonResourceVersion',
              'activeDeviceMemoryLimitsMiB','activeThreadPercentage','defaults','maxWindowSeconds',
              'uidCompatibilityEvidenceSha256'}
    require(set(value) == fields and value['status'] == 'reviewed-offline-candidate',
            'Closed separately reviewed UID1000 maintenance candidate required')
    require(sha(value['candidateSha256']) and sha(value['reviewSha256']) and
            value['candidateSha256'] != value['reviewSha256'], 'Distinct candidate and review hashes required')
    require(value['server'] == {k:reference['server'][k] for k in ('pid','startTimeTicks','uid')} and
            value['daemonUid'] == reference['daemon']['uid'] and
            value['daemonResourceVersion'] == reference['daemon']['resourceVersion'] and
            value['uidCompatibilityEvidenceSha256'] == reference['uidCompatibilityEvidenceSha256'],
            'Separate review must bind the fresh UID1000 server and daemon')
    require(value['activeDeviceMemoryLimitsMiB'] == dict.fromkeys((g['uuid'] for g in preflight['gpus']),40960)
            and type(value['activeThreadPercentage']) is int and value['activeThreadPercentage'] == 100
            and value['defaults'] == reference['defaults'] and type(value['maxWindowSeconds']) is int
            and value['maxWindowSeconds'] == 180, 'Only temporary40GiB/thread100 with unchanged defaults is reviewed')
    return value


def validate_approval(value, proof, role, pod_uid, *, now=None, require_fresh=True):
    now = now or dt.datetime.now(dt.timezone.utc)
    fields = {'runtimeReviewed','allGatesReviewed','role','podUid','podUids','runId','nodeUid','uid','gid','gpuUuid',
              'probeSha256','compilerWheelSha256','hamiSha256','mps'}
    require(set(value) == fields, 'Closed runtime/MPS approval marker required')
    require(value['runtimeReviewed'] is True and value['allGatesReviewed'] is True and
            value['role'] == role and value['podUid'] == pod_uid and value['runId'] == proof['runId'] and
            value['nodeUid'] == proof['nodeUid'] and (value['uid'],value['gid']) == (UID,GID) and
            value['gpuUuid'] in proof['gpuUuidAllowlist'] and value['probeSha256'] == proof['probeSha256'] and
            value['compilerWheelSha256'] == WHEEL_SHA and value['hamiSha256'] == proof['hami']['sha256'],
            'Runtime approval identity/source binding changed')
    pods = value['podUids']
    require(isinstance(pods,list) and len(pods)==3 and len(set(pods))==3 and pod_uid in pods and
            all(isinstance(uid,str) and uid for uid in pods), 'All three distinct gated Pod identities required')
    mps = value['mps'];reference = proof['mpsReference'];server = reference['server']
    require(set(mps) == {'candidateSha256','reviewSha256','observedAt','windowEndsAtNs','server',
                        'activeDeviceMemoryLimitsMiB','activeThreadPercentage','defaults',
                        'daemonUid','daemonResourceVersion','uidCompatibilityEvidenceSha256'}, 'Closed temporary MPS receipt required')
    review = proof['mpsMaintenanceReview']
    require(mps['candidateSha256'] == review['candidateSha256'] and mps['reviewSha256'] == review['reviewSha256'],
            'Temporary readback must bind the separately reviewed candidate hashes')
    require(mps['server'] == {k:server[k] for k in ('pid','startTimeTicks','uid')} and
            mps['daemonUid'] == reference['daemon']['uid'] and mps['daemonResourceVersion'] == reference['daemon']['resourceVersion'] and
            mps['uidCompatibilityEvidenceSha256'] == reference['uidCompatibilityEvidenceSha256'],
            'Fresh reviewed server/daemon/compatibility identity changed')
    require(mps['activeDeviceMemoryLimitsMiB'] == dict.fromkeys(proof['gpuUuidAllowlist'],40960) and
            type(mps['activeThreadPercentage']) is int and mps['activeThreadPercentage'] == 100 and
            mps['defaults'] == reference['defaults'], 'Reviewed temporary active ceilings with unchanged defaults required')
    observed = instant(mps['observedAt'])
    require(type(mps['windowEndsAtNs']) is int and 0 < mps['windowEndsAtNs']-int(observed.timestamp()*1e9) <= 180*10**9,
            'Independent MPS maintenance window must be at most 180 seconds')
    if require_fresh:
        require(0 <= (now-observed).total_seconds() <= 15 and int(now.timestamp()*1e9) < mps['windowEndsAtNs'],
                'Fresh active-server readback and unexpired review window required')
    return value
