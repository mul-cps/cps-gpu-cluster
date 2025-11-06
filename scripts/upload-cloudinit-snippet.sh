#!/usr/bin/env bash
# Script to upload cloud-init snippet to Proxmox
# This snippet installs qemu-guest-agent on VM first boot

set -euo pipefail

PROXMOX_HOST="cit-gpu-01.unileoben.ac.at"
SNIPPET_NAME="qemu-guest-agent.yml"
LOCAL_FILE="../bootstrap-cluster/terraform/cloud-init-qemu-agent.yml"
REMOTE_PATH="/var/lib/vz/snippets/${SNIPPET_NAME}"

echo "================================================"
echo "Uploading cloud-init snippet to Proxmox"
echo "Host: ${PROXMOX_HOST}"
echo "File: ${SNIPPET_NAME}"
echo "================================================"

# Upload the snippet to Proxmox
scp "${LOCAL_FILE}" "root@${PROXMOX_HOST}:${REMOTE_PATH}"

# Set correct permissions
ssh "root@${PROXMOX_HOST}" "chmod 644 ${REMOTE_PATH}"

echo "✅ Cloud-init snippet uploaded successfully!"
echo "Location: ${REMOTE_PATH}"
