#!/bin/sh
set -eu
operation=${1:?operation required}
node=${2:?node required}
[ "${SYSTEM_UPGRADE_NODE_NAME:?must run under SUC}" = "$node" ]
python3 /kube_preflight.py --operation "$operation" --node "$node"
# The payload is copied into an immutable, content-addressed host location so
# host systemd keeps running after the SUC pod/containerd disappears.
payload_hash=$(sha256sum /host_upgrade.py | cut -d ' ' -f 1)
payload_dir=/var/lib/cps-os-upgrade/payloads
install -d -m 0700 "/host${payload_dir}"
install -m 0500 /host_upgrade.py "/host${payload_dir}/${payload_hash}.py"
exec chroot /host /usr/bin/python3 "${payload_dir}/${payload_hash}.py" launch --operation "$operation" --node "$node"
