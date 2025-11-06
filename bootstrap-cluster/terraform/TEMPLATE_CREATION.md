# Creating Ubuntu Cloud-Init Template for Proxmox

Before you can deploy VMs with Terraform, you need to create the Ubuntu cloud-init template on your Proxmox host.

## Option 1: Manual Script Execution (Recommended)

### Step 1: Copy the script to your Proxmox host

```bash
# From your local machine
scp ../../../scripts/create-ubuntu-template.sh root@cit-gpu-01.unileoben.ac.at:/root/
```

### Step 2: SSH to Proxmox and run the script

```bash
ssh root@cit-gpu-01.unileoben.ac.at
cd /root
chmod +x create-ubuntu-template.sh
./create-ubuntu-template.sh
```

The script will:
1. Download Ubuntu 24.04 LTS cloud image
2. Create VM ID 9000
3. Import the disk
4. Configure cloud-init
5. Set machine type to q35 and BIOS to OVMF (for GPU passthrough)
6. Add EFI disk
7. Convert to template

### Step 3: Verify template creation

```bash
qm list | grep ubuntu-24.04-cloudinit
# Should show: 9000 ubuntu-24.04-cloudinit
```

## Option 2: Manual Commands

If you prefer to run commands manually on the Proxmox host:

```bash
# SSH to Proxmox host
ssh root@cit-gpu-01.unileoben.ac.at

# Download Ubuntu cloud image
cd /tmp
wget https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img

# Create VM
qm create 9000 \
  --name ubuntu-24.04-cloudinit \
  --memory 2048 \
  --cores 2 \
  --net0 virtio,bridge=vmbr0 \
  --scsihw virtio-scsi-pci

# Import disk
qm importdisk 9000 noble-server-cloudimg-amd64.img local-lvm

# Attach disk
qm set 9000 --scsi0 local-lvm:vm-9000-disk-0

# Add Cloud-Init drive
qm set 9000 --ide2 local-lvm:cloudinit

# Configure boot
qm set 9000 --boot c --bootdisk scsi0

# Add serial console
qm set 9000 --serial0 socket --vga serial0

# Enable QEMU guest agent
qm set 9000 --agent enabled=1

# Set machine type and BIOS for GPU passthrough
qm set 9000 --machine q35
qm set 9000 --bios ovmf

# Add EFI disk
qm set 9000 --efidisk0 local-lvm:1,efitype=4m,pre-enrolled-keys=0

# Resize disk to 32GB
qm resize 9000 scsi0 32G

# Convert to template
qm template 9000

# Cleanup
rm -f /tmp/noble-server-cloudimg-amd64.img
```

## After Template Creation

Once the template is created, you can proceed with Terraform deployment:

```bash
cd /home/bjoernl/git/cps-gpu-cluster/bootstrap-cluster/terraform
tofu plan -out=tfplan
tofu apply tfplan
```

## Template Details

- **VM ID**: 9000
- **Template Name**: ubuntu-24.04-cloudinit
- **OS**: Ubuntu 24.04 LTS (Noble Numbat)
- **Machine Type**: q35 (required for GPU passthrough)
- **BIOS**: OVMF/UEFI (required for GPU passthrough)
- **EFI Disk**: Enabled with 4m EFI type
- **Disk Size**: 32GB (can be resized when cloning)
- **Storage**: local-lvm (or your configured storage pool)

## Customization

The template uses cloud-init, so you can customize:
- Hostname
- User accounts
- SSH keys
- Network configuration
- Packages to install

All via the Terraform `proxmox_vm_qemu` resource cloud-init parameters.

## Troubleshooting

### Template already exists

If VM ID 9000 already exists:

```bash
# Check if it's a template
qm config 9000 | grep template

# If not needed, destroy it
qm destroy 9000 --purge

# Then re-run the creation script
```

### Wrong storage pool

If you're using a different storage pool (not `local-lvm`), edit the script:

```bash
nano /root/create-ubuntu-template.sh
# Change STORAGE_POOL="local-lvm" to your pool name
```

### Download fails

If the Ubuntu cloud image download fails, you can manually download and place it in `/tmp`:

```bash
cd /tmp
wget https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img
```

Then modify the script to skip the download step.
