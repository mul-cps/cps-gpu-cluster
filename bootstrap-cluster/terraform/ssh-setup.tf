# SSH Key Distribution via Terraform
#
# This module uses Terraform's null_resource with Proxmox API (qm guest exec)
# to set up SSH keys between VMs without requiring SSH access

# Generate SSH key on maintenance VM using Proxmox qm guest exec
resource "null_resource" "generate_maintenance_ssh_key" {
  # Only run if maintenance VM exists
  count = var.maintenance_ip != "" ? 1 : 0
  
  # Re-run when maintenance VM is recreated
  triggers = {
    maintenance_vm_id = proxmox_vm_qemu.maintenance[0].id
  }
  
  provisioner "local-exec" {
    command = <<-EOT
      #!/bin/bash
      set -e
      
      VMID=${proxmox_vm_qemu.maintenance[0].vmid}
      
      # Wait for guest agent to be ready (up to 15 minutes)
      echo "Waiting for QEMU guest agent on maintenance VM (VMID: $VMID)..."
      echo "This may take several minutes as cloud-init installs qemu-guest-agent..."
      
      for i in {1..90}; do
        if ssh ${var.proxmox_ssh_user}@${var.proxmox_host} \
          "qm guest cmd $VMID ping" &>/dev/null; then
          echo "✓ Guest agent ready after $((i * 10)) seconds!"
          break
        fi
        
        if [ $i -eq 90 ]; then
          echo "ERROR: Guest agent not responding after 15 minutes"
          echo "Troubleshooting:"
          echo "1. Check VM status: qm status $VMID"
          echo "2. Check VM console: qm terminal $VMID"
          echo "3. Check cloud-init logs: qm guest exec $VMID -- journalctl -u cloud-init"
          exit 1
        fi
        
        # Show progress every minute
        if [ $((i % 6)) -eq 0 ]; then
          echo "Still waiting... ($((i * 10)) seconds elapsed)"
        fi
        
        sleep 10
      done
      
      # Verify qemu-guest-agent is installed and running
      echo "Verifying qemu-guest-agent installation..."
      if ! ssh ${var.proxmox_ssh_user}@${var.proxmox_host} \
        "qm guest exec $VMID -- systemctl is-active qemu-guest-agent" | grep -q "active"; then
        echo "WARNING: qemu-guest-agent may not be running properly"
      fi
      
      # Generate SSH key if it doesn't exist
      echo "Generating SSH key on maintenance VM..."
      ssh ${var.proxmox_ssh_user}@${var.proxmox_host} \
        "qm guest exec $VMID -- \
          su - ubuntu -c 'if [ ! -f /home/ubuntu/.ssh/id_ed25519 ]; then \
            mkdir -p /home/ubuntu/.ssh && \
            chmod 700 /home/ubuntu/.ssh && \
            ssh-keygen -t ed25519 -f /home/ubuntu/.ssh/id_ed25519 -N \"\" -C \"ubuntu@k3s-maintenance\"; \
            echo \"SSH key generated\"; \
          else \
            echo \"SSH key already exists\"; \
          fi'"
      
      echo "✓ SSH key generation complete"
    EOT
  }
  
  depends_on = [
    proxmox_vm_qemu.maintenance
  ]
}

# Fetch the public key from maintenance VM using qm guest exec
data "external" "maintenance_pubkey" {
  count = var.maintenance_ip != "" ? 1 : 0
  
  program = ["bash", "-c", <<-EOT
    set -e
    pubkey=$(ssh ${var.proxmox_ssh_user}@${var.proxmox_host} \
      "qm guest exec ${proxmox_vm_qemu.maintenance[0].vmid} -- \
        su - ubuntu -c 'cat /home/ubuntu/.ssh/id_ed25519.pub'" | \
      grep '^ssh-' | tr -d '\r\n')
    echo "{\"pubkey\": \"$pubkey\"}"
  EOT
  ]
  
  depends_on = [
    null_resource.generate_maintenance_ssh_key
  ]
}

# Distribute the key to control plane VMs
resource "null_resource" "distribute_ssh_key_control_plane" {
  count = var.maintenance_ip != "" ? length(proxmox_vm_qemu.k3s_control_plane) : 0
  
  triggers = {
    pubkey = data.external.maintenance_pubkey[0].result.pubkey
    vm_id  = proxmox_vm_qemu.k3s_control_plane[count.index].vmid
  }
  
  provisioner "local-exec" {
    command = <<-EOT
      #!/bin/bash
      set -e
      
      VMID=${proxmox_vm_qemu.k3s_control_plane[count.index].vmid}
      PUBKEY='${data.external.maintenance_pubkey[0].result.pubkey}'
      
      echo "Adding SSH key to control plane VM $VMID..."
      
      # Create .ssh directory if needed and add key
      ssh ${var.proxmox_ssh_user}@${var.proxmox_host} \
        "qm guest exec $VMID -- \
          su - ubuntu -c 'mkdir -p /home/ubuntu/.ssh && \
            chmod 700 /home/ubuntu/.ssh && \
            grep -qF \"$PUBKEY\" /home/ubuntu/.ssh/authorized_keys 2>/dev/null || \
            echo \"$PUBKEY\" >> /home/ubuntu/.ssh/authorized_keys && \
            chmod 600 /home/ubuntu/.ssh/authorized_keys'"
      
      echo "✓ SSH key added to VM $VMID"
    EOT
  }
  
  depends_on = [
    null_resource.generate_maintenance_ssh_key,
    data.external.maintenance_pubkey
  ]
}

# Distribute the key to worker VMs
resource "null_resource" "distribute_ssh_key_workers" {
  count = var.maintenance_ip != "" ? length(proxmox_vm_qemu.k3s_gpu_worker) : 0
  
  triggers = {
    pubkey = data.external.maintenance_pubkey[0].result.pubkey
    vm_id  = proxmox_vm_qemu.k3s_gpu_worker[count.index].vmid
  }
  
  provisioner "local-exec" {
    command = <<-EOT
      #!/bin/bash
      set -e
      
      VMID=${proxmox_vm_qemu.k3s_gpu_worker[count.index].vmid}
      PUBKEY='${data.external.maintenance_pubkey[0].result.pubkey}'
      
      echo "Adding SSH key to worker VM $VMID..."
      
      # Create .ssh directory if needed and add key
      ssh ${var.proxmox_ssh_user}@${var.proxmox_host} \
        "qm guest exec $VMID -- \
          su - ubuntu -c 'mkdir -p /home/ubuntu/.ssh && \
            chmod 700 /home/ubuntu/.ssh && \
            grep -qF \"$PUBKEY\" /home/ubuntu/.ssh/authorized_keys 2>/dev/null || \
            echo \"$PUBKEY\" >> /home/ubuntu/.ssh/authorized_keys && \
            chmod 600 /home/ubuntu/.ssh/authorized_keys'"
      
      echo "✓ SSH key added to VM $VMID"
    EOT
  }
  
  depends_on = [
    null_resource.generate_maintenance_ssh_key,
    data.external.maintenance_pubkey
  ]
}

# Set up known_hosts on maintenance VM
resource "null_resource" "setup_known_hosts" {
  count = var.maintenance_ip != "" ? 1 : 0
  
  triggers = {
    maintenance_vm_id = proxmox_vm_qemu.maintenance[0].id
    control_plane_ips = join(",", var.control_plane_ips)
    worker_ips        = join(",", var.worker_ips)
  }
  
  provisioner "local-exec" {
    command = <<-EOT
      #!/bin/bash
      set -e
      
      VMID=${proxmox_vm_qemu.maintenance[0].vmid}
      
      echo "Setting up known_hosts on maintenance VM..."
      
      # Create known_hosts file with proper permissions
      ssh ${var.proxmox_ssh_user}@${var.proxmox_host} \
        "qm guest exec $VMID -- \
          su - ubuntu -c 'touch /home/ubuntu/.ssh/known_hosts && chmod 644 /home/ubuntu/.ssh/known_hosts'"
      
      # Add host keys for all cluster nodes
      IPS="${join(" ", [for ip in concat(var.control_plane_ips, var.worker_ips) : split("/", ip)[0]])}"
      
      for ip in $IPS; do
        echo "Adding host key for $ip..."
        ssh ${var.proxmox_ssh_user}@${var.proxmox_host} \
          "qm guest exec $VMID -- \
            su - ubuntu -c 'ssh-keyscan -H $ip >> /home/ubuntu/.ssh/known_hosts 2>/dev/null'" || true
      done
      
      echo "✓ known_hosts configured"
    EOT
  }
  
  depends_on = [
    null_resource.distribute_ssh_key_control_plane,
    null_resource.distribute_ssh_key_workers
  ]
}

# Output the public key for reference
output "maintenance_ssh_pubkey" {
  value = var.maintenance_ip != "" ? data.external.maintenance_pubkey[0].result.pubkey : "N/A"
  description = "Public SSH key from maintenance VM"
}
