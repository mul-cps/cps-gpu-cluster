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
UNSUPPORTED_PROFILES = {'gpu-slurm'}


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
        assert configs['dask-cluster']['image'] in image_refs
