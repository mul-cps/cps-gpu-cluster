# JupyterHub GPU Deployment

GPU-enabled JupyterHub for multi-user notebook environment.

## Features

- **Multiple GPU Profiles**: Users can select CPU-only, 1 GPU, 2 GPUs, or 4 GPUs
- **Persistent Storage**: User home directories stored on NFS
- **Fast Scratch**: NVMe-backed scratch space for temporary data
- **Pre-configured Images**: NVIDIA NGC containers with PyTorch/TensorFlow
- **Auto-culling**: Idle notebooks shut down after 1 hour

## Access

After deployment:

```bash
# Get JupyterHub URL
kubectl get svc -n jupyterhub

# Port-forward for local access
kubectl port-forward -n jupyterhub svc/proxy-public 8000:80
```

Access at: http://localhost:8000

Default login (DummyAuthenticator):
- Username: any username
- Password: `jupyter`

## User Profiles

Users can select from:

1. **CPU Only** - 2 cores, 4GB RAM
2. **Single A100** - 8 cores, 32GB RAM, 1 GPU
3. **Dual A100** - 16 cores, 64GB RAM, 2 GPUs
4. **Research** - 32 cores, 128GB RAM, 4 GPUs

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

## Customization

### Change Authentication

Edit `values.yaml` and replace DummyAuthenticator with real auth:

```yaml
hub:
  config:
    JupyterHub:
      authenticator_class: ldapauthenticator.LDAPAuthenticator
    LDAPAuthenticator:
      server_address: ldap.example.com
      # ... LDAP configuration
```

### Add Custom Images

Add new profiles in `values.yaml`:

```yaml
singleuser:
  profileList:
    - display_name: "My Custom Image"
      kubespawner_override:
        image: myregistry/custom-notebook:latest
```

### Adjust Resource Limits

Modify CPU/memory/GPU limits in profile definitions.

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
