# GPU kernel promotion gate

Status: proposed / not installed on hosts. Current GPU Operator rebuilds are
post-boot; a successful recovery is not a preboot compatibility gate.

The operator driver container builds for `uname -r`, the running kernel. It
is not an Ubuntu DKMS hook for inactive kernels. Do not add host-managed DKMS
alongside the container-managed driver: the two would compete for ownership.

Recommended automation, retaining the official R615 driver owner:

1. Keep the known-good kernel installed and persistently selected in GRUB.
   Install the candidate kernel and exact headers without promoting it as the
   normal boot target. Verify actual GRUB behaviour and out-of-band recovery.
2. Build unmodified official driver sources in an isolated, unprivileged
   compile environment against that inactive kernel. Pin driver image/source
   digest, target ABI, OS, module flavour, toolchain and signing requirements.
   Do not replace or load modules on the running host.
3. Check build exit status, expected modules, vermagic, symbol compatibility,
   Secure Boot signatures when applicable and usable initramfs. Store a
   checksummed receipt. Failure leaves the approved boot target unchanged.
4. Only a passing receipt permits a controlled one-shot candidate boot on a
   cordoned/drained canary. Retain the old persistent default and recovery path.
5. Validate loaded driver version, both GPUs' CUDA, plugin inventory and the
   relevant KAI/MPS/native-isolation checks. Promote other nodes sequentially
   only after these hardware checks pass.
6. Gate hypervisor maintenance as well as guest reboots: the October incident
   was triggered by an external guest shutdown. Guest unattended-reboot
   settings cannot prevent a hypervisor from powering off a VM.

Compilation proves build compatibility, not actual A100 runtime operation.
Likewise, an apt post-install hook failure is not reliable transaction rollback:
a candidate kernel may already be installed and selected. Gate boot selection
and reboot, not merely the package command's exit status.

Ubuntu precompiled signed modules or DKMS are supported alternative ownership
models, but require a reviewed migration away from container-owned modules.
NVIDIA precompiled driver containers require exact kernel/OS/branch support;
an exact R615/kernel-6.8.0-147 precompiled image has not been established here.

Sources:
- https://github.com/NVIDIA/gpu-driver-container/blob/main/ubuntu24.04/nvidia-driver
- https://ubuntu.com/server/docs/how-to/graphics/install-nvidia-drivers/
- https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/25.10/precompiled-drivers.html
- https://www.gnu.org/software/grub/manual/grub/html_node/next_005fentry.html
- https://ubuntu.com/server/docs/how-to/software/automatic-updates/
