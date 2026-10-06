# Hub PostgreSQL backup jobs

This chart is outside Fleet's watched paths. It backs up the actual PostgreSQL databases used by both Hubs, independently of the console/gateway SQLite backups. CPS and CIT use separate jobs, existing namespace-local database credential Secrets, dedicated 1 GiB Longhorn PVCs, and the exact PostgreSQL image digests qualified by isolated restores. No credential values are in this directory.

The chart defaults to disabled and suspended. Qualification starts with the owner values and `--set suspend=true`, followed by one-shot jobs created from each CronJob. Qualified activation uses `--set suspend=false`. Each job is confined to database port 5432 and cluster DNS, has no Kubernetes API token or role, and runs without root, writable root filesystem or additional capabilities. Pod affinity keeps the backup on the database node. The source database volumes are not mounted.

```sh
helm template hub-backup platform-staging/hub-backups/chart \
  -f platform-staging/hub-backups/cps-values.yaml --set suspend=true | kubectl apply -f -
helm template hub-backup platform-staging/hub-backups/chart \
  -f platform-staging/hub-backups/cit-values.yaml --set suspend=true | kubectl apply -f -
```

Jobs use `pg_dump` custom format with owners and ACLs excluded, validate the archive with `pg_restore --list`, write a checksum/provenance manifest, flush files and atomically publish a private bundle. Partial failures remove their own temporary directory and keep previous completed bundles. Database diagnostics remain inside the job's private temporary directory because they may contain confidential data. Backups contain real Hub user and token records: any export must remain private and outside Git.

The daily schedule is **02:31 UTC**, concurrency is forbidden and the deadline is five minutes. Backups are retained; no automatic deletion runs before an approved off-host durability/retention policy exists. Check PVC usage and failed Jobs, and do not treat an active CronJob as proof that recent backups succeeded. Failure to capture a new bundle does not remove older bundles.

For recovery, export an archive and its manifest using a credential-free reader pod with a read-only mount on the database node. Verify its checksum, restore to a fresh isolated database using the recorded image version, and initialize the matching Hub image against the restored database. Never apply exported production Secrets or start restored Hub services in a connected test environment without an explicit reviewed recovery procedure.

Qualification evidence is private under `/home/bjoern/cps-platform-evidence/2026-10-06/hub-scheduled-backup/`: one-shot Job reports, checksummed job archives, matching isolated restore reports and a controller-trigger report. The restore tests verify Hub schema `4621fec11365`, 17 tables and six CPS/thirteen CIT users. They do not cover row-by-row comparison, PostgreSQL roles/ACLs, production OAuth, server spawning, NFS recovery, off-host durability or a complete platform restore. Those remain release gates. See [Hub recovery evidence](../gateway-qualified/qualification/hub-database-restore.md).

## Operational alerts

`alerts.yaml` supplies five dedicated Rancher Monitoring rules: stale success (>26 hours), absent expected CronJob telemetry, no success telemetry after two hours, suspended backups and failed owned Jobs. Successful historical runs do not suppress a retained failed-Job alert; inspect and resolve the failure. Prometheus confirmed successful-run metrics for both Hubs. Free-space samples for these PVCs were absent during qualification, so this deployment does not claim continuous filesystem-capacity telemetry.

```sh
kubectl apply -f platform-staging/hub-backups/alerts.yaml
python tests/observability/check_hub_backup_alerts.py
```

The checker extracts the Kubernetes rule spec and runs `promtool` syntax validation plus six synthetic metric scenarios. To use the exact deployed Prometheus image, pull the digest named in the checker and run with `--podman`; containers have networking disabled and no cluster credentials. Live rule-loading/health evidence is under `/home/bjoern/cps-platform-evidence/2026-10-06/hub-backup-alerts/`. Loading and evaluating rules does not qualify notification delivery, backup durability or full recovery.
