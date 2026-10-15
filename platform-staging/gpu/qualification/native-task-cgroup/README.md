# Retained creator-task/cgroup lookup: offline qualification source

This directory supplies a new helper and CPU lifetime harness, not a deployed
driver. It changes no existing raw lookup API, calls no CUDA, loads no module
and enables no GPU profile. The import-guard renderer owns integration.

`task_cgroup_get.c` is intended for `kernel-open/nvidia/os-interface.c`, with
an explicit `<linux/sched/task.h>` include and this declaration in **both**
OS-interface header copies:

```c
void *NV_API_CALL os_cps_cgroup_get_from_pid_info(void *pidInfo, int impl);
```

The caller must hold the stable `struct pid` reference already supplied by
`osGetPidInfo()` or a locked `RmClient.pOsPidInfo`. The helper deliberately has
no numeric PID fallback. It retains the task under RCU, takes a nonzero cgroup
reference under the same RCU section, then releases the task. It returns one
retained **leaf** cgroup or NULL. Missing/dead PID, unavailable backend and a
failed cgroup reference acquisition reject without retrying an ambiguous
identity. Only the reviewed misc/fallback backend is supported.

Save the returned leaf separately from the variable that is normalized to the
nearest capped ancestor. After the accounting mutex is released, call
`os_cgroup_put(original_leaf)` exactly once. Never put the normalized parent
as a substitute: its reference belongs to the independently pinned cap-map
entry. Holding the leaf retains its ancestry while the nearest-parent lookup
runs. Workloads must not be allowed to move tasks between accounting authorities.

## Pinned source and exhaustive callers

NVIDIA source tag `615.71.09` has one direct caller of the raw
`os_cgroup_for_pid` (`kernel-open/nvidia/os-interface.c:2980–3014`):
`osClientGroupID` in `src/nvidia/arch/nvalloc/unix/src/os.c:2118–2133`.
An exhaustive source search found three upstream users of that wrapper:

| Caller | Pinned location | Required opt-in change |
|---|---|---|
| `memacctTryCharge` | `src/nvidia/src/kernel/mem_mgr/memacct.c:170–244` | Retain creator and actual actor leaves; normalize under accounting mutex; require matching capped parent and GPU; unresolved/uncapped/foreign authority must reject once the GPU has caps. Release both original leaves on every success/failure branch. |
| `cliresCtrlCmdOsUnixMemacctSetLimits_IMPL` | `src/nvidia/arch/nvalloc/unix/src/os.c:2963–2993` | CURRENT_PROCESS uses retained helper directly when opted in. Do not acquire a second reference. Explicit cgroup-FD path already returns a retained reference. Keep one common put. |
| `cliresCtrlCmdOsUnixMemacctGetLimits_IMPL` | `src/nvidia/arch/nvalloc/unix/src/os.c:2996–3050` | Same ownership as SetLimits, including failure exits. |

The new import guard adds actor and destination lookups. Replace both with
the retained helper, saving both leaves. Keep `pidInfo` alive until the actor
leaf is acquired; keep the destination RM client locked through its lookup.
Kernel destinations have no creator reference and must continue to require
the proven actual capped actor, never unrestricted kernel delegation.

Do not silently preserve the upstream `memacctTryCharge` NULL-creator branch
(`:179–184`), which returns success without charging. Under the enabled guard,
fresh allocation cannot use a dead creator or another authority's retained
client. The explicit pre-cap boot window remains unprotected and cannot admit
a workload. An opted-in non-fallback backend must reject.

Keep default-off behavior and the existing raw API unchanged. The separate
cap-map lifetime pin is still required; the short-lived lookup reference does
not retain an allocation authority for the backing object's entire lifetime.

## Kernel ABI verified by read-only inspection

On 2026-10-09 the root-authorized existing GPU2 driver canary's Ubuntu
`6.8.0-134-generic` build headers and `Module.symvers` were inspected without
mutation. `CONFIG_CGROUPS=y` and `CONFIG_CGROUP_MISC=y`; PREEMPT_RT and
DEBUG_CGROUP_REF were not set in the inspected configuration. The exact
headers provide `cgroup_tryget` at `include/linux/cgroup.h:354–356`,
`task_cgroup` at `:482–485`, and `get_task_struct`/`put_task_struct` at
`include/linux/sched/task.h:117–164`.

Relevant exported CRCs were:

| Symbol | CRC | License export |
|---|---|---|
| `pid_task` | `0xca9c85ad` | `EXPORT_SYMBOL` |
| `__put_task_struct` | `0xc8c7f97d` | `EXPORT_SYMBOL_GPL` |
| `__put_task_struct_rcu_cb` | `0x94160518` | `EXPORT_SYMBOL_GPL` |
| `get_pid_task` | `0xd0aed02c` | `EXPORT_SYMBOL_GPL` |
| `param_ops_uint` | `0xedfbc05a` | `EXPORT_SYMBOL` |
| `cgroup_get_from_fd` | `0xb4881782` | `EXPORT_SYMBOL_GPL` |

The helper reuses `pid_task` instead of adding a `get_pid_task` import.
`put_task_struct` can introduce an appropriate task-release symbol. Verify
every resulting candidate import against the exact installed kernel's
Module.symvers; common imports must retain their CRCs, and new imports need
explicit valid export/license evidence. Equal raw import-table bytes to an
unchanged baseline are not a substitute for this check.

Primary Linux 6.8 references: [PID task lookup](https://github.com/torvalds/linux/blob/v6.8/kernel/pid.c#L373-L432),
[cgroup reference and task lookup APIs](https://github.com/torvalds/linux/blob/v6.8/include/linux/cgroup.h#L349-L485),
[task reference release](https://github.com/torvalds/linux/blob/v6.8/include/linux/sched/task.h#L116-L164).

## CPU check and remaining gates

```sh
python3 -m unittest discover \
  -s platform-staging/gpu/qualification/native-task-cgroup -p 'test*.py'
```

The C harness compiles the actual helper against a synthetic Linux ABI and
checks retained references, RCU ordering, creator exit, failed acquisition,
namespace identity separation, migration snapshots and missing backend. It
does not prove kernel scheduling races, CUDA compatibility or GPU isolation.
The integrated pinned core must compile, pass import-CRC review, and undergo
controlled creator-exit/fork/retained-client tests with cap readback and peer
continuity before any qualification claim.
