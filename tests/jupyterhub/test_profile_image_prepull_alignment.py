"""Verify continuous and upgrade-hook pre-pullers mirror supported Hub profiles."""
import ast
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
VALUES = ROOT / 'cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml'
CHART = Path(os.environ.get('JUPYTERHUB_CHART', Path.home() / '.cache/helm/jupyterhub-4.4.2.tgz'))
UNSUPPORTED_PROFILES = {'dask-cluster', 'gpu-slurm'}


def profile_configs():
    code = yaml.safe_load(VALUES.read_text())['hub']['extraConfig']['02-profiles']
    tree = ast.parse(code)
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == 'PROFILE_CONFIGS'
                              for target in node.targets))
    return ast.literal_eval(assignment.value)


def rendered_prepuller_images():
    if not CHART.is_file():
        pytest.fail(f'JupyterHub chart archive missing: {CHART}; set JUPYTERHUB_CHART to chart 4.4.2')
    output = subprocess.run(
        ['helm', 'template', 'jupyterhub', str(CHART), '--namespace', 'jupyterhub', '-f', str(VALUES)],
        capture_output=True, text=True, check=True,
    ).stdout
    resources = [resource for resource in yaml.safe_load_all(output) if resource]
    pullers = [resource for resource in resources if resource.get('kind') == 'DaemonSet'
               and resource.get('metadata', {}).get('name') in {
                   'continuous-image-puller', 'hook-image-puller'}]
    assert {resource['metadata']['name'] for resource in pullers} == {
        'continuous-image-puller', 'hook-image-puller'}
    return {
        resource['metadata']['name']: {
            container['image'] for container in resource['spec']['template']['spec']['initContainers']
        }
        for resource in pullers
    }


def test_all_supported_fixed_profile_images_are_pulled_by_both_image_puller_daemonsets():
    configs = profile_configs()
    assert UNSUPPORTED_PROFILES <= configs.keys()
    supported_images = {slug: config['image'] for slug, config in configs.items()
                        if slug not in UNSUPPORTED_PROFILES}
    rendered = rendered_prepuller_images()

    for daemonset, image_refs in rendered.items():
        for slug, image in supported_images.items():
            assert image in image_refs, f'{daemonset} does not pre-pull {slug}: {image}'
        assert configs['dask-cluster']['image'] not in image_refs


def test_fixed_launch_helpers_are_deployed_with_the_verified_compatibility_image():
    output = subprocess.run(
        ['helm', 'template', 'jupyterhub', str(CHART), '--namespace', 'jupyterhub', '-f', str(VALUES)],
        capture_output=True, text=True, check=True,
    ).stdout
    hub = next(r for r in yaml.safe_load_all(output)
               if r and r.get('kind') == 'Deployment' and r['metadata']['name'] == 'hub')
    image = next(c['image'] for c in hub['spec']['template']['spec']['containers'] if c['name'] == 'hub')
    assert image.startswith('ghcr.io/mul-cps/cps-compute:')
    assert image.endswith('@sha256:f00f8c5b63bdce6348153aab6e11c1fd5cbf638ed1b50ef27bdda346ad202b75')
