# Terraform Infrastructure for K3s GPU Cluster

This directory contains Terraform configurations for provisioning VMs on Proxmox with GPU passthrough.

## Prerequisites

1. Proxmox VE installed and configured
2. GPU passthrough enabled (see [../../docs/gpu-passthrough.md](../../docs/gpu-passthrough.md))
3. Terraform >= 1.5 installed
4. API token created in Proxmox

## Configuration

### 1. Copy example variables

```bash
cp example.tfvars proxmox.tfvars
```

### 2. Edit `proxmox.tfvars`

Update the following values:
- `pm_api_url`: Your Proxmox API endpoint
- `pm_api_token_id`: API token ID
- `pm_api_token_secret`: API token secret
- `ssh_public_key`: Your SSH public key
- GPU PCI addresses for passthrough

### 3. Initialize Terraform

```bash
terraform init
```

## Usage

### Plan

```bash
terraform plan -var-file=proxmox.tfvars
```

### Apply

```bash
terraform apply -var-file=proxmox.tfvars
```

This will create:
- 3 control-plane VMs (cp1, cp2, cp3)
- 4 GPU worker VMs (wk-gpu1, wk-gpu2, wk-gpu3, wk-gpu4)
- Each worker with 2x A100 GPUs via PCIe passthrough

### Outputs

Terraform will output:
- IP addresses of all nodes
- Ansible inventory file (saved to `../ansible/inventory.ini`)

### Destroy

```bash
terraform destroy -var-file=proxmox.tfvars
```

## VM Specifications

### Control Plane Nodes
- vCPUs: 4
- Memory: 16 GB
- Disk: 100 GB
- Count: 3

### GPU Worker Nodes
- vCPUs: 16
- Memory: 128 GB
- Disk: 500 GB (OS) + 1 TB NVMe (scratch)
- GPUs: 2x NVIDIA A100 per node
- Count: 4

## GPU Passthrough Configuration

Each GPU worker VM is configured with:
- Machine type: q35
- BIOS: OVMF (UEFI)
- `hostpci0`: First A100 GPU
- `hostpci1`: Second A100 GPU
- IOMMU enabled

## Network

All VMs are attached to the same bridge network:
- Bridge: vmbr0
- Network: 10.0.0.0/24
- Gateway: 10.0.0.1

IP assignments:
- Control planes: 10.0.0.11-13
- GPU workers: 10.0.0.21-24
- VIP (optional): 10.0.0.100

## Troubleshooting

### GPU not visible in VM

1. Verify IOMMU groups on Proxmox host:
   ```bash
   find /sys/kernel/iommu_groups/ -type l
   ```

2. Check GPU is bound to vfio-pci:
   ```bash
   lspci -nnk | grep -A 3 NVIDIA
   ```

3. Verify VM args include vfio-pci

### VM won't boot

- Check OVMF firmware is installed on Proxmox
- Verify machine type is q35
- Check Proxmox logs: `journalctl -u pveproxy`

## Next Steps

After VMs are provisioned, proceed to:
1. [Ansible playbooks](../ansible/README.md) for K3s installation
