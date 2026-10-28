"""The default notebook identity is isolated from Dask write authority."""
from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[2]
JUPYTER = ROOT / 'cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub'


def test_default_notebook_uses_minimal_tokenless_service_account():
    values = yaml.safe_load((JUPYTER / 'values.yaml').read_text())['singleuser']
    assert values['serviceAccountName'] == 'jupyter-notebook'
    assert values['extraPodConfig']['automountServiceAccountToken'] is False

    rendered = subprocess.run(
        ['kubectl', 'kustomize', str(JUPYTER)], capture_output=True, text=True, check=True,
    ).stdout
    resources = [resource for resource in yaml.safe_load_all(rendered) if resource]
    notebook_sa = next(resource for resource in resources
                       if resource['kind'] == 'ServiceAccount'
                       and resource['metadata']['name'] == 'jupyter-notebook')
    assert notebook_sa['automountServiceAccountToken'] is False

    # Keep legacy Dask bindings intact for already-issued research identities,
    # while ensuring the default notebook identity receives none of them.
    bindings = [resource for resource in resources if resource['kind'] == 'RoleBinding']
    assert all(not any(subject.get('kind') == 'ServiceAccount'
                       and subject.get('name') == 'jupyter-notebook'
                       for subject in binding.get('subjects', [])) for binding in bindings)

