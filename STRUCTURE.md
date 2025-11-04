# Repository Structure Overview

Complete file structure of the cps-gpu-cluster repository.

```
cps-gpu-cluster/
│
├── README.md                           # Main repository overview
├── LICENSE                             # MIT License
├── PROJECT_PLAN.md                     # Detailed project specification
├── .gitignore                          # Git ignore patterns
│
├── bootstrap-cluster/                  # Infrastructure provisioning
│   │
│   ├── terraform/                      # Proxmox VM provisioning
│   │   ├── README.md                   # Terraform usage guide
│   │   ├── main.tf                     # VM resources with GPU passthrough
│   │   ├── variables.tf                # Variable definitions
│   │   ├── outputs.tf                  # Cluster outputs
│   │   ├── example.tfvars              # Example configuration
│   │   └── templates/
│   │       └── inventory.tpl           # Ansible inventory template
│   │
│   └── ansible/                        # K3s installation & config
│       ├── README.md                   # Ansible usage guide
│       ├── group_vars/
│       │   └── all.yml                 # Cluster-wide variables
│       └── playbooks/
│           ├── site.yml                # Main orchestration playbook
│           ├── 01-prerequisites.yml    # System setup
│           ├── 02-k3s-cluster.yml      # K3s installation
│           ├── 03-storage.yml          # Storage configuration
│           └── 04-gpu-operator.yml     # GPU Operator deployment
│
├── cluster-maintenance/                # GitOps day-2 operations
│   ├── README.md                       # Fleet/GitOps guide
│   └── clusters/
│       └── homelab/                    # Homelab cluster config
│           ├── fleet.yaml              # Fleet bundle configuration
│           │
│           ├── gpu-operator/           # NVIDIA GPU Operator
│           │   ├── fleet.yaml
│           │   ├── values.yaml
│           │   └── namespace.yaml
│           │
│           ├── jupyterhub/             # JupyterHub deployment
│           │   ├── README.md
│           │   ├── fleet.yaml
│           │   ├── values.yaml
│           │   └── namespace.yaml
│           │
│           ├── storageclasses/         # Storage configurations
│           │   └── storageclasses.yaml
│           │
│           └── tests/                  # Validation pods
│               └── cuda-tests.yaml
│
├── docs/                               # Documentation
│   ├── getting-started.md              # Complete setup guide
│   ├── gpu-passthrough.md              # Proxmox GPU configuration
│   ├── harvester-migration.md          # Future migration path
│   └── troubleshooting.md              # Common issues & solutions
│
└── scripts/                            # Automation scripts
    ├── deploy.sh                       # Full deployment automation
    ├── verify.sh                       # Cluster verification
    └── cleanup.sh                      # Resource cleanup/destroy
```

## File Purposes

### Root Level
- **README.md**: Project overview, quick start, links to documentation
- **PROJECT_PLAN.md**: Original specifications, goals, architecture, timeline
- **LICENSE**: MIT license
- **.gitignore**: Excludes secrets, terraform state, temp files

### bootstrap-cluster/terraform/
Terraform code for provisioning VMs on Proxmox with GPU passthrough.

**Key Files**:
- `main.tf`: Creates 3 control-plane VMs + 4 GPU worker VMs
- `variables.tf`: Configurable parameters (API, storage, GPUs)
- `outputs.tf`: Exports node IPs and inventory
- `example.tfvars`: Template for user configuration
- `templates/inventory.tpl`: Generates Ansible inventory

**What it does**:
- Provisions VMs with UEFI/q35 for GPU passthrough
- Configures PCIe devices for 2 GPUs per worker
- Sets up cloud-init for SSH access
- Generates Ansible inventory automatically

### bootstrap-cluster/ansible/
Ansible playbooks for installing and configuring K3s cluster.

**Key Files**:
- `group_vars/all.yml`: Cluster configuration (versions, paths, settings)
- `playbooks/01-prerequisites.yml`: System prep (swap, modules, packages)
- `playbooks/02-k3s-cluster.yml`: K3s HA installation
- `playbooks/03-storage.yml`: NFS and scratch StorageClasses
- `playbooks/04-gpu-operator.yml`: NVIDIA GPU Operator

**What it does**:
- Installs K3s in HA mode (3 control planes, 4 workers)
- Labels GPU nodes, taints control planes
- Deploys storage provisioners
- Installs GPU drivers and device plugins

### cluster-maintenance/clusters/homelab/
Fleet GitOps configurations for day-2 operations.

**Structure**:
Each subdirectory is a Fleet bundle that deploys an application.

- **gpu-operator/**: NVIDIA GPU Operator Helm chart
- **jupyterhub/**: JupyterHub with GPU profiles
- **storageclasses/**: Storage class manifests
- **tests/**: Validation CUDA pods

**How it works**:
1. Fleet watches this Git path
2. Detects changes automatically
3. Applies Helm charts and manifests
4. Maintains desired state

### docs/
Comprehensive documentation for all aspects.

- **getting-started.md**: Step-by-step deployment walkthrough
- **gpu-passthrough.md**: Proxmox IOMMU/VFIO setup
- **harvester-migration.md**: Future migration strategy
- **troubleshooting.md**: Common problems and solutions

### scripts/
Automation scripts for common tasks.

- **deploy.sh**: Full automated deployment (Terraform → Ansible)
- **verify.sh**: Cluster health checks and GPU verification
- **cleanup.sh**: Destroy all resources (VMs, configs)

## Usage Workflows

### Initial Deployment
```bash
# 1. Configure Proxmox GPU passthrough (docs/gpu-passthrough.md)
# 2. Create proxmox.tfvars
cd bootstrap-cluster/terraform
cp example.tfvars proxmox.tfvars
nano proxmox.tfvars

# 3. Run automated deployment
cd ../..
./scripts/deploy.sh

# 4. Verify cluster
export KUBECONFIG=$PWD/kubeconfig
./scripts/verify.sh
```

### GitOps Deployment
```bash
# 1. Install Rancher
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
helm install rancher rancher-stable/rancher -n cattle-system --create-namespace

# 2. Configure Fleet GitRepo in Rancher UI
# Point to: cluster-maintenance/clusters/homelab

# 3. Fleet auto-deploys all applications
```

### Making Changes
```bash
# Edit application configs
nano cluster-maintenance/clusters/homelab/jupyterhub/values.yaml

# Commit and push
git add .
git commit -m "Update JupyterHub config"
git push

# Fleet automatically applies changes
```

### Cleanup
```bash
# Destroy everything
./scripts/cleanup.sh
```

## Key Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| Infrastructure | Proxmox VE | Type-1 hypervisor |
| Provisioning | Terraform | VM creation |
| Configuration | Ansible | K3s installation |
| Kubernetes | K3s v1.31 | Container orchestration |
| Storage | NFS + Local-path | Persistent volumes |
| GPU | NVIDIA Operator | GPU support |
| Management | Rancher | UI & management |
| GitOps | Fleet | Declarative deployment |
| AI Platform | JupyterHub | Multi-user notebooks |

## Resource Allocation

### Control Plane (3 nodes)
- 4 vCPUs × 3 = 12 vCPUs
- 16 GB RAM × 3 = 48 GB RAM
- 100 GB disk × 3 = 300 GB

### GPU Workers (4 nodes)
- 16 vCPUs × 4 = 64 vCPUs
- 128 GB RAM × 4 = 512 GB RAM
- 500 GB OS + 1 TB scratch × 4 = 6 TB
- 2 GPUs × 4 = 8 GPUs total

### Total Cluster
- 76 vCPUs
- 560 GB RAM
- 6.3 TB storage
- 8 NVIDIA A100 GPUs

## Next Steps After Deployment

1. **Security**: Configure real authentication for JupyterHub
2. **Monitoring**: Deploy Prometheus/Grafana
3. **Backups**: Set up Velero for cluster backups
4. **Ingress**: Configure with TLS certificates
5. **Users**: Create user namespaces and quotas
6. **Custom Images**: Build specialized notebook images
7. **Scaling**: Add more workers or migrate to Harvester

## Support Resources

- **Documentation**: `/docs` directory
- **Examples**: `cluster-maintenance/clusters/homelab/tests/`
- **Troubleshooting**: `docs/troubleshooting.md`
- **Community**: K3s, Rancher, NVIDIA forums
- **GitHub**: File issues for bugs/features

## Success Indicators

✓ All 7 nodes in Ready state
✓ 8 GPUs detected and allocatable
✓ Storage classes provisioning volumes
✓ GPU Operator pods running
✓ CUDA tests passing
✓ JupyterHub spawning GPU notebooks
✓ Rancher UI accessible
✓ Fleet syncing from Git

The repository is complete and ready for deployment!
