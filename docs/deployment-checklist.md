# Deployment Checklist

Use this checklist to deploy the GPU cluster from scratch.

## Phase 1: Pre-Deployment

### ✅ Proxmox Host Preparation

- [ ] Proxmox VE 8.x installed on `cit-gpu-01.unileoben.ac.at`
- [ ] IOMMU enabled in BIOS
- [ ] VFIO modules loaded for GPU passthrough
- [ ] Network configured (VLAN 633 accessible)
- [ ] NVMe ZFS storage pool created (`NvmeZFSstorage`)
- [ ] Ubuntu 24.04 Cloud-Init template created (VMID: 9000)
  - See: [bootstrap-cluster/terraform/TEMPLATE_CREATION.md](bootstrap-cluster/terraform/TEMPLATE_CREATION.md)
- [ ] Proxmox API token created for Terraform
  - User: `terraform-prov@pve`
  - Token name: `mytoken`
  - Privilege: Administrator
- [ ] SSH access to Proxmox host working
  ```bash
  ssh root@cit-gpu-01.unileoben.ac.at
  ```

### ✅ Local Workstation Setup

- [ ] OpenTofu installed (`tofu --version`)
- [ ] Ansible installed (`ansible --version` >= 2.15)
- [ ] kubectl installed
- [ ] helm installed
- [ ] SSH key pair generated
  ```bash
  # Check if key exists
  ls -la ~/.ssh/id_ed25519*
  
  # Generate if needed
  ssh-keygen -t ed25519 -C "your-email@example.com"
  ```

### ✅ Repository Preparation

- [ ] Clone repository
  ```bash
  git clone <repo-url>
  cd cps-gpu-cluster
  ```

- [ ] Review configuration files
  - [ ] `bootstrap-cluster/terraform/terraform.tfvars`
  - [ ] `bootstrap-cluster/ansible/group_vars/all.yml`
  - [ ] `bootstrap-cluster/ansible/inventory.ini`

## Phase 2: Infrastructure Provisioning

### ✅ Terraform Configuration

- [ ] Navigate to Terraform directory
  ```bash
  cd bootstrap-cluster/terraform
  ```

- [ ] Review `terraform.tfvars`
  - [ ] Verify MAC addresses (from MUL allocation)
  - [ ] Verify IP addresses (10.21.0.35-43)
  - [ ] Verify VM names match convention
  - [ ] Check GPU PCIe IDs for each worker
  - [ ] Verify SSH public key is correct

- [ ] Create Proxmox API credentials file
  ```bash
  cat > secrets.tfvars <<EOF
  proxmox_api_token_secret = "<your-actual-token-secret>"
  EOF
  ```

- [ ] Initialize Terraform
  ```bash
  tofu init
  ```
  Expected: ✓ Providers installed (proxmox, null, external)

- [ ] Validate configuration
  ```bash
  tofu validate
  ```
  Expected: "The configuration is valid"

- [ ] Review execution plan
  ```bash
  tofu plan -var-file=secrets.tfvars
  ```
  Expected: 
  - 1 snippet upload
  - 8 VMs to create
  - SSH key setup resources

### ✅ VM Deployment

- [ ] Deploy infrastructure
  ```bash
  tofu apply -var-file=secrets.tfvars
  ```
  
  Monitor for:
  - [ ] Cloud-init snippet uploaded to Proxmox
  - [ ] 3 control plane VMs created (106, 107, 108)
  - [ ] 4 worker VMs created (102, 103, 104, 105)
  - [ ] 1 maintenance VM created (109)
  - [ ] QEMU guest agents become active (may take 5-15 minutes)
  - [ ] SSH key generated on maintenance VM
  - [ ] SSH key distributed to all cluster VMs
  - [ ] known_hosts configured

- [ ] Verify VMs are running
  ```bash
  ssh root@cit-gpu-01.unileoben.ac.at 'qm list | grep -E "10[2-9]"'
  ```
  Expected: All 8 VMs showing "running" status

### ✅ Post-Deployment Verification

- [ ] Check QEMU guest agent on all VMs
  ```bash
  # Test each VM
  for vmid in 106 107 108 102 103 104 105 109; do
    echo -n "VM $vmid: "
    ssh root@cit-gpu-01.unileoben.ac.at "qm guest cmd $vmid ping" && echo "✓" || echo "✗"
  done
  ```

- [ ] Test SSH from maintenance VM to cluster nodes
  ```bash
  # SSH to maintenance VM
  ssh ubuntu@10.21.0.42
  
  # From maintenance VM, test SSH to control plane
  ssh ubuntu@10.21.0.35 'hostname'
  ssh ubuntu@10.21.0.36 'hostname'
  ssh ubuntu@10.21.0.37 'hostname'
  
  # Test SSH to workers
  ssh ubuntu@10.21.0.38 'hostname'
  ssh ubuntu@10.21.0.43 'hostname'
  ssh ubuntu@10.21.0.40 'hostname'
  ssh ubuntu@10.21.0.41 'hostname'
  ```
  Expected: All should connect without password

- [ ] Verify GPU passthrough
  ```bash
  # Check each worker
  for ip in 10.21.0.38 10.21.0.43 10.21.0.40 10.21.0.41; do
    echo "=== Worker $ip ==="
    ssh ubuntu@$ip 'lspci | grep NVIDIA'
  done
  ```
  Expected: Each worker shows 2 NVIDIA devices

## Phase 3: Kubernetes Deployment

### ✅ Ansible Configuration

- [ ] Return to local machine
  ```bash
  cd ../../ansible
  ```

- [ ] Verify inventory was generated
  ```bash
  cat inventory.ini
  ```
  Expected: 7 hosts (3 control plane, 4 workers)

- [ ] Test Ansible connectivity
  ```bash
  ansible all -i inventory.ini -m ping
  ```
  Expected: All hosts respond "pong"

### ✅ K3s Installation

- [ ] Review playbook sequence
  - [ ] 01-prerequisites.yml (Docker, dependencies)
  - [ ] 02-k3s-cluster.yml (K3s HA cluster)
  - [ ] 03-storage.yml (NFS provisioner)
  - [ ] 04-gpu-operator.yml (NVIDIA drivers/operator)

- [ ] Run prerequisites playbook
  ```bash
  ansible-playbook -i inventory.ini playbooks/01-prerequisites.yml
  ```
  Expected: System packages installed, Docker configured

- [ ] Install K3s cluster
  ```bash
  ansible-playbook -i inventory.ini playbooks/02-k3s-cluster.yml
  ```
  Expected: 
  - First control plane initializes cluster
  - Remaining control planes join
  - Workers join cluster

- [ ] Copy kubeconfig
  ```bash
  # From maintenance VM or first control plane
  scp ubuntu@10.21.0.42:~/.kube/config ~/.kube/config-gpu-cluster
  
  # Set as active context
  export KUBECONFIG=~/.kube/config-gpu-cluster
  ```

- [ ] Verify cluster
  ```bash
  kubectl get nodes
  ```
  Expected: 7 nodes, all "Ready"

### ✅ Storage Configuration

- [ ] Configure NFS server (if not already done)
  - [ ] NFS export created
  - [ ] Permissions set correctly
  - [ ] Test mount from worker node

- [ ] Deploy storage playbook
  ```bash
  ansible-playbook -i inventory.ini playbooks/03-storage.yml
  ```
  Expected: 
  - NFS provisioner deployed
  - StorageClasses created

- [ ] Verify storage
  ```bash
  kubectl get sc
  kubectl get pods -n nfs-provisioner
  ```
  Expected: 
  - nfs-client storageclass
  - local-path storageclass (default)
  - NFS provisioner running

### ✅ GPU Operator Installation

- [ ] Deploy GPU operator
  ```bash
  ansible-playbook -i inventory.ini playbooks/04-gpu-operator.yml
  ```
  Expected: NVIDIA GPU Operator deployed via Helm

- [ ] Wait for GPU operator (can take 10-20 minutes)
  ```bash
  watch kubectl get pods -n gpu-operator
  ```
  Wait until all pods are "Running"

- [ ] Verify GPU nodes
  ```bash
  kubectl get nodes -l nvidia.com/gpu.present=true
  ```
  Expected: 4 worker nodes

- [ ] Check GPU capacity
  ```bash
  kubectl describe nodes | grep -A 5 "Capacity:"
  ```
  Expected: Each worker shows `nvidia.com/gpu: 2`

- [ ] Test GPU allocation
  ```bash
  kubectl apply -f - <<EOF
  apiVersion: v1
  kind: Pod
  metadata:
    name: cuda-test
  spec:
    restartPolicy: OnFailure
    containers:
    - name: cuda
      image: nvidia/cuda:12.2.0-base-ubuntu22.04
      command: ["nvidia-smi"]
      resources:
        limits:
          nvidia.com/gpu: 1
  EOF
  
  # Wait for completion
  kubectl wait --for=condition=Ready pod/cuda-test --timeout=300s
  
  # Check output
  kubectl logs cuda-test
  ```
  Expected: nvidia-smi output showing GPU details

- [ ] Clean up test pod
  ```bash
  kubectl delete pod cuda-test
  ```

## Phase 4: GitOps Setup

### ✅ Rancher Installation (Optional)

- [ ] Install Rancher via Helm
  ```bash
  helm repo add rancher-stable https://releases.rancher.com/server-charts/stable
  helm repo update
  
  kubectl create namespace cattle-system
  
  helm install rancher rancher-stable/rancher \
    --namespace cattle-system \
    --set hostname=rancher.your-domain.com \
    --set replicas=1 \
    --set bootstrapPassword=admin
  ```

- [ ] Access Rancher UI
  - [ ] Port-forward or configure ingress
  - [ ] Complete initial setup
  - [ ] Import cluster if needed

### ✅ Fleet GitOps

- [ ] Review Fleet manifests
  ```bash
  cd ../../cluster-maintenance/clusters/homelab
  ls -la
  ```
  Expected directories:
  - gpu-operator/
  - jupyterhub/
  - storageclasses/
  - tests/

- [ ] Install Fleet (if not already via Rancher)
  ```bash
  helm repo add fleet https://rancher.github.io/fleet-helm-charts/
  helm install fleet-crd fleet/fleet-crd -n cattle-fleet-system --create-namespace
  helm install fleet fleet/fleet -n cattle-fleet-system
  ```

- [ ] Apply Fleet configuration
  ```bash
  kubectl apply -f fleet.yaml
  ```

- [ ] Monitor Fleet deployments
  ```bash
  kubectl get fleet -A
  kubectl get bundledeployments -A
  ```

## Phase 5: Application Deployment

### ✅ JupyterHub Installation

- [ ] Review JupyterHub configuration
  ```bash
  cat cluster-maintenance/clusters/homelab/jupyterhub/values.yaml
  ```

- [ ] Deploy via Fleet or Helm
  ```bash
  # If using direct Helm:
  helm repo add jupyterhub https://hub.jupyter.org/helm-chart/
  helm repo update
  
  kubectl create namespace jupyterhub
  
  helm install jupyterhub jupyterhub/jupyterhub \
    --namespace jupyterhub \
    --values cluster-maintenance/clusters/homelab/jupyterhub/values.yaml
  ```

- [ ] Wait for JupyterHub pods
  ```bash
  kubectl get pods -n jupyterhub -w
  ```

- [ ] Access JupyterHub
  - [ ] Configure ingress or port-forward
  - [ ] Test login
  - [ ] Create test notebook
  - [ ] Request GPU in notebook
  - [ ] Run `!nvidia-smi` in notebook

### ✅ GPU Testing

- [ ] Apply CUDA test manifests
  ```bash
  kubectl apply -f cluster-maintenance/clusters/homelab/tests/cuda-tests.yaml
  ```

- [ ] Check test results
  ```bash
  kubectl get pods -n gpu-tests
  kubectl logs -n gpu-tests <test-pod-name>
  ```

- [ ] Verify GPU scheduling across nodes
  ```bash
  kubectl get pods -n gpu-tests -o wide
  ```
  Expected: Pods distributed across worker nodes

## Phase 6: Final Validation

### ✅ System Health Check

- [ ] All nodes ready
  ```bash
  kubectl get nodes
  ```

- [ ] All system pods running
  ```bash
  kubectl get pods -A | grep -v "Running\|Completed"
  ```
  Expected: Empty (no pending/failed pods)

- [ ] GPU resources available
  ```bash
  kubectl describe nodes | grep "nvidia.com/gpu"
  ```
  Expected: Total 8 GPUs (2 per worker × 4 workers)

- [ ] Storage working
  ```bash
  kubectl get pvc -A
  ```
  Expected: PVCs bound

- [ ] DNS working
  ```bash
  kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup kubernetes.default
  ```
  Expected: Resolves successfully

### ✅ Documentation

- [ ] Update README with actual IPs/hostnames
- [ ] Document any deviations from standard config
- [ ] Note GPU PCIe IDs used
- [ ] Record API tokens and credentials (securely!)
- [ ] Create runbook for common operations

## Troubleshooting Reference

If issues occur, see:
- [docs/troubleshooting.md](docs/troubleshooting.md)
- [docs/qemu-guest-agent-setup.md](docs/qemu-guest-agent-setup.md)
- [docs/terraform-ssh-setup.md](docs/terraform-ssh-setup.md)

## Rollback Procedures

### Destroy Everything
```bash
cd bootstrap-cluster/terraform
tofu destroy -var-file=secrets.tfvars
```

### Preserve Data, Destroy VMs
```bash
# Backup any important data first!
# Then destroy VMs
tofu destroy -var-file=secrets.tfvars -target=proxmox_vm_qemu.control_plane
tofu destroy -var-file=secrets.tfvars -target=proxmox_vm_qemu.worker
tofu destroy -var-file=secrets.tfvars -target=proxmox_vm_qemu.maintenance
```

### Reset K3s Without Destroying VMs
```bash
# On each node:
/usr/local/bin/k3s-uninstall.sh  # workers
/usr/local/bin/k3s-agent-uninstall.sh  # control planes

# Then re-run Ansible playbook
ansible-playbook -i inventory.ini playbooks/02-k3s-cluster.yml
```

## Maintenance Tasks

### Update K3s Version
```bash
# Update version in ansible/group_vars/all.yml
# Then re-run playbook
ansible-playbook -i inventory.ini playbooks/02-k3s-cluster.yml
```

### Add Worker Node
```bash
# 1. Update terraform.tfvars (add worker)
# 2. Apply Terraform
tofu apply -var-file=secrets.tfvars

# 3. Update Ansible inventory
# 4. Run K3s playbook for new node
ansible-playbook -i inventory.ini playbooks/02-k3s-cluster.yml --limit new-worker

# 5. Install GPU operator
ansible-playbook -i inventory.ini playbooks/04-gpu-operator.yml --limit new-worker
```

### Backup Cluster
```bash
# Backup etcd
kubectl exec -n kube-system etcd-xxx -- etcdctl snapshot save /tmp/snapshot.db

# Backup manifests
kubectl get all -A -o yaml > cluster-backup.yaml

# Backup Terraform state
cp terraform.tfstate terraform.tfstate.backup.$(date +%Y%m%d)
```

---

## Success Criteria

Deployment is complete when:

✅ All VMs running and accessible  
✅ All K3s nodes in "Ready" state  
✅ All GPU devices visible in Kubernetes (`nvidia.com/gpu: 8` total)  
✅ Storage provisioners operational  
✅ JupyterHub accessible and can spawn GPU notebooks  
✅ Test CUDA workload completes successfully  
✅ GitOps pipeline (Fleet) syncing manifests  
✅ Monitoring/logging operational (if configured)  

**Estimated Total Time**: 2-4 hours (depending on download speeds and troubleshooting)

---

**Note**: Save this checklist and tick off items as you complete them. If you encounter issues, refer to the troubleshooting docs before proceeding.
