# SSH Key Setup via Terraform

This guide explains how to automatically set up SSH keys between VMs using Terraform and the Proxmox API.

## Overview

The Terraform configuration (`ssh-setup.tf`) automatically:
1. Generates an SSH key on the maintenance VM
2. Fetches the public key
3. Distributes it to all cluster nodes (control plane + workers)
4. Sets up known_hosts on the maintenance VM

All of this is done via Proxmox's QEMU guest agent API (`qm guest exec`), which means:
- ✓ No SSH access required
- ✓ No passwords needed
- ✓ Fully automated as part of `tofu apply`
- ✓ Idempotent (safe to re-run)

## How It Works

### Architecture

```
Your Workstation
    ↓
  Terraform
    ↓
  Proxmox API / SSH to Proxmox Host
    ↓
  qm guest exec commands
    ↓
  VM Guest Agent
    ↓
  Commands execute inside VMs
```

### Process Flow

1. **Terraform creates VMs** → All VMs have QEMU guest agent enabled
2. **null_resource waits** → For guest agent to respond
3. **Generate key** → `qm guest exec` creates SSH key on maintenance VM
4. **Fetch key** → `qm guest exec` reads public key
5. **Distribute** → `qm guest exec` adds key to all cluster nodes
6. **Setup known_hosts** → `qm guest exec` adds host keys

## Prerequisites

### 1. SSH Access to Proxmox Host

You need SSH access from your workstation to the Proxmox host:

```bash
# Test SSH access
ssh root@cit-gpu-01.unileoben.ac.at 'qm list'
```

If using a non-root user, ensure they have permissions for `qm guest exec`.

### 2. SSH Key for Proxmox

Add your SSH key to the Proxmox host:

```bash
# Copy your public key
ssh-copy-id root@cit-gpu-01.unileoben.ac.at

# Or manually:
cat ~/.ssh/id_rsa.pub | ssh root@cit-gpu-01.unileoben.ac.at 'cat >> ~/.ssh/authorized_keys'
```

### 3. Configure Variables

In `terraform.tfvars`, ensure these are set:

```hcl
# Proxmox host for SSH access (qm guest exec commands)
proxmox_host = "cit-gpu-01.unileoben.ac.at"

# SSH user for Proxmox host (usually root)
proxmox_ssh_user = "root"

# Enable maintenance VM
maintenance_mac = "00:16:3e:63:79:2d"
maintenance_ip  = "10.21.0.42/16"
```

These variables are already in `variables.tf` with sensible defaults.

## Usage

### Deploy Everything

Simply run your normal Terraform deployment:

```bash
cd bootstrap-cluster/terraform

# Plan
tofu plan -out=tfplan

# Apply (creates VMs AND sets up SSH keys)
tofu apply tfplan
```

The SSH key setup happens automatically after the VMs are created.

### What Happens During Apply

You'll see output like:

```
null_resource.generate_maintenance_ssh_key[0]: Creating...
null_resource.generate_maintenance_ssh_key[0]: Provisioning with 'local-exec'...
Waiting for QEMU guest agent on maintenance VM...
Guest agent ready!
Generating SSH key on maintenance VM...
SSH key generated

null_resource.distribute_ssh_key_control_plane[0]: Creating...
Adding SSH key to control plane VM 106...
✓ SSH key added to VM 106

[... more output ...]

null_resource.setup_known_hosts[0]: Creating...
Setting up known_hosts on maintenance VM...
Adding host key for 10.21.0.35...
✓ known_hosts configured

Apply complete!

Outputs:
maintenance_ssh_pubkey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGx..."
```

### Verify SSH Works

After apply completes:

```bash
# SSH to maintenance VM
ssh ubuntu@10.21.0.42

# Test SSH to cluster nodes (no password!)
ssh ubuntu@10.21.0.35  # k3s-cp1
ssh ubuntu@10.21.0.38  # k3s-wk-gpu1
ssh ubuntu@10.21.0.40  # k3s-wk-gpu3
```

### Manual Trigger

If you need to regenerate/redistribute keys without recreating VMs:

```bash
# Taint the SSH setup resources
tofu taint 'null_resource.generate_maintenance_ssh_key[0]'
tofu taint 'null_resource.distribute_ssh_key_control_plane[0]'
tofu taint 'null_resource.distribute_ssh_key_workers[0]'
tofu taint 'null_resource.setup_known_hosts[0]'

# Apply to recreate
tofu apply
```

## Technical Details

### null_resource with local-exec

The `ssh-setup.tf` file uses `null_resource` with `local-exec` provisioners:

```hcl
resource "null_resource" "generate_maintenance_ssh_key" {
  provisioner "local-exec" {
    command = <<-EOT
      ssh root@proxmox-host \
        "qm guest exec ${vm_id} -- \
          sudo -u ubuntu bash -c 'ssh-keygen ...'"
    EOT
  }
}
```

This runs shell commands on your workstation that SSH to Proxmox and execute `qm guest exec`.

### data "external"

The public key is fetched using an `external` data source:

```hcl
data "external" "maintenance_pubkey" {
  program = ["bash", "-c", "ssh root@proxmox 'qm guest exec...' | jq..."]
}
```

This runs a command and parses JSON output.

### Triggers

Resources have triggers that cause them to re-run when dependencies change:

```hcl
triggers = {
  maintenance_vm_id = proxmox_vm_qemu.maintenance[0].id
  pubkey = data.external.maintenance_pubkey[0].result.pubkey
}
```

## Troubleshooting

### SSH to Proxmox Fails

```bash
# Test basic SSH
ssh root@cit-gpu-01.unileoben.ac.at

# Test qm command
ssh root@cit-gpu-01.unileoben.ac.at 'qm list'
```

If this fails, check:
- SSH keys are set up for the Proxmox host
- Firewall allows SSH
- User has appropriate permissions

### Guest Agent Not Responding

If you see "Waiting for QEMU guest agent..." for a long time:

```bash
# Check agent status via Proxmox
ssh root@cit-gpu-01.unileoben.ac.at 'qm guest cmd <vm-id> ping'

# Check if VM is running
ssh root@cit-gpu-01.unileoben.ac.at 'qm status <vm-id>'

# Reboot if needed
ssh root@cit-gpu-01.unileoben.ac.at 'qm reboot <vm-id>'
```

### Key Not Being Added

Check if the key distribution succeeded:

```bash
# Verify key on target VM
ssh root@cit-gpu-01.unileoben.ac.at \
  'qm guest exec 106 -- cat /home/ubuntu/.ssh/authorized_keys'

# Check for the maintenance key
ssh ubuntu@10.21.0.35 'grep "ubuntu@k3s-maintenance" ~/.ssh/authorized_keys'
```

### SSH Still Requires Password

Possible issues:
1. Key not in authorized_keys
2. Permissions wrong on .ssh directory or authorized_keys
3. SELinux/AppArmor blocking
4. Wrong key being used

Debug:
```bash
# Verbose SSH output
ssh -vvv ubuntu@10.21.0.35

# Check permissions
ssh root@cit-gpu-01.unileoben.ac.at \
  'qm guest exec 106 -- ls -la /home/ubuntu/.ssh/'
```

### Re-run Just SSH Setup

If VMs are already created but SSH setup failed:

```bash
# Taint and reapply
tofu taint 'null_resource.generate_maintenance_ssh_key[0]'
tofu apply -target='null_resource.generate_maintenance_ssh_key[0]'
tofu apply -target='null_resource.distribute_ssh_key_control_plane'
tofu apply -target='null_resource.distribute_ssh_key_workers'
tofu apply -target='null_resource.setup_known_hosts[0]'
```

## Comparison with Manual Script

| Aspect | Manual Script | Terraform |
|--------|---------------|-----------|
| **Automation** | Run separately | Part of `tofu apply` |
| **VM IDs** | Manual lookup | Automatic |
| **Idempotent** | Yes | Yes |
| **Dependencies** | Manual ordering | Automatic |
| **State tracking** | No | Yes (via triggers) |
| **Re-runs** | Safe | Safe |

## Security Considerations

1. **Proxmox SSH Access**: Your workstation needs SSH access to Proxmox
   - Use SSH keys, not passwords
   - Consider SSH jump host if Proxmox isn't directly accessible

2. **Maintenance VM Key**: Generated on maintenance VM, stored there
   - Key is ed25519 (modern, secure)
   - No passphrase (for automation)
   - Only used within the cluster network (VLAN 633)

3. **Known Hosts**: Populated automatically
   - Uses ssh-keyscan with -H (hashed)
   - Prevents MITM attacks within cluster

## Advanced Configuration

### Use Non-Root User on Proxmox

If using a non-root user:

```hcl
# In terraform.tfvars
proxmox_ssh_user = "bellensohn"
```

Ensure the user has sudo/qm permissions:
```bash
# On Proxmox host
pveum acl modify / -user bellensohn -role PVEVMAdmin
```

### Custom SSH Options

Edit `ssh-setup.tf` to add SSH options:

```bash
ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null ...
```

### Skip SSH Setup

To deploy VMs without SSH setup:

```bash
# Don't set maintenance_ip
# In terraform.tfvars:
# maintenance_mac = ""
# maintenance_ip  = ""

# SSH setup resources won't be created
tofu apply
```

## Files

- `ssh-setup.tf` - Main SSH setup Terraform code
- `variables.tf` - Variables including `proxmox_host` and `proxmox_ssh_user`
- `terraform.tfvars` - Your configuration values

## Next Steps

After SSH is working:
1. SSH to maintenance VM: `ssh ubuntu@10.21.0.42`
2. Run Ansible playbooks: `cd ~/cps-gpu-cluster/bootstrap-cluster/ansible && ansible-playbook -i inventory.ini playbooks/site.yml`
3. Configure kubectl (done by Ansible playbook 05-maintenance-vm.yml)
4. Start using k9s, kubectl, etc.
