variable "pm_api_url" {
  description = "Proxmox API URL"
  type        = string
}

variable "pm_api_token_id" {
  description = "Proxmox API Token ID"
  type        = string
}

variable "pm_api_token_secret" {
  description = "Proxmox API Token Secret"
  type        = string
  sensitive   = true
}

variable "pm_tls_insecure" {
  description = "Skip TLS verification for Proxmox API"
  type        = bool
  default     = true
}

variable "proxmox_node" {
  description = "Proxmox node name where VMs will be created"
  type        = string
}

variable "vm_template" {
  description = "Name of the VM template to clone"
  type        = string
  default     = "ubuntu-22.04-cloudinit"
}

variable "storage_pool" {
  description = "Storage pool for VM disks"
  type        = string
  default     = "local-lvm"
}

variable "nvme_storage_pool" {
  description = "NVMe storage pool for fast scratch disks"
  type        = string
  default     = "nvme-pool"
}

variable "network_bridge" {
  description = "Network bridge for VMs"
  type        = string
  default     = "vmbr0"
}

variable "gateway" {
  description = "Network gateway"
  type        = string
  default     = "10.0.0.1"
}

variable "nameserver" {
  description = "DNS nameserver"
  type        = string
  default     = "10.0.0.1"
}

variable "vm_user" {
  description = "Default user for cloud-init"
  type        = string
  default     = "ubuntu"
}

variable "ssh_public_key" {
  description = "SSH public key for VM access"
  type        = string
}

variable "gpu_pci_addresses" {
  description = "List of GPU PCI addresses for passthrough (format: 0000:XX:YY.Z)"
  type        = list(string)
  default = [
    "0000:41:00.0",  # wk-gpu1 GPU 1
    "0000:42:00.0",  # wk-gpu1 GPU 2
    "0000:81:00.0",  # wk-gpu2 GPU 1
    "0000:82:00.0",  # wk-gpu2 GPU 2
    "0000:c1:00.0",  # wk-gpu3 GPU 1
    "0000:c2:00.0",  # wk-gpu3 GPU 2
    "0000:e1:00.0",  # wk-gpu4 GPU 1
    "0000:e2:00.0",  # wk-gpu4 GPU 2
  ]
}
