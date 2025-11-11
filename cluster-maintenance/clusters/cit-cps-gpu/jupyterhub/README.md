# JupyterHub Modular Configuration

This directory contains the modular JupyterHub configuration for the CPS GPU Cluster, split into manageable components for better maintainability and following Fleet GitOps best practices.

## Structure

```
jupyterhub/
├── config/                      # Modular configuration components
│   ├── auth.py                 # OAuth and admin user configuration  
│   ├── culler.py               # GPU-aware idle culling logic
│   ├── profiles.py             # GPU profile definitions and form handling
│   └── ui_options_form.html    # Custom profile selection UI
├── templates/                  # Kubernetes templates
│   ├── custom-templates.yaml   # Custom UI templates (info page, etc.)
│   ├── kustomization.yaml     # Kustomize configuration
│   └── namespace.yaml         # Namespace definition
├── fleet.yaml                 # Fleet deployment configuration
├── namespace.yaml             # JupyterHub namespace
├── storage-pvcs.yaml          # Storage PVC definitions
├── values.yaml                # Original monolithic configuration (deprecated)
├── values-new.yaml            # New modular configuration
└── README.md                  # This file
```

## Configuration Components

### 1. Authentication (`config/auth.py`)
- **Purpose**: Centralized OAuth configuration for Authentik SSO
- **Contains**: Client credentials, endpoints, admin user lists
- **Usage**: Loaded by `00-auth-config` extraConfig section

### 2. Profiles (`config/profiles.py`) 
- **Purpose**: GPU profile definitions and form handling logic
- **Contains**: Profile list, form parser, pre-spawn hooks
- **Features**:
  - CPU-only and GPU profiles (1x, 2x A100)
  - PyTorch, TensorFlow, and MIG slice support
  - Resource limits and node selection
  - Custom image/GPU override for admins

### 3. Culler (`config/culler.py`)
- **Purpose**: GPU-aware idle pod culling configuration
- **Features**:
  - Dynamic timeouts (6h for dual-GPU, 4h for single-GPU, 2h for CPU)
  - Priority-based culling (GPU pods freed first)
  - Pre-cull cleanup hooks
  - Resource-aware scheduling

### 4. UI (`config/ui_options_form.html`)
- **Purpose**: Modern profile selection interface
- **Features**:
  - Layered, responsive design
  - GPU access validation via API
  - Custom image/GPU override controls
  - Real-time group membership checking

## GPU Profiles Available

### Standard Profiles
- **CPU (Default)**: 2 vCPU, 2GB RAM - scipy-notebook
- **GPU PyTorch (1×)**: 16 vCPU, 64GB RAM, 1x A100 - PyTorch 24.11
- **GPU TensorFlow (1×)**: 16 vCPU, 64GB RAM, 1x A100 - TensorFlow 24.11  
- **GPU PyTorch (2×)**: 32 vCPU, 128GB RAM, 2x A100 - PyTorch 24.11
- **GPU TensorFlow (2×)**: 32 vCPU, 128GB RAM, 2x A100 - TensorFlow 24.11
- **GPU MIG 1g.5gb**: 8 vCPU, 32GB RAM, 1x MIG slice - PyTorch 24.11

### Access Control
- **GPU Access**: Requires `cpsHPCAccess` or `jupyter_admin` group membership
- **Admin Features**: Custom image/GPU override for admin users

## Storage Architecture

### 1. Fast Ephemeral Storage (`/home/jovyan`)
- **Type**: EmptyDir on node SSD  
- **Purpose**: Fast workspace for active development
- **Lifecycle**: Deleted when pod terminates

### 2. Persistent User Storage (`/home/jovyan/Persist`)  
- **Type**: NFS with per-user subdirectories
- **PVC**: `jhub-userdir-rwx` (50TB logical capacity)
- **Purpose**: Long-term user file storage

### 3. Shared Team Storage (`/home/jovyan/Shared`)
- **Type**: NFS ReadWriteMany
- **PVC**: `jhub-shared-rwx` (2TB)
- **Purpose**: Team collaboration and shared datasets

## Deployment 

The modular configuration uses Fleet's `extraFiles` feature to mount component files into the JupyterHub hub pod:

1. **Kustomize**: Generates ConfigMaps from component files
2. **Fleet**: Processes and deploys the Helm chart with mounted configs
3. **Hub**: Loads components via `extraConfig` sections

### Switching to Modular Configuration

To deploy the modular configuration:

```bash
# Rename current values.yaml to backup
mv values.yaml values-monolithic.yaml

# Use the new modular configuration
mv values-new.yaml values.yaml

# Commit and let Fleet deploy
git add -A && git commit -m "Switch to modular JupyterHub configuration"
git push
```

## Benefits

1. **Maintainability**: Separate concerns into focused files
2. **Readability**: Each component is self-contained and documented
3. **Reusability**: Components can be shared across environments
4. **Testability**: Individual components can be tested in isolation
5. **Version Control**: Cleaner diffs when modifying specific features

## Access

JupyterHub is accessible at: **https://jupyterhub.cps.unileoben.ac.at**

Authentication via Authentik OIDC (SSO).

## Configuration Lifecycle

1. **Development**: Edit components in `config/` directory
2. **Build**: Kustomize generates ConfigMaps from component files  
3. **Template**: Fleet processes Helm chart with component data
4. **Deploy**: JupyterHub hub loads components via extraConfig
5. **Runtime**: Components provide configuration and logic

## Maintenance

### Adding New Profiles
Edit `config/profiles.py` and add new entries to `PROFILE_LIST`.

### Modifying Authentication  
Update OAuth endpoints and credentials in `config/auth.py`.

### Adjusting Culler Logic
Tune timeout and priority functions in `config/culler.py`.

### UI Customization
Modify the HTML/CSS/JavaScript in `config/ui_options_form.html`.

## Migration Notes

The new modular configuration maintains full compatibility with the existing setup:
- All OAuth settings preserved
- All GPU profiles maintained  
- Storage configuration unchanged
- Same UI functionality with improved design

## Troubleshooting

### Component Loading Issues
Check hub pod logs for import errors:
```bash
kubectl logs -n jupyterhub deployment/hub
```

### Configuration Validation
Verify ConfigMaps are created correctly:
```bash
kubectl get configmaps -n jupyterhub | grep jhub-
```

### File Mounting
Check that component files are mounted in hub pod:
```bash
kubectl exec -n jupyterhub deployment/hub -- ls -la /etc/jupyterhub/extra/
```

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
