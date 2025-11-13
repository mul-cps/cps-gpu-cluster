# CPS GPU Cluster - Presentation Summary

## Executive Overview

A production-ready, highly available Kubernetes cluster on Proxmox VE, designed for AI/ML workloads with GPU acceleration, managed entirely through Infrastructure as Code (IaC) and GitOps principles.

---

## 1. Hardware Architecture

### Physical Infrastructure

- **Host Platform**: Single Proxmox VE server (`cit-gpu-01.unileoben.ac.at`)
  - Multi-core CPU (48+ cores available)
  - ~1 TB RAM
  - 2 TB NVMe storage + NFS backend
  - **8× NVIDIA A100 40GB GPUs** (PCIe passthrough)

### Virtual Machine Topology

```
┌─────────────────────────────────────────────────────────┐
│              Proxmox VE Host (cit-gpu-01)               │
│                                                         │
│  ┌──────────────────┐        ┌─────────────────────┐  │
│  │ Control Plane    │        │  GPU Worker Nodes   │  │
│  │  (HA Cluster)    │        │                     │  │
│  │                  │        │  wk-gpu1 (2×A100)   │  │
│  │  k3s-cp1 (35)   │        │  wk-gpu2 (2×A100)   │  │
│  │  k3s-cp2 (36)   │        │  wk-gpu3 (2×A100)   │  │
│  │  k3s-cp3 (37)   │        │  wk-gpu4 (2×A100)   │  │
│  │                  │        │                     │  │
│  │  4 vCPU × 3      │        │  48 vCPU × 4        │  │
│  │  16 GB × 3       │        │  128 GB × 4         │  │
│  │  100 GB × 3      │        │  500 GB + 1TB × 4   │  │
│  └──────────────────┘        └─────────────────────┘  │
│                                                         │
│  ┌──────────────────┐                                  │
│  │ Maintenance VM   │                                  │
│  │  k3s-maint (42)  │  (Ansible/kubectl operations)   │
│  │  4 vCPU, 8 GB    │                                  │
│  └──────────────────┘                                  │
└─────────────────────────────────────────────────────────┘
```

**Total Cluster Resources:**
- **7 nodes**: 3 control plane + 4 GPU workers
- **204 vCPUs**: 12 (control) + 192 (workers)
- **560 GB RAM**: 48 GB (control) + 512 GB (workers)
- **8 GPUs**: NVIDIA A100 40GB (2 per worker node)
- **Storage**: 6.3 TB total (OS + scratch)

---

## 2. Kubernetes Cluster Structure

### K3s High Availability Configuration

**Control Plane (3 nodes)**
- Embedded etcd for HA consensus
- No single point of failure
- Automatic leader election
- API server load-balanced across all 3 nodes

**Worker Nodes (4 nodes)**
- Dedicated GPU workload execution
- Each node: 2× A100 GPUs via PCIe passthrough
- NVMe scratch storage for high-performance I/O
- Node labels for intelligent scheduling:
  - `accelerator=nvidia`
  - `gpu-model=a100`
  - `scratch=nvme`

**Taints & Tolerations**
- Control plane: `node-role.kubernetes.io/control-plane=true:NoSchedule`
  - Prevents user workloads from consuming control plane resources
- GPU workers: No taints (accept all workloads with proper resource requests)

---

## 3. Network Architecture

### Network Topology (VLAN 633)

```
┌──────────────────────────────────────────────────────────────┐
│                      VLAN 633 (10.21.0.0/16)                 │
│  Gateway: 10.21.1.17 | DNS: 193.171.87.249, 193.171.87.250  │
└──────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                           │
┌───────▼──────────┐                    ┌──────────▼───────────┐
│  Control Plane   │                    │   GPU Workers        │
│                  │                    │                      │
│  k3s-cp1  (.35)  │                    │  k3s-wk-gpu1  (.38)  │
│  k3s-cp2  (.36)  │                    │  k3s-wk-gpu2  (.43)  │
│  k3s-cp3  (.37)  │                    │  k3s-wk-gpu3  (.40)  │
│                  │                    │  k3s-wk-gpu4  (.41)  │
└──────────────────┘                    └──────────────────────┘
                                                 │
                                        ┌────────▼─────────┐
                                        │  Maintenance VM  │
                                        │  k3s-maint (.42) │
                                        └──────────────────┘
```

### IP Allocation Table

| Component | IP Address | MAC Address | Role |
|-----------|-----------|-------------|------|
| k3s-cp1 | 10.21.0.35 | 00:16:3e:63:79:26 | Control Plane 1 |
| k3s-cp2 | 10.21.0.36 | 00:16:3e:63:79:27 | Control Plane 2 |
| k3s-cp3 | 10.21.0.37 | 00:16:3e:63:79:28 | Control Plane 3 |
| k3s-wk-gpu1 | 10.21.0.38 | 00:16:3e:63:79:29 | GPU Worker 1 (2×A100) |
| k3s-wk-gpu2 | 10.21.0.43 | 00:16:3e:63:79:2e | GPU Worker 2 (2×A100) |
| k3s-wk-gpu3 | 10.21.0.40 | 00:16:3e:63:79:2b | GPU Worker 3 (2×A100) |
| k3s-wk-gpu4 | 10.21.0.41 | 00:16:3e:63:79:2c | GPU Worker 4 (2×A100) |
| k3s-maint | 10.21.0.42 | 00:16:3e:63:79:2f | Maintenance/Ansible |

### Kubernetes Internal Networking

- **Pod Network (Flannel CNI)**: `10.42.0.0/16`
- **Service Network**: `10.43.0.0/16`
- **DNS**: CoreDNS in-cluster resolution

---

## 4. Ingress & External Access

### Load Balancer Architecture (MetalLB)

**MetalLB Configuration:**
- **Mode**: Layer 2 (ARP-based)
- **IP Pool**: `10.21.0.50 - 10.21.0.60` (11 addresses)
- **Auto-assignment**: Yes
- **Namespace**: `metallb-system`

**How it Works:**
1. Service requests `type: LoadBalancer`
2. MetalLB assigns IP from pool (e.g., 10.21.0.50)
3. MetalLB speakers announce ARP on VLAN 633
4. External traffic reaches any GPU worker node
5. Node routes to correct pod via iptables/IPVS

```
External User
    ↓ (https://jupyterhub.cps.unileoben.ac.at)
    ↓ DNS resolves to 10.21.0.50
    ↓
MetalLB Layer 2 (ARP response from any worker)
    ↓
NGINX Ingress Controller (DaemonSet on all workers)
    ↓ (routing based on Host header)
    ↓
JupyterHub Service (ClusterIP)
    ↓
JupyterHub Pods
```

### NGINX Ingress Controller

**Deployment Strategy:**
- **Type**: DaemonSet (runs on all 4 GPU workers)
- **Service**: LoadBalancer (MetalLB assigns 10.21.0.50)
- **Traffic Policy**: `Local` (preserves source IP)
- **Metrics**: Enabled for Prometheus

**Ingress Resources:**

| Service | Hostname | IP | TLS |
|---------|----------|-----|-----|
| Rancher | rancher.cps.unileoben.ac.at | 10.21.0.50 | ✓ (wildcard cert) |
| JupyterHub | jupyterhub.cps.unileoben.ac.at | 10.21.0.50 | ✓ (wildcard cert) |
| JupyterHub Test | jupyterhub-test.cps.unileoben.ac.at | 10.21.0.50 | ✓ (wildcard cert) |

**Certificate Management:**
- **Issuer**: Custom CA (wildcard-cert ClusterIssuer)
- **Secret**: `wildcard-cps-cert` (in cert-manager namespace)
- **Scope**: `*.cps.unileoben.ac.at`
- **Provisioning**: Manual (IT-provided certificates)

### Ingress Traffic Flow

```
┌─────────────────────────────────────────────────────────┐
│  Internet / Campus Network                              │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  DNS Resolution        │
        │  *.cps.unileoben.ac.at │
        │  → 10.21.0.50          │
        └────────┬───────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────┐
│  MetalLB Layer 2 Speaker (ARP on VLAN 633)            │
│  Any GPU worker responds                              │
└────────┬───────────────────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  NGINX Ingress Controller DaemonSet                    │
│  Runs on: wk-gpu1, wk-gpu2, wk-gpu3, wk-gpu4         │
│  Port 80/443 → TLS termination                        │
└────────┬───────────────────────────────────────────────┘
         │
         ├──▶ Host: rancher.* → Rancher Service (ClusterIP)
         ├──▶ Host: jupyterhub.* → JupyterHub Service (ClusterIP)
         └──▶ Host: jupyterhub-test.* → JupyterHub-Test Service (ClusterIP)
```

---

## 5. JupyterHub Configuration & Topology

### Architecture Overview

**Multi-tenant Jupyter notebook environment with:**
- OAuth2 authentication (Authentik SSO)
- GPU-aware profile selection
- Persistent user storage (NFS)
- Scalable infrastructure (Kubernetes-native)

### JupyterHub Components

```
┌─────────────────────────────────────────────────────────────┐
│                      JupyterHub Namespace                   │
│                                                             │
│  ┌──────────────┐     ┌─────────────┐    ┌──────────────┐ │
│  │  Hub         │────▶│  PostgreSQL │    │ User Pods    │ │
│  │  (Controller)│     │  (Database) │    │              │ │
│  │              │     └─────────────┘    │ ┌──────────┐ │ │
│  │  - Auth      │                        │ │ Notebook │ │ │
│  │  - Spawner   │     ┌─────────────┐    │ │ GPU:     │ │ │
│  │  - Scheduler │────▶│  Proxy      │    │ │ PyTorch  │ │ │
│  └──────────────┘     │  (Routing)  │    │ └──────────┘ │ │
│                       └──────┬──────┘    │              │ │
│                              │           │ ┌──────────┐ │ │
│                              └───────────┼▶│ Notebook │ │ │
│                                          │ │ GPU:     │ │ │
│                                          │ │ TF       │ │ │
│                                          │ └──────────┘ │ │
│                                          └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### User Profile Options

**1. CPU Profile (Default)**
- **Resources**: 2 vCPU (shared), 2 GiB RAM
- **Image**: `jupyter/datascience-notebook`
- **Use Case**: Lightweight notebooks, data analysis
- **Access**: All authenticated users

**2. GPU Single Profiles**
- **PyTorch Single**: 1× GPU, 16 vCPU, 64 GiB RAM
- **TensorFlow Single**: 1× GPU, 16 vCPU, 64 GiB RAM
- **Resource Request**: `nvidia.com/gpu: 1`
- **RuntimeClass**: `nvidia`
- **Use Case**: Model training, inference

**3. GPU Dual Profiles**
- **PyTorch Dual**: 2× GPU, 32 vCPU, 128 GiB RAM
- **TensorFlow Dual**: 2× GPU, 32 vCPU, 128 GiB RAM
- **Resource Request**: `nvidia.com/gpu: 2`
- **Use Case**: Multi-GPU training, large models

**4. MIG (Multi-Instance GPU) Profiles**
- **MIG 1g.5gb**: 1× MIG slice, 6 vCPU, 24 GiB RAM
- **MIG 2g.10gb**: 1× MIG slice, 10 vCPU, 40 GiB RAM
- **Resource Request**: `nvidia.com/mig-1g.5gb` or `nvidia.com/mig-2g.10gb`
- **Use Case**: Efficient GPU sharing, smaller workloads
- **Note**: Only available on `k3s-wk-gpu1` (configured for MIG)

### GPU Allocation Strategy

**Mixed Mode Configuration:**
- **3 nodes** (wk-gpu2, wk-gpu3, wk-gpu4): Full GPU mode
  - Each provides 2× exclusive A100 GPUs
  - Total: 6 full GPUs available
  
- **1 node** (wk-gpu1): MIG mode
  - Each A100 partitioned into smaller instances
  - Example: 7× 1g.5gb slices per GPU
  - Enables more concurrent users with smaller resource needs

**Scheduling Logic:**
```python
# Kubernetes pod placement
if profile == "mig-1g" or profile == "mig-2g":
    node_selector = {"nvidia.com/mig.capable": "true"}
    # Schedules to wk-gpu1 only
else:
    resource_request = {"nvidia.com/gpu": count}
    # Schedules to any of wk-gpu2, wk-gpu3, wk-gpu4
```

### Authentication & Authorization

**OAuth2 Flow (Authentik):**
1. User navigates to `https://jupyterhub.cps.unileoben.ac.at`
2. Redirected to Authentik SSO (`auth.cps.unileoben.ac.at`)
3. User authenticates with university credentials
4. OAuth2 callback returns user info + groups
5. JupyterHub checks group membership:
   - `jupyter_admin`: Full admin access
   - `cpsHPCAccess`: GPU profile access
   - All authenticated users: CPU profile access

**Group-based Access Control:**
```python
# Hub configuration
admin_groups = ["jupyter_admin"]
allowed_gpu_groups = ["cpsHPCAccess", "jupyter_admin"]

# Profile visibility determined by group membership
if user.groups.intersection(allowed_gpu_groups):
    show_gpu_profiles = True
```

### Storage Architecture

**Persistent Volumes:**
- **Home Directories**: NFS-backed PVCs (per-user)
  - StorageClass: `nfs-client`
  - Shared across all notebook servers
  - Survives pod restarts
  
- **Database**: PostgreSQL PVC
  - Stores user sessions, server state
  - 10 GiB allocation

- **Scratch Storage** (Optional):
  - Local NVMe on worker nodes
  - StorageClass: `fast-scratch`
  - For temporary high-IOPS workloads

**Storage Flow:**
```
User → Notebook Pod
         ├─ /home/jovyan (NFS PVC, persistent)
         ├─ /scratch (Local NVMe, ephemeral)
         └─ /datasets (Optional shared NFS)
```

### High Availability Features

**Hub Redundancy:**
- **Database**: PostgreSQL with persistent storage (survives restarts)
- **Proxy**: Configurable replicas (default: 1)
- **User Schedulers**: 2 replicas for load distribution

**Pod Distribution:**
- User pods scheduled across 4 GPU workers
- Affinity rules prevent over-subscription
- Automatic rescheduling on node failure

---

## 6. GitOps & Fleet Management

### GitOps Architecture

```
┌────────────────────────────────────────────────────────┐
│  GitHub Repository                                     │
│  cps-gpu-cluster/cluster-maintenance/                  │
│                                                        │
│  ├── metallb/          (LoadBalancer)                  │
│  ├── ingress-nginx/    (Ingress Controller)            │
│  ├── gpu-operator/     (NVIDIA drivers)                │
│  ├── jupyterhub/       (AI Platform)                   │
│  └── monitoring/       (Observability)                 │
└────────────┬───────────────────────────────────────────┘
             │ git pull (every 15s)
             ▼
┌────────────────────────────────────────────────────────┐
│  Rancher Fleet (GitOps Controller)                     │
│  - Watches Git repository                              │
│  - Detects changes in manifests                        │
│  - Applies Helm charts & Kubernetes resources          │
└────────────┬───────────────────────────────────────────┘
             │ kubectl apply
             ▼
┌────────────────────────────────────────────────────────┐
│  Kubernetes Cluster                                    │
│  - Bundles deployed automatically                      │
│  - Dependency ordering enforced                        │
│  - Drift detection & auto-correction                   │
└────────────────────────────────────────────────────────┘
```

### Deployment Dependencies

```
storage-classes
     ↓
gpu-operator
     ↓
metallb
     ↓
metallb-config
     ↓
ingress-nginx  ←──── wildcard-cert
     ↓                     ↓
jupyterhub ←──────────────┘
     ↓
monitoring
```

**Fleet Bundle Status:**
- `storage-classes`: ✅ 1/1 Ready
- `gpu-operator`: ✅ 1/1 Ready
- `metallb`: ✅ 1/1 Ready
- `metallb-config`: ✅ 1/1 Ready
- `ingress-nginx`: ✅ 1/1 Ready
- `wildcard-cert`: ✅ 1/1 Ready
- `jupyterhub`: ⏳ Deploying
- `monitoring`: ✅ 1/1 Ready

---

## 7. GPU Operator & Device Management

### NVIDIA GPU Operator Components

**Deployed as Helm chart in `gpu-operator` namespace:**

```
┌──────────────────────────────────────────────────────┐
│  GPU Operator Stack                                  │
│                                                      │
│  ┌────────────────┐  ┌─────────────────────────┐   │
│  │ Driver Manager │  │ Container Toolkit       │   │
│  │ (DaemonSet)    │  │ (DaemonSet)             │   │
│  │ - NVIDIA       │  │ - nvidia-docker         │   │
│  │   drivers      │  │ - runtime config        │   │
│  └────────────────┘  └─────────────────────────┘   │
│                                                      │
│  ┌────────────────┐  ┌─────────────────────────┐   │
│  │ Device Plugin  │  │ DCGM Exporter           │   │
│  │ (DaemonSet)    │  │ (DaemonSet)             │   │
│  │ - GPU          │  │ - GPU metrics           │   │
│  │   discovery    │  │ - Prometheus export     │   │
│  │ - Resource     │  └─────────────────────────┘   │
│  │   advertising  │                                 │
│  └────────────────┘  ┌─────────────────────────┐   │
│                      │ Node Feature Discovery  │   │
│                      │ - Detect GPU hardware   │   │
│                      │ - Auto-label nodes      │   │
│                      └─────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

### GPU Resource Advertising

**Node Capacity (per worker):**
```yaml
status:
  capacity:
    nvidia.com/gpu: "2"        # Full GPU mode (3 nodes)
    # OR
    nvidia.com/mig-1g.5gb: "14"  # MIG mode (1 node)
    nvidia.com/mig-2g.10gb: "6"
```

**Pod Resource Request:**
```yaml
resources:
  limits:
    nvidia.com/gpu: 1  # Request 1 full GPU
    # OR
    nvidia.com/mig-1g.5gb: 1  # Request 1 MIG slice
```

---

## 8. Monitoring & Observability

### Prometheus + Grafana Stack

**Components:**
- **Prometheus**: Metrics collection (30s scrape interval)
- **Grafana**: Dashboards and visualization
- **Alertmanager**: Alert routing
- **Node Exporter**: Node-level metrics
- **DCGM Exporter**: GPU-specific metrics

**GPU Metrics Collected:**
- GPU utilization (%)
- Memory usage (GB)
- Temperature (°C)
- Power consumption (W)
- PCIe throughput
- Compute/memory clock speeds
- ECC error counts

**Dashboards:**
- NVIDIA DCGM GPU Dashboard (official)
- Custom GPU utilization dashboard
- JupyterHub user activity
- Cluster resource overview

---

## 9. Key Technical Decisions

### Why K3s?
- **Lightweight**: Minimal overhead vs. full Kubernetes
- **Embedded etcd**: No external dependency
- **Single binary**: Easy installation & updates
- **Production-ready**: CNCF certified Kubernetes distribution

### Why MetalLB Layer 2?
- **No BGP required**: Campus network doesn't support BGP
- **Simple ARP-based**: Works with existing switch infrastructure
- **VLAN compatibility**: Integrates with MUL VLAN 633

### Why NGINX Ingress (not Traefik)?
- **Mature**: Battle-tested in production
- **Performance**: Highly optimized for throughput
- **Metrics**: Native Prometheus integration
- **Compatibility**: Wide ecosystem support

### Why NFS for Storage?
- **Shared access**: Multiple pods can mount same volume (ReadWriteMany)
- **Simple**: No complex distributed storage needed
- **Reliable**: MUL-provided NFS infrastructure
- **Future**: Can migrate to Longhorn when HA storage nodes available

### Why Mixed MIG Strategy?
- **Flexibility**: Support both exclusive and shared GPU workloads
- **Efficiency**: MIG enables more concurrent users for smaller jobs
- **Cost-effective**: Maximize GPU utilization
- **Future-proof**: Can adjust MIG configuration per node as needed

---

## 10. Deployment Workflow

### Initial Provisioning (Terraform)

```bash
# 1. Create VMs with GPU passthrough
cd bootstrap-cluster/terraform
tofu init
tofu plan -out=tfplan
tofu apply tfplan

# Output: 7 VMs + Ansible inventory
```

### Cluster Installation (Ansible)

```bash
# 2. Install K3s HA cluster
cd bootstrap-cluster/ansible
ansible-playbook -i inventory.ini playbooks/site.yml

# Installs:
# - K3s control plane (embedded etcd)
# - K3s workers with GPU support
# - Storage classes (NFS + local-path)
# - GPU Operator
```

### GitOps Configuration (Fleet)

```bash
# 3. Deploy applications via Fleet
# Push to Git → Fleet automatically deploys
git add cluster-maintenance/
git commit -m "Deploy JupyterHub"
git push

# Fleet monitors:
# - cluster-maintenance/clusters/cit-cps-gpu/
# - Applies all fleet.yaml bundles
# - Respects dependency order
```

---

## 11. Disaster Recovery

### Backup Strategy

**Cluster State:**
- etcd snapshots (automated by K3s)
- Stored on control plane nodes
- Configurable retention (default: 5 snapshots)

**Application State:**
- JupyterHub database: PostgreSQL PVC (backed by NFS)
- User home directories: NFS (backed by MUL storage)
- GitOps: All configs in Git (source of truth)

**Recovery Procedure:**
1. Rebuild cluster with Terraform + Ansible
2. Restore etcd snapshot (if needed)
3. Fleet re-deploys all applications from Git
4. User data persists on NFS (no data loss)

---

## 12. Future Enhancements

### Short-term (3-6 months)
- [ ] Implement automated etcd backups to object storage
- [ ] Add GPU time-slicing for over-subscription
- [ ] Deploy additional monitoring dashboards
- [ ] Configure Alertmanager notifications (Slack/email)
- [ ] Implement resource quotas per user/group

### Medium-term (6-12 months)
- [ ] Add second Proxmox node for true HA
- [ ] Migrate to Longhorn for distributed storage
- [ ] Implement cluster-wide backup solution (Velero)
- [ ] Add JupyterHub usage analytics
- [ ] Integrate with university identity management

### Long-term (1+ year)
- [ ] Migrate to Harvester HCI platform
- [ ] Implement multi-cluster management
- [ ] Add MLOps pipeline (Kubeflow)
- [ ] Deploy model serving infrastructure
- [ ] Implement chargeback/showback for resources

---

## 13. Lessons Learned

### Successes
✅ **Infrastructure as Code**: 100% reproducible infrastructure  
✅ **GitOps**: Declarative, auditable deployments  
✅ **GPU Passthrough**: Full PCIe performance in VMs  
✅ **HA Control Plane**: No single point of failure  
✅ **Automated SSH Setup**: Terraform + QEMU guest agent integration  

### Challenges
⚠️ **Network Conflicts**: IP/MAC address collision required reconfiguration  
⚠️ **MetalLB CRDs**: Required careful Fleet bundle ordering  
⚠️ **Certificate Management**: Manual wildcard cert provisioning needed  
⚠️ **JupyterHub Complexity**: OAuth2 + profile config requires expertise  

### Best Practices Established
📋 **Documentation**: Everything documented in Markdown  
📋 **Version Control**: All configs in Git, no manual kubectl apply  
📋 **Validation**: Automated verification scripts (`scripts/verify.sh`)  
📋 **Modularity**: Separate bundles for each component  
📋 **Security**: Secrets in Kubernetes, not in Git  

---

## Conclusion

This cluster represents a **production-grade AI/ML platform** that balances:
- **Performance**: GPU acceleration, NVMe storage, optimized networking
- **Reliability**: HA control plane, automatic failover, persistent storage
- **Usability**: Web-based notebooks, SSO integration, profile selection
- **Maintainability**: GitOps, IaC, automated deployments
- **Scalability**: Horizontal scaling of workers, MIG partitioning, resource quotas

**Ready for:**
- Research workloads (model training, data analysis)
- Teaching (multi-tenant notebook environment)
- Production ML (model serving, batch inference)
- Future expansion (additional nodes, storage, applications)
