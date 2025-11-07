# SSH Key Setup via Proxmox QEMU Guest Agent

This guide explains how to set up SSH keys between VMs using Proxmox's QEMU guest agent, bypassing the need for SSH access or passwords.

## Problem

After creating VMs with Terraform, the maintenance VM cannot SSH to cluster nodes because:
- The maintenance VM doesn't have a private SSH key
- The VMs only have the public key from the provisioning machine (bjoernl@nixos)

## Solution

Use Proxmox's QEMU guest agent to:
1. Generate an SSH key on the maintenance VM
2. Distribute the public key to all cluster nodes
3. Set up known_hosts automatically

This works through the Proxmox API without requiring SSH access.

## Prerequisites

- All VMs must have QEMU guest agent installed and running
- You need SSH access to the Proxmox host
- You need root or sudo access on the Proxmox host

## Step-by-Step Instructions

### 1. SSH to the Proxmox Host

```bash
ssh root@cit-gpu-01.unileoben.ac.at
# Or if using a non-root user with sudo:
ssh bellensohn@cit-gpu-01.unileoben.ac.at
```

### 2. Copy the Scripts to Proxmox

From your local machine, copy the scripts:

```bash
# Copy from your local repo to Proxmox
scp scripts/find-vm-ids.sh scripts/setup-ssh-keys.sh root@cit-gpu-01.unileoben.ac.at:/tmp/
```

Or if you're already on Proxmox, clone the repo:

```bash
cd /tmp
git clone https://github.com/mul-cps/cps-gpu-cluster.git
cd cps-gpu-cluster/scripts
chmod +x find-vm-ids.sh setup-ssh-keys.sh
```

### 3. Find VM IDs

First, find the actual VM IDs:

```bash
./find-vm-ids.sh
```

Example output:
```
Finding VM IDs by name...
========================

106  k3s-cp1          running
107  k3s-cp2          running
108  k3s-cp3          running
102  k3s-wk-gpu1      running
103  k3s-wk-gpu2      running
104  k3s-wk-gpu3      running
105  k3s-wk-gpu4      running
109  k3s-maintenance  running
```

### 4. Update VM IDs in setup-ssh-keys.sh

Edit `setup-ssh-keys.sh` and update these lines with the actual VM IDs:

```bash
# VM IDs (adjust if different)
MAINTENANCE_VM=109  # Adjust to actual VM ID
CONTROL_PLANE_VMS=(106 107 108)
WORKER_VMS=(102 103 104 105)
```

### 5. Run the SSH Setup Script

Execute the script on the Proxmox host:

```bash
./setup-ssh-keys.sh
```

The script will:
1. ✓ Check QEMU guest agent on all VMs
2. ✓ Generate SSH key on maintenance VM (if not exists)
3. ✓ Fetch the public key
4. ✓ Distribute to all cluster nodes
5. ✓ Fix permissions
6. ✓ Add host keys to known_hosts
7. ✓ Test SSH connectivity

### 6. Verify SSH Works

From your local machine, SSH to maintenance VM and test:

```bash
ssh ubuntu@10.21.0.42  # maintenance VM

# Once on maintenance VM:
ssh ubuntu@10.21.0.35  # k3s-cp1
ssh ubuntu@10.21.0.38  # k3s-wk-gpu1
ssh ubuntu@10.21.0.40  # k3s-wk-gpu3
# etc.
```

All SSH connections should work without password prompts.

## Troubleshooting

### QEMU Guest Agent Not Responding

If you get "QEMU guest agent not responding" errors:

1. Check if the agent is running in the VM:
   ```bash
   # Via Proxmox console or qm command:
   qm guest cmd <vmid> ping
   ```

2. If not running, the VMs may need to be rebooted:
   ```bash
   qm reboot <vmid>
   ```

3. Verify agent is installed (should be via cloud-init):
   ```bash
   qm guest exec <vmid> -- systemctl status qemu-guest-agent
   ```

### SSH Still Not Working

1. Check if the key was added:
   ```bash
   qm guest exec <vmid> -- cat /home/ubuntu/.ssh/authorized_keys
   ```

2. Check permissions:
   ```bash
   qm guest exec <vmid> -- ls -la /home/ubuntu/.ssh/
   ```

3. Manually test from maintenance VM:
   ```bash
   ssh -vvv ubuntu@10.21.0.35  # Verbose output shows what's failing
   ```

### Permission Issues

If you get permission errors on known_hosts:

```bash
# Fix via Proxmox console:
qm guest exec <maintenance-vm-id> -- sudo -u ubuntu chmod 644 /home/ubuntu/.ssh/known_hosts
qm guest exec <maintenance-vm-id> -- sudo -u ubuntu chown ubuntu:ubuntu /home/ubuntu/.ssh/known_hosts
```

## Alternative: Manual Setup

If the script doesn't work, you can do it manually via Proxmox web console:

1. Open Proxmox web UI → Select maintenance VM → Console
2. Login as ubuntu (use the password from terraform.tfvars)
3. Generate key:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
   cat ~/.ssh/id_ed25519.pub
   ```
4. Copy the public key
5. For each cluster node, open console and:
   ```bash
   echo "paste-public-key-here" >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

## What the Script Does

### Using qm guest exec

The `qm guest exec` command runs commands inside VMs through the QEMU guest agent:

```bash
# Example: Run hostname command in VM 109
qm guest exec 109 -- hostname

# Example: Run command as specific user
qm guest exec 109 -- sudo -u ubuntu whoami

# Example: Create a file
qm guest exec 109 -- bash -c "echo 'content' > /tmp/file.txt"
```

This bypasses SSH entirely and works as long as:
- The VM is running
- QEMU guest agent is installed and active

### Security Note

The maintenance VM's SSH key will have access to all cluster nodes. This is intended for cluster management but means:
- Protect the maintenance VM
- Don't expose it to untrusted networks
- Consider rotating keys periodically
- The maintenance VM can be stopped when not needed (onboot=false by default)

## Next Steps

After SSH is working:
1. Run Ansible playbooks from the maintenance VM or your local machine
2. Configure kubectl access (Ansible playbook 05-maintenance-vm.yml handles this)
3. Start cluster deployment

## Files

- `find-vm-ids.sh` - Helper to list VM IDs
- `setup-ssh-keys.sh` - Main script to configure SSH keys
- This README

## References

- [Proxmox QEMU Guest Agent](https://pve.proxmox.com/wiki/Qemu-guest-agent)
- [qm guest exec documentation](https://pve.proxmox.com/pve-docs/qm.1.html)
