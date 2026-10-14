# CPS/CIT production completion

**The platform remains `limited-pilot`; the full project and production
qualification are unfinished.** This ledger follows the original platform plan
through source implementation, immutable publication, live deployment and
measured acceptance. Evidence for one stage does not establish the next stage.
See the [operational acceptance record](qualification/operational-acceptance-20261013.md)
for the bounded live results of 2026-10-13 and their retained evidence.

## Binding requirements

- Separate CPS/CIT consoles and databases; shared policy and person allowance.
- Preserve usernames, homes, research data, local grants and dirty checkouts.
- Dynamic GPU sharing without MIG. Run GPU acceptance only with trusted probes.
- Authoritative identity mapping; no linkage inferred from matching usernames.
- Retain Authentik/Dex. University OAuth registration stays externally deferred.
  Email verification is available but is not mandatory.
- Local courses active; Moodle visibly planned, disabled and inert.
- NFS addresses remain unchanged; S3 uses the accepted NetBird relay path.
- Protect existing workloads; confirmed shutdown precedes reservation release.
- Promote immutable qualified artifacts and retain matching backups/rollback.

## Acceptance ledger

| Gate | Verified state | Remaining completion evidence |
| --- | --- | --- |
| Repository ownership and shared policy | Separate application/deployment responsibilities and shared policy implemented; compatibility branches retained | Integrate and promote one tested consumer matrix with its exact policy hash; account for Fleet's watched branches |
| SDK, Hub and Lab packages | All 12 notebook OCI variants with the packaged PageConfig hook and refreshed Lab addon are published; integrated Hub/Gateway images passed installed-package tests and actual remote overlay checks. Both live Hubs run the earlier registered CPU adapter | Complete normal new-account lifecycle; adopt the qualified Hub and notebook packages through the controlled handover, then verify actual visitor authentication and live API refresh |
| Both admin UI consoles | Both consoles run Source87a1 with visible-view API refresh; 66 synthetic-API browser tests passed and actual installed bytes match. Authenticated CIT `akadmin` API/browser checks now confirm real polling, zero page errors and the 10 GiB choice for its approved pilot workspace; supplied token revoked through normal HTTP | New-account HTTP lifecycle, reviewed CIT person linkage and ordinary-user API acceptance; API-token browser checks do not establish fresh human OAuth |
| Identity and group ownership | Existing reviewed aliases retained; both CPS legacy neutral accounts have permanent ready provenance; explicit custody migration and exact QA repair passed; both Hubs restarted without changing the repaired or legitimate legacy roles | Complete CIT adoption, real login grant survival/expiry and scoped administration; cross-Hub allowance continuity |
| Native GPU isolation | Controlled no-MIG 5/20 GiB history retained; current CPS pair passed distinct 5 GiB OOM/recovery with peer progress, IPC denial in both directions, positive controls, kernel witnesses, restart retirement, complete bounded MPS OOM/recovery and observer cleanup, and confirmed normal closure | Complete restart behavior and broader packing; current bounded pool is 5/10 GiB, not a normal 20 GiB or cross-Hub qualification |
| Shared GPU reservations | Shared accounting implementation and reviewed qualification bindings exist | Actual simultaneous cross-Hub starts, all-member atomicity and partial-conflict rollback; prove permitted CPU sessions and independent batch execution; release only after confirmed stop |
| Workspaces and local assignments | Local management, source-neutral reconciliation and RTC implementations exist | Two real visitors retaining their own identity, membership removal closing existing access, retained files and stopped-writer read-only archives |
| Workflow gateway and admission | Source validation/ownership paths implemented; bounded CPS own-success/failure artifact/log bytes and foreign-versus-absent rejection passed; controller admission/RBAC checks passed | CIT normal-user own/foreign access, human authentication, token renewal and crafted workflow/admin bypass scenarios on the current release |
| Notebook execution | Immutable runner/package/browser tests and bounded CPS selected-import/typed-parameter success/failure outputs passed | Complete current release/live coverage for saved snapshots, selected files, parameter cells, approved image digests and both owning Hubs |
| GPU scheduling and packing | Stock KAI/HAMi components and controlled evidence exist; integrated Core/Hub source passed 2,151 tests with three known skips, plus separate installed Gateway/Hub suites. The Node image handover passed actual hardware zero and four-process epoch checks; coordinator activation remains disabled | Coordinator/binder deployment and actual post-Bind cap/CDI qualification; eight-A100 packing, teaching reclaim, protected sessions, 4/8-GPU JobSet retry and physical free-GPU telemetry |
| Startup and defragmentation | Acceptance executors and thresholds are defined; representative measurements pending | Pre-pulled CPS/CIT bursts: p95 <=180s and maximum <=300s; KAI/fallback comparison with free capacity >=95% and waits/start <=110% of baseline, protected sessions unaffected |
| NFS and S3 artifacts | Existing storage preserved; accepted TLS relay path and owner-filtered artifact access work; ten owned-prefix 14/90-day retention cases passed against real S3 and Argo with least-privilege authentication | Real gateway-created notebook lifecycle, scheduled cleanup and off-host recovery; new CIT filer requires its actual endpoint/export |
| Monitoring | All four deployed dashboards rendered through actual Grafana with seven panels each and no browser page errors; unavailable physical/cap data was visibly marked | Promote and verify the newer dashboard definitions; complete eight-GPU inventory, physical placement/free-capacity and cap/protection telemetry, timing data and alert notification delivery |
| Restore and recovery | All five overnight automatic backup jobs succeeded; three corrected console/gateway runs verified current application/policy provenance, checksums, SQLite integrity and cleanup; matching logical restore history retained | Next automatic schedule after provenance correction, coordinated matching application/configuration capture, connected login/spawn, populated NFS/archive/artifact recovery and encrypted off-host durability |
| Moodle scaffold | Local provider, provenance migration, disabled scaffold and source tests implemented | Retain local CRUD, fake-provider reconciliation, no-network disabled behavior and clear enablement failure in the qualified release; Moodle remains planned/not deployed |
| Release train and compatibility | Candidate artifacts and compatibility tooling prepared; no unified production release declared | Complete pilot -> RC -> production gates, matched SDK/Hub/Lab/runner/notebook matrix, immutable digests, checksums/SBOMs, release notes, rollback and qualified Fleet promotion |
| Hub 6 | Separate staging scope | Keep outside production promotion until stable chart compatibility and migration/storage qualification pass |

## Current rollout boundary

Both Hubs are Ready on the corrected package image
`ghcr.io/mul-cps/cps-compute@sha256:a7155bebb5dff1b70ff79edbf57a1012bb37feed082bac8212c885b46e1cb950`.
All 13 installed Hub code modules match wheel `abcd84c0`; the actual image passed
158 focused tests, including 24 actual-installer/KubeSpawner cases. The full
source suite passed 1,838 tests with three existing
fixture skips. Four fresh component acknowledgments and a separate completed
immutable delivery journal confirm the current unchanged policy/driver epoch.
The successful recovery preserved the explicit custody migrations, repaired QA
roles and legitimate legacy accounts; it did not recreate revoked ownership.
See `platform-staging/gpu/qualification/hub-registered-cpu-20261014/`
and `platform-staging/gpu/qualification/neutral-custody-migration-20261014/`.

Both admin consoles are Ready on
`ghcr.io/mul-cps/e2x-course-hub@sha256:87a1c0b99331259199ff56d52b83c5bc5fcff1c05d0965a9f097138208ea1e61`,
Source revision `1443b05a5d2f3aa33b2f2c2a70c136a9e5023e04`.
Only the console image changed. Both online SQLite database byte hashes, schema 7,
all five mounted configuration objects and the original identity receipt were
preserved. Actual post-startup QA identity, service and runtime/control role
readbacks matched the successful repair. The normal CPU HTTP lifecycle and human
OAuth are separate acceptance gates.

A fresh pair of ordinary Source-managed GPU workspaces reached Ready together
with exact 5 GiB caps. The complete bounded MPS run passed: the over-cap
allocation failed with CUDA result 2, both clients recovered and the peer
continued verified kernels. All 479 native samples stayed within the respective
caps. Private processes and endpoints exited, staged sources were removed and
the observer confirmed exact baseline restoration with zero charged bytes.
Both subsequent normal Close operations confirmed shutdown, released
reservations and restored the original membership/grant windows and Hub groups.
See `platform-staging/gpu/qualification/current-source-pair-mps-20261014/`.
The exact successful hardware receipt is
`877d6d496e327a264f5b936a34f8a7fc20830d88ccd75b634a0b457bce3448d4`.
Earlier transport/observer failures remain retained as inconclusive attempts.

The released CPU adapter addresses the missing legacy profile slug and passes
the immutable operator image through the real native wrapper. A new normal
registered CPU HTTP run returned 503 because the new owner inherited an actual
chart `V1Container` init object that was not normalized by the fixed neutral
template. Normal Stop restored `state=stopped`, with empty servers and Shares.
The tested neutral-template fix now runs in both Hubs. Its subsequent normal
HTTP retry stopped earlier at a gateway storage-provisioning 409 and did not
reach Hub Start. Normal Stop again confirmed the workspace stopped with no
servers or Shares; exact owned grant/membership windows and groups were restored
through the API. One subsequent normal Start returned 409 at central workspace
registration before a new storage operation or Pod. The existing provisioning
fence rejects even identical registration, preventing the trusted provisioning
resume path from being reached. Its minimal recovery fix is under test; the
fence has not been forcibly reset. Normal Stop, Pod absence, original windows,
memberships and grants were verified, and the retry's scoped tokens were revoked.
The CPU lifecycle gate remains open and is separate from the passed GPU pair.
See `platform-staging/jupyter-extensions-20261013/registered-cpu-v8-attempt-20261014.json`.
The admin and Lab APIs authenticate the actual browser visitor;
visible admin records now refresh after each 20-second interval, with stale data
marked and drafts preserved. The Lab package passed 30 Node tests, four
wheel/sdist tests, actual Lumino polling/lifecycle regressions and all seven
views in installed JupyterLab 4.6.4. Those browser APIs were synthetic. The active
trusted CPU notebook image has neither compute package nor the Lab addon;
The packaged CPS/CIT PageConfig hook now passes actual installed Jupyter Server
HTML tests across all 12 image variants; Hub/Gateway packages and the notebook
images are published. Live notebook adoption and actual normal-user OAuth/API
acceptance remain open.
See `platform-staging/jupyter-extensions-20261013/admin-ui-live-refresh-receipt-20261014.json`
and `platform-staging/jupyter-extensions-20261013/lab-live-refresh-qualification-20261014.json`.

## Earlier rollout and retained diagnostics

The following captures describe the preceding deployments and failed attempts.
They do not supersede the current healthy Hub/Source boundary above.

The preceding healthy Hub baseline was the reviewed package image
`ghcr.io/mul-cps/cps-compute@sha256:466b8398285a513499440dd00aaf0abc377cc49afe05f19e5556e79908106486`.
The permanent neutral-account registry and scoped Source service API are active.
Both actual PostgreSQL schemas passed validation, and automatic registry
migration is **disabled** after the controlled explicit migration. Fresh startups
acknowledged the unchanged Source revision, policy and GPU epoch in all four
components at **2026-10-13T23:53:43.388084Z**. A separate input Secret and durable
journal preserve the earlier delivery history. The initial configuration attempt
and its verified inverse remain retained; the corrected retry has its own fresh
matching database/configuration/role backups and independent process evidence.
See `platform-staging/jupyter-extensions-20261013/hub-registry-activation-receipt-20261014.json`.

Both consoles are Ready on
`ghcr.io/mul-cps/e2x-course-hub@sha256:9698e84452c98385155571e570208e362f19ba4127e8cfe1e4320232a4365849`,
Source commit `55c9a8865c462e4baeb306965fb1a6ed5da07dbd`. This adds the narrow
permanent account adapter and concurrent course Start fix. Image-only rollout
preserved every preexisting SQLite table fingerprint, schema 7, integrity and
complete console configuration. The candidate passed **303 source and 303
installed-image tests**. Its UI assets are unchanged from the previous image's
11 successful CPS browser checks. Those operator-token checks are not human
OAuth acceptance. New generic account creation is implemented and configured;
its normal HTTP create/restart/access-removal lifecycle remains a separate live
gate. Existing CPS legacy adoptions remain durable; CIT adoption still requires
an actual administrator login refresh. No identity is inferred from names or
email equality.

The bounded normal HTTP CPU run created its owned course, term, group,
membership and workspace, then created the new permanent Hub identity. Start
failed before any notebook Pod: the owning console's actual service-token user
response omits `created`, which Source requires to verify the saved identity
receipt. The saved receipt and administrator-visible timestamp match exactly;
the installed Source validator reproduced the denial read-only. The service
also lacks server lifecycle permission for this new owner. Actual SQL revealed
that the neutral account receives the ordinary `user` role as well as its
restricted group; its inherited `self` privilege needed removal. Explicit custody
migrations now passed in both Hub PostgreSQL databases. The exact stopped CPS QA
account was repaired with only its registered runtime/control roles and owned
empty course group; its original identity receipt and every unrelated account,
role, group and service remained unchanged. All three temporary CPU operator
Jobs and Pods are confirmed absent. The normal HTTP lifecycle still awaits
compatible Hub/Source rollout.

Two ordinary approved CPS workspaces completed distinct 5 GiB cap tests, OOM
recovery with peer progress and normal confirmed shutdown. A subsequent current
pair denied cross-parent IPC in **both directions** with CUDA result 800,
distinct importer/exporter process IDs, same-parent positive controls, surviving
kernels, explicit cleanup and correlated driver witnesses. A fresh restart
readback checked exact new caps and prior parent retirement. Both normal Close
operations then released reservations and restored windows/groups. These are
bounded results, recorded separately from the earlier incomplete attempts in
`platform-staging/gpu/qualification/concurrent-source5/ipc-restart-receipt-20261014.json`.
MPS, full restart semantics, KAI placement and wider packing remain unqualified.

The next two normal Source pair starts did not reach simultaneous readiness;
no MPS workload executed. The first aborted pair eventually closed both
workspaces and restored all windows/groups. The second timed out in the Hub's
native binding acquisition HTTP calls before either Pod existed. Its two
reservations were subsequently released through confirmed normal Source Close.
Exact saved memberships, grants and Hub groups were restored afterward. Root
independently reread both released ledger rows; the protected hardware readback
reported zero active caps and zero charged bytes. No force clear was used.

Read-only tracing found repeated component readiness observations during
immutable configuration reads. A tested released-package candidate removes
that repetition while retaining fresh authorization, readiness-loss and
revocation checks. All 1,863 core tests passed; 43 installed modules matched
the built wheel, and the remote image digest matched the reviewed local image.
The candidate now runs in the live gateway at
`ghcr.io/mul-cps/cps-compute@sha256:440711b2bb00151f8625e9df54c97e7ed4d137ca246453aae9ad7524d6681c3d`.
The image-only handover verified a fresh Ready process, four current component
acknowledgments, unchanged service-role permissions, zero active native caps and
released reservations. Earlier candidate preparation and recovery boundaries
are recorded in
`platform-staging/gpu/qualification/concurrent-source5/gateway-readiness-receipt-20261014.json`.
The actual successful handover has its separate immutable receipt in
`platform-staging/gpu/qualification/gateway-readiness-handover-20261014/`.
The frozen MPS runner and mapper passed their CPU controls; that is preparation,
not hardware evidence.

The next normal Source pair still failed before simultaneous readiness: a Hub
workspace lookup received a disconnected HTTP response. Both workspaces closed,
both reservations released and original grant/membership windows and Hub groups
were restored. The gateway process stayed Ready without a restart. The replacement
Hub extension retries this specific read-only transport failure once; mutation
requests, permission failures and unknown outcomes retain their existing guards.
Its 126 installed tests include a real TCP server closing the first connection,
and all 12 Hub code modules exactly match the wheel while the core package is
unchanged. The published candidate is
`ghcr.io/mul-cps/cps-compute@sha256:f5bff2df99281b659f550f8cddbdfafbdbc6593d827c1f417779263658998396`.
The paired rollout applied this candidate, then stopped before fresh delivery
activation because both Hubs failed startup with
`Kernel role configuration cannot restore revoked ownership`. The configured
legacy owners still hold their direct kernel-role assignments in both databases;
the new startup guard omits them from its registered-account subset. Delivery
remains paused and no workspace Start is attempted before convergence. Recovery
must preserve current legitimate assignments while continuing to reject restored
revoked ownership. The successful migrations and exact QA repair remain intact.
See the application verification record at
[`cps-compute` revision 6d87231](https://github.com/mul-cps/cps-compute/blob/6d87231/docs/hub-disconnected-read-verification.json).

The controlled retention run passed all ten cases against the actual S3
endpoint: 14/90-day boundaries, active/retained preservation, stale-ETag HTTP
412, acknowledgement ambiguity and fresh-process recovery. Its CPU Pod used
only ten exact named-workflow permissions; an unrelated workflow read was
denied. All fifteen owned Kubernetes resources are now absent, and the
production CronJob's exact UID/spec remain unchanged and suspended. Terminal
workflow states were explicitly synthetic. Real notebook lifecycle and
automatic cleanup remain unqualified. See
`platform-staging/artifacts/qualification/retention-controlled-20261014/`.

The matched core and Lab extensions built and passed runtime checks in **all
12 local notebook OCI variants**. Installed discovery/uninstall/reinstall,
Hera/RTC, UID 1000 and pinned inherited image/package provenance were checked.
All twelve images are now published as qualification artifacts; none is promoted
to production. The publication receipt is in the notebook repository at
[`cps-jupyter-notebook` revision 1424a20](https://github.com/mul-cps/cps-jupyter-notebook/blob/1424a20/release/qualification/publication-20261014/receipt.json).
The newer browser-hook matrix is recorded at
[`cps-jupyter-notebook` revision 563d74e](https://github.com/mul-cps/cps-jupyter-notebook/blob/563d74e/release/qualification/notebook-browser-consumer-20261014/publication-receipt.json).
The integrated Gateway and Hub publication is recorded at
[`cps-compute` revision 04404d3](https://github.com/mul-cps/cps-compute/blob/04404d3/docker/qualification/integrated-consumer-20261014/publication-receipt.json).
Those immutable artifacts have installed-package and remote byte evidence; they
are not deployed runtime acceptance evidence.
The Node package handover subsequently completed at 10:37 UTC on 14 October.
Its immutable `8c2c456` image is running, both Hub images and the Gateway main
image remain unchanged, and the capture companion now targets that Node image.
The controlled read-only hardware probe required the driver's root plus
`CAP_SYS_ADMIN` read permission and confirmed zero native allocations after
the stop barrier. All four current processes acknowledged the new epoch,
and delivery resumed with a new completed journal while retaining the previous
journal. The receipt is
`platform-staging/jupyter-extensions-20261013/native-node-handover-actual-20261014.json`.
This closes the Node handover gate; coordinator activation and actual post-Bind
cap/CDI execution remain open.
Actual authenticated CIT browser/API evidence is retained in
`platform-staging/jupyter-extensions-20261013/cit-authenticated-ui-api-readback-20261014.json`.
The owning `akadmin` token successfully read the admin API. A fresh headless
browser rendered the real deployed console, observed another status poll, and
showed `interactive-shared-10` after selecting its approved shared workspace.
No browser API mutation or page error occurred. Unscoped grant choices remain
CPU-only. The separate operator report was stale, while the live approval API
was ready; these states must not be conflated. The account alias and shared
Gateway/Hub canonical mappings still need the reviewed coordinated update.
The separate KAI coordinator, signed-lease Hub glue and terminal-cleanup
contracts passed **2,036 source tests** (3 existing fixture skips), **314
installed-wheel tests**, and the pinned official KAI replay/build. The inert
qualification OCI was published with exact remote digest verification.
Activation stays disabled. Source contracts do not
establish actual placement, Node UID API preconditions or post-Bind cap/CDI
qualification; combined release integration and the live controlled pilot remain open.

The approved CPS pilot remains bounded to its two existing workspaces and
5/10 GiB policy. Source mutation initially reports `ready=false`; actual current
process convergence is required before Start. None of these results enables
broader entitlements or establishes production qualification.

The CIT administrator's upstream Dex session requires a real login refresh.
Operator-created Hub API tokens do not refresh that upstream session and do not
establish human browser acceptance. CPS work and independent operational tests
continue while that login is pending.

University OAuth client registration and the new CIT filer endpoint/export are
external deferred inputs. They do not block independent acceptance work. The
reported client allowlist addresses are not a substitute for the filer endpoint.
The existing NAS and NFS paths stay in place; account for the stated Tuesday
05:00–08:00 fileserver maintenance window before storage-dependent tests.

No production release, full-project completion or broad GPU entitlement is
asserted by this ledger. Every remaining gate retains its required live evidence.
