terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    proxmox = {
      source  = "telmate/proxmox"
      version = "3.0.2-rc04"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3"
    }
  }
}

provider "proxmox" {
  pm_api_url          = var.pm_api_url
  pm_api_token_id     = var.pm_api_token_id
  pm_api_token_secret = var.pm_api_token_secret
  pm_tls_insecure     = var.pm_tls_insecure
}

# Control Plane VMs
resource "proxmox_vm_qemu" "k3s_control_plane" {
  count       = 3
  name        = "k3s-cp${count.index + 1}"
  target_node = var.proxmox_node
  
  # VM Configuration
  clone      = var.vm_template
  full_clone = true
  
  # Hardware
  cores   = 4
  sockets = 1
  memory  = 16384
  
  # SCSI controller
  scsihw = "virtio-scsi-single"
  
  # Machine type for GPU passthrough compatibility
  machine = "q35"
  bios    = "ovmf"
  
  # Serial console
  serial {
    id   = 0
    type = "socket"
  }
  
  # EFI disk (v3 provider supports efidisk block)
  efidisk {
    efitype = "4m"
    storage = var.storage_pool
  }
  
  # OS Disk
  disk {
    slot    = "scsi0"
    size    = "100G"
    type    = "disk"
    storage = var.storage_pool
  }
  
  # Cloud-init drive
  disk {
    slot    = "ide2"
    type    = "cloudinit"
    storage = var.storage_pool
  }
  
  # Network
  network {
    id     = 0
    model  = "virtio"
    bridge = var.network_bridge
    macaddr = var.control_plane_macs[count.index]
    tag    = var.vlan_id
  }
  
  # Cloud-init
  os_type   = "cloud-init"
  ipconfig0 = "ip=${var.control_plane_ips[count.index]},gw=${var.gateway}"
  
  ciuser     = var.vm_user
  cipassword = var.vm_password
  sshkeys    = var.ssh_public_key
  nameserver = "${var.nameserver} ${var.nameserver_secondary}"
  
  # Use cloud-init vendor snippet to install qemu-guest-agent
  # Using vendor= keeps the user-data (ciuser/cipassword) intact
  cicustom = "vendor=local:snippets/install-qemu-agent.yml"
  
  # VM description and tags for Proxmox UI
  desc = "K3s Control Plane Node ${count.index + 1} - Ubuntu 24.04 LTS"
  tags = "k3s,control-plane,kubernetes,ubuntu-2404"
  
  # Boot configuration
  boot    = "order=scsi0"
  
  # QEMU Guest Agent
  agent = 1
  
  # Start on boot
  onboot = true
  
  # Lifecycle
  lifecycle {
    ignore_changes = [
      network,
      disk,
    ]
  }
  
  # Ensure cloud-init snippet is uploaded before VM creation
  depends_on = [
    null_resource.upload_qemu_agent_snippet
  ]
}

# GPU Worker VMs
resource "proxmox_vm_qemu" "k3s_gpu_worker" {
  count       = 4
  name        = "k3s-wk-gpu${count.index + 1}"
  target_node = var.proxmox_node
  
  # VM Configuration
  clone      = var.vm_template
  full_clone = true
  
  # Hardware
  cores   = 48 #16
  sockets = 1
  memory  = 131072  # 128 GB
  
  # SCSI controller
  scsihw = "virtio-scsi-single"
  
  # Machine type for GPU passthrough
  machine = "q35"
  bios    = "ovmf"
  
  # Serial console
  serial {
    id   = 0
    type = "socket"
  }
  
  # EFI disk (v3 provider supports efidisk block)
  efidisk {
    efitype = "4m"
    storage = var.storage_pool
  }
  
  # OS Disk
  disk {
    slot    = "scsi0"
    size    = "500G"
    type    = "disk"
    storage = var.storage_pool
  }
  
  # NVMe scratch disk
  disk {
    slot    = "scsi1"
    size    = "1000G"
    type    = "disk"
    storage = var.nvme_storage_pool
  }
  
  # Cloud-init drive
  disk {
    slot    = "ide2"
    type    = "cloudinit"
    storage = var.storage_pool
  }
  
  # Network
  network {
    id     = 0
    model  = "virtio"
    bridge = var.network_bridge
    macaddr = var.worker_macs[count.index]
    tag    = var.vlan_id
  }
  
  # GPU Passthrough using resource mappings
  pcis {
    pci0 {
      mapping {
        mapping_id = "NVIDIA-A100-40GB"
        pcie       = true
        rombar     = true
      }
    }
    pci1 {
      mapping {
        mapping_id = "NVIDIA-A100-40GB"
        pcie       = true
        rombar     = true
      }
    }
  }
  
  # Cloud-init
  os_type   = "cloud-init"
  ipconfig0 = "ip=${var.worker_ips[count.index]},gw=${var.gateway}"
  
  ciuser     = var.vm_user
  cipassword = var.vm_password
  sshkeys    = var.ssh_public_key
  nameserver = "${var.nameserver} ${var.nameserver_secondary}"
  
  # Use cloud-init vendor snippet to install qemu-guest-agent
  # Using vendor= keeps the user-data (ciuser/cipassword) intact
  cicustom = "vendor=local:snippets/install-qemu-agent.yml"
  
    # VM description and tags for Proxmox UI
  desc = "K3s GPU Worker Node ${count.index + 1} - 2x A100 GPUs - Ubuntu 24.04 LTS"
  tags = "k3s,worker,gpu,nvidia-a100,kubernetes,ubuntu-2404"
  
  # Boot configuration
  boot    = "order=scsi0"
  
  # QEMU Guest Agent
  agent = 1
  
  # Start on boot
  onboot = true
  
  # Lifecycle
  lifecycle {
    ignore_changes = [
      network,
      disk,
    ]
  }
  
  # Ensure cloud-init snippet is uploaded before VM creation
  depends_on = [
    null_resource.upload_qemu_agent_snippet
  ]
}

# Maintenance VM (optional - enabled when maintenance_ip is set)
resource "proxmox_vm_qemu" "maintenance" {
  count       = var.maintenance_ip != "" ? 1 : 0
  name        = "k3s-maintenance"
  target_node = var.proxmox_node
  
  # VM Configuration
  clone      = var.vm_template
  full_clone = true
  
  # Hardware - Minimal resources for maintenance tasks
  cores   = 2
  sockets = 1
  memory  = 4096  # 4 GB
  
  # SCSI controller
  scsihw = "virtio-scsi-single"
  
  # Machine type
  machine = "q35"
  bios    = "ovmf"
  
  # Serial console
  serial {
    id   = 0
    type = "socket"
  }
  
  # EFI disk
  efidisk {
    efitype = "4m"
    storage = var.storage_pool
  }
  
  # OS Disk - Smaller for maintenance VM
  disk {
    slot    = "scsi0"
    size    = "50G"
    type    = "disk"
    storage = var.storage_pool
  }
  
  # Cloud-init drive
  disk {
    slot    = "ide2"
    type    = "cloudinit"
    storage = var.storage_pool
  }
  
  # Network
  network {
    id     = 0
    model  = "virtio"
    bridge = var.network_bridge
    macaddr = var.maintenance_mac
    tag    = var.vlan_id
  }
  
  # Cloud-init
  os_type   = "cloud-init"
  ipconfig0 = "ip=${var.maintenance_ip},gw=${var.gateway}"
  
  ciuser     = var.vm_user
  cipassword = var.vm_password
  sshkeys    = var.ssh_public_key
  nameserver = "${var.nameserver} ${var.nameserver_secondary}"
  
  # Use cloud-init vendor snippet to install qemu-guest-agent
  # Using vendor= keeps the user-data (ciuser/cipassword) intact
  cicustom = "vendor=local:snippets/install-qemu-agent.yml"
  
  # VM description and tags for Proxmox UI
  desc = "Maintenance VM - Ansible, Terraform, Git, Debugging Tools - Ubuntu 24.04 LTS"
  tags = "maintenance,tools,ansible,terraform,ubuntu-2404"
  
  # Boot configuration
  boot    = "order=scsi0"
  
  # QEMU Guest Agent
  agent = 1
  
  # Start on boot
  onboot = false  # Don't auto-start maintenance VM
  
  # Lifecycle
  lifecycle {
    ignore_changes = [
      network,
      disk,
    ]
  }
  
  # Ensure cloud-init snippet is uploaded before VM creation
  depends_on = [
    null_resource.upload_qemu_agent_snippet
  ]
}

# Storage VM (optional - enabled when storage_ip is set)
# Provides NFS storage for the cluster until proper storage server is available
resource "proxmox_vm_qemu" "storage" {
  count       = var.storage_ip != "" ? 1 : 0
  name        = "k3s-storage"
  target_node = var.proxmox_node
  
  # VM Configuration
  clone      = var.vm_template
  full_clone = true
  
  # Hardware - More resources for storage server
  cores   = 4
  sockets = 1
  memory  = 8192  # 8 GB
  
  # SCSI controller
  scsihw = "virtio-scsi-single"
  
  # Machine type
  machine = "q35"
  bios    = "ovmf"
  
  # Serial console
  serial {
    id   = 0
    type = "socket"
  }
  
  # EFI disk
  efidisk {
    efitype = "4m"
    storage = var.storage_pool
  }
  
  # OS Disk
  disk {
    slot    = "scsi0"
    size    = "100G"
    type    = "disk"
    storage = var.storage_pool
  }
  
  # Large data disk for NFS storage
  disk {
    slot    = "scsi1"
    size    = "2000G"  # 2TB for cluster storage
    type    = "disk"
    storage = var.storage_pool
  }
  
  # Cloud-init drive
  disk {
    slot    = "ide2"
    type    = "cloudinit"
    storage = var.storage_pool
  }
  
  # Network
  network {
    id     = 0
    model  = "virtio"
    bridge = var.network_bridge
    macaddr = var.storage_mac
    tag    = var.vlan_id
  }
  
  # Cloud-init
  os_type   = "cloud-init"
  ipconfig0 = "ip=${var.storage_ip},gw=${var.gateway}"
  
  ciuser     = var.vm_user
  cipassword = var.vm_password
  sshkeys    = var.ssh_public_key
  nameserver = "${var.nameserver} ${var.nameserver_secondary}"
  
  # Use cloud-init vendor snippet to install qemu-guest-agent
  # Using vendor= keeps the user-data (ciuser/cipassword) intact
  cicustom = "vendor=local:snippets/install-qemu-agent.yml"
  
  # VM description and tags for Proxmox UI
  desc = "NFS Storage Node - Provides shared storage for K3s cluster - Ubuntu 24.04 LTS"
  tags = "storage,nfs,k3s,ubuntu-2404"
  
  # Boot configuration
  boot    = "order=scsi0"
  
  # QEMU Guest Agent
  agent = 1
  
  # Start on boot
  onboot = true  # Auto-start storage VM
  
  # Lifecycle
  lifecycle {
    ignore_changes = [
      network,
      disk,
    ]
  }
  
  # Ensure cloud-init snippet is uploaded before VM creation
  depends_on = [
    null_resource.upload_qemu_agent_snippet
  ]
}

# Generate Ansible inventory
resource "local_file" "ansible_inventory" {
  content = templatefile("${path.module}/templates/inventory.tpl", {
    control_plane_ips = [for vm in proxmox_vm_qemu.k3s_control_plane : vm.default_ipv4_address]
    worker_ips        = [for vm in proxmox_vm_qemu.k3s_gpu_worker : vm.default_ipv4_address]
    storage_ips       = var.storage_ip != "" ? [for vm in proxmox_vm_qemu.storage : vm.default_ipv4_address] : []
    maintenance_ips   = var.maintenance_ip != "" ? [for vm in proxmox_vm_qemu.maintenance : vm.default_ipv4_address] : []
    vm_user           = var.vm_user
  })
  filename = "${path.module}/../ansible/inventory.ini"
}
