# Native import guard: offline prototype only

**Not deployed. Full NVIDIA core has not been compiled or loaded. GPU imports,
MPS and group GPU sharing are not qualified by these CPU checks.** This is a
second-stage source candidate for the root operator, separate from the existing
UVM managed-memory guard. It needs a full pinned `nvidia.ko` build, review,
quiescent GPU canary load and rollback; a UVM-only rebuild cannot enforce it.

## Evidence and selected hooks

Pinned source is NVIDIA `open-gpu-kernel-modules` tag `615.71.09`.

* [`video_mem.c:463–536`](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/src/nvidia/src/kernel/mem_mgr/video_mem.c#L463-L536):
  its copy constructor retains the source `pCharge` and increments its reference
  count (517–522). Duplication does not establish a new importer charge.
* [`memacct.c:109–164`](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/src/nvidia/src/kernel/mem_mgr/memacct.c#L109-L164):
  fallback accounting resolves the nearest ancestor with configured native
  limits and stores that parent in the allocation charge. Same-Pod children
  may therefore share one accounting authority.
* [`mem_export.c:1155–1176`](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/src/nvidia/src/kernel/mem_mgr/mem_export.c#L1155-L1176):
  ordinary MemoryExport import duplicates into the destination RM client.
* [`nv_gpu_ops.c:8389–8411`](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/src/nvidia/src/kernel/rmapi/nv_gpu_ops.c#L8389-L8411):
  UVM's external duplication resolves the original `Memory` before fabric/IOMMU
  mappings or DupObject. A second hook checks this original FB allocation.
* [`client.c:108–135`](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/src/nvidia/src/kernel/rmapi/client.c#L108-L135):
  user RM clients retain stable PID information; kernel intermediaries may not.
* [`os-interface.c:2919–2933`](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/kernel-open/nvidia/os-interface.c#L2919-L2933)
  and [`2980–3014`](https://github.com/NVIDIA/open-gpu-kernel-modules/blob/615.71.09/kernel-open/nvidia/os-interface.c#L2980-L3014):
  current-process PID references avoid `find_vpid(host_tgid)` ambiguity inside
  container PID namespaces. The current actor and user destination are checked
  separately; an uncapped server is never sufficient authorization.

The patch inserts one shared helper into memacct.c and calls it **before**
VideoMemory copy refcounts and before UVM FB external mappings. With native
limits present, backing must retain a matching original GPU/limited-parent
charge. Both current actor and any user destination must normalize to that
same parent. Kernel export intermediaries are permitted only under an actual
capped actor matching the source charge. Uncharged memory and uncapped
MPS/asynchronous delegation reject. It does not globally disable VMM:
ordinary creation and same-Pod IPC/VMM remain intended compatibility tests.

Before any limits exist, or with no accounting implementation, ordinary boot
is unprotected and passes through. The runtime must reject these states and
set/read back the correct Pod cap **before every CUDA initialization**. The
unsupported dmem backend fails closed for copies; only the reviewed Linux6.8
fallback/misc pilot is in scope.

## Render and CPU tests

No command here applies a patch, loads a module, or calls CUDA.

```sh
python3 platform-staging/gpu/qualification/native-import-guard/render_patch.py
CPS_R615_SOURCE=/private/pristine-615.71.09 \
  python3 -m unittest discover \
  -s platform-staging/gpu/qualification/native-import-guard -p 'test*.py'
python3 platform-staging/gpu/qualification/native-import-guard/render_patch.py \
  --render --source /private/pristine-615.71.09 --output /private/NEW-import-guard.patch
```

Renderer verifies SHA256 of all four pristine input files, checks unique
anchors and refuses an existing output. Three CPU tests compile the actual
helper against explicit synthetic stubs, exercise same-parent/cross-parent,
missing charge/GPU/user/actor/region and ambiguous server decisions, and check
an exact patch apply/round trip. They **do not prove the full driver compiles**
or that closed CUDA user space reaches these hooks.

## Review and hardware gates for the root operator

1. Review the generated patch and include/ABI/lock ordering against the exact
   core build source. Compile core offline with that baseline; preserve both
   original and candidate signed module digests. Existing charge operations
   already take the accounting mutex under RM locks; still check all hook
   contexts and asynchronous call stacks. No candidate is promoted automatically.
2. Confirm isolated node/GPU identity, rollback, quiescence and native misc
   backend, fresh VA spaces, managed/HMM denial and no unknown GPU actors.
   Apply cap before initialization, retain original capped cgroups until all
   imported backing is gone. Do not move tasks or reuse deleted cgroup identities
   while retained charges exist. Privileged code is outside this workload boundary.
3. Run the bounded `../native-imports/` probes: ordinary allocation/OOM/recovery,
   same-Pod IPC and VMM, export intermediary and retained-backing cleanup must
   succeed; cross-Pod IPC and VMM must fail with recorded numeric CUDA errors
   before any importer write. Bracket with an independent healthy peer and
   native charges, physical memory and cgroup/PID/Pod fences. Driver tracing must
   prove the hook actually denied the import, rather than a fixture transport issue.
4. Check user libraries relying on same-Pod multiprocessing and ordinary VMM,
   runtime initialization, restart with retained backing, and protected peer
   continuity. Ambiguous internal copies may deliberately reject; failed
   compatibility is a gate failure, not evidence of complete isolation.
5. Legacy handles can travel over ordinary network/files; private sockets and
   namespaces are fixture hygiene, not the enforcement boundary. These hooks
   do not certify DMA-BUF, graphics memory, GPUDirect, Fabric/MIG or remote-peer
   paths, pre-existing mappings, external devices or every memory class. Audit
   or restrict those device/capability paths before any broader production claim.
6. MPS is excluded: an uncapped server or a server aggregating several client
   authorities fails closed. Per-client native accounting/registration and
   authoritative original client provenance must be demonstrated before
   changing this policy. No-MPS time slicing remains the first dynamic-sharing
   target. Do not infer compatibility or containment from documentation alone.

Retained backing is charged to the original allocation authority; enforcing
import policy does not reassign charges. Keep its reservation until final
reference release is observed, even after the originating Pod stops. Removing
access does not revoke mappings that existed before guard/cap installation.
