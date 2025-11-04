# CPS GPU Cluster - Project Plan

This file contains the original project specification and goals.

## Project Name
**homelab-k3s-gpu-cluster** (Repository: cps-gpu-cluster)

## Goal
Deploy a reproducible GPU-enabled Kubernetes environment for AI and JupyterHub workloads.
The environment must support Rancher + Fleet GitOps management.

## Deployment Paths

### Option A: K3s on Proxmox VMs (Current Implementation)
- Terraform provisioning of VMs
- Ansible installation of K3s
- GPU passthrough via VFIO
- NFS shared storage + local NVMe scratch
- **Status**: Fully implemented in this repository

### Option B: Harvester Bare-Metal (Future)
- When second bare-metal server available
- Native VM management
- Longhorn distributed storage
- Better HA capabilities
- See [docs/harvester-migration.md](harvester-migration.md)

## Hardware Topology

### Current Setup
- **Host**: Single Proxmox VE server
  - CPU: Multi-core Xeon/EPYC
  - RAM: ~1 TB
  - Storage: 2 TB NVMe + HDD/NFS
  - GPUs: 8x NVIDIA A100 (PCIe)

### VM Layout
- **Control Plane**: 3 nodes (cp1, cp2, cp3)
  - 4 vCPUs, 16 GB RAM each
  - 100 GB disk
  - HA with embedded etcd

- **GPU Workers**: 4 nodes (wk-gpu1 through wk-gpu4)
  - 16 vCPUs, 128 GB RAM each
  - 500 GB OS disk + 1 TB NVMe scratch
  - 2x A100 GPUs per worker (PCIe passthrough)

### Future Expansion
- Add second Proxmox or bare-metal node
- Possible migration to Harvester
- Additional GPU workers as needed

## Software Stack

### Infrastructure Layer
- **Hypervisor**: Proxmox VE
- **Provisioning**: Terraform (proxmox provider)
- **Configuration**: Ansible
- **Passthrough**: VFIO/IOMMU

### Kubernetes Layer
- **Distribution**: K3s v1.31 (HA mode, embedded etcd)
- **Network**: Flannel CNI
- **Ingress**: NGINX Ingress Controller
- **Certificates**: cert-manager

### Storage
- **Shared Storage**: NFS Subdir External Provisioner (default SC)
- **Fast Scratch**: Local-path provisioner on NVMe
- **Future**: Longhorn (when multiple nodes available)

### GPU Support
- **Operator**: NVIDIA GPU Operator v23.9.1
- **Runtime**: containerd with nvidia-container-toolkit
- **Discovery**: Node Feature Discovery (NFD)
- **Monitoring**: DCGM Exporter

### Management
- **UI**: Rancher
- **GitOps**: Fleet
- **Helm**: v3 for package management

### AI Platform
- **Notebook**: JupyterHub 3.1.0
- **Profiles**: Multiple GPU configurations (0, 1, 2, 4 GPUs)
- **Images**: NVIDIA NGC containers (PyTorch, TensorFlow)
- **Storage**: Persistent home + fast scratch

## Network Configuration

- **Network**: 10.0.0.0/24
- **Gateway**: 10.0.0.1
- **API VIP**: 10.0.0.100 (optional, for kube-vip/MetalLB)
- **Control Planes**: 10.0.0.11-13
- **GPU Workers**: 10.0.0.21-24
- **NFS Server**: 10.0.0.30:/export/k3s
- **Cluster CIDR**: 10.42.0.0/16
- **Service CIDR**: 10.43.0.0/16

## Repository Structure

### bootstrap-cluster/
Infrastructure provisioning and initial cluster setup.

**Terraform**: VM creation with GPU passthrough
- Proxmox provider configuration
- Control plane VMs (q35, OVMF)
- GPU worker VMs with PCIe passthrough
- Cloud-init integration
- Inventory generation

**Ansible**: K3s installation and configuration
- System prerequisites
- K3s HA cluster setup
- Node labeling and tainting
- Storage provisioners
- GPU Operator installation

### cluster-maintenance/
Day-2 operations via Fleet GitOps.

**Structure**:
- `clusters/homelab/fleet.yaml` - Bundle configuration
- `clusters/homelab/gpu-operator/` - GPU Operator Helm chart
- `clusters/homelab/jupyterhub/` - JupyterHub deployment
- `clusters/homelab/storageclasses/` - Storage configurations
- `clusters/homelab/tests/` - Validation pods

**Benefits**:
- Declarative configuration in Git
- Automatic synchronization
- Version control for all changes
- Easy rollback
- Multi-cluster support (future)

## Deployment Flow

### Phase 1: Infrastructure (Terraform)
1. Enable GPU passthrough on Proxmox
2. Create VM templates with cloud-init
3. Provision control plane VMs
4. Provision GPU worker VMs with PCIe devices
5. Generate Ansible inventory

### Phase 2: Cluster Setup (Ansible)
1. System prerequisites (swap, modules, sysctl)
2. K3s installation on control planes (HA)
3. K3s agent installation on workers
4. Node labeling and tainting
5. NFS provisioner deployment
6. Fast-scratch StorageClass creation
7. Helm repository configuration

### Phase 3: GPU Support
1. NVIDIA GPU Operator installation
2. Driver and toolkit deployment
3. Device plugin configuration
4. DCGM exporter for monitoring
5. GPU resource verification

### Phase 4: Management (Rancher + Fleet)
1. cert-manager installation
2. Rancher deployment
3. Fleet GitOps configuration
4. GitRepo creation for cluster-maintenance
5. Automatic application deployment

### Phase 5: AI Platform (JupyterHub)
1. JupyterHub Helm chart via Fleet
2. Multiple GPU profile configuration
3. Persistent storage setup
4. Fast scratch volume configuration
5. NVIDIA NGC image integration
6. User access and testing

## Key Features

### High Availability
- 3-node control plane with embedded etcd
- Rancher with 3 replicas
- Storage redundancy via NFS (future: Longhorn)

### GPU Scheduling
- Node labels for GPU workers
- Resource requests/limits
- Multiple profile templates
- Automatic GPU discovery

### Storage Tiers
1. **NFS (nfs-client)**: Default, shared, persistent
   - JupyterHub home directories
   - Rancher/Fleet configurations
   - Application data

2. **Fast Scratch (fast-scratch)**: Local NVMe, high-performance
   - Temporary computation data
   - Dataset caching
   - Build artifacts

### GitOps Workflow
1. Make changes to `cluster-maintenance/` files
2. Commit and push to Git
3. Fleet detects changes automatically
4. Applications updated in cluster
5. Rollback via Git revert if needed

## Testing Strategy

### Infrastructure Tests
- VM creation and GPU visibility
- Network connectivity
- Storage mount points

### Cluster Tests
- All nodes in Ready state
- etcd cluster health
- Pod networking (CNI)

### GPU Tests
- CUDA vector add sample
- PyTorch GPU detection
- TensorFlow GPU utilization
- Multi-GPU workloads

### Application Tests
- JupyterHub spawner
- GPU notebook access
- Persistent storage
- Scratch volume performance

## Monitoring & Observability

### Metrics (Future)
- Prometheus for cluster metrics
- DCGM Exporter for GPU metrics
- Grafana dashboards
- Alert Manager

### Logging (Future)
- Loki for log aggregation
- Promtail for log collection
- Grafana for visualization

### Current
- `kubectl top nodes` for resource usage
- GPU Operator logs for GPU status
- JupyterHub logs for user activity

## Backup & Disaster Recovery

### Current
- Manual etcd snapshots: `k3s etcd-snapshot`
- NFS backups (external)
- Git for all configurations

### Future
- Velero for cluster backups
- Automated snapshot scheduling
- Disaster recovery runbooks

## Security Considerations

### Network
- Private network (10.0.0.0/24)
- Firewall rules on nodes
- NetworkPolicies (future)

### Access Control
- SSH key authentication only
- Kubernetes RBAC
- Rancher user management
- JupyterHub authentication (currently DummyAuth)

### Secrets
- Kubernetes Secrets for sensitive data
- Sealed Secrets or External Secrets (future)
- Never commit secrets to Git

## Performance Tuning

### CPU Pinning
- Pin vCPUs to physical cores for GPU VMs
- Reduce context switching
- Better deterministic performance

### Huge Pages
- Enable for large memory VMs
- Improved memory performance

### GPU Isolation
- PCIe passthrough with VFIO
- Dedicated GPUs per VM
- No GPU sharing (future: MIG or time-slicing)

### Storage
- NVMe for OS disks
- Separate scratch volumes
- NFS tuning (rsize, wsize)

## Cost Optimization

### Resource Management
- JupyterHub auto-culling (1 hour idle)
- Resource quotas per namespace
- LimitRanges for default limits

### GPU Sharing (Future)
- NVIDIA MIG for A100 partitioning
- Time-slicing for development workloads
- Fractional GPU allocation

## Migration to Harvester

When second server available:

### Benefits
- Unified management (VMs + Kubernetes)
- Built-in Longhorn storage
- Better HA and live migration
- Native Rancher integration

### Challenges
- GPU passthrough is beta in Harvester
- Learning curve
- Migration downtime

### Hybrid Approach
- Harvester for control plane and non-GPU workloads
- Bare-metal K3s for GPU workers
- Both managed via Rancher/Fleet

See [docs/harvester-migration.md](harvester-migration.md) for details.

## Success Criteria

### Infrastructure
- [x] VMs provisioned with GPU passthrough
- [x] K3s HA cluster operational
- [x] Storage classes available
- [x] All nodes in Ready state

### GPU Support
- [x] All 8 GPUs visible in cluster
- [x] GPU Operator running
- [x] CUDA tests passing
- [x] GPU resource scheduling working

### Management
- [ ] Rancher installed and accessible
- [ ] Fleet GitOps configured
- [ ] GitRepo syncing correctly

### Applications
- [x] JupyterHub deployed
- [x] GPU profiles configured
- [ ] Users can access GPU notebooks
- [ ] Persistent storage working

### Documentation
- [x] README with overview
- [x] Getting started guide
- [x] Troubleshooting guide
- [x] Migration guide

## Timeline (Initial Deployment)

- **Week 1**: Proxmox GPU passthrough, VM template
- **Week 2**: Terraform VMs, Ansible K3s cluster
- **Week 3**: Storage, GPU Operator, verification
- **Week 4**: Rancher, Fleet GitOps setup
- **Week 5**: JupyterHub deployment, user testing
- **Week 6**: Documentation, optimization, handoff

## Deliverables

1. **Infrastructure Code**
   - [x] Terraform modules for Proxmox
   - [x] Ansible playbooks for K3s
   - [x] Configuration templates

2. **GitOps Repository**
   - [x] Fleet bundle structure
   - [x] Application manifests
   - [x] Helm values

3. **Documentation**
   - [x] Setup guides
   - [x] Architecture overview
   - [x] Troubleshooting
   - [x] Migration path

4. **Automation**
   - [x] Deployment script
   - [x] Verification script
   - [x] Cleanup script

## Future Enhancements

### Short Term
- [ ] Ingress with TLS (Let's Encrypt)
- [ ] Real authentication (LDAP/OAuth) for JupyterHub
- [ ] Monitoring stack (Prometheus/Grafana)
- [ ] Backup automation (Velero)

### Medium Term
- [ ] Second node addition
- [ ] Harvester evaluation
- [ ] GPU time-slicing or MIG
- [ ] Custom notebook images

### Long Term
- [ ] Multi-cluster Federation
- [ ] Advanced GPU scheduling
- [ ] ML/AI workflow automation
- [ ] Research computing portal

## References

- [K3s Documentation](https://docs.k3s.io/)
- [Proxmox PCI Passthrough](https://pve.proxmox.com/wiki/PCI_Passthrough)
- [NVIDIA GPU Operator](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/)
- [Rancher Documentation](https://rancher.com/docs/)
- [Fleet GitOps](https://fleet.rancher.io/)
- [JupyterHub Kubernetes](https://z2jh.jupyter.org/)

## Contributors

This project was created based on specifications for a GPU-enabled Kubernetes homelab.

## License

MIT License - See LICENSE file for details
