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

## What replaced it: plain device-plugin mode + KAI-native GPU sharing

GPU sharing for interactive/student workloads is handled by **KAI
Scheduler's own `gpu-memory` annotation + automatic reservation-pod
mechanism** (namespace `kai-resource-reservation`), on top of the device
plugin running in **plain mode** (`devicePlugin.config.default: plain` —
no `sharing.mps` block, `nvidia.com/gpu` advertised as the real physical
GPU count). Per-client VRAM enforcement still comes from NVIDIA MPS
(`CUDA_MPS_PINNED_DEVICE_MEM_LIMIT`, set by JupyterHub server profiles),
but the MPS *server* now runs as a standalone always-on DaemonSet
(`mps-control-daemon-standalone.yaml`), decoupled from the device
plugin's sharing config.

**This design superseded an earlier `mps-sharing`-as-default architecture**
(device plugin sharing config with 8 replicas/GPU) after live testing
showed that mode caps every pod at 1 GPU (`failRequestsGreaterThanOne`),
making real multi-GPU/NVLink distributed batch jobs impossible
cluster-wide. Plain mode + KAI-native sharing gives you both: real
`nvidia.com/gpu: 2+` requests for distributed batch jobs, and fractional
`gpu-memory` requests for interactive/student sessions, correctly
arbitrated on the same nodes at the same time (verified live 2026-07-06 —
see `docs/troubleshooting.md`). There is no MIG geometry and no per-node
mode split to manage — profile/tier definitions live in
`cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml`
(`PROFILE_CONFIGS` in its `extraConfig`), which is the current source of
truth for how GPU capacity is sliced up between users.

## Components
- **GPU Operator** (`gpu-operator/values.yaml`): `mig`/`migManager`
  settings are vestigial from the retired MIG setup and left functionally
  as-is for now; see comments in that file. `devicePlugin.config` defines
  three keys (`mig-mixed` historical, `mps-sharing` retained for
  comparison/fallback and as the standalone MPS daemon's own config
  source, `plain` — the active cluster-wide default). `ClusterPolicy` is
  otherwise standard GPU Operator config for driver, toolkit, device
  plugin, DCGM exporter, and GFD on all 4 nodes.
- **`mps-control-daemon-standalone.yaml`**: a hand-maintained DaemonSet
  (not owned by `ClusterPolicy`) that runs the MPS control daemon
  unconditionally on every GPU node, because GPU Operator's own
  MPS-daemon DaemonSet only schedules onto nodes GPU Feature Discovery
  labels `nvidia.com/mps.capable=true` — a label tied to the device
  plugin's sharing config, which is `false` cluster-wide now that the
  default is `plain`. See its header comment and
  `docs/troubleshooting.md` for the full incident.
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
kubectl -n gpu-operator get pods -l app=mps-control-daemon-standalone -o wide
kubectl get pods -n kai-resource-reservation
```
Expect all 4 GPU nodes to show `mig.config=all-disabled`, `mig.config.state=success`,
and `nvidia.com/gpu=2` allocatable (real physical count, not MPS replicas).
Expect a `mps-control-daemon-standalone` pod `Running` on all 4 nodes
regardless of `nvidia.com/mps.capable` (which will read `false` — that's
expected under plain mode, see above). `kai-resource-reservation` pods
appear only while a `gpu-memory` request is actively holding a physical
GPU on that node.

## Troubleshooting
See `docs/troubleshooting.md`'s GPU Issues section, in particular:
- "ClusterPolicy stuck NotReady / MIG config stuck in 'failed'" — transient
  mig-manager reconcile issue, fixed by deleting the stuck pod.
- "MIG mode toggle needs a REAL reset — in-guest reboot is not enough on
  passthrough GPUs" — why MIG mode changes need a Proxmox-level VM
  stop/start, and why that cost is part of why MIG was retired here.
