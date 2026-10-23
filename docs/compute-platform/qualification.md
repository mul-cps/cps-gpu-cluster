# Qualification and releases

**The full platform is not production qualified.** Successful local tests and
configuration renders are necessary checks, not acceptance evidence for hardware,
real authentication, shared kernels or data recovery.

The latest bounded results are in the
[2026-10-23 current-state ledger](current-state-20261023.md), including the
same-device CPS/CIT running pair and peer-safe shutdown. The October 12 lifecycle
below is historical, not the latest hardware result.
Earlier dated failures and pending statements below remain historical evidence;
the latest receipt supersedes them only for its exact scopes and measured pins.

Run configuration checks with `scripts/compute-platform/verify-config.sh`.
It verifies pinned chart checksums, catalog/generated artifacts, disabled staging,
console/store isolation, effective Loki retention, Alloy node discovery and narrow
Descheduler scope. It runs existing storage/Jupyter manifest checks. Public PRs
use GitHub-hosted runners; GPU qualification must be a trusted operator job.

`python scripts/compute-platform/qualify-admission.py --context CONTEXT --evidence
/PRIVATE/PATH/new.json` creates an isolated temporary namespace, parameter CRD and scoped admission
policy, checks API-server dry-run requests, then removes those resources. It runs
no workload containers. On 2026-10-05 the checks accepted a credential-free main
container and approved read-only executor mounts, and rejected automatic token mounts,
user secret environments/projected tokens, an untrusted executor image, an approved
executor image with an overridden command, loader environment variables, binary-shadowing
mounts, and shared process namespaces. The final ten checks passed; the preceding
eight-check suite also passed after cleanup/recreation. Generated Argo
Pods, kernel credential probes and failed artifact uploads remain separate gates.

Local fresh-kernel Papermill tests execute tagged typed parameters and a selected
Python helper import, retaining the executed notebook after success and an intentional
failure. This qualifies local execution; it does not establish live S3 transfer.

| Acceptance scenario | Required evidence before a release |
| --- | --- |
| Identity/storage | Reviewed university issuer/subject/person aliases; unchanged homes, named-server slugs/PVCs/NFS; one allowance per person |
| Authorization | Crafted gateway, admin and direct workload requests denied for resources, image, mount, queue, priority and entitlement bypasses |
| Permissions | Imported local grants survive login; expired grants stop being effective; instructor operations remain course-scoped |
| Collaboration | Two browser visitors retain their own identity while sharing RTC state; removed members lose existing access |
| Pooling | Cross-Hub simultaneous starts conflict atomically; rollback; shutdown-confirmed release; CPU/batch independent |
| Notebook jobs | Immutable saved notebook/files; typed tagged parameters; fresh kernel; authorized successful and failed executed notebook retrieval |
| Isolation | Intentional OOM respects the measured cap and its peer continues |
| Scheduling | Idle batch fill, teaching reclaim, protected sessions, bounded checkpoint retry and no distributed orphans |
| Startup | Representative pre-pulled CPS/CIT bursts: p95 ≤180s and maximum ≤300s |
| Defragmentation | KAI with/without fallback: free GPU availability ≥95% baseline; wait/start ≤110%; protected sessions unaffected |
| Recovery | Matching Hub/console/database/application restore, NFS archives, artifact ownership/retention |
| Moodle scaffold | Local CRUD and provenance references; no disabled side effects; enable fails; fake provider reconciles |

`compile_compute_policy.py --qualification-evidence FILE --check` binds evidence
to the exact policy hash and verifies artifact SHA256 bytes. All twelve scenario
names are required. `scenarioReports` must map every scenario to a distinct local
JSON report listed in `artifacts` with its SHA-256. Each report must declare the
matching `scenario` and `policyHash`, `passed: true`, and
`qualifiedScope: "production"`. Report parsing uses the same bytes that passed checksum verification, avoiding
a second file read. Shared report paths, missing references, failed
or fixture-only reports and checksum/content mismatches are rejected. Existing
blanket evidence bundles must be replaced with separately reviewed reports.

This is a structure and integrity check; report declarations do not independently
prove hardware results, real identity/permissions, measured timing thresholds or
recovery. An operator still reviews the actual results and attached logs against
the acceptance table. Controlled fixture reports in `platform-staging` are
supporting evidence, not production reports. The command does not enable
profiles, deploy applications or issue releases.

| Stage | Compute | Admin fork | Cluster / CIT | Notebook |
| --- | --- | --- | --- | --- |
| Pilot target | 0.1.0 | cps-v0.1.0 | v1.1.0 | 0.1.0 |
| Candidate target | 1.0.0-rc.1 | cps-v1.0.0-rc.1 | v2.0.0-rc.1 | 1.0.0-rc.1 |
| Production target | 1.0.0 | cps-v1.0.0 | v2.0.0 | 1.0.0 |

Python prereleases use PEP 440 equivalents. Preserve upstream admin tags and use
CPS-prefixed fork tags. Each release needs wheels, immutable image digests,
deployment artifacts, checksums/SBOMs, compatible Hub/chart/policy/upstream versions,
migration/rollback procedures and qualification artifacts. Build all notebook
variants from the same clean tagged source and promote the same tested bytes.
Never fabricate image digests or publish a production tag to unblock staging.

Release gates must be assessed against the latest ledger: controlled GPU
isolation, shared lifecycles, RTC/revocation and artifact-retention checks have
passed within their recorded scopes. Broader GPU packing/scheduling, startup
bursts, JobSet, hard-maximum expiry, complete identity/grant migration, final
variant integration and matching-version full restore still require their own
evidence. Earlier dated pending statements below do not invalidate later passes.
The referenced application docs track the exact implementation boundary.

## 2026-10-05 live staging evidence

Persistent NetBird relay recovered after a Deployment restart, preserving peer identity. Both CPS and CIT Hub Pods reached the artifact service with normal DNS and verified TLS; anonymous bucket access returned 403. Signed 50 MiB upload/download and cleanup passed through the relay.

Private Argo 3.7.18 controller/server deployed with image digests, scoped client authentication and operator-signed TLS. Restricted Pod Security and the compute admission policy admitted the qualified executor shape. Operator-controlled CPU notebook tests passed success and deliberate-failure outcomes; both executed notebooks were downloaded and hash-recorded, with selected local imports and typed parameters working. Main containers had no Secret mounts and automounted API tokens were disabled. Runner/executor UIDs must agree: 10001 is the staging baseline.

Evidence is held privately under `cps-platform-evidence/2026-10-05/notebook-live/results.json`. Runner image: `ghcr.io/mul-cps/cps-compute:qualification-a7abe7d13465a8ea@sha256:f107b407f3e6c9218a4a9b5ec4df9f0ea013f4abd0a177e474013ff6b682c893`. Operator-test policy hash: `sha256:46078b979b4c04fde933ab72c48e558fd5e15a8c604f13f0aa0e950c046d8a00`. This is runner/admission/artifact evidence, not end-user gateway authorization or a production release.

KAI 0.18.1 staging components are healthy. The pinned HAMi isolator is restricted to the operator qualification namespace. A nominal 5 GiB allocation rejected a 6 GiB allocation while a peer on the same physical GPU continued running. KAI rounding produced a measured 5324 MiB cap; this does not qualify nominal 10/20 GiB packing, MPS throughput or production scheduling. Non-root HAMi cache creation reported a permissions warning, so per-container telemetry remains unqualified.

A new operator-only retained NFS dataset passed write/read checks through unchanged server `193.170.30.58`. ZFS archival preserved its contents; a subsequent writable client mount received server-side `EROFS` on write. This qualifies the NAS mechanism, not the complete console/controller lifecycle. No existing home or shared data was modified.

At the time of this 2026-10-05 evidence, email setup and linkage were deferred.
The later user decision makes email verification optional, not mandatory.
University federation linkage uses exact issuer and upstream subject with
reviewed aliases; matching email or display names never activates allowances.
Direct university Dex login still awaits ICT registration. The dated results
above do not supersede the newer qualification evidence below.


## 2026-10-06 qualification update

The full platform remains unqualified; no pilot, candidate or production release
is established by these individual checks.

- [Notebook and artifact data path](../../platform-staging/gateway-qualified/qualification/notebook-artifacts.md): actual gateway handlers, real Argo and SeaweedFS over the relay passed controlled success/failure, snapshot, supporting files, typed parameters, ownership checks and retention fencing. Synthetic workspace principals were used; human Hub OAuth and the final notebook image matrix remain separate gates.
- [Current-version database restore](../../platform-staging/gateway-qualified/qualification/backup-restore.md): both consoles and the gateway passed fresh, matching-image/policy backups and isolated database/application-open restores. Full Hub authentication, populated migration and offsite recovery remain open.
- [Combined GPU isolation](../../platform-staging/scheduler/qualification/runtime-isolation.md): normal OOM and peer continuation passed, but a crafted process bypassed the nominal cap by disabling MPS and HAMi participation. This contradicts runtime isolation qualification; ordinary GPU profiles remain disabled.
- The scheduled artifact retention template uses the current script and policy. A [fresh live-template dry run](../../platform-staging/artifacts/truenas/retention-current-dryrun-report.json) examined 37 objects with zero errors, deletions or metadata reconciliation; its temporary Job was removed. This checks the deployed CLI and read path, not the newest gateway image or mutation recovery. Scheduled deletion remains suspended pending mutation activation qualification.
- The CPU notebook overlay and Xpra parent image builds are ongoing. The complete twelve-variant image/release matrix remains open.
- Four operational dashboards retain explicit unavailable/stale telemetry and now link to both admin consoles and internal TrueNAS. The private Argo operator UI route and the required controller telemetry remain open.

Existing authenticator group management remains in place until reviewed grant
migration and login-survival qualification. No cross-Hub global allowance is
activated by username/email matching. Real two-visitor RTC, member removal,
pooled starts, teaching reclaim/protection, startup bursts, defragmentation,
distributed cleanup and full recovery remain required acceptance scenarios.


## 2026-10-07 matching candidate qualification

The [partial candidate inventory](../../platform-staging/network/qualification-candidate-set-6bb6a57.md)
records the gateway, admin and notebook images built against compute source
`6bb6a57bc8d8426e281c0654ac8eedd1668ae600` and wheel checksum
`05d82345b0f65a3a94c715c68788f52d14c545cba41a5e622249870e0e848667`.
The adjacent JSON pins each remotely verified image index and Linux manifest,
links its exact qualification evidence and records the remaining notebook count.
This inventory is not a deployment or promotion lock. Its production image
snapshot has its own observation timestamp; adding a candidate does not update
that production observation.

Matching notebook candidates pass forced offline wheel installation and
installed SDK/addon source hash checks. Fresh kernels verify typed parameters,
immutable input and retained success/failure notebooks. The MuJoCo parent and
PyTorch and TensorFlow candidates additionally verify source hashes inside the fresh kernel.
The PyTorch code variant also
passes its CPU ML imports, native TorchVision NMS, in-memory datasets and
scikit-learn execution. The TensorFlow candidate passes CPU matrix operations,
gradients and a Keras training batch. GPU execution, isolation and browser/RTC acceptance
are separate gates. The minimal MuJoCo parent intentionally lacks MuJoCo;
physics and rendering belong to its descendant qualification.

All twelve matching notebook variants now have remotely verified candidates.
Common clean source-tag construction,
authenticated integration of the updated packaged artifacts, identity/grant
migration, GPU qualification, scheduling/startup/defragmentation and full
recovery gates remain open. No release or GPU access is enabled by these
candidate results. The generated release lock stays `unqualified` with an
empty qualified compatibility list.

The ROS desktop and ROS Xpra candidates pass local ROS Jazzy pub/sub through
the separate system Python interpreter. Xpra variants pass isolated HTML HTTP
and live XFCE checks; the MuJoCo descendant also passes CPU physics. ComfyUI
passes CPU HTTP startup, persistent data/database creation and a saved latent
workflow. The ROS and ComfyUI full standalone SPDX/native inventories are
verified locally and as remote referrers bound to exact image subjects.
These checks exclude GPU execution, model inference and browser interaction;
the inventory remains a partial platform qualification with no promotion.

The [packaged gateway storage refusal probe](../../platform-staging/artifacts/truenas/gateway-6bb6a57-storage-guard.md)
passes internal service authorization and active-parent refusal for CPS/CIT
under the actual controller service account. It makes zero NAS calls and uses
only temporary databases. That refusal probe excludes successful storage lifecycle, actual Hub ownership,
shutdown and production HTTP/OAuth.

The [current packaged gateway V2 HTTPS lifecycle](../../platform-staging/artifacts/truenas/gateway-6bb6a57-v2-http-qualification.md)
passes bounded CPS/CIT registration/provision/idempotence/archive checks through
a real Hub fixture, forced NAS RPC and quota-compatible verifier Jobs. The
preceding refusal probe covers V1 only. Full admin/Hub/browser integration,
production identity/grants, privacy, handover, recovery and GPU gates remain open.

The [legacy Dask transition evidence](../../platform-staging/network/legacy-dask-transition.md)
now also covers WorkerGroup scale PATCH/PUT dry-runs for both isolated
principals: baseline allowed, guard denied, operator allowed, zero replicas
preserved and no execution Pods created. Production transition remains disabled.

## 2026-10-08 live acceptance checkpoint

The [current checkpoint](../../platform-staging/releases/qualification-20261008.json)
pins the compute/admin candidates and keeps production qualification false.
The [CPU coordination run](../../platform-staging/scheduler/qualification/dynamic-coordination/LIVE_CPU_20261008.md)
passed actual KAI CPU scheduling, API-server webhook transport, native UID/resourceVersion
binding preconditions and exact original-Pod cancellation. The real API server's
webhook timeout query exposed a routing defect; the fix and 54 source tests pass.
The isolated webhook was removed and its service stopped. No GPU workload or
production admission configuration was changed. Positive GPU generation sealing
and KAI GPU preBind/rollback integration remain unqualified.

Fresh private CPS/CIT database/config backups preceded the personal Argo rollout.
Both databases [restored logically](../../platform-staging/hub-backups/logical-restore-20261008.json)
inside isolated local containers using their exact running PostgreSQL images.
This excludes source-row/ACL comparisons, connected Hub authentication/spawning,
NFS archives and off-host recovery.

The [CPU runtime preflight](../../platform-staging/scheduler/qualification/mps-dynamic/uid-cpu-preflight-20261008.json)
checks UID 1000/GID 100 and private scratch/cache permissions in the proposed
immutable runtime on GPU2, with zero GPU requests and no CUDA initialization.
The idle MPS server still uses UID 10001. That mismatch requires a separate
bounded compatibility test before mixed dynamic sharing; no MIG or GPU-mode
change was made. Browser OAuth qualification and the missing ICT filer
hostname/export remain explicit external gates.

A later GPU2 no-MIG canary tested native R615 Pod-parent cgroup memory limits.
Stock managed memory bypassed those limits. A pinned experimental UVM guard
then denied the tested fresh managed allocations and passed ordinary CUDA
OOM/recovery and PyTorch 2.11 allocation/OOM/recovery at a 5 GiB cap. Each
matrix retained 597 successful independent peer heartbeats. The earlier
512 MiB PyTorch failure remains inconclusive. See the
[actual no-MIG results](../../platform-staging/gpu/qualification/r615-uvm-guard/actual-outcomes-20261008.md).

The experiment used manual cap assignment and fresh independent contexts.
Automatic node reconciliation, driver-reload generations, restart/cancellation
races, imported/shared VAspaces, managed globals and MPS interaction remain
unqualified. GPU group profiles remain disabled; this checkpoint does not
activate the experimental driver or claim hostile tenant isolation.

GPU2 returned to its original operator-owned R580 driver, with both A100s
MIG disabled, GPU services Ready and the node uncordoned. Protected CPU/PVC
identities and readiness were checked. Toolkit recovery restarted
K3s/containerd. The verified independent firmware directory/search path
remains required because the usual firmware path is empty. The
[rollback receipt](../../platform-staging/gpu/qualification/gpu2-r615-canary/rollback-receipt.md)
records that temporary deviation and removal of the owned canary/test objects.

## Earlier 2026-10-09 automatic cap and admin checkpoint

The controlled GPU2 no-MIG group pilot passed automatic 5 GiB cap assignment.
Pod UID prefix `696bab5d` completed its first gate with exit code `0`; native
limit readback was `5368709120` bytes. The notebook container never executed:
its management CDI GPU UUID was unresolved. Shutdown cleanup then remained
blocked by NVML result `17` when querying the removed cgroup. This does not
qualify notebook startup, automatic cleanup or release of the associated
allowance.

Root corrected the supplemental CDI file
`/var/run/cdi/management.nvidia.com-native-pilot-r615.json`, SHA256
`55d23389ef8745a9ffef4b58181ed350f549100b03d7f8e7cb9590ae4f3bc5fd`.
It contains only `GPU-16128952-b438-556a-00bb-93039ee24e56`; 57 current R615 mount
paths were validated, and `nvidia-ctk cdi list` resolves the UUID. This correction
has not yet passed actual notebook startup or the group OOM/peer matrix. The
[node-authority runbook](../../platform-staging/gpu/native-group-pilot/README.md)
also records the required resolved-host `--crictl` override; an absolute k3s
`data/current` symlink is unusable beneath the container's `/host` mount.

At 14:17 UTC, independent read-only verification found both admin services Ready
on `ghcr.io/mul-cps/e2x-course-hub@sha256:1689e38c6f87cb1d75e6186a2a177afb3f0e0c8a2ab28e5b79d094ac72851845`
(source `54cead22f03bed6e37f998b43eaaaab913dbd3d6`). Running as UID/GID
`10001:10001`, each service read and parsed the same current directory-mounted
status ConfigMap, updated at `2026-10-09T14:14:42.099193Z`; all 45 Python source
files and three compiled UI assets matched the qualified image receipt. The
status panel reports cap assignment **passed**, startup and shutdown cleanup
**blocked**, and ordinary group GPU access **disabled**. Its mounted status is
refreshed rather than pinned by a `subPath` mount. CIT human OAuth/browser
acceptance remains unverified.

Root separately observed both Hubs Ready on
`ghcr.io/mul-cps/cps-compute@sha256:05b47ef4d78840d58907c3416903d5150c4af98ed8c390499ce93d42cf36be70`.
Deployment readiness does not establish a successful shared GPU notebook.
Group startup, OOM/recovery, peer continuity, restart, native shutdown cleanup,
cross-Hub reservation and MPS qualification remain open. This checkpoint is
sanitized operational evidence and does not enable general group GPU sharing.

## 2026-10-09 qualified no-MIG group pilot

The later [actual runtime receipt](../../platform-staging/gpu/native-group-pilot/qualification/qualified-runtime-receipt-20261009.json),
reviewed at `2026-10-09T21:28:09.230649Z`, closes the earlier startup, isolation,
restart and cleanup blockers for **only CPS `native-group-b` and CIT
`native-group-a`**. Policy `0.1.1`, hash
`sha256:78fb2d7ca42585a000e58b52c297d072a11dfbc466b19f50aa9d276d567a413f`,
admits canonical `interactive-shared-5` on the selected physical A100 on GPU2,
with a native 5120 MiB cap per workspace and at most two workspaces, without MIG.

All six [bounded hardware gates](../../compute-policy/qualification/native-groups-v1.json)
passed: cap assignment, OOM with peer continuity, aggregate accounting, memory
import, restart cleanup and MPS. Both normal source profile handovers and six
profile-only grant updates passed. CPS used authenticated console Start; CIT
used its controlled owning source service. Both normal starts and real CUDA
positive/recovery controls passed with exact caps and stable physical identity.
Original registered storage identities were preserved. Both fixtures stopped,
native reservations released, and immutable zero-charge retirement evidence
remained. CIT's first 409 completed through the same normal Close resume. These
results do not establish human CIT OAuth or browser collaboration.

The [current release-candidate inventory](../../platform-staging/releases/qualification-20261009.json)
binds actual source commits, wheel/module hashes, immutable images, policy and
receipt hashes. Its [local verifier](../../platform-staging/releases/README.md)
reuses the existing policy compiler and six-report validator. Gateway/Hubs/admin
use SDK `a5a75b7…`; the notebook and cap gate intentionally retain their distinct
measured SDK builds. Thus the older complete twelve-image build remains a
historical candidate, not a current matching SDK/runtime release matrix.

Whole-platform acceptance remains open for:

- Human CIT OAuth and browser collaboration, general reviewed identity/grant
  migration and same-person simultaneous cross-Hub pooled accounting.
- Representative pre-pulled teaching bursts, reclaim/protected sessions,
  production distributed workloads and KAI/Descheduler defragmentation comparison.
- Cap/Descheduler telemetry qualification, physical free-GPU measurement and
  operational storage/retention sizing.
- Scheduled artifact deletion and ambiguous-delete/crash recovery; coordinated
  connected Hub/application/NFS recovery and approved off-host durability.
- A current SDK matching twelve-image runtime matrix, reviewed integration/Fleet
  promotion, compatible release artifacts and actual release tags.

The general compiler release lock and whole-platform production qualification
remain `unqualified`. The two-scope pilot is an observed qualification snapshot,
not a continuous operational heartbeat or approval for other profiles,
workspaces or the eight-GPU fleet. Moodle remains planned/disabled, Hub 6 remains
a separate target, and direct university Keycloak login through Dex still
depends on ICT registration.

## 2026-10-11 mixed 5/10 GiB qualification checkpoint

Controlled, normal Source starts on the selected GPU2 A100 assigned a 5120 MiB
cap to CPS `native-group-b` and a 10240 MiB cap to CIT `native-group-a`, without
MIG. Profile handovers preserved the existing storage identities and CPU
permissions. The measured policy hash is
`sha256:02316f90f705f5550ab54d1d514ed48f73aa6a13324eea7d4aeaaef959af2fd5`.

The main hardware phases passed: real kernel/recovery controls, typed OOM
with peer continuity, aggregate accounting, same-parent positive controls,
bidirectional cross-workspace IPC/VMM denial, and scoped MPS OOM/recovery and
process cleanup. The separate creator-exit test passed retained VMM backing
accounting, subsequent release and final zero charge. MPS reached OOM early;
this does not establish a sustained 120-second MPS load. One VMM attempt failed
because its private bridge directory had not been created. That failed attempt
remains inconclusive; the independently captured fresh retry passed.

Both genuine Source Stops completed. CIT's initial cleanup-pending 409 was
retained and the same normal Close operation succeeded after controller cleanup.
The complete native ledger held 21 released records. Protected host observations
retained the eight prior inert caps and added exactly these two lifetimes, with
finite 5/10 GiB limits, offline pinned accounting and zero charge. All three
qualification notebook Pods were absent.

The frozen automated Stop inspector failed because it compared the raw journal
file digest with the cleanup receipt's canonical JSON digest. Independent Root
review verified the full original journal, identity, intent and retirement proof:
the raw file is the same canonical record plus its stored newline. The failed
inspector was not relabeled as passing. Its correction and fresh mixed-profile
normal restart/kernel/final-Stop acceptance remain open. This checkpoint does
not qualify 20 GiB profiles, new workspaces or the wider GPU fleet.

Twelve audited membership/grant expiry updates restored the original expired
values. Complete before/after readbacks differed only in those expiry fields;
profiles, course ceiling, aliases, storage and the version 2 native history
remained intact. Both admin consoles returned to one Ready replica and the
temporary operators were removed. The archived
[admin assessment](../../platform-staging/admin-status/qualification-20261011.json)
uses `qualification`, with mixed-profile restart pending and general GPU group
access unavailable. Its timestamp remains a qualification snapshot; do not
reapply it as a fresh availability assessment.

## 2026-10-12 limited group lifecycle and personal Argo source checkpoint

The immutable [measured results](https://github.com/mul-cps/cps-gpu-cluster/blob/079b2b60e7a5fd88c305febada90afec152c81f8/platform-staging/gpu/native-group-pilot/qualification/limited-group-20261012/measured-results.md)
and [lifecycle receipt](https://github.com/mul-cps/cps-gpu-cluster/blob/079b2b60e7a5fd88c305febada90afec152c81f8/platform-staging/gpu/native-group-pilot/qualification/limited-group-20261012/lifecycle-acceptance.json)
close the earlier mixed-profile restart and normal Stop gate for exactly CPS
`native-group-b` at 5 GiB and CIT `native-group-a` at 10 GiB on the selected
GPU2 A100, without MIG. The measurement is bound to policy hash
`sha256:4f1dff1a92aba5cd7376dfb897612b7e6f2e6f15a09515dbdf29efa4c522359d`.
Normal Start/Stop/restart/Stop passed; both replacement Pods received automatic
finite caps and executed 33 verified kernel ticks. All four lifetime Pods were
absent at final inspection, all 35 allocation records were released, and the
retained offline native rows had zero charge. These are dated observations,
not a continuous availability assessment.

Fresh OOM/recovery and independent peer continuation, 120-second two-client
MPS at the 10 GiB cap, and same-workspace IPC/retained VMM controls passed.
Fresh cross-Pod import denials were not exercised for those lifetimes. The
results do not qualify 20 GiB profiles, additional groups, the eight-GPU fleet,
same-person concurrent cross-Hub starts or human CIT OAuth/RTC collaboration.
CPS used authenticated console HTTP; CIT used the trusted normal console
manager. Their authentication evidence is kept distinct.

The later [source/admin verification](https://github.com/mul-cps/cps-gpu-cluster/blob/079b2b60e7a5fd88c305febada90afec152c81f8/platform-staging/gpu/native-group-pilot/qualification/limited-group-20261012/post-publication-verification.json)
records the corrected teardown source suite: 280 native tests and 161 cluster
tests with 139 subtests passed. The GPU runtime was unchanged and the original
failed test run remains preserved. Source54 passed 44 UI tests and TypeScript/
Vite; Root confirmed the grant workspace selector in both public assets and
restored four temporary grants and four memberships after physical shutdown.
The [source-only personal Argo receipt](../../platform-staging/argo/personal-activation-20261012/source-acceptance.json)
records the current immutable gateway, console and private frontend pins.

Private frontend acceptance covers actual user information, an empty owned
workflow list, ignored injected identity headers, bearer-only login rejection,
and absent-object privacy. Its fixture is explicitly a Root-signed cookie with
a real Hub user token. Human browser OAuth, nonempty own-versus-foreign workflow
and artifact access, successful/failed current notebook runs and public personal
Argo routing remain pending. Both prepared personal ingress settings stay false.
The historical five-GiB release inventory remains a historical snapshot, not a
validator for this mixed-profile measurement. General GPU access and the
full-platform release lock remain unqualified. The scheduling, collaboration,
recovery and release gates listed above remain open; Moodle stays disabled,
Hub 6 stays separate, and direct university Dex login awaits ICT registration.


## 2026-10-12 CPU policy and current private Argo follow-up

The [CPU-only policy revision](../../platform-staging/gpu/native-group-pilot/qualification/cpu-runner-policy-20261012/README.md)
adds the locally qualified immutable notebook runner `1fab0663…` to `batch-cpu`
at two CPU cores and 8 GiB. Its compiled version is `0.1.2`, hash
`sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0`.
Local rootless UID 10001 success and intentional failure retained their executed
notebooks; local acceptance does not establish cluster artifact delivery.
The original GPU measurements remain byte-identical, and compatibility
attestations do not claim new GPU measurements. Exactly the reviewed CPS
five-GiB and CIT ten-GiB group scopes remain; no wider GPU profile is enabled.

Root's [dated historical custody receipt](../../platform-staging/argo/personal-activation-20261012/cpu-policy-historical-custody-receipt.json)
records immutable node ConfigMap `cps-native-node-cpu-v2-d48f6553ed03-h32`,
preserving all 28 original history rows and adding four proved released
lifetimes. Native runtime source is unchanged. Protected ledger and journal
records were retained separately and must not be replaced by a source recipe.

The [current private Argo inventory](../../platform-staging/argo/personal-activation-20261012/source-acceptance.json)
records gateway `d3f744bd…` and both dedicated frontends `7e150996…` from Root's
sanitized deployment receipt. Its [partial private acceptance](../../platform-staging/argo/personal-activation-20261012/current-private-partial-acceptance.json)
returned owned list/detail 200 and artifact HEAD 200, while actual artifact GET
returned 502 and logs 503. Foreign and absent detail/log/artifact requests
returned 404. Artifact bytes and logs remain unqualified. Authentication was
Root's signed cookie with a real Hub user token; human browser OAuth and public
personal routing remain pending, and both prepared ingress flags remain false.
These receipts are dated observations, not ongoing availability checks. General
GPU access and the full-platform release remain unqualified.


## 2026-10-12 private owned Argo byte and log acceptance

Root's later [sanitized private owned receipt](../../platform-staging/argo/personal-activation-20261012/current-private-owned-acceptance.json)
closes the earlier private artifact GET/log failures for the same pinned gateway
and dedicated frontends. The preceding 502/503 receipt is preserved unchanged.
Own success/failure list and details, executed-notebook GET/HEAD and logs
returned 200. The owned list contained only the two authorized runs. Actual
foreign workflow detail/log/artifact failures matched missing objects with the
same 404 body. Retrieved notebooks preserved typed parameters and selected
helper execution; the successful run returned 42 and the failed notebook retained
its intentional RuntimeError. This qualifies the private CPS workflow and
artifact path with Root's signed cookie containing a real Hub user token.

The dedicated backend reader Role from source
`c8335b4bf20f531b6c2fb59f4dd77c77dd524331` allows only named `get` for artifact
credentials and CA Secrets. Root's actual bearer SelfSubjectAccessReview
allowed those reads and denied unrelated Secret reads and Secret listing.
Browser frontends retain no Kubernetes identity or artifact credentials.
Human browser OAuth, public personal ingress, human CIT/RTC collaboration,
same-person cross-Hub concurrency, broader GPU/fleet and complete release gates
remain open. Both prepared ingress flags and general production qualification
remain false. Dated receipts do not establish continuous availability.
