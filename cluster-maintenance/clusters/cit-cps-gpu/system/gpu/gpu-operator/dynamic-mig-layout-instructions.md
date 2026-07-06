# Dynamic MIG layout — historical note (superseded)

This document used to describe a plan to run dynamic, on-demand MIG
repartitioning across the GPU worker nodes using the nebuly-ai `nos`
project as an autoscaler on top of the NVIDIA GPU Operator's MIG Manager.
That plan was never deployed (the `nos` Fleet bundle carried a
`fleet.yaml.disabled` suffix so Fleet never picked it up) and has since
been abandoned entirely, for two reasons:

1. **A100 can't do automatic, on-the-fly MIG repartitioning.** NVIDIA's
   newer DRA-based `DynamicMIG` feature, which is what would be needed to
   reshape MIG geometry in response to demand without manual
   intervention, explicitly excludes the A100 generation.
2. **MIG mode toggles are disruptive on this hardware.** Flipping the MIG
   *mode* bit (MIG-enabled vs. MIG-disabled) on a GPU requires a real
   device reset (FLR/bus-reset). On this cluster's PCIe passthrough
   (VFIO) setup, that reset only happens on a full VM stop/start at the
   Proxmox host level — an in-guest `systemctl reboot` is not enough,
   since QEMU never releases and reacquires the device. See "MIG mode
   toggle needs a REAL reset — in-guest reboot is not enough on
   passthrough GPUs" in `docs/troubleshooting.md` for the full mechanism
   and the `qm stop`/`qm start` fast fix. That disruption cost is what
   made per-node, demand-driven MIG repartitioning impractical here.

`nos` itself is also unmaintained upstream, independent of these
hardware constraints.

## What replaced it

All 8 A100 GPUs across the 4 GPU worker nodes now run in full/non-MIG
mode permanently (`nvidia.com/mig.config=all-disabled`). GPU sharing for
interactive/student workloads is handled instead by **NVIDIA MPS**,
driven by JupyterHub server profiles together with KAI Scheduler's
`gpu-memory` annotation for memory-fraction-based scheduling. This
requires no MIG geometry changes and no VM-level resets — profiles are
just Kubernetes-level scheduling/annotation config.

For the current profile and tier definitions, see
`cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml`
(`PROFILE_CONFIGS` in its `extraConfig`), which is the live source of
truth going forward.
