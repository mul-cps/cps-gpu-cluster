This qualification-only inventory retains all limits and cgroup pins. It never
clears a limit, deletes an entry, changes charge references, or authorizes a gate.
The existing renderer stays unchanged unless `--readonly-cap-inventory` is set.
The module's immutable `NVreg_CpsNativeImportGuard=1` is also required.

The per-GPU path is `/proc/driver/nvidia/gpus/<PCI BDF>/cps_native_caps`, owned by
root with mode0400. Opening and every read require effective UID0 and
CAP_SYS_ADMIN in the initial user namespace. There is no write or seek handler;
seeking must not invoke seq traversal outside the PM read-lock wrapper. Each
successful read returns one complete JSON document:

```json
{"version":1,"backend":"misc-fallback","gpu_uuid":"GPU-...","gpu_id":0,"entries":[{"cgroup_id":17,"kernfs_id":17,"inode":17,"offline":true,"pinned":true,"default_hierarchy":true,"soft":5368709120,"hard":5368709120,"used":0}]}
```

IDs/limits/used are unsigned integers, flags are JSON booleans. A snapshot copies
the exact selected GPU map under the existing accounting mutex and formats only
after that succeeds. Unsupported backend, disabled guard, missing GPU, unknown
pin, inconsistent accounting/identity, or more than256 entries fail the read;
there is no successful truncated snapshot. Rows contain no kernel pointers.
The OSAPI wrapper holds the existing RM API lock and enters the normal RM runtime
before taking the accounting mutex; this also fences the mutex's last-GPU
destruction. Proc reads hold the same system PM read lock as existing proc files.
The vendor's optional alternate RM stack can be disabled. In that build, its
stack allocator succeeds with a NULL stack and the RM runtime macros are no-ops;
the inventory wrapper accepts this convention. A NULL stack remains an error
when the alternate stack is enabled. CPU tests join the actual proc callback to
the actual RM wrapper in both modes, rather than substituting a wrapper stub.
The default-hierarchy check uses the exported GPL `cgrp_dfl_root` data symbol;
the unexported kernel-local `cgroup_on_dfl` function is not callable by a module.

On the qualified 64-bit Linux6.8 cgroup2 hierarchy, full cgroup ID, kernfs ID and
stat inode are equal. The original journal already records that inode. The
consumer must reject duplicate/missing/mismatched IDs, require the expected GPU
UUID and exact old soft/hard cap, and verify `offline=true`, `pinned=true`,
`default_hierarchy=true`, `used=0`. Original st_dev and cgroup2 mount identity
remain separately validated host facts. Healthy node/boot/module/load epoch
must be checked immediately before and after each inventory read. This JSON
contains no assertion that the module epoch is unchanged.

The pin prevents reuse of the old cgroup object and kernfs ID. An offline
cgroup cannot accept new tasks. Positive-byte charges are subtracted from
Available and restored only when the last MemoryCharge reference is released;
`used=HardLimit-Available` therefore includes retained backing. Zero-size
references are not enumerated. Keeping the entry pinned permits their later
release without a dangling authority. A finite inactive row is an inert cap
tombstone, not an unlimited/removed-limit readback.

A newly loaded module cannot inspect the previous module's cap map. Old journals
must remain held until separately audited maintenance proves the previous map
teardown; the new inventory cannot substitute for that evidence. NVML17,
pathname absence, empty process lists, and rounded device-memory readings alone
are never inactive-charge proof. No driver load/build or live qualification is
performed by this package.

CPU verification and offline rendering:

```sh
python3 -m unittest discover -s platform-staging/gpu/qualification/native-import-guard -p 'test_readonly_cap.py'
CPS_R615_SOURCE=/tmp/cps-r615-import-primary/tree python3 -m unittest discover -s platform-staging/gpu/qualification/native-import-guard -p 'test_guard.py'
python3 platform-staging/gpu/qualification/native-import-guard/render_patch.py --readonly-cap-inventory --render --source /tmp/cps-r615-import-primary/tree --output /private/new-readonly-cap.patch
```

The renderer verifies every pristine NVIDIA615.71.09 input SHA and uses
exclusive output creation. The output is source for independent review and
canary module qualification, not permission to load it.
