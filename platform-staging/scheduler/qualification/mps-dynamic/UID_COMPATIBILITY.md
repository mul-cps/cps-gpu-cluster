# Process UID compatibility before real Hub qualification

Status: **prepared only**. The existing mixed process UIDs cannot establish
concurrent Hub/batch MPS compatibility. This is an operating-system process
identity decision, independent of canonical person linkage, Hub usernames,
entitlements, browser identity, or workspace principals.

The observed GPU2 server has UID 10001. The protected real Hub process has
UID 1000/GID 100. The controller runs as root without `-multiuser-server`.
NVIDIA describes matching-UID admission, queuing a different UID while existing
clients remain, and replacing the server once its clients have disconnected.
The optional multiuser server changes the isolation model; this candidate does
not enable it. [NVIDIA provisioning sequence](https://docs.nvidia.com/deploy/mps/latest/architecture.html#provisioning-sequence),
[system/application limitations](https://docs.nvidia.com/deploy/pdf/CUDA_Multi_Process_Service_Overview.pdf).

## Smallest direction

Use process UID 1000 consistently for trusted GPU workloads, preserving the
already running Hub UID. JobSet workers already use UID 1000. The released
compiler accepts operator-resolved UID/GID pairs, so a future versioned catalog
can set `trusted.sharedGpuRuntime.uid=1000`, `gid=100`. Hub identity overrides
remain the actual spawner UID/GID. Matching UID is the MPS requirement; groups
and filesystem permissions still need their own checks.

The current Argo runtime compiler puts its main security context in a template
PodSpecPatch, applied after the notebook launcher's base UID 10001 context. Thus
shared GPU mains can take the trusted UID 1000 without changing interactive
homes or the gateway service process. Check the final actual Pod, not just
the catalog or source. Keep CPU/exclusive behavior explicit and reviewed.

Static source supports a candidate, not a permission pass:

- The compute Dockerfile creates only the compute UID 10001 account and declares
  `USER 10001`. A Kubernetes UID 1000 override needs testing in each approved
  actual image, including imports and libraries that query passwd/HOME.
- Notebook execution uses a temporary extraction directory and writes the
  executed artifact beneath `/tmp`; the launcher sets workingDir `/tmp`.
  HOME/Jupyter/Papermill caches, kernel connection files, artifact input/output,
  and read-only root filesystems still need end-to-end checks.
- Private cache initialization uses the actual trusted UID/GID and a Pod-local
  emptyDir with fsGroup. Test its inode/permissions at 1000/100. Verify MPS pipe
  and shared-memory permissions without broad chmod/chown.
- Workspace/NFS ownership and approved mounts must keep working. Do not
  recursively chown existing homes or alter usernames/storage paths to solve
  this. Browser visitor attribution and shared-kernel principal rules stay intact.

## Tests that distinguish readiness from compatibility

First, a CPU-only UID preflight inside the proposed runtime records `os.getuid()`,
`os.getgid()`, HOME, approved image digest, and protected storage/write checks
on scratch paths. Compare its UID with a freshly captured MPS server UID before
any CUDA context is created. UID 1000 versus10001 fails this readiness gate; it
does not empirically measure driver queuing. This check requires no MPS setting
or GPU mode changes.

A deliberate cross-UID CUDA connection is not a read-only inspection: it may
queue or replace the idle server. Therefore it cannot run within the existing
PID10001 maintenance candidate's immutable server fence.

For a separate root-reviewed compatibility test, keep the existing daemon and
mode configuration unchanged, fence idle GPU2, and stage only a trusted tiny
UID 1000/GID 100 client. Allow its first CUDA context to cause the documented
idle-server handover. Record the resulting server PID/start time/UID, unchanged
controller/configuration, actual GPU UUID, and client membership. This is a
controlled process-state transition even though it changes no daemon settings.
It must not be represented as zero side effects or as continuing the old candidate.

After the handover, capture a new reference and review a new candidate against
that UID 1000 server. Stage two scratch-only UID 1000 clients using the actual
approved Hub/runner images on the same GPU. Each holds at most 256 MiB and emits
bounded synchronized progress. Require two simultaneous controller client
receipts, matching real UIDs/GPU UUIDs, continuing peer progress, clean CUDA
synchronization/exit, and an unchanged protected GPU1 notebook. Do not mount
the real user's home or claim a clone is a completed real-Hub qualification.

Then qualify the mixed 5/10/20 workspace budgets with source/image versions
bound to that new server. Missing image permissions, a changed server PID,
queuing, unknown GPU processes, or a fault stops the test. There is no automatic
multiuser switch, restart, replacement-PID reapplication, or GPU mode change.

The offline renderer intentionally rejects UID 1000 under the old UID 10001
reference. A fresh UID 1000 reference needs a reviewed candidate revision;
changing a JSON UID or replacing the server PID in a command does not qualify it.
