#!/usr/bin/env python3
"""Compile the shared policy without cluster access or third-party dependencies."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
NATIVE_GROUP_PROFILE = 'interactive-shared-5'
NATIVE_GROUP_WORKLOAD = 'ghcr.io/mul-cps/cps-jupyter-notebook:qualification-native-group-980408a@sha256:9167861058c1364c58d1c2fca0d6f536c3ffb53a33800dcdb9a1560f14ca4dc0'
NATIVE_GROUP_GATE = 'ghcr.io/mul-cps/cps-compute@sha256:bc5b128f582641eae8395e1121d1fb248eddc39a56c9e863b7c564badd94b167'
NATIVE_GROUP_POOL = {'node':'k3s-wk-gpu2','node_uid':'3336cdd5-d245-436e-b57c-2f66c6dcaa41',
                    'gpu_uuid':'GPU-16128952-b438-556a-00bb-93039ee24e56','max_workspaces':2}
NATIVE_GROUP_PINS = {'core_sha256':'4fdcafcdf7f57b9de81f56e8e17db06a91e27680c6a711f3888fd0b76da46421',
    'uvm_sha256':'b2ae67722e9e21a70c319aeed2184f5b2d1f23b8e32dea00816cfd5cd2c3ee61',
    'health_sha256':'52fdbdae3d5e2f66fd4653d94ef5a62f734e185fabec30450f4a1b70cfee7d67'}
NATIVE_GROUP_GATES = frozenset({'cap-assignment','oom-peer','aggregate','memory-import','restart-cleanup','mps'})


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def _native_require(ok, message):
    if not ok:
        raise ValueError('native group qualification: '+message)


def _decode_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _native_require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def validate_native_group_evidence(evidence, policy_hash, policy_version, artifacts):
    """Match the released NativeGroupDeployment proof and read all six gate files.

    This is an explicit operator input. Hardware truth and semantic equivalence
    of historical receipts require independent operator review; a compiler
    cannot create that authority from filenames or checksums.
    """
    fields = {'version','policy_hash','policy_version','node_pool','core_sha256','uvm_sha256',
              'health_sha256','gate_image','workload_image','gates'}
    version = evidence.get('version') if type(evidence) is dict else None
    if type(version) is int and version == 2:
        fields |= {'profile_caps', 'capacity_evidence_sha256'}
    _native_require(type(evidence) is dict and set(evidence) == fields, 'exact deployment evidence fields required')
    _native_require(type(version) is int and version in (1, 2)
        and evidence['policy_hash'] == policy_hash and evidence['policy_version'] == policy_version,
        'exact target policy/version required')
    if version == 1:
        _native_require(type(evidence['node_pool']) is dict and evidence['node_pool'] == NATIVE_GROUP_POOL
            and type(evidence['node_pool']['max_workspaces']) is int, 'exact bounded selected pool required')
        caps = {NATIVE_GROUP_PROFILE: 5120}
    else:
        pool = evidence['node_pool']
        pool_fields = set(NATIVE_GROUP_POOL) | {'total_memory_mib', 'free_memory_mib',
            'headroom_mib', 'memory_budget_mib', 'boot_id', 'driver_generation'}
        _native_require(type(pool) is dict and set(pool) == pool_fields
            and all(pool[k] == NATIVE_GROUP_POOL[k] for k in ('node', 'node_uid', 'gpu_uuid')),
            'exact measured selected pool required')
        _native_require(all(type(pool[k]) is int for k in ('max_workspaces', 'total_memory_mib',
            'free_memory_mib', 'headroom_mib', 'memory_budget_mib'))
            and 1 <= pool['max_workspaces'] <= 32 and 0 < pool['total_memory_mib'] <= 40960
            and 0 < pool['free_memory_mib'] <= pool['total_memory_mib'] and pool['headroom_mib'] >= 1024
            and 0 < pool['memory_budget_mib'] <= pool['free_memory_mib'] - pool['headroom_mib'],
            'memory budget must fit measured free memory minus headroom')
        for key in ('boot_id', 'driver_generation'):
            try:
                identity = UUID(pool[key])
                _native_require(str(identity) == pool[key] and identity.int != 0, 'exact measured epoch required')
            except (ValueError, TypeError, AttributeError):
                raise ValueError('native group qualification: exact measured epoch required') from None
        caps = evidence['profile_caps']
        expected = {f'interactive-shared-{size}': size * 1024 for size in (5, 10, 20)}
        _native_require(type(caps) is dict and 1 <= len(caps) <= 3
            and all(k in expected and type(v) is int and v == expected[k]
                and v <= pool['memory_budget_mib'] for k, v in caps.items()),
            'exact measured 5/10/20 GiB profile caps required')
    _native_require(all(evidence[k] == v for k,v in NATIVE_GROUP_PINS.items())
        and evidence['workload_image'] == NATIVE_GROUP_WORKLOAD
        and evidence['gate_image'] == NATIVE_GROUP_GATE, 'exact tested native driver/image pins required')
    gates = evidence['gates']
    _native_require(type(gates) is dict and set(gates) == NATIVE_GROUP_GATES
        and type(artifacts) is dict and set(artifacts) == NATIVE_GROUP_GATES | ({'capacity'} if version == 2 else set()),
        'all acceptance records and artifact paths required')
    receipts = dict(gates)
    if version == 2:
        receipts['capacity'] = {'passed': True, 'evidence_sha256': evidence['capacity_evidence_sha256']}
    for gate, entry in receipts.items():
        _native_require(type(entry) is dict and set(entry) == {'passed','evidence_sha256'}
            and entry['passed'] is True and isinstance(entry['evidence_sha256'],str)
            and re.fullmatch(r'sha256:[a-f0-9]{64}',entry['evidence_sha256'])
            and entry['evidence_sha256'] != 'sha256:'+'0'*64, 'passed checksummed '+gate+' required')
        _native_require(isinstance(artifacts[gate], (str,Path)), 'local gate artifact path required')
        fd = os.open(artifacts[gate], os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            _native_require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) in (0o400,0o600) and info.st_uid == os.geteuid()
                and 0 < info.st_size <= 2*1024*1024, 'private bounded regular gate artifact required')
            raw = os.read(fd, 2*1024*1024+1); after = os.fstat(fd)
            _native_require(len(raw) == info.st_size
                and all(getattr(info,k) == getattr(after,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
                and 'sha256:'+hashlib.sha256(raw).hexdigest() == entry['evidence_sha256'], 'missing or altered '+gate+' artifact')
        finally:
            os.close(fd)
        report = _decode_json(raw)
        _native_require(type(report) is dict and report.get('gate') == gate and report.get('passed') is True
            and report.get('policy_hash') == policy_hash and report.get('policy_version') == policy_version,
            'gate report must bind the exact qualified target policy/version')
    return caps


def _native_group_profile(profile, version, cap_mib=5120, proof_version=1):
    expected_gpu = {'mode':'shared','nominalMemoryGiB':cap_mib // 1024,'qualification':{
        'mechanism':'r615-native-cgroup-managed-deny','status':'qualified-group',
        'policyVersion':version,'evidence':[f'native-groups-v{proof_version}']}}
    return (type(profile.get('enabled')) is bool and profile['enabled'] is True
        and profile.get('kind') == profile.get('queue') == 'interactive'
        and profile.get('cpu') == '4' and profile.get('memory') == '16Gi'
        and profile.get('images') == [NATIVE_GROUP_WORKLOAD]
        and type(profile.get('gpu')) is dict and profile['gpu'] == expected_gpu
        and type(profile['gpu']['nominalMemoryGiB']) is int)


def validate_evidence(evidence, policy_hash):
    """Require policy-bound qualification and verify every local evidence artifact."""
    if evidence.get('policyHash') != policy_hash or evidence.get('passed') is not True:
        raise ValueError('qualification must pass for the exact policy hash')
    required = {'identity-storage', 'authorization', 'permissions', 'collaboration', 'pooling',
                'notebook-jobs', 'isolation', 'scheduling', 'startup', 'defragmentation',
                'recovery', 'moodle-scaffold'}
    if set(evidence.get('scenarios', [])) != required:
        raise ValueError('all acceptance scenarios require independent evidence')
    if not evidence.get('artifacts'):
        raise ValueError('qualification requires evidence artifacts')
    verified = {}
    for artifact in evidence['artifacts']:
        path = Path(artifact['path'])
        if not path.is_file():
            raise ValueError('missing or altered qualification artifact')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != artifact['sha256']:
            raise ValueError('missing or altered qualification artifact')
        resolved = str(path.resolve())
        if resolved in verified:
            raise ValueError('duplicate qualification artifact')
        verified[resolved] = data
    reports = evidence.get('scenarioReports')
    if not isinstance(reports, dict) or set(reports) != required:
        raise ValueError('every acceptance scenario requires a checksummed production report')
    used = set()
    for scenario, reference in reports.items():
        if not isinstance(reference, str):
            raise ValueError('scenario report path required')
        resolved = str(Path(reference).resolve())
        if resolved not in verified or resolved in used:
            raise ValueError('scenario reports must be distinct verified artifacts')
        used.add(resolved)
        try:
            report = json.loads(verified[resolved])
        except (ValueError, UnicodeError):
            raise ValueError('scenario qualification report must be JSON') from None
        if (not isinstance(report, dict) or report.get('scenario') != scenario
                or report.get('policyHash') != policy_hash or report.get('passed') is not True
                or report.get('qualifiedScope') != 'production'):
            raise ValueError('scenario requires passed production qualification for the exact policy')


def compile_catalog(catalog, *, native_group_evidence=None, native_group_artifacts=None):
    native = native_group_evidence is not None or native_group_artifacts is not None
    native_caps = {}
    if native:
        native_caps = validate_native_group_evidence(native_group_evidence,
            'sha256:'+hashlib.sha256(canonical(catalog)).hexdigest(), catalog.get('version'), native_group_artifacts)
        for name, cap_mib in native_caps.items():
            _native_require(_native_group_profile(catalog.get('profiles',{}).get(name,{}), catalog.get('version'),
                cap_mib, native_group_evidence['version']), 'exact qualified profile contract required: ' + name)
    if catalog.get('schemaVersion') != 1 or not re.fullmatch(r'\d+\.\d+\.\d+', catalog.get('version', '')):
        raise ValueError('unsupported schema or invalid policy version')
    if catalog['priorities'] != {'exam':90,'lecture':80,'ta':70,'research':60,'project':50,'homework':40,'batch':10,'ci':5}:
        raise ValueError('priority convention differs from the reviewed v1 policy')
    if catalog.get('workloadScheduling') != {'interactive': {'queue':'cps-interactive','priorityClassName':'cps-homework'}, 'batch': {'queue':'cps-batch','priorityClassName':'cps-batch'}}:
        raise ValueError('workload scheduling differs from reviewed interactive/homework and batch mapping')
    if set(catalog['queues']) != {'interactive','batch'}:
        raise ValueError('unknown workload queue identifier')
    for name, deserved in [('interactive', 8), ('batch', 0)]:
        queue = catalog['queues'][name]
        if queue['gpu'] != {'deserved': deserved, 'limit': 8}:
            raise ValueError('queue GPU capacity differs from the eight-GPU pool')
        for resource in ['cpu', 'memory']:
            if set(queue[resource]) != {'deserved','limit'} or not 0 <= queue[resource]['deserved'] <= queue[resource]['limit']:
                raise ValueError('queue CPU/memory capacities must be explicit and bounded')
    jobsets = catalog['trusted'].get('jobsets')
    distributed = catalog.get('distributedQualification')
    if 'jobsets' in catalog['trusted'] or 'distributedQualification' in catalog:
        fields = {'namespace','serviceAccountName','command','maxWorkers','maxRetries',
                  'ttlSecondsAfterFinished','checkpointClaims'}
        if (not isinstance(jobsets, dict) or set(jobsets) != fields
                or jobsets['namespace'] != catalog['trusted']['namespace']
                or jobsets['serviceAccountName'] != catalog['trusted']['serviceAccountName']
                or jobsets['command'] != ['python']
                or not isinstance(jobsets['checkpointClaims'], dict)
                or len(jobsets['checkpointClaims']) > 128):
            raise ValueError('invalid trusted JobSet namespace/account/command/checkpoint contract')
        for project, entry in jobsets['checkpointClaims'].items():
            if not isinstance(project, str) or not project.strip() or len(project) > 253:
                raise ValueError('invalid trusted JobSet checkpoint project')
            if isinstance(entry, str):
                entry = {'claimName': entry}
            if not isinstance(entry, dict) or set(entry) - {'claimName','subPath'}:
                raise ValueError('invalid trusted JobSet checkpoint entry')
            claim = entry.get('claimName')
            if (not isinstance(claim, str) or not claim or len(claim) > 253
                    or any(len(part) > 63 or not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', part)
                           for part in claim.split('.'))):
                raise ValueError('invalid trusted JobSet checkpoint claim name')
            path = entry.get('subPath')
            if 'subPath' in entry and (not isinstance(path, str) or not path or len(path) > 1024
                    or '\\' in path or '\x00' in path
                    or any(part in ('', '.', '..') for part in path.split('/'))):
                raise ValueError('invalid trusted JobSet checkpoint subpath')
        for field, minimum, maximum in [('maxWorkers', 1, 8), ('maxRetries', 0, 3),
                                         ('ttlSecondsAfterFinished', 60, 86400)]:
            value = jobsets[field]
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError('invalid trusted JobSet ' + field)
        if (not isinstance(distributed, dict) or set(distributed) != {'qualified'}
                or distributed['qualified'] is not False):
            raise ValueError('distributed qualification requires independently reviewed evidence, not catalog assertions')
    for image in catalog['approvedImages']:
        if not re.fullmatch(r'[^\s@]+@sha256:[a-f0-9]{64}', image):
            raise ValueError('approved images must use immutable sha256 digests')
    if catalog['courseProviders']['moodle']['enabled']:
        raise ValueError('Moodle provider is planned / not deployed; enabling is unsupported')
    if catalog['notebook']['snapshotLimitBytes'] != 50 * 1024 * 1024:
        raise ValueError('v1 snapshot limit must be 50 MiB')
    if catalog['gpuQualification']['nominalDeviceMemoryGiB'] != 40:
        raise ValueError('v1 targets the inventoried nominal 40 GiB A100 pool')
    for name, profile in catalog['profiles'].items():
        if profile['kind'] not in ['interactive','batch'] or profile['queue'] != profile['kind']:
            raise ValueError(f'{name}: invalid queue/kind')
        if not re.fullmatch(r'[1-9]\d*(?:m)?', profile['cpu']) or not re.fullmatch(r'[1-9]\d*(?:Mi|Gi)', profile['memory']):
            raise ValueError(f'{name}: invalid resource quantity')
        if not set(profile['images']).issubset(catalog['approvedImages']):
            raise ValueError(f'{name}: profile image is not approved')
        gpu = profile['gpu']
        if gpu['mode'] not in ['none','shared','exclusive']:
            raise ValueError(f'{name}: invalid GPU mode')
        selected_native = name in native_caps
        if gpu['mode'] == 'shared' and not selected_native and (gpu['nominalMemoryGiB'] not in [5,10,20] or gpu.get('fraction') != str(gpu['nominalMemoryGiB']/catalog['gpuQualification']['nominalDeviceMemoryGiB'])):
            raise ValueError(f'{name}: invalid nominal GPU profile')
        if gpu['mode'] == 'exclusive' and gpu['count'] not in [1,2,4,8]:
            raise ValueError(f'{name}: invalid exclusive GPU count')
        if gpu['mode'] == 'exclusive' and profile['kind'] == 'interactive' and not profile.get('administrativeExceptionRequired'):
            raise ValueError('exclusive interactive GPUs require an administrative exception')
        if gpu['mode'] != 'none' and profile['enabled'] and not selected_native:
            raise ValueError('GPU activation requires a separate qualified deployment; catalog targets stay disabled')
    if catalog['gpuQualification']['qualified']:
        raise ValueError('qualification belongs in independently verified evidence, not catalog assertions')
    for bundle in catalog['entitlements'].values():
        if set(bundle['profiles']) - catalog['profiles'].keys() or set(bundle['priorities']) - catalog['priorities'].keys():
            raise ValueError('entitlement references an unknown profile or priority')
    result = copy.deepcopy(catalog)
    result['policyHash'] = 'sha256:' + hashlib.sha256(canonical(catalog)).hexdigest()
    return result


def manifests(policy):
    labels = {policy['labels']['policyVersion']: policy['version']}
    annotations = {policy['labels']['policyHash']: policy['policyHash']}
    objects = []
    for name, queue in policy['queues'].items():
        # KAI v0.18.1 uses millicpu and decimal MB; catalog uses cores and MiB.
        # Descendants are provisioned by the controller.
        resources = {r: {'quota': values['deserved'], 'limit': values['limit'], 'overQuotaWeight': 1}
                     for r, values in queue.items()}
        for field in ('quota', 'limit'):
            resources['cpu'][field] *= 1000
            resources['memory'][field] *= 1.048576
        objects.append({'apiVersion':'scheduling.run.ai/v2','kind':'Queue','metadata':{'name':f'cps-{name}','labels':labels,'annotations':annotations},'spec':{'resources':resources}})
    for name, value in policy['priorities'].items():
        objects.append({'apiVersion':'scheduling.k8s.io/v1','kind':'PriorityClass','metadata':{'name':f'cps-{name}','labels':labels,'annotations':annotations},'value':value,'globalDefault':False,'preemptionPolicy':'PreemptLowerPriority','description':f'CPS compute policy {name}; activation requires qualification'})
    return {'apiVersion':'v1','kind':'List','items':objects}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=ROOT / 'compute-policy/catalog.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'compute-policy/generated')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--qualification-evidence', type=Path)
    parser.add_argument('--native-group-evidence', type=Path)
    parser.add_argument('--native-group-artifacts', type=Path,
        help='Private JSON map of the six native gate names to local checksummed reports')
    args = parser.parse_args()
    try:
        _native_require(bool(args.native_group_evidence) == bool(args.native_group_artifacts),
            'both explicit native group evidence and local artifact map are required')
        native_evidence = _decode_json(args.native_group_evidence.read_bytes()) if args.native_group_evidence else None
        native_artifacts = _decode_json(args.native_group_artifacts.read_bytes()) if args.native_group_artifacts else None
        policy = compile_catalog(_decode_json(args.catalog.read_bytes()),
            native_group_evidence=native_evidence,native_group_artifacts=native_artifacts)
        if args.qualification_evidence:
            validate_evidence(json.loads(args.qualification_evidence.read_text()), policy['policyHash'])
        outputs = {'policy.json':policy, 'queues-priorities.json':manifests(policy),
                   'release-lock.json':{'policyVersion':policy['version'],'policyHash':policy['policyHash'],'status':'unqualified','compatibility':policy['compatibility']}}
        if native_evidence is not None:
            outputs['native-group-evidence.json'] = native_evidence
        for name, value in outputs.items():
            data = json.dumps(value, sort_keys=True, indent=2) + '\n'
            path = args.output / name
            if args.check:
                if not path.exists() or path.read_text() != data:
                    raise ValueError(f'{path}: generated artifact is stale; run compiler')
            else:
                args.output.mkdir(parents=True, exist_ok=True)
                path.write_text(data)
        print(policy['policyHash'])
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f'compute policy: {error}', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
