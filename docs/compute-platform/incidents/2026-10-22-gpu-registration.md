# GPU registration outage, 22 October 2026

Status: driver registration recovered; shared-agent reboot recovery remains open.
Times below are UTC.

## Proven cause

GPU workers 1 and 4 record QEMU guest-agent `guest-shutdown` and logind
`hypervisor initiated shutdown` at 07:37:27. This was an external hypervisor
shutdown, not an unattended-upgrades automatic reboot. The responsible host
operator or automation cannot be identified from guest logs.

On GPU4, unattended upgrades installed kernel 6.8.0-147.147 on 15 October at
06:16. The worker continued running 6.8.0-134 until the 22 October shutdown;
it booted 6.8.0-147 at approximately 07:47. Thus the compatibility defect was
latent until the next boot. GPU4 has `GRUB_DEFAULT=0`, a hidden boot menu
and zero menu timeout: the next boot automatically selected the newest
installed kernel. Both 6.8.0-134 and 6.8.0-147 images are still present.

The installed official NVIDIA 580.95.05 driver failed to compile its open
kernel module against the new kernel headers: `nv-pci.c:232: too few arguments
to function pci_resize_resource`. The headers require four arguments; the old
driver supplies three. This prevents driver readiness, which blocks toolkit
validation, device-plugin startup and GPU resource registration. Kubernetes
nodes remain Ready despite advertising zero GPUs, so node readiness alone did
not detect the failed GPU service.

GPU2 has a different, healthy, separately managed official 615.71.09 driver.
Its reboot erased the volatile `/run/nvidia/validations/toolkit-ready` marker.
The operator-validator is deliberately disabled for the pilot; without another
validator, the restarted plugin waits forever for a marker nobody recreates.
The official driver and toolkit validators both exited zero in a controlled
recovery Pod. The existing device plugin then registered one approved GPU.
GPU2 keeps its maintenance selector and qualified UUID filter; recovery does
not expose the pilot node to ordinary exclusive-GPU workloads.

## Recovery

The user subsequently directed standardizing all workers on the same official
**615.71.09** already working on GPU2. The remaining R580 sequence was stopped
before GPU3; GPU4 had recovered on R580 and GPU1 was still installing it.
The current R615 migration uses the unchanged pinned GPU2 driver/firmware
specification, activates one new node at a time and leaves GPU2 untouched.
See `platform-staging/gpu/r615-driver/README.md`.


User approved the official 580.178.04 driver for workers 1/3/4 on 22 October.
This stays within R580 and includes the upstream kernel API adaptation.
The registry image resolves to
`nvcr.io/nvidia/driver@sha256:2b6e81c01ffa5634d2e3e798ad19e287877ef7551086eb36782348e653e34b74`.
GPU2's driver, device filter and native isolation settings remain unchanged.

Automatic driver upgrades are temporarily disabled and the OnDelete driver
DaemonSet is advanced one worker at a time. Recovery is not complete until
actual driver health, device-plugin registration and workload startup pass.

A dedicated GPU2 driver/toolkit validator DaemonSet uses the pinned official
validator image and original validation steps. It performs no CUDA workload,
MIG reconfiguration, driver install or reset. It restores validation on Pod
sandbox recreation instead of relying on hand-created marker files.

The proposed prevention mechanism is documented in
[`kernel-maintenance.md`](../kernel-maintenance.md). It has not been installed
on hosts; current recovery does not imply a preboot gate is active.

## Prevention and remaining investigation

- Pin the driver explicitly in Git; the previous values inherited an old
  chart default while security updates installed newer kernels independently.
- Qualify each kernel/driver pair before coordinated worker maintenance;
  update one worker, verify GPU registration and a CUDA workload, then proceed.
- Alert on expected versus advertised GPU capacity and plugin readiness, not
  merely Kubernetes Node Ready.
- Coordinate hypervisor shutdowns with cluster maintenance; guest logs prove
  the trigger but do not identify the hypervisor actor. Host audit logs are
  needed for attribution.
- A real reboot qualification of the dedicated GPU2 validator remains open;
  creating its replacement Pod is not equivalent to a host reboot test.

## Latest-driver assessment

As of 22 October, NVIDIA lists 615.71.10 (19 October) and R580 patch 580.196.07
(21 October). Latest .run availability does not imply GPU Operator container
availability or validation of KAI/HAMi/MPS/native isolation. Use the user-selected exact 615.71.09 release across the workers,
with per-node validation; qualify newer images separately.

References:
- https://github.com/NVIDIA/open-gpu-kernel-modules/blob/580.178.04/kernel-open/nvidia/nv-pci.c#L217-L221
- https://developer.nvidia.com/datacenter-driver-archive
- https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/25.10/platform-support.html
- https://docs.nvidia.com/datacenter/tesla/tesla-release-notes-615-71-10/index.html

## Shared-agent reboot recovery is separate

After GPU2 registration recovered, the native Node agent remained unavailable.
Its kubelet event is `hostPath type check failed: /run/cps-native-gpu is not a
directory`. The directory was absent on the rebooted host. The agent intentionally
requires an existing protected directory rather than silently adopting empty
custody state. Runtime binaries mounted under `/opt/cps-native-runtime` in the
container actually come from existing k3s/NVIDIA host paths; absence of a host
`/opt/cps-native-runtime` directory is not evidence of a provisioning defect.

Do not recreate empty custody or reuse old boot/load attestations. Locate and
verify complete original protected records before a reviewed new-boot recovery.
The published SDK requires authenticated historical private records and an exact
current boot epoch. Driver health alone does not satisfy these requirements.
A complete checksummed durable custody backup and tested recovery remain
production gates. No native-agent recovery bypass was applied in this incident.

## Verified final driver state

All four workers now run the same official 615.71.09 image digest. All eight
physical GPUs report that driver and MIG disabled. All workers are uncordoned
and all four device-plugin Pods are Ready. Separate vector-addition kernel runs
passed on both GPUs of workers 1/3/4 and the approved GPU of worker2 (seven
CUDA tests). Worker2 retains its approved UUID filter and original driver owner;
its second device remains excluded from advertised inventory intentionally.
Thus advertised capacity is 2+1+2+2, not an accidental claim of eight qualified
shared GPUs. Own completed validation Pods were archived and removed.

Evidence: `platform-staging/gpu/r615-driver/evidence/20261022-driver-recovery.json`.
This proves basic driver/registration recovery, not native-group or full
production qualification.


## Custody recovery coverage after the reboot

A read-only recovery investigation verified the original protected backup for all
82 lifetimes in the current terminal index: all 323 index-required private files
match their pinned hashes. This is historical coverage, not current-boot authority.
For later lifetimes, 32 enrollment-abort audit hashes and one prepared-offline
journal were matched. Original journals for 29 subsequently retired lifetimes
remain unavailable in the searched captures. The bounded search included the six
large runtime captures previously excluded by the size limit; none supplied the
missing journal hashes. Cache and image inventories were excluded deliberately.

The recorded TrueNAS recovery directory was checked over SSH. It contains two
encrypted Hub bundles; no Node custody backup was established there. A bounded
host search under `/var/backups`, `/var/lib/cps-native-gpu` and `/root` likewise
found no Node custody backup. These searches do not establish universal absence.

A fresh Kubernetes ledger read still reports 197 allocations, all released.
The Node Deployment nevertheless has zero available replicas and its protected
host directory remains absent. Released ledger state does not authenticate lost
private journals or authorize a new boot. Existing cleared-offline recovery
requires an original private record and the original epoch; it cannot recover
these missing journals across a reboot. Re-enrollment must not erase that history.

Next recovery work requires a distinct, explicitly reviewed loss declaration
and terminal-history protocol, preserving all original public references and
missing journal hashes without inventing CapRecords or seal identifiers. It
must close only the exact released historical cohort, prove physical quiescence,
exclude concurrent claims, and separately qualify a fresh current-boot epoch.
The declaration itself must never authorize GPU access. Durable, verified custody
storage and off-host backup must precede reactivation. This protocol is not yet
implemented or deployed; existing admission checks remain unchanged.


## Current loaded native guard gap

A later read-only check on GPU2 confirms that the reboot restored the stock
615.71.09 module build. Its `NVreg_CpsNativeImportGuard` parameter is absent;
loaded core/UVM source versions differ from the exact previously qualified
CPS guarded builds. The official driver can pass ordinary CUDA tests while
lacking those guards. Restoring custody alone therefore cannot restore shared
GPU enforcement. A guarded build for kernel 6.8.0-147, dependency validation,
reviewed load and relevant hardware qualification remain required. No module
was unloaded or replaced during this observation.

See `platform-staging/gpu/r615-driver/evidence/20261022-native-postboot-gap.json`.
