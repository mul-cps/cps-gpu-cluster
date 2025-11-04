output "control_plane_ips" {
  description = "IP addresses of control plane nodes"
  value       = [for vm in proxmox_vm_qemu.k3s_control_plane : vm.default_ipv4_address]
}

output "gpu_worker_ips" {
  description = "IP addresses of GPU worker nodes"
  value       = [for vm in proxmox_vm_qemu.k3s_gpu_worker : vm.default_ipv4_address]
}

output "control_plane_names" {
  description = "Names of control plane VMs"
  value       = [for vm in proxmox_vm_qemu.k3s_control_plane : vm.name]
}

output "gpu_worker_names" {
  description = "Names of GPU worker VMs"
  value       = [for vm in proxmox_vm_qemu.k3s_gpu_worker : vm.name]
}

output "ansible_inventory_path" {
  description = "Path to generated Ansible inventory file"
  value       = local_file.ansible_inventory.filename
}
