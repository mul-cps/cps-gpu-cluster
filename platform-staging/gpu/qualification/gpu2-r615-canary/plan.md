Root is running a controlled GPU2-only R615 canary to measure the documented
managed-memory isolation gap. MIG is explicitly excluded: both current and
pending MIG modes must stay Disabled. The earlier MIG document is historical
research, not an active option. No isolation capability is accepted before the
actual allocation, Managed-memory, and independent heartbeat tests complete.

This worker performs read-only live audits and source/render changes. Root owns
the cache fills, private rollback journal, GPU2 cordon/operand exclusions and
canary application. Driver reload and rollback remain separate runtime gates.

The live operator is v25.10.0 (Fleet/Helm revision 105). ClusterPolicy uses the
legacy R580 driver DaemonSet; `useNvidiaDriverCRD=false`. That driver DaemonSet
is `OnDelete`, although the policy's general daemonset strategy says RollingUpdate.
The NVIDIA driver CRD v1alpha1 exists, serves `nodeSelector`, and has no instances.
It supports different node pools, but changing global driver management is a
separate migration. The v25.10 source registers its CRD reconciler unconditionally,
while its generated CRD driver Pods also require `gpu.deploy.driver=true`.
Do not create an overlapping CR or switch global management during this canary.
See the [NVIDIA driver CRD documentation](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/25.10/gpu-driver-configuration.html).

The candidate image exists in NGC; manifest metadata only was fetched:

- Version: `615.71.09-ubuntu24.04`, created 2026-09-21.
- Index: `sha256:0ed39c3e75c219954ba81be558c9aa0e6abbfa838c0f60d61bf9a139776fa186`.
- Linux amd64 child: `sha256:bc7572b7f14177c467e4dd8b66c4f4535f462ea9cf6a65cebd7603cc966ebbd7`.
- Driver-container source: `575c9011c4fa4b94200c56818b1f97cdbcf610af`.
- Current R580 rollback: `nvcr.io/nvidia/driver@sha256:41515698692bd5e192186e620b65717af960a66d22dbb5a06e3656575a5d9148`.
- Existing driver-manager v0.9.0: `sha256:a6c12abacc9c4f51d3653c90fcad32f19799069889338601407eba05fea4ba18`.

`render.py` copies only the current driver Pod shape into a new DaemonSet with a
unique selector/owner label and exact hostname `k3s-wk-gpu2`. It pins the driver
digest and omits driver-manager after verified manual quiescence. It uses an
independent `/run/nvidia/firmware-r615-canary` host directory; a tiny init sets
the kernel firmware search path there. Save the previous path in the private
root rollback journal first. It only reads and renders;
it has no apply path. The new DS does not use the operator's driver component
label, preventing its automatic upgrade controller from selecting this fixture.
The renderer guards the original DaemonSet UID and canonical specification hash;
status/resourceVersion churn is allowed, source specification changes are not.
This candidate is intentionally a temporary standalone
canary, with the original Fleet-managed source unchanged.

The target is Ubuntu 24.04.3, kernel 6.8.0-134-generic, two A100 PCIe 40 GB devices.
Its UID is `3336cdd5-d245-436e-b57c-2f66c6dcaa41`. It has 55 running Pods,
including CPS Hub PostgreSQL, CPS admin and Loki PVC consumers, plus Longhorn
storage processes. Their exact UIDs are captured in `preflight.json`. A drain,
reboot, K3s/containerd restart or broad DaemonSet image change is excluded.
Idle GPU/MPS status must be rechecked immediately before a maintenance step;
earlier root read-only checks are not a future idle guarantee.

Root executes these bounded steps with a private rollback journal:

1. Fresh-read target UID/kernel, both GPUs' process lists and MPS clients, KAI
   reservations, GPU workloads, all CPU/PVC Pod UIDs and health. Refuse if any
   user GPU client exists or protected GPU1/3/4 driver/user Pod state drifted.
   Verify kernel headers/build dependencies, module signing/Secure Boot state,
   R615 container build/unload behavior and current module references first.
2. Cordon only GPU2 without eviction. Save its exact labels/annotations. Change
   GPU2 `accelerator` temporarily from `nvidia` to a maintenance value: the
   standalone MPS DS selects this label. Set only GPU2 deployment labels for
   device-plugin, DCGM exporter, GFD and operator-validator false.
   Leave MIG-manager unchanged; do not change MIG mode, instances or profiles.
   Leave toolkit and every CPU/storage Pod running. Verify these labels survive
   operator reconciliation and all GPU2 GPU-consumer processes/FDs disappear.
   If node labels are reconciled back, stop and restore; do not edit shared DSs.
3. Set only GPU2 `nvidia.com/gpu.deploy.driver=false`; wait for the one legacy
   driver Pod to leave. Verify GPU1/3/4 driver Pod UIDs/digests are unchanged.
   Wait for all NVIDIA module references to be clear. If unloading requires
   killing a CPU/PVC process, draining or rebooting, abort and restore R580.
4. Save the original firmware search path privately. Apply the reviewed uniquely
   named node-pinned canary DS without driver-manager. Root must have verified
   actual NVIDIA modules and device FDs absent first. Capture actual image ID, build log,
   module type/version and `nvidia-smi`. Bound the install by a root-agreed timeout;
   if unavailable or unsafe, enter rollback. No automatic retries across nodes.
5. Re-enable only required GPU2 operands. Keep production MPS stopped until an
   R615-compatible MPS binary/control transport is explicitly identified from
   the new driver root or a pinned CUDA13.4 image. The existing v0.18 device-plugin
   image and toolkit v1.18.0 are recorded, not declared new-feature compatible.
   Avoid toolkit/runtime rollout: assess whether GPU2 CDI regeneration is needed
   and review that node-only operation first. Root's CPU-only isolation prototype
   then checks small bounded standard/two-context/Managed allocations and
   independent heartbeat survival. No production admission policy is enabled.
6. Compare CPU/PVC health, Pod UIDs and protected-node baseline throughout.
   Leave the node cordoned until root accepts either the canary or rollback.

Rollback uses only GPU2. Stop owned canary clients and required GPU2 operands;
verify module references clear; delete the owned R615 DS/Pod and wait for its
driver cleanup. Stage the exact R580 GSP files in the independent firmware directory
and preserve that search path through cold580 bootstrap, as described in
[r580-rollback.md](r580-rollback.md). Restore
`gpu.deploy.driver=true` so the unchanged legacy R580
DS recreates only GPU2's driver Pod. Verify its image ID equals the recorded
R580 digest, actual loaded driver is 580.95.05, both GPUs are healthy, and old
MPS control/client behavior returns. Restore only journaled GPU2 labels and
prior cordon state. Verify CPU/PVC Pod UIDs/health and GPU1/3/4 baselines again.
If modules cannot reload without reboot, keep GPU2 cordoned and report the
failure; no reboot is authorized by this plan. Driver-container rollback is
not a proof against irreversible installer behavior, hence source/build and
unload review remains a prerequisite before proceeding.

The first canary included manager v0.9.0: its unconditional operand shutdown
recreated GPU2 toolkit and MIG-manager Pods despite drain/eviction being false.
The same unchanged init exists in legacy R580 restoration, so its effects must
be reviewed before that path. Do not claim toolkit, MIG-manager or containerd
remain unchanged merely from disabled drain flags. The corrected candidate
omits that init and does not change node labels or restart services.

The first R615 install loaded modules but found no GPUs: firmware installation
failed with ENOENT because `/lib/firmware` was backed by
`/run/nvidia/driver/lib/firmware`, inside the driver rootfs that initialization
unmounts. `first-attempt-with-manager.yaml` preserves that attempt. The corrected
independent firmware hostPath and explicit search-path init avoid that self
dependency; actual firmware files, device health and capabilities still require
runtime verification. Source references and bounded receipts are in
`source-and-maintenance-receipt.md`.

Released R615 availability does not prove CUDA13.4, new MPS memory controls,
new context-isolation or dmem behavior on this installed A100/kernel. Those are
separate actual capability and workload receipts owned by the root/researcher.
Source references: [operator main](https://github.com/NVIDIA/gpu-operator/blob/v25.10.0/cmd/gpu-operator/main.go),
[CRD driver template](https://github.com/NVIDIA/gpu-operator/blob/v25.10.0/manifests/state-driver/0500_daemonset.yaml),
[node-pool selectors](https://github.com/NVIDIA/gpu-operator/blob/v25.10.0/internal/state/nodepool.go),
[upgrade controls](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/25.10/gpu-driver-upgrades.html).
