#!/usr/bin/env python3
"""Compile the shared policy without cluster access or third-party dependencies."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


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


def compile_catalog(catalog):
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
        if gpu['mode'] == 'shared' and (gpu['nominalMemoryGiB'] not in [5,10,20] or gpu['fraction'] != str(gpu['nominalMemoryGiB']/catalog['gpuQualification']['nominalDeviceMemoryGiB'])):
            raise ValueError(f'{name}: invalid nominal GPU profile')
        if gpu['mode'] == 'exclusive' and gpu['count'] not in [1,2,4,8]:
            raise ValueError(f'{name}: invalid exclusive GPU count')
        if gpu['mode'] == 'exclusive' and profile['kind'] == 'interactive' and not profile.get('administrativeExceptionRequired'):
            raise ValueError('exclusive interactive GPUs require an administrative exception')
        if gpu['mode'] != 'none' and profile['enabled']:
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
    args = parser.parse_args()
    try:
        policy = compile_catalog(json.loads(args.catalog.read_text()))
        if args.qualification_evidence:
            validate_evidence(json.loads(args.qualification_evidence.read_text()), policy['policyHash'])
        outputs = {'policy.json':policy, 'queues-priorities.json':manifests(policy),
                   'release-lock.json':{'policyVersion':policy['version'],'policyHash':policy['policyHash'],'status':'unqualified','compatibility':policy['compatibility']}}
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
