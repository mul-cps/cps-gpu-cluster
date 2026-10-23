# Current platform state — 23 October 2026

The full platform remains **limited-pilot**, not production qualified. The
ordinary `cps:shared-gpu-lab` 5 GiB lifecycle now passes on the durable authority,
including automatic KAI reservation cleanup. This supersedes earlier pending
statements for that specific lifecycle, not every production acceptance gate.

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
