# Reviewed account alias console rollout — 2026-10-08

Both existing consoles in `cps-compute` are ready on the full admin console image
`ghcr.io/mul-cps/e2x-course-hub:qualification-reviewed-alias-f5c005c@sha256:735f891ba008c58a9d3f4d324c22893d13b094dabe7ea39f80c776ffb6c89767`.
Its source is `f5c005ca8b36995c6b4221873d3d0b4d334be3d4`.
The image contains the reviewed compute SDK from `40b9525`, JupyterHub 5.5.2,
Python 3.12.15 and built console UI assets; its 116-test suite passed before rollout.
The exact source SHA is also recorded in `observed.json` and the image label.

| Console | Ready pod | Live SQLite | Existing records | Email links | Reviewed aliases |
| --- | --- | --- | ---: | ---: | ---: |
| CPS | `cps-admin-58c6f68c88-pq58n` | schema 6, integrity `ok` | 0 | 0 | 0 |
| CIT | `cit-admin-5b985f6949-bmpzj` | schema 6, integrity `ok` | 0 | 0 | 0 |

The live databases were empty apart from their separate console ownership rows.
All preexisting table row counts and logical checksums remained identical; adding
the alias table did not create identity authority or promote email verification.
Populated-record migration behavior is covered by the image's regression tests,
not by these empty production database snapshots.

The unchanged owning Hub APIs returned exact existing accounts `bjoern` for CPS
and `akadmin` for CIT, both with `admin: true`. No canonical UUID existed for either
account in console identity tables. This task did not seed or link either account.

## Backup and startup qualification

Before either live image changed, bounded Jobs reused the existing console backup
helper, which matched the tracked helper SHA256
`3238c37f373ea84667221f3c964c0fd4634bbe4d472518faea69222a50ad5838`.
They read live SQLite through its supported online backup API, including committed
WAL state, and wrote current private snapshots on the existing separate backup PVCs.
No live database/WAL files were copied directly.

Exact snapshot copies migrated from schema 5 to 6 under the new image, preserving
all existing rows, references, checksums and verification flags. The unchanged
mounted startup config, Secret references and filesystem SDK imports were checked
with only provider database access redirected to the copy; live data was mounted
read-only. Probes ran as UID 10001 with a read-only root filesystem and no capability
or GPU requests added.

Each snapshot was exported to an operator-owned private directory outside Git:
`/home/bjoern/.local/state/cps-reviewed-alias-rollout/20261008`.
Local directories are 0700 and database/manifest/Deployment evidence files are 0600.
Persistent snapshot database files were rechecked as 0600; directories are 02700
(0700 plus setgid). Hashes, paths, timestamps and sanitized row checksums are in
`observed.json`; database bytes and credentials are absent from this repository.

## Live changes and health

Deployment changes replaced only the console image. JSON Patch tested the current
`resourceVersion`, previous image, `Recreate` strategy and one replica before applying.
Complete Pod templates matched their originals after normalizing the image field.
Console, policy and CA ConfigMap resource versions and hashes remained unchanged.

Each protected `/app` endpoint returned HTTP 302 to `/hub/api/oauth2/authorize`.
This proves the expected authentication redirect and ready service, not a completed
human browser OAuth session or collaboration test.

The two backup CronJobs' `BACKUP_IMAGE` references were then patched to the new
digest with resource-version and prior-value tests. Their runner image, schedules,
other environment, mounts and remaining spec fields stayed unchanged. Stale-version
and wrong-observed-image guard tests failed without mutation. One current bounded
post-upgrade snapshot per console was captured and reverified as schema 6 with
new-image provenance, integrity `ok`, matching SHA256 and 0600 file permissions.
The backup runner uses the standalone SQLite helper, without starting the old app.

Hub services, roles, aliases, grants, gateway state, storage configuration, ingress
and GPU flags were not changed. Fleet promotion remains separate.

## Concrete rollback

Both pre-upgrade schema-5 snapshots remain intact. On private copies, each was
migrated to schema 6, restored using SQLite's backup API, and reopened successfully
with the exact old image at UID 10001 with all row checksums preserved.

The operator script records old image and Deployment state privately. Its rollback
stops only the affected console, refuses restore over concurrent record or identity
changes, restores the matching snapshot through SQLite's backup API, verifies old
schema/checksums, and then restarts the old image. It also restores that console's
backup `BACKUP_IMAGE` provenance to the old image. It never starts an old application
against schema 6. No live rollback was needed or exercised.

```sh
python platform-staging/admin/qualification/reviewed-alias/rollout.py \
  --private-dir /home/bjoern/.local/state/cps-reviewed-alias-rollout/20261008 \
  --rollback cps-admin
```

Use `cit-admin` for the other console. After new records are created, this pre-upgrade
rollback is intentionally refused; reconcile that newer state before any downgrade.
Default inventory does not overwrite rollback evidence, and replaying `--execute`
against an existing evidence bundle is rejected. A new rollout requires a fresh
operator-owned private directory.
