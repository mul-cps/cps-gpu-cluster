# Harvester Migration Guide

This guide covers migrating from K3s on Proxmox VMs to Harvester bare-metal when a second server becomes available.

## What is Harvester?

Harvester is a modern, open-source hyperconverged infrastructure (HCI) solution built on Kubernetes. It provides:

- Built-in VM management via KubeVirt
- Integrated Longhorn distributed storage
- Native Rancher integration
- Kubernetes-based architecture
- GPU support (beta)

## When to Migrate

Consider migrating to Harvester when:

1. **Second bare-metal server available** - Harvester requires 3 nodes for HA
2. **Need distributed storage** - Longhorn provides replicated volumes
3. **Want simplified management** - Single pane of glass for VMs and containers
4. **Require better HA** - VM live migration, storage replication

## Prerequisites

- 2-3 physical servers (minimum)
- Harvester v1.3.0 or later (for GPU support)
- Same hardware specs per node (recommended)
- Dedicated network for cluster communication

## Migration Strategy

### Option A: Parallel Installation (Recommended)

1. Install Harvester on new hardware
2. Deploy applications via Fleet
3. Migrate workloads gradually
4. Decommission Proxmox cluster

### Option B: In-Place Migration (Advanced)

1. Backup all data and configurations
2. Install Harvester on existing hardware
3. Restore from backups
4. Redeploy applications

## Step 1: Install Harvester

### Download ISO

```bash
wget https://releases.rancher.com/harvester/v1.3.0/harvester-v1.3.0-amd64.iso
```

### Create Bootable USB

```bash
dd if=harvester-v1.3.0-amd64.iso of=/dev/sdX bs=4M status=progress
```

### Installation Process

1. Boot from ISO on first node
2. Select "Create a new Harvester cluster"
3. Configure:
   - Cluster token (generate secure token)
   - Management network (10.0.0.x/24)
   - VIP for management (e.g., 10.0.0.50)
   - Storage configuration

4. Complete installation
5. Access Harvester UI at `https://<VIP>:443`

### Add Additional Nodes

On second/third nodes:

1. Boot from same ISO
2. Select "Join an existing Harvester cluster"
3. Enter:
   - Cluster token from first node
   - Management VIP
4. Complete installation

## Step 2: Configure GPU Passthrough

Harvester supports GPU passthrough via PCI devices.

### Enable PCI Devices

1. Navigate to **Advanced** → **PCI Devices**
2. Enable GPUs for passthrough
3. Assign to specific nodes

### Create GPU-enabled VMs

In VM configuration:
```yaml
spec:
  domain:
    devices:
      gpus:
        - deviceName: nvidia.com/A100_PCIE_40GB
          name: gpu1
```

Or via Harvester UI:
1. Create VM
2. Add PCI Device
3. Select NVIDIA GPU

## Step 3: Import into Rancher

Harvester clusters can be imported into Rancher for unified management.

### Import Process

1. In Rancher, go to **Cluster Management**
2. Click **Import Existing**
3. Select **Harvester**
4. Enter Harvester cluster URL
5. Apply registration command in Harvester

### Benefits

- Single dashboard for K3s and Harvester clusters
- Unified Fleet deployments
- Centralized monitoring
- Multi-cluster application management

## Step 4: Restore Fleet Configurations

The same Fleet GitOps repository can target Harvester clusters.

### Update Fleet Targets

Edit `cluster-maintenance/clusters/homelab/fleet.yaml`:

```yaml
targetCustomizations:
- name: harvester-cluster
  clusterSelector:
    matchLabels:
      cluster.cattle.io/cluster-name: harvester-local
```

Fleet will automatically deploy applications to the new cluster.

## Step 5: Configure Longhorn Storage

Harvester includes Longhorn for distributed storage.

### Create StorageClass

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: longhorn-gpu
provisioner: driver.longhorn.io
parameters:
  numberOfReplicas: "2"
  staleReplicaTimeout: "30"
  fromBackup: ""
  fsType: "ext4"
reclaimPolicy: Delete
volumeBindingMode: Immediate
```

### Benefits over NFS

- Replication for HA
- Snapshots and backups
- Better performance for databases
- No single point of failure

## Step 6: Migrate GPU Workloads

### JupyterHub Migration

1. Backup user data from NFS
2. Update JupyterHub values for Longhorn storage:

```yaml
singleuser:
  storage:
    dynamic:
      storageClass: longhorn-gpu
```

3. Apply via Fleet
4. Restore user data
5. Test GPU access in notebooks

### GPU Operator

NVIDIA GPU Operator works on Harvester with minor adjustments:

```yaml
# values.yaml
operator:
  defaultRuntime: containerd
  
# Enable KubeVirt support
kubevirt:
  enabled: true
```

## Step 7: Implement HA Features

### VM Live Migration

Harvester supports live migration of VMs between nodes:

```bash
kubectl virt migrate <vm-name>
```

### Storage Replication

Configure Longhorn replicas:

```bash
kubectl -n longhorn-system edit settings.longhorn.io default-replica-count
```

Set to 2 or 3 for HA.

### Network Redundancy

Use bonded interfaces for cluster network:

1. Navigate to **Networks** in Harvester UI
2. Create VLAN network
3. Configure bonding (active-backup or LACP)

## Step 8: Testing

### Verify GPU Access

Deploy test pod:

```yaml
apiVersion: kubevirt.io/v1
kind: VirtualMachine
metadata:
  name: gpu-test-vm
spec:
  template:
    spec:
      domain:
        devices:
          gpus:
            - deviceName: nvidia.com/A100_PCIE_40GB
              name: gpu1
```

Inside VM:
```bash
nvidia-smi
```

### Test Storage Performance

```bash
kubectl apply -f https://raw.githubusercontent.com/yasker/kbench/main/deploy/fio.yaml
```

## Comparison: Proxmox vs Harvester

| Feature | Proxmox + K3s | Harvester |
|---------|---------------|-----------|
| Management | Separate UIs | Unified Kubernetes |
| Storage | NFS/local | Longhorn distributed |
| HA | Manual setup | Built-in |
| GPU Support | Mature | Beta (improving) |
| Backup | Manual/scripted | Integrated |
| Learning Curve | Lower | Higher |
| Community | Large | Growing |

## Rollback Plan

If migration fails:

1. Keep Proxmox cluster running during testing
2. Export VM configurations from Harvester
3. Document all changes
4. Test restore procedures
5. Have backup of all data

## Known Limitations

### GPU Support

- GPU passthrough on Harvester is beta
- Some features may not work
- Driver management less mature than bare-metal

### Workaround

Deploy GPU workloads on bare-metal K3s nodes managed by Rancher:

1. Keep GPU workers as standalone K3s nodes
2. Import into Rancher
3. Use Harvester for non-GPU workloads
4. Unified management via Rancher/Fleet

## Timeline

Recommended migration timeline:

1. **Week 1**: Install Harvester on new hardware
2. **Week 2**: Configure storage and networking
3. **Week 3**: Deploy non-GPU workloads
4. **Week 4**: Test GPU support
5. **Week 5**: Migrate GPU workloads or keep hybrid
6. **Week 6**: Decommission old infrastructure

## Resources

- [Harvester Documentation](https://docs.harvesterhci.io/)
- [Harvester GPU Support](https://docs.harvesterhci.io/v1.3/advanced/pcidevices/)
- [Rancher Integration](https://docs.harvesterhci.io/v1.3/rancher/rancher-integration/)
- [Longhorn Documentation](https://longhorn.io/docs/)

## Conclusion

Harvester provides a modern HCI platform with excellent Rancher integration. However, for GPU-intensive workloads, the current recommendation is:

1. **Use Harvester** for management VMs, control planes, non-GPU workloads
2. **Keep bare-metal K3s** for GPU workers
3. **Manage both** via Rancher and Fleet

As Harvester's GPU support matures (v1.4+), full migration becomes more viable.
