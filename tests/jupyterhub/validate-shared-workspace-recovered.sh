#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
jupyter_dir="$root/cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub"

rg -F "claimName': 'jupyterhub-shared-storage'" "$jupyter_dir/values.yaml"
rg -F -- '- shared-pvc.yaml' "$jupyter_dir/kustomization.yaml"
test ! -e "$jupyter_dir/shared-pvc-replacement.yaml"
