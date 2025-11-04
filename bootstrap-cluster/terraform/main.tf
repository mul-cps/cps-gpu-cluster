terraform {
  required_version = ">= 1.5.0"
  
  required_providers {
    proxmox = {
      source  = "telmate/proxmox"
      version = "~> 2.9"
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
  
  # Machine type for GPU passthrough compatibility
  machine = "q35"
  bios    = "ovmf"
  
  # EFI disk
  efidisk {
    efitype = "4m"
    storage = var.storage_pool
  }
  
  # OS Disk
  disk {
    size    = "100G"
    type    = "scsi"
    storage = var.storage_pool
    ssd     = 1
  }
  
  # Network
  network {
    model  = "virtio"
    bridge = var.network_bridge
  }
  
  # Cloud-init
  os_type   = "cloud-init"
  ipconfig0 = "ip=10.0.0.${11 + count.index}/24,gw=${var.gateway}"
  
  ciuser     = var.vm_user
  sshkeys    = var.ssh_public_key
  nameserver = var.nameserver
  
  # Start on boot
  onboot = true
  
  # Lifecycle
  lifecycle {
    ignore_changes = [
      network,
      disk,
    ]
  }
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
  cores   = 16
  sockets = 1
  memory  = 131072  # 128 GB
  
  # Machine type for GPU passthrough
  machine = "q35"
  bios    = "ovmf"
  
  # EFI disk
  efidisk {
    efitype = "4m"
    storage = var.storage_pool
  }
  
  # OS Disk
  disk {
    size    = "500G"
    type    = "scsi"
    storage = var.storage_pool
    ssd     = 1
  }
  
  # NVMe scratch disk
  disk {
    size    = "1000G"
    type    = "scsi"
    storage = var.nvme_storage_pool
    ssd     = 1
  }
  
  # Network
  network {
    model  = "virtio"
    bridge = var.network_bridge
  }
  
  # GPU Passthrough - First A100
  hostpci0 {
    host    = var.gpu_pci_addresses[count.index * 2]
    pcie    = 1
    rombar  = 1
    x-vga   = 0
  }
  
  # GPU Passthrough - Second A100
  hostpci1 {
    host    = var.gpu_pci_addresses[count.index * 2 + 1]
    pcie    = 1
    rombar  = 1
    x-vga   = 0
  }
  
  # Cloud-init
  os_type   = "cloud-init"
  ipconfig0 = "ip=10.0.0.${21 + count.index}/24,gw=${var.gateway}"
  
  ciuser     = var.vm_user
  sshkeys    = var.ssh_public_key
  nameserver = var.nameserver
  
  # Additional args for VFIO
  args = "-cpu host,kvm=off"
  
  # Start on boot
  onboot = true
  
  # Lifecycle
  lifecycle {
    ignore_changes = [
      network,
      disk,
    ]
  }
}

# Generate Ansible inventory
resource "local_file" "ansible_inventory" {
  content = templatefile("${path.module}/templates/inventory.tpl", {
    control_plane_ips = [for vm in proxmox_vm_qemu.k3s_control_plane : vm.default_ipv4_address]
    worker_ips        = [for vm in proxmox_vm_qemu.k3s_gpu_worker : vm.default_ipv4_address]
    vm_user           = var.vm_user
  })
  filename = "${path.module}/../ansible/inventory.ini"
}
