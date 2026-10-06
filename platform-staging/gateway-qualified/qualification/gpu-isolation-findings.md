# GPU isolation findings

Status: failed; fractional GPU profiles remain disabled.

The controlled combined HAMi/MPS probe on the same physical GPU denied an ordinary 6 GiB allocation under a nominal 5 GiB profile while its peer continued. Changing the client MPS pipe path, increasing the HAMi environment limit and recreating the writable HAMi cache allowed the 6 GiB allocation. This is a runtime bypass, not a gateway admission omission. Evidence: operator-private `2026-10-06/gpu-runtime/combined-mps-reproducible.json`.

On 2026-10-06 the live `gpu-operator/mps-control-daemon-standalone` DaemonSet command was inspected. It runs `nvidia-smi -c DEFAULT` every five seconds for all GPUs. A saved specification is `gpu-runtime/mps-daemon-current.json`. Consequently, changing a client MPS path can fall back to direct CUDA. Admission and fixed startup environment variables cannot prevent arbitrary code inside a notebook from changing its child process environment.

[NVIDIA's MPS documentation](https://docs.nvidia.com/deploy/mps/latest/when-to-use-mps.html) recommends `EXCLUSIVE_PROCESS` mode so the MPS server becomes the CUDA arbitration point. Its legacy limits apply per client process, using server-wide ceilings with client-side further constraints. That does not by itself prove an aggregate per-workspace allowance across multiple processes, or distinct trusted 5/10/20 GiB ceilings for mixed profiles on one server. HAMi's userspace interception and writable cache remain relevant bypass surfaces.

The next controlled investigation must use a quiescent, reserved GPU and restore its original settings. It must prevent the existing DEFAULT-mode loop from undoing the test, verify MPS client UID compatibility, reject direct CUDA bypass while an MPS server owns the device, and exercise multiple processes against the aggregate workspace budget. Exclusively allocated batch/debugging workloads also need an explicit mode transition with no active shared clients. A single successful 5 GiB process test cannot qualify the mixed-profile platform.

No compute mode or production daemon settings were changed during this inspection. No cooperative-use trust assumption, MIG conversion or MPS v3 migration has been substituted for the original v1 requirements.

## Quiescent-node preflight

Read-only checks on `k3s-wk-gpu3` found no active GPU Pod allocations/reservations, no CUDA compute processes and no active MPS server. Both A100s were in DEFAULT mode with 1 MiB used. The daemon reported default device pinned-memory limits of `5G` on each GPU and active thread percentage `12.0`. Evidence: `gpu-runtime/mps-preflight-current.json`.

These defaults are not mixed-profile qualification: larger client environment settings cannot raise the server ceiling, and multiple client processes require aggregate accounting beyond individual limits. The DEFAULT-mode reset loop is a separate child of the daemon wrapper; any controlled exclusive-mode test must fence that loop only on the selected node, reserve the node against new GPU workloads, and restore the loop and compute modes even on timeout. The active CIT GPU session on `k3s-wk-gpu1` remains outside the test scope. No settings were changed in this preflight.
