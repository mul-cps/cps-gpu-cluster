This is a bounded GPU2 canary receipt, not a claim that R615 closes memory
isolation or that rollback has passed. Root performs maintenance; this worker
reads live state and prepares source/manifests only. MIG is excluded.

The initial read-only cache audit found R580 complete/unpacked but seven required
manager amd64 compressed layers missing, despite an unpacked snapshot. Root
filled that cache and the pinned R615 cache using existing GPU2 containerd.
`cache-receipt.json` independently verifies the final state:

| Reference | Content | Unpacked |
| --- | --- | --- |
| R580 index `41515698692b...` | 13/13, 619.8 MiB | true |
| manager index `a6c12abacc9c...` | 28/28, 31.1 MiB | true |
| R615 amd64 child `bc7572b7f141...` | 13/13, 756.3 MiB | true |

All 29 manager linux/amd64 descriptors (manifest/config/layers) are present with
the expected file sizes. This verifies local content availability, not rollback
execution. `cache_audit.py` only reads metadata/file sizes and never pulls.

The cache-only command used the existing privileged GPU2 driver Pod before its
removal. It requires a fresh matching node/Pod UID. This command fetches content,
unpacks a snapshot and registers image metadata; it does not run tasks, restart
containerd/K3s, or restart Pods. It can fail normally on network/TLS errors:

```sh
kubectl -n gpu-operator exec nvidia-driver-daemonset-ssr7r -c nvidia-driver-ctr -- \
  /proc/1/root/var/lib/rancher/k3s/data/65415f7708224bbfc7865f032e84da4a5123a3acebef70c8ee40fa991aa68555/bin/ctr \
  --address /proc/1/root/run/k3s/containerd/containerd.sock --namespace k8s.io \
  images pull --local --platform linux/amd64 --snapshotter overlayfs \
  --max-concurrent-downloads 2 \
  nvcr.io/nvidia/cloud-native/k8s-driver-manager@sha256:a6c12abacc9c4f51d3653c90fcad32f19799069889338601407eba05fea4ba18
```

No registry credential was read or supplied: this is a public image. The exact
running `ctr images pull --help` describes its fetch/snapshot/metadata actions.

Before maintenance, both A100 UUIDs had current+pending MIG Disabled, only the
idle UID10001 MPS server used memory (36 MiB/device), and its actual control
`get_client_list 3166883` returned no clients. GPU-resource/binding annotations
and GPU2 reservation Pods were absent. A finite full host `/proc/*/fd` scan found
five holder processes, all mapped to GPU operator Pod UIDs: MPS root1260846,
MPS UID10001 3166883, driver persistenced952231, DCGM953455, plugin954286.
No CPU/PVC Pod NVIDIA device FD was observed; future clients remain a fresh gate.
`holder-pvc-before.json` preserves this receipt.

The loaded module was Open580.95.05. Initial refs were nvidia112, uvm10,
modeset0. After root's GPU2 consumer exclusion, only owning driver persistenced
remained: nvidia11, uvm0, modeset0. After root stopped that one driver Pod,
read-only `host_holders.sh` in the unchanged toolkit Pod found no NVIDIA modules
and no NVIDIA device FD holders. There was no forced unload/reset/reboot.

Both host kernel header Makefiles were present (generic6.8.0-134 and common6.8.0-134).
Host lockdown was `[none] integrity confidentiality`. The host SecureBoot EFI
variable bytes were `6 0 0 0 0`: four attribute bytes, then SecureBoot=0. Module
signature enforcement is disabled (`CONFIG_MODULE_SIG_FORCE` unset; module taint
OE). These are current read-only prerequisites, not a guarantee of compilation.

Pinned R615 driver-container source is
[575c9011 ubuntu24.04/nvidia-driver](https://github.com/NVIDIA/gpu-driver-container/blob/575c9011c4fa4b94200c56818b1f97cdbcf610af/ubuntu24.04/nvidia-driver):

- Lines333–447 SIGTERM driver persistence daemons, check module refs against
  dependent-module refs, and invoke plain `rmmod`, without force. The precheck
  returns1 when in use. A raced `rmmod` error is not explicitly propagated before
  the unconditional return0; external actual module disappearance is essential.
- Lines462–500 run the installer with no-drm/no-nvidia-modprobe and, for this
  branch, skip-module-load. Lines293–335 later use explicit normal modprobe.
- Lines519–546 lazily unmount the driver-root bind only after unload succeeds.
  This is a mount operation, not a K3s/containerd service restart.
- Lines736–795 handle TERM through shutdown and initialize after checked unload.
  No `systemctl`, K3s/containerd restart, or reboot command appears in this file
  or the pinned image-build `install.sh`. Firmware/sysfs, module configuration,
  driver-root mount and kernel-update hook changes still occur on this node.

Fetched source SHA256: nvidia-driver
`027a9128c5e5eebfdefae2831f65d28210036bbf83a9414bc22c68b37db0c16b`;
install.sh `6f15e0eaf62581cf48688d57a9459af38f417c20614b3f328982d5744f7dc657`.
Inherited startupProbe is120 failures at10s, initial60s, timeout60s; Pod
termination grace30s. Do not equate Probe success with installed version or
assume Pod timeout guarantees orderly unload. Root uses explicit module/version
and device checks, with a bounded timeout and no forced operation.

Manager v0.9.0 is
[a837602b cmd/driver-manager/main.go](https://github.com/NVIDIA/k8s-driver-manager/blob/a837602b5d1a5c3a62ea2166a19d71fea2cf0984/cmd/driver-manager/main.go):
lines275–288 always evict operator operands before evaluating user GPU eviction
or drain flags. Lines505–529 include toolkit and MIG-manager. Lines829–843 only
disable later user GPU eviction/drain under autoUpgrade. The
[node patch](https://github.com/NVIDIA/k8s-driver-manager/blob/a837602b5d1a5c3a62ea2166a19d71fea2cf0984/internal/kubernetes/client.go#L96-L113)
targets the configured node, with no global DaemonSet mutation.

The first live attempt therefore recreated GPU2 toolkit and MIG-manager Pods.
It performed no MIG device-mode/instance operation, but their Pod UIDs did change.
GPU2 Spegel registry also restarted0→1, exit255 Unknown at13:36:29Z and running
again13:36:32Z. Its UID stayed unchanged. Do not claim zero CPU interruption.
At13:43:23Z every protected GPU1/3/4 baseline Pod and GPU2 CPU/PVC baseline Pod
was Ready with the original UID; only that Spegel restart counter differed.
The critical PostgreSQL/CPSadmin/Loki PVC Pod restart counters remained unchanged.

Root preserved the first failed install logs privately. Modules loaded615.71.09
but nvidia-smi saw no devices; installer reported ENOENT creating
`/lib/firmware/nvidia`, and kernel firmware requests for615 gsp/ucodes tu10x failed.
The inherited firmware hostPath lived beneath the driver-root bind that init
unmounts. The corrected candidate uses independent
`/run/nvidia/firmware-r615-canary` at `/lib/firmware`, omits driver-manager, and
sets the kernel firmware search path there using one tiny pinned-image init.
Source lines293–311 retain an existing nonempty path, making that explicit init
necessary. Root saves the original path `/run/nvidia/driver/lib/firmware` privately
for rollback. Actual memory-isolation tests remain a separate acceptance gate.

The corrected live canary then became Ready at the pinned amd64 image ID, with
Open615.71.09, both expected A100 UUIDs healthy, current+pending MIG Disabled,
and all four expected615 gsp/ucodes firmware files present and nonempty in the
independent directory. `healthy-driver-receipt.json` records the current Pod UID,
actual module/GPU state and host processes. This closes the narrow firmware
startup defect; it does not qualify memory isolation.

Runtime continuity failed on the first attempt. The original read-only
containerd PID was954817; the later PID is1457904, with k3s-agent1457864.
`runtime-journal-receipt.json` records the exact host unit sequence:

- Prototype libsync ldpreload volume detached13:34:13Z. Its live DaemonSet has
  no lifecycle/preStop; command only copies the two files then execs sleep.
  Monitor also has no lifecycle/preStop.
- At13:36:21.301Z, original k3s-agent954775 received shutdown because
  `containerd exited: signal: hangup`.
- systemd scheduled restart13:36:26.730Z; new agent started13:36:26.898Z,
  containerd ran13:36:28.677Z and was ready13:36:30.684Z; service started13:36:32.844Z.

The toolkit source identifies the matching cleanup path:
[v1.18.0 installer main](https://github.com/NVIDIA/nvidia-container-toolkit/blob/v1.18.0/cmd/nvidia-ctk-installer/main.go#L219-L232)
waits for termination then calls runtime.Cleanup;
[containerd cleanup](https://github.com/NVIDIA/nvidia-container-toolkit/blob/v1.18.0/cmd/nvidia-ctk-installer/container/runtime/containerd/containerd.go#L114-L140)
unconfigures then restarts;
[signal implementation](https://github.com/NVIDIA/nvidia-container-toolkit/blob/v1.18.0/cmd/nvidia-ctk-installer/container/runtime/containerd/containerd_linux.go#L74-L87)
sends SIGHUP to the containerd socket's peer PID. Default restart mode is signal,
and the actual operator entrypoint execs nvidia-toolkit without an override.
This source path and the manager/toolkit termination timeline support toolkit
cleanup as the cause; this journal does not record the exact signal-sender PID.
Keeping toolkit running and omitting manager prevents this path in the corrected
canary. Legacy-manager rollback can repeat it and is not approved by a claim of
unchanged runtime. `RUNTIME_RESTART_MODE=none` exists as an option, but no shared
toolkit DaemonSet change was made or proposed as part of this receipt.

A virgin fallback-memory-limit GET returning NotSupported is not evidence that
the backend is unavailable: the open615 source
[memacct.c](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/src/nvidia/src/kernel/mem_mgr/memacct.c#L324-L347)
also returns that error when no nearest configured limit exists. Root is testing
a bounded real SET before considering any module parameter. The kernel has
CONFIG_CGROUP_MISC=y and root controllers/subtree_control include misc. No force
parameter or further reload was prepared/applied by this worker. If later needed,
the driver-container reads `/drivers/nvidia.conf`; NVIDIA_MODULE_PARAMS env is
overwritten by its array initialization and is not an input. The documented
override is `NVreg_RegistryDwords="RmMemacctMode=1"`, rather than a standalone
NVreg_RmMemacctMode parameter. The default is auto3, with force-misc1 only a
downgrade; no capability conclusion follows from that option alone.

The root later set and read128 MiB soft/hard limits successfully on both owned
QA cgroups, so no forced registry parameter was needed. The unprivileged CUDA
fixtures initially failed to start because their requested UUID CDI devices were
unresolved. Management discovery mode only generates `all`; root generated a
node-only NVML-mode specification with vendor `management.nvidia.com`, containing
the two exact UUIDs and `all`. Existing host CLI is1.18.0 commit
f8daa5e26de9fd7eb79259040b6dd5a52060048c, at
`/usr/local/nvidia/toolkit/nvidia-ctk`; its wrapper requires the host/chroot context.
No runtime restart is required to write this independently named CDI file.

`cdi-file-receipt.json` records root's actual registered file
`/var/run/cdi/cps-r615-canary.json`, SHA256
`bf89492a56f1235e0772fb1d26e88243200c739c09793e770a16a6a842c7f448`.
At14:04Z, agent1457864 and containerd1457904 still had the same process start
ticks as the first restart. Protected baseline UIDs and Ready states all matched;
the prior Spegel restart remained the sole restart-count difference.

One worker probe intended to emit to stdout passed an empty `--output=` flag
before `--format json`. The CLI consumed the next flag as a filename and created
unregistered host `/--format.yaml`, size19880, SHA256
`29cad3cef29273fdee40cb610f9eb21cc0fd56269795edb447d162511e873f59`.
This is outside CDI search directories and affected no runtime registration.
Root was informed immediately after discovery and owns exact hash-guarded
cleanup. A corrected stdout probe omitted the output flag. No more generation
probes are needed. This bounded accidental write is the exception to the worker's
read-only live operations and is recorded explicitly.

Cleanup order is root-owned: stop the owned CUDA processes while retaining their
fixture Pods/cgroups, zero any configured soft reservations, verify actual
clients gone, then delete fixtures and remove only the named owned CDI file
after matching its recorded hash.
Remove the stray file after matching its separate hash. Do not clear the entire
CDI directory or affect existing files. Root's original directory baseline was
empty. The independent firmware directory must remain while the615 module uses
it. Only after owned CUDA stops and actual NVIDIA modules/FDs are absent may root
restore the original journaled firmware search path, before the chosen R580 path.

Restoring the original R580 DaemonSet uses its unchanged manager, which can
recycle toolkit and produce the same brief K3s restart. A temporary node-only
R580 driver without that manager can avoid the cycle while under manual
ownership, but later return to legacy ownership still requires handling it.
No overlapping drivers or ownership adoption are proposed or performed. Root
chooses the rollback path and must verify the CPU/PVC baseline after it.
The planner's `restore` now refuses a live canary and requires a Ready original
R580 image plus actual580.95.05/MIG Disabled on both GPUs before emitting any
consumer/uncordon patch. Recovering the driver is a separate root-controlled step.

`node_journal.py` only emits private CAS patches. Root's consumers patch tests
fresh node UID/resourceVersion, cordons GPU2 and excludes MPS/plugin/DCGM/GFD/
validator; toolkit, driver and MIG-manager remain unchanged by that patch.
The driver patch is a separate gate after consumers and holders clear. Private
patch output is exclusive-created; a stale resourceVersion rejection applies
nothing, and root explicitly archives it before regeneration. Nothing applies
automatically or retries across nodes. Root keeps the full private rollback journal.
