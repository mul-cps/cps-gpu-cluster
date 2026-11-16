"""Verify a reviewed Hub template against a freshly rendered upstream chart.

Helm Secret output stays inside a private temporary directory and is discarded.
Only the Deployment and nonsecret checksums are emitted/validated.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--chart', type=Path, required=True)
parser.add_argument('--bundle', type=Path, required=True)
parser.add_argument('--values', required=True, help='Values path relative to bundle')
parser.add_argument('--namespace', required=True)
parser.add_argument('--release', required=True)
parser.add_argument('--server-dry-run', action='store_true')
a = parser.parse_args()
a.bundle = a.bundle.resolve()
expected = yaml.safe_load((a.bundle / 'reviewed-hub-template.patch.yaml').read_text())
expected_template = copy.deepcopy(expected['spec']['template'])
expected_template.pop('$patch')
expected_strategy = copy.deepcopy(expected['spec']['strategy'])
expected_strategy.pop('$patch')
render = subprocess.check_output(['helm', 'template', a.release, str(a.chart.resolve()),
    '--namespace', a.namespace, '--values', str(a.bundle / a.values)], text=True)
base = next(x for x in yaml.safe_load_all(render) if x and x.get('kind') == 'Deployment'
            and x['metadata']['name'] == 'hub')
with tempfile.TemporaryDirectory(prefix='cps-fresh-hub-render-') as directory:
    root = Path(directory) / 'bundle'
    shutil.copytree(a.bundle, root)
    fleet = root / 'fleet-manifests.yaml'
    fleet.write_text(render)
    fleet.chmod(0o600)
    path = root / 'kustomization.yaml'
    k = yaml.safe_load(path.read_text())
    k['resources'] = ['fleet-manifests.yaml', *k.get('resources', [])]
    path.write_text(yaml.safe_dump(k))
    docs = yaml.safe_load_all(subprocess.check_output(['kubectl', 'kustomize', str(root)], text=True))
    hub = next(x for x in docs if x and x.get('kind') == 'Deployment' and x['metadata']['name'] == 'hub')
    if hub['spec']['template'] != expected_template or hub['spec']['strategy'] != expected_strategy:
        raise RuntimeError('Fresh upstream chart did not receive the exact reviewed Hub template/strategy')
    if hub['metadata']['namespace'] != a.namespace:
        raise RuntimeError('Wrong Hub namespace')
    if a.server_dry_run:
        deployment = Path(directory) / 'hub.yaml'
        deployment.write_text(yaml.safe_dump(hub))
        deployment.chmod(0o600)
        subprocess.check_output(['kubectl', 'apply', '--server-side', '--dry-run=server',
            '--field-manager=upstream-hub-persistence-check', '--force-conflicts',
            '-f', str(deployment), '-o', 'name'], text=True)
print(json.dumps({'namespace': a.namespace, 'release': a.release,
    'fresh_chart_sha256': hashlib.sha256(a.chart.read_bytes()).hexdigest(),
    'fresh_hub_original_namespace': base['metadata'].get('namespace'),
    'exact_reviewed_template': True, 'exact_reviewed_strategy': True,
    'server_dry_run': a.server_dry_run,
    'image': hub['spec']['template']['spec']['containers'][0]['image']}, indent=2))
