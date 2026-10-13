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
| SDK, Hub and Lab packages | Separate core/Hub/Lab packages and installed Lab/RTC tests passed; both Hubs now run the reviewed Hub package image with four fresh component acknowledgments | Activate the permanent account-registry configuration and Source adapter; build and qualify all 12 notebook variants from the matched release source |
| Both admin UI consoles | Both consoles run the corrected packaged GPU-status UI; schema 7/integrity/full configuration readbacks pass; all 11 CPS live browser checks pass | CIT neutral-account adoption, actual human OAuth/API acceptance and permanent account-registry compatibility |
| Identity and group ownership | Existing reviewed aliases retained; both CPS legacy neutral accounts have permanent ready provenance and exact live group/storage readbacks; schema upgrade disabled after migration | Complete the CIT adoption and Hub package cutover; real login grant survival/expiry and scoped administration; cross-Hub allowance continuity |
| Native GPU isolation | Controlled no-MIG 5/20 GiB evidence retained; automatic revoke/approve and restart passed; normal Source-owned 5 GiB Start/Stop passed with an exact live driver cap and restored records | Pair/restart/import/MPS acceptance and broader packing; current bounded pool is 5/10 GiB, not a normal 20 GiB qualification |
| Shared GPU reservations | Shared accounting implementation and reviewed qualification bindings exist | Actual simultaneous cross-Hub starts, all-member atomicity and partial-conflict rollback; prove permitted CPU sessions and independent batch execution; release only after confirmed stop |
| Workspaces and local assignments | Local management, source-neutral reconciliation and RTC implementations exist | Two real visitors retaining their own identity, membership removal closing existing access, retained files and stopped-writer read-only archives |
| Workflow gateway and admission | Source validation/ownership paths implemented; bounded CPS own-success/failure artifact/log bytes and foreign-versus-absent rejection passed; controller admission/RBAC checks passed | CIT normal-user own/foreign access, human authentication, token renewal and crafted workflow/admin bypass scenarios on the current release |
| Notebook execution | Immutable runner/package/browser tests and bounded CPS selected-import/typed-parameter success/failure outputs passed | Complete current release/live coverage for saved snapshots, selected files, parameter cells, approved image digests and both owning Hubs |
| GPU scheduling and packing | KAI/HAMi/MPS components and controlled evidence exist | Full eight-A100 packing, teaching borrow/reclaim, protected sessions, distributed 4/8-GPU JobSet retry without orphans and genuine physical free-GPU telemetry |
| Startup and defragmentation | Acceptance executors and thresholds are defined; representative measurements pending | Pre-pulled CPS/CIT bursts: p95 <=180s and maximum <=300s; KAI/fallback comparison with free capacity >=95% and waits/start <=110% of baseline, protected sessions unaffected |
| NFS and S3 artifacts | Existing storage preserved; accepted TLS relay path and owner-filtered artifact access work; actual retention Job dry run passed | Natural 14/90-day expiry, active/retained negatives, conditional deletion/recovery and qualified scheduling; new CIT filer requires its actual endpoint/export |
| Monitoring | Four dashboards, scraping/rules and unavailable/stale handling implemented; several real targets up | Fresh complete GPU inventory, physical placement/free-capacity and cap/protection telemetry; rendered dashboards, timing data and alert notification delivery |
| Restore and recovery | Fresh CPS logical backup Job restored with the matching PostgreSQL/Hub images and identical restored row fingerprints; bounded console/gateway/artifact restores retained | Next automatic backup success, coordinated matching application/configuration capture, connected login/spawn, populated NFS/archive/artifact recovery and encrypted off-host durability |
| Moodle scaffold | Local provider, provenance migration, disabled scaffold and source tests implemented | Retain local CRUD, fake-provider reconciliation, no-network disabled behavior and clear enablement failure in the qualified release; Moodle remains planned/not deployed |
| Release train and compatibility | Candidate artifacts and compatibility tooling prepared; no unified production release declared | Complete pilot -> RC -> production gates, matched SDK/Hub/Lab/runner/notebook matrix, immutable digests, checksums/SBOMs, release notes, rollback and qualified Fleet promotion |
| Hub 6 | Separate staging scope | Keep outside production promotion until stable chart compatibility and migration/storage qualification pass |

## Current rollout boundary

The earlier controlled automatic-delivery runtime's independent readback at
**2026-10-13T20:37:45.163169Z** verified `ready=true` for Source revision
`sha256:832e841b6e7b5885a80de27e8850e8e25087b7a26a08a8270f38869f10bf71ca`
and genuine matching acknowledgments from gateway, CPS Hub, CIT Hub and node
agent. Both Hubs have since completed a guarded image handover to the reviewed
package image `sha256:bc32b73d244738c3778560a1f48e701efd10f8c57ac4834f486b3f27a30d2623`,
with unchanged policy, Source revision, GPU epoch and four fresh acknowledgments.
The controller was restarted on a separate input Secret and journal PVC;
the old immutable input and journal were preserved. The final independent
new-journal readback passed: actual completed state matches the exact new seed,
publication, live process targets and Role guards. See the retained sanitized
`hub-handover-receipt.json`; this does not activate the permanent account registry.
Source mutation initially returns `ready=false`; current process
convergence is required before a Start. This result neither enables general GPU
access nor qualifies the larger scheduling and lifecycle gates above.

Both consoles are Ready on the final reviewed Source image
`ghcr.io/mul-cps/e2x-course-hub@sha256:e720c8af11d6a7c43958108221a3154c31753694afc5b524cb06a1ffe0badb14`.
The live status API validates the gateway's `sha256:` policy-hash format. The
actual desktop/mobile browser checks passed for approved-workspace status,
owning-console profile choices, permanent account state and disabled Moodle,
with zero page errors or writes. These operator-token checks are not human OAuth
acceptance. The UI reports two approved CPS workspaces and their 5 GiB profile;
it separately reports the unavailable broader production qualification record.
Both reviewed CPS legacy account adoptions completed through the actual CLI.
The live group/marker, non-admin, stopped-server and inactive-reservation
readbacks passed, and an actual SQLite online backup verified two permanent
`ready` accounts with identity-bound `reviewed_legacy_adoption` receipts. The
remaining CIT legacy adoption is pending a real login refresh. One normal CPS
5 GiB lifecycle passed with live driver readback, confirmed shutdown and exact
restoration. The reviewed Hub package is now installed in both live images;
replacing the existing inline login guard with its released installer and
activating the permanent registry remain separate configuration gates. The
registry and Source creation adapter are published candidates and have passed
real Hub ORM tests on both PostgreSQL 15.17 and CIT's 18.4. Fresh matching logical
archives for both Hubs were verified before the planned migration. The registry
transaction is not yet deployed; new account creation remains gated. Do not
infer neutral identity from usernames, membership, email or transient discovery.

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
