# Automatic native-cap node qualification adapter

Status: bounded qualification prototype / production disabled. No MIG.

This directory connects the released-source transaction core to actual
Kubernetes Pod/Node reads, CRI inspection, host proc/cgroup files and the
reviewed R615 NVML ABI. It does not load a driver, change MIG mode, install a
DaemonSet, grant profiles or enroll users. Root owns the isolated GPU2 canary
and must preserve its protected CPU/PVC workloads and restoration journal.

Pinned inputs are the compute core from commit
`4e5438ebd25ba42e4a2b2e8ae2db605313604436` (SHA256
`2c9770188a79406c674560616a8d9da8f4dafa275f0644d9669dfab001e7690e`)
and `scheduler/qualification/r615-pod-cap/pod_cap.py` from cluster `311d265`
(SHA256 `5c84ab668dd276b0216199a964f42886712af9225f9fc702740bfa9bb361a39f`).
`poll.py` checks both hashes before execution. The adapter imports the manual
helper into an isolated module and changes its gate constant in memory to
`cps-native-cap-gate`; the reviewed helper source is unchanged.

## Root authority and usage

Use the verified R615 driver container in host PID namespace. Host cgroups are
mounted at `/sys/fs/cgroup`; host proc identities are visible through `/proc`.
The root-owned host directories `/run/cps-native-gpu`, `receipts`, `authority`,
`authority/intents`, `authority/bootstrap` and `authority/journal` must all have
mode `0700`. The intent, epoch, bootstrap, journal and gate receipt files have
mode `0600`. None of these directories may be writable by users. Only gate
receipt and current epoch mounts are supplied read only to the approved CPU
gate; the private intent/bootstrap/journal directories are never mounted there.

Root enrolls each **actual** admitted Pod UID in
`authority/intents/<pod-uid>.json`, containing the exact `CapIntent` fields.
An admitted, defaulted full Pod spec hash must be computed before user gate
execution; an annotation alone is not admission authority. Each intent binds
the actual node UID, canonical physical GPU UUID, fixed cap and policy hash.
Changing an enrolled intent is refused, including changing its cap in place.

`authority/driver-generation` is a raw canonical UUID issued only after root
verifies the exact loaded core/UVM modules, all guard parameters and GPU health.
It must be invalidated before approved module maintenance. A module address
or version string is not a reload epoch. Root maintenance must use the same
exclusive journal mutation domain, stop/quarantine native workloads and issue
a new nonce after verification. External root changes outside that protocol
are not claimed to be race-free.

The default command is inert and performs no API, NVML or process calls:

```sh
python poll.py
```

Root can run a bounded canary loop after verifying module and source hashes:

```sh
env PYTHONHOME=/proc/1/root/usr PYTHONNOUSERSITE=1 \
  /proc/1/root/usr/bin/python3.12 /var/tmp/cps-native-gpu/poll.py \
  --execute --qualification \
  --controller-module /var/tmp/cps-native-gpu/cps_compute/native_gpu_controller.py \
  --manual-helper /var/tmp/cps-native-gpu/pod_cap.py \
  --node k3s-wk-gpu2 --iterations 180 --interval 1
```

Paths may be supplied explicitly; the default state path from the container is
`/proc/1/root/run/cps-native-gpu`. The projected service account is used only by
the host controller. urllib uses its Kubernetes CA and no environment proxy;
Pod deletion carries an exact UID precondition. Credentials are never passed
to the gate or workload. Commands use fixed argument arrays and timeouts,
without a shell. Root controls enrollment and the source paths.

## Ambiguous native bootstrap

NVML code 3 is preserved as `unset-or-unsupported`; it is never converted to
`None`. Only a fresh, still-blocked gate with no previous user init/main start
and no GPU client in its Pod-parent may bootstrap. A separate exact identity
`bootstrap/prepared` record is durably saved before writing explicit unlimited
limits. That write must succeed and read back exactly `{soft:0, hard:UINT64_MAX,
used:0}`. Only then is the bootstrap marked applied and the compute core may
prepare and assign its actual restrictive cap.

An existing finite limit is never reset by bootstrap. An unsupported setter,
ambiguous post-set readback, changed PID/cgroup/epoch or stale receipt keeps
the gate blocked. A crash after the unlimited write resumes only from the
exact prepared bootstrap identity. Bootstrap is not GPU qualification or a
permission grant; no CUDA code runs in the CPU gate.

After successful parent support/readback, the controlled writer permits a
descendant's inherited equal-parent or unlimited limit and rejects differing
finite limits or unknown NVML errors. The getter cannot prove whether an
identical value is an exact child override or inherited; the experiment relies
on sole root mutation authority, nonroot workloads and aggregate-tree OOM
tests. It does not claim isolation against another hostile host administrator.

## Lifecycle and limitations

Every seal rechecks exact Pod/CRI/PID-start/boot/cgroup inode, root maintenance
epoch, driver/guard health and native readback. A cgroup descriptor remains
open across native writes and its identity is checked on both sides. Receipt
publication uses Linux `renameat2(RENAME_NOREPLACE)` and file/directory `fsync`,
so it neither overwrites foreign content nor exposes a temporary extra link.

Sealed reconciliation uses the surviving Pod-parent after the first gate
exits. Drift or missing epoch/health conditionally deletes only the expected
Pod UID, revokes only its matching owned receipt and retains the cap. Failure
to stop is surfaced. This qualification callback does not revoke real Hub
Shares or browser sessions; those are required production integration gates.

Cleanup requires expected Pod gone/terminal, recursive `cgroup.procs` and
`cgroup.threads` empty, kernel `populated=0`, native used bytes zero and no
remaining client on the selected GPU. All GPU clients are conservatively
treated as possible retained import owners; cleanup waits even for an
otherwise legitimate peer. `retained-awaiting-stop` logs reflect this
expected deferral. Missing cgroups are retired without a driver write to a
path that could name a replacement. No timer or cancellation request clears
the cap. Boot/driver epoch changes block cleanup until reviewed recovery.

The loop reads enrolled root intents each iteration and resumes pending
journals only when the original enrollment remains available. It retains all
observed errors in its final result; it cannot report a clean qualification
after an ignored failure. GPU tasks, imports, all permitted images, driver and
workload restarts and compute-sharing mode still require actual qualification.
External MPS remains disabled for this fresh-CUDA pilot.

## CPU verification

Supply the exact pinned core source; tests fail rather than silently skip if
that dependency is missing:

```sh
CPS_NATIVE_CONTROLLER_SOURCE=/path/to/cps_compute/native_gpu_controller.py \
  python -m unittest discover \
  -s platform-staging/gpu/qualification/native-cap-controller \
  -p test_node_backend.py -v
```

Tests inject fake API/CRI/NVML operations and temporary proc/cgroup/state
trees. They run no live requests, device calls or privileged writes. CPU
results establish adapter behavior; they are not hardware evidence.
