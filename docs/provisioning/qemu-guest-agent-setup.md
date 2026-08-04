# QEMU Guest Agent Setup via Cloud-Init

## Overview

The QEMU guest agent is **required** for the SSH key distribution to work via Terraform. This document explains how it's configured and verified.

## How It Works

### 1. Cloud-Init Snippet

The file `cloud-init-qemu-agent.yml` contains:

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

### 2. Snippet Upload (Automatic)

Terraform automatically uploads this snippet to Proxmox before creating VMs:

```hcl
resource "null_resource" "upload_qemu_agent_snippet" {
  provisioner "local-exec" {
    command = "scp cloud-init-qemu-agent.yml root@proxmox:/var/lib/vz/snippets/install-qemu-agent.yml"
  }
}
```

### 3. VM Configuration

All VMs reference this snippet:

```hcl
resource "proxmox_vm_qemu" "..." {
  # ... other config ...
  
  agent = 1  # Enable guest agent communication
  
  cicustom = "user=local:snippets/install-qemu-agent.yml"
  
  depends_on = [
    null_resource.upload_qemu_agent_snippet
  ]
}
```

### 4. Deployment Flow

```
tofu apply
    ↓
Upload cloud-init snippet to Proxmox
    ↓
Create VMs (with cicustom reference)
    ↓
Cloud-init runs on first boot
    ↓
Install qemu-guest-agent package
    ↓
Enable and start qemu-guest-agent service
    ↓
Wait for guest agent to respond (up to 15 minutes)
    ↓
Generate SSH keys via qm guest exec
```

## Verification

### Before VM Creation

Ensure the snippet will be uploaded:

```bash
cd bootstrap-cluster/terraform

# Check snippet exists locally
ls -la cloud-init-qemu-agent.yml

# Dry-run the upload
tofu plan | grep -A5 "upload_qemu_agent_snippet"
```

### After VM Creation

#### On Proxmox Host

Check if snippet was uploaded:

```bash
ssh root@cit-gpu-01.unileoben.ac.at 'ls -la /var/lib/vz/snippets/install-qemu-agent.yml'
```

#### Check Guest Agent Status

For each VM:

```bash
# Check if agent is responding
ssh root@cit-gpu-01.unileoben.ac.at 'qm guest cmd <vm-id> ping'

# Expected output:
# {"return":{}}

# Check agent version
ssh root@cit-gpu-01.unileoben.ac.at 'qm guest cmd <vm-id> get-guest-info'
```

#### Inside VM

If you can SSH to a VM (using password or your original key):

```bash
# Check if package is installed
dpkg -l | grep qemu-guest-agent

# Check service status
systemctl status qemu-guest-agent

# Check if it's running
ps aux | grep qemu-guest-agent
```

## Troubleshooting

### Snippet Not Uploaded

If Terraform fails to upload the snippet:

```bash
# Manual upload
scp bootstrap-cluster/terraform/cloud-init-qemu-agent.yml \
  root@cit-gpu-01.unileoben.ac.at:/var/lib/vz/snippets/install-qemu-agent.yml

# Set permissions
ssh root@cit-gpu-01.unileoben.ac.at \
  'chmod 644 /var/lib/vz/snippets/install-qemu-agent.yml'

# Re-run terraform
cd bootstrap-cluster/terraform
tofu apply
```

### Guest Agent Not Responding

If `qm guest cmd <vm-id> ping` fails:

#### 1. Check VM is Running

```bash
ssh root@cit-gpu-01.unileoben.ac.at 'qm status <vm-id>'
```

#### 2. Check Cloud-Init Logs

```bash
# Via Proxmox console or if you have SSH access
ssh ubuntu@<vm-ip> 'sudo journalctl -u cloud-init-local.service'
ssh ubuntu@<vm-ip> 'sudo journalctl -u cloud-init.service'
ssh ubuntu@<vm-ip> 'sudo cat /var/log/cloud-init.log'
```

Look for:
- Package installation logs
- Errors installing qemu-guest-agent
- Network issues preventing package download

#### 3. Check Agent Installation

Access via Proxmox web console (doesn't require SSH):

```bash
# Check if installed
dpkg -l | grep qemu-guest-agent

# If not installed, install manually
sudo apt update
sudo apt install -y qemu-guest-agent
sudo systemctl enable qemu-guest-agent
sudo systemctl start qemu-guest-agent
```

#### 4. Reboot VM

Sometimes the agent needs a reboot to start properly:

```bash
ssh root@cit-gpu-01.unileoben.ac.at 'qm reboot <vm-id>'

# Wait 2-3 minutes, then test
ssh root@cit-gpu-01.unileoben.ac.at 'qm guest cmd <vm-id> ping'
```

### Agent Takes Too Long to Start

The Terraform script waits up to 15 minutes for the guest agent. If it times out:

**Cause**: Cloud-init is installing packages, which requires:
- Network connectivity
- DNS resolution
- Access to Ubuntu package repositories
- Sufficient VM resources

**Solutions**:

1. **Check Network**: Ensure VM has network access
   ```bash
   ssh ubuntu@<vm-ip> 'ping -c 3 archive.ubuntu.com'
   ```

2. **Check Cloud-Init Status**:
   ```bash
   ssh ubuntu@<vm-ip> 'cloud-init status'
   # Should show: status: done
   ```

3. **Wait Longer**: First boot with package installation can take 5-10 minutes

4. **Manual Install**: If urgent, install manually and retry Terraform

### cicustom Not Working

If VMs don't use the snippet:

#### Check Template

Ensure the template doesn't have conflicting cloud-init config:

```bash
ssh root@cit-gpu-01.unileoben.ac.at 'qm config 9000 | grep cicustom'
```

If template has `cicustom`, it might conflict. Remove from template:

```bash
ssh root@cit-gpu-01.unileoben.ac.at 'qm set 9000 --delete cicustom'
```

#### Verify VM Config

After VM creation:

```bash
ssh root@cit-gpu-01.unileoben.ac.at 'qm config <vm-id> | grep cicustom'

# Should show:
# cicustom: user=local:snippets/install-qemu-agent.yml
```

#### Check Snippet Syntax

Validate the YAML:

```bash
# On Proxmox
cat /var/lib/vz/snippets/install-qemu-agent.yml | python3 -c "import sys,yaml; yaml.safe_load(sys.stdin)"
```

## Why Guest Agent is Required

The SSH setup process relies on the guest agent for:

1. **Command Execution**: `qm guest exec` requires the agent
2. **File Operations**: Reading/writing files inside VMs
3. **Status Checks**: Verifying VMs are ready before configuring SSH

Without the guest agent:
- ❌ Cannot generate SSH keys inside VMs
- ❌ Cannot add keys to authorized_keys
- ❌ Cannot set up known_hosts
- ❌ Must manually configure SSH on each VM

## Alternative: Manual Installation

If automation fails, install on each VM:

### Via Proxmox Console

1. Open Proxmox UI → Select VM → Console
2. Login as ubuntu (use password from terraform.tfvars)
3. Run:
   ```bash
   sudo apt update
   sudo apt install -y qemu-guest-agent
   sudo systemctl enable qemu-guest-agent
   sudo systemctl start qemu-guest-agent
   ```
4. Exit console
5. Test: `qm guest cmd <vm-id> ping`

### Via Ansible

If SSH is already working with passwords:

```yaml
- name: Install QEMU Guest Agent
  hosts: all
  become: yes
  tasks:
    - name: Install qemu-guest-agent
      apt:
        name: qemu-guest-agent
        state: present
        update_cache: yes
    
    - name: Enable and start qemu-guest-agent
      systemd:
        name: qemu-guest-agent
        enabled: yes
        state: started
```

## Best Practices

1. **Always verify** guest agent is responding before running SSH setup
2. **Check logs** if VMs are created but agent doesn't respond
3. **Use template** with pre-installed agent for faster deployments
4. **Monitor timing**: First boot with package install takes longer
5. **Network first**: Ensure VMs have network before expecting package installs

## Testing Guest Agent

Quick test script:

```bash
#!/bin/bash
# Test guest agent on all VMs

for vmid in 106 107 108 102 103 104 105 109; do
  echo -n "VM $vmid: "
  if ssh root@cit-gpu-01.unileoben.ac.at "qm guest cmd $vmid ping" &>/dev/null; then
    echo "✓ Agent OK"
  else
    echo "✗ Agent not responding"
  fi
done
```

## Summary

| Component | Purpose | Status Check |
|-----------|---------|--------------|
| **cloud-init-qemu-agent.yml** | Package install script | `ls /var/lib/vz/snippets/install-qemu-agent.yml` |
| **cicustom parameter** | VM config reference | `qm config <vm-id> \| grep cicustom` |
| **agent = 1** | Enable agent in VM | `qm config <vm-id> \| grep agent` |
| **qemu-guest-agent package** | Actual agent software | `dpkg -l \| grep qemu-guest-agent` |
| **qemu-guest-agent.service** | Running service | `systemctl status qemu-guest-agent` |
| **Communication** | Proxmox ↔ VM | `qm guest cmd <vm-id> ping` |

All must be working for SSH setup automation to succeed.
