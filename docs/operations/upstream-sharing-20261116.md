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
A new private configuration/custody/home archive and temporary-volume archive
are being retained under `/home/bjoern/artifacts/cps-upstream-sharing-20261116/`
on the workstation (mode 0600, credentials intentionally excluded from Git).

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

Standard drain uses PDBs, no force, no eviction bypass, and no local-data deletion
flag. A drain timeout is reconciled from actual remaining Pods, not counted as
successful drain by itself. All non-DaemonSet live Pods must be gone before SUC
can launch the release operation. Prerequisite Ubuntu package updates run under
host systemd in `cps-gpu2-ubuntu-prerequisites.service` with a retained log.

## Compatibility: published claims versus measured acceptance

| Component | Published evidence | Measured target acceptance |
| --- | --- | --- |
| Ubuntu 24.04 → 26.04.1 | Canonical enables this upgrade and recommends `do-release-upgrade` | Direct GPU2 pilot, pending |
| Rancher 2.13.3 / K3s 1.34 | Matrix supports K3s 1.34; its explicit Ubuntu provisioning rows list 22.04/24.04, not 26.04 | Current 24.04 cluster operates; 26.04 worker compatibility pending |
| Longhorn 1.9.2 | Release-tested OS list includes Ubuntu 24.04; tested K8s versions listed are 1.31–1.33 | Current K3s 1.34 storage observed; Ubuntu 26.04/kernel, reads/writes and restore still require pilot evidence |
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
The driver and OS images are published but have not yet run as qualified GPU2
artifacts.

Local verification: 17 pytest tests and 4 subtests pass. The review found a
lost-reply status gap; the reproducer failed first, then the fix passed. Lost
systemd replies and missing/failed same-boot units now become `unknown`, retain
operation identity, and prohibit replay. Released Fractioning, KAI and GPU
Operator charts render successfully; the Fractioning CR validates against its
released CRD, GPU2 selection is narrow, HAMi is disabled in the KAI overlay,
stock Binder is selected, and operand/NFD update strategies are OnDelete. The
installed SUC CRD accepted the candidate Plan in strict server dry-run.

No OS acceptance, R620 hardware enforcement, workspace cutover, peer promotion,
eight-GPU acceptance, or custom-runtime retirement is claimed by these checks.
