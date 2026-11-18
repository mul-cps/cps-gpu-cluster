# GPU2 upstream sharing pilot — 2026-11-16

**2026-11-18 latest state:** six GPUs remain normally qualified; GPU4 remains GPU-fenced. Dedicated-personal compatibility is now enabled at the two backends (Gateway444/Hub396, matching9037745a); the dedicated UI remains disabled while qualification finishes. Actual one-/two-device CUDA and CPU reset pass with retained files and requested storage mounts. A documented old NFS-Ganesha/new-kernel compatibility issue blocked a new home; the same home and full native GPU workflow passed after the supported client directory-delegation flag was disabled. That runtime setting is now N on all four workers, with no reboot or GPU/runtime change. The standard modprobe option is now persisted and verified on all four workers; selected-kernel initramfs regeneration/coldboot and the new home's second replica remain open. Canonical409 enforcement works; the Hub-only native progress-message fix is deployed and healthy, with exact database/configuration/credential/CIT preservation. Its fresh live denial test remains pending: API ordering was corrected without changing membership, then native Ready/public200 passed before the test incorrectly attempted to recreate an existing retained witness. Normal cleanup passed; the fixed fixture will read the retained file. GPU2/3/4 peer home read/write/fsync and both-card64MiB CUDA checks now pass with normal probe cleanup. The initial driver-container command failed before allocation because Python is absent there; an explicit reviewed resume used existing host Python and official R620 libcuda, without dependency installation or repeating the GPU2 storage write. All owned test roles/tokens/Pods/reservations are now clean. See the [current partial acceptance receipt](evidence/upstream-sharing-20261116/personal-gpu-native-partial-and-nfs-20261118.json). The timestamped sections below retain prior states and failure witnesses.

**2026-11-18 current state (10:14 UTC):** GPU2, GPU3 and GPU1 have scoped worker acceptance,
with six qualified GPUs back in normal service. GPU1 passed hardware, coldboot/NRI,
stock KAI and final Source image `d52d0a7a…`: all six CPS/CIT GPU profiles, both
CPU/member lifecycles, and both strict first-active backend200 Stop-response-loss
cases. The Source cleanup-race fix is deployed on both services. QA memberships,
credentials and five grants are closed; the then-normal Hubs were restored
(CPS387/CIT325), six temporary objects were deleted and temporary node rights revoked.
See the [GPU1 worker receipt](evidence/upstream-sharing-20261116/gpu1-worker-acceptance-20261118.json),
[final GPU tests](evidence/upstream-sharing-20261116/gpu1-final-source-gpu-20261118/README.md),
[lifecycle tests](evidence/upstream-sharing-20261116/gpu1-final-source-lifecycle-20261118/README.md)
and [current status](evidence/upstream-sharing-20261116/gpu2-current-status.json).
GPU4 now boots Ubuntu26.04.1/kernel7.0.0-43; its sole SUC operation is reconciled
as OS-verified and nomination removed. Matched R620 and upstream runtime are
installed on both cards. Warm enforcement/contention, runtime restart continuity,
coldboot/NRI failure and recovery, CPU/AppArmor, Longhorn/fast-scratch read/write
and the fifteen-role stock-KAI qualification have passed with confirmed cleanup.
Its final boot is `9f770278-3655-42da-b088-a227f5eb45dc`. It remains cordoned,
maintenance-tainted, Longhorn-scheduling-disabled and unqualified until final
CPS/CIT Source lifecycle acceptance and restoration of paused services.
Original local data inventories, mounts/PVC/PV identities and scoped recovery files
are preserved. One upstream GPU Operator controller relist reconciled its stale
node-owner label; peer GPU runtimes did not restart. See
[GPU4 OS/runtime stage](evidence/upstream-sharing-20261116/gpu4-os-runtime-stage-20261118.json)
and the [earlier drain/OS submission](evidence/upstream-sharing-20261116/gpu4-pre-os-progress-20261118.json).
The [post-coldboot stage receipt](evidence/upstream-sharing-20261116/gpu4-postcoldboot-stage-20261118.json)
binds the five verified hardware/storage/KAI manifests; this is not worker promotion.

Both Sources currently run `7e7726d8…` (source `126e0e80…`, generation126):
controlled Start errors, effective membership expiry handling, current-request
XSRF headers, readable Notice widths and content-versioned assets. The user's
`shared-gpu-lab` is running on qualified GPU1; preserve its Pod and allocation.
Member discovery uses JupyterHub's native self/group Shares API through a Home
template extension, not the unpublished custom Source access API/Overview.
The first Home release mounted the template but did not activate it because
the reviewed Pod templates retain immutable runtime Secrets. The corrected
standard `config.d` extraFile is now actually loaded by both Hubs (currently CPS393/CIT328),
with unchanged existing crypto, stable access/workspace-account records and
the original running notebook Pod/container. The user confirmed the native Home
shared list appeared. Responsive cards are now deployed; a genuine Open click
from the styled cards remains unverified.
See [native Home rollout](evidence/upstream-sharing-20261116/native-hub-home-20261118/README.md).
The empty Notice fallback is deployed on both Sources as “No additional notices.”
CPS also has the compact native personal spawn form and CPU reset image `b045f8a3…`.
Its normal configuration now defaults Network storage, Project share and Scratch1
on where the existing role permits access; current-form unchecks remain authoritative.
The upstream CPU pre-puller now pins the actual `efc3b485…` image and completed
on all three eligible workers. The ordinary Hub configuration is restored.
Disposable personal CPU acceptance now passes on normal Hub 393: public notebook
HTTP 200, actual UID 1000, no GPU devices, NVIDIA_VISIBLE_DEVICES=void, normal
Stop 204 and confirmed user/Pod/PVC/Secret removal with all 58 grants and the real
shared notebook unchanged. The150second readiness gate stayed unchanged. Earlier
cases retain the 149-second cold-pull deadline failure and empty SSH-pod CA-store
probe failure; the final public probe used Root-local strict TLS, no proxy and no
redirects. Transient fresh-volume NFS/subPath mount retries remain recorded. The user explicitly requested retaining dedicated GPU choices
during migration; a same-reservation compatibility path is being implemented before
removing the temporary UI/backend block.

The obsolete `accelerator=r615-canary-maintenance` key was removed from all four
workers by UID/resourceVersion/full-label/spec guarded patches. The three legacy
MPS/HAMI DaemonSets stayed at zero and the user's running notebook was preserved.
GPU1/2/3 retain qualification; GPU4's maintenance and storage fences are unchanged.
This deprecates a label, not the historical runtime/custody evidence.

GPU4 subsequently passed actual CPS 5/10/20 GiB Source workloads on both cards,
including typed CUDA OOM, Torch CPU reference, SDK/files,45-second progress,
stored metrics, normal Stop/charge return and confirmed idempotent Stop. Its
temporary QA window and credential are closed, temporary objects/Node permission
removed, and five QA grants closed while all other 53 rows stayed exact. All four
CPS test memberships were removed through supported APIs; the remaining empty
QA group Share was revoked through one targeted native Hub PATCH. Final members,
group users and Shares are zero, the barrier is clear and the lease inactive/null.
The fresh cleanup credential is revoked; files and native accounts are retained. CIT,
CPU/member and strict Stop-loss final gates remain open; GPU4 is cordoned and
unqualified. See the [CPS partial receipt](evidence/upstream-sharing-20261116/gpu4-cps-source-partial-20261118.json).
Gateway node observation now permits exact GET of GPU4 as well as GPU1/2/3;
the actual service-account token still receives403 for LIST and an unlisted node.
Controller cutover, all-eight-GPU rollout, startup bursts and full platform gates remain open.

**2026-11-17 historical checkpoint:** GPU2 passed the scoped fixed-profile worker
acceptance and is restored to shared placement and Longhorn scheduling. Its old
OS nomination is cleared. See the [worker receipt](evidence/upstream-sharing-20261116/gpu2-worker-acceptance-20261117.json),
[CIT Source lifecycle evidence](evidence/upstream-sharing-20261116/source-provider-qualification/cit-20261117/README.md)
and [final-artifact bypass checks](evidence/upstream-sharing-20261116/child-aggregation-final-20261117/README.md).
Real CIT nonadministrator IdP/browser/two-person access remains open; these
tests used a genuinely authenticated administrator and workload-owned sessions.
GPU3/1/4 are unchanged. GPU3 must satisfy the replica and activator/PDB
prerequisites before nomination. The narrative below retains historical stages.

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
| NVIDIA GPU Operator | Current platform matrix includes Ubuntu 26.04, K3s 1.33–1.37 and containerd 2.0–2.3 | Selected GPU2 operands Ready with 26.7.1/R620/kernel7.0.0-43; global ClusterPolicy remains notReady during the deliberate OnDelete rollout of peer operands |
| R620.70.06 Ubuntu 26.04 driver | Official pinning and driver/firmware/NVML/MPS packages available | Derived c3b loaded on both cards; final-artifact CUDA, contention, bypass and cleanup passed; managed memory explicitly rejected, MIG disabled |
| Fractioning 0.1.9 / KAI 0.18.1 | Released charts fetched and locally rendered; matching CRD/watch checked | Stock placement, mandatory-plugin failures, limits, CPS/CIT Source-controller lifecycle and tested reply-loss reconciliation passed; real CIT human access remains open |

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

## Stock scheduler and application cutover (17:45 UTC)

The live KAI 0.18.1 release now owns the historical hook-created `kai-config`. Its Helm-rendered Config was applied under Fleet ownership after reconciling the existing object metadata. The global mode is `NvFractions`; the stock `binder:v0.18.1` is Ready with CDI enabled and the HAMi/custom sharing plugins disabled. The KAI Fleet bundle is Ready 1/1.

The gateway and both Hubs are Ready on qualified application artifacts: gateway `sha256:3a90de138a011786015ee1b631a926a3f0e689509c75ba2d25917f4e0e709d06` (source `f4eac3a`), CPS Hub `sha256:80ae1eaa71fa3011fad4e35ed85a9248e3df576d6223e14dd401be70191f5635`, and CIT Hub `sha256:2d6cec7b8639f9bd2ae10c56586ce839c0b718eec5c42ea290d742574c7280f3`. The gateway retains the original custody policy and reservation database; the new upstream catalog is separate. Two demonstrated integration bugs required narrow application repairs: legacy approval responses must retain the custody policy hash, and current upstream profile grants must not require legacy native approvals. The focused application suite passed 336 tests, and all five changed installed gateway source hashes matched.

Fresh operator-only qualification accounts were created through the supported Source APIs, preserving revoked memberships. Temporary QA grants remain capped at 5 GiB and one allowance per existing canonical person; they must be revoked after normal test shutdown. Existing production grants were not renewed. Both Hubs installed the reviewed upstream helper; the actual CPS legacy shared-profile hooks rejected eighteen attempts before invoking the old allocation machinery.

For controlled real-workspace acceptance, GPU2 alone now carries `cps.unileoben.ac.at/upstream-gpu-sharing=qualified` and is uncordoned without its temporary maintenance taint. Its legacy `accelerator=r615-canary-maintenance` fence remains. No other GPU worker is qualified or nominated for upgrade. This eligibility transition does not imply GPU2 acceptance: real notebook startup, CUDA, cross-service allowance conflict, retained files, normal shutdown and returned capacity are still being measured. The first real CPS Pod was assigned to GPU2 by stock KAI; notebook initialization then exposed a read-only-home Jupyter migration path, which is being addressed without relaxing the container security settings.

## Active blocker: managed peer loses its promised share (17:54 UTC)

The deployed-budget contention witness uses **16 GiB CPU RAM per container**. A managed-memory peer with a 20 GiB request/limit filled 19.5 GiB first. A later managed borrower with a 5 GiB request/limit then filled 36 GiB. The protected peer was CPU-cgroup OOM-killed while the borrower continued CUDA memset/synchronize progress. This was reproduced; the confirmation records the actual main-container CRI leaf cgroups and NVIDIA readback of 5120/5120 MiB and 20480/20480 MiB. This is a sharing-protection failure under the current user policy, not an idle-overage failure.

GPU2 has been re-cordoned, its temporary maintenance taint restored and its trusted qualified label removed. New pilot starts are stopped. All fixtures are cleaned normally and GPU memory/process return is recorded. No peer worker is nominated. Passing ordinary-memory contention in both arrival orders, the 10 GiB ordinary peer, and the opposite managed arrival order do not supersede this failure. NVIDIA documents that managed allocations are tracked only by system-memory accounting; a configuration or released upstream fix must be considered before any minimal driver-boundary rejection patch. Library interception or environment settings cannot resolve enforcement.

The reproducible harness, complete per-case manifests/logs/Pod states and [current verdict](evidence/upstream-sharing-20261116/managed16/acceptance-summary.json) retain this causal failure. Real application startup also exposed a writable Jupyter directory configuration issue and a missing deferred normal-stop release retry. Those application repairs continue without creating more GPU Pods or forcibly releasing unresolved reservations.

## Stopped allocation recovery and compatibility prerequisites

The reviewed Hub cleanup repair (source `1bcf087`) is deployed: CPS `sha256:2a73a06ebd7c6c5ed8235332da9a43296c343becc98f9ff4d68284364031c3f9`, CIT `sha256:d24a4b11ef2ab2689ad1bf49846449d5944b0c6a6a7a4e8f7285e3391fd60d1a`. Source tests passed 345; installed Hub suites each passed 344 with one notebook-runner test deselected. Actual cold-load plus normal Source-service DELETE recovered the stopped CPS generation from one binding/two charges to zero/zero after original-node identity/health and Pod absence checks. All four temporary QA grants were revoked; the 49 original grants were unchanged. This establishes this recovery path, not full real notebook acceptance.

Extended stock-driver baselines passed VMM, async pools, IPC aggregation, repeated process crashes, allocation races and recreated-Pod cleanup on both cards. Every completed case returned to idle GPU usage with no clients and retired cgroups absent. Both cards report `CU_DEVICE_ATTRIBUTE_PAGEABLE_MEMORY_ACCESS_USES_HOST_PAGE_TABLES=0`. The first crash test instead reproduced the Ubuntu 26.04 AppArmor stacked-label signal bug. GPU2 received only the two upstream exact-peer signal/ptrace rules; the same and fresh confined CPU Pods then passed signaling/ptrace while mount denial, enforcement and the hardening sysctl remained intact. Existing Pod identities/restart counts were unchanged. Boot persistence is configured but awaits a reboot test. See the [upstream fix](https://github.com/containerd/containerd/pull/14487) and [retained evidence](evidence/upstream-sharing-20261116/apparmor-compat/summary.json).

The minimal managed-memory policy candidate adds twelve C lines to R620 UVM: a default-false read-only opt-in flag rejects new managed VA ranges after collision classification using existing cleanup. Released `uvm_disable_hmm=1` closes pageable HMM migration separately. This is a node-wide compatibility restriction, including exclusive jobs and explicit managed globals; it does not preserve managed-memory applications. No stock userspace/firmware/version change, RM bridge or scheduler fork is included. The exact kernel build passed, preserving the twelve base image layers; package differences are limited to the UVM source and its checksum metadata. Candidate `sha256:c3b71557aa17df43faad5a2661d81f1025ba355ac3adf784096de12cd2ef3e73` is published but not yet loaded or qualified. GPU2 stays quarantined.

Reviewed full Hub template snapshots preserve the retained private configuration references through Helm post-rendering. Both were independently rendered and matched the live templates and Recreate strategies exactly, with server-side dry runs passing. They intentionally freeze chart Pod-template changes until deliberately refreshed. CPS currently remains pinned to GPU1; resolve that pin before GPU1 maintenance. CIT source selection must use its immutable GitRepo revision with the branch unset: Fleet 0.14.3 prioritizes branch over revision when both are set. Secret contents remain in existing private Secrets and are not included in these snapshots.

The first CPS persistence rollout exposed a validation gap: its namespace-qualified patch target matched the installed Helm manifest but not a freshly rendered chart, whose Hub namespace is absent. The overlay silently matched zero objects and Helm reset CPS to the vanilla image/config Secret. The exact reviewed template was immediately restored while GPU2 remained quarantined. Both overlays now match namespace-agnostically inside their own bundle, with explicit output namespaces. The durable fresh-chart verifier demonstrates the old CPS target fails and both corrected overlays produce exact reviewed templates/Recreate strategies and pass server dry runs. This supersedes the earlier installed-manifest-only persistence check.

## Loaded final platform candidates and active workflow gate

GPU2 cold-booted as `a39cdade-f00d-4cd1-9a81-c290d668194f` and loaded the derived R620 image `c3b71557…`. Both read-only UVM flags are `Y`; loaded and compiled module srcversion match `10301D70B8ED1758BC717E9`, and the installed UVM source matches `5648dbfe…`. Both cards reject repeated explicit managed requests with CUDA error801, preserve ordinary CUDA after every rejection, report no host-page-table GPU access, and reject raw host-pointer prefetch. Ordinary fixed profiles, VMM/pools/IPC, crash/race/reuse and real PTX/direct bidirectional P2P pass. The reproduced managed-contention sequence now rejects the oversized borrower and preserves ordinary protected-peer progress. This is deliberate managed-memory incompatibility, not bounded managed-memory support.

Fault testing then demonstrated a separate upstream NRI first-request timeout bug: a required plugin was recorded before its callback and could time out while container creation continued. No unlimited CUDA-access claim is made for that marker fixture. No released K3s/containerd integration supplied the needed fix. The exact small upstream author patch `9cb8bc1…` was backported to NRI0.12.0 inside the existing K3s1.34.9 artifact; Fractioning0.1.9 and all dependency versions remain unchanged. Real Unix/ttrpc regressions were RED on stock and GREEN after the patch, with the full NRI suite passing. Coherent official packaging regenerated the embedded archive identity; all375 ancillary asset entries and495 module-version records were verified.

Derived runtime artifact `sha256:1e79df5dd8d75db5407a4b3b8c62d3cce1f099fe137dfc88339f4ffdb733b456` was installed ONLY on fenced GPU2 as one-time same-version OUTER binary maintenance. Original binary, operation identity and configuration hashes are retained under `/var/lib/cps-runtime-artifacts/gpu2-nri-required-39c5/`; a retained host systemd oneshot performed the restart. Actual outer hash `6ce27630…`, both running agent/containerd inner hash `0ca3be05…`, and new data archive `2277a2c4…` were verified. Unit, environment, configuration, Rancher version settings and control-plane/peer binaries were unchanged. This is an explicit artifact exception, not an upstream released K3s binary or a new competing version controller.

The final installed runtime rejects the FIRST fresh GPU CREATE during an actual fractiond hang, rejects a subsequent disconnected-plugin request, and permits CPU creation. CUDA quota/recovery passes on both cards after reconnect; a further runtime restart preserves owned GPU/CPU Pod and container identities, CUDA PID/cgroup, quota and progress. The selected artifact-download service also retains its identity. All fixtures and resume timers are removed. Original failed witnesses remain retained separately.

Normal Source-registry activation code is separately reviewed: source445 tests and each installed CPS/CIT closure444 tests pass, with one notebook-runner test deselected per image. Published Hub images `0bbeb426…` and `bf138c57…` are not yet deployed. Current live Hubs remain `2a73a06…`/`d24a4b11…`. The fixed catalogb28 remains unchanged; a final immutable acceptance record must bind it to actual current driver/runtime/app artifacts rather than treating historical8d/d8 evidence as current attestation.

GPU2 remains unqualified for normal placement pending the real workflow/placement/observability gates in [current status](evidence/upstream-sharing-20261116/gpu2-current-status.json). Before enabling another worker, Fractioning's selector becomes the explicit `fractioning-runtime=upstream` pool; GPU2 is its sole current member. The hostname restriction is removed while no real allocations are active, causing only GPU2's daemon rollout. This also recreates its metrics collector after driver availability; the first cold-start collector had permanently fallen back without NVML. Two unchanged released0.1.9 Prometheus monitors are added; actual collection still requires measured verification.


## Current staged state — 18 November 2026, 14:42 UTC

This update supersedes the historical rollout status above. All four workers now report Ubuntu26.04.1 and kernel7.0.0-43. GPU1/2/3 are qualified and schedulable (six GPUs); GPU4 is Ready with two advertised GPUs but remains cordoned and fenced. GPU4 has passed actual CPS5/10/20 Source cycles; its remaining CIT, CPU/member and fault gates still precede explicit promotion.

Allowed CPS network mounts now default on: the network master, Project share and Scratch1 use the original role eligibility; manual unchecked choices remain honored. Renderer991 and native Home/spawn assets remain unchanged through the image staging below.

Reviewed dedicated-personal compatibility source1e9af2ff is installed with the feature OFF: Gateway443 image91a72d8f and CPS Hub394 imageb04cf689, owned by CPS GitOps revision3df01e0e. Real health/native reservation API reads return200, installed modules match the reviewed source, old application Pods are gone, all four Gateway SQLite schemas/logical tables match native backups, and Hub stable native tables/configuration/crypto plus the entire CIT snapshot remain exact. The six personal GPU choices are not yet restored. Paired configuration passed independent review but remains unapplied pending the owned-fixture1/2GPU, conflict, confirmed cleanup and CPU-reset qualification. No new canonical mappings or grants were fabricated.

The real shared-gpu-lab stopped at13:27 after approximately its configured four-hour lifetime. Its reservation cleanup is confirmed and its home PVC remains Bound. The timing supports the lifetime explanation; exact caller attribution was not logged. Root issued no Start or Stop for that real workspace.

Stock CPS pre-puller pruning removed only unused RAPIDS/Xpra and replaced an unused fallback with the already cached CPU image. All namespace references were audited; CIT does not require equivalent pruning. Ordinary garbage collection brought GPU1 to76.97percent imageFS utilization. No manual image/data deletion or kubelet threshold changes were used. Other workers retain their measured headroom; no blanket low-watermark claim is made.

See [default-off staging receipt](evidence/upstream-sharing-20261116/personal-gpu-defaultoff-stage-20261118.json). Full-platform qualification, unresolved legitimate identity links, GPU4 promotion and the original timing/restore gates remain open.
