# Maintenance VM Implementation Summary

## Overview

A minimal maintenance VM has been added to the cluster infrastructure. This VM provides a centralized management point with all necessary tools for cluster operations, debugging, and infrastructure management.

## What Was Added

### 1. Terraform Configuration

**Files Modified:**
- `bootstrap-cluster/terraform/main.tf`
  - Added `proxmox_vm_qemu.maintenance` resource (conditionally created)
  - Updated Ansible inventory generation to include maintenance VM
  
- `bootstrap-cluster/terraform/variables.tf`
  - Added `maintenance_mac` variable
  - Added `maintenance_ip` variable

- `bootstrap-cluster/terraform/terraform.tfvars`
  - Added maintenance VM configuration (MAC: 00:16:3e:63:79:2d, IP: 10.21.0.42)

- `bootstrap-cluster/terraform/templates/inventory.tpl`
  - Added `[maintenance]` group for Ansible inventory

**Files Created:**
- `bootstrap-cluster/terraform/cloud-init-maintenance.yml`
  - Cloud-init configuration for tool installation
  - Installs Ansible, OpenTofu, Git, Docker, kubectl, k9s, helm, and debugging tools

### 2. Ansible Configuration

**Files Created:**
- `bootstrap-cluster/ansible/playbooks/05-maintenance-vm.yml`
  - Comprehensive playbook for maintenance VM setup
  - Installs additional tools (jq, yq, ripgrep, fd, bat, fzf, etc.)
  - Sets up kubectl plugins via krew
  - Creates maintenance scripts
  - Configures workspace structure
  - Sets up custom MOTD

**Files Modified:**
- `bootstrap-cluster/ansible/playbooks/site.yml`
  - Added conditional import of maintenance VM playbook

### 3. Documentation

**Files Created:**
- `docs/maintenance-vm.md`
  - Complete documentation for maintenance VM
  - Installation instructions
  - Usage guide
  - Troubleshooting tips
  
- `scripts/maintenance-vm-reference.sh`
  - Quick reference guide for common commands
  - Can be run to display helpful information

**Files Modified:**
- `README.md`
  - Added maintenance VM to architecture overview
  - Added link to maintenance VM documentation

## VM Specifications

- **Name**: k3s-maintenance
- **VM ID**: Auto-assigned by Proxmox
- **CPU**: 2 cores
- **Memory**: 4 GB
- **Disk**: 50 GB (scsi0, VirtIO SCSI)
- **Network**: VLAN 633, Static IP 10.21.0.42/16
- **MAC Address**: 00:16:3e:63:79:2d (cit-vm-42)
- **Auto-start**: Disabled (manual start when needed)

## Installed Tools

### Infrastructure as Code
- OpenTofu (Terraform fork)
- Ansible + ansible-lint
- Git + Git LFS

### Kubernetes Management
- kubectl + plugins (ctx, ns, whoami, tree, tail, view-secret, resource-capacity)
- k9s (Terminal UI)
- helm (Package manager)
- kubectx/kubens

### Container Tools
- Docker + Docker Compose

### Debugging Tools
- Network: tcpdump, nmap, iperf3, mtr, iftop, netcat
- System: strace, lsof, sysstat, htop, iotop, ncdu, stress-ng
- CLI: jq, yq, ripgrep, fd, bat, fzf, httpie
- Load testing: siege, wrk

## Pre-configured Scripts

Located in `/opt/maintenance-tools/scripts/`:

1. **cluster-health.sh** - Comprehensive cluster health check
2. **check-gpus.sh** - GPU status across all worker nodes
3. **quick-deploy.sh** - Quick deployment helper for testing
4. **cleanup-failed-pods.sh** - Clean up failed/completed pods

## Workspace Structure

Pre-configured at `~/workspace`:
- `terraform/` - Infrastructure configurations
- `ansible/` - Playbooks and inventories
- `kubernetes/` - K8s manifests
- `scripts/` - Custom scripts
- `tmp/` - Temporary files
- `README.md` - Workspace documentation

## Deployment Steps

### 1. Enable Maintenance VM

The maintenance VM is **optional** and disabled by default. To enable:

```hcl
# In bootstrap-cluster/terraform/terraform.tfvars
maintenance_mac = "00:16:3e:63:79:2d"  # cit-vm-42
maintenance_ip  = "10.21.0.42/16"      # k3s-maintenance
```

**Note**: The MAC address and IP shown above need to be requested from MUL network administration for VLAN 633.

### 2. Deploy with Terraform

```bash
cd bootstrap-cluster/terraform

# Validate configuration
tofu validate

# Plan deployment
tofu plan -out=tfplan

# Apply changes
tofu apply tfplan
```

### 3. Configure with Ansible

```bash
cd bootstrap-cluster/ansible

# Configure only maintenance VM
ansible-playbook -i inventory.ini playbooks/05-maintenance-vm.yml

# Or run full site playbook
ansible-playbook -i inventory.ini playbooks/site.yml
```

The Ansible playbook will automatically:
- Install all tools and dependencies
- **Fetch kubeconfig from the first control plane node**
- **Configure kubectl to access the K3s cluster**
- **Set up kubectl and helm autocompletion**
- Create maintenance scripts
- Set up workspace structure
- Configure Git and environment

### 4. Access the Maintenance VM

```bash
ssh ubuntu@10.21.0.42
# or
ssh ubuntu@k3s-maintenance
```

## Key Features

### 1. Conditional Creation
The maintenance VM is only created when `maintenance_ip` is set in terraform.tfvars. This allows easy enabling/disabling without code changes.

### 1. Pre-configured Environment
- All tools installed via cloud-init and Ansible
- **kubectl automatically configured with cluster access**
- **kubectl and helm autocompletion enabled**
- Bash aliases for common commands
- Custom MOTD with helpful information
- Pre-structured workspace directory

### 3. Comprehensive Tooling
- Complete Kubernetes management suite
- Network and system debugging tools
- Modern CLI utilities for better productivity
- Container runtime for testing

### 4. Maintenance Scripts
Ready-to-use scripts for common cluster operations:
- Health checks
- GPU monitoring
- Quick deployments
- Cleanup operations

### 5. Documentation
- Detailed usage guide in `docs/maintenance-vm.md`
- Quick reference script for common commands
- In-VM workspace README

## Usage Examples

### Check Cluster Health
```bash
/opt/maintenance-tools/scripts/cluster-health.sh
```

### Monitor GPUs
```bash
/opt/maintenance-tools/scripts/check-gpus.sh
```

### Interactive Cluster Management
```bash
k9s
```

### Quick Test Deployment
```bash
/opt/maintenance-tools/scripts/quick-deploy.sh nginx nginx:latest 3
```

### SSH to Worker Node
```bash
ssh ubuntu@k3s-wk-gpu1
```

### Network Debugging
```bash
# Test connectivity
ping k3s-cp1

# Monitor network
sudo iftop -i eth0

# Performance test
iperf3 -c k3s-wk-gpu1
```

## Disabling the Maintenance VM

To disable without affecting other resources:

1. Comment out maintenance VM variables in `terraform.tfvars`:
```hcl
# maintenance_mac = "00:16:3e:63:79:2d"
# maintenance_ip  = "10.21.0.42/16"
```

2. Apply changes:
```bash
cd bootstrap-cluster/terraform
tofu plan -out=tfplan
tofu apply tfplan
```

## Important Notes

1. **Network Configuration**: The MAC address (00:16:3e:63:79:2d) and IP (10.21.0.42) shown in the configuration need to be officially requested from MUL network administration for VLAN 633.

2. **Optional Resource**: The maintenance VM is completely optional. The cluster operates normally without it.

3. **No Auto-start**: The VM is configured with `onboot = false` to save resources when not needed.

4. **Security**: The maintenance VM has SSH access to all cluster nodes. Protect SSH keys appropriately.

5. **Resource Usage**: With only 2 cores and 4 GB RAM, avoid running heavy workloads on this VM.

## Next Steps

1. **Request Network Resources**: Contact MUL network administration to request/confirm MAC address and IP for VLAN 633
2. **Deploy**: Follow the deployment steps above
3. **Configure kubectl**: Set up kubeconfig from the control plane
4. **Test Scripts**: Run the maintenance scripts to verify functionality
5. **Customize**: Add any additional tools or scripts needed for your workflow

## Files Reference

```
bootstrap-cluster/
├── terraform/
│   ├── main.tf                          # Added maintenance VM resource
│   ├── variables.tf                     # Added maintenance variables
│   ├── terraform.tfvars                 # Added maintenance configuration
│   ├── cloud-init-maintenance.yml       # NEW: Cloud-init config
│   └── templates/
│       └── inventory.tpl                # Updated for maintenance group
├── ansible/
│   └── playbooks/
│       ├── 05-maintenance-vm.yml        # NEW: Maintenance playbook
│       └── site.yml                     # Updated to include maintenance
docs/
├── maintenance-vm.md                    # NEW: Complete documentation
scripts/
└── maintenance-vm-reference.sh          # NEW: Quick reference guide
README.md                                # Updated with maintenance VM info
```

## Validation

Configuration has been validated:
```bash
cd bootstrap-cluster/terraform
tofu validate
# Success! The configuration is valid.
```

The infrastructure is ready to deploy the maintenance VM when needed.
