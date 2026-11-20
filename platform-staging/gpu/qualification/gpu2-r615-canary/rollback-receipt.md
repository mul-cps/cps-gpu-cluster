# GPU2 guard-test rollback receipts

The original R615 UVM module was independently observed restored at
2026-10-08 15:23:55 UTC. The original operator-owned R580 driver was Ready
by 15:29 UTC; normal GPU operands and the uncordoned node were independently
observed Ready at 15:32:45 UTC. This observer made no live changes.

`rollback-before.json` records the fresh guarded-module baseline and binds
the root operator's private node, Pod and driver DaemonSet baseline hashes.
`uvm-review-original-restored.json` preserves the subsequent full read-only
module, holders and runtime receipt; `uvm-original-restore-summary.json`
records the checked comparison and hashes of the operator's actual restore
receipt and log.

The loaded original UVM source version is `2CA5427BFF504A8F70EEAE8`, with no
managed-mmap guard parameter, HMM enabled (`uvm_disable_hmm=N`), ATS=1,
builtin tests=0 and SAM migration disabled. Installed original UVM and core
files retain their SHA256 values `05c2e1319dacdca062bfddc4368be02b66307e0cda31abcd7d28fb37eeefff01`
and `94df0cd9b062ef42091a4f2639438b3596c6a49bcb1b56640ac6ef0f792f2020`.
The R615 core source version and core/modeset load addresses did not change.
The UVM reference count is zero and no UVM client FD remains. Both A100s
retain current and pending MIG mode Disabled.

The K3s agent PID/start ticks remain `1457864/810395303`; containerd remains
`1457904/810395495`. These establish continuity through the UVM-only phase,
after the earlier full-driver maintenance already restarted the runtime.
All baseline GPU2 CPU/PVC Pod UIDs still match and are Ready. The GPU1/3/4
driver Pod UIDs, image IDs, readiness and restart counts match their
baseline. The separately absent GPU1 notebook and historical GPU2 Spegel
restart remain recorded; their cause is not inferred.

The separate 5 GiB Torch helper received independent source review and
passed its four focused CPU tests: it requires an actual positive NVML
baseline and exact native-cap readback, accepts only typed OOM or integer
CUDA error 2, and never touches an unexpectedly successful oversized
allocation. The guard implementation worker owns the second live matrix
receipt and fresh 120-second peer coverage.

`r580-restored.json` verifies the original driver image, DaemonSet UID and
unchanged spec hash, both A100 UUIDs on 580.95.05 with current and pending
MIG Disabled, and removal of the owned CDI and stray file. The full
timestamped installer log is preserved in `r580-restored-driver.log`.
`r580-consumers-initial.json` preserves consumer labels restored while the
node was still cordoned; `r580-operands-restored.json` records the later
Ready GPU operands and uncordoned node. The normal operator validator's
driver, toolkit, CUDA and plugin init containers all completed successfully.

The toolkit initially held a stale R615 driver-root bind and had never
started its main container. The root operator recreated only that GPU2
toolkit Pod. Its subsequent setup restarted K3s agent/containerd to
`1833399/811083578` and `1833446/811083765`. All baseline GPU2 CPU/PVC Pod
UIDs remain unchanged and Ready at 15:34 UTC. Spegel's registry container
restart count is 2 versus the original 0; the remaining baseline CPU/PVC
container restart counts match. GPU1/3/4 driver Pod UIDs, image IDs,
readiness and restart counts remain unchanged.
`r580-toolkit-recovery.log` records the toolkit sending and successfully
delivering SIGHUP to containerd at 15:31:04 UTC.

The original driver firmware directory remains empty. The normal R580
installer warned about missing GSP files there but retained the independent
firmware search path `/run/nvidia/firmware-r615-canary`, whose two staged
R580 GSP hashes were verified. This directory and search path remain a
necessary temporary recovery deviation; removing them before a persistent
firmware repair would break the next cold module load. No additional core
reload was needed for this receipt.

`rollback-final-summary.json` binds the raw observer artifacts and root
operator's private rollback receipt hashes. `rollback-cleanup-verification.json`
also independently verifies that both owned extraction Jobs and Pods,
the R615 canary DaemonSet/Pod, and all UVM QA namespace Pods are absent.
The observer package passes
all 18 tests. Tenant isolation is not qualified by these bounded
trusted-code tests; the experimental guard is no longer loaded.
