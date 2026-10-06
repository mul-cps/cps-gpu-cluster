# Actual Hub database logical restore qualification

Status: CPS and CIT logical database restores passed into matching PostgreSQL images; complete application recovery remains open.

CPS's chart defaults describe SQLite/PVC, but `00-postgres-db-url` overrides the live backend to PostgreSQL. The mounted Hub PVC contained no SQLite database. CIT explicitly uses PostgreSQL and its Hub has no database PVC; the separate PostgreSQL workload owns a Longhorn volume. Do not infer database recovery coverage from Hub mounts or chart defaults alone.

| Hub | Actual database version | Matching restore image digest | Restored schema | Tables | Users | API tokens |
|---|---|---|---|---:|---:|---:|
| CPS | 15.17 | `docker.io/library/postgres@sha256:866264fb97643e747f9d0981cd060114f83b49450e5bac4988324bb3c6af2fd7` | `4621fec11365` | 17 | 6 | 98 |
| CIT | 18.4 | `docker.io/bitnami/postgresql@sha256:256bf40a7343862b9a66d1d27cd34599e80dad99284fc5450b24cb02e26ff34e` | `4621fec11365` | 17 | 13 | 63 |

Consistent `pg_dump --format=custom --no-owner --no-acl` snapshots were streamed directly from the respective database pods into private mode-0600 evidence. Existing in-pod credentials were used without printing them. Both dumps restored with `pg_restore --exit-on-error` into isolated containers using the exact running image digests. The containers had networking disabled and no published ports. SQL inspection confirmed database versions, expected Hub 5.5.2 schema revision and the aggregate counts above. These counts are observations, not a row-by-row production comparison. Both restore containers are stopped. Production Hubs/databases were neither stopped nor modified.

Private evidence: `/home/bjoern/cps-platform-evidence/2026-10-06/{cps,cit}-hub-postgresql-restore/` contains the protected dumps, checksum manifests, private fixture environment and sanitized `restore-report.json`. Database dumps contain sensitive account and token records and must never enter Git or public release artifacts.

Both database workload specifications use mutable tags (`postgres:15`, `bitnami/postgresql:latest`). Restore qualification therefore records immutable running digests; production GitOps pins and migration qualification remain required. Completed Longhorn backups exist for CIT's database volume, but this logical restore does not qualify a Longhorn backup restore or establish off-host durability.

Remaining gates: protected role/credential/configuration backup (owners and ACLs are deliberately excluded from these logical dumps), matching Hub application startup against restored databases, storage/path associations, complete recovery automation and approved off-host backup/restore. No Hub database backup CronJobs were found; compute and both console backup CronJobs are separate and do not cover these PostgreSQL databases.
