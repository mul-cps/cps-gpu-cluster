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

1. Enable GPU passthrough on Proxmox -- see [GPU Passthrough](gpu-passthrough.md)
2. Provision VMs with Terraform
3. Install K3s with Ansible
4. Configure storage (Longhorn/local-path + `fast-scratch`)
5. Install the NVIDIA GPU Operator
6. Install Rancher and enable Fleet GitOps
7. Deploy JupyterHub

For the full step-by-step walkthrough, see the [Deployment Checklist](deployment-checklist.md)
or the [Getting Started](getting-started.md) guide.

## Networking

- Network: `10.21.0.0/16`
- K3s API: `api.cluster.local` (`10.21.0.100`)
- Control planes: `10.21.0.35-37`
- GPU workers: `10.21.0.38`, `10.21.0.43`, `10.21.0.40`, `10.21.0.41`

## Where to look next

- **New to this cluster?** Start with [Getting Started](getting-started.md).
- **Deploying GPU workloads?** See [GPU Scheduling Architecture](gpu-scheduling-architecture.md).
- **Something broke?** Check [Troubleshooting](troubleshooting.md) first.
- **CI/CD on the cluster?** See the in-cluster GitHub Actions runner setup under
  `cluster-maintenance/clusters/cit-cps-gpu/system/ci/README.md` in the repo.
