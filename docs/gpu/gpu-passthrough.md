# GPU Passthrough Setup for Proxmox

This guide covers enabling GPU passthrough on Proxmox VE for NVIDIA GPUs.

## Prerequisites

- Proxmox VE 8.x installed
- NVIDIA GPUs installed in PCIe slots
- IOMMU-capable CPU (Intel VT-d or AMD-Vi)
- UEFI BIOS mode

## Step 1: Enable IOMMU in GRUB

### For Intel CPUs

Edit `/etc/default/grub`:

```bash
nano /etc/default/grub
```

Find the line starting with `GRUB_CMDLINE_LINUX_DEFAULT` and add:

```
GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt"
```

### For AMD CPUs

```
GRUB_CMDLINE_LINUX_DEFAULT="quiet amd_iommu=on iommu=pt"
```

Update GRUB:

```bash
update-grub
```

## Step 2: Load VFIO Modules

Edit `/etc/modules`:

```bash
nano /etc/modules
```

Add the following lines:

```
vfio
vfio_iommu_type1
vfio_pci
vfio_virqfd
```

## Step 3: Blacklist Nouveau Driver

Create `/etc/modprobe.d/blacklist.conf`:

```bash
cat <<EOF > /etc/modprobe.d/blacklist.conf
blacklist nouveau
blacklist nvidia
blacklist nvidiafb
blacklist nvidia_drm
EOF
```

## Step 4: Find GPU PCI IDs

List all NVIDIA devices:

```bash
lspci -nn | grep -i nvidia
```

Example output:
```
41:00.0 3D controller [0302]: NVIDIA Corporation GA100 [A100 PCIe 40GB] [10de:20b0] (rev a1)
41:00.1 Audio device [0403]: NVIDIA Corporation GA100 High Definition Audio Controller [10de:1ef3] (rev a1)
42:00.0 3D controller [0302]: NVIDIA Corporation GA100 [A100 PCIe 40GB] [10de:20b0] (rev a1)
...
```

Note the IDs in brackets, e.g., `10de:20b0` and `10de:1ef3`.

## Step 5: Bind GPUs to VFIO-PCI

Create `/etc/modprobe.d/vfio.conf`:

```bash
cat <<EOF > /etc/modprobe.d/vfio.conf
options vfio-pci ids=10de:20b0,10de:1ef3
EOF
```

**Note**: Replace the IDs with your actual GPU and audio device IDs. Include all 8 GPUs.

## Step 6: Update Initramfs

```bash
update-initramfs -u -k all
```

## Step 7: Reboot

```bash
reboot
```

## Step 8: Verify IOMMU Groups

After reboot, check IOMMU groups:

```bash
find /sys/kernel/iommu_groups/ -type l
```

List NVIDIA devices in IOMMU groups:

```bash
for d in /sys/kernel/iommu_groups/*/devices/*; do
    n=${d#*/iommu_groups/*}
    n=${n%%/*}
    printf 'IOMMU Group %s ' "$n"
    lspci -nns "${d##*/}"
done | grep -i nvidia
```

Ideally, each GPU should be in its own IOMMU group or with only its audio device.

## Step 9: Verify VFIO-PCI Binding

Check that GPUs are bound to vfio-pci:

```bash
lspci -nnk | grep -A 3 NVIDIA
```

You should see:
```
Kernel driver in use: vfio-pci
```

## Step 10: Configure VM for GPU Passthrough

When creating VMs in Terraform, ensure:

1. **Machine type**: q35
2. **BIOS**: OVMF (UEFI)
3. **PCIe devices**: Use `hostpci0`, `hostpci1`, etc.

Example Terraform configuration (already in main.tf):

```hcl
machine = "q35"
bios    = "ovmf"

hostpci0 {
  host   = "0000:41:00.0"
  pcie   = 1
  rombar = 1
  x-vga  = 0
}
```

## Troubleshooting

### IOMMU not enabled

Check if IOMMU is active:

```bash
dmesg | grep -i iommu
```

Should show:
```
DMAR: IOMMU enabled
```

Or for AMD:
```
AMD-Vi: AMD IOMMUv2 loaded and initialized
```

### GPU still using nouveau/nvidia driver

```bash
# Verify blacklist
cat /etc/modprobe.d/blacklist.conf

# Check loaded modules
lsmod | grep nouveau
lsmod | grep nvidia

# Should return nothing
```

### VM won't boot with GPU

1. Verify OVMF firmware installed:
   ```bash
   apt install ovmf
   ```

2. Check VM logs:
   ```bash
   journalctl -u pveproxy -f
   ```

3. Try adding kernel arguments:
   ```hcl
   args = "-cpu host,kvm=off"
   ```

### ACS Override (if GPUs share IOMMU groups)

**Warning**: Only use if necessary and understand the security implications.

Add to GRUB:
```
pcie_acs_override=downstream,multifunction
```

## Best Practices

1. **Reserve CPUs**: Pin vCPUs to specific physical cores for better performance
2. **Huge pages**: Enable for large memory VMs
3. **CPU model**: Use `host` CPU model for best performance
4. **Monitoring**: Watch GPU temps and utilization in Proxmox
5. **Backup**: Always backup working configurations before changes

## GPU Assignment Strategy

For 8x A100 GPUs distributed across 4 worker VMs:

| VM | GPUs | PCI Addresses |
|----|------|---------------|
| wk-gpu1 | 2 | 41:00.0, 42:00.0 |
| wk-gpu2 | 2 | 81:00.0, 82:00.0 |
| wk-gpu3 | 2 | c1:00.0, c2:00.0 |
| wk-gpu4 | 2 | e1:00.0, e2:00.0 |

Adjust based on your actual `lspci` output.

## Verification in VM

After VM boots, verify GPU visibility:

```bash
lspci | grep -i nvidia
```

Should show all passed-through GPUs.

## References

- [Proxmox PCI Passthrough](https://pve.proxmox.com/wiki/PCI_Passthrough)
- [NVIDIA GPU Passthrough](https://nvidia.github.io/gpu-operator/)
- [IOMMU Groups](https://wiki.archlinux.org/title/PCI_passthrough_via_OVMF)
