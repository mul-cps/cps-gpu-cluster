# Proxmox Configuration
pm_api_url          = "https://proxmox.example.com:8006/api2/json"
pm_api_token_id     = "terraform@pam!terraform-token"
pm_api_token_secret = "your-secret-token-here"
pm_tls_insecure     = true

# Proxmox Node
proxmox_node = "pve"

# VM Template
vm_template = "ubuntu-22.04-cloudinit"

# Storage
storage_pool      = "local-lvm"
nvme_storage_pool = "nvme-pool"

# Network
network_bridge = "vmbr0"
gateway        = "10.0.0.1"
nameserver     = "10.0.0.1"

# VM User
vm_user = "ubuntu"

# SSH Public Key (replace with your actual key)
ssh_public_key = <<EOF
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQC... your-key-here
EOF

# GPU PCI Addresses
# Update these with your actual GPU PCI addresses
# Use `lspci | grep NVIDIA` on Proxmox host to find them
gpu_pci_addresses = [
  "0000:41:00.0",  # wk-gpu1 GPU 1
  "0000:42:00.0",  # wk-gpu1 GPU 2
  "0000:81:00.0",  # wk-gpu2 GPU 1
  "0000:82:00.0",  # wk-gpu2 GPU 2
  "0000:c1:00.0",  # wk-gpu3 GPU 1
  "0000:c2:00.0",  # wk-gpu3 GPU 2
  "0000:e1:00.0",  # wk-gpu4 GPU 1
  "0000:e2:00.0",  # wk-gpu4 GPU 2
]
