# GPU Operator Configuration

Fleet-managed GPU Operator configuration for the A100 cluster (4 nodes, 2× A100 PCIE 40GB each).

## Current layout: MIG retired, all nodes full-mode

All 4 GPU worker nodes (`k3s-wk-gpu1..4`) now run permanently in
full/non-MIG mode: `nvidia.com/mig.config=all-disabled`, `mig.config.state=success`,
`nvidia.com/gpu=2` allocatable per node (8 A100s total across the cluster).

MIG-based partitioning (this README used to describe gpu1 as a
MIG-enabled node and gpu2–gpu4 as full-GPU-only) has been dropped
entirely. It was abandoned because:

- NVIDIA's A100 generation is excluded from the newer DRA `DynamicMIG`
  feature, so there's no supported way to repartition MIG geometry
  on-the-fly in response to demand.
- Flipping MIG mode on/off requires a real device reset, which on this
  cluster's PCIe passthrough (VFIO) hardware means a full Proxmox-level
  VM stop/start, not just an in-guest reboot — see "MIG mode toggle
  needs a REAL reset" in `docs/troubleshooting.md` for the mechanism.

See `dynamic-mig-layout-instructions.md` in this directory for the full
history of the abandoned dynamic-MIG plan (which used to depend on the
now-deleted `nos` bundle).

## What replaced it: MPS-based sharing

GPU sharing for interactive/student workloads is now handled by
**NVIDIA MPS**, driven by JupyterHub server profiles together with KAI
Scheduler's `gpu-memory` annotation for memory-fraction-based
scheduling. There is no MIG geometry to manage anymore — profile/tier
definitions live in
`cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml`
(`PROFILE_CONFIGS` in its `extraConfig`), which is the current source of
truth for how GPU capacity is sliced up between users.

## Components
- **GPU Operator** (`gpu-operator/values.yaml`): `mig`/`migManager`/device-plugin
  MIG settings are vestigial from the retired MIG setup and left
  functionally as-is for now; see comments in that file. `ClusterPolicy`
  is otherwise standard GPU Operator config for driver, toolkit, device
  plugin, DCGM exporter, and GFD on all 4 nodes.
- **`node-labeler.yaml`**: a Helm post-install/upgrade hook Job that
  applies `gpu-pool=mig`/`gpu-pool=full` labels and taints per the old
  static MIG split. This is historical/superseded — see the header
  comment in that file. The `gpu-pool` label key may still be referenced
  by other scheduling manifests even though the MIG/full distinction it
  encodes is no longer an active partitioning scheme.

## Verify
```bash
kubectl -n gpu-operator get pods
kubectl get nodes -l nvidia.com/gpu.present=true -o custom-columns='NAME:.metadata.name,MIG_CONFIG:.metadata.labels.nvidia\.com/mig\.config,MIG_STATE:.metadata.labels.nvidia\.com/mig\.config\.state'
kubectl get nodes -o custom-columns='NAME:.metadata.name,GPU:.status.allocatable.nvidia\.com/gpu'
```
Expect all 4 GPU nodes to show `mig.config=all-disabled`, `mig.config.state=success`,
and `nvidia.com/gpu=2` allocatable.

## Troubleshooting
See `docs/troubleshooting.md`'s GPU Issues section, in particular:
- "ClusterPolicy stuck NotReady / MIG config stuck in 'failed'" — transient
  mig-manager reconcile issue, fixed by deleting the stuck pod.
- "MIG mode toggle needs a REAL reset — in-guest reboot is not enough on
  passthrough GPUs" — why MIG mode changes need a Proxmox-level VM
  stop/start, and why that cost is part of why MIG was retired here.
