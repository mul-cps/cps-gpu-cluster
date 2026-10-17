# CPS/CIT current state — 17 October 2026

The platform remains **limited-pilot**. Production qualification and the full
project are unfinished. This record supersedes current-state statements in the
older completion ledger; their dated acceptance results remain historical evidence.

## Current gate — legacy IPC and distinct-process VMM passed at 5/5 GiB

Application `5ca3b4c5b6b0481011ae24958ea2de0cc5652c15` fixes the readiness
clock race by sampling trusted time after external reads. The full application
and Hub suite passed 2,918 tests and 49 subtests (3 skipped). Corrected Gateway
and Hub images are deployed; installed module hashes match the reviewed source.
Six delayed live reads passed, including a real heartbeat arriving during reads.
A fresh post-cleanup read verifies all four consumers ready on revision
`1e2b09e4…01d88a1`. Policy and driver epoch are unchanged.

Two normally started isolated workspace Pods with sealed 5 GiB caps passed
bidirectional legacy CUDA IPC tests: same-parent positive controls, cross-Pod
error 800, matching kernel denial and surviving kernels. Independent offline
review confirmed source pins, process attribution and witness correlations.
[Scoped evidence and cleanup](../../qualification-artifacts/native-cross-pod-ipc-20261017/README.md).
Both normal Stops completed; all 103 native allocations are released. Temporary
grants were restored, the test token revoked, and all four personal notebook
Pod UIDs preserved. No MIG, reset, reboot or personal interruption occurred.

The next actual run also passed both directions of distinct-process VMM/POSIX-FD
import isolation at 5/5 GiB. The same actual 64 MiB FD imported successfully in
a separate same-parent process; cross-parent import returned CUDA800 with exact
kernel attribution (reason6/status27/clientKind4). Both endpoint kernel streams,
cleanup and unchanged authority checks passed; independent offline replay cleared
the evidence. [VMM results](../../qualification-artifacts/native-vmm-distinct-process-20261017/results/).
Both normal Stops completed, all 106 native claims are released, SQL reservations
are empty, temporary grant expiry changes restored and the test token revoked.
Personal notebook Pod identities remain unchanged.

**Remaining primary gates:** other memory routes, larger caps and peer OOM
continuity, MPS, and concurrent startup. One
parallel Start failed while a custody snapshot observed an allocated intent
before its immutable enrollment; sequential fresh Starts later succeeded.
Application `67c6138` fixes the inconsistent ledger/inventory snapshot; 2,922
application/Hub tests and 49 subtests passed (3 skipped). Its Node image is
published but not deployed. Concurrent startup and broader production
qualification remain unqualified.

## Earlier verified checkpoint — native 5 GiB execution and normal Stop passed

Application `7273ad70c497cafcd7116867343a4b5ae9b6909c` is deployed on the node,
Gateway and both Hubs. Its full application suite passed 2,614 tests and 49
subtests (3 skipped). All four jobs in
[CI 38981766707](https://github.com/mul-cps/cps-compute/actions/runs/38981766707)
passed, and the three published image digests were independently verified.
All 24 existing non-Hub Pod identities were preserved during adoption.

The normal console Start of `shared-gpu-lab` returned HTTP 200/running and
created Pod UID `e92edb4d-df2d-46e8-b1c6-77add740af9a`. Independent host NVML
reads confirmed sealed soft and hard caps of 5,368,709,120 bytes. The approved
PyTorch runtime reached OOM at a 4,831,838,208-byte allocator peak, freed its
allocations, and successfully allocated and read back another 256 MiB. No
HAMi preload, limit environment or mapped interposer was observed. The
relationship between allocator bytes and the driver's charged-usage counter
remains unexplained; this result does not establish every memory route or MPS
isolation.

Normal Stop returned HTTP 200/stopped, removed the Pod and released all 95
native ledger claims; both SQL reservation tables were empty. The first fresh
Start was rejected before mutation while readiness was withdrawn during cleanup.
All four acknowledgments recovered without intervention. A second normal Start
returned HTTP 200/running with a new Pod UID
`f0a54c4a-bbc6-4dfe-98e5-eabc3c913cb7`; independent NVML reads confirmed another
sealed 5 GiB cap, and a 256 MiB CUDA allocation/fill/readback passed. Thus the
normal Stop/restart gate passed, with a temporary readiness transition. The
specific transient ValueError is not explained by the available logs.
The second normal Stop also returned HTTP 200/stopped. The Pod is absent, all
96 claims are released and both SQL reservation tables are empty. The temporary
test token was revoked (204; subsequent authentication denied) and removed locally.
The [lifecycle receipt](../../platform-staging/jupyter-extensions-20261013/native-group-lifecycle-20261017.json)
records this checkpoint. Private evidence is under
`~/.local/state/cps-full-project-20261013/native-archive-live-qualification-7273ad7-20261017/`.

The earlier `610814a` rollout and failed pre-enrollment attempt remain historical
in the [protocol verification receipt](../../platform-staging/jupyter-extensions-20261013/native-enrollment-protocol-verification-20261017.json)
and [adoption receipt](../../platform-staging/jupyter-extensions-20261013/native-enrollment-protocol-adoption-20261017.json).
The subsequent archive and bounded Hub cleanup fixes enabled the execution
above. Failed-spawn ghost-state recovery, independent peer isolation,
MPS and the broader production gates remain unqualified. No MIG, driver change,
GPU reset or reboot was performed.

## Same-workspace aggregate allocation qualification

The [trusted raw CUDA probe and receipt](../../qualification-artifacts/native-parent-aggregate-20261017/README.md)
passed on a fresh normally started 5 GiB workspace. Two distinct child processes
used direct libcuda allocations with full writes, synchronization and readback.
With process A holding 2 GiB, B reached 2 GiB before typed driver OOM. After A
reduced its allocation to 256 MiB, B reached 3.75 GiB before another typed OOM.
A continued CUDA heartbeat/readback through both OOM windows. Both children
exited 0, and cleanup completed in 32.82 seconds.

Six independent host samples confirmed the unchanged 5 GiB sealed cap, charged
usage of 5,163,403,648 bytes at both OOM holds, more than 34 GiB physical free
memory throughout, and zero charged usage after child cleanup. Normal Stop then
returned 200, removed the Pod and released all 97 native claims. The one-hour
test token was revoked and removed locally. This establishes ordinary same-Pod
allocation aggregation only; independent Pod isolation, VMM/managed/import routes
and MPS remain unqualified.

A subsequent read-only check of all four current approval scopes using the
released workspace authorization code found only `cps:shared-gpu-lab` eligible.
Both members of CPS `native-group-a` and CIT `native-group-a` lack effective
allowance/profile grants; CPS `native-group-b` additionally has a storage lifecycle
fence. A second independent workspace requires valid grants through the normal
policy path before cross-Pod testing. No grant or storage checks were bypassed.
All four current component acknowledgments were verified ready after cleanup.

## Managed memory and private MPS qualification

The [managed-memory and MPS receipt](../../qualification-artifacts/native-managed-mps-20261017/README.md)
records a fresh normally started 5 GiB workspace. Managed allocation returned
CUDA 801/NOT_SUPPORTED; ordinary kernels passed before and after, and explicit
cleanup completed. Two actual registered private MPS clients reached aggregate
OOM at 4096 MiB held / 4352 MiB attempted, both recovered and verified kernels,
and both clients and their ordinary-user daemon exited cleanly. Nine independent
host samples confirmed the unchanged sealed cap, over 34 GiB physical free memory,
and zero charged usage after cleanup. These results do not establish cross-Pod
isolation, VMM/import paths or other profile sizes.

For the next peer test, two existing fixture grants and course memberships were
renewed temporarily by changing expiry only, with exact normal API readbacks.
Normal Start for `native-group-a` then failed before Pod creation: its legacy v1
storage path is exposed by parent NFS mounts in `jupyter-bjoern` and
`jupyter-cpsadmin`. The privacy guard correctly returned 409; an admin exception
mapping bug exposed 500 instead. The error-handling fix is published as admin source
`81b936adc75d2a992eaceecddab883fdccf1c97d`: 328 tests and 458 subtests pass,
including an actual HTTP regression and installed-wheel checks. It preserves
upstream 4xx codes with a safe error message. It is now deployed to both consoles
as image `sha256:e26ecf6fe2bfec12b08c394cdb4a46c82a1a5b46c62fc18e548c3bcd23194b97`.
A fresh authenticated CPS Start returned the expected safe storage 409, with no
Pod/server and all temporary fixture changes restored. The
[adoption receipt](../../platform-staging/jupyter-extensions-20261013/admin-storage-conflict-adoption-20261017.json)
records image-only changes, installed-image checks and backups. No
storage guard, identity, policy or approval binding was bypassed. The two personal
notebook servers remain running; permission to interrupt their kernels is pending.

Both test workspaces were stopped normally. All 98 native claims are released,
both SQL reservation tables are empty, and both fixture grants and memberships
were restored exactly to their original records through the audited APIs. The
temporary token was revoked and removed locally. All four components are ready.

## Single-process VMM cap qualification

The [trusted VMM probe and receipt](../../qualification-artifacts/native-vmm-single-20261017/README.md)
passed with full writes/readback across distinct physical allocations. Typed
cuMemCreate OOM occurred at 4,898,947,072 bytes held under the independently verified
5 GiB cap; driver charged usage was 5,333,191,360 bytes, with over 34 GiB physical
memory still free. Same-process FD alias coherence, explicit maps/handles/FD/context
cleanup, and fresh-context recovery passed. After normal Stop the Pod was absent,
all 99 native claims were released, both reservation tables were empty and the test
token was revoked. Cross-Pod and distinct-process import isolation remain open.

A related read-only privacy audit confirmed that both Hubs' notebook egress rules
permit direct NAS NFS/RPC traffic. Minimal PVC mounts alone do not prove NFS
isolation; a bounded network-policy fix is being prepared. The legacy provisioning
parent-writer check also lacks a reverse check when a broad parent CPU server
starts later. These remain production gates. A controlled TCP-only probe from
student `armin` (UID 1000) successfully connected to the NAS on port 2049; it sent
no application bytes or RPC requests. Port 111 timed out. An owned temporary file
written/synced/read/removed through the existing mounted path passed as a baseline
for the upcoming policy change; no existing user files were read or changed.
Both policy patches are prepared but not applied; live enforcement remains open.

## Previous checkpoint — packaged node renewal (16 October)

Released application source `f67224e06cd152a8c554822ddb0738685e291995` was deployed
on the isolated node as image
`ghcr.io/mul-cps/cps-native-node@sha256:5a614a6d79bac7911f98a588413126a1b181a65ed28f0e50e33f419618f7916b`.
The complete suite passed 2,819 tests and 68 subtests (six skipped). CI run
38960813947 passed all four jobs, including installed node-only and Lab checks.
The wheel rebuilt identically from its sdist. Startup completed without restart.

An independent **quiescent** live run measured 50/50 strict valid acknowledgments
over 122.5 seconds, no empty/stale samples or restarts, renewal intervals
14.73–15.00 seconds and maximum observed acknowledgment age 14.67 seconds against
the unchanged 30-second TTL. Five fresh authority/process/epoch checks passed.
All 401 original protected files and all 26 Hub-namespace Pod UIDs were preserved;
the 92 released ledger allocations retain identical data bytes. The SQL cutover
barrier made no row/schema changes. No GPU workload or driver modification was
performed during this rollout.

At that checkpoint, Gateway and both Hubs from the same source were deployed and healthy,
with unchanged Hub 5.5.2/KubeSpawner 7.1.0 and no Hub dependency upgrades. Their
version-3 proof/current approval configuration and exact new process observation
permissions are installed. All four components publish fresh acknowledgments for
approval `5517ea8f…b427`, observed less than 30 seconds old, with zero restarts.
Both actual Hub containers passed the protected qualification-reference check as
UID1000. All 24 non-Hub Pods, including four existing user servers, retain their
identities. The installed Gateway consumer's `observe()` and a separate fresh
read both passed actual process ownership, images, epoch and all four current
acknowledgments (its configured TTL is 60 seconds; the node renewal gate remains
30 seconds). Controlled active-group cadence, start/cap/stop cleanup and
end-to-end qualification are the next gates. Quiescent
success does not prove active GPU-group behavior or production readiness.

See the [peer promotion receipt](../../platform-staging/jupyter-extensions-20261013/native-peer-promotion-20261016.json).

## Active start gate — not passed

Actual normal-console tests exposed expired membership/grant records on the old
dedicated pilots, then the expected storage privacy refusal: their v1 paths are
beneath active personal-server NFS parent mounts. Temporary test records were
restored; personal servers and the privacy guard were preserved.

The existing approved `shared-gpu-lab` v2 path avoids that exposure. Its three
memberships and grants are current. Normal Start passed storage and reached Hub
native-intent registration, where the current four-component acknowledgment fence
refused the request after allocation acquisition. The active reservation/readiness
transition needs reproduction and repair before active-group qualification can
pass. Hub registration observed a gated Pod, which was removed during failure
cleanup; no GPU workload started. The released claim has no intent, confirming
the observed refusal preceded enrollment CAS. A separate CPU interleaving also
exposes the post-CAS enrollment-publication gap; fixing only the observed retry
window is insufficient for production qualification. Normal Stop returned
HTTP200; all 93 ledger
claims are released, reservations/bindings are empty, and no native Pod remains.
CIT actor testing also requires a normal akadmin login: its stored upstream OIDC
session expired; a valid Hub API token cannot bypass that refresh requirement.
Both one-hour operator tokens created for these tests were revoked and their
local credential files removed. Original test grants and memberships are restored.

Hub commit `ccdbf379b160f09fbe19f2d5cf5d55826cd7ca4f` adds an exact-response,
bounded registration retry (181 relevant tests; independent focused review and
20 tests passed). It is published source, **not deployed**, and is only a partial
mitigation. Durable post-CAS publication and normal Stop after mid-registration
revocation still need a verified protocol fix; the strict custody refusal remains.

The follow-up protocol is published in application commit
`610814a28dbccd26f47cfd99597d3479ff17daa1`. It uses an
immutable enrollment-slot barrier for a stopped attempt that never published an
enrollment, and a node-produced cleanup proof before releasing capacity. The
actual Gateway-to-node software integration now exercises Stop, proof creation,
reservation release and readiness recovery without driver writes. Independent
verification passes 2,596 tests and 49 subtests (3 skipped), including the
established-enrollment-loss regression found by the broader suite. An established
enrollment whose artifact disappears remains a hard custody failure. Three
vertical race variants cover actual SDK acquisition, a compiled same-name gated
Pod, node readiness before enrollment, registration, subsequent Stop and released
capacity. Canonical Unicode wire/provenance tests pass without changing legacy
binding hashes. Independent review cleared the protocol; node import verification
and the lean node image build pass. All three candidate images are published with
independently verified registry digests, and SDK/Hub wheels are built. CI
[38977494335](https://github.com/mul-cps/cps-compute/actions/runs/38977494335)
passed all four jobs, including installed SDK/Hub and both Lab versions.
These changes were subsequently deployed as recorded in the latest checkpoint.
The software tests do not prove live cap enforcement or hardware isolation.

See the [active start test receipt](../../platform-staging/jupyter-extensions-20261013/native-active-start-qualification-20261016.json).

See the [actual renewal adoption receipt](../../platform-staging/jupyter-extensions-20261013/native-node-renewal-adoption-20261016.json).

## Peer promotion migration preflight

The persistent Gateway approval head was registry version1/generation4
(`e9ed7284…d415`). The node's authenticated current approval is version2/generation5
(`5517ea8f…b427`). Their four complete workspace approvals and all normalized
measured facts match exactly, but the new consumer correctly refuses the old
registry transport. A direct image/configuration swap is therefore unsafe.

Application commit `a192850dfc30462804bd041fa2fcee9361eb7c64` adds an explicit
operator migration with a read-only deterministic plan, reviewed-plan hash,
both database writer locks, exact head CAS, pre/post external native-fence
checks, one append-only revision and one audit event. It neither resets the
database nor accepts old authority as current. The full suite passed 2,834 tests
and 68 subtests (six skipped); CI run38965390310 passed all four jobs. Independent
replay of all five actual immutable revision rows reached the existing node
approval and passed new-consumer startup/capture validation.

The **live migration committed** after a coordinated paired backup and rehearsal
on copies of those exact databases. Both source databases were writer-locked for
0.020 seconds during backup, with zero source row changes. Rehearsal preserved
all five historical revision rows, added one revision and audit event, and left
the reservation copy and original backups unchanged. The isolated operator then
applied the exact reviewed plan with fresh process, acknowledgment, ledger and
Pod checks under both database writer locks. An independent live read confirmed
head `5517ea8f…b427`, six revision records and audit count 2,201 (previously 2,200).

Three namespace-local immutable approval copies were created before the
Gateway/Hub workload promotion. Active-group qualification remains pending; the
running node was not recreated for peer image changes. No additional profiles
or grants were enabled by the migration or peer promotion.
See the [live migration receipt](../../platform-staging/jupyter-extensions-20261013/native-registry-migration-adoption-20261016.json).
See the [migration verification receipt](../../platform-staging/jupyter-extensions-20261013/native-registry-migration-verification-20261016.json).

## Retained notebook hardware qualification checkpoint

The current notebook531 image passed GPU2 5/20 GiB ordinary PyTorch OOM/recovery,
restart/reacquisition, bidirectional CUDA IPC and VMM/POSIX-FD isolation, and
private MPS aggregate OOM/recovery with cleanup. VMM same-parent controls passed;
both cross-parent imports returned CUDA800 with correlated kernel denials.
Unprivileged NVML quota changes returned NO_PERMISSION; managed allocation was
rejected with CUDA801; removing visibility environment variables still exposed
only the assigned GPU. This is measured scope, not full production approval.

Both QA workspaces are stopped CPU workspaces with GPU grants removed. All92
allocations are released, all82 terminal records retained, native active entries
and charged bytes are zero, and four personal Pod UIDs are unchanged. Full
Gateway/Hub/Source specs and policy/runtime/Hub Secret data were restored. Both
consoles, gateway, Hub and node agent are ready; the node progressed beyond its
first reconciliation iteration. CPU registrations were reconciled through the
normal owning-console API without changing workspace rows; its token was revoked.

Restoration exposed a32 KiB reader guard that covered the temporary policy but
not its growing baseline history. The generated reader now applies the same
256 KiB bound to every semantically valid configuration, with unchanged0400,
owner, no-symlink, link-count, policy, cap and provenance checks. A regression
reproduced the failure before the fix. The combined suite passed886 tests and880
subtests, with14 skipped. No driver, MIG or hardware settings changed.

The immediate work is released controller/policy/admin integration and the
remaining lifecycle, all-runtime/all-GPU, scheduling, recovery and release gates.
Avoid extending one-off qualification as a substitute for that integration.
See the [final current-image isolation receipt](../../platform-staging/gpu/native-group-pilot/prospective-pair/current531-final-isolation-20261016.json).
The dated sections below preserve the earlier sequence and its then-open gates;
this checkpoint supersedes their current-status claims.

## Application-owned node backend foundation

`cps-compute` commit `5c8b4de7032487cb274221235243589bf5ebe672` now packages the
injected backend, NVML adapter, exact identity discovery, Kubernetes/CRI transport
and pure Pending-gate decision in the existing SDK wheel. There are no Root
contracts, physical GPU/workspace defaults, driver loaders or manual cap scripts
in this extraction. The installed transaction core/health verifier are reused.
Per-instance gate binding replaces helper-module mutation; failed NVML
construction now closes a successfully initialized session.

The full application suite passed 2,537 tests and 68 subtests (six skipped).
A fresh lean virtualenv passed dependency checks, inert module imports and 32
backend unittest cases from the installed wheel. Wheel rebuilding from the
sdist was byte-identical. Separate CPU performance review found no added hot-path
I/O/NVML calls; Pending decisions took 12.49/12.62 microseconds in the two measured
cases. CI now exercises installed native-module imports alongside SDK imports.
[CI run 38932949445](https://github.com/mul-cps/cps-compute/actions/runs/38932949445)
passed all four jobs: build, installed SDK/Hub, and Lab 4.5.7/4.6.4. Its Python 3.12
suite passed 2,536 tests and 68 subtests, with seven skipped. Local Python 3.13
results are reported above. Both are CPU/build evidence; live adoption is open.

See [canonical application documentation](https://github.com/mul-cps/cps-compute/blob/5c8b4de7032487cb274221235243589bf5ebe672/docs/native-node-package.md)
and its [artifact/CPU verification receipt](https://github.com/mul-cps/cps-compute/blob/5c8b4de7032487cb274221235243589bf5ebe672/docs/contracts/native-node-package-verification.json).
This is application ownership and packaging, not a deployed node service.
Generic orchestration, history/custody migration,
immutable image/RBAC/GitOps adoption and live qualification of the packaged
artifacts remain open. Existing node deployments are unchanged by this commit.

## Packaged CDI reader: live read-only comparison

Application commit `84a6263d08ebff1d17f474302364225a28101898` adds explicit,
immutable CDI/runtime pins and a protected read-only observer to the SDK wheel.
The local application suite passed 2,597 tests and 68 subtests (six skipped).
The wheel rebuilt byte-identically from its source distribution and passed
installed SDK/native-module checks in a lean environment.

The installed candidate reader was compared with the deployed reader in the
existing GPU2 node agent. Both produced identical current CDI mapping, search
proof and two-GPU physical inventory. Pins came from the deployed reader's
reviewed constants, rather than candidate defaults. No GPU API, driver or
configuration change occurred. The complete allocation ledger, node Pod UID,
Deployment specification and driver epoch stayed unchanged; the owned temporary
wheel and staging directory were removed.

See the [read-only receipt](../../platform-staging/jupyter-extensions-20261013/native-node-cdi-read-qualification-20261016.json).
This validates reader compatibility, not workload isolation or node-service
adoption. Initial CI run 38935616473 failed in a coordinator test whose real
100 ms deadline expired during preparation. Runtime correctly rejected the
closed fence. Commit `80d16f6b70bd8f8e9853fab134112d3c4e97ecfb` replaces the
wall-clock sleep with manual triggering of the real deadline and explicit
cleanup completion. Runtime deadlines and safety checks are unchanged. The full
local suite again passed 2,597 tests and 68 subtests (six skipped).
[CI run 38937037169](https://github.com/mul-cps/cps-compute/actions/runs/38937037169)
passed all four jobs: build, installed SDK/Hub, and installed Lab 4.5.7/4.6.4.
Its Python 3.12 suite passed 2,596 tests and 68 subtests (seven skipped); local
Python 3.13 results are above. All three wheels and source distributions built
and rebuilt successfully. This is build/package qualification only. Generic
service orchestration, complete custody migration and
immutable deployment adoption remain the next integration gates.

## Shared authority and node configuration v3

Application commit `3be38cdae748fab133a35629567b8355bbfdef27` adds explicit
qualification authority pinned independently by trusted deployment configuration.
The gateway, Hub, capture/export, registry and approval consumers retain that
authority when reconstructing deployments. V3 permits only the measured pool,
immutable runtime image and 5/10/20 GiB profiles covered by its actual immutable
qualification object. Existing V1/V2 image/device restrictions remain unchanged.
New V3 starts require a current authenticated approval reference.

The node configuration resolves the pinned node → deployment → qualification
chain and derives resources from that deployment. It validates a terminal-index
reference but does not yet consume terminal custody or run the node service.
Those lifecycle modules are unfinished and excluded from this commit.

The exact committed source snapshot passed 2,638 tests and 68 subtests (six
skipped). Independent boundary review found no blocking issue. Installed lean
SDK/node verification passed after fixing an eager optional-Kubernetes import;
a regression now rejects that dependency during import. The wheel rebuilt
byte-identically from its source distribution, SHA-256
`d5e5bcb7ca4bdf111d483dd7c9cf31f26dc9d9adfb18d89996a42fa853f2f489`.
[CI run 38938819760](https://github.com/mul-cps/cps-compute/actions/runs/38938819760)
passed all four jobs (build, installed SDK/Hub, installed Lab 4.5.7/4.6.4).
Its Python 3.12 suite passed 2,637 tests and 68 subtests, with seven skipped.
No deployment or hardware setting changed. Complete custody,
service execution, migration and released-image live qualification remain open.

## Packaged one-iteration node service

Application commit `003e0334399dec5e696c00a57f76df7f6bb3d8cd` packages the real
node reconciliation service, complete paginated custody consumer, protected
terminal-history verifier and explicit operator bootstrap. It uses the existing
controller/journal and packaged backend rather than a substitute execution path.
A separate iteration lock prevents interleaving. Durable prior readiness is
invalidated before configuration/proof loading, including service reconstruction
and CLI startup. Released rows cannot execute; verified scope revocation targets
only the protected original Pod UID and retains capacity until confirmed stop.
Unchanged sealed lifetimes survive unrelated approval changes.

The full isolated source suite passed 2,683 tests and 68 subtests (six skipped).
Independent review found no remaining runtime blocker in this bounded unit.
A test portability correction was then retested with both actual module entry
points and no inherited source path. Installed lean SDK/node checks, dependency
checks and inert installed CLI startup passed. Wheel rebuilding from the source
distribution was byte-identical, SHA-256
`3f67f30fa1e1dd10c8b48bf068b9b43d3ecef77eb36a482b05bda83b8cc796a3`.

The integration matrix uses actual protected files, controller, journal,
process/health/CDI checks and fake API/CRI/NVML boundaries. It includes a complete
lifetime and 129 original terminal journals, enrollments, intents, completion
records and released claims over three API pages/two immutable index pages.
Missing pages, journal changes, completion replacement, changed epoch and
advanced approval block acknowledgment and further cap writes.
[CI run 38941964491](https://github.com/mul-cps/cps-compute/actions/runs/38941964491)
passed all four jobs: build, installed SDK/Hub and installed Lab 4.5.7/4.6.4.
The CI Python 3.12 suite passed 2,682 tests and 68 subtests, with seven skipped.
See the [verification receipt](../../platform-staging/jupyter-extensions-20261013/native-node-service-verification-20261016.json).

This is a one-iteration qualification service, not a production rollout.
Continuous daemon operation, actual legacy-format migration (including original
never-enrolled released claims), immutable image/RBAC/GitOps adoption and live
qualification of these artifacts remain open. No deployment, GPU or driver
setting changed in this package verification.

## Continuous qualification daemon

Application commit `333c1daa2966c558a86a60ec62fb885e11665a88` adds continuous
operation while retaining inert defaults and explicit `--execute --once`.
One service/NVML instance and bounded synchronous API client are reused. API
calls have finite connect/read timeouts and no implicit HTTP mutation retries.
Retries and waits are bounded; inability to withdraw readiness aborts the daemon
conservatively. SIGTERM/SIGINT request cooperative cancellation; shutdown
withdraws readiness and closes clients while preserving caps, journals and
reservations.

Final protected mutation guards cover the actual native setter, gate receipt
write and acknowledgment PATCH after all existing validation. Independent
reproductions confirmed late cancellation prevents each new mutation. Already
entered I/O may finish; the single-threaded daemon narrowly defers its stop
signals around that final check/operation. Validation/API reads stay outside
the native/gate mutation guard.

The isolated full suite passed 2,699 tests and 68 subtests (six skipped).
Installed lean SDK/node verification, dependency checks and inert CLI startup
passed. The wheel rebuilt byte-identically from its source distribution:
`d98f16fe677120e98e84aa4ce6916be3f0904e03ffdea7a0af9789b661fb0982`.
[CI run 38946012484](https://github.com/mul-cps/cps-compute/actions/runs/38946012484)
passed all four jobs: 2,698 tests and 68 subtests, with seven skipped; installed
SDK/Hub and JupyterLab 4.5.7/4.6.4 checks passed. No live deployment or driver
setting changed.

A separate read-only cutover audit found all 92 original ledger claims released,
including ten never-enrolled claims, and 82 terminal lifetimes across 170 labeled
authority objects. Original protected bytes remain unchanged. Actual legacy
configuration formatting, five teardown auxiliaries and missing historical
configuration causality require explicit migration support; the private v2
archive proposal has replayed these records but is not published or adopted.
Its terminal-only basis distinguishes 38 recorded approval references, ten
recorded node-configuration references and 34 unrecorded configuration origins;
unique semantic candidates do not establish historical causality. Migration
code and independent review are now complete in application commit
`754621304d088c6307c5465e757457a1e83aa80e`: the isolated full suite passed
2,725 tests and 68 subtests (six skipped), installed lean SDK/node checks passed,
and the wheel rebuilt byte-identically from its sdist. The ordinary-user offline
CLI replay verified all 82 lifetimes and 92 released claims against complete,
explicitly scoped raw Pod snapshots; missing/foreign scopes fail closed.
[CI run 38947667461](https://github.com/mul-cps/cps-compute/actions/runs/38947667461)
passed all four jobs (2,724 tests, seven skipped and 68 subtests, plus installed
SDK/Hub and both JupyterLab compatibility checks). The reviewed archive has now been published as five immutable ConfigMaps
(basis, three pages and index); the released terminal-index loader read all
82 entries through fresh API GETs and validated their actual UID/RV/data pins.
The original ledger UID, resourceVersion and raw bytes remain unchanged.
The running agent has not adopted the index. Immutable
image/RBAC/GitOps promotion and live artifact qualification remain open. This does not qualify general GPU access or production readiness.

## Packaged node image published, not adopted

Recipe commit `d449307d4dbbcda1b1ce70f2f360a4984e94d11a` builds the reviewed
application wheel from `754621304d088c6307c5465e757457a1e83aa80e` with the node
extra and exact runtime constraints. The tested qualification image is published:

`ghcr.io/mul-cps/cps-native-node@sha256:f312267e949cbac262468d6afdf27193e2e06fd14b7a4c9c325a0e80e0d37f78`

Registry inspection confirms the digest and application/wheel provenance.
The final image passed installed node imports, dependency checks and inert
startup with a read-only root, no network, no capabilities and no new privileges.
Actual builds rejected wrong wheel checksums and missing/malformed source
revisions before installation. Ten focused image/import tests passed. This image
contains no host driver tools or private configuration; deployment supplies them
explicitly. The existing node agent has not been replaced. Adoption, rollback,
restart/cancellation and real GPU isolation tests remain open.

## Cutover contract corrected; image adoption pending

Actual typed validation of the rendered v3 deployment rejected the retained
`d48f6553...511b0` catalog: policy/runtime guards derived `native-groups-v3`
from the authority schema version, while the catalog records its measured
`native-groups-v2` evidence. Deployment and approval publication stopped before
adoption. Application commit `66fb45acc3aafceb471b9e8b7d2441e61dc9246b` now requires
an explicit authenticated policy-evidence version in v3 proof data, preserving
the measured policy label across transport changes; legacy v1/v2 guards remain
unchanged. The exact isolated suite passed 2,745 tests and 68 subtests (six
skipped); installed lean SDK/node checks and byte-identical sdist rebuild passed.
The corrected image is published at
`ghcr.io/mul-cps/cps-native-node@sha256:ff65b54750d800e705295e14df85e256badb6dd04fe6dedb9f9884a64c18b224`.
A fresh corrected proof, deployment, approval and node-config chain is published
and passed all actual typed factories through live API GETs. It preserves the
original d48 policy hash, 5/10 GiB scope and measured facts; the running agent
has not adopted it. One unreferenced v3 proof ConfigMap was created before this guard;
it grants no access and is superseded by the corrected explicit proof schema.
The existing agent remains running, and the original 92-claim ledger retains
its UID, resourceVersion and raw bytes. The five-object terminal archive is
valid independently of this correction.

## Host runtime and Lab build verification

A controlled CPU-only Job on GPU2 verified all three read-only runtime file
hashes, loaded the mounted NVML library without initializing it, and executed
`crictl --version`. It mounted no GPU devices, CRI socket or API token and
requested no GPU resources. The node remained cordoned; the completed test Job
was removed. This proves loader/tool compatibility for the earlier qualification
image, not GPU isolation or the corrected image's live adoption.

Commit `419e29197a4797710935c5acd2ac4777b36e3fa7` fixes the CI build's remote
metadata fallback by building with pinned Lab 4.5.7 and the existing npm builder
4.5.11. All 446 locked dependency entries are unchanged. A fresh build with
metadata HTTP forbidden, 60 addon tests and actual installed checks on Lab
4.5.7/4.6.4 passed. CI run 38950947128 passed all four jobs: 2,744 tests and 68 subtests
(seven skipped), 60 addon tests and both installed Lab/Hub/SDK checks.

## Controlled adoption found a node-only runtime dependency defect

The old publisher was stopped and its ACK withdrawn. A UID/RV/full-data-tested,
metadata-only ledger barrier advanced resourceVersion 371886446 to 372078642;
all original state bytes and 92 released claims remain unchanged. A lock-only
SQLite BEGIN IMMEDIATE barrier observed zero reservations and rolled back with
no row/schema changes. Source writer ordering was verified from the actual
Gateway image before relying on this fence.

The replacement used the published corrected image and actual Pod/ReplicaSet/SA
identities. Its generated init loop initially missed `.items()`; the operator
artifact was corrected and its full script executed successfully on CPU before
retry. The first custody snapshot then failed because a shared validator imported
FastAPI, excluded from the node-only image. No cap mutation path was reached.
That failed candidate was stopped (replicas zero) with readiness withdrawn. Commit
`c162e5893285392c2a24a59ad0abbf1867d969e8` defers web imports until HTTP route
installation or actor checks; no web dependencies were added to the node image.
Its exact full suite passed 2,747 tests and 68 subtests (six skipped). Two actual
installed-node-only custody tests and the real 82-lifetime archive replay passed
with 30 installed distributions and no web extras; lean SDK/node checks and
byte-identical sdist rebuild passed. CI run 38955639154 completed successfully in all four jobs: 2,746 Python tests
and 68 subtests passed (seven skipped), 60 addon tests passed, and both installed
node-only snapshot tests passed. The corrected image was published and adopted
as described below. This does not qualify GPU access.

All 26 existing Hub Pod UIDs remain unchanged. A separate read-only controlled
Job verified all 401 original protected files against their recorded hashes,
owner/mode/link counts and sizes; the completed Job and temporary pins were
removed. Personal servers, original history files and driver settings were
preserved.

## Packaged node adoption and readiness gap

The node-only image `2fb00bf0a389bd4aeb5e99131eb702b2bdef859f4f4c27c47d3840c3e716ac17`
is running on the existing cordoned qualification node. Actual Pod
`cps-native-node-agent-865b7f5686-89dfc` has UID
`c812d4d8-a091-4fe6-9dc3-b81275a96c0e`; its original Deployment UID is preserved.
Real custody acknowledgments were observed for the complete retained history.
The process has one startup restart after its own Pod was not yet Ready.

Continuous readiness is **not qualified**. The service withdraws its acknowledgment
at each iteration, and completed checks were about 75 seconds apart. A read-only
actual-process snapshot measured 13.31 seconds for 82 historical lifetimes and
zero active intents: 1,077 ConfigMap GETs for 200 distinct ConfigMaps, two
ConfigMap LISTs and 184 Pod GETs. The most repeated ConfigMap was read 56 times.
A fresh observation at 19:47:42 UTC again found the acknowledgment empty while
the Pod remained Running with one restart. Snapshot-local immutable historical
read deduplication is under test; current authority, ledger, Pod and final-fence
checks must remain fresh. No cap mutation or GPU workload was run for this
measurement. Gateway and Hub consumer promotion and hardware qualification
remain open; group GPU starts remain fenced.

The bounded optimization and startup retry fix are committed and published as
`b4cfa046e51645e49288e66e98649724ff2b48a7`. The full frozen-source suite passed
2,775 tests and 68 subtests (six skipped); the wheel rebuilt identically from its
sdist. In a separate actual-process **read-only, in-memory source diagnostic**,
ConfigMap GETs fell from 1,077 to 202 (200 distinct), and elapsed snapshot time
fell from 13.31 to 8.32 seconds. All 184 Pod GETs and two inventory LISTs remained;
filesystem/API mutations were actively blocked and no driver was initialized.
This diagnostic did not deploy the new source. The qualification image
`ghcr.io/mul-cps/cps-native-node@sha256:05b052277f84789ff39be6cea38e5eef3b393c4216c5c39b2a3dc94db8557b4e`
is published and registry verified. Its installed isolated custody tests and
82-lifetime replay passed with node-only dependencies. CI run 38958413047 passed all four jobs: 2,774 Python tests and 68 subtests
(seven skipped), 60 addon tests and two installed node-only snapshot tests. Continuous acknowledgment renewal still needs a separate
safe read-only path; neither a short snapshot nor passing tests proves that gate.

## Verified deployment and recovery

Gateway `9e695015` from compute source `de90610f` is now deployed. Both Hubs
retain `e906c9ab`, JupyterHub 5.5.2, KubeSpawner 7.1.0 and chart 4.4.2. Both
separate admin consoles now run consumer `dbaad518` with Core `de90610f` and
their original separate databases. All 16 source-closure modules match in both
live Pods; both are Ready with zero restarts. Their backup images are aligned
and new matching backups passed independent checksum/SQLite integrity checks.
Policy `d48f6553` and the existing driver, NFS paths and canonical mappings remain
unchanged. The gateway deployment changed; the Hub deployments did not restart.

The gateway checks each acknowledgment against the clock after its API reads.
The approved freshness limit changed from 30 to 60 seconds: actual node
acknowledgments had exceeded 30 seconds during complete custody checks. Stale
and future acknowledgments still fail validation. Four-process readback and the
new controller journal passed. The old journal remains retained.

Normal Source Start of `shared-gpu-lab` returned HTTP 200 and Running. Its new Pod
is Ready with zero restarts, a pinned native 5 GiB hard/soft cap, one binding and
three global member reservations. The workspace-scoped admin API exposes
`interactive-shared-5` with `nativeGroupReady=true`. All 45 readiness samples
over 80 seconds passed. Five existing personal Pod UIDs, readiness and zero
restart counts were preserved. The temporary operator token was revoked.

This verifies start and cap assignment. It does **not** repeat CUDA execution,
two-browser RTC, OOM isolation, or GPU916 SDK/addon acceptance. GPU916's ordinary
SDK/addon compatibility remains an open problem. The replacement notebook531
has not completed current 5+20 GiB qualification.

The scheduled gateway backup image and `BACKUP_IMAGE` now match `9e695015`.
A pre-change backup and a new matching-image backup passed checksums and
read-only SQLite integrity checks. Their files were retained; only their owned
completed Jobs/Pods were selected for cleanup. Connected and off-host restore
qualification remain open.

See the [bounded adoption receipt](../../platform-staging/jupyter-extensions-20261013/gateway-clock-readiness-adoption-actual-20261016.json)
for immutable image identifiers, journal/plan hashes and evidence boundaries.

## Full plan status

| Area | Implemented or demonstrated | Still required |
| --- | --- | --- |
| Ownership and policy | Separate application/deployment repositories and shared policy | Integrate and promote a complete tested consumer matrix |
| Hubs and consoles | Stable baseline, two persistent consoles, local management APIs/UI | Complete current-release identity/group migration, instructor boundaries, grant expiry/login survival |
| Identity and sharing | Reviewed aliases; live retained student sessions preserve visitor identity and exact personal-server sharing | CIT Mikasa/Armin mapping, full directory coverage, removal of existing connections |
| Dynamic GPU groups | Historical bounded native R615/cgroup isolation; current 5 GiB group Start and cap assignment restored | Released integration, current 10 GiB/all GPUs/runtime variants and broader packing; no MIG |
| Shared reservations | Historical cross-Hub contention/retry; current three-member reservation | Live different-member partial-conflict rollback and full lifecycle/revocation matrix |
| Account/session APIs | All six API families, grants and pooled allowance | Effective permission/membership information and live allocation, age, idle/lifetime projection |
| SDK and notebook jobs | Actual CPS CPU success/failure, parameters, helper files, logs, executed artifacts and ownership checks | Current GPU/shared-kernel/CIT matrix |
| Hera and distributed jobs | Ordinary inline Hera DAGs/steps/scripts/containers | Referenced templates, approved resource launchers and configured 4/8-GPU JobSet execution/retry |
| Lab addon and snippets | Prebuilt packages, polling, five snippet revisions and CPS CPU GUI evidence | Complete account/session/workspace cards; GPU/CIT acceptance; demo integration into release source |
| Argo user access | Owner-filtered operations and artifact downloads | Deploy OAuth revocation fix and qualify ordinary browser authentication/revocation |
| Scheduling | Live KAI 0.18.1; interactive quota/limit 8/8, batch 0/8; planned priorities | Reconcile Fleet's older pin; GPU2 remains cordoned, six stock GPUs schedulable; teaching reclaim, protection, fairness and distributed retry |
| Startup/defragmentation | Executors and acceptance limits defined | Representative p95 ≤180s/max ≤300s bursts and required KAI/fallback comparison |
| Storage | Preserved NFS; SeaweedFS through the accepted NetBird relay; controlled retention tests | Actual new CIT NAS endpoint/export; active workload lifecycle, archives, scheduled retention and recovery |
| Monitoring | Four dashboards, Hub/KAI scrapes, Loki retention, node-local Alloy | Current rendering/promotion, physical capacity and cap/protection metrics, alert delivery |
| Recovery | Automatic backups; gateway schedule now aligned and matching backup verified | Coordinated current-version capture, connected login/spawn and populated NFS/artifact/off-host restore |
| Releases | Wheels, immutable images and compatibility tooling | Qualified pilot → RC → production tags/releases, complete notebook matrix, checksums/SBOMs and Fleet promotion |

The no-MIG enforcement pilot uses native driver/cgroup caps, rather than the
originally proposed HAMi-only enforcement path. KAI placement is not evidence of
memory isolation. Earlier measured 5/10 GiB isolation and older 5/20 GiB results
do not qualify notebook531 or the full eight-GPU service.

## Immediate remaining production work

1. Package and integrate the node lifecycle as a released application component.
   The current `cps-compute` wheel now owns the injected backend as well as
   transaction/approval modules, but its Dockerfile starts only the gateway. Its native controller documentation still
   explicitly requires qualification-only operation. The deployed node loop and
   generated compatibility overlay live here in cluster staging. Hardware
   evidence alone does not close that application/release gap. Move ownership
   without weakening gate, cap, epoch, journal or completion checks; qualify the
   packaged entrypoint against the current full retained state before adoption.
2. Replace finite policy/physical-scope patches and manual exact Pod/ReplicaSet
   RBAC refreshes with the released controller lifecycle. Introduce reviewed
   archival/migration so retained history and the allocation ledger do not reach
   their128-record limits. The current92 allocations/82 terminal records remain
   complete; do not truncate them to make a deployment pass.
3. Finish current-image10GiB/all intended GPUs and runtime variants, automatic
   MPS lifecycle, and the live workspace/reservation/revocation matrix. Current
   GPU2 5/20GiB evidence is now complete for the listed isolation probes; no-MIG
   dynamic sharing remains the selected approach.
4. Close the API/Hera/distributed gaps, adopt and qualify Argo OAuth revocation,
   then finish scheduling/scale, observability, connected/off-host recovery and
   pilot/RC/production releases against the full plan table above. Apply the
   agreed lifetime catalog through the supported policy migration, not a live
   edit that invalidates existing grants or retained provenance.

Moodle stays planned, disabled and inert, with local management active. Email
verification is optional. Direct university Keycloak awaits ICT registration;
Hub 6 remains separately staged. These are not required v1 promotions.

## Runtime-limit correction staged

Policy catalog 0.2.0 now specifies CPU batch72h, GPU batch24h, interactive CPU8h
(idle1h), shared GPU4h (idle30m), debugging GPU1h (idle15m). Generated artifacts
and policy tests agree. GPU enablement remains unchanged. The live CPS generic
culler was independently read with idle48h and no maximum-age flag, so advertised
CPU profile limits are not proof of enforcement. CIT currently uses idle24h and
max-age24h, independently read from its Hub configuration. A stable-chart culler overlay
is staged outside Fleet. Coordinated live policy/hash and enforcement promotion
is still required; the running D48 qualification scope is unchanged.

## Fresh operator membership check

The 16 October Source capture initially failed because both controlled QA
memberships had expired. Normal owning-console API updates changed only the
two expiry fields to 17:18 UTC on 16 October; all other membership records were
read back unchanged. Grants, registrations, workspaces and Pods were untouched.
The temporary administrator token was revoked (DELETE204, subsequent read403).
Fresh genuine Source application readback now resolves both canonical member
sets, verifies both stopped CPU registrations/no reservations and matches the
reviewed16-module Source531 closure. The native ledger has86 allocations, one
active; the controlled running group must be normally stopped in the coordinated
transition before a zero-charge proof or qualification handover is valid.
No current-image GPU qualification was performed by this renewal.

## Latest controlled shutdown and release baseline

The controlled shared-gpu-lab workspace is now **stopped**, superseding the
earlier Running state above. Normal Source Stop initially returned409 during
cleanup; actual Pod disappearance, native cleanup and inactive reservations were
read back before a second normal Stop returned200/stopped. Both temporary tokens
were revoked. All four personal-server Pod UIDs present at operation start were
preserved. Actual post-stop device observation shows zero active entries, zero
charge and all86 ledger claims released.

Full inventory reconciliation now checks65 finite retirements, one existing
authenticated recovery and12 explicitly pinned unattributed default rows. Those
12 complete rows were unchanged since the previous evening in the same epoch;
they cannot replace workflow evidence or admit unknown additions. The new helper
passes13 focused tests and the full pilot suite passes768 tests/851 subtests
(14 skipped). No notebook531 handover or current5+20 hardware test is claimed.
Fresh full custody collection and coordinated transition remain the next steps.

## Fresh proposal integration

Actual post-stop capture now contains86 released allocations and76 terminal
entries, including the independently retained immutable configuration references.
The Source16-module declaration matches the reviewed manifest; original serialized
capture bytes are retained separately from the verified canonical manifest.
Provisioned storage includes server/evidence metadata, which previously broke
proposal construction. The proposal now verifies the complete captured metadata
and projects only the strict seven-field native descriptor, preserving the full
registration in its target snapshot. Unknown or untyped metadata fails. All33
prospective tests pass; the real capture now produces a typed two-workspace
proposal and validates actual Gateway/CPS Hub forward artifacts.

A separate live Node mismatch was caught before apply: code is supplied by the
Node8c image, with no existing code ConfigMap volume. The earlier Node inverse
assumed such a volume. An explicit image-backed code-overlay transition and
matching inverse are therefore required before handover. No handover deployment
changes were applied; the controlled workspace remains stopped.

## Image-backed Node transition correction

The actual Node8c image-backed shape now has a separate forward/inverse planner.
It overlays only the exact Root-generated Node/epoch files as read-only mounts,
preserves the image/driver/host mounts and removes four dynamic approval argument
pairs during operator mode. Inverse tests cover zero/one/two completed lifetimes
and restore the original group bootstrap. With zero new lifetimes the complete
original image-backed spec returns. Actual image source hashes match the frozen
references. The two ConfigMap creates and Deployment patch passed server dry-run
with exact spec readback; explicit0644 avoids API-default drift. All17 focused
tests pass. No live handover or current5+20 hardware run occurred in this step.

## Source maintenance preparation

A restricted idle operator Pod is prepared on the original Source node using the
reviewed dbaad consumer and original configuration/PVC bindings. It exposes no
HTTP service and opens no SQLite provider. All16 runtime module hashes match;
the SDK exec transport is installed. Actual service-account token checks deny
Deployment patch, Pod create, Secret get and Pod exec. No RoleBindings were added.
Both admin frontends remain Ready1/1 with unchanged specs; freeze is not armed.
The new exclusive-writer verifier passes15 tests, and the full suite passes804
tests/851 subtests with14 skipped. Scoped reader permissions and genuine
application callback wiring remain necessary before pausing frontends/migrating.
The idle Pod expires after one hour; inspect live state before reuse.

## Scoped live Gateway reader

The maintenance runtime now has a Root-contract-scoped SDK registration reader.
It retains every byte of the frozen readonly logic except the exact allowed
workspace guard. A short fixed argv plus length-framed stdin avoids ingress URL
limits. UID/spec/image checks fence both sides of each read.22 focused tests
pass, including real unchanged SQLite reads and bounded websocket failures.

Actual own-token reviews permit GET of only the current Gateway Pod and its
exec subresource, while rejecting other-Pod exec, Secrets and Deployment patch.
Both actual registrations were read and match full captured Source records.
No application/provider was instantiated in the operator, neither Source
database was opened and both frontends remain active. Context/operation callback
wiring and actual freeze/handover remain next; current5+20 is still unexecuted.

## Genuine Source context factory

The pair operator now composes the genuine released CourseServiceApp loader with
fresh Source writer exclusion and the scoped Gateway reader. Forward/restoration
policy modes are explicit. Exact module closure, Root members/caps, existing
SQLite/config paths and local-only provider settings are checked. Registration
callbacks revalidate the actual freeze, and altered reader code is rejected.
Eleven focused CPU tests pass. This is implementation evidence, not a live
freeze, Source migration or notebook531 hardware result. Both frontends have not
been intentionally paused by this change; observer RBAC and live execution remain.

## Live Source context rejection and bounded grant renewal

The existing operator Pod executed the actual context factory with the reviewed
installed application closure and real Kubernetes clients. A truthful unarmed
freeze review was rejected before any provider/configuration was opened. This
proves the live unarmed-review denial, not successful acquisition of a freeze.
Both console Deployment specs remained unchanged and active.

The operator's own token now permits GET of the named CPS/CIT Deployments and
namespace Pod LIST through `cps-qa531-source-observer`. Deployment PATCH and Secret
GET remain denied. This complements the earlier exact-Gateway reader Role. These
operator-only RoleBindings must be removed with the owned runtime after the run.

The two existing dedicated operator CPU grants were renewed by expiry only via
the authenticated owning-console API, with full person grant lists read back.
They expire at2026-10-16T14:38:39.930258+00:00. Other grants remain unchanged; no GPU
profile was granted. The temporary admin token was revoked204 and reread403.
GPU qualification aliases are absent from live D48; their bounded grants belong
after the candidate policy handover. The current5+20 hardware run remains open.

## Genuine Source context positively exercised live

Both Source frontends were temporarily paused with UID/full-spec compare-and-swap
and restored automatically to their exact original specs. The first attempt
rejected valid CoreV1 PodList items because item GVK was omitted by the API.
Four regression cases now cover absent/null and conflicting type fields; the
verifier inherits only missing type from the validated enclosing v1 PodList.

The retry constructed the genuine configured application twice under the actual
exclusive writer observation and read both current Gateway registrations. Both
QA records remained stopped CPU workspaces. A4,599,808-byte SQLite backup passed
integrity and was exported to private host storage. The complete logical dump
before/after application construction was identical. Both consoles returned
Ready1/1 and all four personal server Pod UIDs remained unchanged.

Full qualification suite:841 passed,14 skipped,851 subtests passed. The live
Source loader path is now exercised; Source migration, candidate grants and
current notebook5315+20 hardware qualification remain unexecuted.

## Actual rollout boot findings and fixes

Two controlled unstarted switches exercised actual runtime boot. The first
revealed that qualification mode disabled the dynamic group runtime but retained
its capture sidecar, preventing Gateway readiness. The planner now removes only
the exact pinned capture server; the inverse restores the full original spec.
The second attempt used a real loop-progress readiness check and exposed Node
operator configuration0644 projection plus a32 KiB reader limit for56,968 bytes
of preserved history. Projection now uses0400. Only the Root-pinned pair receives
a256 KiB reader bound; other modes retain32 KiB. The real full candidate passes
the generated reader in the deployed Node image without driver calls.

Rollback was verified against complete original Node/Gateway/Hub/Source specs,
policy/runtime/Hub Secret data, ledger contents and personal Pod UIDs. All are
restored; Node progressed beyond iteration1. Exact Pod GET targets in three
control-plane Roles were refreshed after replacement. Future rollout/rollback
must refresh those bindings and restore configuration data before waiting for
restarted processes. A Kubernetes Ready count alone was too weak for Node boot.

The normal console profile-change API was exercised for both QA CPU workspaces;
all workspace records remained unchanged. This existing guarded API is the path
for the QA profile transition. The expired Source operator, its SA/helper map and
two temporary Roles/Bindings were deleted by UID; backups/PVCs remain intact.
850 tests/851 subtests pass;14 skipped. No GPU alias grants or GPU Starts occurred.
The current notebook5315+20 isolation run remains the next unfinished gate.

## Full historical enrollment compatibility

The third unstarted candidate boot exposed38 completed dynamic enrollments whose
`approval_ref` was rejected by the static qualification parser. The generated
Node now bridges only the exact Root-pinned terminal history through the frozen
approval consumer, retaining full original document/protected-mirror custody and
all completion/journal/ledger/Pod-absence checks. A read-only check on the actual
Node validated all76 records and rejected four individual tampering cases. No
driver was opened, authority written or GPU workload started. The850-test suite
plus851 subtests passes (14 skipped). The actual5/20GiB hardware run is still open.

## Current531 actual GPU5/20 Start, OOM/recovery and Stop

The normal console grant/profile APIs selected the two bounded operator aliases,
and both normal Start calls returned200. The node agent automatically sealed the
5GiB and20GiB caps. Both current531 notebook Pods ran on GPU2. Concurrent PyTorch
clients saw their exact assigned memory limits, rejected a cap+64MiB allocation
with typed `torch.OutOfMemoryError`, recovered with a verified small allocation,
and continued computing while their peer crossed OOM/recovery. Each client
touched at most128MiB; unexpected large allocations would never be touched.
Both Pod UIDs and zero restart counts survived.

Both normal Stop calls returned200. All88 allocations are released; actual node
inventory reports zero active entries and zero charged bytes. Both QA workspaces
returned to CPU and their original CPU grants. MIG current/pending remain0 and
the driver is615.71.09. Complete terminal inverse validation passed for all78
records, including physical zero witnesses and original protected raw files.
The baseline rollout completed: complete original Gateway/Hub specs and policy/runtime/Hub
Secret data are restored. Both Source consoles are ready with their original specs;
all four personal Pod UIDs survive. Node retains the exact generated compatibility
source and restored D48 configuration with the two new immutable qualification
references. It progressed through iteration2. The new Node ReplicaSet required
refreshing exact GET targets in two Roles; no other rules changed.

This closes the current-image5/20 ordinary PyTorch OOM/recovery gate. It does not
close restart/reacquisition, memory-import, MPS, or broader production gates.
Evidence hashes and limits are recorded in
`platform-staging/gpu/native-group-pilot/prospective-pair/current531-torch-isolation-20261016.json`.

## Second current531 GPU cycle: restart, CUDA IPC and MPS

Both QA workspaces restarted through the normal console APIs with fresh Pod
UIDs and native parent inodes in the same physical GPU/boot/driver epoch. Their
old lifetimes stayed retired. Automatic5/20GiB caps and concurrent PyTorch
OOM/recovery passed again. CUDA IPC same-parent positive controls succeeded;
cross-parent imports returnedCUDA_ERROR_NOT_PERMITTED in both directions with
correlated kernel denial evidence, distinct namespace PIDs and explicit cleanup.

Two MPS clients in the5GiB parent hit aggregate OOM, recovered and cleaned up
while the20GiB peer progressed. A bounded20GiB variant held19456MiB before typed
OOM and both clients recovered while the5GiB peer progressed. Its daemon scan
reportedPermissionError. Both clients exited0;32 subsequent independent root
samples showed no MPS process and zero charge in that parent. The automated
20GiB cleanup gate therefore remains open. A fail-closed PID-descriptor observer
fix and cap-forwarding probe have11 passing CPU tests; a live rerun is required.
CUDA IPC evidence does not qualify current-image cross-parent VMM/FD imports.

Both workspaces stopped through normal APIs and returned to CPU with their
original grants. All90 allocations are released; zero active entries and zero
charged bytes remain. The complete inverse retained80 terminal records. Original
Gateway/Hub specs and policy/runtime/Hub Secret data, both ready Source consoles
and all four personal Pod UIDs were restored. CPU registration reconciliation
after policy restoration uses the normal profile API; workspace rows remain
unchanged. Broad GPU access and full production qualification remain disabled.

## Third current531 cycle and completed isolation checks

The latest checkpoint and final receipt above close the earlier20GiB MPS cleanup
and VMM import gates. The restoration reader fix changes only file-size handling,
not semantic authorization. The retained terminal archive now has82 records.
The production qualification flag remains false; ordinary broad GPU rollout is
not implied by operator-only qualification.

## Concurrent process recovery and transport follow-up

During console validation, a concurrent worker reschedule replaced the Gateway
and both Hubs. All four personal notebook Pods retained their original identities.
Five exact named-GET Role updates bound the replacement processes; the installed
Gateway consumer again verifies all four acknowledgments. No workload restart or
readiness bypass was used for recovery. A Start during the service interruption
failed with ConnectionRefusedError before storage. The additional admin fix
`4d51f4e2420d9c90508cfdc19e641f73df72a706` returns safe 503 for explicit transport
failures: 331 tests and 458 subtests pass, with independent review. This transport
follow-up is now deployed to both consoles as
`sha256:1130748e6805f3f93decfe406c69eb4594d54d3588296ce46c8ecc614d6001bb`.
All 12 HTTP tests passed against the installed container image; dependency checks
and both actual deployed module hashes passed. The
[transport adoption receipt](../../platform-staging/jupyter-extensions-20261013/admin-transport-adoption-20261017.json)
records image-only changes and unchanged credentials/storage. No live service outage
was induced to validate the 503 path. All fixture originals have
been restored and the temporary validation token revoked.


### Direct notebook NFS egress repair — 17 October

Applied UID/resourceVersion/egress-guarded patches to both singleuser NetworkPolicies. Actual new TCP connections from CPS student armin and a restricted CIT diagnostic Pod reached 193.170.30.58:2049 before, and were refused after. Port 111 had already timed out before. DNS and verified public HTTPS passed after; CPS Hub TLS passed. CIT Hub resolves to private 10.21.0.50 and was refused both before and after, a separate unchanged gap. Existing mounted NFS passed an owned temporary-file write/fsync/readback/unlink after. Diagnostic Pod removed; no notebooks restarted.

Evidence: `platform-staging/jupyter-extensions-20261013/notebook-nfs-egress-live-20261017/`. CPS source e88903b (upstream a6faadee); CIT source a21ae0426e352938105e83f3c88c043ede5bbd81. Rules preserve CIT public-only access. Existing conntrack flows may survive; UDP policy coverage is source-tested, not a live positive UDP service test. Some unsolicited ICMP differs. This does not close reverse broad-parent mount exposure, cross-Pod GPU import qualification, or full production acceptance.


### Distinct-process IPC positive — 17 October

[Hardware receipt](../../qualification-artifacts/native-ipc-distinct-process-20261017/README.md): two simultaneous processes in the normally started5GiB shared-gpu-lab successfully imported/read the same allocation, executed kernels before/after, recovered and explicitly cleaned up. Exact current approved image916786 and policyd48 were checked; initial stale531preflight was corrected before GPU execution. Stop200, Podgone,100/100nativeclaimsreleased, SQLreservation/binding0, temporarytokenrevoked. This does not qualify cross-Poddenial or distinct-processVMM. A freshv2secondworkspace through normal APIs is the next safe cross-Pod path; oldv1storage cannot be silently rebound. Fullproject remains unfinished.
