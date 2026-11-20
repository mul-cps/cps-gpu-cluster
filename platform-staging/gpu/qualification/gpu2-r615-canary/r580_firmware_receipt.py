#!/usr/bin/env python3
"""Read the two root-owned CPU extraction attempts; never mutate live resources."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


def read(*arguments):
    return subprocess.check_output(['kubectl', '-n', 'gpu-operator', *arguments], text=True)


def collect(name, proposal_file):
    job = json.loads(read('get', 'job', name, '-o', 'json'))
    pods = json.loads(read('get', 'pods', '-l', 'job-name=' + name, '-o', 'json'))['items']
    assert len(pods) == 1
    pod = pods[0]
    assert pod['spec']['nodeName'] == 'k3s-wk-gpu2'
    assert pod['metadata']['ownerReferences'][0]['uid'] == job['metadata']['uid']
    container = pod['spec']['containers'][0]
    status = pod['status']['containerStatuses'][0]
    assert status['imageID'] == container['image']
    logs = read('logs', pod['metadata']['name'])
    return {
        'job': {'name': name, 'uid': job['metadata']['uid'], 'status': job['status']},
        'pod': {'name': pod['metadata']['name'], 'uid': pod['metadata']['uid'],
                'node': pod['spec']['nodeName'], 'phase': pod['status']['phase'],
                'imageID': status['imageID'], 'restartCount': status['restartCount'],
                'state': status['state']},
        'proposalFile': proposal_file,
        'proposalSHA256': hashlib.sha256((HERE / proposal_file).read_bytes()).hexdigest(),
        'actualScriptSHA256': hashlib.sha256(container['args'][0].encode()).hexdigest(),
        'logs': logs,
        'cpuOnly': not any('gpu' in key.lower() or 'nvidia' in key.lower()
                           for values in container['resources'].values() for key in values),
        'serviceAccountTokenMounted': pod['spec']['automountServiceAccountToken'],
        'privileged': container['securityContext']['privileged'],
        'capabilities': container['securityContext']['capabilities'],
    }


if __name__ == '__main__':
    attempts = [collect('gpu2-r580-firmware-preload', 'r580-firmware-preload-not-applied.yaml'),
                collect('gpu2-r580-firmware-preload-v2', 'r580-firmware-preload-v2-not-applied.yaml')]
    receipt = {'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'scope': 'Root-owned GPU2 CPU-only firmware extraction; no driver installation',
               'attempts': attempts,
               'firmwarePreloadPassed': attempts[1]['pod']['state']['terminated']['exitCode'] == 0
                                       and 'EXTRACTION_ONLY_NO_DRIVER_INSTALL_COMPLETE' in attempts[1]['logs'],
               'r580RollbackExecuted': False}
    (HERE / 'r580-firmware-preload-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({key: receipt[key] for key in ('observedAt', 'firmwarePreloadPassed', 'r580RollbackExecuted')}))
