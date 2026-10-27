# Exact-image personal MuJoCo measurement prerequisite

Default commands are inert. No hardware qualification has run. These tools do
not publish passed gates or immutable v4 proof, create Pods, start workspaces,
change caps, or modify users/homes. Existing original v3 evidence is retained.

The image is read from retained CIT `jupyterhub-values.yaml:458`:
`harbor.dshl.unileoben.ac.at/cps-users/cps-jupyter-notebook@sha256:1ed46addaed50f1874edec98001a122bd9da219d89e6cfecf1945c7338261c21`.

`prepare.py --render` takes SHA-pinned existing operator/policy documents,
derives the personal profile/resources from the canonical artifact, preserves
both actual existing operator owners/members/PVCs, and emits an offline proposal
for two10GiB operator parents. Requests2CPU/4G, limits8CPU/24G and lifetime come
from that artifact, not another catalog. The exact-image typed candidate has
two slots/20GiB budget, disjoint canonical nonstudent operators and distinct
existing Pods/PVCs. Absent `personal_candidate` retains original v3 bytes and
5315/20 ceilings/budget. Normal Source configuration/grant/registration and
fenced/drained activation are separate Root-reviewed operations. Old531 helper
scripts deliberately retain their original image restrictions; do not pass these
proposals to an old helper by disabling its checks.

After genuine normal starts, `run.py` requires a separately reviewed owned0600
manifest and exact runner/probe/collector hashes. The two actual PodUIDs/spec
hashes/imageIDs, immutable Node+operator references, context and parent cgroup
paths/inode/device must be current. The manifest fields are closed in main():
`version, context, policy, operator, resources, pods, observer, driver_version,
operator_ref, node_ref`. `pods` has `pressure` and `peer`, each with namespace,
name, uid, spec_sha256, cgroup, inode, device. Observer has namespace/name/uid
and exact image_id. Reference objects use existing six-key ConfigMap references.
Context is the existing strict-v4 context; obtain driver/gate/build/epoch from
actual native authority, not the caller's workload. `resources` is the complete
artifact-derived requests/limits mapping. Operator and policy are actual pinned
protected documents; no bearer token values belong in this manifest.

```sh
python -B run.py
python -B run.py --execute --manifest /private/current-targets.json \
  --manifest-sha256 REVIEWED_RAW_SHA256 --runner-sha256 REVIEWED_RUNNER_SHA256 \
  --probe-source /reviewed/cps_compute/personal_qualification_probe.py \
  --probe-sha256 REVIEWED_PROBE_SHA256 \
  --collector-source /reviewed/cps_compute/personal_qualification_collect.py \
  --collector-sha256 REVIEWED_COLLECTOR_SHA256 --output /private/fresh-output
```

Probe dependencies are the image's existing `mujoco`, `numpy`, `PyOpenGL`, CUDA
`torch`, `xpra` and `vglrun`. SDK/Node imports remain stdlib-only for the new tool
modules; GPU dependencies load only during explicit probe execution. Host reader
needs existing root observer, host `/proc`/cgroups/kernel logs and native NVML
R615 ABI. Runner uses the reviewed SDK and existing kubectl configuration.
No dependency installation, image build/pull or driver change is part of a run.

The runner creates only owned private `/tmp/cps-mujoco-*` source/event/ack files
inside the owned operator Pods. Pressure is a real `xpra control :100 start-child`
child through `vglrun -d egl`; actual host ancestry must prove this. It renders
and retains a real classic MuJoCo NVIDIA EGL frame, touches2GiB GL buffers and
1GiB CUDA tensors. Prewarm, CUDA-only and GL-added barriers independently
measure parent and per-process charge deltas. Both NVML compute-v3 and graphics-v3
queries are required; duplicate PIDs are deduplicated only when their all-app
usage agrees, never summed. Unsupported/unavailable/ambiguous readings fail.
Other parent GPU PIDs/charges and parent-minus-process residual must remain
exact; touched increments must account for at least their bytes, with at most
64MiB extra rounding/bookkeeping each. Existing desktop charge cannot fill a
missing GL delta. See [NVIDIA device queries](https://docs.nvidia.com/deploy/nvml-api/latest/api/group__nvmlDeviceQueries.html).

Separate independently sampled GL-before/GL-rejected and combined-CUDA rejection
phases exercise one GL request whose size alone exceeds10GiB, and an above-
combined-cap CUDA request while both touched allocations remain resident. Only
typed GL_OUT_OF_MEMORY/CUDA OutOfMemory errors qualify their observations. GL
allocation is separate from touch; unexpected success is freed and fails before
touch. No charge change across rejected requests is accepted. Each live stage
pauses for independent readback. The
other explicitly owned test process records CUDA readback progress before,
during and after pressure. Missing NVIDIA context, typed rejection, kernel
history, lineage, current authority, measurements, process completion or charge
recovery is failure/inconclusive; no synthetic success fields fill those gaps.

Raw Pod/authority/host/event/frame bytes and digests are retained. The exact
reviewed manifest bytes are retained as `manifest.raw.json` alongside canonical
`manifest.json`; the recorded raw SHA reproduces the original bytes.

Reset status is explicitly UNKNOWN. Read-only `/dev/kmsg` snapshots retain raw
records, sequence numbers, monotonic timestamps, read-clock bounds and boot.
Empty, inaccessible, truncated/gapped, overwritten-baseline or changed-boot
history fails/inconclusive. Anchored contiguous printk coverage and continuing
owned peer progress do not prove every hardware reset is logged. The producer
therefore suppresses `peer-survival` and NEVER emits `device_reset_count:0`.
`review-material` is incomplete/nonauthoritative and lists that missing probe.
A reviewed actual reset-observation contract remains an immediate qualification
prerequisite, alongside actual-envelope/target-policy promotion. No caller flag
can declare reset completeness. See the [Linux kmsg ABI](https://www.kernel.org/doc/Documentation/ABI/testing/dev-kmsg).

Each GPU child has60s alarm; peer has45s work. The local runner's transports and
whole loop are bounded. Cleanup deletes only owned terminal directories. A lost
setup reply or nonterminal child is an explicit hold; inspect/wait for watchdog
termination and recover only proven ownership. No automatic retry, unknown
process deletion, existing kernel use or user workspace Stop. Parent owns normal
Stop and final reservation/permission/readiness restoration. No drained/fenced
precondition may be achieved by stopping protected research sessions here.

The historical MuJoCo Dockerfile inherits mutable desktop/runtime bases, so its
source alone cannot prove exact image module versions. Existing pending cap
gate runs in its separate gate image and UUID guard is self-contained Python;
exact-image imports/startup/graphics and user desktop remain hardware checks.
Authenticated desktop and actual user training are later separate acceptance.
