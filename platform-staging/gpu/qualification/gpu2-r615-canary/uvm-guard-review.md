The managed-mmap guard source is acceptable for a bounded global experimental
canary with fresh VA spaces. It does not implement per-Pod policy and has no
production isolation qualification. This independent worker changes only review
source/receipts and performs read-only live observation.

Reviewed source is the uncommitted package under
`/tmp/cps-r615-pod-cap/platform-staging/gpu/qualification/r615-uvm-guard/`.
`guard.py` checks the exact pinned upstream source hash, adds a default-off
load-time0444 boolean, and inserts the guard before HMM reclamation or managed
allocation. For any overlapping existing range it preserves
NV_ERR_UVM_ADDRESS_IN_USE; it denies a fresh managed mmap with
NV_ERR_NOT_SUPPORTED. The original caller holds the VA-space write lock and uses
the collision status for exact semaphore/P2P mappings. Unconditional denial
would break that ordinary CUDA support path.
The [pinned constructor](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/kernel-open/nvidia-uvm/uvm_va_range.c#L231-L259)
and [actual caller](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/kernel-open/nvidia-uvm/uvm.c#L853-L887)
were fetched independently; their SHA256 values match the patch generator.
Five tests compiling the actual patched function and actual collision caller
passed independently. Their runtime stubs establish branch behavior, not live
CUDA/kernel correctness.

HMM disable alone does not exclude pageable access: the
[pinned VA-space implementation](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/kernel-open/nvidia-uvm/uvm_va_space.c#L189-L202)
enables it for ATS or HMM. Root must require actual fresh CUDA attributes88=0
and100=0 after the experimental reload. Use fresh independent VA spaces with no
preexisting managed allocations/shared MPS state. CUDA allocation/compute/free,
PyTorch, managed creation denial, aggregate ordinary-memory OOM/recovery and
independent peer continuity remain live gates. Shared/imported mappings,
external memory, managed pools/globals and selective ownership remain gaps.

`uvm-review-before.json` records actual installed files, loaded module identity,
parameters, kernel, holders and runtime before the UVM-only phase:

| File | SHA256 | Bytes |
| --- | --- | ---: |
| Original615 nvidia.ko | 94df0cd9b062ef42091a4f2639438b3596c6a49bcb1b56640ac6ef0f792f2020 | 35867088 |
| Original615 nvidia-uvm.ko | 05c2e1319dacdca062bfddc4368be02b66307e0cda31abcd7d28fb37eeefff01 | 57462096 |

The UVM file is
`/lib/modules/6.8.0-134-generic/kernel/drivers/video/nvidia-uvm.ko` in the pinned
GPU2 canary driver container. Version615.71.09 and vermagic
`6.8.0-134-generic SMP preempt mod_unload modversions` match the actual kernel.
Loaded UVM srcversion is2CA5427BFF504A8F70EEAE8; refs0 and no UVM device FD holder.
Only canary persistenced holds NVIDIA device FDs. Core srcversion is
21362C9DF5C1F6DCBE23F50. Original uvm_disable_hmm=N, uvm_ats_mode=1,
uvm_enable_builtin_tests=0. The receipt preserves every visible UVM parameter.

Current kmod31 `modprobe --dump-modversions` rejects these existing ELF modules.
A read-only canonical __versions section digest avoids that tool limitation:

```sh
readelf -x __versions "$ko" |
  awk '/^  0x/ {printf "%s%s%s%s", $2,$3,$4,$5}' | sha256sum
```

Original UVM digest is
`4ce551ea23acfc754376c9d82915e766653a4faf7f1f85438d7c97b76026ae37`;
core digest is`0b9498bdcdf3b4843f0b86409c609347f97a17675a16238a729ada511075933f`.
Candidate UVM must match the original import-version digest and exact kernel
vermagic/version before any root load. The compilation may build the unchanged
core in an owned source copy to obtain CRCs, but must never install or load that
rebuilt core. Independent review of all113 lines of `build_candidate.py` and
its manifest passed; all nine CPU tests passed independently. The actual source
contains no symlinks, and fresh proposed tool/build directories were absent at
review. It checks five source pins, bounded fresh nonoverlapping source copy,
original module SHA/CRC, exact kernel/headers, modules-only make with at most two
jobs, original files unchanged afterward, and candidate CRC/version/vermagic.
No module install/load or runtime command is present. The900s CPU compilation
and subsequent hardware load remain separate root-controlled gates.
`uvm-source-review-hashes.json` freezes the exact reviewed proposal files.

The root-reviewable original615 UVM restore candidate is:

1. Stop all owned CUDA clients; verify UVM refs0 and no UVM FD holders. Recheck
   untouched original module SHA, kernel/version/vermagic and core identity.
2. Run plain `rmmod nvidia_uvm`; abort on refusal. Never force unload or remove
   nvidia/nvidia_modeset, reset a device, restart a daemon or modify installed .ko.
3. Run `insmod` of the original hash-verified file above with
   `uvm_disable_hmm=0`. Restore any other parameters explicitly changed during
   the canary to their recorded original values; the custom guard parameter is
   absent from the original module. Do not pass it to the original image.
4. Verify original loaded srcversion, original HMM setting, ordinary CUDA and
   actual core/module/hash/GPU UUID/MIG state. Compare runtime PIDs/start ticks,
   GPU2 CPU/PVC health and other GPU driver UIDs/images against the before receipt.
   A failed restore remains a failed gate; do not hide it by broad driver reload.

The earlier [normal R580 rollback](r580-rollback.md) is still ready after the
bounded UVM phase, with exact580 GSP files staged. Normal legacy ownership has
separate toolkit/runtime interruption risk. No canary outcome overrides that
rollback's gates or enables dynamic sharing.
