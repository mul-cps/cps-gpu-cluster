#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
jupyter_dir="$root/cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub"

rg -F 'name: jupyterhub-shared-storage-replacement' "$jupyter_dir/shared-pvc-replacement.yaml"
rg -F 'storageClassName: longhorn-overcommit' "$jupyter_dir/shared-pvc-replacement.yaml"
rg -F 'storage: 500Gi' "$jupyter_dir/shared-pvc-replacement.yaml"
rg -F -- '- shared-pvc-replacement.yaml' "$jupyter_dir/kustomization.yaml"
rg -F "claimName': 'jupyterhub-shared-storage-replacement'" "$jupyter_dir/values.yaml"
