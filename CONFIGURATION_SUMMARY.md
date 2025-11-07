# Configuration Summary

## What Was Fixed

This document summarizes the configuration changes made to prepare the cluster for deployment.

## 1. Network Configuration Update

**Issue**: IP address `10.21.0.39` and MAC address `00:16:3e:63:79:2a` were already in use on the network.

**Solution**: Updated worker VM 2 to use an available address from the MUL-allocated VLAN 633 range.

### Changes Made

**File**: `bootstrap-cluster/terraform/terraform.tfvars`

```diff
worker_macs = [
  "00:16:3e:63:79:2b",  # Worker 1 (GPU1) - 10.21.0.38
- "00:16:3e:63:79:2a",  # Worker 2 (GPU2) - 10.21.0.39  ← CONFLICT
+ "00:16:3e:63:79:2e",  # Worker 2 (GPU2) - 10.21.0.43  ← FIXED
  "00:16:3e:63:79:2c",  # Worker 3 (GPU3) - 10.21.0.40
  "00:16:3e:63:79:2d"   # Worker 4 (GPU4) - 10.21.0.41
]

worker_ips = [
  "10.21.0.38/16",
- "10.21.0.39/16",  ← CONFLICT
+ "10.21.0.43/16",  ← FIXED
  "10.21.0.40/16",
  "10.21.0.41/16"
]
```

**Result**: All VMs now have unique, non-conflicting network addresses.

## 2. SSH Connectivity Setup

**Issue**: Maintenance VM (10.21.0.42) could not SSH to cluster nodes because:
- Cluster VMs had public key from `bjoernl@nixos` in authorized_keys
- Maintenance VM didn't have the corresponding private key
- Ansible requires SSH connectivity to deploy K3s

**Solution**: Automated SSH key generation and distribution using Terraform + Proxmox API.

### Architecture

```
Terraform (Local)
    ↓ SSH
Proxmox Host (cit-gpu-01)
    ↓ qm guest exec (requires QEMU guest agent)
Inside VMs (maintenance, control planes, workers)
```

### New Files Created

#### 1. `bootstrap-cluster/terraform/ssh-setup.tf`

Implements:
- **Wait for QEMU guest agent** (up to 15 minutes)
- **Generate ed25519 SSH key** on maintenance VM
- **Fetch public key** using external data source
- **Distribute key** to all 7 cluster VMs (3 control plane + 4 workers)
- **Configure known_hosts** with all cluster node IPs

#### 2. `bootstrap-cluster/terraform/cloud-init-qemu-agent.yml`

Cloud-init configuration to install QEMU guest agent:
```yaml
#cloud-config
package_update: true
package_upgrade: false

packages:
  - qemu-guest-agent

runcmd:
  - systemctl enable qemu-guest-agent
  - systemctl start qemu-guest-agent
```

#### 3. `bootstrap-cluster/terraform/cloud-init-snippets.tf`

Terraform resource to:
- Upload cloud-init snippet to Proxmox before VM creation
- Ensure snippet is in `/var/lib/vz/snippets/`
- Trigger re-upload if snippet content changes

### Changes to Existing Files

#### `bootstrap-cluster/terraform/main.tf`

Added to all VM resources:
```hcl
resource "proxmox_vm_qemu" "control_plane" {
  # ... existing config ...
  
  agent = 1  # Enable guest agent communication
  
  cicustom = "user=local:snippets/install-qemu-agent.yml"
  
  depends_on = [
    null_resource.upload_qemu_agent_snippet
  ]
}
```

#### `bootstrap-cluster/terraform/variables.tf`

Added:
```hcl
variable "proxmox_host" {
  description = "Proxmox host for SSH access"
  type        = string
  default     = "cit-gpu-01.unileoben.ac.at"
}

variable "proxmox_ssh_user" {
  description = "SSH user for Proxmox host"
  type        = string
  default     = "root"
}
```

Also added required providers:
```hcl
required_providers {
  # ... existing providers ...
  null = {
    source  = "hashicorp/null"
    version = "~> 3.2"
  }
  external = {
    source  = "hashicorp/external"
    version = "~> 2.3"
  }
}
```

## 3. QEMU Guest Agent Installation

**Issue**: QEMU guest agent was not installed on VMs, blocking the use of `qm guest exec` commands.

**Solution**: Used Telmate Proxmox provider's native cloud-init functionality (`cicustom`) to install and enable the agent on first boot.

### How It Works

1. **Snippet Upload** (before VM creation):
   ```
   cloud-init-qemu-agent.yml → /var/lib/vz/snippets/install-qemu-agent.yml
   ```

2. **VM Creation** (with cloud-init reference):
   ```
   cicustom = "user=local:snippets/install-qemu-agent.yml"
   ```

3. **First Boot**:
   - Cloud-init runs
   - Installs `qemu-guest-agent` package
   - Enables service
   - Starts service

4. **Guest Agent Active**:
   - Terraform waits for agent to respond
   - Proceeds with SSH key setup

## 4. Documentation Created

Created comprehensive guides:

1. **`docs/ssh-key-setup.md`**
   - Manual approach using bash scripts
   - Background on the SSH problem
   - Step-by-step manual setup

2. **`docs/terraform-ssh-setup.md`**
   - Automated Terraform approach
   - Architecture explanation
   - How the automation works
   - Testing procedures

3. **`docs/qemu-guest-agent-setup.md`**
   - Why guest agent is required
   - How it's installed via cloud-init
   - Verification procedures
   - Troubleshooting common issues

4. **`DEPLOYMENT_CHECKLIST.md`**
   - Step-by-step deployment guide
   - All phases from prerequisites to validation
   - Troubleshooting references
   - Rollback procedures

5. **Helper Scripts** (in `scripts/`):
   - `setup-ssh-keys.sh` - Manual SSH setup
   - `find-vm-ids.sh` - Locate VM IDs
   
   *(Note: Scripts superseded by Terraform automation but kept for reference)*

## Current State

### ✅ Completed

1. Network conflict resolved
2. SSH automation implemented in Terraform
3. QEMU guest agent installation configured
4. All dependencies properly chained
5. Configuration validated (`tofu validate` passing)
6. Comprehensive documentation written

### 📋 Ready to Deploy

The configuration is now ready for:
```bash
cd bootstrap-cluster/terraform
tofu apply -var-file=secrets.tfvars
```

### 🔄 Deployment Flow

```
tofu apply
    ↓
Upload cloud-init snippet
    ↓
Create 8 VMs (cicustom → install qemu-agent)
    ↓
Wait for guest agents (up to 15 min)
    ↓
Generate SSH key on maintenance VM
    ↓
Distribute key to 7 cluster VMs
    ↓
Configure known_hosts
    ↓
✓ Infrastructure ready for Ansible
```

## Network Layout

| VM Name | VMID | Role | IP | MAC | GPUs |
|---------|------|------|----|----|------|
| cit-vm-35 | 106 | Control Plane 1 | 10.21.0.35/16 | 00:16:3e:63:79:28 | - |
| cit-vm-36 | 107 | Control Plane 2 | 10.21.0.36/16 | 00:16:3e:63:79:29 | - |
| cit-vm-37 | 108 | Control Plane 3 | 10.21.0.37/16 | 00:16:3e:63:79:30 | - |
| cit-vm-38 | 102 | Worker 1 (GPU1) | 10.21.0.38/16 | 00:16:3e:63:79:2b | 2× A100 |
| cit-vm-43 | 103 | Worker 2 (GPU2) | 10.21.0.43/16 | 00:16:3e:63:79:2e | 2× A100 |
| cit-vm-40 | 104 | Worker 3 (GPU3) | 10.21.0.40/16 | 00:16:3e:63:79:2c | 2× A100 |
| cit-vm-41 | 105 | Worker 4 (GPU4) | 10.21.0.41/16 | 00:16:3e:63:79:2d | 2× A100 |
| cit-vm-42 | 109 | Maintenance | 10.21.0.42/16 | 00:16:3e:63:79:2f | - |

**Total**: 8 VMs, 8 GPUs (2 per worker)

## Key Design Decisions

### Why QEMU Guest Agent?

The guest agent is **essential** for:
- Running commands inside VMs from Proxmox host
- Automating configuration without SSH passwords
- Enabling Terraform to orchestrate post-deployment setup

Without it:
- ❌ Cannot use `qm guest exec`
- ❌ Must manually configure SSH on each VM
- ❌ Ansible cannot connect to VMs

### Why Cloud-Init for Agent Installation?

Cloud-init is:
- ✅ Native to the Telmate Proxmox provider (`cicustom`)
- ✅ Runs on first boot automatically
- ✅ Declarative and version-controlled
- ✅ No manual intervention required

Alternatives considered:
- ❌ Pre-installed in template → harder to update
- ❌ Ansible playbook → chicken-and-egg (need SSH first)
- ❌ Manual installation → not reproducible

### Why Terraform for SSH Setup?

Using Terraform instead of post-deployment scripts:
- ✅ Single workflow (`tofu apply` does everything)
- ✅ Idempotent (can re-run safely)
- ✅ Dependencies tracked automatically
- ✅ State managed by Terraform
- ✅ Integrates with existing IaC

Alternatives considered:
- ❌ Bash scripts → separate workflow, error-prone
- ❌ Ansible → requires SSH already configured (circular dependency)
- ❌ Manual → not repeatable

## Validation Results

```bash
$ tofu validate
Success! The configuration is valid, but there were some validation warnings

Warning: Deprecated argument
│ cores is deprecated for proxmox_vm_qemu
│ Use cpu { cores = X } instead
```

**Status**: ✅ Valid (warnings are non-blocking)

## Next Steps

1. **Deploy Infrastructure**:
   ```bash
   cd bootstrap-cluster/terraform
   tofu apply -var-file=secrets.tfvars
   ```

2. **Wait for Completion** (15-20 minutes):
   - VMs created
   - Guest agents activated
   - SSH keys distributed

3. **Verify SSH**:
   ```bash
   ssh ubuntu@10.21.0.42  # maintenance VM
   ssh ubuntu@10.21.0.35  # should work without password
   ```

4. **Run Ansible**:
   ```bash
   cd ../ansible
   ansible-playbook -i inventory.ini site.yml
   ```

5. **Deploy K3s** and follow remaining steps in `DEPLOYMENT_CHECKLIST.md`

## References

- [Terraform SSH Setup Guide](docs/terraform-ssh-setup.md)
- [QEMU Guest Agent Setup](docs/qemu-guest-agent-setup.md)
- [Full Deployment Checklist](DEPLOYMENT_CHECKLIST.md)
- [Troubleshooting Guide](docs/troubleshooting.md)

## Support

If issues arise during deployment:

1. Check QEMU guest agent status: [docs/qemu-guest-agent-setup.md](docs/qemu-guest-agent-setup.md)
2. Review SSH setup logs: `tofu apply` output
3. Verify network connectivity: `ping` tests
4. Consult troubleshooting guide: [docs/troubleshooting.md](docs/troubleshooting.md)

---

**Configuration Date**: 2024  
**Terraform Version**: OpenTofu  
**Proxmox Version**: 8.x  
**Telmate Provider**: v3.0.2-rc04
