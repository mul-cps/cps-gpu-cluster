#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
bootstrap="$root/cluster-maintenance/clusters/cit-cps-gpu/system/storage/longhorn/backup-target-bootstrap.yaml"
target="$root/cluster-maintenance/clusters/cit-cps-gpu/system/storage/longhorn/backup-target.yaml"

test -f "$bootstrap"
test -f "$target"
rg -F 'mountPath: /backup' "$bootstrap"
rg -F 'server: 193.170.30.58' "$bootstrap"
rg -F 'path: /mnt/scratch1/cps_scratch1_tmp' "$bootstrap"
rg -F 'mkdir -p /backup/longhorn-backups' "$bootstrap"
rg -F 'name: default' "$target"
rg -F 'nfs://193.170.30.58:/mnt/scratch1/cps_scratch1_tmp/longhorn-backups?' "$target"
rg -F 'nfsvers=4.2,proto=tcp,hard,timeo=150,retrans=3,rsize=1048576,wsize=1048576,noresvport' "$target"
