# GPU2 upstream sharing pilot — 2026-11-16

Implementation worktree: branch `work/upstream-gpu-sharing-20261116`, based on
Fleet's deployed revision `281c8134cfac2302966aa3652a81cd398dfd565a`. The original
shared checkout was preserved. Runtime candidates and the OS integration are in
[the preparation package](../../platform-staging/gpu/upstream-sharing/README.md).

The user explicitly directed testing on **real GPU2**, without a clone or a fresh
test VM, relying on the existing backup. This supersedes the original clone
rehearsal gate. No clone was created. Recovery remains backup/repair, not an
Ubuntu release downgrade.

## Observed baseline and preparation

The [inventory snapshot](evidence/upstream-sharing-20261116/inventory.json) records
seven Ready nodes on K3s `v1.34.9+k3s1`, containerd `2.2.5-k3s2`, kernel
`6.8.0-149-generic`; GPU1/3/4 advertise two GPUs each, GPU2 zero. Existing CUDA
validator logs on all three peers report vector-addition success.

Installed components: Rancher 2.13.3, Longhorn 1.9.2, SUC 0.17.0, GPU Operator
25.10.0, KAI 0.18.1 with a custom Binder and explicitly enabled HAMi plugin.
There were no SUC Plans before this work. The management and storage versions
have not been upgraded.

Proxmox SSH works using the user's `~/.ssh/id_ed25519`; the VM102 serial terminal
can be opened through `qm terminal`. GPU2 is VM102, with 500 GiB OS and 1000 GiB
scratch virtual disks. Both disk locations must survive the in-place upgrade.
Production ZFS was 95.56% occupied, with approximately 259 GiB available; this is
why a production clone is prohibited.

Existing full recovery archive:
`NvmeZFSstorage:backup/vzdump-qemu-102-2026_02_01-01_03_53.vma.zst`, 379940290698
bytes. Proxmox successfully extracted its VM configuration; its original backup
log records successful completion. It contains both disks and is **old**. No full
restore or full archive integrity scan has been claimed. Preserve current user
files/configuration and never restore February Longhorn replicas as authoritative.
The user subsequently canceled the additional configuration/custody/home backup and instructed proceeding with the existing VM backup. Its interrupted workstation file is marked `INCOMPLETE` and is not a valid recovery archive. The small infrastructure temporary-volume archive and original maintenance manifests remain under `/home/bjoern/artifacts/cps-upstream-sharing-20261116/` (mode 0600, credentials excluded from Git).

Maintenance started on GPU2 only: it was cordoned, kured's standard manual lock
was acquired, and Longhorn scheduling on GPU2 was disabled. Longhorn replica
evacuation moved most replicas. For storage capacity, two unreferenced image IDs
and one obsolete notebook image were removed from GPU4's cache; the first CRI
removals timed out but space reclamation was observed, so they were not blindly
repeated. GPU4's previously disabled root disk was enabled for Longhorn with its
existing reserved capacity, overprovisioning and free-space thresholds intact.
No capacity threshold was loosened. Subsequent healthy-volume state is required
before the OS release operation.

Infrastructure emptyDir contents were archived. Relevant deployments were
restarted gracefully to move their services off the cordoned node. Loki's
hostname selector was moved from GPU2 to GPU1 so its retained Longhorn volume
could attach there; its Pod subsequently reached 2/2 Ready. The node agent was
scaled to zero after checking that all 44 enrollments had published cleanup or
abort records, every published cleanup was confirmed, and no CUDA compute
process was reported on GPU2. Custody records were retained unchanged.

The completed standard drain used PDBs, no force, no eviction bypass, and no local-data deletion flag. The user later authorized force-removing any remaining stuck GPU2 Pods; none were stuck when checked, so no force deletion was needed. A drain timeout is reconciled from actual remaining Pods, not counted as
successful drain by itself. All non-DaemonSet live Pods must be gone before SUC
can launch the release operation. Prerequisite Ubuntu package updates run under
host systemd in `cps-gpu2-ubuntu-prerequisites.service` with a retained log.

## Compatibility: published claims versus measured acceptance

| Component | Published evidence | Measured target acceptance |
| --- | --- | --- |
| Ubuntu 24.04 → 26.04.1 | Canonical enables this upgrade and recommends `do-release-upgrade` | GPU2 booted 26.04.1 / 7.0.0-43; clean package audit |
| Rancher 2.13.3 / K3s 1.34 | Matrix supports K3s 1.34; its explicit Ubuntu provisioning rows list 22.04/24.04, not 26.04 | 26.04 worker Ready, Rancher Ready/Connected; management versions unchanged |
| Longhorn 1.9.2 | Release-tested OS list includes Ubuntu 24.04; tested K8s versions listed are 1.31–1.33 | GPU2 nonroot Longhorn read/write passed; restore not tested |
| NVIDIA GPU Operator | Current platform matrix includes Ubuntu 26.04, K3s 1.33–1.37 and containerd 2.0–2.3 | Exact 26.7.1/R620/selected kernel combination pending |
| R620.70.06 Ubuntu 26.04 driver | Official pinning and driver/firmware/NVML/MPS packages available | Candidate image package versions verified; kernel module build and GPU execution pending |
| Fractioning 0.1.9 / KAI 0.18.1 | Released charts fetched and locally rendered; matching CRD/watch checked | NRI, driver enforcement, lifecycle, CPS/CIT acceptance pending |

Sources checked during this run:

- [Canonical upgrade announcement](https://lists.ubuntu.com/archives/ubuntu-announce/2026-September/000328.html)
- [Canonical server release upgrades](https://ubuntu.com/server/docs/how-to/software/upgrade-your-release/)
- [Rancher 2.13.3 matrix](https://www.suse.com/suse-rancher/support-matrix/all-supported-versions/rancher-v2-13-3/)
- [Longhorn 1.9.2 release-tested systems](https://longhorn.io/docs/archives/1.9.2/best-practices/)
- [GPU Operator platform matrix](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/platform-support.html)
- [Upstream driver-container recipe](https://github.com/NVIDIA/gpu-driver-container/tree/d0ff0f87636185423a45a1d80093a600fe5a5492/ubuntu26.04)
- [Fractioning v0.1.9](https://github.com/kai-scheduler/gpu-fractioning/tree/v0.1.9)
- [KAI sharing integration](https://github.com/kai-scheduler/KAI-Scheduler/blob/v0.18.1/docs/gpu-sharing/README.md)
- [containerd 2.2.5 NRI validator](https://github.com/containerd/containerd/blob/v2.2.5/docs/NRI.md)
- [K3s containerd template configuration](https://docs.k3s.io/advanced#configuring-containerd)
- [NVIDIA accounting modes and managed-memory limitations](https://docs.nvidia.com/deploy/mps/latest/mpsv3-memory-partitioning.html)
- [kured maintenance lock](https://kured.dev/docs/operation/)

## Built artifacts and source verification

Unmodified NVIDIA driver-container source commit:
`d0ff0f87636185423a45a1d80093a600fe5a5492`. Base image:
`docker.io/library/ubuntu@sha256:157dc3d6e4a3e4f2c68d12df9df9ed6e808b59af6d4c3757b432b4f519916725`.
BuildKit built the Ubuntu 26.04 driver using DRIVER_VERSION=620.70.06,
DRIVER_BRANCH=620, TARGETARCH=amd64 and upstream GOLANG_VERSION=1.27.3.
Podman attempts failed on its OCI SHELL handling and unmatched optional COPY;
those builder failures did not cause a source patch.

Published image:
`ghcr.io/mul-cps/cps-nvidia-driver@sha256:0fcbf7340155f8d6868e30b1b0fbf09b601d093a9316621902d5ac09ad7874a1`.
The remote registry digest was re-read and matched the OCI build metadata.
Driver pinning, firmware, kernel common, headless userspace, libnvidia-compute
and persistenced all report `620.70.06-1ubuntu1` inside the final image.
This verifies packaging, **not** the target kernel or hardware.

Published OS payload:
`ghcr.io/mul-cps/cps-ubuntu-release-upgrade@sha256:5030556ecf8cd38fc9acc4676316bd0a3217d1ab10930b75b9dba7106e8f4004`.
Ubuntu 24.04 base:
`docker.io/library/ubuntu@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8`.
The final container's payload, preflight and entrypoint hashes were inspected.
The OS image ran the successful host upgrade on GPU2. R620 driver loading and
hardware/workspace qualification are tracked below.

Local verification: 17 pytest tests and 4 subtests pass. The review found a
lost-reply status gap; the reproducer failed first, then the fix passed. Lost
systemd replies and missing/failed same-boot units now become `unknown`, retain
operation identity, and prohibit replay. Released Fractioning, KAI and GPU
Operator charts render successfully; the Fractioning CR validates against its
released CRD, GPU2 selection is narrow, HAMi is disabled in the KAI overlay,
stock Binder is selected, and operand/NFD update strategies are OnDelete. The
installed SUC CRD accepted the candidate Plan in strict server dry-run.

The local source checks do not qualify R620 hardware enforcement, workspace
cutover, peer promotion, eight-GPU acceptance or custom-runtime retirement.

## Prerequisite reboot and deployed OS Plan

Ubuntu prerequisites completed successfully under host systemd, resulting in Ubuntu 24.04.5 with a clean package audit. AppArmor requested a reboot. The prerequisite reboot reached systemd reboot target after a CRI scope stop timeout; the warm reboot then failed to return SSH/QGA. After reconciling serial and QMP state, VM102 was stopped and cold-started. The other three workers stayed Ready; no release upgrade had yet run at that point.

Fleet GitRepo `fleet-local/upstream-gpu2-os-pilot` is pinned to source commit `b71839011cadf52d5f1646ade7381b1298e596ee`, watching only the OS bundle path. It reconciled Ready 1/1 and installed `cattle-system/cps-ubuntu-gpu2-ubuntu-20261116`. The required nomination label was absent, so no worker upgrade Job ran. `Complete=True` with zero selected nodes is not OS acceptance. The private image pull secret was supplied from the existing registry credential, and the final OS image was pulled and its source hashes verified in a nonprivileged GPU2 Pod.

## Release operation result before post-upgrade boot

The SUC Job completed after submitting the host service; Canonical subsequently completed successfully with `ExecMainStatus=0`. Durable state became `reboot-required` at 2026-11-16 11:14 UTC. Ubuntu 26.04.1 packages and `/boot/vmlinuz-7.0.0-43-generic` plus its initramfs were present, and `dpkg --audit` was clean. The legacy GPU2 R615 driver and validator DaemonSets were scoped to an absent legacy-enable label after confirming no CUDA compute processes; both reached desired/current zero and their Pods exited gracefully. No force deletion or module reset was used. The guest was powered down cleanly for a cold start, avoiding the reproduced warm-reboot issue. OS acceptance awaits the new-kernel boot and reconciliation.

The current source moves the OS bundle under `platform-staging/gpu/upstream-sharing/os-plan` to prevent duplicate bundle ownership if the original broad cluster GitRepo is advanced. The already-deployed OS GitRepo remains pinned to historical commit `b7183901`, where its original path still exists, so its active Plan does not change during the host operation. A selected-worker R620 NVIDIADriver candidate was added with a digest pin, `default: false`, driver auto-upgrade/drain/force disabled and stock driver manager v0.12.1. It validates against the released 26.7.1 CRD. The installed 25.10 CRD lacks its safety-policy field; upgrade the controller/CRD before applying rather than dropping that field.

## Post-upgrade boot and upstream driver ownership

GPU2 booted Ubuntu 26.04.1 with kernel `7.0.0-43-generic`; boot identity is
`25b0d1c8-3a45-4623-91bd-3724fd6e5341`. The durable host operation reconciled to
`os-verified`. SSH, K3s, the scratch mount and the package audit passed. A 100 MiB
Longhorn fixture using UID 1000 wrote and read successfully, then its Pod/PVC
were removed. Longhorn 1.9.2 requires an uncordoned node to start its instance
manager; GPU2 was temporarily uncordoned with the separate maintenance taint and
GPU placement fence retained, then cordoned again. This measures compatibility
of this operation; it does not expand published Rancher/Longhorn support claims.

The controller passed through actual GPU Operator 26.3.3 to 26.7.1, with pinned
operand images and OnDelete updates. A nested vendored 25.10 chart initially
shadowed the requested remote chart; its unchanged source was preserved under
`platform-staging/vendor/gpu-operator-v25.10.0`. Actual Helm release and running
controller images were checked after removing that shadow. Peer operand Pod
UIDs and restart counts remained unchanged. Fleet's unrelated bundle deployment
IDs were unchanged when its root Git revision advanced.

The separate R620 NVIDIADriver is digest pinned, non-default and selected only
by `cps.unileoben.ac.at/driver=620.70.06`. Auto-upgrade, forced eviction and drain
are disabled. Its kernel module configuration selects misc accounting. Legacy
GPU2 driver/validator Pods exited before selection; the custom cap writer is
stopped with existing custody retained.

Creating the NVIDIADriver before adding its custom selector label reproduced a
26.7.1 routing event gap: an unowned node's custom selector-label change does
not enqueue NodeLabeling reconciliation. The driver reconciled zero owned
nodes and misleadingly reported Ready. Restarting only the upstream operator
refreshed owner assignment and created the selected GPU2 driver DaemonSet;
no runtime patch was required. Verify nonzero desired Pods, actual loading and
CUDA rather than accepting a zero-node CR's Ready condition. For subsequent
workers, nominate the node before creating/changing the matching driver CR,
or explicitly reconcile and verify owner assignment.

The stock driver manager init exited successfully and the pinned R620 image
compiled and loaded open modules for kernel 7.0.0-43. Both A100-PCIE-40GB cards
report 620.70.06 and 40960 MiB through NVML. `/proc/driver/nvidia/params` confirms
`RmMemacctMode=1`; the driver DaemonSet is 1/1 Ready. GPU2 remains cordoned
with zero advertised GPUs while the toolkit/plugin transition is prepared. Fractioning, KAI cutover and real workspace acceptance
are still pending; no next worker is nominated.
