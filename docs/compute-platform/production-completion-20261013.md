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
| SDK, Hub and Lab packages | Both Hubs run Hub466 with the permanent registry installed, migration disabled and four fresh acknowledgments; core/Hub/Lab packages and all 12 local notebook OCI builds passed | Complete normal new-account lifecycle, immutable notebook publication and one promoted consumer matrix |
| Both admin UI consoles | Both consoles run Source9698 with neutral creation and concurrent Start fixes; all preexisting rows and complete configuration preserved; unchanged UI assets previously passed 11 CPS browser checks | New-account HTTP lifecycle, CIT adoption and actual human OAuth/API acceptance |
| Identity and group ownership | Existing reviewed aliases retained; both CPS legacy neutral accounts have permanent ready provenance; both owning Hub registries are installed with explicit scoped service creation | Complete CIT adoption, real login grant survival/expiry and scoped administration; cross-Hub allowance continuity |
| Native GPU isolation | Controlled no-MIG 5/20 GiB history retained; current CPS pair passed distinct 5 GiB OOM/recovery with peer progress, IPC denial in both directions, positive controls, kernel witnesses, restart retirement and confirmed normal closure | MPS, complete restart behavior and broader packing; current bounded pool is 5/10 GiB, not a normal 20 GiB or cross-Hub qualification |
| Shared GPU reservations | Shared accounting implementation and reviewed qualification bindings exist | Actual simultaneous cross-Hub starts, all-member atomicity and partial-conflict rollback; prove permitted CPU sessions and independent batch execution; release only after confirmed stop |
| Workspaces and local assignments | Local management, source-neutral reconciliation and RTC implementations exist | Two real visitors retaining their own identity, membership removal closing existing access, retained files and stopped-writer read-only archives |
| Workflow gateway and admission | Source validation/ownership paths implemented; bounded CPS own-success/failure artifact/log bytes and foreign-versus-absent rejection passed; controller admission/RBAC checks passed | CIT normal-user own/foreign access, human authentication, token renewal and crafted workflow/admin bypass scenarios on the current release |
| Notebook execution | Immutable runner/package/browser tests and bounded CPS selected-import/typed-parameter success/failure outputs passed | Complete current release/live coverage for saved snapshots, selected files, parameter cells, approved image digests and both owning Hubs |
| GPU scheduling and packing | Stock KAI/HAMi components and controlled evidence exist; pending native-allocation compiler contracts passed installed-package tests | Protected coordinator, terminal binder and post-Bind cap/CDI integration; eight-A100 packing, teaching reclaim, protected sessions, 4/8-GPU JobSet retry and physical free-GPU telemetry |
| Startup and defragmentation | Acceptance executors and thresholds are defined; representative measurements pending | Pre-pulled CPS/CIT bursts: p95 <=180s and maximum <=300s; KAI/fallback comparison with free capacity >=95% and waits/start <=110% of baseline, protected sessions unaffected |
| NFS and S3 artifacts | Existing storage preserved; accepted TLS relay path and owner-filtered artifact access work; actual retention Job dry run passed | Owned-object 14/90-day policy expiry using a bounded test clock, active/retained negatives, conditional deletion/recovery and scheduling; new CIT filer requires its actual endpoint/export |
| Monitoring | Four dashboards, scraping/rules and unavailable/stale handling implemented; several real targets up | Fresh complete GPU inventory, physical placement/free-capacity and cap/protection telemetry; rendered dashboards, timing data and alert notification delivery |
| Restore and recovery | Fresh CPS logical backup Job restored with the matching PostgreSQL/Hub images and identical restored row fingerprints; bounded console/gateway/artifact restores retained | Next automatic backup success, coordinated matching application/configuration capture, connected login/spawn, populated NFS/archive/artifact recovery and encrypted off-host durability |
| Moodle scaffold | Local provider, provenance migration, disabled scaffold and source tests implemented | Retain local CRUD, fake-provider reconciliation, no-network disabled behavior and clear enablement failure in the qualified release; Moodle remains planned/not deployed |
| Release train and compatibility | Candidate artifacts and compatibility tooling prepared; no unified production release declared | Complete pilot -> RC -> production gates, matched SDK/Hub/Lab/runner/notebook matrix, immutable digests, checksums/SBOMs, release notes, rollback and qualified Fleet promotion |
| Hub 6 | Separate staging scope | Keep outside production promotion until stable chart compatibility and migration/storage qualification pass |

## Current rollout boundary

Both live Hubs now run the reviewed package image
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
restricted group; its inherited `self` privilege needs removal. These are
concrete package/custody defects under repair, not GPU or network failures.
The new identity and all owned records remain preserved for guarded retry.

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

The matched core and Lab extensions built and passed runtime checks in **all
12 local notebook OCI variants**. Installed discovery/uninstall/reinstall,
Hera/RTC, UID 1000 and pinned inherited image/package provenance were checked.
Their images are not yet published or promoted. The separate pending KAI
allocation compiler contracts passed **1,957 source tests** (3 existing fixture
skips) and **171 installed-wheel tests**; these contracts do not themselves
install a protected coordinator, binder transport or post-Bind native cap gate.

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
