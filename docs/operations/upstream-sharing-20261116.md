# GPU2 upstream sharing pilot — 2026-11-16

**Current user policy:** idle users may borrow spare VRAM. Sharing acceptance
protects promised shares under contention; the historical strict idle-cap
verdict below is superseded. See the final policy/competition section.

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

## GPU2 toolkit, CUDA and NRI checks

Fleet source `00855fd7` selects toolkit 1.20.1 and stock device plugin/GFD 0.20.1,
retaining OnDelete. Only GPU2 Pods were enabled/recreated. Both cards advertised
normally and each separately passed CUDA vector-add in a nonroot Pod using two
stock device-plugin allocations. The fixture exited and was removed; logs are
retained in the execution artifacts. The initial toolkit CDI race resolved
when toolkit setup completed; no retry bypass or security change was needed.

GPU2 now uses a K3s `config-v3.toml.tmpl` extending the base template with the
standard NRI/default-validator fragment. After restarting only its K3s agent,
the generated config, NRI socket and containerd plugin status were verified.
A container requiring absent plugin `gpu-fractioning` was rejected by
`00-default-validator` before creation. An ordinary nonroot CPU container using
the NVIDIA runtime started successfully and received SIGTERM, logged its
shutdown handler and exited on normal Pod deletion. No force deletion or
AppArmor relaxation was needed. The negative fixture was also removed.

The released Fractioning chart is rendered as separate CRD/namespace and operand
Fleet bundles. Its default configuration's Helm hook annotations are removed so
Fleet manages the already-scoped CR directly. The two-part GPU2 selector,
fail-open=false, retroactive enforcement and K3s sockets validate against the
released schema. The separate runtime nomination label remains absent until
installation checks complete; no peer is selected.

## Enforcement gate: managed/UVM failure, no promotion

Upstream Fractioning v0.1.9 reached Ready on GPU2 only. MPS reported driver620,
threshold events for both devices and memacct available with mps_only=false;
fractiond registered with containerd and metricsd initialized NVML. Peer GPU
operand Pod UIDs/restart counts remain unchanged. GPU2 remains cordoned with
its maintenance taint and accelerator fence. KAI and gateway cutover have not
been performed.

The 5120 MiB raw-driver probe passed: 1024 MiB allocated/filled/freed, 6144 MiB
returned CUDA_ERROR_OUT_OF_MEMORY (2), and 2048 MiB then allocated/filled/freed.
The same exact candidate failed managed/UVM qualification: a 6144 MiB managed
allocation, GPU prefetch, memset and synchronization all succeeded under a
5120 MiB profile. During the hold, the host reported 6567 MiB physical GPU use;
the capped container reported total5120/used415 MiB and process accounting
reported416 MiB. Thus successful managed use was not merely a large virtual
allocation: host-wide physical use exceeded the profile while per-container
accounting omitted it. NVIDIA's current published limitation still states that
managed memory is tracked in system memory only.

The probe released its allocation/context and exited; its Pods and ConfigMaps
were removed. Source fixtures and sanitized logs plus the measured gate are in
`tests/upstream-sharing/hardware/` and the adjacent evidence directory. No cap
writer, library interception or environment workaround was introduced. The next
required work is the smallest driver-boundary rejection/accounting fix after
considering upstream configuration/released fixes, followed by the same failing
case and complete final-artifact acceptance. GPU3 is not nominated.

## Current policy and verified hard-limit/competition diagnostics

The user explicitly clarified that limits matter for sharing, and a user alone
may use extra memory. This supersedes the earlier strict idle hard-cap criterion.
Do not add a custom driver restriction solely to prohibit idle managed/UVM
borrowing. The observations above remain valid diagnostics, not an automatic
rejection under the revised policy. Full sharing/workspace acceptance remains
required.

Following NVIDIA's diagnostics, the actual leaf cgroup was resolved from the
running container's host CRI PID on GPU2. Soft1024/hard5120 MiB were read back,
explicitly set through nvidia-smi and read back again. Ordinary2048 MiB succeeded
above soft; ordinary6144 MiB returned typed OOM; managed6144 MiB still completed
GPU prefetch/fill/sync with physical6567 MiB and driver-accounted415 MiB.
GPU2 remained cordoned: each test explicitly selected spec.nodeName, with Pod
hostIP, host hostname/PID/cgroup and physical GPU UUID checked together.
The kernel exposes dmem files even with misc forced; they contained no GPU
entries, while the driver module parameter confirmed RmMemacctMode1.

Two containers then competed on the same card. With soft18/hard30 GiB each,
A filled24 GiB. B requested17 GiB; MPS selected A's over-soft cgroup, killed only
the test borrower, logged26209746944 bytes freed and B succeeded. This verifies
the measured ordinary-memory borrowing/reclamation path.

With soft=hard5 GiB each, managed A filled36 GiB (host physical37287 MiB).
B requested/fill4 GiB successfully. A was CPU-memory-cgroup OOM-killed at its
4 GiB host-memory limit; kernel and container status confirm the cause. This
protects the measured peer's progress but is not a GPU hard-limit rejection.
All fixtures were removed and both GPUs returned to1 MiB usage. Preserve this
causal distinction when extending tests: two outcomes do not establish every
profile, ordering, contention pattern or application lifecycle.

The complete readbacks, identity snapshots, probe source, fixture YAML and
MPS/kernel logs are retained under
[evidence/hard-limit-and-contention](evidence/upstream-sharing-20261116/hard-limit-and-contention/current-acceptance-policy.json).

## Final platform checks before workspace cutover

GPU2 passed mixed5/10/20 GiB ordinary-memory probes on both physical cards,
first filling A then B, then B then A with reversed profile order. All12 cases
returned typed CUDA OOM for a request1 GiB above the actual hard limit, then
filled the in-budget allocation. Each card held34030 MiB physical use with all
three profiles active. A5 GiB parent/child case enforced aggregate use even
when children replaced memory-limit environment values with999999 and used a
nonexistent MPS pipe: parent3 GiB +child3 GiB was rejected, child1 GiB succeeded.
Tenant nested-cgroup creation failed with read-only filesystem.

A running CUDA workload survived K3s/containerd restart with the identical Pod
UID, containerID and restartCount0; it continued GPU memset/synchronize calls.
fractiond reconnected after5 seconds and recovered the live container mapping.
GPU2 subsequently completed a clean poweroff/cold-start cycle, newbootID
043e6e01-0e3a-44ab-bca9-f6d42ababe60. R620, toolkit, device plugin and Fractioning
returned healthy automatically. The Longhorn instance manager required the
known temporary fenced uncordon to recover; GPU2 was re-cordoned afterward.
Storage stayed healthy. No host driver packages were present; the pinned
upstream driver container remains the only driver owner.

A controlled15-second SIGSTOP of only fractiond, with an independent host
systemd timer armed to resume it, verified hung/disconnected plugin handling.
The required-plugin GPU Pod was rejected by containerd's default validator
while the plugin was absent; an ordinary CPU Pod succeeded. After plugin
reconnection, the GPU Pod passed its1 GiB /6 GiB typedOOM /2 GiB recovery probe.
All test fixtures were removed. No production workspace acceptance is implied.

The app implementation review is approved through cps-compute8d45f06; source
334 tests and actual CPS/CIT overlay closures333 tests each passed. Immutable
Gateway/CPSHub/CITHub candidates were published and source-verified. These are
candidates pending coordinated live cutover and real workspace acceptance.
