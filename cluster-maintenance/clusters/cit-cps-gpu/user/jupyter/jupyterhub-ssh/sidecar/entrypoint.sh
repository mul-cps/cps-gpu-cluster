#!/bin/sh
# cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/sidecar/entrypoint.sh
set -eu

if [ -z "${AUTHORIZED_KEY:-}" ]; then
  echo "entrypoint: AUTHORIZED_KEY env var is required" >&2
  exit 1
fi

mkdir -p /etc/ssh/sidecar_authorized_keys
echo "$AUTHORIZED_KEY" > /etc/ssh/sidecar_authorized_keys/authorized_keys
chmod 0644 /etc/ssh/sidecar_authorized_keys/authorized_keys

if [ ! -f /etc/ssh/sidecar_host_keys/ssh_host_ed25519_key ]; then
  ssh-keygen -q -t ed25519 -N "" -f /etc/ssh/sidecar_host_keys/ssh_host_ed25519_key
fi

exec /usr/sbin/sshd -D -e -f /etc/ssh/sshd_config.sidecar
