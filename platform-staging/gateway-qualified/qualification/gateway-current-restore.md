# Current gateway database restore

Status: bounded database restore passed; full platform recovery remains incomplete.

On 2026-10-06 a fresh Job from `compute-state-backup` took a backup using the deployed gateway image `ghcr.io/mul-cps/cps-compute:qualification-5771df5@sha256:627f093c3c96038c7ecd9e9b99f0138198c23c9460cabb7bd11b19e94f465096`. A separate non-root Job using that same image mounted the backup PVC read-only and restored into an ephemeral directory. It verified the manifest image and policy hash, both database file hashes, SQLite integrity, and successful opening through the installed `ControlStore` and `Reservations` classes. Source hashes were rechecked after application opening.

Private evidence: `/home/bjoern/cps-platform-evidence/2026-10-06/backup-gateway-5771df5/`, containing `report.json`, `restore.log`, the exact restore fixture and completed Job snapshots. Both owned Jobs were removed after evidence collection; backup data and production stores were retained. The restore had no mounted production database and no service-account token.

This does not demonstrate Hub/PostgreSQL, Authentik, application configuration, off-site backup, NFS archives or artifact ownership/retention recovery. Those original acceptance gates remain open.
