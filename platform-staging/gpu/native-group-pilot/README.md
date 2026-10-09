# Native group GPU2 node authority pilot

This package is disabled by default. Both CLIs make no API/NVML/module calls
without `--execute`; the committed proposal has zero replicas and a deliberately
unusable image digest. It is an offline review artifact, outside the Fleet
production path. Root owns activation, GPU2 quiescence, module changes and every
live Kubernetes call.

`node_agent.py` runs bounded iterations through the existing source-pinned
`QualificationNodeBackend`, `poll.py` helpers and SDK `NativeCapController`.
The service uses CPU resources, host PID visibility, privileged device access,
read-only host CRI/cgroups/module metadata, and a persistent local root0700
`/run/cps-native-gpu`. Source and config ConfigMaps are immutable. Its projected
credential remains inside the service. The final image must contain Python3 and
R615 `nvidia-smi`/`libnvidia-ml.so.1`; its NVML version must equal 615.71.09.

The root-selected configuration pins the authority namespace, GPU2 node UID,
physical GPU UUID, policy hash and CPS/CIT workspace/profile allowlist. The
service accepts only immutable `cps-native-enrollment-{binding_id[:40]}` maps
from that namespace. A binding is exactly 60 lowercase hex characters. Each
closed enrollment fixes the start attempt, workspace principal, sorted member
IDs and final `CapIntent`. The actual Pod UID, complete admitted spec hash,
selected node and digest-pinned container images must agree before a cap write.
No caller can choose placement through this agent.

Root0600 intent and enrollment mirrors preserve the source ConfigMap UID and
full record. Missing, replaced, duplicated or changed records block authority;
original enrollments must survive along with cleaned journal tombstones. The
writer lock prevents a second node loop from owning the same state. The SDK
journal separately serializes all cap transactions. Errors retain protection
and allocation ownership; the backend can stop only the exact enrolled Pod
using a UID-preconditioned delete.

A cleanup ConfigMap is published only after the original Pod is actually absent
and fresh exact native accounting proof succeeds. A surviving cgroup requires a
`cleaned` journal, zero recursive tasks and global GPU clients, and positive NVML
unset/unlimited readback with zero usage. An absent cgroup requires a distinct
`retired-inert-cap` journal with its original finite cap retained: a complete
root0400 guarded inventory must identify the exact original inode/kernfs ID as
offline, pinned, default-hierarchy and physically charged zero bytes. Original
Pod absence, cgroup2 mount device and the same healthy driver/node/boot epoch
are checked on both sides of the read. Only this branch permits unrelated live
peer GPU clients; it performs no native cap reset and never interprets NVML
error 17 as unset. A terminal Pod still present is insufficient. An absent
Pod without an original native journal cannot get a cleanup receipt and needs
operator recovery. Deadlines, lease expiry and cancellation alone never release
allowances. Immutable cleanup conflicts are accepted only after an exact GET
comparison, including a real ConfigMap UID. A private publication tombstone
allows later restarts to retain the old receipt when a replacement Pod or peer
now uses the GPU; it never resets a new workload.

Normal cleanup v1 remains unchanged. A retained cap adds the closed optional
`retirement` member containing typed `proof` (`cps-native-retired-inert-cap/v1`),
`enrollment_uid`, canonical full `enrollment_sha256`, and protected
`journal_sha256`. Its state is explicitly `retired-inert-cap`, with the original
finite limits preserved. The gateway must run the matching SDK validator before
this node code is enabled: it validates actual immutable cleanup/enrollment
ConfigMap identities and referenced UID/hash, plus the exact intent, epoch and
finite cap in the typed proof. Old gateways reject this extra evidence and keep
the allocation held. A newly loaded driver's map cannot prove an older journal's
epoch; module teardown recovery requires separate operator evidence.

RBAC grants only exact Pod GET/DELETE in `jupyterhub` and `cit-jhub`, GET of the
single GPU2 node, and ConfigMap GET/LIST/CREATE in the authority namespace.
Because RBAC cannot restrict CREATE by resource name, a fail-closed admission
policy limits this node credential to immutable cleanup ConfigMaps with one
`receipt.json`, one matching binding label and no garbage-collection owner.
The node credential cannot create enrollments or modify the allocation ledger.
The API authority owns the ledger and releases allowances only after its own
exact receipt validation. Admission policy server-side validation is a live
activation gate owned by root; these CPU tests do not establish server support.

## Offline verification and rendering

```sh
python3 -m unittest discover -s platform-staging/gpu/native-group-pilot -p 'test_*.py' -v
python3 platform-staging/gpu/native-group-pilot/node_agent.py
python3 platform-staging/gpu/native-group-pilot/driver_loader.py
python3 platform-staging/gpu/native-group-pilot/render.py > /tmp/native-node-disabled.json
```

The committed `source-snapshot.json` stores exact reviewed bytes, checked against
source pins before rendering/import. It is also available in the immutable code
ConfigMap. Controller pin: `2c9770188a79406c674560616a8d9da8f4dafa275f0644d9669dfab001e7690e`;
shared health pin: `22107515ecdc2ffe18afbafa8f15432ed9439aa6fc56ed9531649f790b29e769`.

For a reviewable activation proposal, root prepares a configuration based on
`config.example.json` with the actual policy hash, an explicit workspace/profile
allowlist and `enabled: true`, builds the service from an already pinned base
image with the required userland, and supplies the resulting image digest:

```sh
podman build --build-arg SERVICE_BASE_IMAGE=REGISTRY/REVIEWED-BASE@sha256:ACTUAL_DIGEST \
  -t LOCAL-TAG platform-staging/gpu/native-group-pilot
python3 platform-staging/gpu/native-group-pilot/render.py \
  --config /ROOT/REVIEWED/enabled.json --image REGISTRY/SERVICE@sha256:ACTUAL_DIGEST \
  --enable > /ROOT/REVIEWED/activation.json
```

The build checks that the base is digest-pinned and contains Python3/NVML/tools;
it performs no GPU calls or package installation. The service image itself and
live deployment are not built or activated by this package's CPU verification.
Root must prepare all state directories root0700, retain journals across service
restarts and approve the scoped credential/admission objects before activation.
The CRI helper defaults to the host k3s `data/current/bin/crictl`. On GPU2,
`current` is an absolute host symlink: following it beneath `/host` escapes that
mount prefix and does not locate the host binary inside the service container.
Root must resolve the actual binary on the host, verify its executable and
runtime socket, and override the node-agent command with
`--crictl /host/var/lib/rancher/k3s/data/ACTUAL_RESOLVED_DATA_DIRECTORY/bin/crictl`.
The directory observed on 2026-10-09 begins `65415f`; that is evidence for that
host revision, not a reusable default. Resolve it again after a k3s update.

## Exact root driver loader

`driver_loader.py --execute --quiesced-gpu2` can run only as root on the GPU2
hostname. Root manually removes every NVIDIA module after quiescing consumers;
the loader refuses to load while any NVIDIA module remains in sysfs or
`/proc/modules`. It never unloads, resets, enables MIG, drains or reboots.
Before root begins any maintenance, invalidate the authority explicitly:

```sh
python3 /ROOT/REVIEWED/driver_loader.py --execute --quiesced-gpu2 --invalidate
```

Copy the reviewed files into protected root-owned directories and use the
following default inputs (the original user-owned build paths are not accepted):

- `/run/cps-native-gpu/driver-inputs/nvidia.ko`: ELF SHA256
  `59f623fe5fdc89ef06f8055ee4dbfafeabe70b1d0bcabc487bc6fe04b78d6e77`,
  source version `C6CF64F73A3430C26C030B7`.
- `/run/cps-native-gpu/driver-inputs/nvidia-uvm.ko`: ELF SHA256
  `b2ae67722e9e21a70c319aeed2184f5b2d1f23b8e32dea00816cfd5cd2c3ee61`,
  source version `9353E234906B1910373B07A`.
- `/run/cps-native-gpu/driver-inputs/native_gpu_health.py`: the exact shared
  health source from the snapshot above.

All directory ancestors must be root-owned and protected from group/other
writes; inputs must be single-link regular root-owned files. Hashing uses one
held file descriptor, and `insmod /proc/self/fd/N` inherits that descriptor via
`pass_fds`. Input metadata is checked before/after load. Core loads with
`NVreg_CpsNativeImportGuard=1`; UVM loads with managed-mmap denial, HMM disabled,
ATS 0, built-in tests 0, and SAM migration disabled.

Only after loaded version/source/flag/module-inode checks does the loader write
a fresh root0400 `driver-load-manifest.json` and root0600 `driver-generation`
inside root0700 `authority`. It uses the closed
`cps-native-driver-load/v1` schema and the shared verifier. A failure invalidates
authority and retains any loaded modules for root inspection/recovery. The
`/run/nvidia/firmware-r615-canary` directory is required and never altered or
removed, because the stock R580 rollback also needs it. Original driver
DaemonSet recovery remains root's separate operation.

## Root-reviewed abort before the gate (qualification only)

`abort_before_gate.py` defaults to an inert status and imports only the Python
standard library. This one-shot recovery is restricted to the closed GPU2 pool
and CPS `native-group-a/b` or CIT `native-group-a`. It applies only when root
has proved that a failed node-agent startup never began a native transaction:
the controller writes its protected journal before setting any cap, the
journal still has the same inode/device and no records, no gate was published,
the exact Pod is absent, and the healthy driver epoch remains unchanged.
Missing journals, reset epochs, journals with any record, unavailable APIs,
existing/replacement Pods, and uncertain observations retain the allocation.

Root stops all native writers and reviews the exact gate-only Pod capture,
failed node-agent log, pinned node-agent/controller sources, original ledger
allocation and immutable enrollment. The closed evidence object records their
hashes, exact attempt, ledger/enrollment UIDs and full enrollment hash. Its
`proof` contains the typed node epoch, journal device/inode, true
`journal_protected`, `journal_empty`, `gate_receipts_absent`,
`native_writers_quiesced`, `exclusive_lock`, `driver_healthy`, and integer-zero
`global_gpu_memory_mib`, `global_gpu_clients`, `global_compute_apps`,
`pod_runtime_tasks`. `review.native_transaction_never_started` must be true.
All hashes use `sha256:` followed by SHA256 of the exact reviewed artifact;
object hashes use canonical JSON (`sort_keys=True`, separators `(',', ':')`,
`allow_nan=False`). An explicit canonical evidence hash is required.

The root fence command is a reviewed argv JSON array pinned by its canonical
hash in the evidence. It must acquire the exclusive protected host journal
writer lock and retain it while the CLI runs. It emits a fresh JSON line
`{event: "fence-acquired", observed_at: UTC-Z, proof: ...}`; each stdin
`{"op":"verify"}` independently rechecks the same protected journal, healthy
epoch, quiesced writers, zero GPU clients/memory/tasks and emits
`fence-verified` with fresh UTC time. `{"op":"release"}` releases the lock and
exits successfully. The CLI checks a live subprocess around every actual API
operation and repeats the proof before publication and CAS. A static JSON
claim cannot replace this live root fence. Root must pin and protect any
remote helper bytes referenced by the command before execution.

First generate a private offline proposal from exact captured API objects:

```sh
python3 platform-staging/gpu/native-group-pilot/abort_before_gate.py \
  --propose --qualification-only --evidence /ROOT/REVIEWED/evidence.json \
  --evidence-sha256 sha256:CANONICAL_REVIEWED_EVIDENCE_HASH \
  --ledger /ROOT/REVIEWED/ledger.json --enrollment /ROOT/REVIEWED/enrollment.json \
  --output /ROOT/REVIEWED/new-proposal.json
```

Root can API-server dry-run the proposal's `abort_configmap` using its existing
operator credential. The proposal includes a CAS plan with an explicitly
unresolved abort UID; it cannot be applied as a ledger patch. After independent
review, execute with the pinned live fence and root operator credential:

```sh
python3 platform-staging/gpu/native-group-pilot/abort_before_gate.py \
  --execute --qualification-only --evidence /ROOT/REVIEWED/evidence.json \
  --evidence-sha256 sha256:CANONICAL_REVIEWED_EVIDENCE_HASH \
  --fence-command-file /ROOT/REVIEWED/fence-command.json \
  --kubeconfig /ROOT/REVIEWED/operator.kubeconfig \
  --output /ROOT/REVIEWED/new-execution-receipt.json
```

The CLI independently reads the exact Node UID, Pod absence, ledger and
immutable enrollment. It creates and reads back a distinct immutable
`cps-native-abort-{binding_id[:40]}` ConfigMap, with only the binding label and
`abort.json`, then JSONPatch-tests both original ledger UID and fresh
resourceVersion. The allocation becomes `released` and gains
`pre_gate_abort: {configmap, configmap_uid, sha256}` referencing the actual API
UID and canonical payload hash. The original intent, immutable allocation,
other rows, enrollment and all files remain. An orphan abort ConfigMap after
CAS failure holds no capacity; retry requires exact proof equality. A completed
retry requires the same real ConfigMap UID and exact ledger tuple.

The node agent requires the matching immutable CM and ledger proof, unchanged
healthy epoch, no journal record and first actual Pod absence before recording
its separate protected abort tombstone. It excludes that old UID from capacity
and never constructs a cap identity or cleanup receipt for it. Preserve the
abort CM, enrollment and ledger UID/rows permanently for these tombstones.
There are no SQL, device/cap, Pod-delete or enrollment-delete operations in
this CLI. Release the matching member reservation afterward through the
existing gateway service API, which still independently observes Hub/Pod
shutdown. Existing gateway/node credentials must remain unable to create abort
ConfigMaps. This recovery does not enable profiles or qualify general packing.

## 2026-10-09 qualification boundary

The controlled no-MIG pilot passed automatic 5 GiB cap assignment: Pod UID
prefix `696bab5d` completed the first gate with exit code `0` and native limit
readback `5368709120` bytes. Its notebook container never executed because the
runtime could not resolve its management CDI GPU UUID. Shutdown cleanup remains
blocked: querying the removed cgroup returned NVML result `17`. Cap assignment
does not establish notebook startup, cleanup or reservation-release evidence.

Root subsequently corrected GPU2's supplemental CDI specification at
`/var/run/cdi/management.nvidia.com-native-pilot-r615.json`, SHA256
`55d23389ef8745a9ffef4b58181ed350f549100b03d7f8e7cb9590ae4f3bc5fd`.
It exposes only `GPU-16128952-b438-556a-00bb-93039ee24e56`; 57 mounts were validated
against the current R615 driver paths, and `nvidia-ctk cdi list` resolves that
UUID. This is specification-resolution evidence; a successful notebook start,
OOM/recovery and independent peer continuity remain unqualified.

See the [platform checkpoint](../../../docs/compute-platform/qualification.md#2026-10-09-automatic-cap-and-admin-checkpoint)
for the verified console status and remaining gates. Ordinary group GPU access
remains disabled.
