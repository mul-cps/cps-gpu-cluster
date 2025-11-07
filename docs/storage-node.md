# Storage Node Setup

This document describes the temporary NFS storage node for the K3s cluster until a proper storage server is available.

## Overview

The storage node (`k3s-storage`) is a VM that provides NFS-based shared storage to the Kubernetes cluster. It includes:

- **VM Name**: k3s-storage
- **IP Address**: 10.21.0.44/16 (requires MUL approval)
- **MAC Address**: 00:16:3e:63:79:2f (requires MUL approval)
- **Resources**: 4 CPU cores, 8GB RAM
- **Storage**: 
  - 100GB OS disk (scsi0)
  - 2TB data disk (scsi1) for NFS exports

## Prerequisites

Before deploying the storage node, you need to:

1. **Request network allocation from MUL for VLAN 633:**
   - Request IP: 10.21.0.44
   - Request MAC: 00:16:3e:63:79:2f
   - Purpose: K3s NFS storage node

2. **Update configuration** (if different from above):
   ```bash
   vim bootstrap-cluster/terraform/terraform.tfvars
   # Edit storage_mac and storage_ip if needed
   ```

## Deployment Steps

### 1. Deploy Storage VM with Terraform

```bash
cd bootstrap-cluster/terraform

# Plan the changes
tofu plan

# Apply to create the storage VM
tofu apply
```

This will:
- Create the k3s-storage VM (VM ID will be assigned by Proxmox)
- Configure networking with the specified IP/MAC
- Add 2TB data disk for NFS storage
- Set up SSH access from maintenance VM
- Update Ansible inventory

### 2. Setup NFS Server

Run the Ansible playbook to configure NFS on the storage node:

```bash
cd bootstrap-cluster/ansible

# Setup NFS server on storage node
ansible-playbook -i inventory.ini playbooks/02a-setup-storage-node.yml
```

This playbook will:
- Install NFS server packages
- Format and mount the 2TB data disk (/dev/sdb) to /srv/nfs
- Create NFS export at /srv/nfs/k3s-storage
- Configure NFS exports for the cluster subnet (10.21.0.0/16)
- Start and enable NFS server

### 3. Deploy NFS Provisioner to Kubernetes

After the storage node is configured, deploy the NFS provisioner:

```bash
# This will automatically use the storage node IP
ansible-playbook -i inventory.ini playbooks/03-storage.yml
```

This will:
- Install NFS Subdir External Provisioner via Helm
- Configure it to use the storage node as NFS server
- Create StorageClasses (nfs-client as default, fast-scratch for local NVMe)
- Verify storage is working

## Storage Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   K3s Cluster                           │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  CP1     │  │  CP2     │  │  CP3     │             │
│  └──────────┘  └──────────┘  └──────────┘             │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  GPU1    │  │  GPU2    │  │  GPU3    │  │  GPU4  │ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
│       │             │             │             │       │
│       └─────────────┴─────────────┴─────────────┘       │
│                         │                               │
│                         ↓ NFS mounts                    │
└─────────────────────────┼───────────────────────────────┘
                          │
                          ↓
                ┌─────────────────────┐
                │  k3s-storage        │
                │  (10.21.0.44)       │
                │                     │
                │  /srv/nfs/k3s-storage │
                │  └─> /dev/sdb (2TB) │
                └─────────────────────┘
```

## Configuration Details

### NFS Export Configuration

- **Export Path**: `/srv/nfs/k3s-storage`
- **Allowed Network**: `10.21.0.0/16` (entire cluster subnet)
- **Options**: `rw,sync,no_subtree_check,no_root_squash,insecure`
- **Permissions**: 777 (nobody:nogroup)

### Storage Classes

After deployment, two StorageClasses will be available:

1. **nfs-client** (default)
   - Backed by NFS storage node
   - Access mode: ReadWriteMany (RWX)
   - Use for: Shared data, multi-pod access
   - Reclaim policy: Retain

2. **fast-scratch**
   - Backed by local NVMe on worker nodes
   - Access mode: ReadWriteOnce (RWO)
   - Use for: High-performance temporary storage
   - Reclaim policy: Delete

## Verification

### Check Storage Node

```bash
# SSH to storage node
ssh ubuntu@10.21.0.44

# Verify NFS exports
showmount -e localhost

# Check disk usage
df -h /srv/nfs

# Check NFS server status
systemctl status nfs-kernel-server
```

### Check from Kubernetes

```bash
# SSH to first control plane
ssh ubuntu@10.21.0.35

# Check StorageClasses
kubectl get sc

# Check NFS provisioner
kubectl get pods -n nfs-provisioner

# Test with a PVC
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-nfs
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: nfs-client
  resources:
    requests:
      storage: 1Gi
EOF

# Check PVC status
kubectl get pvc test-nfs

# Clean up test
kubectl delete pvc test-nfs
```

## Troubleshooting

### NFS Mount Issues

If pods can't mount NFS volumes:

```bash
# On storage node - check NFS exports
exportfs -v

# On worker nodes - test NFS mount manually
showmount -e 10.21.0.44
sudo mount -t nfs 10.21.0.44:/srv/nfs/k3s-storage /mnt
```

### Disk Full

If the storage disk fills up:

```bash
# On storage node
df -h /srv/nfs

# Find largest directories
sudo du -sh /srv/nfs/k3s-storage/*

# In Kubernetes - check PV usage
kubectl get pv
```

### NFS Server Not Starting

```bash
# On storage node
sudo journalctl -xeu nfs-kernel-server

# Check if disk is mounted
mount | grep /srv/nfs

# Restart NFS server
sudo systemctl restart nfs-kernel-server
```

## Migration to Production Storage

When a proper storage server becomes available:

1. **Deploy new storage server** with production-grade features (RAID, backups, etc.)

2. **Update Ansible variables**:
   ```yaml
   # In group_vars/all.yml
   nfs_server: "production-storage-server.example.com"
   nfs_path: "/export/k3s-production"
   ```

3. **Migrate data**:
   ```bash
   # On storage node
   rsync -avP /srv/nfs/k3s-storage/ \
     production-storage:/export/k3s-production/
   ```

4. **Redeploy NFS provisioner**:
   ```bash
   ansible-playbook -i inventory.ini playbooks/03-storage.yml
   ```

5. **Decommission k3s-storage VM**:
   ```bash
   cd bootstrap-cluster/terraform
   # Comment out or set storage_ip = "" in terraform.tfvars
   tofu apply
   ```

## Limitations

This storage node is intended as a **temporary solution**:

- ❌ No redundancy (single disk)
- ❌ No backup system
- ❌ No high availability
- ❌ Limited performance compared to dedicated storage
- ✅ Sufficient for development/testing workloads

For production workloads, use a proper storage solution like:
- Ceph RBD
- NetApp/Dell EMC storage arrays
- Longhorn (distributed storage)
- Cloud provider persistent volumes
