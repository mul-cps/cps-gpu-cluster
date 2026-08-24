#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
values="$root/cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml"

rg -F 'name="mount_shared_longhorn"' "$values"
rg -F 'name="mount_shared_longhorn" value="1" checked' "$values"
rg -F "opts['mount_shared_longhorn'] = form_bool(formdata, 'mount_shared_longhorn', False)" "$values"
rg -F "mount_shared_longhorn = bool(spawner.user_options.get('mount_shared_longhorn', False))" "$values"
rg -F 'if is_power_user(spawner.user):' "$values"
rg -F 'if mount_shared_longhorn:' "$values"
