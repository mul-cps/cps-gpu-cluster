# Quick Reference

Essential commands for managing the GPU cluster.

## Initial Deployment

```bash
# 1. Initialize and deploy infrastructure
cd bootstrap-cluster/terraform
tofu init
tofu validate
tofu plan -var-file=secrets.tfvars
tofu apply -var-file=secrets.tfvars

# 2. Wait for VMs and SSH setup (15-20 minutes)

# 3. Verify SSH connectivity
ssh ubuntu@10.21.0.42  # maintenance VM
ssh ubuntu@10.21.0.35  # test cluster node access

# 4. Deploy K3s cluster
cd ../ansible
ansible all -i inventory.ini -m ping
ansible-playbook -i inventory.ini site.yml

# 5. Get kubeconfig
scp ubuntu@10.21.0.42:~/.kube/config ~/.kube/config-gpu-cluster
export KUBECONFIG=~/.kube/config-gpu-cluster

# 6. Verify cluster
kubectl get nodes
kubectl get pods -A
```

## VM Management

```bash
# List all VMs
ssh root@cit-gpu-01.unileoben.ac.at 'qm list'

# Check specific VM status
ssh root@cit-gpu-01.unileoben.ac.at 'qm status <vmid>'

# Start/stop/restart VM
ssh root@cit-gpu-01.unileoben.ac.at 'qm start <vmid>'
ssh root@cit-gpu-01.unileoben.ac.at 'qm stop <vmid>'
ssh root@cit-gpu-01.unileoben.ac.at 'qm reboot <vmid>'

# Check guest agent
ssh root@cit-gpu-01.unileoben.ac.at 'qm guest cmd <vmid> ping'

# Execute command in VM
ssh root@cit-gpu-01.unileoben.ac.at 'qm guest exec <vmid> -- <command>'

# VM IDs quick reference:
# 106-108: Control planes (cit-vm-35, 36, 37)
# 102-105: Workers (cit-vm-38, 43, 40, 41)
# 109: Maintenance (cit-vm-42)
```

## Kubernetes Operations

```bash
# Check cluster health
kubectl get nodes
kubectl get pods -A
kubectl get componentstatuses

# Check GPU resources
kubectl describe nodes | grep -A 5 "Capacity:"
kubectl describe nodes | grep nvidia.com/gpu

# List GPU nodes
kubectl get nodes -l nvidia.com/gpu.present=true

# View GPU allocation
kubectl describe nodes | grep -A 10 "Allocated resources:"

# Check GPU operator
kubectl get pods -n gpu-operator
kubectl logs -n gpu-operator <pod-name>

# Test GPU workload
kubectl run cuda-test --image=nvidia/cuda:12.2.0-base-ubuntu22.04 \
  --restart=OnFailure --rm -it -- nvidia-smi

# Check storage
kubectl get sc
kubectl get pv
kubectl get pvc -A
```

## SSH & Connectivity

```bash
# From local machine to maintenance VM
ssh ubuntu@10.21.0.42

# From maintenance VM to cluster nodes
ssh ubuntu@10.21.0.35  # control plane 1
ssh ubuntu@10.21.0.36  # control plane 2
ssh ubuntu@10.21.0.37  # control plane 3
ssh ubuntu@10.21.0.38  # worker 1
ssh ubuntu@10.21.0.43  # worker 2
ssh ubuntu@10.21.0.40  # worker 3
ssh ubuntu@10.21.0.41  # worker 4

# Check SSH key on maintenance VM
ssh ubuntu@10.21.0.42 'cat ~/.ssh/id_ed25519.pub'

# Verify authorized_keys on cluster node
ssh ubuntu@10.21.0.35 'cat ~/.ssh/authorized_keys'
```

## Ansible Operations

```bash
cd bootstrap-cluster/ansible

# Test connectivity
ansible all -i inventory.ini -m ping

# Run specific playbook
ansible-playbook -i inventory.ini playbooks/01-prerequisites.yml
ansible-playbook -i inventory.ini playbooks/02-k3s-cluster.yml
ansible-playbook -i inventory.ini playbooks/03-storage.yml
ansible-playbook -i inventory.ini playbooks/04-gpu-operator.yml

# Run on specific hosts
ansible-playbook -i inventory.ini playbooks/site.yml --limit control_plane
ansible-playbook -i inventory.ini playbooks/site.yml --limit workers

# Run with verbosity
ansible-playbook -i inventory.ini playbooks/site.yml -vvv

# Check Ansible facts
ansible all -i inventory.ini -m setup | less
```

## Terraform Operations

```bash
cd bootstrap-cluster/terraform

# Show current state
tofu show

# Show specific resource
tofu state list
tofu state show proxmox_vm_qemu.control_plane[0]

# Refresh state
tofu refresh -var-file=secrets.tfvars

# Plan changes
tofu plan -var-file=secrets.tfvars

# Apply changes
tofu apply -var-file=secrets.tfvars

# Destroy specific resource
tofu destroy -target=proxmox_vm_qemu.worker[1] -var-file=secrets.tfvars

# Destroy all
tofu destroy -var-file=secrets.tfvars

# Validate configuration
tofu validate

# Format code
tofu fmt -recursive
```

## Troubleshooting

```bash
# Check QEMU guest agent on all VMs
for vmid in 106 107 108 102 103 104 105 109; do
  echo -n "VM $vmid: "
  ssh root@cit-gpu-01.unileoben.ac.at "qm guest cmd $vmid ping" && echo "✓" || echo "✗"
done

# Check GPU passthrough
for ip in 10.21.0.38 10.21.0.43 10.21.0.40 10.21.0.41; do
  echo "=== Worker $ip ==="
  ssh ubuntu@$ip 'lspci | grep NVIDIA'
done

# Check cloud-init status
for ip in 10.21.0.{35..38} 10.21.0.{40..43}; do
  echo "=== Node $ip ==="
  ssh ubuntu@$ip 'cloud-init status' || echo "Failed"
done

# Check K3s service
for ip in 10.21.0.{35..38} 10.21.0.{40..43}; do
  echo "=== Node $ip ==="
  ssh ubuntu@$ip 'sudo systemctl status k3s || sudo systemctl status k3s-agent'
done

# View Terraform output
cd bootstrap-cluster/terraform
tofu output

# Check Proxmox cloud-init snippet
ssh root@cit-gpu-01.unileoben.ac.at 'cat /var/lib/vz/snippets/install-qemu-agent.yml'

# Check VM configuration
ssh root@cit-gpu-01.unileoben.ac.at 'qm config <vmid>'

# View VM console (for debugging)
# Access via Proxmox web UI: https://cit-gpu-01.unileoben.ac.at:8006
```

## Logs & Debugging

```bash
# Proxmox system logs
ssh root@cit-gpu-01.unileoben.ac.at 'journalctl -u pvedaemon -f'
ssh root@cit-gpu-01.unileoben.ac.at 'journalctl -u pveproxy -f'

# VM logs (from inside VM)
ssh ubuntu@<vm-ip> 'sudo journalctl -u cloud-init -f'
ssh ubuntu@<vm-ip> 'sudo journalctl -u qemu-guest-agent -f'
ssh ubuntu@<vm-ip> 'sudo journalctl -u k3s -f'
ssh ubuntu@<vm-ip> 'sudo journalctl -u k3s-agent -f'

# Cloud-init logs
ssh ubuntu@<vm-ip> 'sudo cat /var/log/cloud-init.log'
ssh ubuntu@<vm-ip> 'sudo cat /var/log/cloud-init-output.log'

# K3s logs
kubectl logs -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l app=local-path-provisioner

# GPU operator logs
kubectl logs -n gpu-operator -l app=nvidia-driver-daemonset
kubectl logs -n gpu-operator -l app=nvidia-container-toolkit-daemonset
kubectl logs -n gpu-operator -l app=nvidia-device-plugin-daemonset
```

## Maintenance Tasks

```bash
# Update K3s version (edit group_vars/all.yml first)
cd bootstrap-cluster/ansible
ansible-playbook -i inventory.ini playbooks/02-k3s-cluster.yml

# Drain node for maintenance
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# Uncordon node
kubectl uncordon <node-name>

# Backup etcd
kubectl get nodes  # verify control plane
ssh ubuntu@10.21.0.35 'sudo k3s etcd-snapshot save'

# Backup terraform state
cd bootstrap-cluster/terraform
cp terraform.tfstate terraform.tfstate.backup.$(date +%Y%m%d)

# Export all K8s resources
kubectl get all -A -o yaml > cluster-backup-$(date +%Y%m%d).yaml

# Force recreate VM (example for worker 2)
cd bootstrap-cluster/terraform
tofu taint proxmox_vm_qemu.worker[1]
tofu apply -var-file=secrets.tfvars
```

## Quick Status Check

```bash
# One-liner cluster status
kubectl get nodes && echo "---" && kubectl get pods -A | grep -v "Running\|Completed"

# GPU availability
kubectl get nodes -o json | jq '.items[] | {name:.metadata.name, gpus:.status.capacity["nvidia.com/gpu"]}'

# Resource usage
kubectl top nodes
kubectl top pods -A --sort-by=memory

# Check all services
kubectl get svc -A

# Fleet status (if using GitOps)
kubectl get fleet -A
kubectl get bundledeployments -A
```

## Network Info

| Component | IP/Range | Notes |
|-----------|----------|-------|
| Control Planes | 10.21.0.35-37 | 3 nodes, HA |
| GPU Workers | 10.21.0.38, 43, 40, 41 | 4 nodes, 2 GPUs each |
| Maintenance VM | 10.21.0.42 | Ansible/management |
| Gateway | 10.21.0.1 | VLAN 633 gateway |
| Subnet | 10.21.0.0/16 | Class B private |
| Proxmox | cit-gpu-01.unileoben.ac.at | Host |

## Resource Limits

| Resource | Total | Per Worker |
|----------|-------|------------|
| Worker VMs | 4 | - |
| GPUs (A100) | 8 | 2 |
| CPU Cores | ~48 | 12 |
| RAM | ~512 GB | 128 GB |
| Storage | 2 TB NVMe | 500 GB |

## Important Files

```
bootstrap-cluster/terraform/
  ├── terraform.tfvars          # VM configuration
  ├── secrets.tfvars            # API tokens (not in git!)
  ├── main.tf                   # VM definitions
  ├── ssh-setup.tf              # SSH automation
  └── cloud-init-qemu-agent.yml # Guest agent install

bootstrap-cluster/ansible/
  ├── inventory.ini             # Generated by Terraform
  ├── group_vars/all.yml        # K3s configuration
  └── playbooks/                # Deployment playbooks

cluster-maintenance/clusters/homelab/
  ├── jupyterhub/              # JupyterHub config
  ├── gpu-operator/            # GPU operator config
  └── fleet.yaml               # GitOps config
```

## Emergency Contacts

- **Proxmox Admin**: root@cit-gpu-01.unileoben.ac.at
- **Network (VLAN 633)**: MUL network team
- **GPU Support**: NVIDIA documentation / forums

## Useful Links

- Proxmox UI: https://cit-gpu-01.unileoben.ac.at:8006
- K3s Docs: https://docs.k3s.io
- NVIDIA GPU Operator: https://docs.nvidia.com/datacenter/cloud-native/gpu-operator
- Telmate Provider: https://registry.terraform.io/providers/Telmate/proxmox

---

**Tip**: Bookmark this page for quick access to common commands!
