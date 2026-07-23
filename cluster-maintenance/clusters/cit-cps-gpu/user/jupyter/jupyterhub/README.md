# JupyterHub Modular Configuration

This directory contains the modular JupyterHub configuration for the CPS GPU Cluster, split into manageable components for better maintainability and following Fleet GitOps best practices.

## Structure

```
jupyterhub/
├── fleet.yaml                 # Fleet deployment configuration
├── namespace.yaml             # JupyterHub namespace
├── storage-pvcs.yaml          # Storage PVC definitions
├── values.yaml                # Live configuration (Helm values + extraConfig, incl. PROFILE_CONFIGS)
└── README.md                  # This file
```

All JupyterHub configuration — authentication, GPU/CPU profile
definitions, idle culling, and the profile-selection UI — is defined
inline in `values.yaml`'s `hub.extraConfig` sections, keyed by
`PROFILE_CONFIGS` and related settings. There is no separate
`config/` or `templates/` directory anymore: an earlier iteration of
this bundle split those pieces into standalone Python/HTML files
mounted as ConfigMaps (`templates/profiles.py`, `auth.py`, `culler.py`,
`ui_options_form.html`), but nothing in the live Helm release ever
mounted those ConfigMaps — Fleet's `valuesFiles` only loads
`values.yaml` — so that directory was confirmed dead and removed.

## Configuration Components

All of the below now live directly in `values.yaml`'s `extraConfig`:

### 1. Authentication
- **Purpose**: Centralized OAuth configuration for Authentik SSO
- **Contains**: Client credentials, endpoints, admin user lists
- OAuth client_secret, the LDAP bind password, the Postgres password, and
  the proxy auth token are all SOPS-encrypted `SopsSecret` resources
  (`oauth-sopssecret.yaml`, `ldap-sopssecret.yaml`,
  `postgres-sopssecret.yaml`, `proxy-sopssecret.yaml`) rather than
  plaintext values in `values.yaml` — see `docs/sops-secrets-migration.md`
  for the full migration record and per-secret rotation status.

### 2. Profiles (`PROFILE_CONFIGS` in `values.yaml`)
- **Purpose**: GPU profile definitions and form handling logic
- **Contains**: Profile list, form parser, pre-spawn hooks
- **Features**:
  - CPU-only and GPU profiles
  - PyTorch, TensorFlow support
  - Resource limits and node selection
  - Custom image/GPU override for admins
- GPU sharing for these profiles is now driven by NVIDIA MPS + KAI
  Scheduler's `gpu-memory` annotation, not MIG slices (see
  `system/gpu/gpu-operator/README.md` for the MIG-to-MPS migration
  context).

### 3. Culler
- **Purpose**: GPU-aware idle pod culling configuration
- **Features**:
  - Dynamic timeouts (6h for dual-GPU, 4h for single-GPU, 2h for CPU)
  - Priority-based culling (GPU pods freed first)
  - Pre-cull cleanup hooks
  - Resource-aware scheduling

### 4. UI
- **Purpose**: Modern profile selection interface
- **Features**:
  - Layered, responsive design
  - GPU access validation via API
  - Custom image/GPU override controls
  - Real-time group membership checking

## GPU Profiles Available

All GPUs run in full (non-MIG) mode; sharing for the VRAM-tiered profiles
below is done via NVIDIA MPS, with NVIDIA KAI Scheduler's `gpu-memory`
annotation driving scheduling/bin-packing and a matching
`CUDA_MPS_PINNED_DEVICE_MEM_LIMIT` container env var providing enforcement
(see `system/gpu/gpu-operator/README.md` for the MIG-to-MPS migration
context). Every GPU profile except `gpu-slurm` is scheduled via
`kai-scheduler` with a queue/priority class assignment.

### Whole-GPU profiles (queue `phd-interactive`, priority `kai-phd-interactive`)
- **GPU PyTorch (1×)**: 16 vCPU, 64GB RAM, 1x A100 - PyTorch 24.11
- **GPU TensorFlow (1×)**: 16 vCPU, 64GB RAM, 1x A100 - TensorFlow 24.11
- **GPU PyTorch (2×)**: 32 vCPU, 128GB RAM, 2x A100 - PyTorch 24.11
- **GPU TensorFlow (2×)**: 32 vCPU, 128GB RAM, 2x A100 - TensorFlow 24.11
- **GPU Desktop (ROS2)**: 1x A100 - Desktop/ROS2 image
- **ComfyUI**: 1x A100 - ComfyUI image

### MPS VRAM-tier profiles (queue `phd-interactive`, priority `kai-phd-interactive`)
- **gpu-3gb** / **gpu-5gb** / **gpu-8gb** / **gpu-10gb** / **gpu-12gb** / **gpu-20gb**: shared A100 access at the named VRAM tier (MiB value matches the profile name), PyTorch 24.11
- **gpu-desktop-5gb**: 5GB VRAM tier, Desktop/ROS2 image

### Student profile (queue `courses`, priority `kai-course-high`)
- **gpu-student**: 5GB VRAM tier, gated to student user groups (see `STUDENT_GROUPS` in `values.yaml` — currently a placeholder pending the real Authentik/LDAP group name)

### CPU-only profiles
- **CPU (Default)**: 2 vCPU, 2GB RAM - scipy-notebook
- **Dask Cluster**, **CPU Desktop**: power-user only

### Access Control
- **GPU Access**: Requires `cpsHPCAccess` or `jupyter_admin` group membership (students see only `gpu-student` plus CPU profiles)
- **Admin Features**: Custom image/GPU override for admin users

### Known follow-up
- The GPU Operator's device-plugin config (`system/gpu/gpu-operator/values.yaml`) still needs to be switched from its current `mig-mixed` config to an MPS-sharing config before the VRAM-tier profiles above achieve real GPU memory sharing — until then, the `gpu-memory` annotation/`CUDA_MPS_PINNED_DEVICE_MEM_LIMIT` env var are set correctly but inert.

## Storage Architecture

### 1. Fast Ephemeral Storage (`/home/jovyan`)
- **Type**: EmptyDir on node SSD  
- **Purpose**: Fast workspace for active development
- **Lifecycle**: Deleted when pod terminates

### 2. User Home Storage (`/home/jovyan`)
- **Type**: Dynamic PVC on `longhorn-fast`
- **PVC template**: `claim-{username}`
- **Purpose**: Primary notebook home and working directory
- **Availability**: Required for all singleuser sessions, but not NFS-dependent

### 3. Persistent User Storage (`/home/jovyan/cps_persistent1_users`)
- **Type**: NFS-backed per-user share
- **PVC**: `cps-persistent1-users-pvc`
- **Mount rule**: Added only when LDAP UID/GID lookup succeeds and the user keeps the network-mount toggle enabled
- **Purpose**: Long-term user files

### 4. Shared Team Storage and Scratch
- **Type**: Mixed storage
- **Longhorn shared workspace**: `jupyterhub-shared-storage` at `/home/jovyan/shared`
- **NFS project share**: `cps-persistent1-shared-pvc` at `/home/jovyan/cps_persistent1_shared`
- **NFS scratch1 export**: `cps-scratch1-tmp-v2-pvc` at `/home/jovyan/cps_scratch1`
- **Purpose**: Team collaboration and larger shared datasets
- **Scope**: Longhorn shared workspace stays available for power users; the NFS mounts are individually selectable

### Spawn Resilience
- The base notebook home stays on Longhorn, and the shared power-user workspace stays on Longhorn as well.
- The spawn page now opens on a quick-start welcome face. Pressing `Start Server` launches the default profile immediately.
- An `Options` button flips the card to an advanced configuration face with the full profile and storage controls.
- The advanced face shows the standard NFS mounts as individual checkboxes with the cluster-default mount options prefilled for visibility.
- Power users can also enter a custom NFS server, export path, and notebook mount path on the advanced face.
- If NFS is degraded, users can uncheck network mounts entirely or deselect just the affected NFS entries and still launch the session.
- If the network-mount toggle stays enabled and NFS is unavailable, Kubernetes can still leave the pod in `ContainerCreating` or `Pending` until the mount is satisfied.

## Deployment 

Fleet deploys the JupyterHub Helm chart with `values.yaml` as the sole
values file. All hub-side customization (auth, profiles, culler, UI)
loads via `extraConfig` sections embedded directly in `values.yaml` —
there is no separate ConfigMap-mounting step for these anymore.

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
Edit `values.yaml` and add new entries to `PROFILE_CONFIGS` in its `extraConfig`.

### Modifying Authentication  
Update OAuth endpoints and non-secret settings in `values.yaml`'s auth-related `extraConfig` section. The OAuth `client_secret` itself lives in `oauth-sopssecret.yaml` (SOPS-encrypted) — see `docs/sops-secrets-migration.md`.

### Adjusting Culler Logic
Tune timeout and priority functions in `values.yaml`'s culler `extraConfig` section.

### UI Customization
Modify the profile-selection UI markup embedded in `values.yaml`.

## Troubleshooting

### Component Loading Issues
Check hub pod logs for import/config errors:
```bash
kubectl logs -n jupyterhub deployment/hub
```

### NFS Outage Behavior
- By default, all users request their personal NFS share when LDAP lookup succeeds.
- Power-user profiles can opt into the project-share and scratch NFS mounts individually from the advanced options face.
- If NFS is degraded, flip to `Options` and clear `Enable network mounts` to start on Longhorn-only storage.
- If you see `Pending` or `ContainerCreating`, check the pod events first and then verify the NFS PV/PVCs.

### Recommended Fail-Safe Strategy
1. Keep `/home/jovyan` on non-NFS storage for every profile.
2. Treat NFS-backed storage as optional and let users opt out at spawn time.
3. Preserve core compute behavior when NFS is disabled so the same profile still launches.
4. Expose the degraded-storage mode clearly in the UI and logs.
5. As a later improvement, move optional NFS attachment fully out of the critical spawn path.

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
