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

## Current GPU sharing

The GPU device plugin advertises the two physical A100s on each worker.
KAI schedules whole-device workloads and qualified fractional profiles.
GPU Fractioning supplies the NRI device injection and manages the MPS
servers on the workers. The gateway owns tenant profile and quota checks.
Shared profiles use fixed memory limits. Whole-device profiles request the
physical GPU count directly.

The separate, hand-maintained MPS DaemonSet has been retired. Its
[manifest is archived](../../../../../../docs/operations/archive/standalone-mps/mps-control-daemon-standalone.yaml).
Jobs with explicit `/run/nvidia/mps` mounts are historical examples.
Use a current gateway profile for tenant submissions.

## Components
- **GPU Operator** (`gpu-operator/values.yaml`): `mig`/`migManager`
  settings are vestigial from the retired MIG setup. The device plugin
  keeps `plain` as the active default. The `mig-mixed` and
  `mps-sharing` settings document earlier configurations.
  `ClusterPolicy` manages the driver, toolkit, device plugin, DCGM
  exporter and GFD.
- **GPU Fractioning** runs the supported `mpsd` and `fractiond`
  DaemonSets. They use the `/run/nvidia-mps` runtime tree.
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
kubectl -n gpu-fractioning get pods -o wide
kubectl get clusterpolicy cluster-policy
kubectl get pods -n kai-resource-reservation
```
Expect four Ready, schedulable GPU workers with two allocatable
physical GPUs each. The Fractioning DaemonSets should each have one Ready
Pod per worker, and GPU Operator should report `ClusterPolicy` Ready.

## Troubleshooting
See `docs/troubleshooting.md`'s GPU Issues section, in particular:
- "ClusterPolicy stuck NotReady / MIG config stuck in 'failed'" — transient
  mig-manager reconcile issue, fixed by deleting the stuck pod.
- "MIG mode toggle needs a REAL reset — in-guest reboot is not enough on
  passthrough GPUs" — why MIG mode changes need a Proxmox-level VM
  stop/start, and why that cost is part of why MIG was retired here.

## Pending: v25.10.0 -> v26.3.3 bump (not yet done, scoped below)

`gpu-operator/` (this directory's chart subdirectory) is a **vendored
local copy** of the upstream chart (full `Chart.yaml`/`values.yaml`/
`templates/`/`crds/` tree checked into Git), not a plain remote-repo
reference. Fleet resolves the chart from this local directory whenever
`helm.chart` in `fleet.yaml` matches a subdirectory name here — the
`version:` field in `fleet.yaml` has **no effect** in this setup; bumping
it alone is a silent no-op (confirmed empirically 2026-07-06: two Fleet
reconciles plus a forced `gitrepo` resync all redeployed the vendored
`v25.10.0` chart even with `fleet.yaml`'s `version:` set to `v26.3.3`,
which is why both that field and `bootstrap-cluster/ansible/group_vars/all.yml`'s
`gpu_operator_version` were reverted to `v25.10.0` to match live state).

To actually land v26.3.3:
1. `helm pull nvidia/gpu-operator --version v26.3.3 --untar` and replace
   this `gpu-operator/` subdirectory wholesale with the pulled contents.
2. Re-apply this cluster's only local customization on top — confirmed via
   `diff -r` against a clean `v25.10.0` pull that the *only* delta from
   stock upstream is two `gpu-pool:NoSchedule` toleration blocks added to
   `values.yaml` (one in the daemonsets' common tolerations, one further
   down for a second component) — port those same two blocks into the new
   `values.yaml`, don't hand-merge the rest of the file.
3. Check the CRD diff between the two chart versions
   (`nvidia.com_clusterpolicies.yaml`, `nvidia.com_nvidiadrivers.yaml`)
   for breaking schema changes before applying, since this is a 3-minor
   jump (25.10 -> 26.3) treated as its own risk-tested step per
   `docs/upgrade-path-2026-k3s-1.34-dra.md`.
4. Verify per the same pattern used for the K3s 1.34 upgrade: ClusterPolicy
   `ready`, all 4 nodes report correct `nvidia.com/gpu` allocatable, a real
   GPU pod runs via both plain scheduling and the KAI scheduler.
