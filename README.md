# CPS GPU Cluster

GPU-enabled Kubernetes cluster for AI and JupyterHub workloads, managed via GitOps.

## Overview

This repository contains infrastructure-as-code for deploying a reproducible GPU-enabled Kubernetes environment on Proxmox VMs using Terraform and Ansible, with day-2 operations managed via Rancher Fleet.

### Hardware Topology

- **Host**: Single Proxmox server
  - CPU: Multi-core Xeon/EPYC
  - RAM: ~1 TB
  - Storage: 2 TB NVMe + HDD/NFS backend
  - GPUs: 8x NVIDIA A100 (PCIe)

- **VM Layout**:
  - 3x control-plane nodes (cp1, cp2, cp3)
  - 4x worker nodes (wk-gpu1 through wk-gpu4)
  - 1x maintenance VM (optional, for cluster management)
  - Each worker VM: 2x A100 GPUs via PCIe passthrough

### Software Stack

- **Infrastructure**: Proxmox VE with PCIe passthrough
- **Kubernetes**: K3s v1.31 (HA mode with embedded etcd)
- **Provisioning**: Terraform + Ansible
- **Storage**: NFS Subdir External Provisioner + Local-path for scratch
- **GPU**: NVIDIA GPU Operator via Helm
- **Management**: Rancher + Fleet GitOps
- **AI Platform**: JupyterHub with GPU profiles

## Repository Structure

```
cps-gpu-cluster/
├── bootstrap-cluster/       # Infrastructure provisioning
│   ├── terraform/          # VM provisioning with GPU passthrough
│   └── ansible/            # K3s installation & configuration
├── cluster-maintenance/     # Day-2 operations via Fleet
│   └── clusters/homelab/   # GitOps manifests
├── docs/                   # Additional documentation
└── README.md
```

## Quick Start

### Prerequisites

1. Proxmox VE installed with GPU passthrough enabled
2. Terraform >= 1.5
3. Ansible >= 2.15
4. kubectl
5. helm

### Deployment Flow

1. **Enable GPU Passthrough on Proxmox** (see [docs/gpu-passthrough.md](docs/gpu-passthrough.md))
2. **Provision VMs with Terraform** (see [bootstrap-cluster/terraform/README.md](bootstrap-cluster/terraform/README.md))
3. **Install K3s with Ansible** (see [bootstrap-cluster/ansible/README.md](bootstrap-cluster/ansible/README.md))
4. **Configure Storage** (NFS + fast-scratch StorageClasses)
5. **Install NVIDIA GPU Operator**
6. **Install Rancher Management**
7. **Enable Fleet GitOps** (see [cluster-maintenance/README.md](cluster-maintenance/README.md))
8. **Deploy JupyterHub**

## Networking

- Network: 10.0.0.x/24
- K3s API: api.cluster.local (10.0.0.100)
- NFS Server: 10.0.0.30:/export/k3s
- Control Planes: 10.0.0.11-13
- GPU Workers: 10.0.0.21-24

## Future Expansion

When a second bare-metal node becomes available, consider migrating to Harvester for:
- Built-in VM management
- Integrated Rancher support
- Longhorn distributed storage
- Enhanced HA capabilities

See [docs/harvester-migration.md](docs/harvester-migration.md) for details.

## Documentation

- [GPU Passthrough Setup](docs/gpu-passthrough.md)
- [Terraform Usage](bootstrap-cluster/terraform/README.md)
- [Ansible Playbooks](bootstrap-cluster/ansible/README.md)
- [Maintenance VM Guide](docs/maintenance-vm.md)
- [Fleet GitOps](cluster-maintenance/README.md)
- [Network Configuration](docs/network-configuration.md)
- [Harvester Migration](docs/harvester-migration.md)
- [Troubleshooting](docs/troubleshooting.md)

## License

MIT
