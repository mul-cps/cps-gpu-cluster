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
The initial observer awk digest was incorrect: the final partial row included
ASCII, while the first build parser dropped the final byte. Root's original
build precondition correctly failed before any source copy. The CRC fields in
`uvm-review-before.json` are historical incorrect metadata and are superseded by
`uvm-raw-section-proof.json`; module-file SHA and other baseline fields remain
valid. The corrected observer parses ELF section headers and reads the exact
__versions bytes with read-only `dd`, without executing objcopy or writing a live
file. Three tests cover final partial-byte inclusion, truncation and ELF class.

Original and candidate UVM each have10017 section bytes; SHA256 of their full
`bytes.hex()` strings is
`0054b45bf40416a31ae6e77554935731d29b0235c5a49452590408ebb0f5184a`.
Original core has12409 section bytes, canonical digest
`30e9bd10a691e10d45a81fe6d3dac3aa0c4375c6487c458e5398699e6dd60b28`.
Candidate UVM must match the original import-version digest and exact kernel
vermagic/version before any root load. The compilation may build the unchanged
core in an owned source copy to obtain CRCs, but must never install or load that
rebuilt core. Independent review of all113 lines of `build_candidate.py` and
its manifest passed; all nine CPU tests passed independently. The actual source
contains no symlinks, and fresh proposed tool/build directories were absent at
review. It checks five source pins, bounded fresh nonoverlapping source copy,
original module SHA/CRC, exact kernel/headers, modules-only make with at most two
jobs, original files unchanged afterward, and candidate CRC/version/vermagic.
No module install/load or runtime command is present. Root's CPU compilation then passed, exit0. The candidate UVM SHA256 is
`b2ae67722e9e21a70c319aeed2184f5b2d1f23b8e32dea00816cfd5cd2c3ee61`,
version615.71.09, exact kernel vermagic and raw-section digest matching original.
Original source/module hashes remained unchanged. Actual CUDA tests remain a
separate gate.
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


At15:02Z, `uvm-review-guard-loaded.json` independently records root's successful
UVM-only load: srcversion9353E234906B1910373B07A, guardY/HMMY/ATS0/SAMY/builtins0,
UVMrefs0 and no UVM device clients. Core srcversion21362C9DF5C1F6DCBE23F50 and
loaded address0xffffffffc0df9000 remain unchanged; modeset address0xffffffffc1639000
also matches baseline. Runtime agent1457864/containerd1457904 and start ticks
810395303/810395495 match. Original installed files are unchanged; both original
A100 UUIDs show615.71.09 and current+pending MIG Disabled. Canary UID/Ready/restart0,
GPU2 CPU/PVC UIDs/Ready and other GPU driver UIDs/images/Ready match. Historical
Spegel restart and absent GPU1 notebook limitations remain recorded separately.
No core or daemon continuity claim applies to the earlier full-driver phase.

The runtime proposal was independently reviewed and all13 CPU tests passed.
It checks actual guard/HMM/ATS/builtin state, CUDA attributes88/100, UID1000/GID100,
no preload, exact physical UUID, fixed512 MiB parent readback, bounded raw64/256/
recovery allocations with verified cap margin, managed64 denial, fresh process
and fork-before-CUDA cases, and an independent120s peer. Raw CUDA cleanup is
explicit; Torch contexts end with their fresh process. Outer subprocess timeout
can kill a fork launcher while its child runs briefly until its own bounded
60s deadline; root must verify actual FD/reference cleanup, not infer it from
launcher exit. No inherited/shared/imported state or selective per-Pod policy is
qualified by this proposal. Actual CUDA outcomes and original-UVM restoration
remain pending.
