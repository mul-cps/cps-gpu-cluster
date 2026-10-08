#!/usr/bin/env python3
"""Read protected CPU/PVC and other GPU node Pod state; no live mutations."""
import datetime
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent


if __name__ == '__main__':
    baseline = json.loads((HERE / 'protected-node-receipt.json').read_text())
    current = json.loads(subprocess.check_output(['kubectl', 'get', 'pods', '-A', '-o', 'json']))['items']
    by_name = {(p['metadata']['namespace'], p['metadata']['name']): p for p in current}
    protected = baseline['protectedOtherGpuNodePods'] + [p for p in baseline['gpu2ActivePods']
        if p['namespace'] not in ('gpu-operator', 'kai-resource-isolator')]
    results = []
    for previous in protected:
        pod = by_name.get((previous['namespace'], previous['name']))
        ready = bool(pod and any(c['type'] == 'Ready' and c['status'] == 'True'
                                for c in pod['status'].get('conditions', [])))
        restarts = bool(pod and [(c['name'], c.get('restartCount', 0)) for c in pod['status'].get('containerStatuses', [])]
                       == [(c['name'], c['restartCount']) for c in previous['containers']])
        results.append({'namespace': previous['namespace'], 'name': previous['name'],
                        'node': previous['node'], 'expectedUID': previous['uid'],
                        'currentUID': pod['metadata']['uid'] if pod else None,
                        'uidMatched': bool(pod and pod['metadata']['uid'] == previous['uid']),
                        'ready': ready, 'containerRestartsMatched': restarts,
                        'containerImagesMatched': bool(pod and
                            [(c['name'], c.get('imageID')) for c in pod['status'].get('containerStatuses', [])]
                            == [(c['name'], c['imageID']) for c in previous['containers']])})
    report = {'observedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'scope': 'GPU1/3/4 baseline Pods and GPU2 CPU/PVC Pods; root-owned GPU2 GPU operator/prototype operands excluded',
              'allProtectedUIDsMatched': all(p['uidMatched'] for p in results),
              'allProtectedReady': all(p['ready'] for p in results),
              'allProtectedRestartsMatched': all(p['containerRestartsMatched'] for p in results),
              'gpu2CpuPvcUIDsMatched': all(p['uidMatched'] for p in results if p['node'] == 'k3s-wk-gpu2'),
              'gpu2CpuPvcReady': all(p['ready'] for p in results if p['node'] == 'k3s-wk-gpu2'),
              'otherGpuDriverUIDsImagesReadyMatched': all(
                  p['uidMatched'] and p['ready'] and p['containerImagesMatched'] and p['containerRestartsMatched']
                  for p in results if p['namespace'] == 'gpu-operator' and p['name'].startswith('nvidia-driver-daemonset-')),
              'protectedPods': results}
    (HERE / 'protected-current-receipt.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'protectedPods'}))
