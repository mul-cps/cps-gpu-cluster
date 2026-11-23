# CPS/CIT GPU platform rollout on 2026-11-23

## Course profiles and controller backup

The live CIT Hub uses the immutable `cit-student-shared5-rino-20261123` Secret
and retains the scoped `cps-rino-mujoco-exception` reference. Fleet adopted
CIT teaching platform revision `e876e33e069de3c896454d8e03563d3fc3c21ce7`
and reported nine of nine bundles and 55 of 55 resources ready. Helm records
the current Secret reference. The live Hub pod template and Deployment
generation matched their pre-adoption values, and `claim-m12113877` is Bound.

The [Gateway and backup render](../../platform-staging/compute-checkpoint-authority/current-rollout/)
matches the live Deployment, CronJob and backup ConfigMap. It references the
immutable runtime Secret containing the reviewed identity link. Secret
contents stay in the protected configuration. The render passed server-side
dry run. The scoped `cps-compute-authority` Fleet GitRepo adopted revision
`12063190878ee5a868bf66814b6c01a395db945f` and reports three of three
resources ready. Helm owns the existing objects. API readback matched all
three UIDs and their original live content, and the gateway kept its pod
template revision and ready replica. Its Deployment generation advanced
during adoption.

The live scheduled backup now uses `compute-state-timed-gpu3-20261119` with
a digest-pinned runner and the gateway image and upstream policy hash recorded
in the CronJob. Snapshot `20261123T083647.220371Z` was restored onto
`compute-state-restore-pin-1123083635`, whose PV has reclaim policy Retain.
All four database content hashes, schema digests, integrity and foreign-key
checks passed. The isolated allowance check verified both CPS/CIT acquisition
orders and reacquisition after release. All 116 custody records were clean,
with one retained delete record. The allowance check used a synthetic
canonical identity on a copy of the restored data.

A second backup ran successfully with the new schema guard. A local fixture
verified that the guard rejects schema drift and leaves no partial snapshot.
The scheduled job now mounts that exact immutable guard. Both gateway
Deployments were available after the change.

The earlier 43.72-second handoff remains the last measured production
handoff. A new live recovery and rollback timing rehearsal is open.
Alertmanager's effective configuration has only the `null` receiver.
External firing and resolved acknowledgement awaits the approved destination.
Ordinary account, current-course, MuJoCo/Xpra and ambiguous CREATE/STOP
qualification remains open.

## KAI and workload admission

The [KAI staging package](../../platform-staging/gpu/upstream-sharing/kai-019/)
contains the chart and enabled-image digest locks. The candidate render uses
KAI 0.19.0, whose Chart.lock resolves Fractioning 0.1.9. Six KAI CRDs changed
and each still declares all of its live stored versions. Both default queues
match live. The rollback chart, live admission webhooks, queues, installed
image IDs, and separately installed Fractioning configuration were captured
before any promotion. The staging hardware matrix and rollout are open.
All four workers report Ready and advertise eight allocatable GPU devices.

The 16-start burst still requires eight verified canonical people per Hub.
GPU batch remains disabled. Interactive-first shared allowance, durable waiting
and checkpoint/resume, and normal-user and CI pilot qualification remain open.
The tenant guide documents the gateway submission path and current NvFractions
runtime. Production SM sharing, GPU4 eviction recovery, elastic VRAM and
superseded component retirement remain open.

Evidence is stored in the rollout artifact directories
`backup-cron-pin-zbeVH2Bo`, `cit-gitops-readback-TffSraGk`,
`cit-fleet-adoption-2fRN4cn3`, `gateway-fleet-adoption-oA2VtROX`, and
`kai-019-render-20261123` under
`/home/bjoern/artifacts/cps-upstream-sharing-20261116/`.

## 5 GiB GPU workflow operator fixture

Argo workflow `gpu-batch-nvfractions-fixture-1123093838` reached Succeeded
through KAI on `k3s-wk-gpu1`. Pod UID
`750d69b4-aa1c-4a3a-95be-4837068f5b34` recorded the required Fractioning
plugin and equal 5120 MiB request and limit. CUDA enumerated one device and
reported the same GPU UUID as the admitted pod annotation. It allocated,
wrote and freed a 16 MiB device buffer. Argo removed the pod after completion.
The evidence is under `gpu-batch-profile-render-y45VXJ4j` in the rollout
artifact directory. Normal tenant admission, 5 GiB enforcement under
contention, and the live checkpoint/resume path remain open.

The replacement workflow `gpu-batch-limit-fixture-1123093957` used the same
physical GPU on worker 1. Its new pod UID was
`79895022-f7a2-4df7-a870-92fd7720a1b9`. A 5,248 MiB CUDA request returned
error 2 (out of memory). The process subsequently allocated, wrote and freed
16 MiB. The workflow succeeded and Argo removed its pod. This qualified
sequential device reuse and the standalone cap for this fixture. The
concurrent contention and tenant gates remain open.

The pair `gpu-batch-pair-1123094107-a/b` ran concurrently on the same GPU
on worker 1. Both main containers completed 20 synchronized CUDA writes
and readback checks against their own 256 MiB buffers, and both workflows
succeeded with no pods remaining. The receipt binds each workflow to its
pod UID and container ID and records the overlapping CUDA execution times.
This tests concurrent progress at the 5 GiB profile. The test held
256 MiB per process, so it does not establish competing near-capacity
working sets or tenant checkpoint behaviour.

The near-capacity pair `gpu-batch-nearcap-1123094241-a/b` held 4.5 GiB per
main container on the same GPU for 20.30 overlapping seconds. Each process
completed 20 synchronized full-buffer writes, checked its readback, and
continued after two 768 MiB allocations returned CUDA error 2. Both
workflows succeeded and their pods were removed. The evidence is in
`gpu-batch-profile-render-y45VXJ4j/near-capacity-WgPyJtEi/receipt.json`.
The tenant and checkpoint pilot remains open.

## Isolated KAI upgrade and recovery rehearsal

All six KAI 0.19.0 CRDs, its Config and its two default queues passed
server-side dry run. On a separate Kubernetes 1.34.3 kind cluster, Helm
installed 0.18.1 and upgraded to 0.19.0. The 0.19.0 admission and scheduler
Deployments became available and a CPU pod using `kai-scheduler` reached
Running. This single-node staging cluster omitted the production admission
anti-affinity and had no NVIDIA hardware.

Plain Helm rollback failed because the original
`kai-resource-reservation` Namespace was missing. A forward Helm upgrade
with the pinned 0.18.1 chart recovered the release, admission and scheduler.
A fresh CPU pod then reached Running through the restored scheduler.
Production remains on 0.18.1. A production-matched rollback and physical
GPU staging still require qualification.
Evidence is in `kai-019-api-validation-7K0ZhOUe`.

A second isolated upgrade rehearsed the production release layout, where
the reservation Namespace is absent from the installed KAI Helm manifest.
A production-aware Helm dry run confirmed the candidate leaves that
existing Namespace outside its release. The second Helm rollback restored
0.18.1, retained the Namespace UID, and preserved the CPU pod's UID,
container ID and Running phase. Helm left the BindRequest and Topology
CRD schemas at 0.19.0. The staging rehearsal restored both baseline specs
under resource-version checks after verifying their stored versions.
Readback matched all six baseline CRD version schemas. Hardware
qualification remains open.

The Fractioning 0.1.9 chart installed separately on the isolated cluster
and its CRD hook completed. KAI was then upgraded again to 0.19.0. The
Fractioning Config kept its UID and spec, eight running controller images
matched the digest lock, and KAI scheduled a new CPU pod. Fractioning
reported `NoTargetNodes` for the device daemons. The isolated cluster
remains on both target release versions for further staging.

KAI staging revision 8 uses digest-bearing image references in the
operator, the generated services, and the Helm hooks. The pinned overlay
was applied to staging, where all seven KAI pod specs and three hook Job
templates matched the image lock. Production still runs the previous
release.

## Recovery source after the gateway image rollout

A backup using the current scheduled template and gateway pin
`sha256:2d4578b7dbee657a41b84c364f990b9950646fd6b38a28fb2261fe9996fae53a`
completed and restored all four databases on
`compute-state-current-restore-1123095535`. The independent PV is retained.
Integrity, database and schema hashes, custody, and both cross-Hub allowance
orders passed on the restored copy. Both production authorities remained
available during the operation. Evidence is in
`current-image-restore-1QzWquSI`. The timed endpoint recovery and rollback
rehearsal remain open.

The current recovery input bundle `recovery-current-inputs-RbiQEPMy` captures
the two Gateway Deployments, backup CronJob, claims, PVs, EndpointSlices
and Fleet revision. It binds the standby specs to the exact source specs
and volume UIDs. The new standby claim has a live
`cps-current-restore-write-fence` admission policy and binding. A server-side
dry run accepted a read-only mount and rejected the otherwise identical
writable mount through that exact policy and binding. The standby has
no active writable pods. Both production Deployments remain on the
original authority. Endpoint handoff and rollback timing remain open.

The source-side `cps-current-authority-write-fence` is installed in
Warn/Audit mode. A source writable-mount dry run emitted the exact
policy/binding warning and a source read-only mount produced no warning.
The Deny/Audit binding render passed server-side dry run. Both gateways
remain available on the original claim. The source deny phase has not
been activated.
