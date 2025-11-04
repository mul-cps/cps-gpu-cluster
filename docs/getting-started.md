# Getting Started Guide

Complete walkthrough for deploying the GPU cluster from scratch.

## Prerequisites

### Hardware
- Proxmox VE server with:
  - 8x NVIDIA A100 GPUs (or similar)
  - ~1 TB RAM
  - 2 TB+ storage
  - IOMMU-capable CPU

### Software on Your Workstation
- Terraform >= 1.5
- Ansible >= 2.15
- kubectl
- helm (optional, will be installed on cluster)
- Git
- SSH client

### Proxmox Setup
- Proxmox VE 8.x installed
- API token created for Terraform
- Ubuntu 22.04 cloud-init template created
- Network bridge configured

## Quick Start (30 minutes)

### 1. Clone Repository

```bash
git clone https://github.com/<your-org>/cps-gpu-cluster.git
cd cps-gpu-cluster
```

### 2. Enable GPU Passthrough on Proxmox

Follow [docs/gpu-passthrough.md](gpu-passthrough.md) to:
- Enable IOMMU in GRUB
- Load VFIO modules
- Bind GPUs to vfio-pci
- Reboot and verify

### 3. Configure Terraform

```bash
cd bootstrap-cluster/terraform
cp example.tfvars proxmox.tfvars
nano proxmox.tfvars
```

Update:
- Proxmox API credentials
- GPU PCI addresses (use `lspci | grep NVIDIA` on Proxmox)
- SSH public key
- Network settings

### 4. Run Deployment Script

```bash
cd ../..
chmod +x scripts/*.sh
./scripts/deploy.sh
```

This will:
1. Provision VMs with Terraform
2. Install K3s with Ansible
3. Configure storage
4. Install GPU Operator
5. Fetch kubeconfig

### 5. Verify Cluster

```bash
export KUBECONFIG=$PWD/kubeconfig
./scripts/verify.sh
```

Should show:
- 7 nodes ready (3 CP + 4 workers)
- 8 GPUs available
- Storage classes configured
- GPU operator running

### 6. Install Rancher

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Wait for cert-manager
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=cert-manager -n cert-manager --timeout=300s

# Add Rancher repo
helm repo add rancher-stable https://releases.rancher.com/server-charts/stable
helm repo update

# Install Rancher
kubectl create namespace cattle-system
helm install rancher rancher-stable/rancher \
  --namespace cattle-system \
  --set hostname=rancher.cluster.local \
  --set bootstrapPassword=admin \
  --set replicas=3

# Wait for Rancher
kubectl -n cattle-system rollout status deploy/rancher
```

### 7. Access Rancher

```bash
# Port forward
kubectl -n cattle-system port-forward deploy/rancher 8443:443
```

Open https://localhost:8443 in browser
- Username: admin
- Password: Get with `kubectl get secret --namespace cattle-system bootstrap-secret -o go-template='{{.data.bootstrapPassword|base64decode}}{{"\n"}}'`

### 8. Configure Fleet GitOps

In Rancher UI:
1. Navigate to **Continuous Delivery**
2. Click **Git Repos** → **Create**
3. Configure:
   - Name: `cluster-maintenance`
   - Repository URL: Your Git repo URL
   - Branch: `main`
   - Paths: `cluster-maintenance/clusters/homelab`
4. Click **Create**

Fleet will now deploy:
- JupyterHub
- Additional storage classes
- Test pods

### 9. Access JupyterHub

```bash
# Get service
kubectl get svc -n jupyterhub proxy-public

# Port forward
kubectl port-forward -n jupyterhub svc/proxy-public 8000:80
```

Open http://localhost:8000
- Username: any name
- Password: `jupyter`

Select a GPU profile and test:

```python
import torch
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"GPU count: {torch.cuda.device_count()}")
```

## Detailed Steps

### Creating Proxmox VM Template

If you don't have a cloud-init template:

```bash
# On Proxmox host
wget https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img

# Create VM
qm create 9000 --name ubuntu-22.04-cloudinit --memory 2048 --cores 2 --net0 virtio,bridge=vmbr0

# Import disk
qm importdisk 9000 jammy-server-cloudimg-amd64.img local-lvm

# Attach disk
qm set 9000 --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-9000-disk-0

# Add cloud-init drive
qm set 9000 --ide2 local-lvm:cloudinit

# Set boot disk
qm set 9000 --boot c --bootdisk scsi0

# Add serial console
qm set 9000 --serial0 socket --vga serial0

# Convert to template
qm template 9000
```

### Manual Terraform Deployment

If not using deploy.sh:

```bash
cd bootstrap-cluster/terraform
terraform init
terraform plan -var-file=proxmox.tfvars
terraform apply -var-file=proxmox.tfvars
```

### Manual Ansible Deployment

If not using deploy.sh:

```bash
cd bootstrap-cluster/ansible

# All steps
ansible-playbook -i inventory.ini playbooks/site.yml

# Or individual steps
ansible-playbook -i inventory.ini playbooks/01-prerequisites.yml
ansible-playbook -i inventory.ini playbooks/02-k3s-cluster.yml
ansible-playbook -i inventory.ini playbooks/03-storage.yml
ansible-playbook -i inventory.ini playbooks/04-gpu-operator.yml
```

### Testing GPU Access

Create test pod:

```bash
kubectl apply -f cluster-maintenance/clusters/homelab/tests/cuda-tests.yaml

# Wait and check logs
kubectl wait --for=condition=ready pod/cuda-vectoradd --timeout=120s
kubectl logs cuda-vectoradd
# Should show: "Test PASSED"

# Cleanup
kubectl delete -f cluster-maintenance/clusters/homelab/tests/cuda-tests.yaml
```

### Customizing JupyterHub

Edit `cluster-maintenance/clusters/homelab/jupyterhub/values.yaml`:

```yaml
# Change authentication
hub:
  config:
    JupyterHub:
      authenticator_class: your.authenticator.Class

# Add GPU profile
singleuser:
  profileList:
    - display_name: "Custom Profile"
      kubespawner_override:
        image: your/custom-image:tag
        extra_resource_limits:
          nvidia.com/gpu: "2"
```

Commit and push - Fleet will auto-deploy.

## Troubleshooting

See [docs/troubleshooting.md](troubleshooting.md) for common issues.

Quick checks:

```bash
# Cluster health
kubectl get nodes
kubectl get pods -A

# GPU resources
kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'

# Storage
kubectl get pvc -A
kubectl get sc

# Logs
kubectl logs -n gpu-operator -l app=nvidia-device-plugin-daemonset
kubectl logs -n jupyterhub -l component=hub
```

## Cleanup

To destroy everything:

```bash
./scripts/cleanup.sh
```

## Next Steps

- Configure monitoring (Prometheus/Grafana)
- Set up backups (Velero)
- Configure ingress with TLS
- Add user authentication (LDAP/OAuth)
- Tune GPU scheduling (time-slicing, MIG)
- Set up logging (ELK/Loki)

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Proxmox Host                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │  CP-1      │  │  CP-2      │  │  CP-3      │           │
│  │  (K3s)     │  │  (K3s)     │  │  (K3s)     │           │
│  │  4vCPU     │  │  4vCPU     │  │  4vCPU     │           │
│  │  16GB      │  │  16GB      │  │  16GB      │           │
│  └────────────┘  └────────────┘  └────────────┘           │
│                                                             │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────┐ │
│  │ GPU-1      │  │ GPU-2      │  │ GPU-3      │  │GPU-4 │ │
│  │ 2x A100    │  │ 2x A100    │  │ 2x A100    │  │2xA100│ │
│  │ 16vCPU     │  │ 16vCPU     │  │ 16vCPU     │  │16vCPU│ │
│  │ 128GB      │  │ 128GB      │  │ 128GB      │  │128GB │ │
│  │ 1TB NVMe   │  │ 1TB NVMe   │  │ 1TB NVMe   │  │1TBNVMe│
│  └────────────┘  └────────────┘  └────────────┘  └──────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                    ┌───────┴────────┐
                    │   Kubernetes   │
                    │   (K3s v1.31)  │
                    └───────┬────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
    ┌───┴────┐        ┌────┴─────┐      ┌─────┴──────┐
    │ Rancher│        │   Fleet  │      │GPU Operator│
    │        │        │ (GitOps) │      │            │
    └────────┘        └──────────┘      └────────────┘
                            │
                    ┌───────┴────────┐
                    │  Applications  │
                    │  - JupyterHub  │
                    │  - Custom apps │
                    └────────────────┘
```

## Support

- GitHub Issues: File bug reports and feature requests
- Documentation: All docs in `/docs` directory
- Troubleshooting: See [docs/troubleshooting.md](troubleshooting.md)
