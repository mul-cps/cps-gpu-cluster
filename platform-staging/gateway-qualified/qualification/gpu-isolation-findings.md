# GPU isolation findings

Status: failed; fractional GPU profiles remain disabled.

The controlled combined HAMi/MPS probe on the same physical GPU denied an ordinary 6 GiB allocation under a nominal 5 GiB profile while its peer continued. Changing the client MPS pipe path, increasing the HAMi environment limit and recreating the writable HAMi cache allowed the 6 GiB allocation. This is a runtime bypass, not a gateway admission omission. Evidence: operator-private `2026-10-06/gpu-runtime/combined-mps-reproducible.json`.

On 2026-10-06 the live `gpu-operator/mps-control-daemon-standalone` DaemonSet command was inspected. It runs `nvidia-smi -c DEFAULT` every five seconds for all GPUs. A saved specification is `gpu-runtime/mps-daemon-current.json`. Consequently, changing a client MPS path can fall back to direct CUDA. Admission and fixed startup environment variables cannot prevent arbitrary code inside a notebook from changing its child process environment.

[NVIDIA's MPS documentation](https://docs.nvidia.com/deploy/mps/latest/when-to-use-mps.html) recommends `EXCLUSIVE_PROCESS` mode so the MPS server becomes the CUDA arbitration point. Its legacy limits apply per client process, using server-wide ceilings with client-side further constraints. That does not by itself prove an aggregate per-workspace allowance across multiple processes, or distinct trusted 5/10/20 GiB ceilings for mixed profiles on one server. HAMi's userspace interception and writable cache remain relevant bypass surfaces.

The next controlled investigation must use a quiescent, reserved GPU and restore its original settings. It must prevent the existing DEFAULT-mode loop from undoing the test, verify MPS client UID compatibility, reject direct CUDA bypass while an MPS server owns the device, and exercise multiple processes against the aggregate workspace budget. Exclusively allocated batch/debugging workloads also need an explicit mode transition with no active shared clients. A single successful 5 GiB process test cannot qualify the mixed-profile platform.

No compute mode or production daemon settings were changed during this inspection. No cooperative-use trust assumption, MIG conversion or MPS v3 migration has been substituted for the original v1 requirements.
