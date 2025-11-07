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

variable "proxmox_host" {
  description = "Proxmox host address for SSH access (for qm guest exec commands)"
  type        = string
  default     = "cit-gpu-01.unileoben.ac.at"
}

variable "proxmox_ssh_user" {
  description = "SSH user for Proxmox host access (for qm guest exec commands)"
  type        = string
  default     = "root"
}

variable "vm_template" {
  description = "Name of the VM template to clone"
  type        = string
  default     = "ubuntu-24.04-cloudinit"
}

variable "storage_pool" {
  description = "Storage pool for VM disks"
  type        = string
  default     = "NvmeZFSstorage"
}

variable "nvme_storage_pool" {
  description = "NVMe storage pool for fast scratch disks"
  type        = string
  default     = "NvmeZFSstorage"
}

variable "network_bridge" {
  description = "Network bridge for VMs"
  type        = string
  default     = "vmbr0"
}

variable "vlan_id" {
  description = "VLAN ID for VM network interfaces"
  type        = number
  default     = 633
}

variable "gateway" {
  description = "Network gateway"
  type        = string
  default     = "10.21.1.17"
}

variable "nameserver" {
  description = "Primary DNS nameserver"
  type        = string
  default     = "193.171.87.249"
}

variable "nameserver_secondary" {
  description = "Secondary DNS nameserver"
  type        = string
  default     = "193.171.87.250"
}

# MAC addresses and IPs assigned by MUL for VLAN 633
variable "control_plane_macs" {
  description = "MAC addresses for control plane VMs (cit-vm-35, 36, 37)"
  type        = list(string)
  default = [
    "00:16:3e:63:79:26",  # k3s-cp1 -> cit-vm-35 (10.21.0.35)
    "00:16:3e:63:79:27",  # k3s-cp2 -> cit-vm-36 (10.21.0.36)
    "00:16:3e:63:79:28",  # k3s-cp3 -> cit-vm-37 (10.21.0.37)
  ]
}

variable "control_plane_ips" {
  description = "Static IP addresses for control plane VMs"
  type        = list(string)
  default = [
    "10.21.0.35/16",  # k3s-cp1 (cit-vm-35)
    "10.21.0.36/16",  # k3s-cp2 (cit-vm-36)
    "10.21.0.37/16",  # k3s-cp3 (cit-vm-37)
  ]
}

variable "worker_macs" {
  description = "MAC addresses for GPU worker VMs (cit-vm-38, 39, 40, 41)"
  type        = list(string)
  default = [
    "00:16:3e:63:79:29",  # k3s-wk-gpu1 -> cit-vm-38 (10.21.0.38)
    "00:16:3e:63:79:2a",  # k3s-wk-gpu2 -> cit-vm-39 (10.21.0.39)
    "00:16:3e:63:79:2b",  # k3s-wk-gpu3 -> cit-vm-40 (10.21.0.40)
    "00:16:3e:63:79:2c",  # k3s-wk-gpu4 -> cit-vm-41 (10.21.0.41)
  ]
}

variable "worker_ips" {
  description = "Static IP addresses for GPU worker VMs"
  type        = list(string)
  default = [
    "10.21.0.38/16",  # k3s-wk-gpu1 (cit-vm-38)
    "10.21.0.39/16",  # k3s-wk-gpu2 (cit-vm-39)
    "10.21.0.40/16",  # k3s-wk-gpu3 (cit-vm-40)
    "10.21.0.41/16",  # k3s-wk-gpu4 (cit-vm-41)
  ]
}

variable "maintenance_mac" {
  description = "MAC address for maintenance VM"
  type        = string
  default     = ""  # Set in terraform.tfvars if maintenance VM is needed
}

variable "maintenance_ip" {
  description = "Static IP address for maintenance VM"
  type        = string
  default     = ""  # Set in terraform.tfvars if maintenance VM is needed
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

variable "vm_password" {
  description = "Password for the default user (hashed)"
  type        = string
  sensitive   = true
}

variable "gpu_mappings" {
  description = "List of GPU resource mapping IDs from Proxmox (e.g., '83', '88', etc.)"
  type        = list(string)
  default = [
    "83",   # wk-gpu1 GPU 1
    "88",   # wk-gpu1 GPU 2
    "35",   # wk-gpu2 GPU 1
    "40",   # wk-gpu2 GPU 2
    "185",  # wk-gpu3 GPU 1
    "190",  # wk-gpu3 GPU 2
    "130",  # wk-gpu4 GPU 1
    "135",  # wk-gpu4 GPU 2
  ]
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
