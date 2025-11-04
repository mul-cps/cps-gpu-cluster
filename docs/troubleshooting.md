# Troubleshooting Guide

Common issues and solutions for the GPU cluster setup.

## Table of Contents

- [Terraform Issues](#terraform-issues)
- [Ansible Issues](#ansible-issues)
- [K3s Issues](#k3s-issues)
- [GPU Issues](#gpu-issues)
- [Storage Issues](#storage-issues)
- [Fleet/GitOps Issues](#fleetgitops-issues)
- [JupyterHub Issues](#jupyterhub-issues)

---

## Terraform Issues

### Proxmox API connection failed

**Symptom**: `Error: error creating Proxmox client: error reading API token`

**Solution**:
```bash
# Verify API token
pveum user token list terraform@pam

# Recreate if needed
pveum user token add terraform@pam terraform-token --privsep=0

# Update proxmox.tfvars with new token
```

### VM creation fails with GPU passthrough

**Symptom**: `Error: unable to create VM: invalid PCI device`

**Solutions**:

1. Verify GPU is bound to vfio-pci:
```bash
lspci -nnk | grep -A 3 NVIDIA
```

2. Check IOMMU groups:
```bash
find /sys/kernel/iommu_groups/ -type l | grep -i nvidia
```

3. Verify PCI address format in tfvars (must be `0000:XX:YY.Z`)

### Cloud-init timeout

**Symptom**: VMs created but no IP assigned

**Solution**:
```bash
# Check cloud-init status in VM
sudo cloud-init status

# View cloud-init logs
sudo cat /var/log/cloud-init.log

# Verify network bridge in Proxmox
pvesh get /nodes/<node>/network
```

---

## Ansible Issues

### SSH connection failed

**Symptom**: `Failed to connect to the host via ssh`

**Solutions**:

1. Verify VMs are running:
```bash
pvesh get /nodes/<node>/qemu --output-format=json
```

2. Check SSH key:
```bash
ssh -i ~/.ssh/id_rsa ubuntu@10.0.0.11
```

3. Update known_hosts:
```bash
ssh-keygen -R 10.0.0.11
```

### K3s installation hangs

**Symptom**: Ansible task "Install K3s" never completes

**Solutions**:

1. Check network connectivity:
```bash
ansible -i inventory.ini all -m ping
```

2. Verify firewall rules:
```bash
# On nodes
sudo ufw status
sudo ufw allow 6443/tcp
sudo ufw allow 10250/tcp
```

3. Check system resources:
```bash
free -h
df -h
```

### Helm installation fails

**Symptom**: `Error: failed to download "nvidia/gpu-operator"`

**Solutions**:

1. Manually add repo:
```bash
helm repo add nvidia https://nvidia.github.io/gpu-operator
helm repo update
```

2. Check connectivity:
```bash
curl -I https://nvidia.github.io/gpu-operator/index.yaml
```

---

## K3s Issues

### Nodes not joining cluster

**Symptom**: `kubectl get nodes` shows only control planes

**Solutions**:

1. Check K3s agent status:
```bash
sudo systemctl status k3s-agent
sudo journalctl -u k3s-agent -f
```

2. Verify K3s token:
```bash
# On control plane
sudo cat /var/lib/rancher/k3s/server/node-token

# On worker
sudo cat /etc/systemd/system/k3s-agent.service.env
```

3. Check network connectivity:
```bash
# From worker to control plane
nc -zv 10.0.0.11 6443
```

### Control plane not HA

**Symptom**: Only one control plane is leader

**Solutions**:

1. Check etcd status:
```bash
sudo k3s kubectl get endpoints -n kube-system kube-controller-manager
```

2. Verify cluster-init flag:
```bash
sudo systemctl cat k3s | grep cluster-init
```

3. Check etcd member list:
```bash
sudo k3s etcd-snapshot ls
```

### Pods stuck in ContainerCreating

**Symptom**: Pods never start, stuck in `ContainerCreating`

**Solutions**:

1. Check pod events:
```bash
kubectl describe pod <pod-name> -n <namespace>
```

2. Check CNI:
```bash
kubectl get pods -n kube-system -l k8s-app=flannel
```

3. Restart containerd:
```bash
sudo systemctl restart k3s
```

---

## GPU Issues

### GPUs not visible in VMs

**Symptom**: `lspci` shows no NVIDIA devices

**Solutions**:

1. Check Proxmox host:
```bash
lspci | grep -i nvidia
lspci -nnk | grep -A 3 vfio-pci
```

2. Verify VM configuration:
```bash
qm config <vmid> | grep hostpci
```

3. Check VM logs:
```bash
journalctl -u pve-cluster -f
```

### GPU Operator pods failing

**Symptom**: `kubectl get pods -n gpu-operator` shows CrashLoopBackOff

**Solutions**:

1. Check driver installation:
```bash
kubectl logs -n gpu-operator -l app=nvidia-driver-daemonset
```

2. Verify kernel headers:
```bash
# On GPU workers
dpkg -l | grep linux-headers
uname -r
```

3. Check device plugin:
```bash
kubectl logs -n gpu-operator -l app=nvidia-device-plugin-daemonset
```

### nvidia-smi not working

**Symptom**: `nvidia-smi: command not found` in pods

**Solutions**:

1. Check GPU operator installation:
```bash
kubectl get pods -n gpu-operator
```

2. Verify container runtime:
```bash
kubectl get runtimeclass
```

3. Check pod GPU requests:
```yaml
resources:
  limits:
    nvidia.com/gpu: 1
```

### No GPUs allocated to pods

**Symptom**: Pods scheduled but `nvidia-smi` shows "No devices found"

**Solutions**:

1. Check node capacity:
```bash
kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'
```

2. Verify device plugin:
```bash
kubectl get daemonset -n gpu-operator nvidia-device-plugin-daemonset
```

3. Check node labels:
```bash
kubectl get nodes --show-labels | grep accelerator
```

---

## Storage Issues

### NFS mount failed

**Symptom**: Pods can't mount NFS volumes

**Solutions**:

1. Test NFS from node:
```bash
showmount -e 10.0.0.30
sudo mount -t nfs 10.0.0.30:/export/k3s /mnt
```

2. Check NFS provisioner:
```bash
kubectl get pods -n nfs-provisioner
kubectl logs -n nfs-provisioner -l app=nfs-subdir-external-provisioner
```

3. Verify firewall:
```bash
# On NFS server
sudo ufw allow from 10.0.0.0/24 to any port nfs
```

### PVC stuck in Pending

**Symptom**: `kubectl get pvc` shows Pending status

**Solutions**:

1. Check PVC events:
```bash
kubectl describe pvc <pvc-name>
```

2. Verify StorageClass:
```bash
kubectl get sc
kubectl describe sc <storage-class>
```

3. Check provisioner logs:
```bash
kubectl logs -n kube-system -l app=local-path-provisioner
```

### Fast-scratch not working

**Symptom**: PVCs using fast-scratch SC fail

**Solutions**:

1. Verify NVMe mount on workers:
```bash
# On GPU workers
df -h | grep nvme
ls -la /mnt/nvme/scratch
```

2. Check StorageClass:
```bash
kubectl get sc fast-scratch -o yaml
```

3. Verify node selector:
```bash
kubectl get nodes -l scratch=nvme
```

---

## Fleet/GitOps Issues

### GitRepo not syncing

**Symptom**: Fleet shows old commit or not syncing

**Solutions**:

1. Check GitRepo status:
```bash
kubectl get gitrepo -n fleet-local cluster-maintenance -o yaml
```

2. Force sync:
```bash
kubectl annotate gitrepo cluster-maintenance -n fleet-local \
  force-sync="$(date +%s)" --overwrite
```

3. Check Fleet agent logs:
```bash
kubectl logs -n cattle-fleet-system -l app=fleet-agent
```

### Bundle stuck in NotReady

**Symptom**: `kubectl get bundles` shows NotReady

**Solutions**:

1. Check bundle status:
```bash
kubectl describe bundle <bundle-name> -n fleet-local
```

2. Check target cluster:
```bash
kubectl get clusters -n fleet-local
```

3. Verify bundle deployment:
```bash
kubectl get bundledeployments -A
```

### Helm release failed

**Symptom**: Fleet shows Helm release error

**Solutions**:

1. Check Helm releases:
```bash
helm list -A
```

2. View Helm history:
```bash
helm history <release-name> -n <namespace>
```

3. Manual rollback:
```bash
helm rollback <release-name> -n <namespace>
```

---

## JupyterHub Issues

### Hub pod not starting

**Symptom**: JupyterHub hub pod in CrashLoopBackOff

**Solutions**:

1. Check logs:
```bash
kubectl logs -n jupyterhub -l component=hub
```

2. Verify database:
```bash
kubectl get pvc -n jupyterhub
```

3. Check secrets:
```bash
kubectl get secret -n jupyterhub hub-secret -o yaml
```

### User pods not spawning

**Symptom**: Users can't start notebooks

**Solutions**:

1. Check JupyterHub logs:
```bash
kubectl logs -n jupyterhub -l component=hub --tail=100
```

2. Verify resources available:
```bash
kubectl top nodes
kubectl describe nodes
```

3. Check quotas:
```bash
kubectl get resourcequota -n jupyterhub
```

### GPUs not available in notebooks

**Symptom**: `nvidia-smi` fails in notebook

**Solutions**:

1. Verify profile configuration:
```bash
kubectl get configmap -n jupyterhub hub -o yaml | grep -A 20 profileList
```

2. Check pod GPU requests:
```bash
kubectl describe pod -n jupyterhub jupyter-<username>
```

3. Verify node has GPUs:
```bash
kubectl get nodes -o json | jq '.items[] | select(.metadata.labels.accelerator=="nvidia")'
```

### Persistent storage issues

**Symptom**: User notebooks lose data

**Solutions**:

1. Check PVCs:
```bash
kubectl get pvc -n jupyterhub
```

2. Verify storage class:
```bash
kubectl get sc nfs-client -o yaml
```

3. Check NFS mounts:
```bash
kubectl exec -n jupyterhub jupyter-<username> -- df -h
```

---

## General Debugging Commands

### Check cluster health

```bash
# Node status
kubectl get nodes -o wide

# All pods
kubectl get pods -A

# Events
kubectl get events -A --sort-by='.lastTimestamp'

# Logs from all containers
kubectl logs -n <namespace> <pod> --all-containers=true
```

### Resource usage

```bash
# Node resources
kubectl top nodes

# Pod resources
kubectl top pods -A

# Describe node for allocated resources
kubectl describe node <node-name>
```

### Network debugging

```bash
# DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup kubernetes.default

# Network connectivity
kubectl run -it --rm debug --image=nicolaka/netshoot --restart=Never -- bash

# Service endpoints
kubectl get endpoints -A
```

### Storage debugging

```bash
# PV/PVC status
kubectl get pv,pvc -A

# Storage class
kubectl get sc

# CSI drivers
kubectl get csidrivers
```

---

## Getting Help

If issues persist:

1. **Check logs systematically** from bottom of stack up
2. **Search GitHub issues** for similar problems
3. **Rancher Forums**: https://forums.rancher.com/
4. **K3s Issues**: https://github.com/k3s-io/k3s/issues
5. **NVIDIA GPU Operator**: https://github.com/NVIDIA/gpu-operator/issues

### Collecting Debug Info

```bash
# K3s check
sudo k3s check-config

# System info
kubectl cluster-info dump > cluster-dump.txt

# GPU operator info
kubectl logs -n gpu-operator --all-containers=true --tail=-1 > gpu-operator.log

# Fleet info
kubectl get gitrepo,bundles,bundledeployments -A -o yaml > fleet-debug.yaml
```
