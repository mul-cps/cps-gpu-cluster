#!/usr/bin/env bash
# Script to create Ubuntu 24.04 Cloud-Init template on Proxmox
# This script should be run on the Proxmox host

set -euo pipefail

# Configuration
TEMPLATE_ID=9000
TEMPLATE_NAME="ubuntu-24.04-cloudinit"
UBUNTU_VERSION="24.04"
UBUNTU_IMAGE_URL="https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"
STORAGE_POOL="local-lvm"  # Template uses local-lvm (VMs will use NvmeZFSstorage)
MEMORY=2048
CORES=2
DISK_SIZE="32G"

echo "================================================"
echo "Creating Ubuntu ${UBUNTU_VERSION} Cloud-Init Template"
echo "Template ID: ${TEMPLATE_ID}"
echo "Template Name: ${TEMPLATE_NAME}"
echo "================================================"

# Check if template already exists
if qm status ${TEMPLATE_ID} &>/dev/null; then
    echo "WARNING: VM/Template ${TEMPLATE_ID} already exists!"
    read -p "Do you want to destroy it and recreate? (yes/no): " -r
    if [[ $REPLY == "yes" ]]; then
        echo "Destroying existing VM ${TEMPLATE_ID}..."
        qm destroy ${TEMPLATE_ID} --purge || true
    else
        echo "Aborting. Please choose a different TEMPLATE_ID or use existing template."
        exit 1
    fi
fi

# Download Ubuntu cloud image
echo "Downloading Ubuntu ${UBUNTU_VERSION} cloud image..."
cd /tmp
wget -O ubuntu-${UBUNTU_VERSION}-cloudimg.img "${UBUNTU_IMAGE_URL}" || {
    echo "ERROR: Failed to download Ubuntu cloud image"
    exit 1
}

echo "Cloud image downloaded successfully"

# Create VM
echo "Creating VM ${TEMPLATE_ID}..."
qm create ${TEMPLATE_ID} \
    --name ${TEMPLATE_NAME} \
    --memory ${MEMORY} \
    --cores ${CORES} \
    --net0 virtio,bridge=vmbr0 \
    --scsihw virtio-scsi-pci

echo "VM created"

# Import disk
echo "Importing disk to ${STORAGE_POOL}..."
qm importdisk ${TEMPLATE_ID} ubuntu-${UBUNTU_VERSION}-cloudimg.img ${STORAGE_POOL}

# Attach disk to VM
echo "Attaching disk to VM..."
qm set ${TEMPLATE_ID} --scsi0 ${STORAGE_POOL}:vm-${TEMPLATE_ID}-disk-0

# Add Cloud-Init drive
echo "Adding Cloud-Init drive..."
qm set ${TEMPLATE_ID} --ide2 ${STORAGE_POOL}:cloudinit

# Customize cloud-init to install qemu-guest-agent
echo "Configuring cloud-init to install qemu-guest-agent..."
# Ensure snippets directory exists
mkdir -p /var/lib/vz/snippets

cat > /var/lib/vz/snippets/install-qemu-agent.yml << 'EOF'
#cloud-config
package_update: true
packages:
  - qemu-guest-agent
runcmd:
  - systemctl enable qemu-guest-agent
  - systemctl start qemu-guest-agent
EOF

# Set cloud-init custom config
qm set ${TEMPLATE_ID} --cicustom "user=local:snippets/install-qemu-agent.yml"

# Configure boot
echo "Configuring boot settings..."
qm set ${TEMPLATE_ID} --boot c --bootdisk scsi0

# Add serial console
echo "Adding serial console..."
qm set ${TEMPLATE_ID} --serial0 socket --vga serial0

# Enable QEMU guest agent
echo "Enabling QEMU guest agent..."
qm set ${TEMPLATE_ID} --agent enabled=1

# Set machine type and BIOS for GPU passthrough compatibility
echo "Setting machine type to q35 and BIOS to OVMF..."
qm set ${TEMPLATE_ID} --machine q35
qm set ${TEMPLATE_ID} --bios ovmf

# Add EFI disk for OVMF
echo "Adding EFI disk..."
qm set ${TEMPLATE_ID} --efidisk0 ${STORAGE_POOL}:1,efitype=4m,pre-enrolled-keys=0

# Resize disk
echo "Resizing disk to ${DISK_SIZE}..."
qm resize ${TEMPLATE_ID} scsi0 ${DISK_SIZE}

# Convert to template
echo "Converting VM to template..."
qm template ${TEMPLATE_ID}

# Cleanup
echo "Cleaning up downloaded image..."
rm -f /tmp/ubuntu-${UBUNTU_VERSION}-cloudimg.img

echo "================================================"
echo "Template creation complete!"
echo "Template ID: ${TEMPLATE_ID}"
echo "Template Name: ${TEMPLATE_NAME}"
echo "================================================"
echo ""
echo "You can now use this template in Terraform with:"
echo "  vm_template = \"${TEMPLATE_NAME}\""
echo ""
echo "To customize default user, SSH keys, etc., use cloud-init"
echo "settings in your Terraform configuration."
