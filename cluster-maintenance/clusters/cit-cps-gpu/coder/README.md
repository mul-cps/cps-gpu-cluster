# Coder Deployment on Kubernetes

Coder is deployed as a JupyterHub replacement providing cloud development environments with GPU support, persistent storage, and OIDC authentication.

## Architecture

### Components

- **Coder Server**: Main control plane running in the `coder` namespace
- **PostgreSQL**: Dedicated database for Coder state (10Gi Longhorn storage)
- **Workspaces**: User development environments deployed as Kubernetes pods
- **Templates**: Terraform configurations defining workspace types

### Access

- **Primary URL**: https://coder.dshl.unileoben.ac.at
- **Authentication**: OIDC via Authentik (https://auth.cps.unileoben.ac.at)
- **Wildcard Subdomains**: `*.coder.dshl.unileoben.ac.at` for workspace apps

## Available Templates

### CPU Templates

#### cpu-default
- **Resources**: 2 vCPU (0.5 guarantee), 2Gi RAM (1Gi guarantee)
- **Image**: `ghcr.io/mul-cps/cps-jupyter-notebook:latest-standard-cpu`
- **Storage**: 10Gi persistent home directory
- **Use Case**: General development, Python, data science

### GPU Templates

#### gpu-pytorch-single
- **Resources**: 1× NVIDIA GPU, 16 vCPU (8 guarantee), 64Gi RAM (32Gi guarantee)
- **Image**: `ghcr.io/mul-cps/cps-jupyter-notebook:latest-pytorch-code`
- **Features**: PyTorch, CUDA, sudo access
- **Use Case**: Deep learning with PyTorch

#### gpu-tensorflow-single
- **Resources**: 1× NVIDIA GPU, 16 vCPU, 64Gi RAM
- **Image**: `ghcr.io/mul-cps/cps-jupyter-notebook:latest-tf-code`
- **Features**: TensorFlow, CUDA, sudo access
- **Use Case**: Deep learning with TensorFlow

#### gpu-pytorch-dual
- **Resources**: 2× NVIDIA GPU, 32 vCPU (16 guarantee), 128Gi RAM (64Gi guarantee)
- **Image**: `ghcr.io/mul-cps/cps-jupyter-notebook:latest-pytorch-code`
- **Use Case**: Multi-GPU training with PyTorch

#### gpu-tensorflow-dual
- **Resources**: 2× NVIDIA GPU, 32 vCPU, 128Gi RAM
- **Image**: `ghcr.io/mul-cps/cps-jupyter-notebook:latest-tf-code`
- **Use Case**: Multi-GPU training with TensorFlow

### MIG Templates

#### gpu-mig-1g
- **Resources**: 1× MIG 1g.5gb slice, 6 vCPU (3 guarantee), 24Gi RAM (12Gi guarantee)
- **Image**: `ghcr.io/mul-cps/cps-jupyter-notebook:latest-pytorch-code`
- **Use Case**: Smaller GPU workloads, efficient resource sharing

#### gpu-mig-2g
- **Resources**: 1× MIG 2g.10gb slice, 10 vCPU (5 guarantee), 40Gi RAM (20Gi guarantee)
- **Image**: `ghcr.io/mul-cps/cps-jupyter-notebook:latest-pytorch-code`
- **Use Case**: Medium GPU workloads with more memory

### Specialized Templates

#### dask-cluster
- **Resources**: 2 vCPU (1 guarantee), 8Gi RAM (4Gi guarantee)
- **Image**: `nvcr.io/nvidia/rapidsai/base:24.08-cuda12.2-py3.10`
- **Features**: Dask operator integration, ServiceAccount for cluster creation
- **Use Case**: Distributed computing with Dask

#### desktop-ros2
- **Resources**: 1× NVIDIA GPU, 16 vCPU, 64Gi RAM
- **Image**: `ghcr.io/mul-cps/cps-jupyter-notebook:latest-desktop-ros2`
- **Features**: Desktop environment (noVNC), ROS 2, GPU graphics support
- **Use Case**: Robotics development, GUI applications

## Storage

### Home Directories
- **Type**: Persistent Volume Claims (ReadWriteOnce)
- **Storage Class**: `longhorn-fast`
- **Size**: 10-30Gi depending on template
- **Mount**: `/home/coder`
- **Lifecycle**: Persists across workspace restarts and rebuilds

### Shared Storage
- **PVC**: `coder-shared-storage`
- **Type**: ReadWriteMany (RWX)
- **Size**: 500Gi
- **Mount**: `/home/coder/shared`
- **Use Case**: Collaboration, shared datasets

### CPS Persistent Storage
- **PVC**: `cps-persistent1-shared-pvc`
- **Mount**: `/home/coder/cps_persistent1_shared`
- **Use Case**: Long-term data storage

## Template Management

### Creating a Template

1. Navigate to **Templates** in Coder UI
2. Click **Create Template**
3. Select a template directory (e.g., `cpu-default`)
4. Upload the Terraform files
5. Configure template settings:
   - **Name**: Display name for users
   - **Description**: Template purpose and features
   - **Icon**: Visual identifier
   - **Group Access**: Restrict to specific groups (optional)

### Updating a Template

1. Modify the Terraform files in the template directory
2. In Coder UI, navigate to the template
3. Click **Update Template**
4. Upload the modified files
5. Review changes and publish

### Template Development Workflow

```bash
# Navigate to template directory
cd /home/bjoern/git/cps-gpu-cluster/cluster-maintenance/clusters/cit-cps-gpu/coder/templates/cpu-default

# Initialize Terraform
terraform init

# Validate syntax
terraform validate

# Format code
terraform fmt

# Test locally (requires Coder CLI)
coder templates push cpu-default --directory .
```

## User Guide

### Creating a Workspace

1. Log in to https://coder.dshl.unileoben.ac.at
2. Click **Create Workspace**
3. Select a template based on your needs
4. Configure workspace name
5. Click **Create**

### Accessing a Workspace

- **VS Code (code-server)**: Click the "VS Code" app in workspace dashboard
- **SSH**: Use `coder ssh <workspace-name>`
- **Terminal**: Click "Terminal" in workspace dashboard

### GPU Access

GPU templates are restricted to users in the `app_jupyterhub_poweruser` or `jupyter_admin` groups. To verify GPU access in your workspace:

```bash
nvidia-smi
```

### Dask Cluster Creation

In a Dask workspace:

```python
from dask_kubernetes.operator import KubeCluster

cluster = KubeCluster(
    name="my-dask-cluster",
    namespace="dask-compute",
    n_workers=3
)

client = cluster.get_client()
```

## Authentication & Authorization

### OIDC Configuration

Coder uses OpenID Connect (OIDC) with Authentik:

- **Issuer**: https://auth.cps.unileoben.ac.at/application/o/coder/
- **Scopes**: `openid`, `profile`, `email`, `groups`
- **Group Sync**: Automatic via `groups` claim

### Group-Based Access

- **All Users**: Can create CPU-only workspaces
- **`app_jupyterhub_poweruser`**: Can create GPU and MIG workspaces
- **`jupyter_admin`**: Full admin access to Coder

### Setting Up Authentik

1. Create new OAuth2/OIDC Provider in Authentik
2. Set redirect URI: `https://coder.dshl.unileoben.ac.at/api/v2/users/oidc/callback`
3. Configure scopes: `openid`, `profile`, `email`, `groups`
4. Create application and link to provider
5. Copy Client ID and Client Secret
6. Update `values.yaml`:
   ```yaml
   - name: CODER_OIDC_CLIENT_ID
     value: "<client-id>"
   - name: CODER_OIDC_CLIENT_SECRET
     value: "<client-secret>"
   ```

## Deployment

### Prerequisites

- Kubernetes cluster with Fleet
- Longhorn storage classes: `longhorn`, `longhorn-fast`, `longhorn-overcommit`
- NVIDIA GPU Operator (for GPU workspaces)
- Ingress NGINX with TLS
- Authentik OIDC provider configured

### Deploy via Fleet

```bash
# Commit changes to Git
cd /home/bjoern/git/cps-gpu-cluster/cluster-maintenance/clusters/cit-cps-gpu
git add coder/
git commit -m "Add Coder deployment"
git push

# Fleet will automatically deploy
# Monitor deployment
kubectl get bundles -n fleet-local | grep coder
kubectl get pods -n coder
```

### Manual Deployment (for testing)

```bash
cd /home/bjoern/git/cps-gpu-cluster/cluster-maintenance/clusters/cit-cps-gpu/coder

# Apply Kubernetes resources
kubectl apply -k .

# Install Helm chart
helm repo add coder-v2 https://helm.coder.com/v2
helm repo update
helm install coder coder-v2/coder \
  --namespace coder \
  --values values.yaml \
  --version 2.29.1
```

## Troubleshooting

### Workspace Stuck in "Starting"

Check pod events:
```bash
kubectl get pods -n coder | grep coder-
kubectl describe pod <pod-name> -n coder
```

Common issues:
- Image pull failures: Check image name and registry access
- Resource constraints: Verify node has sufficient CPU/memory/GPU
- PVC binding: Check storage class and available capacity

### GPU Not Available

Verify GPU operator:
```bash
kubectl get pods -n gpu-operator
```

Check node labels:
```bash
kubectl get nodes -L accelerator
```

Verify runtime class:
```bash
kubectl get runtimeclass nvidia
```

### OIDC Authentication Failing

Check Coder logs:
```bash
kubectl logs -n coder deployment/coder
```

Verify Authentik configuration:
- Redirect URI matches exactly
- Client ID and secret are correct
- Scopes include `openid`, `profile`, `email`, `groups`

### Database Connection Issues

Test PostgreSQL connectivity:
```bash
kubectl run -n coder psql-test --rm -it --image=postgres:15 --restart=Never -- \
  psql "postgres://coder:coder-secure-db-password-2025@postgresql.coder.svc.cluster.local:5432/coder?sslmode=disable" -c '\l'
```

## Monitoring

### Coder Metrics

Coder exposes Prometheus metrics on port 2112:
```bash
kubectl port-forward -n coder deployment/coder 2112:2112
curl http://localhost:2112/metrics
```

### Workspace Resource Usage

View in Coder UI dashboard or use:
```bash
coder stat cpu
coder stat mem
coder stat disk
```

## Migration from JupyterHub

### User Data Migration

1. Users should backup data from JupyterHub home directories
2. Copy to Coder shared storage: `/home/coder/shared/`
3. Or use `cps_persistent1_shared` for long-term storage

### Workflow Differences

| JupyterHub | Coder |
|------------|-------|
| Notebook-centric | IDE-agnostic (VS Code, SSH, terminal) |
| Single server per user | Multiple workspaces per user |
| Profile selection at spawn | Template selection at creation |
| Hub-managed lifecycle | User-managed lifecycle |

### Feature Parity

✅ OIDC authentication
✅ GPU support (full devices + MIG)
✅ Shared storage
✅ Persistent home directories
✅ Dask integration
✅ Desktop environments
✅ Group-based authorization

## Support

For issues or questions:
1. Check Coder logs: `kubectl logs -n coder deployment/coder`
2. Review workspace logs in Coder UI
3. Consult [Coder documentation](https://coder.com/docs)
4. Contact cluster administrators
