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
| CPS/CIT console schema and UI | Both real databases upgraded from schema 6 to 7 without changing preexisting rows; automatic upgrades disabled; both public UI bundles returned 200 with exact packaged bytes; both CPS legacy adoptions have permanent ready provenance | CIT adoption, real user OAuth and subsequent packaged Hub cutover |
| Approval transport | Trusted TLS and independent export-token checks passed; 17 actual API admission/RBAC checks passed | Broader deployment and credential-rotation qualification |
| Automatic approval delivery | Actual revoke and approve converged to four genuine current acknowledgments; fresh controller restart resumed with its original durable journal | Normal workspace Start/Stop after account cutover and broader GPU/scheduling acceptance |
| Packaged Hub login guard | Reviewed immutable image published; installed tests keep registered neutral identities blocked after group/marker revocation | Qualified live software handover, existing-account cutover and enforced registry publication before any new Source-created account |

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

The controlled schema migration used the reviewed immutable image
`ghcr.io/mul-cps/e2x-course-hub@sha256:65927f27b7f81fcc4c7b34e509d21213e9691df33eaf4a4b137fa46f8b8c3e3c`.
Subsequent Source image replacement is a separate rollout and does not relabel
this migration receipt. Consistent live SQLite backups preceded the explicitly
enabled schema migration.
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
**false** and both consoles restarted. The final reviewed Source implementation,
commit `a35ec33526b2f5082b4fd652a00b6472e89086f6`, was subsequently promoted to
both consoles; both are Ready on
`ghcr.io/mul-cps/e2x-course-hub@sha256:8b718d5e789f901b4be7a0b2c48afb875031dc350c1595c3d3f556dc9a8b64b7`.
It binds the gateway principal to the workspace identifier and checks the
separate neutral owner without rewriting registration or storage descriptors.

Both existing CPS neutral accounts were adopted through actual CLI plan and
execute requests after review of the exact pre-upgrade course, term, group and
workspace records, source binding, raw storage and stopped-owner preimages.
Actual Hub readbacks confirmed fixed-group membership, the zero-scope marker,
non-admin status and stopped servers. Reservations were inactive, no attempts
remained, and original identifiers/storage associations were preserved.

An actual consistent SQLite online backup afterward passed integrity checking
and schema **7** verification. It contained **two permanent ready accounts** with
identity-bound `reviewed_legacy_adoption` receipts; backup SHA-256 was
`7efeb4f309300320cc1652651ff657612b3894726b3f905b46385c25b5990387`.
The third legacy account, owned by CIT, is not adopted yet. These were
operator-controlled requests using owning Hub user tokens, **`human_oauth=false`**;
no complete cross-Hub cutover or normal Start/Stop acceptance is asserted yet.
The adoption API requires an actual owning Hub administrator of `kind=user`,
a reviewed exact plan, confirmed stopped writers and durable provenance. A
same-name service principal does not qualify as that administrator.

The CPS **and CIT** public `main.js` each returned HTTP **200** with 437,600
bytes and expected SHA-256
`cfc5cdcbccd96bf4f3c4ff6fddbe940a39e090934a987def43a91300568d9875`.
This proves delivery of the packaged bytes; it is not a real-user browser or
account-adoption acceptance test. The CIT administrator's upstream Dex session
was expired: the Hub rejected even a newly issued API token until a real login
refresh. Operator-issued tokens do not refresh upstream authentication and are
not recorded as human OAuth acceptance.

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
reviewed account adoption is recorded below. Broader cross-Hub fairness, isolation, startup bursts
and scheduling gates remain required by the main acceptance plan.

## Normal Source-owned 5 GiB lifecycle

After both CPS reviewed adoptions, the actual configured Source service started
the approved 5 GiB workspace through its normal Start operation. It reached Hub
Ready in **113.0506 seconds**, held the all-member reservation, exposed exactly
one native group Share and preserved its registered storage binding. While it
was Ready, an independent operator read bound the actual Pod UID to the sealed
node journal and the protected driver inventory: soft and hard limits were both
**5,368,709,120 bytes** on the selected physical GPU, with an online, pinned Pod
parent cgroup. This was automatic cap assignment; MIG and driver settings were
unchanged.

Normal Stop confirmed server shutdown, native cleanup and reservation release;
Shares were empty afterward. The terminal journal state was
`retired-inert-cap`, not a physical free-GPU measurement. Existing membership and
grant windows were temporarily refreshed without adding profiles or allowance,
then restored byte-for-byte through audited APIs. The previous Hub group
membership was also restored. The retained Source result SHA-256 is
`c358e039ea14b1052571042971fce904ac3639a3e7d375022a38aeac46bc7115`.
This is one configured-client lifecycle exercise (`human_oauth=false`), not a
representative burst, two-visitor, peer-isolation or production-packing result.

Live standalone browser acceptance then verified the deployed CPS forms offer
the approved 5 GiB GPU profile, exclude unapproved 10 GiB and unqualified 20 GiB
choices, and show both permanent account receipts as ready. All 25 requests
returned 200, with no writes, foreign requests or browser errors. Nine of eleven
assertions passed; two exposed one misleading qualification-status card whose
missing operator report was presented as unavailable GPU access. That UI fix
and its new live verification remain pending. Browser authentication used an
operator-issued user token and does not establish human OAuth acceptance.

## Historical Hub package publication before cutover

The reviewed login guard is published as
`ghcr.io/mul-cps/cps-compute@sha256:bc32b73d244738c3778560a1f48e701efd10f8c57ac4834f486b3f27a30d2623`.
Its exact Hub wheel is SHA-256
`e99e27dc9e1010ebbcc8a4587b95ea4fff847354781b02cd69d09d5aba1575ed`,
from source commit `74bf8aea9323ef24e4d0d99e7e3ce643bb74899a`.
Actual read-only, network-disabled image checks passed on JupyterHub 5.5.2 and
OAuthenticator 17.4.0. The overlay preserved the other 136 distributions and
29,272 dependency-file hashes, the core SDK and the runtime configuration.

The permanent reviewed neutral-owner registry denies interactive OAuth even
after group or marker removal. Temporary legacy marker refresh is a separate
subset that can be retired without losing that denial. Startup rejects marked
neutral accounts missing permanent records; runtime discoveries are deny-only
and cannot replace durable provenance. The bounded existing-owner review passed
34 installed guard cases, with 1,730 SDK/Hub tests passing and 3 skipped.

At this historical checkpoint, this image was **published, not yet deployed**. A qualified operator software
handover must bind the exact existing Source revision, complete Deployment/Role
preimages, retained document/reference identities and fresh real process
acknowledgments; a Source update or a manually edited journal is not a substitute.
The old journal and its custody must be preserved.

The guard does not implement Source's permanent-registry publication/creation
transaction. New account creation remains gated until every neutral identity is
published durably and accepted by its owning Hub before the Hub user is created.
The existing-account adoption and generic account-creation gates are separate.
No broader production, normal 20 GiB workspace, full eight-GPU packing, startup
burst, defragmentation, two-visitor or coordinated recovery claim follows from
these package tests.

## Evidence custody

Private operator receipts and exact bytes are retained outside Git with restricted
directory/file modes. The original strict revoke-readback path was overwritten by
the later final readback; it is not listed as a retained independent receipt.
The recorded 20:29 revoke observation is supported by the subsequent configured
Source approve capture, whose preimage still reports the revoke revision ready.
The strict current four-component Source2 readback is retained. Useful
non-identifying receipt fingerprints are:

| Receipt | SHA-256 |
| --- | --- |
| Actual backup/restore sanitized receipt | `0ca6b6de2890feebf074e15967f324d4c664b5e6882c4323e0167d494cadc9cd` |
| Retention actual Job log | `74064fb59c15fc2e06f5d350a688efe3906da2a16de421c259300a762eefc31a` |
| Configured Source approve capture, including prior revoke readiness | `2d97245835034ee147b4b459160ed68bcb4187ba304640362f0f4c16add8be40` |
| Strict four-component final approve readback | `0290cda61b595d742ca878d40969e40017f6c1ec4dab79e9fb29cf0cdab0ae2f` |
| Both CPS permanent reviewed adoption accounts | `66c88f0372e3f8e22f686dde6fb798029361ff2459eb10bfdfc683263703aa4a` |
| First CPS stopped-account live adoption receipt | `002975e3c0ca30eec8e33b43a1d1d6fcd9c1b4eeca6dc6032b7cc5e5045eb2ef` |
| Second CPS stopped-account live adoption receipt | `bf06e98ca89bd071bdbd058c9b12b490b7e98bafb26515bb12e526936f5e6b91` |
| CPS public UI byte receipt | `183263bbce10f17ec5e0eb8132eb8ea031226b4e76629f8dc649ae3cc2f2332a` |
| CIT public UI byte receipt | `f13dca4d99daaef84b1a43598b76f7c658b127d1ea01d19fe50564ccb322fe66` |
| CPS exact schema-7 preservation receipt | `c396e3342d26fec4eb3a04c24820db83f851532bfcde98d02812082706be89d2` |
| CIT exact schema-7 preservation receipt | `ff3fcfbced0d6b977f8f5994eab300e1c487515dcddfcbca09a910f0651105cc` |
| Fresh private-journal init Deployment readback | `8da7a8197057dcb6209090f59ee3358a9f3c6ed80ce79e45ecae0735b1130497` |

This document records actual results and their limits. It creates no release tag,
publication approval, production qualification assertion or deployment mutation.


## Corrected GPU-status UI and matching pre-registry backups

Both consoles subsequently completed guarded image-only rollouts to Source
commit `55585c0de5631610bb840f138696b476ed1bbb6e`, image
`ghcr.io/mul-cps/e2x-course-hub@sha256:e720c8af11d6a7c43958108221a3154c31753694afc5b524cb06a1ffe0badb14`.
Actual Ready Pod imageIDs and complete applied Deployment specifications matched.
Both SQLite databases remain at schema 7 with integrity `ok`, and automatic
schema upgrades remain disabled. The package has 277 passing Python tests and
57 passing UI tests. Actual gateway responses use a `sha256:`-prefixed policy
hash; the corrected UI and backend validate that exact format.

All **11** standalone CPS browser checks passed with zero page errors, blocked
requests or writes. They exercised the actual app, separate approval/production
status, Source-scoped GPU registry, permanent account status, approved 5 GiB
grant/form choices, both existing workspace Start availability, planned Moodle
and mobile viewport fit. The owning operator-issued user API token is not a
human OAuth session. The two approved CPS workspaces are available; an absent
broader qualification report remains explicitly unknown. Historical rollout
receipts are preserved; the latest image overlay is paired with
`platform-staging/jupyter-extensions-20261013/live-status-receipt.json`.

Before the separately planned permanent Hub account-registry migration, fresh
matching-client logical backup Jobs completed during **22:10:45Z–22:10:59Z**:

| Owner | PostgreSQL | Job UID | Archive bytes | Archive SHA-256 |
| --- | --- | --- | ---: | --- |
| CPS | 15.17 (Debian 15.17-1.pgdg13+1) | `a0ff1669-b6d6-4795-a2df-8678937fd639` | 65,343 | `30cc26e0ff007128804b2cd52fdf6e9b413d122444f80da70f7330cd97478458` |
| CIT | 18.4 | `fdc2bd79-0f76-40b2-8871-83d65607dc4b` | 167,018 | `b0ec27bb9f89354a5a5e37a29f82966ec71d1a9910a759619ac7fb98c0b3c23c` |

Each exact-current CronJob clone used the same immutable image as its owning
live database. Complete Job/Pod ownership, unchanged template/configuration/PVC,
PGDMP signature, the legacy six-field manifest, remote/local/archive checksums
and matching-image `pg_restore --list` passed. The selected bundle was the sole
complete bundle in its actual Job window. Read-only exporters ran without
ServiceAccount tokens; exact UID-precondition deletion and disappearance passed.
Archives and full custody receipts remain private. These are matching logical
migration backups, not a claim of coordinated restored production service,
roles/ACL preservation, NFS/configuration capture or off-host durability.

The reviewed permanent registry also passed 34 real Hub ORM tests against an
isolated exact PostgreSQL **18.4** server, in addition to its PostgreSQL 15.17
qualification. At this historical checkpoint the registry/Source creation adapter remained
published candidates. The later guarded activation is recorded below.


## Qualified Hub image and automatic-delivery handover

Both live Hubs completed the first reviewed package handover to
`ghcr.io/mul-cps/cps-compute@sha256:bc32b73d244738c3778560a1f48e701efd10f8c57ac4834f486b3f27a30d2623`.
The guarded handover preserved policy, Source revision and the physical GPU's
boot/driver epoch, updated only the closed image/bootstrap/runtime trust inputs,
and read back four genuine matching component acknowledgments. Gateway runtime
Hub-image pins were verified from actual mounted inputs.

Automatic delivery was activated with a new immutable six-key input Secret and
a separate 100 MiB Longhorn journal PVC. The original immutable input, journal
PVC and stable historical bytes remain untouched with no old writer. A strict
independent verifier checked the actual new controller/ReplicaSet/Pod, complete
executable/security/mount provenance, exact completed journal seed/publication,
live process/Role custody and fresh four-component readiness. The new seed is
`sha256:b08c5131e2111af6771229e6699d065820e4882a23ea824ce4f0e8f19b051a38`.
The historical mutator and intent remain byte-identical. The corrected read-only
verifier is separately hash-bound to the reviewed process module, which permits
only Kubernetes' exact default token projection on approved init containers;
changed init execution and duplicate volume/mount inputs remain rejected.

At that handover checkpoint, the package was installed while the existing inline
guard remained until the separate permanent-registry installer rollout. This
receipt does not claim that registry migration, generic account creation,
human OAuth, general GPU scheduling or production qualification have passed.

## Two concurrent ordinary CPS five-GiB workspaces

The two existing approved CPS groups, with disjoint canonical membership,
completed concurrent normal Source Start and a common 180-second observation
window on the unchanged, cordoned, no-MIG GPU2 pilot. Actual Pod UIDs and sealed
node records established two distinct cgroup caps of **5,368,709,120 bytes**.
The exact existing notebook images, driver/boot epoch, policy and approval
revision remained pinned. No group, grant, course ceiling or GPU owner was added.

In each direction, the existing reviewed direct-CUDA VMM probe allocated and
verified 64 MiB, received typed CUDA result **2** for an untouched oversized
allocation, then allocated and verified 64 MiB again. Its peer completed **225**
successful GPU heartbeat ticks over **45 seconds**, spanning the OOM and
recovery, and confirmed cleanup. The successful private pair receipt SHA256 is
`ffefcc219230e16f790e5d2e0f57dbd8f107df032d5ad24902d209984800cd3f`;
the sanitized result is retained in
`platform-staging/gpu/qualification/concurrent-source5/live-receipt-20261014.json`.

Both normal Close operations confirmed shutdown before releasing reservations,
restored their permission windows and Hub groups, and returned the reviewed
Source records, registrations, Shares and storage associations to their exact
preimages. Fresh readback reported zero active native entries and zero charged
bytes. Retired inventory history changed as expected; it was retained. This is
not an inference that a physical GPU is free.

The earlier attempt stopped before Start because an old evidence parent had
inherited an fsGroup mode. The executor now uses a fresh private directory per
canonical run ID. The first hardware attempt completed both OOM/recovery probes,
but shutdown interrupted the second peer window; that receipt remains
inconclusive. The subsequent complete run passed both directions after the
trusted-artifact staging code normalized only its newly created, inode-bound
directory. Existing directories remain untouched and rejected. The frozen
operator runner SHA256 is
`d241f8f3ad8ff03c42d18f3a914db578e3138511f9355ef29cd99c5152490bbd`;
19 focused offline staging/measurement tests passed.

This qualifies bounded two-workspace CUDA cap isolation through the ordinary CPS
lifecycle. Cross-parent imports, current-pair restarts, MPS, cross-Hub reservations,
KAI placement, wider packing and production remain separate unfinished gates.


## Permanent Hub registry and Source adapter activation

Both owning Hubs subsequently completed the reviewed Hub466 handover and
permanent registry installation. The exact live image is
`ghcr.io/mul-cps/cps-compute@sha256:466b8398285a513499440dd00aaf0abc377cc49afe05f19e5556e79908106486`.
Fresh matching private backups captured each Hub database, application
configuration and roles before migration. Actual PostgreSQL 15.17/18.4 archive
listing verified matching tools; archive SHA256s are retained in the sanitized
registry activation receipt. This records matching backups, not restored service
or off-host durability.

Both actual registry schemas validated, with zero new rows at activation.
Each owning Source service role gained the exact narrow custom scope
`custom:cps:provision:workspace-account`. Migration configuration was then
returned to false, both Hub processes restarted, and actual independent readback
at **23:53:43.388084Z** confirmed all four component acknowledgments, exact
current journal completion, unchanged policy/revision/epoch and retired migration.
The first failed configuration attempt and its verified inverse remain distinct
historical evidence. No existing user, storage association or reviewed alias was
created or changed by the retry.

Both Source consoles now run commit
`55c9a8865c462e4baeb306965fb1a6ed5da07dbd`, immutable image
`ghcr.io/mul-cps/e2x-course-hub@sha256:9698e84452c98385155571e570208e362f19ba4127e8cfe1e4320232a4365849`.
The image contains the permanent account adapter and course concurrency fix;
303 source and 303 installed-image tests passed. Exact image-only rollout
preserved every preexisting database table fingerprint, schema 7/integrity,
sidecars, mounts and complete configuration. Its frontend bytes are unchanged.
See `hub-registry-activation-receipt-20261014.json` and
`source-concurrency-live-receipt-20261014.json` under
`platform-staging/jupyter-extensions-20261013/`.
Normal new-account create/retry/Start/removal, CIT adoption and human OAuth remain
separate live gates.

## Current pair IPC denial and restart retirement

A fresh pair of ordinary CPS 5 GiB workspaces passed both A-to-B and B-to-A
cross-parent CUDA IPC tests. Actual importer/exporter namespace PIDs differed
before open. Both directions returned **800, CUDA_ERROR_NOT_PERMITTED** with
matching actual host-TGID driver witnesses (reason 6, status 27, client kind 4).
Same-parent positive controls, exporter kernel continuity/recovery, importer
kernels, explicit endpoint cleanup and final zero native charge all passed.
The importer observation does not infer which human ran a shared-kernel cell.

The fresh current-cap readback also verified that the previous pair's parents
were retired and inert while the exact two current 5 GiB caps were present.
Both normal Close operations subsequently confirmed shutdown before reservation
release and restored their original windows/groups. The sanitized combined
receipt is
`platform-staging/gpu/qualification/concurrent-source5/ipc-restart-receipt-20261014.json`.
The earlier PID collision and launcher-abort attempts remain incomplete; the
successful new receipt does not relabel them. The main-thread launcher passed
24 offline regressions, including the held-open stdin shutdown reproducer.

This is bounded current-pair import denial and prior-parent retirement. Full
restart behavior, MPS, cross-Hub allowance atomicity, KAI placement and production
remain unqualified. Actual physical free-GPU capacity is not inferred from
zero native charge or the presence of a stopped Hub model.

## Notebook and scheduler contract packages

All 12 matched local notebook OCI builds passed genuine network-disabled runtime
checks. Their exact digests and pinned core/Lab provenance are recorded in the
notebook repository's `release/qualification/notebook-oci-20261014/` artifacts.
They are not published notebook images or a GPU hardware qualification.
The separate pending-allocation SDK candidate passed 1,957 source tests with
3 existing fixture skips and 171 installed-wheel tests. The protected coordinator,
terminal KAI transport, current-RV Binding, cancellation holds and post-Bind cap
seal/CDI remain required before its controlled live placement gate.
