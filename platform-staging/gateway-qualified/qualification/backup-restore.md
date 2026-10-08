# Current-version database backup and restore qualification

Status: database/application-open restore passed; full disaster recovery remains open.

On 2026-10-06, the CPS console, CIT console and gateway backup CronJobs were
updated to the actual deployed immutable images and central policy hash.
Their `BACKUP_IMAGE` and `BACKUP_POLICY_HASH` values were updated together with
the executing image. Earlier snapshots remain available with their original
version manifests; they must not be relabeled as current-version backups.

Fresh jobs cloned from all three CronJobs completed. Isolated restore jobs,
using the corresponding application images, mounted only each backup PVC
read-only and a new empty directory for the restored databases. They verified
manifest hashes and SQLite integrity before opening the databases through the
installed application. Both console restores rejected the other console owner.
The gateway opened both control and reservation databases. Source snapshots
were preserved and temporary qualification jobs were removed.

The operator report is `2026-10-06/backup-current-release/report.json`, SHA-256
`163511bfafcfa99ff6c594d7d53ae4b0a3ab5c07f849206139a1cda368c84d64`.

For every application/policy rollout, update its backup CronJob image and
version environment values in the same deployment batch. Compare them with
the running Deployment before calling the rollout complete. The Helm chart
already derives both values from the same application image and policy inputs;
applying only an application Deployment leaves recovery provenance stale.
Create a fresh backup and restore it with the manifest's exact image before
promoting a release. Never overwrite an old snapshot to make it match a new
release.

This exercise does not prove restored Hub OAuth sessions, populated course/grant
migration, offsite recovery, NFS archive restoration, or all application runtime
configuration. Those remain separate release gates. Backups of different
applications were taken independently; no cross-application atomic snapshot is
claimed. Rollback uses the private pre-change CronJob definitions and retains
all old and new snapshots.
