# JupyterHub GPU Deployment

GPU-enabled JupyterHub for multi-user notebook environment with dynamic profile selection based on user groups.

## Features

- **Dynamic Profile Selection**: Profile options change based on user group membership
- **Group-Based Access Control**: `cpsHPCAccess` group gets full GPU access, others get CPU-only
- **Custom Image Support**: HPC users can specify custom container images
- **Flexible Resource Configuration**: HPC users can customize CPU, memory, and GPU allocation
- **Persistent Storage**: User home directories stored on NFS with multiple storage tiers
- **OIDC Authentication**: Integration with Authentik for SSO
- **Auto-culling**: Idle notebooks shut down after 1 hour

## Storage Architecture

JupyterHub uses a three-tier storage approach:

### 1. Fast Ephemeral Storage (`/home/jovyan`)
- **Type**: EmptyDir on node SSD
- **Purpose**: Fast workspace for active development
- **Lifecycle**: Deleted when pod terminates
- **Best for**: Active notebooks, temporary files, caches

### 2. Persistent User Storage (`/home/jovyan/Persist`)
- **Type**: NFS with per-user subdirectories via subPathExpr
- **PVC**: `jhub-userdir-rwx` (50TB logical capacity)
- **Purpose**: Long-term user file storage
- **Best for**: Important notebooks, datasets, personal projects

### 3. Shared Team Storage (`/home/jovyan/Shared`)
- **Type**: NFS ReadWriteMany
- **PVC**: `jhub-shared-rwx` (2TB)
- **Purpose**: Team collaboration and shared datasets
- **Best for**: Shared datasets, team projects, collaboration

### Storage Lifecycle
- **Auto-backup**: On pod termination, important files are automatically backed up from ephemeral to persistent storage
- **Symlink**: `/home/jovyan/Save` → `/home/jovyan/Persist` for easy access

## Access

JupyterHub is accessible at: **https://jupyterhub.cps.unileoben.ac.at**

Authentication via Authentik OIDC (SSO).

## User Profiles

### Regular Users (No Special Groups)

Users without the `cpsHPCAccess` group see a single profile:

- **💻 Standard Notebook Environment**
  - 2 CPU cores, 4GB RAM
  - CPU-only (no GPU access)
  - Fixed image: `quay.io/jupyter/pytorch-notebook:2025-11-06`
  - Note displayed: "For GPU access, please contact your administrator."

### HPC Users (cpsHPCAccess Group)

Users in the `cpsHPCAccess` Authentik group have access to:

#### Pre-configured Profiles

1. **💻 CPU Only (Basic)**
   - 2 cores, 4GB RAM
   - Default selection

2. **🚀 Single A100 GPU**
   - 1 NVIDIA A100 GPU
   - 8 cores, 32GB RAM

3. **🔥 Dual A100 GPUs**
   - 2 NVIDIA A100 GPUs (maximum per node)
   - 16 cores, 64GB RAM

#### Custom Configuration Profile

4. **⚙️ Custom Configuration**
   
   Allows full customization with the following options:

   **Container Image:**
   - Pre-configured: PyTorch, TensorFlow, Data Science Stack
   - Custom: Enter any valid `image:tag` format
   - Validation ensures proper image format

   **GPU Count:**
   - 0 GPUs (CPU-only)
   - 1 GPU (default)
   - 2 GPUs (maximum)

   **CPU Cores:**
   - 2, 4, 8 (default), or 16 cores

   **Memory (RAM):**
   - 4 GB, 8 GB, 16 GB, 32 GB (default), 64 GB, or 128 GB (maximum)

## Managing User Access

To grant GPU access to a user:

1. Log in to Authentik admin interface
2. Navigate to the user or create a new user
3. Add the user to the **`cpsHPCAccess`** group
4. User will see expanded profile options on next login to JupyterHub

To grant admin access to JupyterHub:

1. Add user to the **`jupyter_admin`** group in Authentik
2. User will have access to `/hub/admin` panel

## Testing GPU Access

After spawning a GPU-enabled notebook, run:

```python
import torch

# Check CUDA availability
print(f"CUDA available: {torch.cuda.is_available()}")
print(f"CUDA version: {torch.version.cuda}")
print(f"GPU count: {torch.cuda.device_count()}")

# List GPUs
for i in range(torch.cuda.device_count()):
    print(f"GPU {i}: {torch.cuda.get_device_name(i)}")
    
# Simple GPU test
if torch.cuda.is_available():
    x = torch.rand(1000, 1000).cuda()
    y = torch.rand(1000, 1000).cuda()
    z = x @ y
    print(f"Matrix multiply on GPU: {z.shape}")
```

Or with TensorFlow:

```python
import tensorflow as tf

print("TensorFlow version:", tf.__version__)
print("GPU devices:", tf.config.list_physical_devices('GPU'))

# Simple GPU test
if tf.config.list_physical_devices('GPU'):
    with tf.device('/GPU:0'):
        a = tf.random.normal([1000, 1000])
        b = tf.random.normal([1000, 1000])
        c = tf.matmul(a, b)
        print(f"Matrix multiply on GPU: {c.shape}")
```

## Configuration Details

### Dynamic Profile Implementation

The profile list is generated dynamically using an async function that checks user group membership:

```python
async def dynamic_profile_list(spawner):
    user = spawner.user
    user_groups = set(group.name for group in user.groups)
    
    if 'cpsHPCAccess' in user_groups:
        return [... full GPU profiles ...]
    else:
        return [... CPU-only profile ...]
```

This ensures that users only see options they're authorized to use.

### Custom Image Validation

Custom images must follow the `image:tag` format and are validated with regex:

```regex
^.+:.+$
```

Examples of valid custom images:
- `nvcr.io/nvidia/pytorch:24.10-py3`
- `quay.io/jupyter/scipy-notebook:latest`
- `custom-registry.example.com/ml-notebook:v1.0`

### Resource Limits

Maximum resources per user (enforced for cpsHPCAccess group):
- **GPUs**: 2 (hardware limit per node)
- **CPUs**: 16 cores
- **Memory**: 128 GB

Regular users are limited to:
- **GPUs**: 0
- **CPUs**: 2 cores
- **Memory**: 4 GB

## Architecture

### Authentication Flow

1. User accesses JupyterHub URL
2. Redirected to Authentik for OIDC login
3. Authentik returns user info + group memberships
4. JupyterHub processes groups via `claim_groups_key`
5. Dynamic profile list generated based on groups
6. User selects profile and spawns notebook

### Group Synchronization

Groups are synchronized from Authentik on each login:
- `manage_groups: true` ensures group memberships stay current
- Groups are stored in JupyterHub database
- Profile list regenerates on each spawn page visit

## Customization

### Adding New Pre-configured Profiles (for HPC users)

Edit `values.yaml` and add to the HPC user profile list:

```yaml
{
    'display_name': '🎯 Your Custom Profile',
    'description': 'Description here',
    'kubespawner_override': {
        'cpu_limit': 4,
        'mem_limit': '8G',
        'image': 'your-image:tag'
    }
}
```

### Modifying Resource Options

Adjust available choices in the Custom Configuration profile by editing the `profile_options` section in `values.yaml`.

### Changing Group Name

To use a different group name instead of `cpsHPCAccess`:

1. Edit `values.yaml`
2. Find: `has_hpc_access = 'cpsHPCAccess' in user_groups`
3. Replace `'cpsHPCAccess'` with your group name
4. Commit and push changes (Fleet will auto-deploy)

## Monitoring

View active notebooks:

```bash
kubectl get pods -n jupyterhub -l component=singleuser-server
```

Check resource usage:

```bash
kubectl top pods -n jupyterhub
```

## Troubleshooting

### Notebook won't start

```bash
# Check pod events
kubectl describe pod -n jupyterhub <pod-name>

# Check GPU availability
kubectl get nodes -o json | jq '.items[].status.capacity."nvidia.com/gpu"'
```

### GPU not visible in notebook

1. Verify GPU operator is running
2. Check node labels: `kubectl get nodes --show-labels | grep accelerator`
3. Verify profile has GPU resource requests
