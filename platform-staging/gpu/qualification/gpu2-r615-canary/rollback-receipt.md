# GPU2 guard-test rollback receipts

The original R615 UVM module was independently observed restored at
2026-10-08 15:23:55 UTC. R580 driver/operator/node recovery remains pending
in this checkpoint. This observer made no live changes.

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

The observer package passes all 18 tests. Tenant isolation is not qualified
by these bounded trusted-code tests. Consumer labels and the original
cordon state must be restored separately, with uncordon last, after actual
R580 hardware recovery and operator readiness.
