# GPU isolation findings

Status: dynamic ordinary-use accounting passed one controlled run; the earlier
deliberate bypass remains reproducible. Fractional GPU profiles remain disabled
pending the integration and remaining qualification gates.

## Current dynamic-sharing direction — 2026-10-07

The operator requires dynamic resource sharing and rejected MIG. KAI/HAMi/MPS
remains the selected runtime. The earlier findings below are retained as
evidence of the software enforcement boundary, rather than a hardware migration
proposal.

The controlled `dyn071421c` run used a fixed private accounting-file mount,
verified the loaded HAMi binary and actual 5120 MiB indexed quota, and ran two
CUDA children on the independent peer's physical GPU. A second 3 GiB allocation
was denied while the first remained active; after the first freed its allocation,
the second succeeded. All 16 tested allocation rounds had actual overlap, with
one success and one OOM each. The independent peer kept making progress.
See the [complete controlled result](../../scheduler/qualification/dynamic-cache/RESULTS.md).

This establishes bounded ordinary same-workspace accounting and reuse after
freeing memory. It does not qualify deliberate runtime tampering, every CUDA
allocation API, crash recovery, the 10/20 GiB profiles, or the final generated
Hub/Argo/JobSet Pods. Exact runtime settings, private cache initialization and
MPS mounts are being integrated in the shared application; their approved image,
admission exceptions and live group reservation/revocation gates still require
qualification. No GPU mode or MPS daemon setting was changed in this run.

## Earlier deliberate-bypass investigation

The controlled combined HAMi/MPS probe on the same physical GPU denied an ordinary 6 GiB allocation under a nominal 5 GiB profile while its peer continued. Changing the client MPS pipe path, increasing the HAMi environment limit and recreating the writable HAMi cache allowed the 6 GiB allocation. This is a runtime bypass, not a gateway admission omission. Evidence: operator-private `2026-10-06/gpu-runtime/combined-mps-reproducible.json`.

On 2026-10-06 the live `gpu-operator/mps-control-daemon-standalone` DaemonSet command was inspected. It runs `nvidia-smi -c DEFAULT` every five seconds for all GPUs. A saved specification is `gpu-runtime/mps-daemon-current.json`. Consequently, changing a client MPS path can fall back to direct CUDA. Admission and fixed startup environment variables cannot prevent arbitrary code inside a notebook from changing its child process environment.

[NVIDIA's MPS documentation](https://docs.nvidia.com/deploy/mps/latest/when-to-use-mps.html) recommends `EXCLUSIVE_PROCESS` mode so the MPS server becomes the CUDA arbitration point. Its legacy limits apply per client process, using server-wide ceilings with client-side further constraints. That does not by itself prove an aggregate per-workspace allowance across multiple processes, or distinct trusted 5/10/20 GiB ceilings for mixed profiles on one server. HAMi's userspace interception and writable cache remain relevant bypass surfaces.

The next controlled investigation must use a quiescent, reserved GPU and restore its original settings. It must prevent the existing DEFAULT-mode loop from undoing the test, verify MPS client UID compatibility, reject direct CUDA bypass while an MPS server owns the device, and exercise multiple processes against the aggregate workspace budget. Exclusively allocated batch/debugging workloads also need an explicit mode transition with no active shared clients. A single successful 5 GiB process test cannot qualify the mixed-profile platform.

No compute mode or production daemon settings were changed during this inspection. No cooperative-use trust assumption, MIG conversion or MPS v3 migration has been substituted for the original v1 requirements.

## Quiescent-node preflight

Read-only checks on `k3s-wk-gpu3` found no active GPU Pod allocations/reservations, no CUDA compute processes and no active MPS server. Both A100s were in DEFAULT mode with 1 MiB used. The daemon reported default device pinned-memory limits of `5G` on each GPU and active thread percentage `12.0`. Evidence: `gpu-runtime/mps-preflight-current.json`.

These defaults are not mixed-profile qualification: larger client environment settings cannot raise the server ceiling, and multiple client processes require aggregate accounting beyond individual limits. The DEFAULT-mode reset loop is a separate child of the daemon wrapper; any controlled exclusive-mode test must fence that loop only on the selected node, reserve the node against new GPU workloads, and restore the loop and compute modes even on timeout. The active CIT GPU session on `k3s-wk-gpu1` remains outside the test scope. No settings were changed in this preflight.

## Aggregate workspace bypass reproduced

A trusted bounded probe on the idle `k3s-wk-gpu3` created one nominal 5 GiB Pod and two CUDA processes, each allocating 3 GiB. Before starting each process it recreated the regular writable HAMi cache. Both allocations were simultaneously live on the same GPU, exceeding the workspace allowance at 6 GiB while each process stayed below the daemon's 5 GiB ceiling. Evidence: `gpu-runtime/aggregate-probe-report.json`, `aggregate-probe-pod.json`, `aggregate-probe-final-pod.json` and `aggregate-probe.log`. The Pod used the existing digest-pinned operator fixture, and no compute mode or daemon limit was changed.

After collecting evidence the completed Pod was deleted. MPS reported no remaining clients; its idle server retained only approximately 36 MiB per GPU. This independently demonstrates that exclusive mode alone cannot solve aggregate workspace enforcement. A trusted aggregate accounting mechanism must survive cache replacement and multiple processes, alongside forced MPS mediation and mixed-profile support. GPU profiles remain disabled.

## Upstream enforcement boundary confirmed

The official [HAMi FAQ](https://project-hami.io/docs/faq) describes HAMi-core as userspace library interception with soft CUDA-level memory enforcement. It explicitly excludes applications bypassing the CUDA library, including direct-driver applications, and contrasts this with MIG hardware partitioning. The [HAMi-core README](https://github.com/Project-HAMi/HAMi-core) documents environment-controlled limits and deletion of the local cache after changing limits. These sources support treating the reproduced cache/child-process bypass as an enforcement-boundary issue rather than a missing profile dropdown or admission field. They do not prove that every possible HAMi hardening is ineffective.

Live read-only verification still found the existing MPS DaemonSet at generation 3 with four desired/ready nodes, using device-plugin image v0.18.0. No GPU mode, daemon setting or policy qualification flag was changed. Evaluating hardware isolation requires a reviewed architecture decision because mixed 5/10/20 GiB profiles and exclusive batch capacity must remain accounted for. MIG has not been enabled or accepted as a replacement.
