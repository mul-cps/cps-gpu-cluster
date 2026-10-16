# Bounded CUDA VMM descriptor isolation qualification

These are trusted operator qualification tools, not a user service or CI GPU job.
Every executable defaults to inert behavior and requires `--execute`. Public pull
requests run CPU protocol tests only; they must never execute these probes on a
cluster runner.

`endpoint.py` uses the CUDA Driver API inside an already capped notebook. Its
same-parent positive control maps a 64 MiB allocation and checks its contents.
The cross-parent test attempts import only: an unexpectedly accepted handle is
released without mapping or touching it. Both endpoints verify ordinary kernel
progress and explicitly clean up their own objects. An external coordinator must
supply the reviewed trial, parent/GPU identity, cap and lifecycle; this directory
does not create workspaces or assign entitlements.

`process_attribution.py` derives actual host process identity and checks the
protected sealed parent record. `fd_relay.py` is a CPU-only root transport: it
rechecks PID/start/cgroup/epoch/descriptor identity, duplicates the exact export
with `pidfd_getfd`, enters the importer's network namespace, permanently drops to
UID 1000/GID 100, and passes one descriptor over a trial-specific abstract UNIX
socket. It creates no mounts, routes or firewall rules and calls no CUDA API.

The collector, validator and transport correlate a contiguous kernel-message
window with the exact API, GPU, lifetime and host TGID. IPC retains its existing
client-kind requirement. VMM accepts the defined three-bit client diagnostic
flags; this does not relax API, reason/status, identity or sequence checks. Root
witness archives stay private and must not overwrite unrelated operator files.
The witness modules derive from the previously frozen IPC qualification tools;
CUDA ctypes layouts derive from the reviewed CUDA 13.4 VMM probe ABI.

The current-image evidence is recorded in
[the final isolation receipt](../../native-group-pilot/prospective-pair/current531-final-isolation-20261016.json).
It covers GPU2, notebook image `531027c8`, and 5/20 GiB parents. It does not qualify
all GPUs, the 10 GiB runtime, other images, automatic MPS lifecycle or production
rollout. It requires Linux x86-64, the qualified native driver/cgroup stack and a
trusted root observer; none of these tools belongs in ordinary notebooks.

CPU tests exercise descriptor ownership/cleanup and credentials, strict
attribution inputs, inert defaults, ABI layout and witness tampering. Run with
the compute project's Python/test dependencies:

```sh
python -m pytest -q platform-staging/gpu/qualification/native-vmm
```
