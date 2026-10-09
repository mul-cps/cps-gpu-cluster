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
foreign parents, and unmarked kernel/null-client allocations after caps fail closed.
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

Renderer verifies SHA256 of all twelve pristine input files, checks unique
anchors and refuses an existing output. Nine CPU tests compile the actual
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

## Guarded initialization regression and correction

The first retained-creator candidate passed module loading, the immutable flag
check, cap readback and root NVML, but ordinary user `cuInit` failed before a
context was created. Recorded NVRM denials point to `nvGpuOpsAllocPhysical` FB
allocation, not an imported memory object. In pinned source, kernel RM clients
intentionally have no `pOsPidInfo` (`client.c:131–134`); UVM uses a global GPU-ops
session (`uvm_global.c:120`). Binding that global session to its creation PID
would assign later users' initialization to the wrong authority.

The correction appends a driver-owned `bCpsGpuOpsSession` marker to the official
pre-generated RmClient declaration, explicitly initializes it false in every
constructor, and marks only the private client created by `nvGpuOpsCreateSession`.
The setter holds the write RM API lock and client write lock, with no GPU lock,
and releases them before failed creation cleanup. Cached kernel privilege is a
sanity check, not the source of marker authority; allocation parameters cannot
set the marker. The complete RM core must be rebuilt because RmClient size changes.

Only a marked kernel session with no user creator can charge an allocation to
its retained actual synchronous actor. Its nearest selected cap must have a
nonzero finite HardLimit; a zero/MAX entry rejects without searching past it.
The native debit occurs under the same accounting mutex. The uncapped operator
exception is forbidden for this branch. Unmarked kernel clients and dead user
creators still fail. Kernel import destinations similarly need the marker and
an existing original source charge matching the finite actual actor; no
cross-owner exemption is added.

Global UVM backing may remain charged to the first allocating authority until
its final reference is released. Measure cleanup with a second peer still alive
and retain capacity reservations while backing survives. Compatibility and
isolation for this corrected candidate require fresh hardware tests.

## Earlier candidate CPU build receipt

The earlier retained-creator nine-file patch compiled with GCC/G++ 13.3.0 on Ubuntu kernel
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

## Corrected marked-session CPU build receipt

The eleven-file marked-session finite-cap patch compiled in 157.931 seconds
with the same two-thread/nice19 bounded toolchain. Installed files remained
unchanged. All seven CPU fixtures passed; two independent source reviews found
no remaining blocker for controlled hardware qualification. This corrected
module has not been loaded by the compilation workflow.

* Patch SHA256: `111bb7c3d4180b60b017727421ca9fd33e39a12c3b2f670398d581602ff6c5e4`.
* Candidate core SHA256: `7d5a650dd395f478384bf77c7849083a90285a5b04541879c666161c58774f3e`.
* Full receipt SHA256: `f33d01df1723fd2ae97df9126796a6a7d352f960f109869409b7bfa2bb2a9523`.
* Evidence archive SHA256: `ca4706cfa22c70420773733e7c9952aa15c8579da09298abe0715a1e56b22502`.

Every candidate named CRC matches the exact kernel Module.symvers; there are
no missing or changed baseline imports and the same two legitimate additions.
Version/vermagic match. **The srcversion remains `FDFF9E35B0C7DFAC675EE42` across
the RM correction, so it cannot distinguish these candidates.** Require the
exact ELF digest, reviewed source receipt and fresh loader nonce, rather than
srcversion alone. Artifacts are in the private `final-uvm-session-core` directory.
Ordinary capped CUDA, same-owner/cross-owner imports and global backing cleanup
with a healthy peer remain hardware gates before any group GPU activation.

## Private VMM export-client correction

The marked-session candidate allowed ordinary CUDA initialization and same-Pod
legacy IPC in the controlled canary, but the operator reported VMM FD export
failing with CUDA 800. Its NVRM trace names `RmExportObject`'s DupObject into the
private `hObjExportRmClient`. Pinned `rmobjexportimport.c:257–263` creates that
kernel root client; `:498–506` duplicates the user's backing into it. This is a
different intermediary from UVM's GPU-ops session.

A separate constructor-default-false `bCpsObjExportClient` marker is set only on
that fresh private client in `RmRefObjExportImport`, before memory allocator or
maps are initialized. Its helper verifies the already-held RM API lock, takes
and releases the client write lock, and uses the original failed-construction
cleanup on error. The export marker authorizes destination copies only; it is
never considered by the allocation path. Every copy still requires original
backing charge, a nonzero finite actual-actor cap, and exact matching nearest
parent authority. A source-owned marker is not a cross-owner exemption.

Denial diagnostics log only fixed reason numbers, marker-kind bits, GPU ID,
status and the actual current host TGID. They emit after releasing the native
accounting mutex and use one kernel rate limiter with a burst of 8 per 5 seconds.
They include no kernel pointers, user handles or credentials. Default-off and
successful operations emit no denial events. Reasons are:

| Reason | Denial |
|---|---|
| 1 | Missing actual PID reference |
| 2 | Missing GPU accounting region |
| 3 | Missing/mismatched original backing charge |
| 4 | Actual actor cgroup cannot be retained |
| 5 | No selected finite actor cap (including zero/MAX) |
| 6 | Actual actor parent differs from original charge owner |
| 7 | Missing destination client |
| 8 | Destination user creator cannot be retained |
| 9 | Destination user has no matching parent cap |
| 10 | Unmarked/invalid kernel destination |
| 11 | Unsupported or absent accounting backend |

The nine CPU fixtures include exact export-marker lock paths, export-only
allocation denial, same-owner export compatibility, foreign-owner/zero/MAX
rejection and a synthetic denial logger gate. Actual kernel rate limiting,
same-Pod VMM export/import and cross-Pod VMM hook denial remain hardware gates.

## Private export-client CPU build receipt

The reviewed twelve-file patch compiled in 159.167 seconds with two threads,
nice19 and the same bounded toolchain. Installed core, RM binary and interface
hashes remained unchanged. Nine CPU fixtures and both independent source reviews
passed. No module load or GPU call occurred in this compilation workflow.

* Patch SHA256: `58823f1b3518578ef0c275d77caf194e5cb00fd4dc322dff1ef30389ab78689a`.
* Candidate core SHA256: `59f623fe5fdc89ef06f8055ee4dbfafeabe70b1d0bcabc487bc6fe04b78d6e77`.
* Candidate srcversion: `C6CF64F73A3430C26C030B7`.
* Full receipt SHA256: `691fbf79e9f762129f917512d0eea80c88050de41664b738fcafd1b4873ae938`.
* Evidence archive SHA256: `0810774ceaaba72b247a25a8b5ae1598d429995a0a7f23a4e091233f9fbeb4d5`.

Every named import CRC matches the exact kernel Module.symvers. No baseline
symbols are missing or changed; the third added dependency is
`___ratelimit=0x1d24c881`, alongside the prior two. Version/vermagic match.
Use the exact ELF hash and fresh loader/source receipt. Candidate and full
receipts are retained in the private `final-object-export-core` directory.
Hardware VMM export/import, cross-parent denial and retained exporter-exit
cleanup remain required before activation.
