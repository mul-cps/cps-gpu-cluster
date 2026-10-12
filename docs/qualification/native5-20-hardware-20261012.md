# Dynamic native GPU memory caps: 5/20 GiB hardware results

Status: controlled hardware tests passed on 12 October 2026; general group GPU access remains disabled.

These tests exercised one isolated A100 on `k3s-wk-gpu2` with the already deployed R615 615.71.09 driver and MIG disabled. Root created fresh, owned cgroups, assigned exact native limits before allowing ordinary UID 1000 / GID 100 CUDA clients to run, and sampled native accounting. No driver rollout, GPU reset, VM reboot, Hub configuration or production compute-policy change was needed.

## Measured results

| Test | Actual result |
| --- | --- |
| 20 GiB virtual-memory allocation | CUDA reported exactly 21,474,836,480 bytes; over-cap VMM allocation returned typed CUDA OOM; recovery and context destruction passed. |
| Ordinary allocation beside a 5 GiB peer | 19,968 MiB held before typed OOM at 20,224 MiB; an untouched 20,736 MiB request was denied. The independent peer verified 100 kernels, including 20 during the OOM-to-recovery interval. |
| Short two-client MPS check | 19 GiB held for 10 seconds under one 20 GiB group cap; typed OOM, both recovery clients and private daemon shutdown passed. |
| Sustained two-client MPS and independent 5 GiB peer | 19 GiB held for 120.200713522 seconds; 479 verified two-client kernel ticks. The independent peer completed 933 ticks across 140.283034456 seconds, continuing beyond daemon shutdown. |
| Native accounting during sustained MPS | 279 samples retained exact 20/5 GiB limits. Maximum MPS charge was 20,314.406 MiB; maximum combined charge was 20,794.533 MiB, below the 25,600 MiB combined cap. |
| Memory-import controls | Same-cgroup IPC and VMM imports succeeded, including three seconds of retained VMM backing after exporter references were released. Both cross-cgroup directions returned exactly CUDA error 800 (`NOT_PERMITTED`) for IPC and VMM; all other CUDA operations and cleanup succeeded. |

Every accepted run observed zero native charge and no remaining processes before restoring exact unlimited defaults (soft 0, hard UINT64_MAX) and removing its owned cgroups and files. Final GPU accounting reported zero workload memory. The sustained MPS run completed at **08:32:11 UTC**; the import controls completed at **10:55:26 UTC**. These are dated measurements, not live telemetry.

## Fast test-driven loop

The initial launcher failed before executing CUDA because of file permissions, then `/run` being mounted `noexec`. The launcher was corrected to use an owned executable directory under `/var/tmp`; caps were cleared after both failed attempts. A cross-cgroup import initially appeared to fail. Same-cgroup positive controls then distinguished functioning imports from enforced cross-cgroup denial. No unrelated test framework or driver change was added to clear these failures.

## Qualification boundary

These results establish native memory-cap behavior and MPS concurrency on this one GPU. They do not establish a 20 GiB Hub start/Stop/restart cycle, arbitrary workspace approval, the whole eight-GPU fleet, MPS compute-share enforcement, cross-Hub same-person reservation races, PyTorch behavior or release acceptance. The earlier 5/10 GiB Source pilot remains separate evidence. General access must pass its corresponding application and authorization gates before activation.

The machine-readable companion records hashes of the exact retained private stdout, command receipts and executed host sources. Raw artifacts remain in the operator's protected qualification evidence directory; they contain no user-submitted workloads and are not executed by public pull-request runners.
