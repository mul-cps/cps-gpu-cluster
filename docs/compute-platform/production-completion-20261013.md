# CPS/CIT production completion

**The platform remains `limited-pilot`; the full project and production
qualification are unfinished.** This ledger follows the original platform plan
through source implementation, immutable publication, live deployment and
measured acceptance. Evidence for one stage does not establish the next stage.
See the [operational acceptance record](qualification/operational-acceptance-20261013.md)
for the bounded live results of 2026-10-13 and their retained evidence.

The ordinary-student `shared-gpu-lab` pilot now passes normal Source Start,
Ready, a current native 5 GiB cap, two-browser RTC and GPU execution without MIG.
[Open the shared GPU demo](https://jupyterhub.dshl.unileoben.ac.at/user/cps-ws-27c474f74f9d41c53eac0be01fcca8a3/rtc/lab/tree/shared-gpu-demo-20261015.ipynb).
Gatewayd974 now exposes the authorized workspace in both students’ normal
**Compute → Shared Workspaces → Open workspace** flow. A normal Stop/Start
verified shutdown before reservation release, a fresh capped Pod, persisted demo
files/output, and renewed two-way RTC/GPU execution. The GPU916 Compute addon
and ordinary SDK still fail. Three active global member reservations are
verified. See the
[current status and limits](shared-gpu-lab-20261015.md).

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
| SDK, Hub and Lab packages | Both Hubs now run Hub604c from source47e. Its default user role preserves later student membership across restart, retaining the Compute scopes, CIT personal GPU guard, persistent personal root and SDK fixes. Its 93 installed tests passed under Hub 5.5.2/KubeSpawner 7.1.0. CPS old-cookie Compute and personal Share access passed for both students; CIT old-cookie default-role access passed without reauthentication. Both managed CPU configurations select CPUd75; existing bjoern/cpsadmin Pods remain on CPUad | CIT personal SDK/Compute/RTC image adoption, a fresh post-restart RTC edit test and other notebook variants remain separate gates |
| Both admin UI consoles | Both consoles run Source51f with authenticated download-header forwarding and the reviewed legacy runtime validator; frontend and dependencies remain equal to Source87a1. CIT legacy runtime enrollment, cold startup and real notebook activity reporting passed; the existing UI and approved 10 GiB choice remain bounded evidence | Normal registered CPU lifecycle and reviewed CIT `akadmin` canonical API linkage passed; ordinary-user/human OAuth and remaining modes are separate gates |
| Identity and group ownership | Existing reviewed aliases retained; both CPS legacy neutral accounts have permanent ready provenance; explicit custody migration and exact QA repair passed; both Hubs restarted without changing the repaired or legitimate legacy roles | Reviewed CIT alias is live in Source, Hub and Gateway and `/me` resolves the same person; real login grant survival/expiry, scoped administration and cross-Hub allowance continuity remain |
| Native GPU isolation | Controlled no-MIG 5/20 GiB history retained; current CPS pair passed distinct 5 GiB OOM/recovery with peer progress, IPC denial in both directions, positive controls, kernel witnesses, restart retirement, complete bounded MPS OOM/recovery and observer cleanup, and confirmed normal closure | Complete restart behavior and broader packing; current bounded pool is 5/10 GiB, not a normal 20 GiB or cross-Hub qualification |
| Shared GPU reservations | Actual simultaneous CPS5/CIT10 pilot starts passed: one winner held both shared members once, loser had no server/Pod/binding; confirmed Stop preceded successful retry on the other Hub; exact windows/groups/grants restored. Installed first-free/second-busy rollback also passed. The current student workspace has three actual global member reservations bound to one attempt; a normal GUI CPU batch succeeded in 22 seconds while its GPU Pod remained Ready | Different-member live API partial-conflict rollback, permitted CPU sessions while held and broader pool qualification |
| Workspaces and local assignments | The ordinary shared-gpu-lab 5 GiB workspace passed normal Source Start, Ready, actual native cap verification, two-browser RTC and live GPU output. Mikasa/Armin retained distinct visitor identities and the same demo kernel. Storage version 2, exact group Share and three seven-day grants are verified. After Gatewayd974 adoption both students discover and open the workspace through Compute; normal Stop/Start preserved the saved demo/output and renewed RTC/GPU execution on a fresh capped Pod | GPU916 addon/SDK compatibility; membership removal closing existing access and stopped-writer read-only archives |
| Workflow gateway and admission | Source validation/ownership paths implemented; bounded CPS own-success/failure artifact/log bytes and foreign-versus-absent rejection passed; controller admission/RBAC checks passed | CIT normal-user own/foreign access, human authentication, token renewal and crafted workflow/admin bypass scenarios on the current release |
| Notebook execution | Personal CPS SDK success/failure jobs passed. Ordinary Mikasa Submit UI jobs passed typed parameters, selected support imports, authenticated executed-notebook downloads and logs, with Armin denied personal job access. A further GUI CPU job succeeded in 22 seconds while the shared GPU workspace remained Ready with its three reservations | CIT personal/shared-kernel runs and broader current-release coverage remain open |
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
personal SDK/Lab XSRF handover ran Hub1e. The persistent-home rollout adopted
Hub8e from source `13d6604821caacff0a07190c041792fe56747354`; that historical
image passed 529 installed tests with five existing skips. The subsequent
paired-Hub handover `81a6f1ca` adopted Hubf6 from source
`53f5c75283c38927aa5bb97e5c5270230ece380e` on both Hubs:
`ghcr.io/mul-cps/cps-compute@sha256:f6c40516a180407aa42d64e4b1b4205ef44879e9f98b997b7ea1a01469c37fe4`.
Its 52 installed tests remain historical evidence. The current paired-Hub
membership handover `fdef85f9` now runs
`ghcr.io/mul-cps/cps-compute@sha256:604c94e62da8c3594579dcec21b3b5810479fadece94abfc0e90aec542165b62`
from source `47e01f738817d425fdf0e2b26b4ff1e7ff418fe9`. Its 93 installed tests
passed under Hub 5.5.2/KubeSpawner 7.1.0, including actual startup/restart
membership and neutral-account custody, login guards, CPU and native 5/10 GiB
preservation. Only `cps_compute_hub/hub.py` and one RECORD row changed from f6;
the other 63 Python modules, all 137 dependency versions, all f6 base layers and
the entire runtime configuration are preserved. Final and controller activation
readbacks are ready with `production_qualified: false`. Historical f6
publication/adoption receipts remain retained. The earlier persistent-home
candidate failed its UID1000 packaging check and was never published.
See [persistent-home adoption](../../platform-staging/jupyter-extensions-20261013/personal-root-adoption-actual-20261015.json).
The earlier Gatewayeea5 storage adoption enabled versioned storage routing,
retaining the S3 end-of-file fix. New workspaces select private storage version
2; existing version 1 bindings retain their paths. Explicit CPS mappings for
the two student accounts remain preserved. The latest Gateway-only handover
`8bfcb51c` adopted
`ghcr.io/mul-cps/cps-compute@sha256:d974acab8ee692fd68419875f8e0519f5bca482b83b33d36f990abc526959c38`
from source `3e053ba82461f8c95ea0e725400b9c82135b2afc`. Its 341 installed
tests and the 32 offline handover checks passed. Four fresh component
acknowledgments, the final completed journal and actual controller activation
readback are ready. Both Hub604 processes, Node8c, Source51f, GPU916, storage,
canonical mappings, policy and driver epoch were retained. No activation
continuation was needed.

The current delivery seed is
`sha256:ef1d257be57411fb94548657e1214ec8c19f328415f4c713b5e3ffb52aa0ebe5`;
the activation intent is
`sha256:917c0b9c9e465d895ff9dc676fba37fbf249f6a74dac228bdff2e76306c763d1`.
The earlier ce5/a106 membership completion, f6 seed `0474dec6` and storage seed
`2636966b` remain historical lineage. Handover completed at native zero; a
subsequent normal Source Start runs the test group with three actual member
reservations on fresh Pod `79388657-dea1-4d49-b5e6-6c7d7e6a514b`.
Root revoked its temporary operator access at 16:41:31 UTC; ordinary human OAuth
sessions were untouched. Four personal Pods retained their UIDs and restart
counts. See [discovery adoption and restart acceptance](../../platform-staging/jupyter-extensions-20261013/student-discovery-adoption-actual-20261015.json).
See [student storage and identity adoption](../../platform-staging/jupyter-extensions-20261013/student-storage-identity-adoption-actual-20261015.json)
and [604c membership adoption](../../platform-staging/jupyter-extensions-20261013/student-user-role-membership-adoption-actual-20261015.json).
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
The running personal bjoern/cpsadmin Pods remain on CPUad. The qualified prebuilt
frontend is now installed through the standard user package prefix in both homes;
fresh Lab HTML and both JavaScript bundles match the fixed wheel. The three bjoern
kernels and one cpsadmin kernel retained their IDs, and neither server restarted.
A browser reload is required to replace already loaded JavaScript. Human panel
acceptance remains pending. Remove the recorded user override after an approved
restart onto a qualified fixed image so it does not shadow future image upgrades.
See [live frontend update evidence](../../platform-staging/jupyter-extensions-20261013/compute-live-ui-update-actual-20261015.json).
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
remain unchanged; the subsequent standard user-prefix frontend update now serves
the fix without a restart, while actual human panel acceptance remains pending. See
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
The demo also has a persistent home copy. Both Hubs now apply the personal-only
root/CWD correction to new servers; the existing default servers retain their
current runtime root until an approved restart. Actual temporary-server acceptance
now passed: a notebook and text file saved through the normal ContentsAPI retained
exact hashes after normal Stop/restart, on the same home claim/PV. Both test
starts used `/home/jovyan` as root/CWD; temporary files/server were cleaned up and
token a692 was revoked. All four existing kernels retained their IDs.
See [persistence acceptance](../../platform-staging/jupyter-extensions-20261013/personal-root-persistence-actual-20261015.json). Take another current backup
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

The Source51f image-only rollout passed strict before/after online SQLite checks:
schema7, integrity and all six table row fingerprints are unchanged for each console.
New Source Pod observer bindings replace the old Pod-UID closure for future work;
the completed75b/seed6c4 journal remains unchanged. Read-only successor checks passed
with four fresh ACKs, unchanged central approval raw hash and native zero.
See [Source adoption](../../platform-staging/jupyter-extensions-20261013/source-artifact-header-adoption-actual-20261015.json).
Four actual CPS proxy downloads (snapshot/executed notebook for success and failure)
returned HTTP200, matched the original SDK bytes, and retained attachment/no-store/
nosniff/sandbox headers. Token a695 was revoked; this is API-token acceptance, not
human browser or CIT acceptance. See [download checks](../../platform-staging/jupyter-extensions-20261013/source-artifact-header-downloads-actual-20261015.json).

The current `bjoern` and `cpsadmin` Compute extensions now preserve regular
workflow cards when the optional distributed launcher reports its exact
not-configured response. Other service, workflow, network and authentication
failures still surface. Source `db49a558` passed 45 Node tests, 10 packaging tests
with 12 subtests, and the rendered panel test. Both running servers serve the
new bundle; their Pod specs and four existing kernels are unchanged. A browser
reload is required. Notebook image defaults are not changed by this user-package
update. See [live update](../../platform-staging/jupyter-extensions-20261013/workloads-optional-jobsets-live-20261015.json).


## Student Compute access and personal server sharing, 2026-10-15

The two ordinary test accounts, Mikasa and Armin, use the existing CIT directory
through Dex on the CPS Hub. They remain non-administrators. Their explicit
reviewed directory identities map to distinct canonical people; no account was
linked by name or email. Their course/project CPU grants are time bounded.

Armin completed a normal directory login and opened Mikasa's existing CPU server
with HTTP 200. The server reported the actual visitor as Armin. His Share grants
only `access:servers!server=mikasa/`; an OAuth authorization URL itself is not
a Share. Open the stable [workspace URL](https://jupyterhub.dshl.unileoben.ac.at/user/mikasa/lab)
while logged in as Armin. The subsequent actual two-browser personal CPU RTC
test passed edits in both directions without reload, retaining Mikasa and
Armin as distinct visitors. No notebook code was executed, and only the demo
sessions were cleaned up. This two-way edit test remains evidence from before
the f6 restart. After the 604c restart, both original CPS browser sessions again
passed Compute and personal Share access with HTTP 200, preserving distinct
canonical people and notebook visitor identities; both admin requests returned
HTTP 403. A new two-way RTC edit test is not recorded by this readback. These
personal CPU checks do not establish pooled GPU execution.

Both dedicated Compute visitor services are deployed with separate OAuth/cookie
credentials, verified Hub/Gateway TLS and working proxy redirects. Mikasa and
Armin each completed ordinary CPS Compute OAuth and saw their own canonical
identity and project grants. Mikasa's My Workloads view renders normally with
the optional distributed service visibly unavailable; her admin-console request
returns HTTP 403. No admin-console service scope was granted to either student.

The latest prebuilt addon includes the five Snippets refinement passes, ordinary
Hera examples, permitted profile/project/image choices, safe cell insertion and
the optional JobSet fix. Its visitor-prefix compatibility wheel is installed in
the three running CPS servers without a restart. Their kernel IDs are preserved.

Hub restart first exposed that a database-only custom role is removed during
startup. The historical f6 adoption moved Compute access into the default user
role and closed the unqualified legacy CIT personal GPU path. A later real Hub
5.5.2 restart exposed an inherited static `user.users` snapshot that removed
students added after that snapshot. The current 604c image removes that snapshot
while retaining the role's scopes and other configuration. Its 93 installed
tests passed, and both Hubs now run it through the completed `fdef85f9` handover.
The final and controller activation readbacks are ready; production qualification
remains false. CPS old-cookie Compute and personal Share acceptance passed for
both students. On CIT, both original cookies retained each student's default
user role without a login, role change or new spawn; this test issued no CIT
Compute requests. CIT's personal runtime adoption remains a separate gate.

Ordinary Mikasa also submitted a saved CPU notebook through the normal Submit
UI, with typed parameters and an explicitly selected support module. The job
succeeded and its executed notebook downloaded through the authenticated API.
Armin could not list it and received HTTP 403 for inspection, logs and artifacts.
See [ordinary student GUI batch acceptance](../../platform-staging/jupyter-extensions-20261013/ordinary-student-gui-batch-actual-20261015.json).

See [student access and addon evidence](../../platform-staging/jupyter-extensions-20261013/student-compute-sharing-actual-20261015.json).
See [604c membership adoption and browser readbacks](../../platform-staging/jupyter-extensions-20261013/student-user-role-membership-adoption-actual-20261015.json).
For `shared-gpu-lab`, normal Source structural approval, provision of
`interactive-shared-5` with storage version 2, and seven-day grants for Mikasa,
Armin and Bjoern are verified. Normal Source Start returned HTTP 200 and reached
Ready in 26 seconds. The existing GPU916 Pod on GPU2 has a current driver row
with both soft and hard limits of 5,368,709,120 bytes, matching its current boot
and cgroup. Mikasa and Armin opened the exact shared server with HTTP 200,
retained their own visitor identities, shared the same demo kernel and passed
RTC edits in both directions. The GPU cell executed and the peer saw its live
output. Only the one owned demo session/kernel was cleaned up. The neutral
account remains non-admin without the default `user` role; its exact server
Share belongs to the three-member `mikasa-armin` group.

The earlier Start/Hub capture's RTC/allocation flags were false because those
checks had not yet run. The later cap and browser receipts establish the bounded
GPU/RTC result. The old GPU916 addon still has a null Compute PageConfig URL and
shows `Failed to fetch`; its ordinary SDK still fails CA trust. Explicit trusted
CA plus both SDK headers passed diagnostic `/v1/me` as the workspace principal,
and a separate 64 MiB CUDA allocation/sum passed with CUDA reporting 5 GiB.
Those diagnostics do not establish ordinary addon/SDK compatibility. The
replacement GPU531 image is packaged and published but has not been adopted.
The earlier empty personal C7 workspace list was fixed by Gatewayd974; both
normal students now find and open the authorized group workspace through
**Compute → Shared Workspaces → Open workspace**, preserving their own canonical
identities. After a normal Source Stop/Start, the saved demo and output remained,
the fresh Pod passed the current 5 GiB cap check, and two-way RTC plus same-kernel
GPU execution/live peer output passed again. A Root-reviewed read-only Gateway observer
confirms the three registered canonical people each hold an actual global
reservation bound to one attempt for `cps:shared-gpu-lab`. A normal Mikasa GUI
CPU batch was accepted with HTTP 200 and succeeded in 22 seconds while the GPU
workspace stayed Running and Ready on the same Pod. Its typed parameters,
selected helper import, authenticated notebook download and logs passed; Armin
could not list, inspect or read the personal job's logs, artifacts or download.
See [CPU batch during the shared GPU session](../../platform-staging/jupyter-extensions-20261013/cpu-batch-during-shared-gpu-actual-20261015.json).

See the [working shared GPU lab guide](shared-gpu-lab-20261015.md),
[current discovery/restart receipt](../../platform-staging/jupyter-extensions-20261013/student-discovery-adoption-actual-20261015.json),
and [historical initial native 5 GiB acceptance](../../platform-staging/jupyter-extensions-20261013/shared-gpu-lab-native5-actual-20261015.json).
The prospective-only `efa3c8ab` validator and two qualified Gateway/Hub image
candidates are unpublished and not live; no fresh six-category hardware gates
have run for GPU531. GPU batch remains disabled.
Membership-removal connection revocation, CIT own/foreign workflows, CIT
personal runtime adoption, wider GPU packing and production qualification remain
distinct work.
