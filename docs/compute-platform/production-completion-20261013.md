# CPS/CIT production completion

This ledger carries the original platform plan through deployment and measured
acceptance. Passing source tests, published candidates and production acceptance
are separate states. Existing qualified evidence is retained unless a relevant
change invalidates it.

## Binding requirements

- Separate CPS/CIT consoles and databases; shared policy and person allowance.
- Preserve usernames, homes, research data, local grants and dirty checkouts.
- Dynamic GPU sharing without MIG. Run GPU acceptance only with trusted probes.
- Authoritative identity mapping; no linkage inferred from matching usernames.
- Retain Authentik/Dex. University OAuth registration stays externally deferred.
- Local courses active; Moodle visibly planned, disabled and inert.
- NFS addresses remain unchanged; S3 uses the accepted NetBird relay path.
- Protect existing workloads; confirmed shutdown precedes reservation release.
- Promote immutable qualified artifacts and retain matching backups/rollback.

## Acceptance ledger

| Gate | Current state | Required completion evidence |
|---|---|---|
| Repository ownership and shared policy | Implemented; reconcile branches | One integration revision, policy hash and tested consumers |
| SDK, Hub and Lab packages | Source/install/browser tests passed | Promote exact Hub/notebook artifacts; installed live checks |
| Both admin UI consoles | Live; verified 2026-10-13 | Retain API/auth and backend compatibility |
| Identity and group ownership | Existing mapping; audit in progress | Storage continuity, login grant survival, expiry, scoped admin checks |
| Native GPU isolation | Controlled 5/20 GiB evidence passed | Automatic approval/cap delivery, restart/import/MPS and current runtime acceptance |
| Shared GPU reservations | Implementation exists; live acceptance pending | Simultaneous cross-Hub starts, all-member atomicity, conflict rollback, confirmed stop |
| Workspaces and local assignments | Implemented; acceptance audit | Two visitor identities, RTC, removal access closure, read-only archive |
| Workflow gateway and admission | Implemented; acceptance audit | Crafted bypass rejection, own-only logs/artifacts/termination, idempotency |
| Notebook execution | Package/browser tests passed; live audit | Immutable snapshot, selected imports, typed parameters, success/failure outputs |
| GPU scheduling and packing | Deployed components; unqualified broader use | Borrow/reclaim, protected sessions, distributed retry, physical free-GPU telemetry |
| Startup and defragmentation | Pending measured load gate | Pre-pulled CPS/CIT p95 <=180s, max <=300s; fallback comparison |
| NFS and S3 artifacts | Existing storage; relay accepted | Ownership, active-input retention, 14/90-day rules; maintenance runbook |
| Monitoring | Implemented; live audit | Four dashboards, fresh scrape targets, physical/VRAM/utilization distinction |
| Restore and recovery | Existing controlled evidence; audit | Matching Hub/console versions, NFS/archive and artifact checks |
| Moodle scaffold | Implemented; audit | Local CRUD/provenance/fake-provider tests; disabled inert; enable fails clearly |
| Release train and compatibility | Prepared; production not qualified | Pilot -> RC -> production gates, immutable artifacts, notes, checksums, rollback |
| Hub 6 | Independent staging work | Remains outside production promotion pending stable compatibility qualification |

## Execution record

- 2026-10-13: Fresh read-only access confirmed. Both admin deployments are Ready
  with image `sha256:72cb8b044e8e091d038c8c8f4cf983c433629733847db879667c0c51bd2f7411`.
- GPU automation, Hub ownership/package migration and remaining operational
  acceptance are audited independently; the root agent owns live mutations.
- No production release or broad GPU entitlement is declared by this ledger.
