# CPS GPU Cluster

GPU-enabled Kubernetes cluster for AI and JupyterHub workloads, managed via GitOps.

## Overview

This repository is infrastructure-as-code for a reproducible GPU-enabled Kubernetes
environment on Proxmox VMs, provisioned with Terraform and Ansible, with day-2
operations managed continuously via Rancher Fleet GitOps.

### Hardware Topology

- **Host**: single Proxmox server -- multi-core Xeon/EPYC, ~1 TB RAM, 2 TB NVMe +
  HDD/NFS backend, 8x NVIDIA A100 GPUs (PCIe)
- **VM layout**: 3x control-plane nodes (cp1-cp3), 4x GPU worker nodes
  (wk-gpu1-4, 2x A100 each via PCIe passthrough), 1x optional maintenance VM

### Software Stack

| Layer | Choice |
| --- | --- |
| Infrastructure | Proxmox VE with PCIe passthrough |
| Kubernetes | K3s v1.34.9+k3s1 (HA, embedded etcd) |
| Provisioning | Terraform + Ansible |
| Storage | Longhorn + local-path (default), `fast-scratch` (NVMe scratch) |
| GPU | NVIDIA GPU Operator (Helm) + KAI Scheduler |
| Management | Rancher + Fleet GitOps |
| AI Platform | JupyterHub with GPU profiles |
| CI/CD | In-cluster self-hosted GitHub Actions runners (ARC) + shared rootless BuildKit pool |

!!! note "Two-phase lifecycle"
    `bootstrap-cluster/` is one-time provisioning (Terraform + Ansible), run
    manually. `cluster-maintenance/` is everything after the cluster exists,
    deployed continuously via Rancher Fleet watching this repo -- never apply
    those manifests by hand; edit them and let Fleet reconcile.

!!! note "About this docs site"
    This `docs/` tree uses fully auto-discovered navigation (folders +
    `.pages` files, no hand-maintained `nav:` list in `mkdocs.yml`) -- the
    reusable setup is published separately as
    [bjoernellens1/mkdocs-docs-template](https://github.com/bjoernellens1/mkdocs-docs-template)
    if you want the same structure for another project.

## Repository Structure

```
cps-gpu-cluster/
├── bootstrap-cluster/       # One-time provisioning
│   ├── terraform/          # VM provisioning with GPU passthrough
│   └── ansible/            # K3s installation & configuration
├── cluster-maintenance/     # Day-2 operations via Fleet (continuous GitOps)
│   └── clusters/cit-cps-gpu/
├── docs/                   # This documentation
├── scripts/                # Maintenance and utility scripts
└── README.md
```

## Quick Start

1. Enable GPU passthrough on Proxmox -- see [GPU Passthrough](gpu/gpu-passthrough.md)
2. Provision VMs with Terraform
3. Install K3s with Ansible
4. Configure storage (Longhorn/local-path + `fast-scratch`)
5. Install the NVIDIA GPU Operator
6. Install Rancher and enable Fleet GitOps
7. Deploy JupyterHub

For the full step-by-step walkthrough, see the [Deployment Checklist](getting-started/deployment-checklist.md)
or the [Getting Started](getting-started/getting-started.md) guide.

## Networking

- Network: `10.21.0.0/16`
- K3s API: `api.cluster.local` (`10.21.0.100`)
- Control planes: `10.21.0.35-37`
- GPU workers: `10.21.0.38`, `10.21.0.43`, `10.21.0.40`, `10.21.0.41`

## Where to look next

- **New to this cluster?** Start with [Getting Started](getting-started/getting-started.md).
- **Deploying GPU workloads?** See [GPU Scheduling Architecture](gpu/gpu-scheduling-architecture.md).
- **Running a GPU job without an interactive notebook?** See [Running GPU Jobs Without an Interactive Session](gpu/gpu-batch-jobs.md).
- **Something broke?** Check [Troubleshooting](operations/troubleshooting.md) first.
- **CI/CD on the cluster?** See the in-cluster GitHub Actions runner setup under
  `cluster-maintenance/clusters/cit-cps-gpu/system/ci/README.md` in the repo.

### Deployment & operations reference

- [Deployment Checklist](getting-started/deployment-checklist.md) — step-by-step checklist for deploying the cluster from scratch, phase by phase.
- [Quick Reference](getting-started/quick-reference.md) — essential commands for initial deployment and day-to-day cluster management.
- [GPU Passthrough](gpu/gpu-passthrough.md) — enabling PCIe GPU passthrough on Proxmox VE for NVIDIA GPUs.
- [Network Configuration](networking-auth/network-configuration.md) — VLAN/subnet/gateway/DNS layout for the cluster network at MUL.
- [Storage Node](provisioning/storage-node.md) — the original NFS storage node setup, with a live-status note on which StorageClasses are actually in use today.
- [Maintenance VM](provisioning/maintenance-vm.md) — purpose and setup of the utility VM used for cluster administration and debugging.
- [SSH Key Setup](provisioning/ssh-key-setup.md) — distributing SSH keys between VMs via the Proxmox QEMU guest agent.
- [Terraform SSH Setup](provisioning/terraform-ssh-setup.md) — the Terraform-automated version of SSH key distribution (`ssh-setup.tf`).
- [QEMU Guest Agent Setup](provisioning/qemu-guest-agent-setup.md) — how the QEMU guest agent is configured/verified, a prerequisite for the SSH automation above.
- [SOPS Secrets Migration](networking-auth/sops-secrets-migration.md) — how cluster secrets are committed to Git encrypted with SOPS and decrypted in-cluster.

### JupyterHub

- [JupyterHub Overview](jupyterhub/jupyterhub-overview.md) — deep dive into the JupyterHub deployment (note: its MIG-sharing sections are marked stale; see the doc's own staleness note).
- [JupyterHub Access Control and Dynamic Profile UI](jupyterhub/jupyterhub-access-and-ui.md) — how GPU access control and the profile-selection UI are implemented.
- [JupyterHub OIDC Setup](jupyterhub/jupyterhub-oidc-setup.md) — OIDC authentication configuration against CPS Authentik.
- [JupyterHub SSH Access](jupyterhub/jupyterhub-ssh-access.md) — accessing notebook pods over SSH/SFTP via the jupyterhub-ssh gateway.
- [Dex OIDC broker for Rancher](networking-auth/dex-idp-broker.md) — the Dex broker Rancher now authenticates through, fanning out to CPS and CIT Authentik.

### Example notebooks

- [gpu-cluster-test.ipynb](examples/gpu-cluster-test.ipynb) — notebook that verifies GPU/OIDC/storage functionality after a fresh cluster setup.
- [fancy-profiles-showcase.ipynb](examples/fancy-profiles-showcase.ipynb) — placeholder notebook for showcasing JupyterHub profiles (currently empty).

### History / past incidents & superseded designs

These describe point-in-time plans, migrations, or incidents rather than the current state of the cluster — read them for background, not as a reference for what's live today.

- [Project History](project/project-history.md) — the original project specification and goals this repo was built from.
- [Harvester Migration Guide](project/harvester-migration.md) — plan for migrating from K3s-on-Proxmox-VMs to bare-metal Harvester if a second server becomes available (not executed).
- [Rancher + Authentik SSO Plan](networking-auth/rancher-authentik-sso-plan.md) — the SAML-to-OIDC migration for Rancher auth; superseded by the Dex broker (see above).
- [SFTP via Contents API Scoping](jupyterhub/sftp-via-contents-api-scoping.md) — design exploration for per-user SFTP; superseded by the sidecar approach documented in JupyterHub SSH Access.
- [Upgrade Path: K3s 1.34 + DRA-capable GPU Operator](operations/upgrade-path-2026-k3s-1.34-dra.md) — planning doc for a future upgrade to enable NVIDIA DRA; not yet executed.
- [Migration Path: ingress-nginx Retirement](operations/upgrade-path-ingress-nginx-retirement.md) — research/planning doc for replacing ingress-nginx after its upstream retirement; not yet executed.
