# Operational acceptance — 2026-10-13

**These checks passed for their measured scopes. The full platform remains
`limited-pilot` and is not production qualified.** This record contains sanitized
results; database rows, identities, credentials, complete configuration and full
Role documents remain in private operator evidence. It supplements the
[platform acceptance requirements](../qualification.md).

## Results and remaining gates

| Check | Observed result | Scope still requiring qualification |
| --- | --- | --- |
| CPS logical backup | A newly completed Job's actual archive restored; matching PostgreSQL and Hub initialization preserved all restored row fingerprints | Next automatic scheduled success, coordinated configuration/console/NFS/artifact recovery and off-host durability |
| Artifact retention | Real cluster Job, projected-token Argo authentication and HTTPS S3 dry run passed | Natural-age expiry, conditional deletion/recovery, retained/active negatives and automatic scheduling |
| CPS/CIT console schema | Both real databases upgraded from schema 6 to 7; every preexisting table's exact rows preserved; automatic upgrades disabled afterward | Reviewed neutral-account adoption and subsequent Hub/group ownership cutover |
| Approval transport | Trusted TLS and independent export-token checks passed; 17 actual API admission/RBAC checks passed | Broader deployment and credential-rotation qualification |
| Automatic approval delivery | Actual Source revoke converged to all four independently observed acknowledgments; subsequent approve and fresh controller restart resumed automatically | Normal workspace Start/Stop after account cutover and broader GPU/scheduling acceptance |

## Actual CPS logical backup and restore

The operator removed only the unnecessary required database-Pod affinity from
the existing CPS backup CronJob. The database Pod was on a cordoned GPU node;
logical backup connects through its Service and does not need that placement.
The backup PVC, existing data, historical Jobs and the node's cordon were preserved.

Job `jupyterhub/cps-hub-backup-acceptance-ca21fe`, UID
`6c98ccf1-8e04-4574-a174-91ac9e9428a9`, completed on GPU1 during
`2026-10-13T19:39:13Z`–`19:39:33Z`. The archive selected from that exact Job window
was 64,441 bytes, SHA-256
`d668f143e0c7234bef19feac8506042362364a2b961d1ea46aa42c0d2dbde828`.
Its PostgreSQL custom-format signature, remote/local checksum, manifest checksum,
archive listing and matching client version passed.

Restore used the exact PostgreSQL **15.17** image
`docker.io/library/postgres@sha256:866264fb97643e747f9d0981cd060114f83b49450e5bac4988324bb3c6af2fd7`,
with `pg_restore --exit-on-error --no-owner --no-acl`. An isolated helper using
the exact live **JupyterHub 5.5.2** image
`ghcr.io/mul-cps/cps-compute@sha256:c22c7460ae3ddc3cac454a7f0fac41fc7308e4601e06162b91ca7af7ba301233`
completed `JupyterHub.init_db()` with `reset_db=False` and `upgrade_db=False`.
Every restored table's row fingerprint and schema revision `4621fec11365` were
identical before and after Hub initialization.

Local fixtures had no production credentials, host ports or production volumes;
the PostgreSQL fixture used `--network=none`, bounded resources and tmpfs storage.
The sole cluster exporter mounted the backup PVC read-only, had no service-account
token and used UID/GID 1000, dropped capabilities and a read-only root filesystem.
Both fixtures and the exporter were removed, with actual exporter UID/precondition
cleanup and disappearance verified.

The deployed archive has the legacy six-field manifest, whose stated scope is a
logical Hub database backup excluding roles, ACLs, configuration, NFS and off-host
durability. This test does not assert deployment of the richer source-chart
manifest, compare restored rows with a separately captured live database, or
prove connected OAuth/spawning. A manually created Job does not advance the
CronJob's `lastSuccessfulTime`; observe the next daily automatic run separately.

## Actual retention dry run

An exact-current-template Job completed on GPU1 during
`2026-10-13T19:56:54Z`–`19:57:25Z` after correction of a stale policy hash and
configuration of an existing, UID-bound Succeeded workflow probe. The template
kept deadline 300 seconds, backoff 0 and an examination bound of 1,000. Its
immutable runner was
`ghcr.io/mul-cps/cps-compute@sha256:7a9caff2fe4874adad523dd2be3fc6dcb00930b7dc4d3ddbc2f3141de20d15ea`.

The real projected ServiceAccount token authenticated to Argo over verified
HTTPS. The unmodified packaged controller accessed the current HTTPS S3 endpoint:
**44 examined, 44 skipped, 0 eligible, 0 errors, 0 deleted, 0 reconciled,
`apply=false`, `truncated=false`.** The live mounted controller matched source
SHA-256 `9cadec1f0229222f34923b18f456a0506ae5e92826ea78ab7e791e1e72e73542`;
the current config SHA-256 was
`0464f6c023ec0f9614e15e6ce620b71011e9b5d63a96e68f29b64c19c2b9694c`.
Policy was
`sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0`.

The owned completed Job and Pod were deleted with their actual UID preconditions;
fresh reads confirmed them absent. The original CronJob UID
`cbb1c416-4c05-43f2-bf74-ec8cc6ac30ce` and resourceVersion stayed unchanged and
**`spec.suspend` remains true**. Apply, reconciliation, lifecycle and conditional
delete qualification flags remain false. Zero eligible objects does not exercise
the 14/90-day expiry or deletion path. This result does not authorize unsuspension
or application of deletion policy.

## Console schema and packaged UI

Both consoles now use the reviewed immutable image
`ghcr.io/mul-cps/e2x-course-hub@sha256:65927f27b7f81fcc4c7b34e509d21213e9691df33eaf4a4b137fa46f8b8c3e3c`.
Consistent live SQLite backups preceded the explicitly enabled schema migration.
Both upgraded databases passed integrity checking, report schema **7**, and added
`workspace_accounts`. Exact row comparison with those backups passed for every
preexisting table:

| Preexisting table | CPS rows before/after | CIT rows before/after | Exact rows preserved |
| --- | ---: | ---: | --- |
| `audit` | 633 / 633 | 341 / 341 | Yes |
| `console_owner` | 1 / 1 | 1 / 1 | Yes |
| `email_links` | 0 / 0 | 0 / 0 | Yes |
| `records` | 11 / 11 | 6 / 6 | Yes |
| `reviewed_account_aliases` | 5 / 5 | 2 / 2 | Yes |

After this controlled migration, `allow_console_schema_upgrade` was returned to
**false** and both consoles restarted. No reviewed account adoption has yet been
executed; legacy neutral owners and workspace associations remain unchanged.
The new adoption API requires an actual owning Hub administrator of `kind=user`,
a reviewed exact plan, confirmed stopped writers and durable provenance. A
same-name service principal does not qualify as that administrator.

The CPS public `main.js` returned HTTP **200** with 437,600 bytes and expected
SHA-256 `cfc5cdcbccd96bf4f3c4ff6fddbe940a39e090934a987def43a91300568d9875`.
This proves delivery of the packaged bytes; it is not a real-user browser or
account-adoption acceptance test. CIT public UI delivery is a separate check.

## Protected transport and automatic delivery

The protected capture sidecar uses
`ghcr.io/mul-cps/cps-compute@sha256:042b8b60c0bbdfd2c4506ddf8007677016ef5d278ad5720d7d6b7ac41d136b1b`.
Its independently authenticated TLS endpoint has no public ingress and is
network-policy restricted to the namespaced delivery controller. Source capture
is read-only; its separate epoch observation requires the current node process
and acknowledgment. Export credentials are distinct from administrative Hub and
Source credentials and copied to owned mode-0600 runtime inputs.

Actual trusted-CA HTTPS probes returned `200` for capture and epoch with
`Cache-Control: no-store`, `401` without authentication or with a wrong token,
`400` for a query and `404` for an unknown path. These probes used the packaged
Python 3.12 runtime. They do not establish Python 3.13 strict certificate
compatibility; the existing certificate's missing Authority Key Identifier
caused that separate probe to fail without weakening TLS verification.

At `19:38:05Z`, **17 checks passed** against the real API server using a dedicated
controller credential. Admission accepted only the bounded immutable
content-addressed document shape and allowed Role target changes; it rejected
foreign names, mutability, foreign/binary data, owner references, additional
verbs/rules and foreign GET names. RBAC denied Secret listing, Pod exec creation,
RoleBinding creation, ConfigMap/Deployment listing and acknowledgment mutation.
Created references, retained documents, Deployment targets and Role updates are
bound to observed UIDs and exact compare-and-swap preimages. No root credential
is supplied to the controller and it cannot manufacture acknowledgments.

The existing Source client performed an actual revoke and subsequent approve
while the target workspace was stopped, without a reservation or attempt. This
was a configured-client operator exercise; **`human_oauth=false`**, not a browser
authentication claim. The actual revisions were:

| Transition | Source revision |
| --- | --- |
| Initial | `sha256:0ebca4cc37cf1cddb156d3d9efd2f6fe3e051270e86cfa1930cc754def58e294` |
| Revoke | `sha256:3c2f1f8c8e14de512b37e426da5679eb88c890a7ade15f73e8416153c70bcbb8` |
| Approve | `sha256:832e841b6e7b5885a80de27e8850e8e25087b7a26a08a8270f38869f10bf71ca` |

A strict independent read at **20:29:03.530844Z** confirmed `ready=true` for the
revoke revision and actual matching acknowledgments from **gateway, CPS Hub,
CIT Hub and node agent**. Publication includes new immutable documents and
references, guarded permission updates and complete Deployment targets. Source
mutation initially returns `ready=false`; convergence and current process
acknowledgments establish readiness afterward.

The rollover exposed a bootstrap deadlock: the new node process required GET
permission for its own Pod before it could acknowledge startup, while the delivery
controller required the fresh epoch before updating that permission. The reviewed
fix resumes only process GET permissions from a complete, UID-bound durable
transition and verified target processes. It returns `ready=false` until a fresh
epoch and all four genuine acknowledgments pass. It does not reuse a stale epoch,
create missing retained documents, broaden Role rules or run GPU work.

The controlled live controller now uses
`ghcr.io/mul-cps/cps-compute@sha256:9cd73355e7f46e586516daf4e2c982a841f865c51c511de740fc45c67d5baaac`,
one replica and its original dedicated journal PVC. A fresh Recreate startup
with the reviewed private-input/journal initialization resumed the approve
revision automatically and reported `ready=true`. Actual owned UID 1000 journal
directory mode **0700**, state mode **0600** and lock mode **0600** were verified;
no root chmod was needed after that restart. Independent strict readback at
**20:37:45.163169Z** confirmed the final approve revision, `ready=true`, all four
genuine matching acknowledgments and the actual four current processes.

The source manifest's default controller replica count remains **0**; the
explicitly controlled runtime has **1**. This operational exercise does not
activate general GPU access, change MIG or the driver, qualify full eight-GPU
packing, or enable production Fleet promotion. Normal workspace lifecycle after
reviewed account adoption, broader cross-Hub fairness, isolation, startup bursts
and scheduling gates remain required by the main acceptance plan.

## Evidence custody

Private operator receipts and exact bytes are retained outside Git with restricted
directory/file modes. Useful non-identifying receipt fingerprints are:

| Receipt | SHA-256 |
| --- | --- |
| Actual backup/restore sanitized receipt | `0ca6b6de2890feebf074e15967f324d4c664b5e6882c4323e0167d494cadc9cd` |
| Retention actual Job log | `74064fb59c15fc2e06f5d350a688efe3906da2a16de421c259300a762eefc31a` |
| Strict four-component revoke readback | `65db3082fe58ca038e3585121d1679c8304b558a664ee285cd18ed6ebd91d122` |
| Strict four-component final approve readback | `0290cda61b595d742ca878d40969e40017f6c1ec4dab79e9fb29cf0cdab0ae2f` |
| Fresh private-journal init Deployment readback | `8da7a8197057dcb6209090f59ee3358a9f3c6ed80ce79e45ecae0735b1130497` |

This document records actual results and their limits. It creates no release tag,
publication approval, production qualification assertion or deployment mutation.
