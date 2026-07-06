# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Infrastructure-as-code for a single-site, GPU-enabled Kubernetes cluster (K3s on Proxmox VMs), managed day-2 via Rancher Fleet GitOps. There is no application code, build step, or test suite in the traditional sense — this repo is Terraform, Ansible, Helm values, and Kubernetes/Fleet manifests. "Verification" means applying changes against real infrastructure and checking cluster state with kubectl, not running a test runner.

## Repository layout and the two-phase lifecycle

The repo is split into two distinct lifecycle phases that use different tools and that Fleet does not touch:

- `bootstrap-cluster/` — one-time (or rare) provisioning, run manually from a workstation/maintenance VM.
  - `terraform/` — OpenTofu/Terraform provisions Proxmox VMs (3 control-plane + 4 GPU workers) with PCIe passthrough for 2x A100 per worker. Outputs an Ansible inventory to `../ansible/inventory.ini`.
  - `ansible/` — installs and configures K3s (HA, embedded etcd), NFS/local-path storage, NVIDIA GPU Operator prerequisites, and optionally Rancher, against the VMs Terraform created.
- `cluster-maintenance/clusters/cit-cps-gpu/` — everything after the cluster exists, deployed continuously via Rancher Fleet watching this path in Git. Never apply these manifests by hand in normal operation; edit them and let Fleet reconcile (`kubectl get gitrepo/bundles -n fleet-local` to check sync status).
    - `system/` — cluster-wide infrastructure bundles: `gpu/` (gpu-operator, kai-scheduler), `networking/` (ingress-nginx, metallb), `observability/` (alloy, loki, monitoring), `storage/` (longhorn, storageclasses), `utils/` (node-tuning, reflector).
    - `user/` — user-facing workloads: `jupyter/` (jupyterhub, jupyterhub-ssh), `llm/` (ollama, open-webui).
    - Each bundle directory is a self-contained Fleet unit: a `fleet.yaml` (chart/repo/version/valuesFiles, `dependsOn` for ordering) plus `values.yaml` and/or raw manifests/Helm chart. Use existing bundles as the template when adding a new one.
    - `.vcluster-ckf/` — a vcluster hosting Charmed Kubeflow; unlike other bundles it requires a manual post-sync bootstrap step (see its README) rather than being fully declarative.

`scripts/` holds one-off operational scripts run against a live cluster (not part of any pipeline): `check_orphans.py` (find orphaned PVCs/PVs), `verify.sh` (post-deploy health checks: nodes, GPU count, storage classes, GPU Operator pods), `deploy.sh`, `cleanup.sh` (destroys the entire cluster — destructive, confirm before ever suggesting it), plus template/SSH/password-hash setup scripts.

`tests/nfs-testclaim/` is not an automated test suite — it's a manifest (PV/PVC/Pod) applied manually to smoke-test NFS storage.

`docs/` contains the authoritative deep-dive docs (network config, GPU passthrough, JupyterHub OIDC/SSH access, troubleshooting, harvester migration plan, project history) — check there before re-deriving cluster facts from manifests.

## Common commands

Provisioning (from `bootstrap-cluster/terraform/`):
```bash
tofu init
tofu plan -out=tfplan
tofu apply tfplan
```

K3s/cluster install (from `bootstrap-cluster/ansible/`), run against the Terraform-generated `inventory.ini`:
```bash
ansible-playbook -i inventory.ini playbooks/site.yml       # full install
ansible-playbook -i inventory.ini playbooks/04-gpu-operator.yml   # single step, e.g.
```

Post-deploy verification against a live cluster:
```bash
export KUBECONFIG=./kubeconfig
./scripts/verify.sh
python3 scripts/check_orphans.py
```

Fleet/GitOps status:
```bash
kubectl get gitrepo -n fleet-local
kubectl get bundles -n fleet-local
kubectl describe bundle <bundle-name> -n fleet-local
```

## Key facts to keep straight

- Network: 10.21.0.0/16; API at `api.cluster.local` (10.21.0.100); NFS server 10.21.0.44:/srv/nfs/k3s-storage; control planes 10.21.0.35-37; GPU workers .38/.43/.40/.41.
- Storage classes: `nfs-client` (default, general-purpose via NFS) and `fast-scratch` (local-path, NVMe scratch per GPU worker at `/mnt/nvme/scratch`).
- GPU worker node labels: `accelerator=nvidia`, `scratch=nvme`, `gpu-model=a100`.
- Changes to `cluster-maintenance/` take effect only after Fleet syncs from Git — there is no local "apply" step for that tree.
- Secrets are never stored in Git; cross-namespace secret distribution goes through Reflector annotations (see `system/utils/reflector`), not copy-pasted manifests.
