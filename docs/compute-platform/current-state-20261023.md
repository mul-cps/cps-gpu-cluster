# Current platform state — 23 October 2026

The full platform remains **limited-pilot**, not production qualified. As of
24 October, journal30 and Gateway `bff495fb…96a1524` are active. The fresh-readback
optimization passed normal-console shared 5 GiB Start/CUDA/Stop/restart/CUDA/Stop.
First Start returned in 208.80s (Ready194.15s), and restart in219.65s
(Ready207.11s), compared with258.67s and249.05s before this change. Both Pods kept
stable identities and passed a trusted64MiB CUDA operation. Startup still exceeds
the180-second target; representative CPS/CIT bursts remain unqualified.

The runtime source passed5,410 full-suite tests and68subtests (six skips), with
four additional post-collection boundary cases verified separately. Independent
review approved source and actual handover manifests. All nine exact targets are
Ready, all four current components agree, the original anchor and prior29 journal
rotations are preserved, and all54 Source records remain unchanged. Final Stop
released both ledgers; both GPU2 devices have zero allocated memory and no compute
clients. The scoped test token is revoked and both local credential copies are
removed. Existing user Pods are preserved. Node72, Hub/notebook images, drivers,
kernels and storage are unchanged. Full-pool, application, recovery and release
gates remain open.

The sections below are chronological acceptance history. Later completed gates
supersede earlier pending statements for the same scope. Daily artifact retention
is now active and scheduler-verified; see the final retention activation section.

## Latest shared-GPU addon activation

The shared-GPU notebook image `fb9872bf…d32a45` is now deployed through the
reviewed image-only policy edge `2054ee32…e1a1fb`. Its preservation verifier
retains the original hardware proof, 83 base layers, SDK and dependencies.
All eight control services are Ready; the original delivery anchor and first
three rotations remain intact, with a completed fourth rotation. Normal capture,
writer, consoles and service selectors are restored.

A normal CPS shared 5 GiB start completed in 120.885 seconds. Ten installed addon
payload files matched the wheel, 30 SDK modules were unchanged, and a 64 MiB CUDA
allocation passed. Normal close took 16.971 seconds; automatic KAI reservation
cleanup followed in 4.611 seconds without a Binder restart. All 15 native claims
are released and no kernel cap is online. The two existing user notebook Pods
were preserved; temporary operator Jobs and reader credentials were removed.

[Activation evidence](../../platform-staging/argo/qualification/profile-walltime-20261023/addon-image/activation/verification.json)
retains the exact scope and operator fixes (163 delivery regression tests).
This updates the shared-GPU image, not every CPU/other notebook variant. Browser
visual acceptance and CIT student workflow acceptance remain open.

## Remaining variants and CIT student acceptance

The CPS CPU runtime candidate is published as `efc3b485…b6eb72f`. Its full
software-preservation verifier passes with 72 original base layers retained,
43 SDK modules unchanged and 315 other dependency versions unchanged. Both default CPU configurations are now deployed; live acceptance is recorded below. CIT CPU addon checks pass with 48 SDK
modules and 321 other dependency versions unchanged; corrected runtime image `4d945601…baa7289` is published and its full preservation
verifier passes, retaining all 52 original base layers and the original `jovyan` user. Both controlled students, Armin and Mikasa, completed fresh ordinary
CIT directory login at `jhub.dshl.unileoben.ac.at`; Hub identity reads returned
200 with `admin=false`. After the explicit reviewed aliases were added to a new immutable Gateway runtime
secret, fresh temporary student tokens pass both Compute `/v1/me` and `/v1/profiles`
(200). Their canonical identities match the existing CPS people; no new person or
allowance was created. Both tokens were revoked. Only the two runtime aliases changed;
images, policy and native authority remain unchanged. The Gateway is Ready, and the
normal writer returned to Ready at the unchanged scoped Source revision after the
observer automatically granted the new Pod's exact named-read permissions. Source
identity auditing and broader CIT batch/collaboration acceptance remain open. Email
verification was not fabricated or required for these explicit test-account aliases.
The initial browser harness used an incorrect hostname and was corrected from
live ingress readback; no DNS, identity mapping or permission settings were changed.

[Variant and student acceptance evidence](../../platform-staging/argo/qualification/profile-walltime-20261023/addon-image/variants/progress.json)
contains the bounded progress, with separate login and API read receipts.

## CPU image deployment and CIT browser acceptance

Both Hubs now mount new immutable values Secrets containing the verified CPU
image digests. Other values were retained byte-for-byte. The initial attempt
changed dormant Helm Secrets; these were restored after Pod readback revealed
that the live Hubs mount versioned immutable Secrets. Both control Pods are Ready,
and the normal runtime writer returned to Ready at the unchanged scoped revision.
The existing research notebook Pod UIDs remained unchanged throughout.

Armin launched CIT `cpu-small` normally on image `4d945601…baa7289` and reached
JupyterLab in 28.877 seconds. The addon and server extension are installed. The
isolated browser verified his canonical Account identity, My Workloads without
stale-data errors, and dynamic snippet recipe generation after selecting his
permitted profile/project and a notebook path. No snippet was executed. Disabled
JobSet listing returns 503 but does not prevent ordinary workflow listing. CPS
personal CPU live launch, CIT submission/collaboration, snippet insertion/copy
and full release integration remain open.

[CPU image activation](../../platform-staging/argo/qualification/profile-walltime-20261023/addon-image/variants/cpu-image-activation.json)
and [CIT browser receipt](../../platform-staging/argo/qualification/profile-walltime-20261023/addon-image/variants/cit-addon-browser.json)
record this bounded acceptance. The staged operations are not yet a merged GitOps release.

## CPS browser and CIT batch acceptance

Mikasa launched CPS `cpu-default` normally on image `efc3b485…b6eb72f` and reached
JupyterLab in 33.498 seconds. After dismissing the unrelated Notebook Intelligence
welcome tour, normal Compute OAuth, canonical Account identity, My Workloads and
dynamic snippet recipes passed. The browser still reports a separate enhanced
cell-toolbar shared-module dependency warning; notebook packaging follow-up remains
open. No snippets were executed by this browser check.

CIT student Armin submitted both a successful and intentionally failing notebook
through the authenticated Gateway. Both terminal phases matched expectations; typed
parameters, explicitly selected Python imports, stripped stale outputs, executed
notebook artifacts on success/failure, same-UID idempotent retries and Mikasa's
foreign-owner 403 denial all passed. Both temporary student API tokens were revoked.
This verifies Gateway batch execution, not yet notebook-GUI Submit or SDK execution
from the live CIT notebook. CIT collaboration, source identity audit, distributed
qualification and release integration remain open.

[CIT batch evidence](../../platform-staging/argo/qualification/profile-walltime-20261023/addon-image/variants/cit-batch-acceptance.json)
and [CPS browser evidence](../../platform-staging/argo/qualification/profile-walltime-20261023/addon-image/variants/cps-addon-browser.json)
retain the bounded checks and observed console warnings.

## CIT notebook GUI and installed SDK submission

CIT Armin submitted through the actual addon Submit form, including a saved
parameterized notebook and a selected helper file. The job succeeded; executed
output, preservation of original saved outputs and visibility in My Workloads
passed. A privacy notification initially intercepted the browser test's click;
normal notification dismissal cleared it. Four owned test notebooks were removed
through the student's Contents API after acceptance.

The installed SDK initially failed because the chart's notebook egress policy
excludes private cluster ranges. The new staged/live `notebook-sdk-network` overlay
adds only notebook-to-Gateway TCP 8000 egress in both Hub namespaces. Rendered specs
match live readback. The unchanged installed CIT SDK then authenticated as Armin,
submitted parameters and a selected helper file, and retrieved the executed result.
Unauthenticated API access remains 401; private capture port 8001 remains unreachable.
CPS SDK execution, CIT collaboration, source identity audit and release integration
remain open. This does not qualify distributed or GPU batch execution.

[GUI receipt](../../platform-staging/argo/qualification/profile-walltime-20261023/addon-image/variants/cit-gui-submit.json),
[installed SDK receipt](../../platform-staging/argo/qualification/profile-walltime-20261023/addon-image/variants/cit-installed-sdk.json)
and [network overlay](../../platform-staging/notebook-sdk-network/README.md) retain
this acceptance and the root-level connectivity correction.

## CPS SDK and CIT two-student collaboration

The installed CPS SDK authenticated as Mikasa, submitted a parameterized notebook
with a selected helper file and retrieved the successful executed result. Her
personal test server then stopped normally; research notebook Pods were preserved.

CIT Source now contains audited explicit aliases for Armin and Mikasa, using their
existing canonical IDs and reviewed directory provenance. Root management used the
normal provider identity-review service after checking both exact owning Hub
accounts and non-admin status, with actor `operator:kubernetes:u-vhm9n`; this was
not a browser-admin login or fabricated email verification.

A separate CPU-only course/group/workspace `student-collab-20261023` was provisioned
through normal provider/lifecycle services. Existing GPU qualification records
were not modified. Two real student browser sessions opened the neutral named
server through ordinary OAuth and observed each other's edits without executing
cells. Hub identity reads remained Armin and Mikasa, both non-admin. SDK identity
inside the shared server was the workspace principal, not either visitor.

This RTC run uses the existing registered shared-CPU image `9444a023…1df7f`, not
the newly updated personal CPU image. Shared-CPU image refresh, active-member
revocation/restart and broader release integration remain open. The fixture
initially had invalid creation ordering and an explicit zero GPU ceiling; backend
validation rejected both, and the stopped owned fixture was corrected without
weakening policy.

[CPS SDK receipt](../../platform-staging/argo/qualification/profile-walltime-20261023/addon-image/variants/cps-installed-sdk.json),
[CIT RTC receipt](../../platform-staging/argo/qualification/profile-walltime-20261023/addon-image/variants/cit-rtc-browser.json)
and [shared-kernel identity receipt](../../platform-staging/argo/qualification/profile-walltime-20261023/addon-image/variants/cit-shared-kernel-identity.json)
record the bounded acceptance. Full production qualification remains incomplete.

## Refreshed CIT shared CPU and active member revocation

The registered CIT shared-CPU image now selects the verified `efc3b485…b6eb72f`
image through a new immutable mounted values Secret. Only that CPU image reference
changed; native policy, GPU images and authority remain unchanged. Actual shared
Pod readback selected the new image, and SDK identity remained the workspace principal.

With Armin and Mikasa editing the neutral workspace in separate browser sessions,
normal Source member removal stopped the writer, updated access/membership, left
no active reservation and returned a kernel-interruption/files-retained notice.
The final live browser run tracked eight open, frame-receiving collaboration sockets
per visitor from the current document; every one closed after removal within the
unchanged 15-second observation bound. An earlier assertion retained obsolete
protocol handles across navigation; its diagnostic counts and corrected capture
criteria are retained rather than reported as a passing run.

Restart revalidated the remaining membership: Armin accessed the server (200),
Mikasa was denied (403) with her prior browser credentials, and both students' latest
saved edits survived. This is the CPU collaboration/revocation gate; GPU member
removal and broader packing/reclaim qualification remain separate open gates.
The fixture is stopped after acceptance, with Mikasa removed only from this owned
CIT QA course; existing CPS shared-GPU lab membership is unchanged.

[Live session closure](../../platform-staging/argo/qualification/profile-walltime-20261023/addon-image/variants/cit-member-removal-live-browser.json),
[restart denial and file preservation](../../platform-staging/argo/qualification/profile-walltime-20261023/addon-image/variants/cit-after-member-removal.json)
and [capture correction](../../platform-staging/argo/qualification/profile-walltime-20261023/addon-image/variants/cit-socket-instrumentation-correction.json)
retain this acceptance. Full production qualification remains incomplete.

## Shared-GPU live member revocation and restoration

The deployed CPS shared 5 GiB lab now passes connected-member removal: two real
student sessions exchanged edits, then both live collaboration connections per
visitor closed when normal removal stopped the workspace. Native cleanup first
returned guarded 409 with reservations retained; the same operation resumed after
cleanup, without manual release. A reduced-membership preview under the old approval
was rejected. Normal scoped reapproval delivered the new membership to all four
components; GPU restart, CUDA, Armin access, Mikasa 403 and saved edits passed.

Original membership/approval was then restored and republished. A final normal GPU
start confirmed both students' access and preserved edits. Final state is stopped,
original three members/profile restored in Source and Hub, reservation inactive,
zero KAI reservation Pods and four-component approval Ready. The scoped revision is
now `4248ec94…547c80` (generation 4). The original journal anchor and four configuration
rotations are unchanged. Policy and application images were not changed.

Warm individual starts took 103.643, 129.344 and 124.333 seconds. This closes the
bounded GPU connected-member revocation/revalidation gate, not full-pool packing,
cross-Hub reservation races, teaching reclaim, distributed jobs or burst readiness.

[GPU revocation verification](../../platform-staging/admin/qualification/gpu-member-revocation-20261023/verification.json)
and its [run details](../../platform-staging/admin/qualification/gpu-member-revocation-20261023/README.md)
retain the positive/negative cases and final restoration evidence.

## Newly verified live results

- CPS and CIT use the matching Hub image `435c0806…e5cb466`. The Hub wheel is
  based on the deployed source plus the durable receipt-root configuration change;
  unrelated lifetime and UI modules were preserved. Its 33 configuration tests pass.
- Gateway `ac9ee1b0…80c23f4` and Node `9d998baa…047bbeb` use the durable
  `cps-native-runtime` authority. Both control-service image rotations preserved
  the original delivery journal anchor and publication history. Predecessor
  bootstrap inputs remain available; the journal was not reset.
- The startup gate mounts the authority's public receipt/authority directories
  read-only from durable storage. Two initializers completed successfully before
  the actual notebook container became Ready.
- Two sequential normal starts on binder `218f788e…61800a1` took 84.49 and
  86.03 seconds. Actual notebook CUDA execution passed; a 6 GiB allocation was
  rejected under the automatic 5 GiB cap and subsequent allocation recovered.
  A workspace file survived normal shutdown/restart; the owned QA probe was removed.
- Normal stops took 15.11 and 6.96 seconds. KAI deleted the corresponding GPU
  reservation Pods automatically 2.36 and 3.41 seconds after close. The elected
  binder Pod did not restart and no reservation was manually deleted in either cycle.
- Final readback: workspace stopped, no active member reservations, all nine
  current-authority native claims released, no KAI reservation Pods, no online
  kernel cap entries. No MIG, driver, kernel, reset or storage-address change occurred.

[Live cleanup and repeat-start evidence](../../platform-staging/scheduler/native-kai-binder/cleanup-exact-retry-20261023/live-qualification.json)
and [earlier durable-root lifecycle evidence](../../platform-staging/gpu/qualification/native-fresh-unequal/results/normal-shared-gpu-durable-root-lifecycle-20261023.json)
retain the measured scope and identities. The first cleanup candidate was rejected
and replaced by a build from the exact recorded deployed binder patch; its failure
is retained in the adjacent candidate verification record.

## Full-plan completion order

The [original acceptance ledger](production-completion-20261013.md#acceptance-ledger)
and [required scenarios](qualification.md) remain binding. Older passing evidence
is retained; it is not reclassified as wholly untested. The final release matrix
must distinguish that evidence from the current live checks above.

1. The console startup confirmation fix is deployed to CPS/CIT. Normal GPU start
   (99.66 s), normal shutdown and pending-start cancellation passed live; focused
   tests cover lost reservations at final readiness publication. See the
   [package and live verification](../../platform-staging/admin/qualification/start-confirmation-20261023/verification.json).
   Actual 30-minute idle expiry now passes: proxy removal and Pod deletion occurred
   2.23 seconds after the deadline; reservations and kernel caps cleared without
   manual Stop. See [expiry evidence](../../platform-staging/admin/qualification/session-lifetime-20261023/verification.json).
   The stale Source running state after automatic shutdown is fixed: its scheduled
   observer converged the exact record with a system audit, and normal GPU restart
   passed in 89.01 seconds. [Reconciliation evidence](../../platform-staging/admin/qualification/external-shutdown-reconciliation-20261023/verification.json)
   includes preserved active-session checks and normal cleanup.
   Hard-maximum wall-clock expiry and visual warning acceptance remain separate.
2. Complete ordinary-user CPS/CIT access and the remaining collaboration gates:
   current SDK/Compute/RTC variants, membership removal closing existing access,
   and populated archive/recovery scenarios. A dedicated CPU fixture now passes
   normal closure, server-enforced read-only archive and blocked restart;
   [archive acceptance](../../platform-staging/admin/qualification/archive-identifiers-20261023/verification.json)
   retains the scope. CPS CPU connected-visitor revocation now passes: an existing Armin WebSocket
   closed, then restart returned Armin 403 and Mikasa 200. Populated test-file
   archive retention and EROFS passed independently. See
   [connected-member evidence](../../platform-staging/admin/qualification/member-revocation-20261023/verification.json).
   Equivalent CIT/GPU removal remains separate. Prior visitor/RTC
   and local-provider acceptance remains in the historical ledger.
3. The current CPS person-authenticated notebook/batch API matrix passes: typed
   parameters/imports, stripped immutable inputs, success/failure executed
   notebooks, logs/artifact bytes, idempotency, foreign-owner denial and nine
   crafted override rejections. CPU batch remained usable while the shared GPU
   reservation was active. See [live matrix](../../platform-staging/argo/qualification/notebook-owner-matrix-20261023/verification.json).
   Equivalent CIT, fresh GUI/SDK and distributed launcher acceptance remain open.
   A separate [profile-walltime candidate](../../platform-staging/argo/qualification/profile-walltime-20261023/verification.json)
   removes the API/Submit/snippet one-hour override in favor of catalog limits
   (196 API tests, 97 addon tests). The protected Gateway handover is complete and a live 7200-second request passed
   deadline admission and short execution. The shared-GPU addon image/policy rollout
   now passes the live checks above. CPU/other notebook variants still need the
   corresponding addon update; do not infer that every deployed GUI has changed.
4. Finish broader GPU scheduling/packing, teaching reclaim, checkpoint/distributed
   cleanup, representative CPS/CIT startup bursts and the Descheduler comparison.
   These two warm single-workspace starts do not establish burst p95, eight-GPU
   capacity, ordinary 20 GiB access or a whole-pool MPS qualification. Existing
   controlled unequal-cap/import/MPS/peer-survival results retain their bounded scope.
5. Nineteen selected monitoring targets are up; the four dashboards and rules
   now match Git, with 24 valid queries and healthy recording-rule evaluation.
   [Current monitoring evidence](../../platform-staging/monitoring/qualification/current-20261023/verification.json)
   preserves missing native/placement telemetry and the seven-versus-eight GPU
   inventory boundary. Finish monitoring completeness/visual access, matching-version
   backups and actual restores, NFS archives, and artifact ownership/retention on
   the final application matrix. NFS addresses remain unchanged and the accepted
   NetBird relay path remains the S3 transport choice.
6. Integrate the tested application/deployment branches and exact image/policy
   compatibility matrix. Publish and promote pilot, candidate and production
   artifacts only after their respective gates pass; account for Fleet deployment
   on merge. Published candidate images are not production releases.

Local course management stays active. Moodle remains visibly planned, disabled
and inert. Direct university OAuth awaits ICT registration as explicitly deferred;
email verification remains optional. These decisions are not silently expanded
into additional production requirements or identity linkage by username.

## Cross-Hub GPU reservations and independent CPU/batch access

Simultaneous normal CPS/CIT starts, requested 1.67 ms apart, admitted CIT and
rejected CPS with a recorded reservation conflict and no partial member holds.
After normal cleanup, the reverse direction admitted CPS and rejected CIT.
Both GPU winners passed CUDA allocation. While CPS held Armin's allowance,
Armin launched a CIT CPU notebook in 26.646 seconds and completed successful
and intentionally failing notebook batch runs, with timestamp evidence inside
the same GPU hold. No manual reservation release was used.

The temporary CIT GPU approval was removed and its original CPU-only ceiling
and profile restored, stopped with files preserved. The scoped Source revision
is now `d6165151…e8bed9`; all four approval components acknowledged it. Control
services are Ready and the KAI reservation namespace has no remaining Pods.

The initial race encountered a pre-reservation storage-provisioning 409 on both
sides. Concurrent provisioning and the later race passed; the initial transient
has no established root cause and remains an availability observation.

[Cross-Hub receipts](../../platform-staging/admin/qualification/cross-hub-reservations-20261023/README.md)
close the bounded global-member reservation gate, not full-pool scheduling,
burst performance, recovery exercises or production release integration.

## Ordinary student workspace opening

Armin's deployed CIT Compute addon correctly showed the stopped CPU workspace
without an opening link. After a normal maintainer start (19.843 seconds), its
Open workspace action traversed normal Hub OAuth consent and reached the neutral
named server's JupyterLab. Hub identity remained Armin, non-admin. Lifecycle
administration remains maintainer-controlled; no student start permission was
added. Both owned test servers were then stopped normally.

[Student opening receipts](../../platform-staging/admin/qualification/student-workspace-opening-20261023/README.md)
qualify this opening flow; broader scheduling, recovery and release gates remain.

## Retention activation gap revalidated

The scheduled retention CronJob remains suspended and uses older image/policy
provenance. A fresh unchanged-template read-only sweep examined 89 objects,
skipped 82 and returned seven errors, with zero mutations. Exception tracing in
a second owned Job identified seven Argo HTTP 404 proof failures. Missing live
workflow proof correctly preserves the objects; their removal history and
reviewed orphan disposition remain open. Current ordinary workflow TTL is 93
days, longer than the 90-day output retention window. Focused retention tests
pass (20 tests plus four subtests). Automatic deletion is not qualified.

[Read-only diagnostics](../../platform-staging/artifacts/qualification/retention-readonly-20261023/README.md)
retain the exact bounded observation. Temporary diagnostic Jobs were removed.

## Real Gateway retention mutation and active-input protection

The unchanged retention controller now passes conditional expiry against two
actual Gateway-created disposable QA artifacts. Real-clock reconciliation
preserved both; a per-call 91-day test clock expired both. The original Job's
output was observed but its TTL removed it before export; a separate read-only
Job confirmed durable deleting claims and both exact S3 keys absent. No deletion
was repeated, and only those two owned QA artifacts were removed.

A fresh real notebook remained Running before and after an aged-clock apply
sweep: its snapshot ETag/tags were unchanged, with zero reconciliation,
eligibility, deletion or errors. The notebook subsequently succeeded; selected
imports, typed parameters, executed output, foreign-owner denial and idempotency
passed, and both temporary student API tokens were revoked. Owned test Jobs
are removed. Production retention remains suspended pending exact deployment
alignment, scheduled mutation qualification and reviewed orphan disposition.

[Gateway lifecycle receipts and probes](../../platform-staging/artifacts/qualification/gateway-lifecycle-20261023/README.md)
close these specific lifecycle gates, not overall production readiness.

## Retention controller alignment and unmanaged-object fix

The current released image passed failed-notebook artifact expiry and retained
output preservation. The aligned real-clock full-template run reconciled 45
objects and expired one eligible snapshot, but exposed 42 errors. Read-only
classification separated 14 unmanaged key shapes from 28 missing-workflow 404s.
Regression tests reproduced the unmanaged-key bug. Published fix `f0a8773` skips
such objects before reconciliation; all 21 tests and eight subtests pass.

The corrected immutable controller is deployed. Its full-template run reconciled
44 objects, preserved/skipped the unmanaged keys, deleted none, and retained the
28 missing-proof errors. The aligned schedule is still suspended pending reviewed
legacy/orphan handling. This is prepared and tested mutation configuration, not
an active daily cleanup schedule.

[Activation receipts](../../platform-staging/artifacts/qualification/retention-activation-20261023/README.md)
record exact run results, image/policy and controller identity.

## Daily artifact retention active and scheduler-verified

The 28 missing-workflow objects now have an explicit operator preservation review:
seven exact controlled-fixture matches, nine removed qualification-namespace
objects and twelve unattributed legacy objects. They remain in place, with exact
ETag exclusions and reviewed reasons in Git. No ownership or deletion authority
was inferred. Changed ETags and new unknown keys still require normal proof and
fail visibly. All 24 tests and 14 subtests pass, including chart propagation.

The full-template run completed with zero errors, 44 reconciled objects and 28
preserved objects. A read-only re-inventory confirmed unchanged legacy ETags,
metadata and tags. Daily retention is now unsuspended. A genuine Kubernetes
controller-scheduled catch-up run for 03:41 UTC completed successfully with the
same zero-error result. This supersedes the earlier suspension notes above.

[Preservation review and scheduled-run receipt](../../platform-staging/artifacts/qualification/retention-orphan-review-20261023/README.md)
close retention activation and actual scheduled execution. Off-host recovery,
broader GPU scheduling/bursts and release integration remain incomplete.

## Fresh 5+10 GiB packing and startup-performance objective

The current released automatic-cap deployment passed a live CPS5/CIT10 pair on
one A100: over-cap ordinary PyTorch rejection and recovery passed in both
directions while each peer completed 990 GPU progress iterations. Normal cleanup
restored the CPU fixtures, expired temporary grants and revoked approvals; all
reservations/bindings/KAI reservation Pods are gone and four-component readiness
returned. This is bounded current two-peer evidence, not eight-GPU qualification
or a complete rerun of IPC/import/MPS tests.

Concurrent start exposed a real pre-execution admission problem: a nonblocking
execution-fence conflict and withdrawn Node acknowledgment caused both starts
to fail safely. Sequential starts passed in 128/144 seconds. The user explicitly
requires substantially faster startup; these times are a baseline, not accepted
as the final experience. Images were already cached. Measured body caching saves
milliseconds; readiness/enrollment, pre-Pod work and notebook readiness dominate.
A shallow NAS-status fast-path prototype lacked required proof and was discarded
rather than deployed. Live permission/reservation checks remain mandatory.

[Packing and startup baseline](../../platform-staging/gpu/qualification/current-packing-5-10-20261023/README.md)
and [caching investigation](../../platform-staging/startup-performance/qualification/cache-spike-20261023/README.md)
record this progress and the new performance priority.


## Startup control-plane fixes staged, not deployed

Compute source `d0150bdaee8f8888f070b84b4dda98b6ec5aca46` adds bounded
publication-lock waits for existing custody while keeping new acquisition
nonblocking. A proposed server-side new-lease queue was removed: its worker
could outlive a cancelled caller before durable custody existed. Concurrent
new starts still need a closed, pre-dispatch retry protocol; this is not yet
an end-to-end concurrency fix.

Node logs also show validated ledger changes at the final acknowledgment
boundary taking the ordinary 10-second failure backoff. The source now uses
an explicit typed snapshot-change exception and a 0.1-second retry. Readiness
is still withdrawn, a full iteration runs again, the retry budget remains
finite, and API/driver/invalid-proof errors retain the existing backoff. This
explains an avoidable delay on that path, not the entire warm-start baseline.

Focused suites passed (107 authority/pending, 59 publication/custody/readiness,
93 current-group/enrollment, and 132 node-service/custody/ACK/pending tests).
The full suite was deliberately interrupted while correcting the unsafe lease
queue; its partial result is not full-suite qualification. Wheel and both container builds passed. Gateway and Node candidate images
were pushed and their remote manifest digests independently verified; installed
Gateway dependency checks and the inert Node CLI passed. Supported deployment
handover remains pending. No live speed improvement
or production-readiness claim follows from these source tests.

[Staged source verification](../../platform-staging/startup-performance/qualification/cache-spike-20261023/coordinator-fixes.json).


## Startup candidate rejected; previous deployment restored

The first startup candidate (`d0150bd`, Gateway `696b140d…3b01fe`, Node
`ed511696…c54c99`) was attempted and rejected. Its Node source omitted the
kernel-147 health pins and cleanup commits already present in deployed Node
`9d998baa…047bbeb`; exact-load validation correctly withdrew readiness.
Previous service images/configuration and Node admission were restored. A
read-only probe confirmed all four current components Ready at approval
`b7082c51…ea088f`. Journal state and anchor bytes remained unchanged: no journal
rotation ran, and no driver/kernel/GPU change occurred. Research Pod gottam
retained its UID and remained Running. Helpers and seven unmounted candidate
inputs were removed with UID preconditions.

The maintenance helper also exposed recursive fsGroup mode changes on the
shared Gateway PVC. Owned private modes were restored without changing file
contents/inodes; the Gateway and retention now use OnRootMismatch, matching
the existing backup mount policy. Source Helm render tests pass (23 tests and
14 subtests). Neither retention schedule nor application was changed.

Corrected compute source `4f39a686254f692dcce9d5a7d03a34f4271dad85` integrates
the three deployed Node commits. Its Node files differ from deployed source
only by the intended two fast-retry files; its health verifier SHA256 exactly
matches the deployed fc9dd634…4322fe8. 343 focused tests passed. Corrected Gateway `fc77489e…4f6392` and Node `88fa54cb…eacd81` images are
published with independently verified remote manifests. Both installed candidates
passed validation against the actual protected load manifest/kernel, matched the
deployed health-source hash and loaded the actual immutable policy graph without
GPU calls. Another supported handover and live timing remain open.
The first published images must not be promoted.

[Rejected attempt and verified restoration](../../platform-staging/startup-performance/qualification/cache-spike-20261023/rejected-rollout-and-restoration.json).


## Corrected startup pilot active; speed and software gates still open

The corrected Gateway `fc77489e…4f6392` and Node `88fa54cb…eacd81` are deployed
through the supported existing-journal handover. The original anchor and four
prior rotations are preserved (five now); normal delivery is running with four
components Ready. Capture's expected Node image was updated without changing
credentials or authority scope. No driver/kernel/GPU-mode or research-server
change was made. The current CPS5/CIT10 cap/recovery and peer-survival run passed
again, with 991/990 progress iterations.

**Startup speed remains unsatisfactory.** CPS took 193.09 seconds, CIT 146.82;
a traced CPS restart took 154.21. The trace assigns 15.23 seconds to storage,
0.13 to account setup, and 132.16 to Hub spawn/readiness. Image caching was already
warm, and three complete context reads took 1.022 seconds. There is no measured
speedup or burst qualification. Preserve final authorization, live permission,
reservation and device checks while reducing that critical path.

QA cleanup is complete: CPU profiles and original ceilings restored, temporary
grants read back expired, temporary approvals removed, member/binding/KAI
reservations zero. Final approval revision is 394d4256…f66de31 with the original
mainlab approval retained. The full software-suite attempt passed 3427 tests
and 49 subtests, skipped 3, and stopped after five final-enrollment/fence-diagnostic
failures; remaining cases have not run. The earlier stalled fixture was corrected
without relaxing the production bounded-client guard. These gates remain open.

[Corrected deployment, timing, CUDA and cleanup receipts](../../platform-staging/startup-performance/qualification/coordinator-v2-20261023/README.md).

### Subsequent software verification and pooled-budget correction

The complete repository suite at `cps-compute` commit `756e6dd` finished with
5165 passed, 6 skipped and 68 subtests passed. Its single failure was the real
JupyterHub identity-hook test importing absent `jupyter_server` in the test
environment. Installing the Lab addon's declared dependencies made that test pass.
This was a test-environment failure, not evidence of a deployed hook defect.

A separate acceptance test reproduced a pooling defect: members granted only
the qualified 5 GiB profile could not select an approved 10 GiB workspace even
when their combined allowance was sufficient. Commit `8bdacc4` sums the largest
qualified profile budget for each distinct canonical member, independently of
the selected workspace profile. Exact workspace approval, current grants,
interactive allowance and course ceiling checks remain in place. Seven new
regressions cover successful 5+5→10 pooling and rejection of insufficient budget,
lower ceilings, expiry, zero allowance, duplicate members and duplicate grants.

The relevant group, packing, preview and Lab-hook suites pass: 84 tests and
19 subtests. A new complete suite is running against `8bdacc4`; its outcome is
not yet known. The commit is pushed on the existing feature branch, not deployed.
The production-readiness goal and startup-performance work remain open.

### Pooled-budget candidate deployed after complete software pass

The complete repository suite at `8bdacc4` passed 5173 tests and 68 subtests
(6 skipped; 593 warnings). Gateway image `09015137…96e07` is active; Node image
`88fa54cb…eacd81` is unchanged. Current specifications and all four process
acknowledgments were verified at revision `394d4256…6de31`. The normal writer is
Ready. Rotation six preserves the original anchor and all five predecessors,
with no transition pending. Both maintenance Pods were removed using UID pins.

The admission dry-run caught an operator-helper ReplicaSet selection assumption
for unchanged Node images; exact bootstrap matching corrected it before any
incorrect Node Pod launch. Positive and all three negative admission cases pass.

This completes the software and deployment steps for the pooled-budget fix,
not live 5+5→10 workspace acceptance or startup performance. Those tests and
the broader production plan remain open.

[Deployment and full-suite evidence](../../platform-staging/startup-performance/qualification/pooling-candidate-20261023/README.md).

### Live 5+5→10 GiB shared-workspace acceptance passed

Two reviewed canonical members, each with only their existing 5 GiB grant,
started a 10 GiB QA workspace through the ordinary Source path. Exactly two
global member reservations and one binding were verified; a notebook CUDA smoke
passed on the A100. Cleanup restored the stopped CPU fixture, original membership,
ceiling and notice, removed the temporary approval, and read back unchanged grants.
Global reservations/bindings are zero, all native allocations are released, and
the original research Pod remains Running with its original UID.

Startup remains slow: 184.86 seconds, including 53.30 before Pod creation and
83.00 from creation to actual assignment. This closes the functional pooled-budget
acceptance gap; startup optimization, broader GPU/scheduling qualification and
production release gates remain open.

[Live pooled-member evidence](../../platform-staging/startup-performance/qualification/pooled-members-20261023/README.md).

### Pending-work polling optimization staged, not deployed

Coordinator timing from the live pooled-member run identifies 22.51 seconds of
enrollment publication inside the successful 37.11-second Prepare. An earlier
registered-snapshot refresh also required a retry. Shared workspaces already
disable unused per-user PVC creation.

Candidate source `7486ea8` keeps the full fresh-proof protocol while polling
pending registration/placement/gates after at most one second, retaining the
normal five-second cadence for sealed/idle work and the existing failure backoff.
All 109 focused Node tests pass; the full suite is running. A checksum-pinned
Node image is published and passes actual driver/kernel/policy preflight.
No deployment or startup gain is claimed yet.

[Candidate and baseline trace](../../platform-staging/startup-performance/qualification/adaptive-poll-candidate-20261023/README.md).

### Full-suite grant-observation failure corrected in source

The polling candidate's full suite finished with 5178 passed and one failure
in final acquisition grant withdrawal. Deterministic tests reproduce grant
revocation after local authorization but during external approval or final
ledger observation. Source `e837d76` adds a final local Source/member permission
check after those external observations, retaining custody and reservations
on denial. All 111 focused acquisition/authorization/pooling tests pass.
The complete suite is running again; no complete pass is claimed yet.

The candidate was not activated. All eight inactive configuration objects were
removed using UID preconditions; deployed service specifications are unchanged.
The next release candidate includes both this correction and adaptive polling.

### Final local grant guard retains the callback budget

The `e837d76` full run passed 5180 tests but failed the existing one-Source-
callback-per-claim regression. Source `bca0123` removes the repeated full policy
callback and compares local workspace/storage/effective-member-grant observations
before and after the external proof. The original callback and four-component
observation thresholds remain unchanged.

All 32 acquisition/callback tests pass, including grant deletion at two external
boundaries, expiry without database mutation and unrelated-grant noninterference.
The complete suite is running again. The live deployment is unchanged; neither
the pending polling change nor these grant-observation fixes are deployed yet.

[Local permission guard evidence](../../platform-staging/startup-performance/qualification/authorization-local-guard-20261023/README.md).

### Local guard deployed; adaptive polling did not improve the measured start

Source `bca0123756964d1cf0b4fd62b84f04b39bc5846e` completed the full suite:
**5183 passed, 6 skipped, 68 subtests passed** in 567.36 seconds. The Gateway
and Node image pair is active through supported delivery rotation 7. The normal
writer is Ready; maintenance helpers were removed. This supersedes the pending
suite and unchanged-deployment statements immediately above.

The ordinary two-member CPS 5+5 GiB pooled workspace reached Ready in
**219.99 seconds**, compared with the prior **184.86 seconds**. Pod creation to
assignment increased from 83 to 122 seconds. Successful Prepare increased from
37.11 to 46.68 seconds, including 28.81 seconds in enrollment publication and
12.67 seconds across 23 context loads. These spans overlap and must not be added.
Neither Gateway nor Node CPU counters reported quota throttling. This sample
does not demonstrate an adaptive-polling benefit or establish its causal impact.

A 64 MiB CUDA allocation/write/synchronize passed. Normal Source cleanup stopped
the workspace, restored CPU selection, membership and course ceiling, removed
the temporary approval and preserved existing grants. Independent Kubernetes
readback confirms the test Pod is absent and the original research Pod remains
Running with UID `fe5fb5e7-8696-4ac3-a5a8-1883817d00bb`.

Read-only in-container profiling of three context loads took 1.347 seconds:
retained transition-history validation accounted for 0.606 seconds and recursive
Node configuration loading for 0.581 seconds (nested costs, not additive).
There were 138 ConfigMap reads across these three loads. This is a diagnostic
sample, not a startup improvement or a replacement for live authorization.
Next work targets repeated historical validation/read cost while preserving
fresh permission, object-identity, deletion and capacity checks.

[Deployed receipt](../../platform-staging/startup-performance/qualification/authorization-local-guard-20261023/deployed-verification.json).
Full-pool packing, broader scheduling/burst qualification and the remaining
release gates are still open; production readiness is not established.

### Fresh retained-history reads parallelized and deployed

Source `0d0b046e6c3eec59f9a7950856178b299912360a` completed the full suite:
**5184 passed, 6 skipped, 68 subtests passed** in 570.79 seconds. Retained
approval ConfigMaps are read with four bounded workers, freshly on every scan,
then validated in original cohort order inside the existing pointer bracket.
No cross-request authorization cache is introduced.

The image pair passed actual manifest/kernel/policy preflight and is active
through supported delivery rotation **8**, preserving the original anchor and
all seven previous rotations. Admission positive/negative checks passed; the
normal writer is Ready and both maintenance Pods are deleted with UID checks.
A controlled pooled-member startup comparison is running. No startup gain or
full production qualification is claimed before its terminal results.

[Deployment receipt](../../platform-staging/startup-performance/qualification/parallel-history-20261023/deployed.json).

### Live history-read qualification failed; Source success was not Pod readiness

The controlled run must **not** be counted as a successful startup comparison.
The coordinator denied enrollment after 34.19 seconds at the empty Node custody
withdrawal check. The test Pod was independently observed absent before the
Source service subsequently reported a successful start at 208.11 seconds.
No CUDA proof was possible. The cause of the false-ready Source result and the
causal role, if any, of parallel history reads remain unproven.

Normal Source cleanup completed after a transient SQLite writer-lock failure.
CPU profile, membership, course ceiling and notice were restored, temporary
approval removed, existing grants preserved and all four components Ready.
Independent read-only database checks found zero global reservations and zero
bindings; all 28 native allocations are released. The original research Pod
remains Running with its original UID. No manual reservation release was used.

Next acceptance work is reproducing the Node withdrawal/renewal race and the
Source readiness failure. Full-suite success is not sufficient for these live
behaviors. Production readiness and startup improvement remain unconfirmed.

[Failed live qualification and cleanup](../../platform-staging/startup-performance/qualification/parallel-history-20261023/live-functional-failure.json).

### Enrollment renewal race reproduced and corrected in source

A deterministic real-Node-publication regression reproduces the live denial at
`require_withdrawal`: final-generation publication advances during the first
claim, then a healthy same-generation heartbeat arrives during its slow all-peer
authentication. The old branch incorrectly requires that renewal to be empty.

Source `063d85e` authenticates either an exact withdrawal or a same-scope renewal
and repeats the outer fenced proof; it does not complete enrollment from that
intermediate observation. A future-dated receipt with recomputed witness hashes
remains denied. All 48 final-enrollment tests and 48 adjacent amplification,
fence-budget, readiness-boundary and terminal-witness tests pass. The full suite
is running. This correction is not yet deployed.

Refinement of the Source readiness diagnosis: the reported success coincided
with our explicit cleanup Stop from a **second diagnostic process**. Such a
process bypasses the single application process's lifecycle locks. We have not
yet reproduced false-ready behavior through the normal console HTTP path and
must not claim that broader root cause as established. The enrollment failure
and missing Pod still invalidate the live timing sample. The next controlled
run must verify actual Pod readiness and CUDA before accepting Source success.

### Enrollment renewal fix deployed after full-suite pass

Source `063d85e242cf3ec4d7db0585c9987b243e704e2f` passed the complete suite:
**5186 passed, 6 skipped, 68 subtests passed** in 564.71 seconds. Both images
passed checksum checks for the changed installed coordinator as well as actual
manifest/kernel/policy preflight. Supported journal rotation **9** is complete,
preserving the original anchor and all eight previous rotations. Admission
positive/negative cases passed. The normal writer is Ready; both maintenance
Pods were deleted using UID preconditions.

The next live attempt uses an actual authenticated console HTTP request in the
application process. GET authentication and a harmless Stop for the stopped QA
fixture passed; POST uses the normal page-issued CSRF cookie/header. A successful
start must additionally retain the same Pod UID, reach Kubernetes Ready and pass
an actual CUDA allocation/write/synchronize. Live qualification is still pending.

[Deployment receipt](../../platform-staging/startup-performance/qualification/enrollment-renewal-20261023/deployed.json).

### Normal HTTP start denies correctly; pre-CAS readiness retry remains open

The controlled pooled-member test used the actual authenticated console HTTP
endpoint, with its ordinary CSRF cookie/header and in-process lifecycle locks.
Start returned **409 after 307.12 seconds**; the Pod never reached Ready and no
CUDA test was run. Stop returned **200**. No false-success response occurred.
This narrows the previous success-during-cleanup observation to the diagnostic
cross-process Stop race; it does not prove every lifecycle race qualified.

The coordinator first requested a registered snapshot refresh, then denied
Prepare after 38.50 seconds at the fresh full all-four claim immediately before
the reserved-to-enrolling CAS (`runtime.Reader.node_reference`). Registered
readiness had taken 27.73 seconds. The earlier malformed-withdrawal branch did
not recur, but this attempt failed before it could qualify final publication.
The next change must model and handle transient acknowledgment unavailability
at this pre-CAS read-only boundary, preserving the original head, grants,
identity/epoch, custody checks and deadline. No production readiness is claimed.

Normal HTTP Stop and subsequent fixture restoration completed. CPU profile,
membership, ceiling and notice were restored; temporary approval removed and
existing grants unchanged. Independent global reservation/binding counts are
zero; all native allocations are released. The original research Pod remains
Running with its original UID. The short-lived, narrowly scoped QA user token
was revoked and its private credential files removed.

An isolated Hub configuration load temporarily encountered a ConfigMap RBAC
denial while approval delivery was changing. After settled cleanup it **passes**;
the running Hub was never restarted. Do not report this transient result as an
unresolved settled-state cold-start failure.

[HTTP live result and cleanup](../../platform-staging/startup-performance/qualification/enrollment-renewal-20261023/http-live-result.json).

### Pre-CAS acknowledgment withdrawal reproduced and corrected in source

Source `cc80800` repeats the complete read-only scope/Node-ACK/full-claim/Node-ACK
bracket when the existing readiness classifier reports transient unavailability
immediately before the reserved-to-enrolling CAS. The original request deadline
bounds the wait. No enrollment mutation is replayed or skipped, and an existing
staged Session does not gain this retry path.

The real Node publisher regression first failed at the exact live call chain
through `_claim_current` and `node_reference`. Recovery now succeeds. Additional
cases expire the member grant or hold custody during the wait and prove denial
without an enrollment write. The actual server deadline-expiry case retains
custody, closes fences and performs no GPU writes. All **100 focused tests**
pass across final publication, pre/post-fence readiness, read amplification,
fence timing and terminal witness coverage. Existing negative expectations and
normal callback budgets remain unchanged.

The complete suite is running. This correction is committed and published in
the compute source branch, but is not deployed yet; rotation 9 remains active.
The normal HTTP + same-UID Ready Pod + CUDA harness will be reused after release
qualification, followed by normal Stop, fixture restoration and reservation
verification. Production readiness remains unproven.

### Empty pre-CAS capture race caught before the next rollout

An adjacent deterministic real-Node test found a second pre-CAS case before
publishing `cc80800`: the ACK is empty when captured, then recovers before the
full claim returns. Comparing that empty capture as a heartbeat incorrectly
denies enrollment. The superseded full-suite process was deliberately
interrupted for this reproduced code flaw; it is not a completed pass. Its
locally built images were neither published nor activated, and no cluster
configuration objects were staged from them.

Source `2fa6315` validates the exact target and closed receipt first. Only a
canonical empty receipt with no custody/pending witness annotations enters the
existing bounded retry. The next iteration rereads scope and full authority.
Wrong UID, stale witness annotations and noncanonical empty data deny without
waiting or writing enrollment. The existing expired-grant, custody-change and
deadline cases remain passing. All **104 focused tests pass**. The full suite
is now running against this committed source; rotation 9 remains active.

### Combined pre-CAS readiness fix deployed after 5194-test pass

Source `2fa6315cb620ed71baeac2bc4910f997d2c5b3d0` passed the full suite:
**5194 passed, 6 skipped, 68 subtests passed** in 582.35 seconds. This includes
the bounded full-authority retry and exact empty-capture handling; malformed
receipts and changed permissions/custody still deny.

Supported delivery rotation **10** activated the verified image pair, preserving
the original anchor and all nine earlier rotations. Admission positive/negative
checks passed. The normal writer is Ready and both maintenance Pods were deleted
with UID preconditions. No driver, kernel, storage or resource-policy changes
were made. The original research Pod remains Running with its original UID.

The normal HTTP + same-UID Ready Pod + CUDA test is being prepared. Its CPU
samples now also cover the Gateway capture sidecar, whose CPU limit is 500m;
prior no-throttle samples covered Gateway and Node only. No live startup gain
or production readiness is claimed before terminal hardware results.

[Deployment receipt](../../platform-staging/startup-performance/qualification/pre-cas-empty-capture-20261023/deployed.json).

### Rotation 10 live attempts fail at lease entry before Pod creation

Two normal authenticated HTTP attempts with the same image pair and approval
returned **503**, after **48.57** and **53.99 seconds**. Neither created a Pod;
therefore no CUDA or startup-success proof exists. Both reached lease denial
at the `NativeGpuGroupAuthority._workspace` wrapper, before acquisition writes.
The wrapped original denial reason is not established by the current trace.
Do not conflate this with the corrected pre-CAS or final-publication branches,
which these attempts never reached.

The Hub's stored profile is 10 GiB. Static registration/permission checks allow
10 GiB and correctly deny an unapproved 5 GiB selection. Three read-only idle
ACK-reader samples and three deployed-workspace-method replays pass. These
use actual current inputs and no runtime factory/writers, but do not prove
which mutable check failed during the actual requests. The next task is a
lease-entry reproduction plus bounded diagnostic context if needed, rather
than another unchanged hardware attempt or an inferred root cause.

CPU sampling now includes capture: over the first 70.93-second sample Gateway
used 63.05 CPU seconds with no throttling, capture used 4.97 CPU seconds with
2.68 seconds throttled at its 500m limit, and Node used 13.42 CPU seconds with
no throttling. These are sample totals, not failure attribution. No resource
limits were changed on this evidence alone.

After the first failure HTTP Stop returned 200. Both starts were terminal
before final fixture cleanup. The short-lived test credential expired during
diagnosis; final restoration used the existing normal Source lifecycle methods
and the exact test token was revoked. CPU selection, membership, ceiling and
notice are restored; temporary approval removed and original grants unchanged.
Independent counts are zero reservations/bindings and all 29 native allocations
released. The original research Pod remains Running with its original UID.

[Lease-entry live results and cleanup](../../platform-staging/startup-performance/qualification/pre-cas-empty-capture-20261023/lease-entry-live-result.json).

### Initial lease read race reproduced; bounded retry and diagnostics staged

Source `c71cf8b` reproduces an acknowledgment drop after the lease scope check
but inside the first workspace authorization callback. It fails at the same
`_workspace` wrapper seen live. This proves a concrete entry-point race, not
the exact original reason suppressed in the two live denials.

The coordinator now supplies a separate initial-observation wait: the complete
workspace/neutral-owner/approval-reference bracket repeats only on the existing
readiness classification and before member reservations or allocation writes.
The requested immutable revision is checked again. Direct authority callers
retain their original single-observation behavior; final-CAS waiting remains
separate. An expired initial wait preserves the existing authorization-error
contract for direct lease callers. No request/fence budget was increased.

New tests recover from absence, reject grant expiry and changed heads without
reservation writes, avoid retrying unrelated denials, and expire the actual
HTTP server deadline with zero allocations/reservations and no acquiring flag.
Operator logs now retain at most 16 code frames over a bounded exception chain,
including a suppressed inner wrapper, while still excluding messages, locals,
request bodies and tokens. HTTP errors remain generic. Lease readiness and
acquisition timing use fixed labels; existing Prepare instrumentation is intact.

All **125 focused tests pass**, including existing callback budgets and the
unready-lease error contract. The full suite is running. This source is
committed and published but not yet deployed; rotation 10 remains active and
live functional/production qualification is still open.

### Rotation 11 deployed; HTTP start fails before coordinator lease

The initial-lease implementation `c71cf8b` is now deployed. Its full run
finished with **5,199 passed, one failed, six skipped and 68 passed subtests**.
The failure was an old exact count of two readiness phases. Test-only
`de37965` now requires exactly three phases, one identical frozen deadline
within each request, and distinct concurrent request deadlines. All **23**
affected tests pass; no implementation changed after that full run.

Both image builds passed offline manifest/kernel/health-source/policy/module
preflight and registry digest verification. Rotation 11 preserves the original
anchor and ten prior rotations, has no pending transition, and the four current
components were Ready. Admission positive/negative checks passed; both
maintenance helpers were deleted with UID preconditions; normal writer Ready.

The actual console HTTP start returned **503 after 28.056 seconds**. No Pod
was created and no CUDA proof ran. Hub traceback identifies HTTP 400 from
`/internal/v1/reservations/acquire`, before coordinator lease. The underlying
denial remains unknown: do not attribute this run to the initial-lease race.
Source `cbf0841` adds bounded code-location-only diagnostics to this endpoint;
**31 tests pass**, with a red-first regression verifying generic errors, no
secret message logging and no reservation on denial. That diagnostic source
is not deployed yet.

Normal cleanup restored stopped CPU selection, membership, original ceiling
and notice, removed the temporary approval, and left original grants unchanged.
All four current acknowledgments recovered. The short-lived QA credential was
revoked and removed. Research Pod `jupyter-gottam` remains Running with original
UID `fe5fb5e7-8696-4ac3-a5a8-1883817d00bb`. Production qualification remains open.

[Public test, image and live result receipts](../../platform-staging/startup-performance/qualification/initial-lease-readiness-20261023/).

### Reservation-stage readiness denial located; retry suite passes; Hub packaging corrected

Rotation 12 deployed code-location diagnostics (`cbf0841`). The real console
start returned 503 after **30.583 seconds**, without a Pod. Its denial is at
`runtime.py:Reader.node_reference`: no valid complete four-component current
observation, or a revision mismatch, while freezing the first member-reservation
reference. This establishes the failing gate, not which receipt was absent or
stale. It occurs before coordinator lease. Test workspace and credential cleanup
passed; original grants and research Pod were preserved.

Source `725a3a6` adds a 60-second read-only reference wait against a frozen
workspace record and approval revision. Only the exact existing readiness
classification retries. Grants are revalidated before writes; changed Source
records/heads, unrelated errors and timeout deny without reservations.
**42 focused tests** and the full **5,207 passed, six skipped, 68 passed subtests**
run pass. That server fix is not deployed yet.

The first Hub timeout candidate omitted deployed owner-overlay/lifetime code
and failed startup on the `owner_scoped_overlay` keyword. Both Hubs and all
previous service inputs were restored before any journal rotation. Journal
bytes are unchanged, rotation remains 12, all four components Ready, both
maintenance helpers deleted, research Pod still Running with original UID.
The incompatible Hub image is rejected and must not be promoted.

Actual deployed Hub module hashes match `4b3679f` across all 20 Python files.
Source `57425ac` reconciles that package into the integration branch and adds
only the native reservation read timeout (120 seconds; connect/write/pool remain
30; one POST, no mutation replay). Nineteen baseline modules match byte-for-byte
and the twentieth differs only by this timeout. **470 Hub/package tests pass**,
including retained owner-overlay and lifetime behavior. New reconciled image
build and live qualification remain pending.

[Failure, full-suite, package comparison and restoration receipts](../../platform-staging/startup-performance/qualification/reservation-reference-retry-20261023/).

### Corrected Hub timeout package deployed to CPS and CIT; rotation 13 complete

Hub image `sha256:f2dcf6a47ea542a84defa589db48e96cf33e6f626958bc3d264a88bcf14919e1`
contains the hash-pinned Hub wheel from `57425ac`. It preserves every one of the
actual deployed SDK's **78 module hashes**, all dependency versions, and 19 of
20 Hub module hashes. Only `hub.py` differs, by the native reservation response
timeout. Owner-overlay support is retained. Package tests: **470 passed**.
Both Hubs are now Ready on this corrected image; the incompatible candidate
from the preceding section remains rejected.

The paired rollout initially retained old publisher bootstrap process-image
pins. The all-four observation correctly denied the mismatch. Two new immutable
Hub publisher inputs change only `process.image`; UID/RV/spec-fenced deployment
patches select those inputs. Both Hubs restarted Ready and all four acknowledgments
matched the running images. Future paired image rollouts must align these
publisher inputs in their initial exact-change plan.

Journal rotation **13** preserves the original anchor and twelve prior rotations
with no pending transition. Normal writer Ready; both maintenance helpers
deleted using UID preconditions. Research Pod `jupyter-gottam` remains Running
with original UID `fe5fb5e7-8696-4ac3-a5a8-1883817d00bb`.

Gateway/node remain on rotation-12 diagnostic images (`cbf0841`). The server
reference retry (`725a3a6`, full suite **5,207 passed**) is still not deployed.
Next: its service-image transition, then real console GPU startup/CUDA validation.
No production or startup-latency qualification is claimed by Hub readiness.

[Image preservation, publication, journal and live receipts](../../platform-staging/startup-performance/qualification/reconciled-hub-budget-20261023/).

### Server reference retry deployed; real lease succeeds; v2 caller timeout located

Gateway image `sha256:a0fe1dc2bf7fdabdc2ac38993ed7d9cdf37c567253f85dbe3d109d52b355aae0`
and node image `sha256:1dac979f7d428b3d4bb6b1748d6c70f2799aca292fcc5a7e24c0e01c4dd1e6da`
are deployed. All **80 installed SDK modules** in each candidate match the tested
source. Journal rotation **14** preserves its original anchor and thirteen prior
rotations, no pending transition. Four-current acknowledgments passed, normal
writer Ready and both maintenance helpers removed. Corrected Hub packages and
publisher inputs from rotation 13 remain unchanged.

The real console start passed member reservation (**HTTP 200**) and the coordinator
lease (**success in 49.283 seconds**; acquisition 45.272, initial readiness 3.053).
It still returned **503 after 116.124 seconds**, before any Pod was created. Hub
traceback proves that the v2 lease client's outer timeout was **30 seconds**; its
compile/created operations already use 90. The lease completed on the server
after the client had timed out. This is no longer a reservation-reference denial.

Source `bc9b441` uses the existing group readiness budget for all three v2
operations; v1 remains 30 seconds. **342 tests pass**, including exact outer and
transport budgets and expiration without replaying the POST. Server/fence
deadlines and Hub maximum spawn lifetime are unchanged. The new Hub fix has
been pushed but is not deployed.

Normal cleanup restored the stopped CPU fixture, membership/ceiling/notice,
removed temporary approval, retained original grants, and verified all four
current acknowledgments. All **30 native allocations are released**. Temporary
credential revoked/removed; research Pod remains Running at original UID.
Live Pod/CUDA and startup performance qualification remain open.

[Deployment, successful lease timing, timeout and cleanup receipts](../../platform-staging/startup-performance/qualification/reservation-server-retry-live-20261023/).

### V2 lease client fix deployed; actual Pod created; registered readiness still blocks binding

Hub image `sha256:da84bfe42d1389fcb8af96b8c410837a886e677b2970484c973bb25f91ccd844`
from `bc9b441` is live on both Hubs. All 78 deployed SDK modules and 19 Hub
modules are preserved; only `native_pending_hub.py` changes. **342 focused tests
pass**. The initial exact-change plan now includes both Hub publisher-image
inputs. Rotation **15** preserves the anchor and fourteen prior rotations, no
pending transition; normal writer Ready and both maintenance helpers removed.
Both Hubs restarted once on gateway connection refusal during simultaneous
rollout, then became Ready. Future paired activation should await gateway
readiness before patching Hub deployments. This sequencing issue remains open.

The actual console run passed member reservation, lease, compile and created
(**all HTTP 200**). Lease completed in **22.430 seconds**. One pinned Pod UID
was created at **113.007 seconds**, but no actual node binding or Ready state
was observed. KAI emitted a Scheduled event; that event alone does not prove
binding, because observed Pod `spec.nodeName` stayed empty.

The first coordinator Prepare expired at **120.797 seconds**, entirely in
registered readiness (**120.364 seconds**; 32 context calls cost 22.760 seconds).
Its exact inner readiness denial is not established. Subsequent short denials
are not evidence of the original reason. The unchanged Source 300-second
start deadline stopped the Pod; HTTP returned **409 after 312.582 seconds**.
The Pod disappeared without replacement; no CUDA check ran. Do not claim
functional GPU startup or startup-latency qualification from the earlier 200s.

Normal cleanup restored the stopped CPU fixture, membership, ceiling and
notice; temporary approval removed, existing grants unchanged. All four
current acknowledgments recovered. All **31 native allocations are released**;
QA credential revoked/removed and research Pod preserved at original UID.
Next investigation: read-only exact readiness diagnostics while the next
controlled Pod is Pending, rather than a blind same-image retry or a longer
startup deadline.

[Deployment, HTTP/Pod progress, readiness timing and cleanup receipts](../../platform-staging/startup-performance/qualification/hub-lease-budget-live-20261023/).

### Restart recovery defect reproduced; exact persisted-lease cleanup staged

Two instrumented requests did not reach Pending Pod diagnostics. First returned
**422** at the final workspace-policy check after provisioning; its exact inner
denial remains unproven. The second returned **503** before Pod creation. Hub
traceback identifies the retained native-shutdown guard. A later read-only replay
passed both live-view and same-current-projection policy checks; that does not
establish the earlier 422 cause.

Read-only Hub database and native ledger inspection proves that the persisted
Hub start attempt matches **two released records**, with identical binding
scope and actor. Name/attempt lookup therefore returns **409 ambiguity** and
Hub reconciliation retains its old native state. Neither record is active;
all 31 allocations remain released. Do not clear the state by hand or relax
ambiguous lookup's authorization rule.

Source `c7ac644` adds an explicit exact-claim cleanup callback. The Hub already
persists the authenticated immutable lease ID; cleanup validates its complete
lease shape, binding and attempt, then calls the existing exact-ID authenticated
release endpoint once. Existing API proof/ownership checks remain authoritative.
A denied release preserves local state; only normal observed reconciliation
clears it. Both pending adapter generations retain the new callback.

The same source prevents retiring a start attempt and recreating it under a
new workspace identity/approval-derived binding hash. It checks before member
reservation and again before CAS. A fresh attempt remains allowed. A clean
`bc9b441` regression reproduces resurrection after a legal course-ceiling increase;
the fix rejects it without reservation or ledger changes. **426 expanded tests
pass**; full suite is running. Changes are pushed but not deployed.

Both diagnostic fixtures are restored, both temporary credentials revoked,
research Pod preserved. The original registered-readiness timeout remains open:
its live diagnostic has not yet run because restart recovery blocked the request.

[Diagnostic, duplicate-history and qualification boundaries](../../platform-staging/startup-performance/qualification/exact-native-retirement-20261023/diagnostic-result.json).

### Exact retirement/reuse guard deployed; rotations 16 and 17 complete

Implementation `c7ac644` is deployed: both Hubs use
`sha256:c9756cfb7593c1997b5bc8be098b3bba5265f6fff4dbbdca3927cae630e365a0`,
gateway `sha256:fa43f725fef0b023890831a3845c101a26fc5c752251e12833b3305249e4a142`,
node `sha256:b5dd3105f7fc664a84f94c148b41e544c9a0b311c029feb9f79f4cb104e5e20d`.
The Hub-only package preserves all 78 SDK modules/dependency versions and
17 unaffected Hub modules; its three changed modules match committed source.
Gateway/node preflight validates current driver manifest/kernel/health source,
policy graph and changed installed modules without GPU calls.

The full run finished **5,222 passed, two failed, six skipped and 68 passed
subtests**. Both failures were old expectations that a stopped cleanup finalizer
ends after its first poll window. The retained deployed implementation already
retries bounded windows without releasing uncertain capacity. Test-only
`141b801` restores matching `4b3679f` tests, including delayed proof recovery,
new-generation fencing and request-timeout handling. All **448 affected tests
pass** afterward. No implementation changed after the full run.

Paired Hub rotation **16**, then server rotation **17**, preserve the original
anchor and all prior rotations, with no pending transition. Four-current
acknowledgment probes passed. Normal writer Ready; all four maintenance helpers
removed using UID preconditions. Waiting for successor Gateway readiness before
Hub patching produced **zero restarts** on both Hubs. Image/publisher inputs were
aligned in the initial exact-change plan. No driver, resource or storage change.

All **31 native allocations remain released**. The stopped Hub row still retained
its durable claim when read immediately after startup; it has not yet been
exercised through a normal restart using the new exact cleanup callback. Do not
claim live recovery or GPU startup success yet. Next: the instrumented controlled
start, capturing the original registered-readiness denial while Pending. Research
Pod remains Running at original UID.

[Published images, test boundaries, both journal rotations and cleanup](../../platform-staging/startup-performance/qualification/exact-native-retirement-live-20261023/).

### Controlled start after retirement rollout: provisioning denied, fixture restored

The single normal Source HTTP start returned **409 in 42.94 seconds**, before
Hub spawn or Pod creation. The gateway logged `/workspaces/provision` 409.
Storage lifecycle remained `provisioning`, correctly preventing changed
registration during incomplete storage work. TCP/SSH-banner connectivity to the
configured NAS bridge succeeded in 0.006 seconds; this does not explain the
original provisioning denial. A normal authenticated provisioning resume returned
`active`; no database or filesystem state was manually cleared.

Normal Source cleanup then passed: stopped, CPU profile, original membership,
ceiling and notice restored, temporary approval removed, existing grants unchanged,
all-four component readiness confirmed. QA token revoked. Research Pod remains
Running at its original UID. **No CUDA/startup pass or live exact-lease cleanup
recovery is claimed.** Capture the suppressed provisioning exception on the next
controlled run if it recurs; the earlier Pending readiness blocker remains open.

[Controlled start and restoration evidence](../../platform-staging/startup-performance/qualification/exact-retirement-start-attempt3-20261023/live-result.json).

### Next controlled start: registration denial; safe diagnostics tested

Following all-four approval readiness, one normal HTTP start returned **422 in
13.41 seconds** at central workspace registration, before provisioning or Hub
spawn. No Pod or CUDA run. Read-only policy replay afterward allowed both the
live deployment view (2.74 seconds) and same-current projection (0.0027 seconds);
this does not identify the original suppressed exception.

Compute `3330700` adds bounded exception-type/code-location logs for registration
and provisioning denials without exception text, request bodies, locals or tokens.
Regression tests first failed for absent logs; **115 focused tests pass** after
the change, including credential exclusion. Source is pushed and remote verified;
**not deployed**. Next runtime diagnosis requires this logging image.

Normal cleanup passed: stopped/CPU, original membership/ceiling/notice, unchanged
grants, temporary approval removed and four-component readiness. QA token revoked.
No claim of live retirement recovery, startup or production readiness.

[Attempt and cleanup evidence](../../platform-staging/startup-performance/qualification/exact-retirement-start-attempt4-20261023/live-result.json).

### Workspace start diagnostics deployed; rotation 18 complete

Compute `3330700` diagnostics are live in gateway
`sha256:80ebfe5745e6f1613577da2c38590c4221e2bf11c8e35c64842816f6ca3c4e6f`.
The hash-pinned wheel was installed without dependency updates on the prior
gateway image; pip check, source hashes, current policy/driver-manifest/kernel
preflight pass. The node and Hub images remain unchanged. **115 focused tests
passed** before image build. No resource, policy, driver or storage changes.

Exact-change plan and admission positive/negative checks passed. Read-only
four-current readiness first withheld rotation, then passed. Rotation **18**
preserves the anchor and all history with no pending transition. Normal writer
Ready; both maintenance helpers removed with UID preconditions.

The service predecessor chain is now 15 entries under the existing bound of 16;
plan a reviewed checkpoint before exhausting it rather than weakening the bound.
Controlled startup/CUDA qualification remains open.

[Image, preflight, rotation and cleanup receipts](../../platform-staging/startup-performance/qualification/start-denial-diagnostics-live-20261023/).

### Runtime readiness failure captured; Hub heartbeat Source fix tested

The next single normal Source start failed before Pod creation at
`/workspace-policy` (422). Read-only replay immediately afterward captured
`validate_head_ack -> _validate_ack_process`: **Stale or future component
acknowledgment**. Dynamic live policy then rejected GPU qualification while
the same-current immutable projection passed. The rejected component was not
identified in that capture. Later samples showed gateway/CPS/CIT receipt ages
roughly 47/52/50 seconds against TTL60; node age below one second. Those later
samples alone do not identify the original failure.

Code inspection found Hub heartbeat Source checks calling the full runtime
readiness endpoint, creating a circular dependency on the receipts they renew.
Compute **450ecde** switches only that Source read to the existing authenticated
`/native-group-approvals/head` endpoint. A regression fails on the prior endpoint;
**95 focused tests pass** after the change. Receipt freshness/TTL and runtime
readiness requirements remain unchanged. **Source fix not deployed yet**; its
live effect and whether it accounts for all stale receipts remain unverified.

Cleanup passed (stopped/CPU, original membership/ceiling/notice, unchanged grants,
approval removed and four-current readiness). QA token revoked; research Pod
Running at original UID. No startup/CUDA pass claimed.

[Attempt, readiness failure and cleanup receipt](../../platform-staging/startup-performance/qualification/exact-retirement-start-attempt5-20261023/live-result.json).

### Both Hub heartbeats now use Source head; rotation 19 complete

Both Hubs now use
`sha256:445c5fa48735ac077a25282256fba445a9d2af4720b994e66ca525fb519b6aae`.
An initial candidate built from the gateway SDK branch was rejected for 18-module
drift. No rejected candidate was deployed. The retained release variant
**2ed0bb8** captures the exact 78 deployed SDK modules from the prior pinned Hub
image, with a hash manifest. Only `native_group_publisher.py` changes. Image
preflight confirms the other **77 SDK modules**, all **20 Hub modules**, dependency
versions and owner-overlay support unchanged. A hash-pinned wheel is installed
without dependency updates and passes pip check. Gateway/node images unchanged.

The endpoint callback regression passes on the exact Hub variant. Broader gateway
branch fixtures fail before publisher invocation on this SDK generation and are
not variant qualification. SDK baseline convergence remains release work; the
variant branch must not be merged into gateway runtime.

Exact-change plan and admission checks pass; all-four readiness passed before
rotation **19**. Original anchor/history preserved, transition absent, normal
writer Ready, two helpers removed with UID preconditions. No policy, resources,
driver or storage change. **The service predecessor chain is now at the existing
bound of 16**: a reviewed checkpoint is required before another image transition.
The next controlled Source start remains in progress; no startup/CUDA pass claimed.

[Hub image, module verification, rotation and cleanup](../../platform-staging/startup-performance/qualification/heartbeat-source-head-hubs-live-20261023/).

### Controlled pooled workspace start and CUDA succeeded; normal stop verified

After the heartbeat rollout, one normal Source HTTP start of the controlled
10 GiB workspace (two members, existing 5 GiB grants each) returned **200 in
278.02 seconds**. One Pod UID throughout; Ready at HTTP completion, no replacement
or disappearance and no observation errors. A **64 MiB CUDA allocation, fill,
sum and synchronization passed** on one visible NVIDIA A100-PCIE-40GB.
The old persisted claim was retired by exact binding release (**200**), and
lease/compile/created all returned 200. This is live evidence of exact-lease
cleanup recovery and functional pooled startup on the current deployment.

First Pod observed at **73.25 seconds**, real node assignment at **229.92 seconds**,
Ready at **252.94 seconds**; Source response 278.02 seconds. Prepare succeeded
in **96.00 seconds**, including **50.35 seconds registered-readiness** and
**34.41 seconds enrollment-publication** (nested steps are not additive totals).
The first Prepare requested a read-only snapshot refresh. Pending diagnostics
captured transient missing `document` acknowledgment payloads and later repeated
successful current-claim validation. Heartbeat samples during approval propagation
also exceeded TTL60. **Do not claim all freshness/startup latency issues solved.**

Normal Source HTTP stop completed; the actual Pod is gone. All **32 native
allocations released**. Full fixture cleanup passed: CPU/stopped, original
membership/ceiling/notice, unchanged grants, approval removed and four-current
readiness. QA token revoked. Both Hubs zero restarts; research notebook Running
at original UID.

This instrumented single run meets the maximum 300-second bound, but it does not
prove burst p95<=180 seconds, current over-cap peer isolation, cross-Hub pooling,
20 GiB/eight-GPU packing, scheduling/reclaim or overall production readiness.
Next focus: reduce the measured registered-readiness/publication delays; a
reviewed service-configuration checkpoint is needed before another image rollout
because the retained predecessor chain is at its existing bound.

[Actual start, CUDA, timing, heartbeat samples and full cleanup](../../platform-staging/startup-performance/qualification/exact-retirement-start-attempt6-20261023/).

### Measured read path and correction to service ancestry count

Read-only profiling against the live gateway found **0.60-0.62 seconds** for
HeadSource.load with 44 retained history entries, **0.0032-0.0039 seconds** for
the SQLite registry snapshot, and **0.227-0.230 seconds** for typed current
NodeConfiguration.load. No runtime factory, writes, GPU calls or qualification
bypasses were used. These are idle reads; they do not prove startup-load cost,
but do not support attributing the 50-second registered-readiness wait to slow
immutable reads alone. Node logs show readiness withdrawals while custody was
changing during binding; the full cause/timing needs handoff profiling.

**Correction:** walking the actual typed current Node configuration reports
**15 service-image predecessor links**, under the existing bound16. The prior
count16 was an incorrect inference from rotation count. **One additional service
image link remains available**. The existing delivery-journal checkpoint seals
a separate 48-rotation lineage and does not compact this Node service chain.
Do not treat that command as a solution to service ancestry or weaken the bound.
A reviewed service-chain migration is still needed before the following rollout.
No deployment or workload changes were made for this profile.

[Read-only samples and authoritative ancestry count](../../platform-staging/startup-performance/qualification/heartbeat-read-profile-20261023/profile.json).

### Short failure retries implemented and tested; not deployed

The installed heartbeat loops wait their full normal **20 seconds after a failed
proof**. New regression tests reproduce that delay in both Gateway asyncio and
Hub Tornado scheduling. Compute **45be9b5** now retries failed proofs after
**one second**, while successful publication retains the normal 20-second
cadence. Hub callback scheduling adjusts its next interval after each outcome.
Every attempt still executes the complete proof; failed attempts publish nothing.
No cached authorization, extended TTL or concurrent proof attempt is introduced.
The loaded Tornado scheduling implementation reads callback_time for each cycle.

**95 focused tests and 99 additional head/readiness tests pass**. The same patch
on the exact captured Hub SDK branch (**fd7a65d**) passes its **three endpoint/
cadence regressions**, preserving the unrelated deployed SDK baseline. Both
source branches are pushed. **No new image is deployed**, and no startup-speedup
claim is made. Only one service-image ancestry slot remains, so Gateway and paired
Hub image changes cannot both be appended without a reviewed ancestry migration.
The current live success remains the single 278-second pooled CUDA start.

[Tested source and exact verification boundaries](../../platform-staging/startup-performance/qualification/heartbeat-fast-retry-source-20261023/result.json).

### Writer-only service-compaction draft rejected; production guard retained

A source-only draft attempted to archive a service segment while removing only
its current `service_image_predecessor_ref`. Although 322 related tests, 17 draft
scenarios and 58 independent-review tests passed (overlapping sets), offline
parsing against the **actual current live graph** in the deployed Gateway image
rejected the compact configuration: **Policy image edge must preserve every
other actual Node configuration field**. The real configuration retains an addon
policy edge; its images cannot lose the typed service provenance.

Independent review confirmed that mismatch and found another draft-only flaw:
quiescence proof lost after journal commit could leave ordinary tick Ready
without durable incomplete-handover state. **No draft image or configuration was
deployed.** The draft and review are retained privately; its production changes
and synthetic-only tests were withdrawn from the implementation worktree. No
guard, bound, journal, anchor, runtime image or workload was changed.

Compute **d33ac3e** retains only a regression proving that unlinking a real policy
image edge is rejected without modifying authentic ancestry. **63 relevant tests
pass.** Heartbeat retry source remains 45be9b5/fd7a65d, not deployed. One image
slot remains, as directly measured earlier.

The existing `continue_policy_configuration`/reviewed addon-image transition
path already preserves the actual old service context while starting a new
segment. Evaluate it as part of the real required notebook/addon release, with
software-preservation evidence and all normal gates. Do not manufacture a policy
change merely to evade the service bound. A general compaction feature would
need retained typed policy/service provenance and durable recovery semantics.

[Rejected-draft boundary and retained guard regression](../../platform-staging/startup-performance/qualification/service-compaction-rejected-20261023/result.json).

### Current modular release artifacts qualified offline

Release branch **212307b** rebuilds the prebuilt Compute loader against
minimum-supported **JupyterLab 4.5.7** metadata and the locked frontend toolchain.
Two consecutive builds produce identical asset hashes. All **97 frontend tests
pass**, including typed Hera serialization, current policy/resource validation,
notebook control-cell execution rules, dynamic snippet/workload models, visitor
identity request behavior and lifetime warnings. Initial local test runs lacked
the Python SDK/Hera/Hub source paths; the final run uses the qualification
interpreter and explicit application source paths. No tests were weakened.

SDK, Hub and Lab wheels and sdists build. Package verification passes for both
direct wheels and wheels rebuilt from all three sdists; **all uncompressed wheel
payloads match exactly**. Namespace/dependency/install destinations remain
separate, with server autoenable and registered Hub spawner verified. Fresh
noneditable installations pass pip check and installed-runtime probes: lean SDK
without optional runtimes, import-safe Node modules, Hub5.5.2/KubeSpawner7.1.0,
and Lab **4.5.7 and 4.6.4**. Only the addon owns its six prebuilt assets; uninstall
and reinstall preserve SDK. The 4.6.4 lifecycle also verifies removal of Python
hooks and server autoenable configuration. Final oldest-supported assets were
reinstalled and reverified in both Lab versions.

This closes current artifact/installed-package checks, **not live release
qualification**. Wheels remain local candidates; no release/tag, container,
software-preservation attestation, policy handover or deployment was performed.
It does not resolve the existing Hub SDK source-variant convergence or prove
live browser behavior. The runtime remains the earlier qualified single pooled
CUDA start at 278 seconds. A genuine notebook-image update still requires its
complete inventories/OCI preservation proof and normal gated policy transition.

[Source pin, wheel/sdist hashes and exact qualification scope](../../platform-staging/startup-performance/qualification/modular-packages-20261023/qualification.json).

### TTL-15 trial rejected; original runtime restored

A config-only trial lowered Gateway and both Source publisher approval TTLs to
15 seconds (5-second normal cadence), without changing images, Node/delivery
configuration, or the journal. Eight idle read-only samples were Ready, but the
fixture's final profile validation returned HTTP 422 before any start request
or Pod creation. A subsequent read-only policy replay passed; the original
rejection cause is not established. Idle readiness does not qualify the trial.

The original Gateway and both Hub Deployment specs are restored exactly and
all three are Ready. Normal cleanup confirms the fixture is stopped, CPU profile,
membership, ceiling and notice restored, temporary approval removed, four
components Ready and existing grants unchanged. The research Pod remains Running
with its original UID. No database/journal reset or reservation deletion was used.

[Trial and verified rollback boundary](../../platform-staging/startup-performance/qualification/heartbeat-ttl15-trial-20261023/result.json).

### Workspace policy event-loop starvation reproduced and fixed in candidate

Compute **0e33b68** moves both read-only workspace-policy proofs to the existing
shielded worker helper. Four regression cases fail before the change because
validation blocks heartbeat progress, then pass afterward; eight focused tests
pass. Independent review confirms per-call database connections, serialized
readiness-cache access, preserved denial behavior and safe worker completion
after disconnect. Member reservation acquisition remains synchronous and this
does not prove a faster complete startup.

Gateway **6ae6e7f…631890** is deployed after no-GPU installed-source, actual
driver-manifest and current policy-graph checks. It also contains the earlier
failed-heartbeat retry change. The full suite passes: **5,238 tests and 68 subtests;
six skipped** (623 dependency/deprecation warnings, 640.88 seconds).

The gated handover preserves the original anchor and every prior journal
rotation; rotation count is 20 with no pending transition. Gateway, observer and
normal writer are Ready. Admission accepts the approved Node-agent Pod and
rejects wrong bootstrap, wrong owner and extra host mount. Both maintenance
helpers were deleted with UID preconditions. Live policy/heartbeat module hashes
match the candidate. Policy, driver and storage are unchanged; the research Pod
retains its original UID. Controlled full-start measurement remains pending.

[Candidate source, digest and exact verification boundary](../../platform-staging/startup-performance/qualification/policy-event-loop-20261023/result.json).

### Controlled pooled start after event-loop fix: 209 seconds

Normal Source HTTP start returns **200 in 209.22 seconds**, versus 278.02 seconds
in attempt 6 (about 25% faster). The same Pod UID remains present without
replacement or observation errors, reaches Ready, and passes a 64-MiB CUDA
allocation/fill/sum/synchronize check on one A100. First observed Pod is at
81.47 seconds, node assignment at 167.00, Running/Ready at 181.61; the final
Source response follows later.

Coordinator Prepare succeeds in **61.10 seconds**, versus 96.00 previously.
Registered-readiness time is **7.20 seconds**, versus 50.35 previously; enrollment
publication remains **39.43 seconds**. Nested stage durations are not additive.
This supports the readiness-path improvement; it does not isolate every cause
or establish repeatable burst performance. The 209-second result remains above
the p95 target; one successful start cannot establish a p95.

Normal Source stop returns 200 in 17.13 seconds. The actual Pod is gone and all
**33** native allocations are released. Fixture CPU profile, membership, ceiling
and notice are restored; its temporary approval is removed, four components
are Ready and existing grants unchanged. The temporary scoped token is revoked.
The research Pod remains Running with its original UID. No SQL release or
lease-expiry inference was used.

This is a single 10-GiB pooled start from two existing 5-GiB member grants on the
selected A100. Full-pool, 20-GiB, cross-Hub concurrent starts, burst latency and
broader production qualification remain separate gates. Next timing targets
are pre-Pod work and enrollment publication.

[Sanitized exact start, CUDA, nested timing and cleanup proof](../../platform-staging/startup-performance/qualification/policy-event-loop-start-attempt8-20261023/result.json).

### Context prefetch experiment rejected after measurement

A fresh read-only benchmark on the actual Gateway compares three alternating
loads of baseline and expanded immutable-ancestry prefetch. Both issue **102 GETs**
per complete current-context load. Baseline is **0.566–0.581 seconds**, candidate
**0.537–0.553 seconds**: about 5%, less than one second estimated over 28 calls.
The candidate preserves validation/fresh repeated reads and passes focused
checks, but that benefit does not justify the additional traversal/prefetch
complexity. Its draft was withdrawn; **no deployment or policy change**. The
full candidate suite was intentionally interrupted after withdrawal (1,173
passed so far, three skipped, 19 subtests); this is not a full-suite passing claim.
The deployed 0e33b68 full-suite and controlled-start evidence above still apply.

Timestamped existing logs show Hub accepted the spawn at **19.69 seconds**,
while the Pod appeared at **81.47 seconds**. Lease response completes at 71.68
and compile at 80.79. The Pod has **no readiness probe**; its Running/Ready at
181.61 is not proof that Jupyter HTTP was ready then. Native accepted/close
complete at 182.15/182.17; Hub/Source readiness completes around 209 seconds.
Shares take under one second at the end. The next useful trace is notebook
startup plus the Hub's pre-Pod path, rather than a speculative cache or a claim
that the 27-second post-Pod interval is itself a bug.

[Benchmark and withdrawal](../../platform-staging/startup-performance/qualification/context-load-profile-20261023/result.json),
[response milestones and readiness boundary](../../platform-staging/startup-performance/qualification/context-load-profile-20261023/attempt8-http-milestones.json).

### Current cross-Hub native5 running pair and peer-safe shutdown verified

The newer CIT student fixture uses the already reviewed Armin identity and its
existing **global CPS-owned 5-GiB grant**. No grant or membership is added. CIT
starts through the operator service lifecycle in **283.32 seconds** and passes
CUDA on its original Pod. While it remains Running, the CPS Mikasa fixture is
approved and started at 5 GiB in **241.63 seconds**; its original Pod also passes
CUDA. The CIT bounded probe completes **5,981 GPU progress iterations** through
the second start. Both Running/Ready Pods are observed together with **two
5120-MiB native allocations on the same physical selected A100**, and separate
canonical people reserved once each. No MIG or driver/image changes.

Normal CPS stop takes **13.04 seconds**. Its actual Pod disappears and its
allocation retires while CIT keeps its original UID/allocation and passes CUDA
again. A further bounded CIT probe completes **898 iterations** through the CPS
stop. CIT then stops normally in **23.60 seconds**. Both fixtures return to their
CPU profiles, original ceilings/notices and original memberships; temporary GPU
approvals are removed and all four components are Ready. Both Pods are absent,
all **35** native allocations are released, reservation/member-binding tables
are empty and the global grant-row fingerprint is unchanged. Research Pod UID
is preserved.

**Authentication boundary:** the normal CIT HTTP attempt did not reach Start.
Hub rejected akadmin identification because the upstream OIDC token expired
October 15; console responded with an OAuth redirect. The temporary scoped API
token was revoked and re-login requested. No auth check was bypassed. These
service-lifecycle results do **not** qualify browser/admin-UI OAuth or ordinary
student access. The legacy CIT pilot fixture was skipped because its teaching
memberships expired and its central registration uses an older policy; its
reviewed identity links are valid and it was not modified.

Notebook logs identify another concrete startup cost: installed
`notebook_intelligence` **4.6.0** loads about **15.01 seconds** after the preceding
Notebook extension. Its initialization eagerly constructs a Claude client, whose constructor calls
`connect()` and waits on `_connect_resolved` for the configured **15 seconds**.
The running notebook logs the matching handshake-timeout warning. A package-level
fix should defer this agent startup while preserving connection-failure reporting;
it has not been implemented. Both measured starts
remain above the p95 target. This running pair is not a simultaneous burst,
full-pool/20-GiB qualification or injected same-person reservation conflict.

[Exact caller boundary, starts, same-device pair, peer survival and cleanup](../../platform-staging/startup-performance/qualification/cross-hub-native5-20261023/result.json).

### NBI startup candidate qualified and published; live handover remains open

Notebook source branch `fix/nbi-lazy-claude-20261023` contains the reviewed
runtime patch at `9ea3accc594f4a3d1b29798997fb8879dc433c80`. The distribution is
`notebook-intelligence==4.6.0+cps.2`; only the eager constructor connection is
removed. First-use connection, real failure reporting and reconnect remain
functional. The first `cps.1` candidate correctly failed `pip check`: its new
FastMCP bound was too restrictive for the approved image's installed 3.2.4.
The revised bound permits the tested 2.14.7/3.2.4 APIs while excluding 4.x.
No production dependency downgrade occurred.

The pinned wheel rebuilds byte-identically with SHA256
`bef15b74370cfd7ddc55fc9034d105e6c21e4b6bfc4e39d7b7a6edc638a0b71e`.
RECORD integrity, unchanged other Python/frontend payloads and upstream-pin
rejection pass. Three controlled-SDK tests pass in clean environments and the
actual approved notebook base; image `pip check` passes. The repository suite
passes 52 tests and 22 subtests. Independent review reproduces the artifact hash.

Candidate `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:3eabf4238cdc1b48b5e945d62a5bf8bd22761891cbba91ba2aa2c0e54c776b56`
is published. Registry manifest bytes match the tested OCI export exactly.
All 86 approved base layers/diffIDs and runtime settings are retained. A read-only
base-image mount verifies all 79 original NBI payloads against upstream. The two
additional layers contain 116 non-directory entries, confined to NBI and temporary
build paths; no other dependency files change. The temporary builder is stopped,
its SSH forward and image mount removed, and the redundant OCI tar removed after
registry verification. GPU2 preloads the image in 2.88 seconds. The research Pod
remains Running with its original UID. These are package/build checks, not new GPU
execution or live Hub startup results.

**Handover boundary:** the current typed image edge permits only changes to
`cps-compute-jupyterlab`; it correctly excludes NBI dependency changes. A standalone
fresh hardware root also cannot silently retain the current anchor/history.
Review confirms that a new typed migration is needed to authenticate this class
of dependency update while preserving the existing Node context and its 16-link
service history. The candidate remains staged; no guard, policy, database or
journal reset is used to promote it. The full production gates above remain open.

[Canonical package instructions](https://github.com/mul-cps/cps-jupyter-notebook/blob/7921ee7df170f00daf454ab947c5071534915ad7/release/nbi-startup.md)
and [candidate image receipt](https://github.com/mul-cps/cps-jupyter-notebook/blob/7921ee7df170f00daf454ab947c5071534915ad7/release/nbi-startup-image-qualification.json)
retain the exact source, artifact and qualification boundaries. The cluster
configuration verification command also passes; this does not qualify scheduling
or a production release.

### Full-pool scope correction (2026-10-24)

Dynamic native group sharing is not yet an eight-GPU implementation. The pending
Pod compiler authenticates one fixed approved Node/GPU tuple
(`cps-compute/src/cps_compute/native_gpu_pending.py`, `_approved_binding`), and
runtime construction supplies one deployment/pool to `NativeGpuGroupAuthority`.
The trusted binder likewise pins the approved tuple. Full-pool work therefore
requires qualified multi-pool selection and placement, not just additional
packing tests or removal of an allowlist.

The read-only worker inventory on 2026-10-24 found eight physical A100-PCIE-40GB
cards across four workers, with seven advertised to Kubernetes (2/1/2/2).
GPU2 deliberately advertises only its qualified UUID. All four workers report
615.71.09, but only GPU2 has the native import-guard parameter and load manifest;
the matching version string on the other workers does not establish matching
native ABI support. The second GPU2 card and the other workers must not be
implicitly admitted by widening inventory configuration.

Required work remains: qualified per-device authorities and selection, retained
per-device custody/epochs, shared global reservations, compatible guarded worker
rollout and hardware evidence for every admitted device, followed by full-pool
packing, reclaim and startup-burst qualification. Existing single-device
isolation passes remain valid within their measured scope. No driver, kernel,
MIG, device allowlist or production placement setting was changed by this audit.

### Fresh-policy handover software qualified; candidate images published

Application source `453c4f5f2ff2bb2d585fdfb645008e4be8af8b9a` implements the
reviewed fresh-qualification bridge, retained bounded Node history, append-only
Source migration, exact committed retry and durable four-process publication.
Independent review resolved repeated historical traversal, bootstrap image-pin
and operator-proof read-permission findings. The full Python suite passes
**5,320 tests and 68 subtests**, with six skips and 623 warnings (660.21 seconds).
This is software evidence, not new GPU evidence.

The SDK wheel checksum is
`cd0c1866a3cc4229fd0bd829d1d5310a6a8c9e518aeb2cdcd0ea3852220b5d9a`.
All 81 packaged Python modules match source and all 83 RECORD hashes verify.
It owns no Hub or Lab extension payloads. Published candidates are:

- Node: `ghcr.io/mul-cps/cps-native-node@sha256:c2f125440cfa0b339a776bcf82e0060b1a569622373ab9edee91a71d611727f8`.
- Gateway: `ghcr.io/mul-cps/cps-compute@sha256:bcf7bcf1e75d2a981bbbdbbbc63cb1ed7eec700a3397a2e7b4b422f4d64d371b`.

Both registry manifests match the tested OCI archives byte-for-byte. Both actual
images pass `pip check`. The Node image loads a synthetic fresh-policy history
graph with no network/host mounts. The unmodified Gateway image passes a synthetic
Source append/retry/grant-preservation transaction; nine API tests pass against
its installed wheel and pinned FastAPI 0.142.2/Starlette 1.3.1. Added QA tooling
preserves all 44 production dependency versions. These CPU fixtures do not
establish hardware isolation or live migration readiness.

Read-only Hub inventory confirms CPS/CIT installed SDK and Hub payloads match
each other. All 20 installed Hub adapter Python files match the candidate source;
the compatible Hub artifact still needs building and qualification with the new
SDK. All cluster nodes remain Ready, and research Pod `jupyter-gottam` retains its
original UID. No production image, policy, journal, reservation, driver or kernel
was changed by this implementation/build work.

Next are compatible consumer artifacts, actual target-notebook hardware evidence
and a fenced handover with matching backups, current acknowledgments, startup
measurements and normal cleanup. The eight-GPU implementation gap above remains
open. Do not enable the new notebook image using old qualification receipts.

[Canonical operator guide](https://github.com/mul-cps/cps-compute/blob/453c4f5f2ff2bb2d585fdfb645008e4be8af8b9a/docs/native-qualified-policy-transition.md)
and [software candidate evidence](https://github.com/mul-cps/cps-compute/blob/a68686d5ddbaf317d72d4a9c5abe6046caf61703/releases/native-qualified-policy-20261024/software-qualification.json)
record the exact application scope and remaining gates.


### 2026-10-24: NBI preservation evidence and compatible Hub candidate

The corrected, reviewed read-only collector completed both immutable notebook
inventories: 261,444 base entries and 261,446 candidate entries. There are 107
changed filesystem entries; only `claude.py` and `_version.py` change source
content, and hardlink topology is unchanged. All 28 compiled Python files in
each image match compilation of their inventoried source. Installed wheel
payloads and distribution RECORD hashes verify for both images. Exact material
hashes and explicit exclusions are published in the notebook repository's
`release/nbi-filesystem-comparison-evidence.json` at commit
`b0d9a0d04ab2d2e26011b856442dc025bf0dc1bb`.

This supports implementing a separately typed, narrowly scoped NBI software
preservation edge, retaining the original measured hardware evidence. It does
not assert that this candidate passed new hardware gates. The existing Lab
preservation allowlists must remain unchanged. Raw added-layer/whiteout handling,
sealed NBI admission, authenticated policy handover and live startup/restart
verification remain open; the notebook candidate is not deployed.

The compatible Hub candidate now builds successfully using overlay storage.
Its dependency check and actual Hub adapter import pass. All 137 installed
package versions match the deployed baseline; all 81 SDK Python files and 20
Hub adapter Python files match their exact wheels. This is candidate software
verification, not a live Hub rollout or production qualification.

A current read confirms all seven nodes Ready and research Pod `jupyter-gottam`
Running with UID `fe5fb5e7-8696-4ac3-a5a8-1883817d00bb`. No production workload,
policy, driver, kernel, NFS path or reservation was changed in these checks.
The full eight-GPU implementation and broader production acceptance gates remain
open as recorded above.


### 2026-10-24: sealed NBI preservation and service-upgrade prerequisite

Application source `dadf786a472b745a77f5434c84691a4bf1ffa7a9` implements a
separate release-pinned NBI preservation type. Unknown/modified/rehashed material
is refused; existing Lab validation remains separate. Eleven NBI tests pass,
including caller-mutation and cold immutable-authority binding checks. Independent
review has no remaining Critical or Important findings. Installed-wheel and all
three actual consumer-image CPU probes load the exact root and retain the original
synthetic hardware proof/reference; the Gateway image also preserves grants and
two prior revisions through a controlled Source append. These are software tests,
not new hardware measurements or deployment evidence.

The broad source run recorded 5,322 passes and nine subprocess-import failures
because its child interpreter lacked the checkout path. All nine reran successfully
with explicit absolute PYTHONPATH. Those results must not be described as a single
clean full-suite run.

A live preflight authenticated the entire current 16-link service prefix (17
immutable objects), exhausting the old service budget. The active immutable
Observer release has a non-null held-template hash matching the actual Node;
both Hubs' mounted native settings are ordinary enabled version2. Reviewed source
`f895b6820ef89eecfeea0c53a59b32282051562f` raises only the service budget to18,
retaining the complete prefix and the existing Gateway/Node then paired-Hub
rotations. The separate policy depth remains16. Link18 loads with bounded reads,
retained proof and previous-policy context; link19 fails before excess traversal.
Ninety-eight focused service/NBI/delivery tests pass. A clean full run with the
corrected test environment is in progress; compatible consumer images are being
rebuilt. Compatible Writer/Observer/operator readers, matching backups, actual
current acknowledgments and controlled activation are still required.

No production policy/image, reservation, driver, kernel or research Pod was
changed. Full-pool implementation and the remaining production acceptance gates
remain open.


### 2026-10-24: verified SDK reader and Gateway/Node deployment

The final corrected software run completed with **5,332 passed, 6 skipped and
68 subtests passed** (664.79 seconds). Runtime source is
`f895b6820ef89eecfeea0c53a59b32282051562f`; subsequent test and receipt commits
do not change packaged runtime code. The independent package/image checks and
conditional-test coverage are recorded in the application release receipt
`releases/nbi-preservation-20261024/software-qualification.json`.

The exact tested artifacts were published and the Writer, Observer and Gateway
now run `ghcr.io/mul-cps/cps-compute@sha256:9d292feffdef9accad2d020009f4f674e1e4770a8f524703f028b201db5ec0f5`.
The Node main/bootstrap pair and its declared image now use
`ghcr.io/mul-cps/cps-native-node@sha256:fed4253e1f7179c912607631691a60800adb9c65405404261e939f5fa1140451`.
The Gateway/Node successor retains the entire service prefix at link17. Approved
Pod admission succeeds; altered bootstrap, owner and extra host mount probes are
rejected. All four current component acknowledgments pass the authenticated
readiness check after activation.

The Writer journal retains its original anchor and all 20 prior rotations;
rotation21 completed with no pending transition. Before this operation, all four
Source SQLite databases and the Node private state were backed up with payload
hash verification; both trusted PostgreSQL Hub backup Jobs completed successfully.
The temporary two-lock fence and rotation helpers were removed and the owned
worker cordon was removed. The protected research Pod remains Running with its
original UID. No driver, kernel or storage-path change was made.

The paired-Hub successor at link18 is created but **not active**. Its nine inactive
inputs include both new Hub publisher image pins and the compatible capture
reader. Review caught and corrected stale Hub image pins before activation. The
Hub candidate, notebook NBI image, NBI policy handover and actual notebook startup
and restart timing remain pending. These service deployments do not qualify the
full eight-GPU pool or close the remaining production acceptance gates.


### 2026-10-24: paired Hub SDK upgrade active

Both CPS and CIT Hubs now run the tested image
`ghcr.io/mul-cps/cps-compute@sha256:83fdd8c1ef66b66de71fccf0657c40d722fa28310e0bcb819c538fad01873b21`.
Live package checks confirm JupyterHub5.5.2 and KubeSpawner7.1.0 on each Hub.
The capture sidecar now uses the same SDK image as the Gateway. The immutable
service successor retains all18 links. Exact runtime and each Hub publisher
image pins were corrected and independently reviewed before activation.

The two-phase acquisition fence remained held until the old Gateway disappeared,
released only for replacement initialization, and was reacquired before either
Hub replacement. It remained held through current four-component readiness,
clean-custody checks and configuration rotation. The CPU helper test verified
both locks across held/released/held/exit phases without replacing lock inodes.
Actual Pod deadline margins and live-heartbeat checks bounded each mutation.

Rotation22 preserves the original anchor and all21 earlier entries, with no
pending transition. All six Deployment specifications match the reviewed plan;
each has one Ready replica. A post-rotation authenticated readiness check passes
for Gateway, Node and both Hubs. The fence exited normally and the target worker
is schedulable again. The protected research Pod remains Running with its original
UID. Driver, kernel, compute policy and notebook image remain unchanged.

The NBI notebook policy/image handover and measured startup/restart check are
next. Full-pool implementation and the remaining production acceptance scenarios
are still open. Separately, CIT logged a missing `oauth_user.groups` auth-state
claim during activity refresh; group ownership and effective entitlement behavior
need checking before production qualification.

### 2026-10-24: notebook handover exclusions checked

The NBI candidate remains staged; the active notebook image and policy are
unchanged. Read-only backups verified all four Source database payloads, 113
journal files (22 retained rotations), and 201 Node-state files against their
recorded sizes and SHA-256 hashes. Both Hubs, both consoles, Gateway, Writer,
Observer and Node remain Ready; the protected research Pod retains its UID.

Handover review identified the separate, running lifecycle147 QA Gateway as
another launch path. Both prospective execution guards now bind its exact UID,
paused specification and absence of selected Pods, bringing each guard to nine
Deployments. Regression cases reject a resumed QA Gateway, replacement UID or
remaining QA Pod; the combined operator-guard suite passes 39 tests. Revised
read-only permissions passed Kubernetes server validation. The normal Writer
and four-component readiness, preserved Source/journal history, actor and
permission checks must pass before final fence release and Service reopening.
These are prepared maintenance safeguards, not evidence of live NBI activation
or faster notebook startup. Production maintenance has not started.

### 2026-10-24: NBI policy handover active; real start exposed filesystem regression

The fenced handover completed. Policy 0.1.3
`sha256:9d86546fd3b9cc52eb92f030932c64600d352884f949c7d06b8b86a0f1f42620`
and Source generation 53/revision
`sha256:992ae99b027bccef76a537ce91fd6f249f48df6f6263523652ae54fc8985b863`
are active. All 53 previous Source document bytes remain intact, with one
new policy record and one success audit. Journal rotation 23 completed with the
original anchor and previous 22-rotation history retained. Both Hubs, consoles,
Gateway, Node, observer and normal Writer were Ready after reopening; the three
existing notebook Pod UIDs were preserved. Shared 5/10 GiB profiles now authorize
notebook digest `3eabf4238cdc1b48b5e945d62a5bf8bd22761891cbba91ba2aa2c0e54c776b56`.
This is activation evidence, not full-pool or notebook runtime qualification.

A normal Start of `shared-gpu-lab` initially returned 422 before any Pod existed.
The Gateway trace localized rejection to `private_file` in the native custody
writer guard: private state directories had become 02770 and regular files 0660.
The main Gateway completed its private-mode initialization at 05:11:22Z.
The legacy QA Gateway subsequently mounted the same compute-state PVC at
05:16:35Z with fsGroup 10001 and no fsGroupChangePolicy, whose default is recursive
Always. The publication helper mounts a separate journal PVC and is not the
conflicting mount. The guard correctly
refused group-accessible custody state. Owner-only 0700/0600 permissions were
restored for both custody directories and the storage-lock directory; every
device/inode identity was verified unchanged. No lock was unlinked, no database
rewritten and no allocation was inferred released. Normal Stop then returned 200.

The legacy QA Deployment was updated using UID/resourceVersion/spec-preconditioned
JSON Patch to use `OnRootMismatch`, with a successful server dry-run and rollout.
All three private directories remained 0700 and their regular files 0600 after
the new QA Pod mounted the volume. The operator packaging must preserve this
policy and check private state permissions after every volume handoff. A successful Start,
CUDA smoke, Stop/restart and timing on the newly authorized image remain required.
Private operational receipts are retained outside Git under
`nbi-policy-handover-20261024/` and `nbi-workspace-validation-20261024/`.

The next actual Start created Pod UID `396514af-225a-429f-93bf-c935588c9633`
on GPU2 with the new notebook image. It did not pass qualification: Prepare took
82.74 seconds, and final Accepted observation encountered a closed 60-second
execution fence (custody changed from binding to held). The Pod's cap-gate init
completed successfully in 19 seconds, device-identity init in one second; the
notebook ran for five seconds before controlled cleanup terminated it. The
source request failed after 307.58 seconds; no CUDA probe ran. This does not
requalify startup or disprove the previously passed CUDA isolation tests.
Normal Stop subsequently returned 200. The test token was revoked, and 15
temporary handover Pods/reader RBAC/Secrets were deleted with exact UID
preconditions. Final acceptance performance remains the next runtime blocker;
no fence timeout was extended and no authorization check was bypassed.

### 2026-10-24: accepted-read candidate published; handover staged

SDK commit `be2097292ccca44ab7f39d1a4d262fa1e9fca72a` overlaps only the
independent Pod/Node/BindRequest GETs in final Accepted observation. Both read
barriers, final fresh authority/claim checks, custody checks and the original
execution deadline remain. Focused tests passed 62 cases; independent review
passed 20 witness cases with no Important findings. The complete run passed
5,326 cases and failed nine subprocess import cases because its interpreter
lacked an installed SDK. Installing the exact tested wheel without dependency
changes made all nine pass (six skips and 68 passing subtests retained). This
is combined evidence, not a claimed single clean full run.

Published Gateway candidate:
`ghcr.io/mul-cps/cps-compute@sha256:5f924667f14e4922090ead270bbf3521005d655570b79c063a1d6de958080bb1`.
The registry manifest matches the tested OCI. Only the coordinator SDK payload
changed; 82 other payloads match the prior wheel. Installed Python 3.12 image
checks prove overlapping reads, ordered results and drained siblings on failure
and cancellation. Live acceptance-budget improvement remains unproven.

The actual staged immutable successor validates through NodeConfiguration.load
and retains its exact predecessor and original measured proof, changing only
the Gateway authority image. Nine passive consumer inputs are staged with the
new bootstrap unreleased. Both Hub runtime-reader Roles retain their full
existing rules and add only GETs for the two new ConfigMaps; all four live
subject access reviews pass. No running service template has switched. Fresh
checks found nine Ready baseline Deployments, the three original user Pod UIDs,
both native ledgers released and both GPU2 devices at zero memory use with no
compute clients. A read-only SQL snapshot retains all 54 Source rows and the
active generation-53 head.

The pending activation must preserve continuous launch exclusion and actual
native lock custody, validate successor admission before bootstrap release,
confirm all four genuine ACKs and rotate the existing journal to entry 24.
Any attempted or ambiguous rotation prohibits automatic old-image/journal
restoration. Actual GPU Start/CUDA/Stop/restart and the broader production gates
remain open. Software evidence is canonical in cps-compute commit `8bbbd5d`;
private execution material is retained in `accepted-parallel-rollout/`.

### 2026-10-24: candidate active at rotation 24; first CUDA pass, restart still blocked

The same-policy Gateway handover to digest
`5f924667f14e4922090ead270bbf3521005d655570b79c063a1d6de958080bb1`
is complete. Exact Node/RS/bootstrap admission checks passed all four positive/
negative cases; Node and Hub images, driver and kernel stayed unchanged. The
normal Writer, observer, Hubs and both consoles are Ready. Rotation 24 retains
the original anchor, all 23 prior entries and 117 prior immutable journal files;
all 54 Source rows and generation-53 head remained exact. The owned cordon was
restored, Source Services reopened last, and temporary fence/operator/NetworkPolicy
resources were deleted after normal termination and UID checks.

A real normal-API `shared-gpu-lab` 5 GiB Start now passed on notebook digest
`3eabf4238cdc1b48b5e945d62a5bf8bd22761891cbba91ba2aa2c0e54c776b56`,
with one visible GPU and a synchronized 64 MiB CUDA allocation/result check.
The Pod was neither replaced nor lost. It took 263.65 seconds end to end:
first Pod observation 96.40 seconds, node assignment 236.47 seconds and first
Ready 253.20 seconds. Stop returned 200 in 23.42 seconds and the Pod disappeared.

The restart did NOT pass: two registered-snapshot-refresh responses caused long
Prepare replays, then the spawn timeout deleted the pending Pod. It failed after
315.89 seconds without a CUDA probe. This is a demonstrated startup/restart
reliability blocker, not evidence of a new CUDA isolation failure. Final Stop
returned 200; both native ledgers are released, GPU2 has zero memory use/no
compute clients, all three existing notebook Pod UIDs are unchanged and the
short-lived test token is revoked.

The next surgical change is to carry genuine fresh Node resourceVersion/body
progress through registered read-only Prepare when its full semantic projection
is unchanged, rather than replaying the whole operation. UID, specs, labels,
capacity, allocatable, driver/epoch and current Source/claims must remain checked;
Pod/BindRequest and semantic changes must retain their rejection path. Startup
p95 <=180 seconds and maximum <=300 seconds, reliable restart and the remaining
full-platform gates are unqualified.

### 2026-10-24: Node heartbeat candidate qualified in software; live handover pending

SDK source `fce2a828d13c4f3e9f08f7732b3855a35cd664d1` carries genuine
request-local Node body/RV progress into private staging when identity and the
full semantic projection are unchanged. The caller snapshot stays unchanged; an
initially stale reference still requires refresh. Both the refresh and heartbeat
paths retain the same read-only untouched-state proof, repeated stock-map and
publication checks, fresh authority/ACK/custody checks and execution timeout.

The final single full run passes **5,348 tests and 68 subtests**, with six skips
and 623 warnings, in 675.68 seconds. Separately, 178 focused regressions, seven
mid-proof drift cases and 63 operator-helper cases pass. Independent review has
no remaining Important/Critical finding. The rebuilt Python 3.12 image passes
import and dependency checks; only the coordinator module changes, with the
other 82 SDK payloads preserved.

Published immutable candidate:
`ghcr.io/mul-cps/cps-compute@sha256:0ed58c6b39e15a25f4f2d10fa1c99b8f18db3f3bcb3060975ece8dd65cdcc069`.
The registry manifest digest is verified. The canonical
[application software qualification receipt](https://github.com/mul-cps/cps-compute/blob/7a91f7711e189d16fae75d5d0843f59f99759964/releases/node-heartbeat-20261024/software-qualification.json)
records the exact wheel/module hashes and the unqualified live boundary.

The image-only successor Node configuration is staged and typed-validated, but
is inert: the Gateway still runs the rotation-24 image. Read-only preflight
confirms nine Ready deployments, three unchanged user Pod UIDs, released native
ledgers, no GPU2 compute clients and the same 54 Source revision rows/head. No
maintenance exclusion or application rollout has started. Normal console Start,
CUDA result, Stop/restart and the startup latency limits remain to be measured
on the new image. The overall production plan remains unfinished.

### 2026-10-24: journal25 active; ACK renewal liveness reproduced and isolated

The image-only handover to Gateway digest `0ed58c6b39e15a25f4f2d10fa1c99b8f18db3f3bcb3060975ece8dd65cdcc069`
is complete. Journal25 authenticates every archived predecessor, retains the
exact original anchor and all 24 prior entries, and preserves 123 prior files.
The 54 Source rows/head, Node/Hub images, driver/kernel and existing notebook
Pod UIDs remain unchanged. All nine deployments are Ready, the owned cordon is
restored, Source Services reopened last and temporary helpers/NetworkPolicy are
removed. Before activation, private backups verified 219 Node files, four
databases and 124 journal files.

The normal-console Start did **not** pass: it timed out after 313.18 seconds
without CUDA execution; its Pod was deleted at spawn timeout and was not
replaced. No registered-snapshot-refresh response occurred. The first Prepare
spent 120.05 seconds in registered-readiness, including 40 context loads taking
40.47 seconds, then later requests were rejected from held custody. Stop
returned 200 in 2.09 seconds; both ledgers are released, GPU2 memory/client use is
zero, existing user Pods are preserved and the short-lived token is revoked.

A real-producer software regression reproduced healthy Node ACK renewal
forcing the late exact-envelope comparison to repeat the full registered
proof. The existing enrollment comparison already authenticates both complete
witnesses while permitting only monotonic timestamp/RV bookkeeping. Its reuse
now passes the real renewal case without proof replay and 39 targeted checks;
broader regression/review and deployment of that correction remain pending.
No readiness/execution timeout is being widened. This is a startup liveness
defect; it does not invalidate the prior scoped CUDA isolation evidence.

Reliable Start/restart, startup latency and the remaining full-platform gates
remain open. See the [application handover and live qualification receipt](https://github.com/mul-cps/cps-compute/blob/803dbc5/releases/node-heartbeat-20261024/software-qualification.json).

### 2026-10-24: authenticated ACK renewal correction fully tested and published

Source `8a5a52967fb6b11fb08b6e8be9060aa34716ff6f` reuses the existing
enrollment heartbeat comparison during registered proof. Only authenticated
monotonic timestamp/RV bookkeeping may advance: both complete custody/pending
witnesses, exact target/envelope, configuration and process/head/epoch stay
checked. Full registered proof, fresh authority/custody and original timeouts
remain intact. A real producer renewal first failed by replaying proof, then
passed once after this correction.

The final single full run passes **5,370 tests and 68 subtests**, with six skips
and 623 warnings, in 681.59 seconds. The focused run passes 299 tests; independent
review passes 22 cases with no remaining Important/Critical finding. Python 3.12
image import and dependency checks pass, the source-revision image label matches,
and the other 82 SDK payloads remain exact.

Published immutable candidate:
`ghcr.io/mul-cps/cps-compute@sha256:c068278477b0be9459c3f7b575c2fd342b37cc73ae42eaf438aaed407f6d6a48`.
The [canonical software qualification receipt](https://github.com/mul-cps/cps-compute/blob/7ccc9ee/releases/ack-renewal-20261024/software-qualification.json)
records the exact wheel/module hashes. Its Node successor and nine input objects
are staged but inert, with bootstrap release false. Journal25 remains active;
journal26 handover and live Start/CUDA/Stop/restart are pending.

### 2026-10-24: ACK renewal image deployed; journal26 handover complete

The published `c0682784` image is deployed. Journal26 authenticates with the
original anchor, exact prior 25 rotations and 128 retained files; all 54 Source
rows remain unchanged. All nine targets are Ready. Both console Services reopened
last, the original lock holder exited normally, the owned GPU2 cordon was
restored, and temporary helpers/network policy were removed. Existing user Pod
identities remain preserved; Node image, driver and kernel are unchanged.

The restoration helper incorrectly expected the live fence during QA readiness
after its verified normal exit. A bounded resume checked captured deployment
identities/specs, restored scheduling state, successful fence exit and QA
readiness before executing the original final reopening and cleanup steps.
No journal retry or rollback occurred.

Normal-console Start/CUDA/Stop/restart and measured startup latency on this
image remain pending. This deployment is not a production-readiness claim.

### 2026-10-24: journal26 normal Start reaches Prepare, then Accepted fence expires

Normal-console Start did not reach Ready or CUDA. Prepare succeeded in 80.54
seconds with zero registered-snapshot refreshes. The original 60-second execution
fence had 34.14 seconds left at Prepare return and 28.48 seconds at Binding
return; Accepted observed binding custody become held after that fence closed.
The test Pod disappeared without replacement. The observed Start ended after
290.63 seconds during normal Stop cleanup; Stop returned 200 in 11.49 seconds.
Both native ledgers are released, GPU2 has zero memory/client use, existing user
Pod identities are preserved, and the short-lived test token is revoked.

A real NodeService bound-heartbeat regression reproduced Accepted replaying
its observation after a healthy ACK renewal. A source correction reuses the
existing complete heartbeat/witness authenticator only when both observations
consume the exact expected bound generation. All fresh authority, read barriers,
final custody/fence checks and timeouts remain unchanged. The focused run passes
73 tests, including metadata/process/witness rejection cases. Full regression
and independent review are running; this correction is not deployed.

### 2026-10-24: Accepted ACK renewal correction fully qualified in software

The corrected same-generation Accepted heartbeat path passes a clean full run:
5,374 tests and 68 subtests, six skips and 623 warnings, in 685.11 seconds.
The prior two-poll RV-only expectation was explicitly corrected and independently
reviewed; the full terminal security file passes 20 cases. The original real
producer regression was observed failing before the fix and passing afterward.
No execution/readiness timeout or fresh-authority/custody requirement changed.

Published image:
`ghcr.io/mul-cps/cps-compute@sha256:1042a980545792ebd4041e51372e445c840602cc9fc55fbbd113435d45d5434c`.
Registry digest, Python 3.12 import, module hash and dependency checks pass. Only
the coordinator SDK payload changed; 82 others remain exact. The successor Node
configuration and nine inputs are staged inert with bootstrap release false.
Five narrow named-read Role plans pass server dry-run without being applied.
The restoration helper now explicitly verifies ownership after normal fence exit;
its 76 tests pass and its default readiness path still requires the live fence.
Journal26 and normal services remain active. Final handover review, journal27
activation and live Start/CUDA/Stop/restart remain pending.

[Software and staged-artifact receipt](https://github.com/mul-cps/cps-compute/blob/b919672/releases/accepted-ack-renewal-20261024/software-qualification.json).

### 2026-10-24: Accepted ACK renewal image deployed through journal27

The reviewed image-only handover is complete on `1042a980…d5434c`. Journal27
authenticates with the original anchor, exact prior 26 rotations and 133 retained
files. All 54 Source rows remain unchanged. Backups verified 227 Node files, four
databases and 134 journal files before activation. Four Node admission cases and
all four current component acknowledgments passed. All nine targets are Ready;
Source Services reopened last, the original fence exited normally, the owned
cordon was restored and temporary helpers/network policy were removed. Existing
user Pod identities are preserved. Node image, driver, kernel and storage mounts
are unchanged. The corrected post-release readiness helper completed normally.

The normal-console live GPU Start/CUDA/Stop/restart test has started. Its result
and startup timing remain pending; this is not production qualification.

### 2026-10-24: journal27 live Start still exhausts the Accepted fence

Normal-console Start did not reach Ready/CUDA. Prepare succeeded in 111.10
seconds; its return left 33.59 seconds on the original execution fence, and
Binding left 28.21 seconds. Accepted again observed binding custody become held
after that fence expired. The Pod disappeared without replacement; observed
Start ended after 309.49 seconds during normal Stop cleanup. Stop returned 200
in 9.27 seconds. Both ledgers are released, GPU2 has zero memory/client use,
existing user Pods are preserved and the short-lived token is revoked.

The Node trace adds evidence: readiness was withdrawn when terminal replacement
verification used an earlier unbound pending observation against a now-bound Pod,
followed by a custody-ledger change. The general Node failure path backs off,
whereas a recognized concurrent custody change reconciles promptly. This is an
investigation lead, not yet a verified fix or proof that it alone explains the
whole delay. Next work must reproduce the transition across complete custody
scans and examine this phase end to end. The software ACK-renewal regression
remains fixed, but journal27 is not live startup-qualified. No timeout is widened.

### 2026-10-24: Node Binding-transition race reproduced and corrected in software

A complete-custody CPU reproducer reaches the same unbound-Pending failure as
the deployed Node when Binding advances between the typed pending scan and a
historical-name check. Deployed pending/abort/custody module hashes match the
tested baseline exactly. The valid transition failed before correction. The
new path first validates typed approval, exact canonical enrolled claim and
intent, registered/unbound observation, actual Pending Pod identity/full bound
specification and gated execution history. It then discards the mixed proof and
raises the existing reobservation signal; the whole scan repeats under its
unchanged three-attempt bound. No authority is granted and general failure
backoff/timeouts are unchanged.

All 149 focused tests pass, including ten race cases, real Node service renewal
and reconciliation through the race, authenticated bound ACK publication, and
retry exhaustion withdrawing a previously valid ACK without GPU/journal work.
Independent reviews found no Important/Critical issue. A clean full suite is
running. The source correction is committed as `595108cb…2986b`.

The local candidate uses the pinned Node Dockerfile and a built wheel with the
`node` extra. Python 3.12, installed-package verification, source payload hashes,
all 30 unchanged dependency versions and inert no-network/read-only/no-capability
startup checks pass. Compared with the deployed Node package, 80 Python payloads
are exact; only this Node correction and the already-qualified coordinator
correction differ. No new image is published/deployed yet. A Node-only
same-policy successor and guarded handover are required; changing Gateway alone
cannot deliver this Node fix. Live startup/fence margin and the complete original
production gates remain unqualified.

[Node candidate receipt](https://github.com/mul-cps/cps-compute/blob/96867b3/releases/node-binding-transition-20261024/software-qualification.json).

### 2026-10-24: Node correction fully tested, published and staged inactive

The final clean run passed 5,384 tests and 68 subtests, with six skips and 623
warnings, in 686.23 seconds. The pinned Node Dockerfile built the released wheel;
all 82 installed SDK Python files match source, with 80 unchanged from Nodefed.
All 30 dependency versions and 2,047 non-bytecode files in 29 dependency
distributions are exact. Inert no-network/read-only/no-capability startup passes.
Linux command/environment/user settings match; the sole non-label config delta
is omission of deprecated Windows-only `ArgsEscaped`, documented in the
[OCI image specification](https://github.com/opencontainers/image-spec/blob/main/config.md#properties).

Published Node image:
`ghcr.io/mul-cps/cps-native-node@sha256:72a932f4179853875c701b91e023b02af761b5f40bacecdd7a7446444d9e2816`.
The registry manifest and image-config digest match the verified artifact. Its
successor changes only the Node image declaration; policy and Gateway image are
unchanged. Nine staged inputs retain bootstrap release false; five narrow Role
plans pass server dry-run. The Node-only handover gate now checks exact reviewed
UID/image/template and fresh spec rather than requiring unchanged image identity;
84 operator tests pass and review found no remaining Important/Critical delta.
Final actual-manifest review and live handover remain pending. No maintenance
has started. [Canonical software/artifact receipt](https://github.com/mul-cps/cps-compute/blob/b442103/releases/node-binding-transition-20261024/software-qualification.json).

### 2026-10-24: Node-only journal28 handover completed

Final actual-manifest review approved the bounded handover. All four admission
cases passed; the completion gate checked the exact reviewed Node target and
correctly recorded `same_node_image=false`. The live pending-module hash is
`885f6758dfb44fcd70d57f9668db71141ee73f7fe91584bbb9e7db204d6e4c68`, matching qualified
source. Gateway image, driver, kernel and storage settings are unchanged.

Before activation, backups verified 234 Node-state files, four databases and 139
journal files. Journal28 authenticates with the original anchor, all 27 exact
prior rotations and 138 retained files. All 54 Source rows remain unchanged.
Normal writer and services are restored; all nine targets are Ready. Source
Services reopened last, the original fence exited normally, owned cordon state
was restored and temporary helpers/network policy were removed. Existing user
Pod identities are preserved. The normal-console live GPU test is running;
no current Start/restart or latency success is claimed yet.

[Completed handover receipt](https://github.com/mul-cps/cps-compute/blob/3187aaf/releases/node-binding-transition-20261024/software-qualification.json).

### 2026-10-24: journal28 live test fails before Binding; cleanup verified

The corrected Node package is active, but this run never reached its Binding
transition. Prepare exhausted its 120-second request deadline during enrollment
publication after 120.70 seconds. Registered-readiness took 59.24 seconds, forty
context loads took 39.37 seconds, and enrollment publication took 51.66 seconds;
these nested timings overlap. The execution fence opened at Prepare+103.50s,
leaving only 17.2 seconds on the enclosing request budget. No timeout is widened.

Timestamped logs distinguish consequences from cause: Prepare failed at
10:45:38.808Z; the first Node absent-enrolled-Pod error followed removal at
10:45:42.274Z. Those errors do not establish a regression in the Node Binding
fix. The observed Start ended after 304.63 seconds; the Pod disappeared without
replacement or CUDA. Normal Stop returned 200 in 1.58 seconds. Both ledgers are
released, GPU2 has zero memory/client use, all nine exact expected targets are
Ready, existing user Pods are preserved and the short-lived test token is revoked.

Next work traces same-generation Node heartbeat renewal across the complete
registered-readiness path. The existing terminal-only comparison may still replay
initial read-only proofs; this remains a hypothesis pending a real-producer
reproducer. Reliable current Start/restart, startup performance and all original
production gates remain open.

### 2026-10-24: initial registered heartbeat boundary reproduced and covered

A real NodeService renewal during the initial no-Session registered observation
reproduced a complete-observation replay (red 1.91s). The same full heartbeat
authenticator now applies whenever both authenticated selected rows equal the
expected generation, regardless of phase; the regression passes in 1.82s. Strict
workload references, full registered proof, fresh Source authority, final custody
and all deadlines remain unchanged.

The final 12-case phase matrix passes and independent review approves it. It
authenticates validly rebound complete witnesses while preserving selected rows;
rejects other pending/custody-row changes, process/head/epoch, target/envelope and
custody drift before coordinator writes; and proves real Source revocation is
encountered by the fresh claim. Genuine prior-to-expected advancement still
requires multiple complete observations. The broader focused run passes 105
tests; the frozen full suite is running. No live speedup is claimed yet.

The local Gateway candidate installs a released wheel over immutable Gateway1042.
Eighty-one SDK payloads remain exact; only the coordinator and the already-
deployed Node correction differ. Python 3.12, installed coordinator hash and
dependency checks pass. All 43 dependency distributions and 4,590 non-bytecode
files are exact, and runtime configuration is unchanged apart from provenance
labels. The Node image remains72. Eighty-four operator tests and offline
Gateway-only journal28-to29 preparation review pass; final candidate publication,
actual-manifest review and guarded handover await the full suite. No maintenance
has started.

[Source and package candidate receipt](https://github.com/mul-cps/cps-compute/blob/79c9565/releases/registered-renewal-20261024/software-qualification.json).


### 2026-10-24: Gateway renewal fix deployed; first normal-console CUDA passes

The full suite passed 5,396 tests (6 skipped, 68 subtests). Gateway image
`sha256:08c81d394ca0273588ce63331e253ecdc2c22a1b9be5fc62a495830d0722f42a`
is deployed after reviewed actual manifests and verified backups. Journal29 is
authenticated; the original anchor, prior 28 generations and 143 retained files
are exact. All 54 Source rows remain unchanged. All nine deployments are Ready,
Source Services were reopened last, the fence exited normally, the owned cordon
was restored and temporary helpers were removed. Existing user Pods are preserved.
Node, Hub and notebook images, drivers, kernels and storage settings are unchanged.

The first normal-console shared 5 GiB workspace Start returned 200 after 258.67s.
The first observed Pod appeared at 96.12s, assignment at 227.41s and Ready at
244.08s. Its UID stayed stable, with no disappearance or observation errors.
A trusted 64 MiB allocation/fill/synchronize/sum passed on one visible A100.
Normal Stop returned 200 in 26.59s; both ledgers are released, both GPU2 devices
have zero memory use and no compute clients, and existing users are unchanged.
Restart qualification is running. This single start does not qualify reliability,
the p95 startup target, broader pooling or the full platform for production.

[Authenticated deployment receipt](https://github.com/mul-cps/cps-compute/blob/55b3eda/releases/registered-renewal-20261024/software-qualification.json).


### 2026-10-24: restart CUDA passes; final cleanup verified

A normal restart returned 200 after 249.05s: first Pod at 96.38s, assignment at
221.88s and Ready at 238.59s. The new Pod UID stayed stable and the 64 MiB CUDA
operation passed. Stop returned 200 in 20.15s. Both ledgers are released, GPU2 has
zero memory use and no compute clients, all nine exact targets are Ready and
existing user Pods are unchanged. The scoped temporary token was revoked and
both local credential copies removed. No maintenance remains active.

This completes one deployed Start/Stop/restart cycle, not production reliability
or burst qualification. The startup target remains open: both successful starts
are slower than 180 seconds. No deadlines or safety checks were relaxed.

[Start/restart and cleanup receipt](https://github.com/mul-cps/cps-compute/blob/676ec82/releases/registered-renewal-20261024/software-qualification.json).

### 2026-10-24: cold proof reconstruction cost measured; two experiments rejected

Both successful Prepare traces spend 99–102 seconds overall, with 33–34 complete
context loads totaling about 34 seconds. These are nested timings: registered
readiness takes 29–31 seconds and enrollment publication 53–55 seconds, so the
figures must not be added. An isolated, read-only profile of the installed
Gateway found 132 actual ConfigMap GETs across 95 targets per context load,
31 retained Node configurations and 53 distinct historical registry revisions.

Two separately tested prototypes were compared against the installed code in
three paired read-only runs each. Prefetching retained Node references with four
workers and memoizing pure validation for same-registry aliases showed no
consistent live improvement. The aliases optimization passed its controlled
fixture but current production history has 53 distinct registry revisions.
Neither prototype is retained, published or deployed. The current successful
Start/restart deployment and its safety checks are unchanged.

The next optimization should reuse deterministic validation of identical
immutable inputs while freshly checking their actual readbacks and retaining
both mutable-head reads. Current Source/grant checks, Node acknowledgments,
custody, reservations and deadlines must remain fresh and unchanged. Changed,
missing or malformed objects must force full validation or denial; no cached
context may grant access after a head/identity/epoch change. A performance claim
still requires the same normal-console Start/CUDA/Stop/restart measurement.

[Sanitized profiles and rejected-experiment measurements](../../platform-staging/qualification/startup-journal29-20261024/critical-path.json).

### 2026-10-24: fresh-readback context reuse implemented and measured

Source `f059750faed36473e5293cc1fc89bebb78c29058` adds an isolated readback helper
and integrates it into the coordinator. It reuses deterministic validation only
after freshly reading every previous immutable input, including duplicate GETs,
and comparing exact canonical bytes inside two fresh mutable-head reads. Actual
changed bytes enter the existing cold validator through single-use replay. Head
advancement takes the cold path; an in-bracket flip denies. Current Source grants,
Node acknowledgments, custody, reservations and execution deadlines stay outside
the optimization. Reads use four workers and drain on failure/cancellation.

Three paired read-only tests in separate processes against the actual live graph
measured baseline context loads at 0.85–0.91s and warm candidate loads at
0.18–0.21s. Both versions performed 132 fresh GETs across the same 95 targets.
This is a context-load measurement, not an end-to-end startup result.

Independent review found no Important/Critical issue. The broader Source,
pending-generation and final-enrollment set passed 154 tests in 66.76s. The final
18-case boundary suite passed in 1.94s, including malformed/changed observations,
last-duplicate invalidation, 512/513 observation limit, concurrent head advance,
and failure/cancellation drainage. The full suite is running.

The local candidate image passes Python 3.12 imports, installed-payload hash
checks and `pip check`. Eighty-two SDK payloads, 43 dependency distributions and
4,590 non-bytecode dependency files remain exact. Runtime configuration is exact
apart from provenance labels. The image is not published or deployed; no new
maintenance has started. The full project remains limited-pilot, with startup,
CPS/CIT bursts and the original production gates still open.

[Candidate qualification receipt](https://github.com/mul-cps/cps-compute/blob/6b1be66/releases/fresh-context-readback-20261024/software-qualification.json).


### 2026-10-24: readback image deployed; Start and restart CUDA pass

The published image was activated through the reviewed journal29-to30 handover.
Backups verified252 Node files, four Source databases and149 journal files.
Post-rotation validation authenticated generation30, exact prior29 history and
original anchor, plus148 retained original files. All54 Source rows stayed exact.
All nine deployments are Ready; Source Services reopened last, the fence exited
normally, owned worker scheduling was restored and temporary helpers were removed.

The first normal-console Start returned200 in208.80s: first Pod93.85s, assignment
175.33s, Ready194.15s. Restart returned200 in219.65s: Pod92.12s, assignment188.30s,
Ready207.11s. Both new Pods retained their UID without disappearance, replacement
or observation errors and passed allocation/fill/synchronize/sum on64MiB of one
visible A100. Stops returned200 in24.72s and13.20s. Final checks confirm both
ledgers released, two GPU2 devices at zero allocated memory/no compute clients,
all nine exact targets Ready, four current component acknowledgments, unchanged
Source54 and existing user Pods, and revoked/removed temporary credentials.

The first successful Prepare took70.00s versus101.82s before the change. Its31
context loads totaled9.99s versus33.61s previously. The remaining pre-Pod path is
still substantial: Hub OAuth client creation/accepted spawn occurs at22s, the
modify-Pod hook at54–55s and after-Pod-created hook at90–92s. The next trace must
separate the client authentication bootstrap and Source Start request, then the
Hub pre-spawn and modify hooks; no target, timeout or authority check is relaxed.
This single cycle is not burst, full-pool or production qualification.

[Deployed Start/restart and cleanup evidence](https://github.com/mul-cps/cps-compute/blob/b87e7ff/releases/fresh-context-readback-20261024/software-qualification.json).
