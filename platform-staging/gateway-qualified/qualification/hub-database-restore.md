# Actual Hub database logical restore qualification

Status: CPS and CIT logical database restores passed into matching PostgreSQL images; matching Hub application initialization passed; complete application recovery remains open.

CPS's chart defaults describe SQLite/PVC, but `00-postgres-db-url` overrides the live backend to PostgreSQL. The mounted Hub PVC contained no SQLite database. CIT explicitly uses PostgreSQL and its Hub has no database PVC; the separate PostgreSQL workload owns a Longhorn volume. Do not infer database recovery coverage from Hub mounts or chart defaults alone.

| Hub | Actual database version | Matching restore image digest | Restored schema | Tables | Users | API tokens |
|---|---|---|---|---:|---:|---:|
| CPS | 15.17 | `docker.io/library/postgres@sha256:866264fb97643e747f9d0981cd060114f83b49450e5bac4988324bb3c6af2fd7` | `4621fec11365` | 17 | 6 | 98 |
| CIT | 18.4 | `docker.io/bitnami/postgresql@sha256:256bf40a7343862b9a66d1d27cd34599e80dad99284fc5450b24cb02e26ff34e` | `4621fec11365` | 17 | 13 | 63 |

Consistent `pg_dump --format=custom --no-owner --no-acl` snapshots were streamed directly from the respective database pods into private mode-0600 evidence. Existing in-pod credentials were used without printing them. Both dumps restored with `pg_restore --exit-on-error` into isolated containers using the exact running image digests. The containers had networking disabled and no published ports. SQL inspection confirmed database versions, expected Hub 5.5.2 schema revision and the aggregate counts above. These counts are observations, not a row-by-row production comparison. Both restore containers are stopped. Production Hubs/databases were neither stopped nor modified.

Private evidence: `/home/bjoern/cps-platform-evidence/2026-10-06/{cps,cit}-hub-postgresql-restore/` contains the protected dumps, checksum manifests, private fixture environment and sanitized `restore-report.json`. Database dumps contain sensitive account and token records and must never enter Git or public release artifacts.

Both database workload specifications use mutable tags (`postgres:15`, `bitnami/postgresql:latest`). Restore qualification therefore records immutable running digests; production GitOps pins and migration qualification remain required. Completed Longhorn backups exist for CIT's database volume, but this logical restore does not qualify a Longhorn backup restore or establish off-host durability.

Remaining gates: protected role/credential/configuration backup (owners and ACLs are deliberately excluded from these logical dumps), matching Hub application startup against restored databases, storage/path associations, complete recovery automation and approved off-host backup/restore. No Hub database backup CronJobs were found; compute and both console backup CronJobs are separate and do not cover these PostgreSQL databases.

## Matching Hub initialization and repeatable protected capture

The exact running Hub image `quay.io/jupyterhub/k8s-hub@sha256:108fbb01c3fe23e4a81efc8899aa73b4c15413615c73dfcdc44248eb63096e41` initialized successfully against each restored database, using synthetic authentication and restore-only credentials. Database user counts remained six CPS and thirteen CIT. Each Hub test shared the respective PostgreSQL container's network namespace, which had networking disabled; no ports were published. Initialization did not start an HTTP service, spawn servers, or load production OAuth/Kubernetes integrations. Both restored database containers were stopped afterward. An initial fixture used the wrong database name; correcting it to `jupyterhub` resolved the connection failure. The protected per-Hub evidence directories retain `hub-initialize-report.json` and private diagnostics.

Use the repeatable read-only operator command from the repository root:

```sh
python scripts/compute-platform/backup-hubs.py /path/to/private/hub-backups
```

The destination must be operator-owned mode 0700 and outside Git checkouts. The command streams both consistent PostgreSQL custom dumps, namespace workloads, ConfigMaps, Secrets and exact running image identifiers into private mode-0600 files. A checksummed manifest and completed bundle are published atomically only after every capture succeeds. Kubernetes error output is suppressed because it may contain credentials. These bundles are secret: never commit them or attach them to public release evidence.

Four focused tests cover successful private publication/checksums, failed capture cleanup, invalid dump rejection and refusal of public/Git destinations. A live capture of both namespaces passed, with private bundles under `/home/bjoern/cps-platform-evidence/2026-10-06/hub-backup-bundles/`. Captures are sequential; this does not create a globally consistent platform snapshot or preserve PostgreSQL cluster roles/ACLs. The earlier protected configuration capture is retained separately under `hub-protected-configuration-backup/`.

Scheduled PostgreSQL backups, approved encrypted off-host durability, complete role/ACL recovery and full Hub service recovery remain required. The command does not install a CronJob, change production workloads or enable GPU access.
