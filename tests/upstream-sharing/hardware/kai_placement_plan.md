# Stock KAI placement witness — prepared, not executed

Scope: selected GPU2 only. This is trusted administrator placement qualification, not the normal Hub/QA workflow or business allowance acceptance. It deliberately uses the existing cps-interactive Queue directly. No user grant, accounting allowance, scheduler configuration, node label, driver, operator, GPU reset or BindRequest mutation is part of the fixtures. Root owns temporary eligibility and the execution window. Current NRI fault testing must finish first.

`kai_placement_render.py` has **no execution path**, subprocess calls or Kubernetes client. It renders15 Pods, one ConfigMap and an ordered JSON sequence. This is the reviewable input for the root-coordinated runner; rendering does not satisfy placement acceptance. UUID arguments are an allowed physical pair for later verification, never selectors or requested device annotations. Generated names A/B follow the scheduler's first actual placement, rather than imposing a device choice.

## Released source and actual read-only prerequisites

KAI source `/tmp/cps-upstream-20261116/kai-source` tag v0.18.1, commit bdf434e5e9201cccf4e05fad04d814363653f692:

- docs/gpu-sharing/README.md:246–279 documents per-container request/limit Kubernetes quantities; docs/gpu-sharing/gpu-memory.yaml shows schedulerName=kai-scheduler and kai.scheduler/queue label.
- pkg/binder/plugins/nvfractions/nv_fractions.go:45–78 obtains scheduler-reserved GPU IDs, qualifies the device-plugin CDI kind and writes the actual per-container devices annotation. Fixtures must not preseed this output.
- pkg/apis/scheduling/v1alpha2/bindrequest_types.go:14–46 carries podName, selectedNode, receivedGPU and selectedFractionalGpuGroups. Capture scheduler-created objects; never write them.
- pkg/binder/common/utils.go:10–12 classifies ReceivedResourceType=Fraction as shared. The seed instead requests stock nvidia.com/gpu:1, allowing the stock device plugin to reserve an entire card.

Read-only current inventory: GPU2 Node UID3336cdd5-d245-436e-b57c-2f66c6dcaa41, nvidia.com/gpu.memory=40960MiB, allocatable nvidia.com/gpu=2. Existing cps-interactive Queue v2 has GPU quota/limit8; no Queue changes required. Existing PriorityClass cps-peer-protocol-20261108 has value-1000 and preemptionPolicy Never; Pods also request Never. Device-plugin strategy is cdi-annotations,cdi-cri. Recheck immediately before execution rather than assuming this snapshot persists. Check KAI respects the retained low-priority/nonpreempting fixture selection; no existing workload may be displaced.

Selector is exact hostname plus **existing policy key** cps.unileoben.ac.at/upstream-gpu-sharing=qualified. Root alone may temporarily qualify/uncordon the selected worker after other gates. Rendered Pods have no maintenance toleration and cannot bypass that gate. Verify no other worker has the qualification label; hostname also prevents escape. Do not run a command that creates every rendered manifest together: the order matters.

## Forced availability without requesting a UUID

The seed is a stock whole-GPU1 admin Pod, holding only1MiB physically. Its actual assigned UUID defines B; the other UUID is A. Discover via its device-plugin CDI/CRI device allocation and read-only host/container witness, not NVIDIA_VISIBLE_DEVICES alone.

1. While seed reserves B, create/start A5, A10, A20 sequentially, then guardA5. Each must be scheduler-assigned A. Guard holds only1MiB but its request reserves the last5GiB: A is logically40GiB and B exclusively reserved.
2. Gracefully release/delete seed and wait for its scheduler reservation to disappear. Create B5, B10, B20 sequentially; each must land on B because A remains fully booked. At checkpoint both cards have all three profile sizes, each filling profile−1GiB (32GiB/card) plus guardA1MiB. Retain independent progress for all six payloads.
3. Release/delete only original B profiles, leaving A booked40GiB. Create B20, B10, B5 and guardB5 sequentially. These must land on the original B. This starts the reverse physical/profile order.
4. Release/delete original A profiles+guardA and wait for their reservation cleanup. Create A20, A10, A5; these must land on original A because B now reserves40GiB. Retain six-way coexistence/progress again.
5. Gracefully release/delete the remaining owned Pods and ConfigMap. Verify actual originalUID cleanup, all owned BindRequests/reservations gone, no orphan containers/charges, both cards no clients and at most1MiB used.

A/B are bound once by the initial exclusive seed and never relabelled to excuse a wrong placement. A wrong UUID, extra visible card, Pending timeout or unexpected eviction is a failure, not permission to add a device annotation. Stop on first failure. No force-delete, user workload deletion, per-device reset or configuration retry. The extra5GiB guard is logical capacity booking, not an extra standard profile result. It prevents a new5GiB request fitting the otherwise idle tail; no memory oversubscription assumptions are used. Total peak logical GPU use is2physical cards, peak host guarantee at most8×16GiB=128GiB plus existing daemons. Verify actual free allocatable host memory before execution.

## Root runner guards and evidence contract

Before any creation, retain read-only provenance and reject mismatches:

- Explicit selected node name/IP, NodeUID, current bootID, loaded UVM srcversion exact text; driver image+imageID c3b71557aa17df43faad5a2661d81f1025ba355ac3adf784096de12cd2ef3e73, effective source SHA5648dbfe43957eb257d9efb715906de0fb6caa43458752544221d90db6efdb18, both UVM policy parameters Y.
- Actual /usr/local/bin/k3s outer SHA6ce276301723a902da671058730611591c59b5f016b816f57f2d97b05c88fe2c and actual `/proc/<running-containerd-pid>/exe` SHA0ca3be05fd3fcdd9682e68bbff5821ea15027773404a7e47517b822bcb57387a. Validate PID is the running K3s-owned containerd, not just a file in an old data directory. Retain K3s/containerd versions, required-plugin current setup and successful fault-test evidence reference. CPU-only/no mandatory annotation probes do not prove this guard.
- Exactly the allowed two UUIDs and40960MiB/card, Ready node, released stock KAI0.18.1/NvFractions and independent fractioning0.1.9 ready, no CUDA clients and <=1MiB/card. No user GPU consumers or in-flight starts. Verify all selected resources/UIDs at every phase.

Create objects individually and record returned UIDs immediately. Watch BindRequests **before creation** (namespace-scoped continuous watch for this unique pod prefix) because successful ones may be removed quickly. Record complete non-secret Pod/BindRequest specs/status, NodeUID and scheduler-created receivedGPU/group IDs, actual assignment annotations and admitted CDI. For each payload require selectedNode and Pod.spec.nodeName exactly selectedworker, ownerReference UID matching actualPod where provided, CDI exactly one allowed device and the expected A/B, no caller-authored device annotation in the input. Record actual CRI containerID, OCI CDI/device mappings, process PID and physical GPU matching CID. Retain driver memory-limits actualleaf soft/hard5/10/20GiB, host memory.max16GiB and no restart/OOMKilled status.

Reuse `mixed_profiles_run.py`'s host observer and exact leaf-limit, physical PID, progress and UID-delete witnesses. The derived probe is retained historical SHA d2a4f4cdb9ee1e6c09622a3277fffc711d0be0a2ddd140e74b03e0a20dd02515 with only two explicit edits:600-second start/hold bounds for the crossover (formerly120), and fractional hard+1GiB typedOOM assertion conditional on NVIDIA_GPU_MEMORY_LIMIT existing so the full-GPU seed can use the same fill/free lifecycle. For every fractional payload and guard that variable **must exist**; actual leaf guard verifies it. No library interception or environment variable enforces a limit. The historical ctypes CUDA path performs actual cuMemAlloc/cuMemset/synchronize and repeated progress, then cuMemFree/cuCtxDestroy.

Per-Pod scheduling/Ready timeout60s, typedOOM+fill timeout45s, progress sample6s, graceful release30s and UID-precondition deletion45s; overall run limit600s. Rendered activeDeadlineSeconds900 is a final Kubernetes bound, not permission to wait that long. Maximum600s holding a probe includes cleanup, so release all currently active owned probes together on any failure. Never touch /tmp/start solely for cleanup of an unstarted Pod. Do not delete the ConfigMap until all original owned Pods are gone. Preserve evidence and report cleanup exceptions without force or replacement deletion.

At each coexistence checkpoint every payload must have typedOOM2 above hard+1GiB, successful profile−1GiB allocation/fill and increasing CUDA progress while all six coexist. Retain timestamps+NVML/container process mappings, not solely annotations or a successful BindRequest. Only then claim stock placement and runtime fill for both physical orders. Keep real Hub lifecycle, distributed/teaching/monitoring and application restore gates separate.

## Render command verified (no execution)

```sh
python3 tests/upstream-sharing/hardware/kai_placement_render.py \
  --node k3s-wk-gpu2 --operator-selected-worker k3s-wk-gpu2 --node-ip 10.21.0.43 \
  --gpu-a GPU-16128952-b438-556a-00bb-93039ee24e56 \
  --gpu-b GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6 \
  --expected-boot-id a39cdade-f00d-4cd1-9a81-c290d668194f \
  --expected-module-srcversion 10301D70B8ED1758BC717E9 \
  --run-id kai-place-review --output /tmp/kai-placement-review-render
```

The CLI accepts explicit laterworker identity but guards must be reverified and root must release that one worker; no parallel worker qualification. Only syntax/render/structural checks have run. No GPU work or manifests have been applied.
