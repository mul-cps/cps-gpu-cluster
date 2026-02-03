# GPU Operator + Dynamic MIG (NOS)

Fleet-managed GPU Operator configuration for the A100 cluster (4 nodes, 2× A100 40GB each) with dynamic MIG on gpu1–gpu3 and full GPUs on gpu4.

## Layout
- **gpu1–gpu3**: `gpu-pool=mig-dynamic`, `nos.nebuly.com/gpu-partitioning=mig`, `nvidia.com/mig.config=all-enabled`, `nvidia.com/mig.strategy=mixed`. MIG mode stays on; NOS drives MIG partitioning using presets in `custom-mig-config.yaml`.
- **gpu4**: `gpu-pool=full`, `nvidia.com/mig.config=all-disabled`, `nvidia.com/mig.strategy=single`, taint `gpu-pool=full:NoSchedule`. No MIG; full GPUs only.
- Labels/taints applied by the Helm hook `node-labeler.yaml` after GPU Operator install/upgrade.

## Components
- **GPU Operator** (`values.yaml`): MIG strategy `mixed`, time-slicing disabled, custom MIG presets in `custom-mig-config.yaml` (A100 40GB geometries). MIG Manager enabled with default `all-disabled` (nodes are explicitly labeled above).
- **NOS bundle** (`../nos`): vendored Helm chart (0.1.2) with MIG agent enabled on `nos.nebuly.com/gpu-partitioning=mig` nodes; depends on GPU Operator bundle.
- **MIG presets** (`custom-mig-config.yaml`): covers A100 40GB geometries (`1g.5gb`, `2g.10gb`, `3g.20gb`, `4g.20gb`, `7g.40gb`). Names NOS can set include `a100-1g.5gb-7`, `a100-1g.5gbx5-2g.10gbx1`, `a100-1g.5gbx3-2g.10gbx2`, `a100-1g.5gbx1-2g.10gbx3`, `a100-2g.10gbx2-3g.20gbx1`, `a100-1g.5gbx3-4g.20gbx1`, `a100-7g.40gbx1`, etc.

## Scheduling examples
- MIG slice (dynamic nodes):
  ```yaml
  resources:
    limits:
      nvidia.com/mig-1g.5gb: 1  # or nvidia.com/mig-2g.10gb
  nodeSelector:
    gpu-pool: mig-dynamic
  ```
- Full GPU (gpu4 only):
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
kubectl -n gpu-operator get pods -l app=gpu-operator
kubectl -n nos get pods
kubectl describe node k3s-wk-gpu1 | grep -i mig -A2
kubectl get nodes -o json | jq '.items[] | {name: .metadata.name, alloc: .status.allocatable | with_entries(select(.key|test("nvidia")))}'
```

## MIG mode prerequisite
Enable MIG mode once on gpu1–gpu3 (both GPUs per node) if not already:
```bash
sudo nvidia-smi -i <gpu-index> -mig 1
# reboot if required by the platform
```
NOS will then create/delete MIG instances according to pending workloads within the allowed geometries.

## Troubleshooting
- MIG resources missing: check `nos` MIG agent logs and ensure node labels/taints match above; verify MIG mode is enabled on the node.
- Full GPU workloads pending: confirm they target `gpu-pool=full` and tolerate the taint; ensure GPU Operator device plugin is running on gpu4.
- Unexpected repartitions: check `nvidia.com/mig.config` label on MIG nodes and `custom-mig-config.yaml` presets.
