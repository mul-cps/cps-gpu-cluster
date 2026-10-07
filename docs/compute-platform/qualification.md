# Qualification and releases

**The full platform is not production qualified.** Successful local tests and
configuration renders are necessary checks, not acceptance evidence for hardware,
real authentication, shared kernels or data recovery.

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
to the exact policy hash and verifies artifact SHA256 bytes. All scenario names
are required. It is an integrity check; an operator still reviews the validity
of the results. It does not enable profiles, deploy applications or issue releases.

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

Release blocks still include measured GPU isolation/packing and Hub GPU lifecycle,
JobSet launcher qualification, complete legacy grant migration, real browser/RTC
and Shares/NFS provisioning, expired-session/idle lifetime enforcement, actual
artifact retention and matching-version restore exercises. The referenced
application docs track the exact implementation boundary.

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
- The scheduled artifact retention template now uses the current script, image and policy. Its actual CLI dry run examined 25 objects with zero errors or deletions. Deletion remains suspended pending permanent provenance protection and mutation activation qualification.
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
PyTorch candidates additionally verify source hashes inside the fresh kernel.
The PyTorch code variant also
passes its CPU ML imports, native TorchVision NMS, in-memory datasets and
scikit-learn execution. GPU execution, isolation and browser/RTC acceptance
are separate gates. The minimal MuJoCo parent intentionally lacks MuJoCo;
physics and rendering belong to its descendant qualification.

The remaining parent/variant builds, common clean source-tag construction,
authenticated integration of the updated packaged artifacts, identity/grant
migration, GPU qualification, scheduling/startup/defragmentation and full
recovery gates remain open. No release or GPU access is enabled by these
candidate results. The generated release lock stays `unqualified` with an
empty qualified compatibility list.
