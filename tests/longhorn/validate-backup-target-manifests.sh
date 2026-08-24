#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
values="$root/cluster-maintenance/clusters/cit-cps-gpu/system/storage/longhorn/values.yaml"

test ! -e "$root/cluster-maintenance/clusters/cit-cps-gpu/system/storage/longhorn/backup-target-bootstrap.yaml"
test ! -e "$root/cluster-maintenance/clusters/cit-cps-gpu/system/storage/longhorn/backup-target.yaml"
rg -F 'defaultBackupStore:' "$values"
rg -F 'backupTarget: nfs://193.170.30.58:/mnt/scratch1/cps_scratch1_tmp/longhorn-backups?nfsOptions=nfsvers=4.2,proto=tcp,hard,timeo=150,retrans=3,rsize=1048576,wsize=1048576,noresvport' "$values"
rg -F 'pollInterval: 300' "$values"
rg -F 'storageOverProvisioningPercentage: 200' "$values"
rg -F 'extraObjects:' "$values"
rg -F 'name: longhorn-backup-target-bootstrap' "$values"
rg -F 'mountPath: /backup' "$values"
rg -F 'server: 193.170.30.58' "$values"
rg -F 'path: /mnt/scratch1/cps_scratch1_tmp' "$values"
rg -F 'mkdir -p /backup/longhorn-backups' "$values"
