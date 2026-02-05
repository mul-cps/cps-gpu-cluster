# GPU Operator Configuration

Fleet-managed GPU Operator configuration for the A100 cluster (4 nodes, 2× A100 PCIE 40GB each).

## Layout
- **gpu1**: `gpu-pool=mig`, `nvidia.com/mig.config=all-1g.10gb`, `nvidia.com/mig.strategy=mixed`. MIG enabled with 4× `1g.10gb` slices per GPU (8 total).
- **gpu2–gpu4**: `gpu-pool=full`, `nvidia.com/mig.config=all-disabled`, `nvidia.com/mig.strategy=single`. Full GPU access, MIG disabled.
- **gpu4 taint**: `gpu-pool=full:NoSchedule` to reserve for explicit full-GPU workloads.
- Labels/taints applied by the Helm hook `node-labeler.yaml` after GPU Operator install/upgrade.

## A100 40GB Valid MIG Profiles
| Profile | Memory | Slices per GPU |
|---------|--------|----------------|
| `1g.5gb` | 5GB | 7 |
| `1g.10gb` | 10GB | 4 |
| `2g.20gb` | 20GB | 3 |
| `3g.40gb` | 40GB | 2 |
| `4g.40gb` | 40GB | 1 |

## Components
- **GPU Operator** (`gpu-operator/values.yaml`): MIG strategy `mixed`, custom MIG presets in `custom-mig-parted-config` ConfigMap. Tolerates `gpu-pool` and `nvidia.com/gpu` taints.
- **MIG presets** (`custom-mig-parted-config`): A100 40GB geometries including `all-1g.5gb`, `all-1g.10gb`, `all-2g.20gb`, `both-mig-40gb-small`, etc.

## Scheduling examples
- MIG slice (gpu1):
  ```yaml
  resources:
    limits:
      nvidia.com/mig-1g.10gb: 1
  nodeSelector:
    gpu-pool: mig
  ```
- Full GPU (gpu2-4):
  ```yaml
  resources:
    limits:
      nvidia.com/gpu: 1
  nodeSelector:
    gpu-pool: full
  tolerations:
    - key: gpu-pool
      value: full
      effect: NoSchedule
      operator: Equal
  ```
- Ready-to-apply manifests: see `examples/` in this folder.

## Apply / update
- GitOps via Fleet. Push changes to apply, or trigger manually: `kubectl -n fleet-system rollout restart deployment/fleet-agent`.

## Verify
```bash
kubectl -n gpu-operator get pods
kubectl get nodes -l nvidia.com/gpu.present=true -o custom-columns='NAME:.metadata.name,MIG_CONFIG:.metadata.labels.nvidia\.com/mig\.config,MIG_STATE:.metadata.labels.nvidia\.com/mig\.config\.state'
kubectl get nodes -o custom-columns='NAME:.metadata.name,GPU:.status.allocatable.nvidia\.com/gpu,MIG-1g\.10gb:.status.allocatable.nvidia\.com/mig-1g\.10gb'
```

## MIG mode changes
MIG mode changes on passthrough GPUs (e.g., Harvester VMs) require a **node reboot**. The MIG Manager will set the mode, but the change only takes effect after reboot.

To change MIG config:
```bash
kubectl label node <node> nvidia.com/mig.config=<profile> --overwrite
# If switching MIG on/off, reboot the node
```

## Troubleshooting
- **MIG state failed**: Check MIG manager logs. For passthrough GPUs, MIG mode changes require node reboot.
- **Full GPU workloads pending**: Confirm they target `gpu-pool=full` and tolerate the `gpu-pool=full:NoSchedule` taint.
- **Device plugin CrashLoopBackOff**: Usually means MIG mode is pending - node needs reboot.
