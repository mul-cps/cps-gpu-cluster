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
| SDK, Hub and Lab packages | Both Hubs now run Hub1e with the personal SDK environment fix and select CPUd75 with the prebuilt Lab XSRF fix. The actual Hub 5.5.2/Chromium regression and panel tests passed, with 43 Node and 9 installed Lab tests. A fresh personal CPS CPU kernel returned HTTP 200 for `/v1/me`, `/v1/profiles` and `/v1/session` using zero-argument `sdk.client()` and the reviewed person identity. The existing bjoern/cpsadmin notebook Pods remain unchanged on CPUad | Personal server restart, human panel and CIT personal SDK acceptance remain pending. Other notebook variants, ordinary visitor identity separation and human RTC remain separate gates; CIT personal profile hooks retain their independent images |
| Both admin UI consoles | Both consoles run Sourceb36 with the reviewed legacy runtime validator; frontend and dependencies remain equal to Source87a1. CIT legacy runtime enrollment, cold startup and real notebook activity reporting passed; the existing UI and approved 10 GiB choice remain bounded evidence | Normal registered CPU lifecycle and reviewed CIT `akadmin` canonical API linkage passed; ordinary-user/human OAuth and remaining modes are separate gates |
| Identity and group ownership | Existing reviewed aliases retained; both CPS legacy neutral accounts have permanent ready provenance; explicit custody migration and exact QA repair passed; both Hubs restarted without changing the repaired or legitimate legacy roles | Reviewed CIT alias is live in Source, Hub and Gateway and `/me` resolves the same person; real login grant survival/expiry, scoped administration and cross-Hub allowance continuity remain |
| Native GPU isolation | Controlled no-MIG 5/20 GiB history retained; current CPS pair passed distinct 5 GiB OOM/recovery with peer progress, IPC denial in both directions, positive controls, kernel witnesses, restart retirement, complete bounded MPS OOM/recovery and observer cleanup, and confirmed normal closure | Complete restart behavior and broader packing; current bounded pool is 5/10 GiB, not a normal 20 GiB or cross-Hub qualification |
| Shared GPU reservations | Actual simultaneous CPS5/CIT10 pilot starts passed: one winner held both shared members once, loser had no server/Pod/binding; confirmed Stop preceded successful retry on the other Hub; exact windows/groups/grants restored. Installed current Gateway code also passed first-free/second-busy transaction rollback in an isolated SQLite database | Different-member live API partial-conflict rollback, permitted CPU sessions and independent batch execution while held; broader pool and ordinary-user qualification |
| Workspaces and local assignments | Local management, source-neutral reconciliation and RTC implementations exist | Two real visitors retaining their own identity, membership removal closing existing access, retained files and stopped-writer read-only archives |
| Workflow gateway and admission | Source validation/ownership paths implemented; bounded CPS own-success/failure artifact/log bytes and foreign-versus-absent rejection passed; controller admission/RBAC checks passed | CIT normal-user own/foreign access, human authentication, token renewal and crafted workflow/admin bypass scenarios on the current release |
| Notebook execution | A real personal CPS kernel used the installed SDK to submit successful and intentionally failing CPU notebook jobs. Saved snapshots, exact selected helper, typed parameters, executed notebooks on both outcomes, artifact downloads and HTTP 200 log responses passed | Human Submit UI, CIT personal/shared-kernel runs and broader current-release coverage remain open |
| GPU scheduling and packing | Stock KAI/HAMi components and controlled evidence exist; integrated Core/Hub source passed 2,151 tests with three known skips, plus separate installed Gateway/Hub suites. The Node image handover passed actual hardware zero and four-process epoch checks; coordinator activation remains disabled | Coordinator/binder deployment and actual post-Bind cap/CDI qualification; eight-A100 packing, teaching reclaim, protected sessions, 4/8-GPU JobSet retry and physical free-GPU telemetry |
| Startup and defragmentation | Acceptance executors and thresholds are defined; representative measurements pending | Pre-pulled CPS/CIT bursts: p95 <=180s and maximum <=300s; KAI/fallback comparison with free capacity >=95% and waits/start <=110% of baseline, protected sessions unaffected |
| NFS and S3 artifacts | Existing storage preserved; accepted TLS relay path and owner-filtered artifact access work; ten owned-prefix 14/90-day retention cases passed against real S3 and Argo with least-privilege authentication | Real gateway-created notebook lifecycle, scheduled cleanup and off-host recovery; new CIT filer requires its actual endpoint/export |
| Monitoring | All four deployed dashboards rendered through actual Grafana with seven panels each and no browser page errors; unavailable physical/cap data was visibly marked | Promote and verify the newer dashboard definitions; complete eight-GPU inventory, physical placement/free-capacity and cap/protection telemetry, timing data and alert notification delivery |
| Restore and recovery | All five overnight automatic backup jobs succeeded; three corrected console/gateway runs verified current application/policy provenance, checksums, SQLite integrity and cleanup; matching logical restore history retained | Next automatic schedule after provenance correction, coordinated matching application/configuration capture, connected login/spawn, populated NFS/archive/artifact recovery and encrypted off-host durability |
| Moodle scaffold | Local provider, provenance migration, disabled scaffold and source tests implemented | Retain local CRUD, fake-provider reconciliation, no-network disabled behavior and clear enablement failure in the qualified release; Moodle remains planned/not deployed |
| Release train and compatibility | Candidate artifacts and compatibility tooling prepared; no unified production release declared | Complete pilot -> RC -> production gates, matched SDK/Hub/Lab/runner/notebook matrix, immutable digests, checksums/SBOMs, release notes, rollback and qualified Fleet promotion |
| Hub 6 | Separate staging scope | Keep outside production promotion until stable chart compatibility and migration/storage qualification pass |

## Current rollout boundary

The consumer configuration rollout completed at **2026-10-14 14:07 UTC**.
The earlier Hub8a adoption completed at **20:58 UTC on 2026-10-14**.
Gatewaybb and the paired Hub CA/CPU rollouts completed on **2026-10-15**. The subsequent
personal SDK and Lab XSRF handover now runs Hub1e from source
`9b7df79ba591ccc6fd6eb29b32e1e27ef0cc90e1` on both Hubs:
`ghcr.io/mul-cps/cps-compute@sha256:1e8bdc639ecc6f07a0f101f9157a724637bcc4468138fe1e19ff7dfe4bc73da4`.
The latest same-policy Gateway rollout adopted Gateway6d from source `846c02cf`
for the S3 end-of-file fix. Node8c and both consoles on Sourceb36 retain their images.
Four fresh process acknowledgments and a completed new delivery journal confirm
the unchanged policy and GPU driver epoch. The delivery controller is ready and
the final native allocation check is zero. The current delivery seed after these rollouts is
`sha256:0e99ef04a8d9b6f28a1a77d0969d90c1a9e74c3358fa742e1240147b0ce53f93`.
The earlier CIT legacy runtime enrollment and same-image cold handover remain
retained evidence; their previous seed is preserved in the new handover lineage.
The canonical policy hash is
`sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0`.
See [configuration evidence](../../platform-staging/jupyter-extensions-20261013/notebook-consumer-config-actual-20261014.json).
See [first-stage Hub adoption](../../platform-staging/jupyter-extensions-20261013/hub-stop-persistence-adoption-actual-20261014.json).
See [CIT runtime enrollment and cold handover](../../platform-staging/jupyter-extensions-20261013/cit-legacy-runtime-cold-handover-actual-20261014.json).
See [current trusted SDK Hub adoption](../../platform-staging/jupyter-extensions-20261013/trusted-sdk-hub-adoption-actual-20261015.json).

Both managed CPU configurations now select
`ghcr.io/mul-cps/cps-jupyter-notebook@sha256:d75d54d9b2b3b1b497e577124a30ca4c82993dd8458550a0b1fa73c37159b64f`.
The running personal bjoern/cpsadmin Pods are preserved on CPUad; loading the new
plugin requires a user-approved stop/start. Their current kernels have not been stopped.
The earlier CPU86 lifecycle evidence below remains historical. A temporary personal
CPS CPU named server has now verified the zero-argument SDK in an actual fresh kernel;
identity, profiles and session returned HTTP 200 as the reviewed bjoern person.
Its served prebuilt Lab entry exactly matched the qualified wheel. The test kernel
was deleted and the temporary server was stopped without removal; both original
personal Pods and the shared home PVC remain intact. Human panel and CIT personal
runtime acceptance remain pending. See [personal runtime evidence](../../platform-staging/jupyter-extensions-20261013/personal-sdk-runtime-actual-20261015.json). See [latest adoption evidence](../../platform-staging/jupyter-extensions-20261013/lab-xsrf-adoption-actual-20261015.json).
The normal Source lifecycle passed at **14:15 UTC**: Start, Ready, actual SDK/Lab
package verification, the live Compute panel, automatic account polling, NFS
writes and restart persistence, then normal Stop. The five ordinary visitor API
routes returned 200. Fresh read-only cleanup at **14:25 UTC** confirmed Pod
absence, a stopped and tokenless Hub account, inactive reservation and exact
retained PV/PVC identities and specifications. Original owned windows/groups
were restored and the temporary token was revoked. CIT personal profile hooks
retain their independently selected images.
See [runtime evidence](../../platform-staging/jupyter-extensions-20261013/notebook-consumer-runtime-actual-20261014.json).

The reviewed CIT `akadmin` alias is consumed by Source, its Hub and Gateway.
A normal authenticated `/compute/v1/me` read returned the reviewed canonical
person ID shared with CPS `bjoern`; its temporary token was revoked through the
Hub API. These checks used short-lived tokens for existing users issued through
the JupyterHub ORM. They establish actual API/browser behavior; fresh human
OAuth and distinct ordinary visitor RTC remain open.

The existing CIT `citnativegroupa` workspace account was adopted through the
normal authenticated Source plan/execute API. Its name, created identity, roles,
workspace descriptor and storage binding were preserved; only the neutral group
membership and Source adoption receipt were added. It now reports `ready`.
A later native server run exposed HTTP 403 for its activity callback. The
released operator CLI then enrolled the existing account with exactly its own
RTC-server access and activity-reporting scopes. Both Hubs restarted with the
permanent identity and role intact. A subsequent normal CIT Start/Stop test
verified HTTP 200 from the notebook's actual server token, automatic state and
token cleanup, the retained PVC and exact grant/group restoration.
See [adoption evidence](../../platform-staging/jupyter-extensions-20261013/cit-neutral-adoption-actual-20261014.json).
See [enrolled notebook activity and cleanup](../../platform-staging/jupyter-extensions-20261013/cit-enrolled-notebook-activity-actual-20261014.json).

Hub8a supplies the SDK connection environment after successful managed workspace
preparation, using the current notebook token. Its package passed 72 focused and
426 installed tests, with three unchanged root-fixture skips. The fresh CIT GPU
run on **2026-10-15** reached Ready, reported activity with HTTP 200 and received
all three SDK environment variables without probe injection. The ordinary
installed SDK request then failed with `ConnectError`; it did not produce an
authenticated `/v1/me` result. Normal Stop cleared native state, Hub/ORM server
records, notebook tokens and OAuth codes, preserved the PVC, and restored owned
windows, grants and groups. The current registered CPU attempt remains under
diagnosis. SDK acceptance and human OAuth remain open.
See [package publication](../../platform-staging/jupyter-extensions-20261013/trusted-sdk-hub-publication-actual-20261014.json)
and [adoption and subsequent SDK attempt](../../platform-staging/jupyter-extensions-20261013/trusted-sdk-hub-adoption-actual-20261015.json).
The publication receipt retains `deployed=false` at its original publication
boundary; the separate adoption receipt records the later live deployment.

Subsequent unauthenticated probes in both Hub namespaces resolved the initial
TCP refusal within five seconds, then consistently reached the gateway. Default
HTTPX verification failed because the SDK lacks the private CA; loading the
current CA exposed a missing Authority Key Identifier on the gateway leaf. A
local leaf repair then exposed a missing Key Usage extension on the CA. A local
renewal using the same CA key, subject and Subject Key Identifier passed strict
TLS while preserving hostname and trust rejection. The renewed
certificates were subsequently deployed with Gatewaybb, followed by the packaged CA transport in Hub4e and the selected CPUad notebook. The latest
CPU attempt failed during its NFS marker command before package or SDK capture;
its normal Stop, exact restoration, retained PV/PVC and token cleanup passed a
fresh read-only check. Both temporary operator tokens were revoked with HTTP
204. See [connection diagnosis and bounded cleanup](../../platform-staging/jupyter-extensions-20261013/sdk-connection-diagnosis-actual-20261015.json).

The CA transport fix at `a7b2850d1881b2bff8c0a9b865dfb3fa5ba9f94b` is
published as immutable qualification images: Hub `624a98b3`, CPU `ad693e5d` and
GPU `7e3f6f7d`. Actual installed tests passed (Hub 481 with four known skips;
CPU 14; GPU 14). Dependencies and original compressed base layers are preserved.
CPU image adoption uses the independently pinned Hub CPU image input and does
not require a catalog edit. The coordinated trust and Hub
rollover is complete; real kernel submissions from both Hubs are the next gate. The legacy CIT
neutral account now has a packaged CPU adapter at source `31ff2e72`. Its exact
Hub4e image passed 509 installed Hub tests (five skips), 13 SDK tests (one skip),
and the configured UID1000 check; that adoption preceded the current Hub1e. A profile
switch alone on the earlier Hub does not supply its trusted CPU image. The GPU image update retains its
separate policy/workload transition gate. The current production/pilot
deployment subsequently moved to Hub1e with CPUd75 selected and then Gateway6d;
native GPU image916 remains unchanged. A stale acknowledgment during finalization was recovered by
repeating read-only finalization at the unchanged 30-second TTL; previous mutations
were not replayed. Four fresh ACKs, the new completed journal and native zero
passed. See [paired Hub adoption](../../platform-staging/jupyter-extensions-20261013/notebook-batch-hub-adoption-actual-20261015.json) and
[package and remote publication evidence](../../platform-staging/jupyter-extensions-20261013/sdk-ca-publication-actual-20261015.json).

The actual personal CPS notebook exposed a second browser boundary on October
15: its same-origin Compute API was configured correctly, but an unauthenticated
fetch encountered the console's OAuth redirect. Completing that redirect in the
browser then failed because nginx rejected the callback response headers as too
large. Both Hub ingresses now use a 16 KiB response-header buffer and 32 KiB busy
buffers. All four controllers passed their compiled configuration checks; the
existing notebook was not restarted. The user subsequently logged in again;
ingress logs confirm the CPS OAuth callback redirected successfully and console
browser APIs returned HTTP 200, without another header error. The Lab visitor
API retest still failed: Hub 5.5.2 requires the Source-bound XSRF token even on
browser GET requests, while the old addon only obtains it for mutations. The
existing authenticated bootstrap route also needs the intended same-origin
read-only `no-cors` fetch mode. A real Chromium check confirms that this response
is readable, while OAuth redirects remain opaque. The prebuilt fix at `6854d532`
now bootstraps that token and sends it on every normal API request, retaining Hub
authentication and XSRF checks without substituting the kernel's identity. The earlier candidate
CPU722 is published for traceability but must not be deployed as the functional
connection fix; it only improves the error message.
The fix includes the explicit Connect action from `49c9b972` and distinguishes
authentication, permission and network failures. Its CPUd75 image is published and
selected for future CPU starts on both Hubs. The actual Hub 5.5.2 Chromium regression,
panel browser tests, 43 Node tests and 9 installed Lab tests passed. The handover
completed with four fresh process acknowledgments, a new completed delivery journal
and native zero. A stale acknowledgment at activation was recovered through readonly
freshness checks at the unchanged 30-second TTL followed by the single remaining
original controller CAS; prior mutations were not replayed. Existing personal Pods
remain unchanged; restart and actual panel acceptance remain pending. See
[adoption evidence](../../platform-staging/jupyter-extensions-20261013/lab-xsrf-adoption-actual-20261015.json) and
[browser connection evidence](../../platform-staging/jupyter-extensions-20261013/compute-browser-connection-actual-20261015.json).

The walkthrough notebook and its separate batch target/helper are delivered to
`bjoern` in `compute-demo-20261015-5df04787`; existing notebooks were preserved.
Its network access and job submissions require explicit opt-in. A real CPU
submission through the authenticated visitor API succeeded as workflow
`cps-3d0ee6ec7090b84ee51fdf46b3c32979a110c9dca8079ad7`.
The reproduced S3-stream EOF fix at `846c02cf` is now deployed as Gateway6d.
Authenticated reads of this existing workflow, artifact listing, 20,480-byte
snapshot and 4,315-byte executed notebook all returned HTTP 200. Retained download
bytes verified the exact selected helper, stripped input outputs, typed parameters
and completed execution cells. No new workflow was submitted. The rollout completed
with four fresh process acknowledgments, a new delivery journal and native zero.
Two pre-image helper failures were retained and corrected without replaying
previous mutations. The temporary API actor was revoked with HTTP 204. Source
attachment/security-header forwarding remains a separate staged fix. See
[EOF rollout and download evidence](../../platform-staging/jupyter-extensions-20261013/artifact-eof-adoption-actual-20261015.json).
This is a visitor-token test, not human OAuth or the fresh-kernel SDK gate.

A subsequent fresh personal CPS kernel used the ordinary installed SDK to submit
both a successful and intentionally failing notebook job. Both immutable snapshots
and executed notebooks were downloaded and validated; selected helper bytes,
stripped input outputs and typed parameters matched. The log API returned HTTP 200
for both cases. The owned kernel, temporary server and API token were removed or
revoked normally, preserving both default servers. These are real SDK submissions,
not the earlier visitor-token-only test. See [SDK batch evidence](../../platform-staging/jupyter-extensions-20261013/notebook-sdk-batch-actual-20261015.json).

That test also exposed an existing personal-storage hazard: image CWD and the
notebook root fall back to `/home/jovyan/work`, which the Hub mounts as `emptyDir`.
The persistent home PVC is mounted at `/home/jovyan`. Both default users' current
work files have now been copied into private, hash-verified point-in-time backups
on their persistent homes, without changing the source files or stopping kernels.
The demo also has a persistent home copy. Future saves need the personal-only
packaged root/CWD correction; restart remains pending. Take another current backup
before any approved restart. See [preservation evidence](../../platform-staging/jupyter-extensions-20261013/personal-work-preservation-actual-20261015.json).

The personal notebook's startup Longhorn attachment warning recovered without
intervention: the same PVC became attached/healthy, and the notebook became
Ready with no restart. Managed CPU Start remains separately blocked by the
storage privacy guard: the personal notebook's existing parent NFS mount exposes
the retained V1 workspace subtree. The attempted lifecycle was stopped and its
owned changes restored. Do not weaken that guard or stop the personal notebook
to force acceptance; a reviewed migration to the existing private V2 root is
still needed. Personal zero-argument SDK configuration was also found absent;
the fix at `9b7df79b` passed 524 actual installed Hub tests with five existing
skips and is deployed as Hub1e. Existing servers receive its environment on their
next start; a fresh personal CPS named-server kernel has now verified HTTP 200
using its own token and zero-argument SDK. The reviewed bjoern mapping is retained; cpsadmin is not automatically
linked to that person. Its identity relationship requires an explicit decision.

Notebook submissions already snapshot saved inputs, strip outputs and execute
through the approved batch runner. The new owner-authenticated artifact byte API
also supports shared kernel principals, without using the personal-only Argo UI
route or an S3 presigned URL. The exact Gateway candidate `bb6113b7` passed 235
installed tests, preserves all 48 Core modules apart from the three reviewed
source changes, and was deployed before the current EOF correction. The coordinated TLS and capture credential
rollover passed all four process acknowledgments, the new completed delivery
journal and native-zero checks. See [gateway adoption evidence](../../platform-staging/jupyter-extensions-20261013/notebook-batch-gateway-adoption-actual-20261015.json). A frozen 32-test kernel
harness covers successful/failed notebooks, selected helper files, typed
parameters, immutable snapshots, logs/results and ordinary Hera submission.
No new live kernel submission acceptance is claimed. A fresh read-only policy
check confirms only `batch-cpu` is enabled; all seven GPU batch profiles remain
disabled. See [notebook batch preparation and package evidence](../../platform-staging/jupyter-extensions-20261013/notebook-batch-preparation-20261015.json).

Authenticated profile/status API checks passed on both consoles. Selecting the
approved `native-group-a` workspace returns an enabled 5 GiB profile on CPS and
10 GiB on CIT, with `nativeGroupReady=true`. The global profile list retains its
CPU baseline while broader GPU qualification is disabled. Each workspace gets
its own approved profile; this does not enable arbitrary new GPU workspaces.
Both temporary API-reader tokens were revoked through the normal Hub endpoint.
See [paired admin profile APIs](../../platform-staging/jupyter-extensions-20261013/admin-scoped-gpu-profiles-actual-20261014.json).

The simultaneous cross-Hub pilot reservation test passed at **15:32 UTC**.
CIT held both shared canonical members once while CPS was denied; CPS then
reached Ready after CIT's confirmed shutdown. Both workspaces closed and original
windows/groups/grants were restored. The two owned tokens were revoked. Source
reported the losing asynchronous spawn as 503; a fresh exact Gateway
`reservation_conflict` audit is required to classify it, so ordinary startup
failures are not accepted as conflicts.
See [reservation evidence](../../platform-staging/jupyter-extensions-20261013/cross-hub-reservation-actual-20261014.json).

Both console image-only updates to **Sourceb36** completed with guarded
Deployment UID/spec/resourceVersion comparisons and fresh matching SQLite
backups. Each console has one ready application replica and zero restarts;
configuration, frontend and runtime dependencies are preserved. Before the Hub
update, its CLI rejected stale stopped-server bookkeeping. The Hubd920 package
from source `406a7a40342fd9fc021a3eb09a191ac987c135a7` then passed 421 installed
tests with three explicit root-fixture skips and completed paired-Hub adoption.
Normal Source CIT Start/Stop subsequently passed: automatic cleanup left all
four native runtime fields empty, Hub and ORM server records absent, and zero
notebook tokens and OAuth codes. The original Longhorn PVC UID was preserved;
owned windows, all grants, Hub group membership and actor groups were restored
exactly through the normal paths, without direct SQL writes. This acceptance did
not perform legacy runtime enrollment or qualify human OAuth or hardware caps.
See [console adoption](../../platform-staging/jupyter-extensions-20261013/console-legacy-runtime-adoption-actual-20261014.json)
and [installed partial rollback](../../platform-staging/jupyter-extensions-20261013/reservation-installed-partial-rollback-actual-20261014.json).
See [normal CIT Stop persistence](../../platform-staging/jupyter-extensions-20261013/cit-normal-stop-persistence-actual-20261014.json).

Dynamic no-MIG GPU sharing remains bounded to the approved 5/10 GiB pilot and
two parents within a 15 GiB pool. The passed current pair isolation/MPS history
is retained below. KAI coordinator/binder activation and wider GPU packing
remain unqualified. Distributed JobSets are disabled: `/jobsets` returned the
expected 503 while workflow reads succeeded. The platform remains
**limited-pilot**, with broader scheduling, recovery and production release
gates open in the ledger above.

## Earlier rollout and retained diagnostics

### Superseded Hub and CPU rollout diagnostics


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

### Earlier platform deployments

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
The Gateway then completed its `08f7720` image handover at 10:47 UTC. This
includes the exact unchanged-workspace registration fix for a resumable
provisioning fence. Both Hubs, Source, the Node image and capture companion
remain unchanged. Fresh hardware zero, four-process acknowledgments and the
new delivery journal passed. The actual handover receipt is
`platform-staging/jupyter-extensions-20261013/gateway-storage-resume-handover-actual-20261014.json`.
The normal CPU Start, Ready, NFS marker and Stop gate remains separate.
The following normal CPU retry passed registration/provisioning and KAI
placement, but the notebook repeatedly crashed. A bounded repeat captured
the actual startup exception before automatic shutdown: Jupyter attempted to
create `/home/jovyan/.local/share/jupyter` on the immutable filesystem.
Both failed attempts have genuine stopped-state, reservation, token, Shares
and original-window restoration proof.
The packaged Hub fix at source `acb34b06` sets four trusted directory paths
inside the writable workspace for registered CPU workspaces. Its immutable
`29b7b3e` image passed 2,159 source and 187 installed tests, independent review,
the actual readonly-image constructor regression and remote overlay readback.
Generic personal servers, native GPU workspaces and security/resource/mount
settings retain their existing behavior. Publication evidence is
`platform-staging/jupyter-extensions-20261013/neutral-cpu-bootstrap-hub-fix-publication-20261014.json`.
Paired-Hub adoption completed at 12:16 UTC. At that earlier boundary both Hubs
ran `29b7b3e`, all
four processes acknowledged the new configuration, delivery completed its new
journal and the final native allocation check was zero. Only the two Hub images,
their immutable bootstrap references and matching runtime trust pins changed.
The existing notebook image, identity maps, Source, Gateway, Node and storage
remained unchanged. Actual evidence is
`platform-staging/jupyter-extensions-20261013/neutral-cpu-bootstrap-hub-handover-actual-20261014.json`.
The normal CPU Ready/NFS marker gate then passed at 12:44 UTC with exit code
zero. An existing CPS administrator's short-lived API token used normal Source
Start/Stop: the notebook became Ready with zero restarts, authenticated API
access worked, and a UID 1000/GID 100 process wrote and read its NFS marker at
`/workspace`. A newly spawned Pod read the previous marker with the same hash
on the retained volume, confirming restart persistence. Stop removed server
access and Shares. Full creation audit checks passed; original grant/membership
windows and groups were restored exactly, and only the test token was revoked.
The runner required canonical Kubernetes quantity comparison and an 8 MiB
allowance for the exact audit endpoint, whose complete history exceeded its
ordinary 1 MiB response bound. These were test-harness corrections; workload
resources and storage configuration were unchanged. Actual evidence is
`platform-staging/jupyter-extensions-20261013/neutral-cpu-nfs-lifecycle-actual-20261014.json`.
The original `ff0c30d` notebook image was retained for this acceptance. Notebook
package adoption, fresh human OAuth and distinct ordinary visitor RTC remain
separate gates.
Actual authenticated CIT browser/API evidence is retained in
`platform-staging/jupyter-extensions-20261013/cit-authenticated-ui-api-readback-20261014.json`.
The owning `akadmin` token successfully read the admin API. A fresh headless
browser rendered the real deployed console, observed another status poll, and
showed `interactive-shared-10` after selecting its approved shared workspace.
No browser API mutation or page error occurred. Unscoped grant choices remain
CPU-only. The separate operator report was stale, while the live approval API
was ready; these states must not be conflated. The reviewed CIT `akadmin` alias
to the existing CPS `bjoern` person was subsequently persisted through normal
authenticated Source HTTP, without email matching or mandatory verification.
Its receipt is
`platform-staging/jupyter-extensions-20261013/cit-reviewed-source-alias-actual-20261014.json`.
Gateway and CIT Hub canonical mapping propagation and runtime linkage still
need the coordinated update; Source alias persistence alone does not close
that gate.
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
