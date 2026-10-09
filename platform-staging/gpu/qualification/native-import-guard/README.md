# Native import guard: compiled qualification candidate

**Not deployed. The full pinned NVIDIA core compiled in a CPU-only build and
has never been loaded by this workflow. GPU imports, MPS and group GPU sharing
remain unqualified.** This second-stage candidate is separate from the existing
UVM managed-memory guard. A quiescent GPU canary load, rollback and the hardware
gates below are required; a UVM-only rebuild cannot enforce this policy.

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
VideoMemory copy refcounts and before UVM FB external mappings. The immutable load-time parameter `NVreg_CpsNativeImportGuard` defaults to `0`.
It rejects load values other than 0 and 1 and uses readonly 0400 sysfs and `__ro_after_init` storage; it is deliberately
excluded from the mutable NVIDIA registry table. The helper bypasses all policy
checks unless this flag equals `1`. The controller must verify flag1 plus exact
module/source identity before treating imports as protected.

With native
limits present and this opt-in enabled, backing must retain a matching original GPU/limited-parent
charge. Both current actor and any user destination must normalize to that
same parent. Kernel export intermediaries are permitted only under an actual
capped actor matching the source charge. Uncharged memory and uncapped
MPS/asynchronous delegation reject. It does not globally disable VMM:
ordinary creation and same-Pod IPC/VMM remain intended compatibility tests.

Before any limits exist, ordinary boot is unprotected and passes through.
With the flag enabled, missing accounting is rejected. With flag0, all guard
policy checks bypass and preserve baseline behavior. The runtime must reject these states and
set/read back the correct Pod cap **before every CUDA initialization**. The
unsupported dmem backend fails closed for imports and protected allocations; only the reviewed Linux6.8
fallback/misc pilot is in scope.


Opt-in allocation charging resolves the retained original RM creator and actual
current actor through stable PID references. RCU-protected task lookup and
`cgroup_tryget` retain each original leaf through nearest-parent normalization;
leaf references are released after the native accounting mutex. Charge debit
and authority comparison use that same mutex. Missing or dead creator identity,
foreign parents, and kernel/null-client allocations after caps fail closed.
Set/Get current-process limits use the retained lookup while enabled; default-off
paths keep their original behavior.

The sole uncapped operator allocation exception requires a live creator and
actor in the identical uncapped leaf plus the actual caller's host
`CAP_SYS_ADMIN` (`osIsAdministrator`), not cached RM privilege. This permits
trusted operator/NVML compatibility tests; it is not MPS delegation authority.
Before the first cap entry, driver bootstrap is unprotected. The controller must
hold user initialization until a finite assigned cap is read back. Root NVML and
ordinary capped CUDA after the first cap remain mandatory hardware gates.

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

Renderer verifies SHA256 of all nine pristine input files, checks unique
anchors and refuses an existing output. Six CPU tests compile the actual
helpers against explicit synthetic stubs, exercise same-parent/cross-parent,
default-off bypass, missing charge/GPU/user/actor/region and ambiguous server decisions, plus
load-value validation, protected allocation and per-entry cgroup reference lifetime,
and check an exact patch apply/round trip. They do not prove that closed CUDA
user space reaches these hooks or that driver initialization remains compatible.

## Review and hardware gates for the root operator

1. Review the generated patch, readonly parameter, include/ABI/lock ordering against the exact
   core build source. Compile core offline with that baseline; preserve both
   original and candidate module digests. Compare complete import CRC symbol/name maps and raw `__versions` bytes,
   version and vermagic. All common CRCs must match the installed module; any
   new imports must match the exact kernel Module.symvers and be reviewed.
   Raw byte equality is not expected when a new kernel dependency is added. Core-only
   builds register the official `memory_device_coherent_present` conftest from
   UVM Kbuild in the core Kbuild: the core consumes this macro but does not register its own test.
   Clear the owned generated conftest cache when adding this test; a warm build
   may otherwise retain a stale header. Do not force an untested feature macro.
   The first unconditional candidate is NEVER eligible to load. Existing charge operations
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
6. Cross-Pod and uncapped host MPS delegation are excluded. Separate legacy
   MPSv2 control/server pairs inside each finite-capped Pod, with private pipe
   directories and all actor/destination/source authorities under the same Pod
   parent, are a separate hardware qualification gate. A capped server can
   aggregate clients into one workspace allowance; this guard has no MPS
   client-provenance check and cannot distinguish students inside that workspace.
   No-MPS time slicing remains the first dynamic-sharing target. Do not infer
   compatibility or containment from documentation alone.

Retained backing is charged to the original allocation authority; enforcing
import policy does not reassign charges. Keep its reservation until final
reference release is observed, even after the originating Pod stops. Removing
access does not revoke mappings that existed before guard/cap installation.

Enabled cap-map entries pin their exact cgroup at successful insertion and
release it only at `memacctRemoveGpu` before map clear. Updating a cap takes no
additional reference. The upstream map has no per-entry deletion; dynamic
workloads therefore retain cgroup references until GPU teardown. This is a
bounded-pilot limit, requiring reviewed inactive-entry removal for long-running
production. Pinning prevents recycled cgroup pointers from impersonating the
original allocation authority while exported backing remains charged.

## CPU build receipt

The reviewed nine-file patch compiled with GCC/G++ 13.3.0 on Ubuntu kernel
`6.8.0-134-generic` in 149.703 seconds, with two threads and nice 19. No GPU calls
or module load occurred, and installed core, RM binary and interface hashes
remained unchanged. Candidate version/vermagic match the installed 615.71.09 core.

* Official tag commit: `61dcc93722ecb418bb5f2e00923f05b4b8051dd1`.
* Official archive SHA256: `caf48cda7d5fe7374d1d24ca4a90efb4dc783eefabfad5fa4b64fdc24213b62a`.
* Patch SHA256: `cf2e05fc1a6b4741bae7014b79f8838f53f370dabcbb953f7b29dda6cba1a13a`.
* Candidate core SHA256: `cef578b7938e3825ae7fef8050ce3f7ed01d82c958dc6b188b7d9f404815a0c4`.
* Candidate srcversion: `FDFF9E35B0C7DFAC675EE42`.
* Candidate raw `__versions` SHA256: `b08758c33438f486b4b148826633017a77f21a7d3ef089a3a64b39a7ede5ee00`.
* Exact kernel `Module.symvers` SHA256: `642c198495de116e366e8060890a5054fdf09d45729133c2959e9c668c3598f4`.

All candidate named import CRCs match this exact kernel. No baseline imports
are missing or have changed CRCs. New imports are `param_ops_uint=0xedfbc05a`
and `__put_task_struct=0xc8c7f97d`; therefore raw byte equality is not expected.
Full receipts, raw sections, modinfo, patch, compiler script, log and candidate
are retained in the operator's private `final-retained-core` evidence directory.
Compilation and CPU fixtures do not authorize production activation.
