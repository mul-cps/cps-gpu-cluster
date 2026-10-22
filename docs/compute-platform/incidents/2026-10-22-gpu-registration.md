# GPU registration outage, 22 October 2026

Status: recovery in progress. Times below are UTC.

## Proven cause

GPU workers 1 and 4 record QEMU guest-agent `guest-shutdown` and logind
`hypervisor initiated shutdown` at 07:37:27. This was an external hypervisor
shutdown, not an unattended-upgrades automatic reboot. The responsible host
operator or automation cannot be identified from guest logs.

On GPU4, unattended upgrades installed kernel 6.8.0-147.147 on 15 October at
06:16. The worker continued running 6.8.0-134 until the 22 October shutdown;
it booted 6.8.0-147 at approximately 07:47. Thus the compatibility defect was
latent until the next boot.

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
