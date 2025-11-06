# OpenTofu/Terraform Infrastructure for K3s GPU Cluster

This directory contains OpenTofu/Terraform configurations for provisioning VMs on Proxmox with GPU passthrough.

## Prerequisites

1. Proxmox VE installed and configured
2. GPU passthrough enabled (see [../../docs/gpu-passthrough.md](../../docs/gpu-passthrough.md))
3. OpenTofu or Terraform >= 1.5 installed
4. API token created in Proxmox
5. Ubuntu 24.04 cloud-init template created (see [TEMPLATE_CREATION.md](TEMPLATE_CREATION.md))

## Quick Start

### 1. Create Ubuntu 24.04 Template

First, create the cloud-init template on your Proxmox host:

```bash
ssh root@cit-gpu-01.unileoben.ac.at 'bash -s' < ../../scripts/create-ubuntu-template.sh
```

See [TEMPLATE_CREATION.md](TEMPLATE_CREATION.md) for detailed instructions.

## Configuration

### 1. Review and update `terraform.tfvars`

The repository includes a pre-configured `terraform.tfvars` file with:
- Proxmox API credentials
- VLAN 633 network configuration with MUL-assigned MAC addresses
- GPU PCI addresses
- Storage pool: NvmeZFSstorage

Update as needed:
- `pm_api_token_secret`: Your actual API token secret
- `gpu_pci_addresses`: Your GPU PCI addresses (use `lspci | grep NVIDIA` on Proxmox)

### 2. Initialize OpenTofu

```bash
tofu init
```

## Usage

### Plan

```bash
tofu plan -out=tfplan
```

### Apply

```bash
tofu apply tfplan
```

This will create:
- 3 control-plane VMs (k3s-cp1, k3s-cp2, k3s-cp3)
- 4 GPU worker VMs (k3s-wk-gpu1, k3s-wk-gpu2, k3s-wk-gpu3, k3s-wk-gpu4)
- Each worker with 2x A100 GPUs via PCIe passthrough

### Outputs

OpenTofu will output:
- IP addresses of all nodes
- Ansible inventory file (saved to `../ansible/inventory.ini`)

### Destroy

```bash
tofu destroy
```

## VM Specifications

### Control Plane Nodes
- **vCPUs**: 4
- **Memory**: 16 GB
- **Disk**: 100 GB (NvmeZFSstorage)
- **Count**: 3
- **SCSI Controller**: VirtIO SCSI Single
- **Serial Console**: Enabled
- **Tags**: k3s, control-plane, kubernetes, ubuntu-2404

### GPU Worker Nodes
- **vCPUs**: 16
- **Memory**: 128 GB
- **OS Disk**: 500 GB (NvmeZFSstorage)
- **Scratch Disk**: 1 TB (NvmeZFSstorage)
- **GPUs**: 2x NVIDIA A100 per node
- **Count**: 4
- **SCSI Controller**: VirtIO SCSI Single
- **Serial Console**: Enabled
- **Tags**: k3s, worker, gpu, nvidia-a100, kubernetes, ubuntu-2404

## GPU Passthrough Configuration

Each GPU worker VM is configured with:
- Machine type: q35
- BIOS: OVMF (UEFI)
- Two `hostpci` blocks for dual A100 GPUs
- IOMMU enabled
- CPU args: `-cpu host,kvm=off` (for VFIO compatibility)

## Network Configuration

All VMs are attached to **VLAN 633** with MUL-assigned network settings:

- **Bridge**: vmbr0
- **VLAN ID**: 633
- **Network**: 10.21.0.0/16
- **Gateway**: 10.21.1.17
- **DNS**: 193.171.87.249, 193.171.87.250

### IP and MAC Assignments

#### Control Plane VMs
| VM | Hostname | MAC Address | IP Address |
|----|----------|-------------|------------|
| k3s-cp1 | cit-vm-35.cit-gpu.local | 00:16:3e:63:79:26 | 10.21.0.35/16 |
| k3s-cp2 | cit-vm-36.cit-gpu.local | 00:16:3e:63:79:27 | 10.21.0.36/16 |
| k3s-cp3 | cit-vm-37.cit-gpu.local | 00:16:3e:63:79:28 | 10.21.0.37/16 |

#### GPU Worker VMs
| VM | Hostname | MAC Address | IP Address |
|----|----------|-------------|------------|
| k3s-wk-gpu1 | cit-vm-38.cit-gpu.local | 00:16:3e:63:79:29 | 10.21.0.38/16 |
| k3s-wk-gpu2 | cit-vm-39.cit-gpu.local | 00:16:3e:63:79:2a | 10.21.0.39/16 |
| k3s-wk-gpu3 | cit-vm-40.cit-gpu.local | 00:16:3e:63:79:2b | 10.21.0.40/16 |
| k3s-wk-gpu4 | cit-vm-41.cit-gpu.local | 00:16:3e:63:79:2c | 10.21.0.41/16 |

See [../../docs/network-configuration.md](../../docs/network-configuration.md) for more details.

## Troubleshooting

### Template not found

If you see `vm 'ubuntu-24.04-cloudinit' not found`:

1. Create the template first (see [TEMPLATE_CREATION.md](TEMPLATE_CREATION.md)):
   ```bash
   ssh root@cit-gpu-01.unileoben.ac.at 'bash -s' < ../../scripts/create-ubuntu-template.sh
   ```

2. Verify template exists:
   ```bash
   ssh root@cit-gpu-01.unileoben.ac.at 'qm list | grep ubuntu-24.04-cloudinit'
   ```

### GPU not visible in VM

1. Verify IOMMU groups on Proxmox host:
   ```bash
   find /sys/kernel/iommu_groups/ -type l
   ```

2. Check GPU is bound to vfio-pci:
   ```bash
   lspci -nnk | grep -A 3 NVIDIA
   ```

3. Verify PCI addresses in `terraform.tfvars` match your hardware:
   ```bash
   lspci | grep NVIDIA
   ```

### VM won't boot

- Check OVMF firmware is installed on Proxmox
- Verify machine type is q35
- Check Proxmox logs: `journalctl -u pveproxy -f`
- Verify storage pool `NvmeZFSstorage` exists and has space

### Serial console access

To access VM console via serial:

```bash
ssh root@cit-gpu-01.unileoben.ac.at
qm terminal <vmid>
```

Press `Ctrl+O` to exit the serial console.

## Provider Version

This configuration uses **Proxmox provider v3.0.2-rc04** which includes:
- Support for `efidisk` blocks (proper EFI configuration)
- Named disk slots (e.g., "scsi0", "scsi1")
- Improved network configuration with required `id` attribute
- Serial console support

The provider is installed via filesystem mirror at `~/.terraform.d/plugins/`.

See `~/.tofurc` for provider configuration.

## Next Steps

After VMs are provisioned, proceed to:
1. [Ansible playbooks](../ansible/README.md) for K3s installation
