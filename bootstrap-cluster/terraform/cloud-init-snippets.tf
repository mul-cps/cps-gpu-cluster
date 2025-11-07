# Cloud-init configuration files for Proxmox VMs
# These need to be uploaded to Proxmox as snippets before VM creation

# Upload cloud-init snippet for QEMU guest agent installation
resource "null_resource" "upload_qemu_agent_snippet" {
  # Only run once, or when the snippet content changes
  triggers = {
    snippet_content = filemd5("${path.module}/cloud-init-qemu-agent.yml")
  }
  
  provisioner "local-exec" {
    command = <<-EOT
      #!/bin/bash
      set -e
      
      echo "Uploading cloud-init snippet for QEMU guest agent..."
      
      # Ensure snippets directory exists
      ssh ${var.proxmox_ssh_user}@${var.proxmox_host} \
        'mkdir -p /var/lib/vz/snippets'
      
      # Upload the snippet
      scp ${path.module}/cloud-init-qemu-agent.yml \
        ${var.proxmox_ssh_user}@${var.proxmox_host}:/var/lib/vz/snippets/install-qemu-agent.yml
      
      # Set proper permissions
      ssh ${var.proxmox_ssh_user}@${var.proxmox_host} \
        'chmod 644 /var/lib/vz/snippets/install-qemu-agent.yml'
      
      echo "✓ Cloud-init snippet uploaded successfully"
    EOT
  }
}
