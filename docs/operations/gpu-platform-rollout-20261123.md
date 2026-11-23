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

The refreshed authenticated observer reached its cadence gate but did not
pass the all-samples criterion. Seven of 26 baseline cycles had at least
one timeout. A concurrent-request variant timed out in eight of 26 cycles
and was discarded. A separate probe measured bare Kubernetes exec at up
to 171 ms. Authenticated four-request batches sometimes took 1.09 s even
when every individual HTTP response and body was correct. The eight-probe
measurement remains unqualified at the original sample deadline.

Reusing one TLS context per Source batch produced three timeouts in 27
cycles. Combining TLS reuse with parallel GETs produced five timeouts in
26 cycles. Neither met the all-samples criterion, so both experiments were
discarded. The evidence is in the `observer-shared-tls-X9eIcJ7Q` and
`observer-parallel-shared-tls-10Er2YIo` directories under the refreshed
recovery input bundle.

Reusing a single verified HTTPS connection for each Source batch passed
all 48 consecutive live observer cycles across all eight endpoints.
The maximum gap between sample starts was 0.797 seconds. The probe still
pins Source pod and container identities, verifies TLS and response bodies,
and keeps the original deadline. Twenty-five offline cutover tests passed.
This read-only prequalification is in `observer-keepalive-iWvUCUEr`.

## SM-sharing canary scope

The released Fractioning 0.1.9 chart was rendered with SM sharing off and
on. Only the operator Deployment changed, via its `SUPPORT_SM_SHARING`
environment variable. The production operator targets all four upstream
workers through its single cluster-scoped Fractioning Config. Its node
selector controls the whole daemon installation. Restricting a workload
profile to one worker does not scope the operator feature switch.

The operator-managed SM-sharing canary therefore still needs isolated GPU
capacity under a separate installation, or a verified mechanism that can
scope the operator change to the test worker. Production remains on
`SUPPORT_SM_SHARING=false`. The exact release renders are in
`sm-canary-render-rYq2u6ze`.

## GPU4 eviction source trace

Fractioning 0.1.9 source `fb75540adca3392ab4b51d03e6c0da9b393fa842`
takes the assigned device from the KAI annotation and passes it through
`NVIDIA_VISIBLE_DEVICES` and CDI. It injects the independent memory request
and limit before the workload starts. The open R620.70.06 kernel code
charges video memory against `pGpu->gpuId` and sends the borrower
soft-limit event to the subdevice looked up by that same ID. The open
kernel release contains the notifier producer, while the logged MPS
ordinal conversion remains unattributed.

R620.73.04 is available in the upstream open-module source. The two
kernel files on this charge and notification path are identical between
R620.70.06 and R620.73.04. This does not establish parity of the MPS
userspace binaries or qualify the newer driver. Re-run the stored
cross-card witness with matched kernel and userspace versions before
considering an elastic rollout.

NVIDIA's R620.73.04 Linux production download lists the A100-SXM4-40GB.
The vendor archive passed its published SHA-256 check. Extraction
produced CUDA, MPS control, and MPS server binaries whose hashes differ
from the deployed R620.70.06 copies on GPU4. These artifacts support a
matched-version retest. NVIDIA's Ubuntu 26.04 CUDA package index still
listed R620.70.06 for the existing container build inputs, and the tested
R620.73.04 NGC driver image tags had no manifests. The extracted vendor
archive is not yet an operator-compatible driver image and has not been
installed. Evidence is in `gpu4-eviction-source-3CH3TS4Y`.

The disabled-dispatch gateway image was rolled back. Installed OpenAPI
inspection found that it lacked the production personal GPU reservation
route. The pod annotation indicated an earlier base source revision, but
the working image's OCI revision is `cef384b3558eb958c137f6ff25c03733cd18e087`
with an additional internal module pin. Fleet restored revision
`1de46bc9dc251d47c558fd998ad9da1f94720b9c`, the original image and backup
image pin. The restored gateway exposes the personal reservation route.
The next batch candidate must preserve the installed route set and be
tested against the live Hub compatibility contract before promotion.

The production-based GPU batch candidate preserves the installed package
outside seven batch-related files. Its installed-image suite passed 66
tests, including CPS and CIT personal GPU compatibility. The registry
image is pinned at
`sha256:531ec0539de3ea13a4efedb6e102e0cfc05d071b515a4d52bd18703de32ffb15`.

A disposable route-parity startup fixture used the current protected
references and a separate empty state directory. After adding the native
bootstrap init container, both the candidate and the incumbent image
failed with `Current group approval head changed during configuration`.
The existing production Pod remained available. This blocks the parity
test and requires recovery of the approval/bootstrap relationship before
relying on a fresh gateway start. Evidence is in
`gateway-source-parity-WQkiJQcn`.

The approval mismatch was caused by the empty-state fixture. Its registry
projection differed from the mounted bootstrap head, which matched the
live ConfigMaps. Both images successfully constructed their gateway
applications once given independent copies of the four restored databases
and a writer lock scoped to each temporary clone. The incumbent clone
matched all 50 live route and method entries. The candidate retained all
50 and added the checkpoint route. The source claim and retained snapshot
were not mounted writable. The restore contains database copies and needs
a verified writer-lock provisioning step before a real authority starts
from it. Production stayed on the incumbent image.

Fleet then deployed the route-verified image at revision `809c05f132b6`.
The authority bundle reported Ready, the gateway Deployment had one ready
replica, and the live OpenAPI route/method comparison retained all 50
incumbent routes and added only `/v1/workflows/{key}/checkpoint`. The
scheduled `compute-state-backup` Job template pins the same image.
GPU batch dispatch remains disabled in the mounted runtime configuration.
The live workflow inventory contained 17 succeeded and nine failed
workflows, with no active workflows. This verifies staged deployment.
The normal-user and approved-CI pilots remain open. See
`gateway-source-parity-WQkiJQcn/compatible-live-*.json` for evidence.

A manual Job from the current scheduled backup template recorded the
staged gateway image and policy hash in snapshot `20261123T102843.756798Z`.
An isolated restore to `compute-state-staged-restore-1123102832` passed
manifest SHA-256, SQLite integrity, required-table, and foreign-key checks
for all four databases. The independent PV uses reclaim policy `Retain`.
Evidence is in `staged-image-restore-TTHSgfGn`. This exercise did not
switch the production endpoint.

The deployed gateway image also passed the cross-Hub allowance check on
a disposable clone of the restored reservation database. Using one
synthetic canonical identity, CPS blocked CIT and CIT blocked CPS in
the two launch orders. The blocked source acquired the allowance after
confirmed release in each case. All 116 restored custody records were
clean, and all four restored database hashes stayed identical.
See `staged-image-restore-TTHSgfGn/allowance-result.json`.
