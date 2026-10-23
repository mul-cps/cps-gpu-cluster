# Current platform state — 23 October 2026

The full platform remains **limited-pilot**, not production qualified. The
ordinary `cps:shared-gpu-lab` 5 GiB lifecycle now passes on the durable authority,
including automatic KAI reservation cleanup. This supersedes earlier pending
statements for that specific lifecycle, not every production acceptance gate.

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
