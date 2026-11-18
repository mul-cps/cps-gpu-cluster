"""Read-only guard for the declared operator delivery; never applies manifests."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def podspec(document):
    spec = document['spec']
    return spec['jobTemplate']['spec']['template']['spec'] if document['kind'] == 'CronJob' else spec['template']['spec']

def assert_current(pointer, current_pvc, current_objects):
    claim = pointer['currentClaim']
    assert current_pvc['metadata']['name'] == claim['name']
    assert current_pvc['metadata']['namespace'] == claim['namespace']
    assert current_pvc['metadata']['uid'] == claim['uid'], 'Authoritative PVC replaced'
    assert current_pvc['spec']['volumeName'] == claim['pvName']
    for row in pointer['resources']:
        obj = current_objects[row['name']]
        assert obj['metadata']['uid'] == row['uid'], 'Controller replaced'
        expected_key = 'baselineSpecSHA256' if pointer['status'] == 'BASELINE-current' else 'candidateSpecSHA256'
        assert pointer['status'] in ('BASELINE-current', 'CHECKPOINT-current')
        assert digest(obj['spec']) == row[expected_key], 'Current spec differs: review a successor desired-source record'
        volume = next(v for v in podspec(obj)['volumes'] if v['name'] == row['sourceVolume'])
        assert volume['persistentVolumeClaim']['claimName'] == claim['name'], 'Stale claim reference'
    return True

def validate_local():
    pointer = json.loads((ROOT / 'current-delivery.json').read_text())
    for row in pointer['resources']:
        for directory, key in [('baseline', 'baselineSpecSHA256'), ('candidate', 'candidateSpecSHA256')]:
            obj = json.loads((ROOT / directory / (row['name'] + '.json')).read_text())
            assert digest(obj['spec']) == row[key], 'Desired manifest hash differs'
    return pointer

def get(kind, name, namespace):
    return json.loads(subprocess.check_output(['kubectl', '--request-timeout=15s', '-n', namespace,
        'get', kind, name, '-o', 'json'], stderr=subprocess.PIPE, timeout=25))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-check', action='store_true', help='GET-only exact current claim/three specs check')
    args = parser.parse_args()
    pointer = validate_local()
    if args.live_check:
        claim = pointer['currentClaim']
        pvc = get('pvc', claim['name'], claim['namespace'])
        objects = {r['name']: get(r['kind'], r['name'], r['namespace']) for r in pointer['resources']}
        assert_current(pointer, pvc, objects)
    print(json.dumps({'localHashes': True, 'liveCurrentClaimAndSpecs': args.live_check,
        'status': pointer['status'], 'mutations': False}))

if __name__ == '__main__':
    main()
