# KAI/HAMi admission source trace

Status: read-only source review; no live admission/controller qualification.

## Provenance

Official tag refs resolve KAI v0.18.1 to `bdf434e5e9201cccf4e05fad04d814363653f692`, and resource-isolator v1.1.0 to `b7058586fe75e7c5a1addc553f408575bb31647f`. These 39 public-source files were fetched through the read-only GitHub connector. All local Git blob and SHA256 hashes were independently recomputed. Thirty-eight KAI/isolator files also match their pinned GitHub tree entries; the Kubernetes random-alphabet file is checked against its API blob at tag v0.36.2, without an independent tree comparison. `source-manifest.json` and `supplement-manifest.json` retain those distinctions, URLs/blob/SHA256/byte counts; the two SHA256SUMS files verify the downloaded bytes.

The sources below are pinned upstream behavior, not proof that installed image bytes were built from these commits. Historical receipts identify image digests and source-compatible final shapes; they lack API audit userInfo and intermediate mutations.

## CREATE mutation

KAI registers gpusharing before hamicore, then runtime enforcement. The Pod mutating webhook is CREATE-only, failurePolicy Fail, reinvocation IfNeeded:
- [plugin order](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/cmd/admission/main.go#L45-L72)
- [webhook rules](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/operator/operands/admission/resources.go#L254-L275)

For `gpu-memory`, gpusharing adds `nvidia.com/container.main.gpu-memory.request`. Parse of 5120/10240/20480 Mi and Kubernetes Quantity canonical serialization yields 5Gi/10Gi/20Gi. The saved 5Gi Pod confirms the first value; 10Gi/20Gi are source-derived, not historical runtime receipts. It sets `runai/shared-gpu-configmap`, creates four ConfigMap env refs, one envFrom ref and one ConfigMap volume; **no ConfigMap API object is created in admission**. Hami adds optional=true only to CUDA_DEVICE_MEMORY_LIMIT. Runtime enforcement supplies `runtimeClassName: nvidia` if absent/empty.
- [normalization and refs](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/admission/webhook/v1alpha2/gpusharing/gpu_sharing.go#L52-L95)
- [env/volume shapes](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/admission/webhook/v1alpha2/gpusharing/pod_mutation.go#L19-L106)
- [Hami ref](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/admission/webhook/v1alpha2/hamicore/hamicore.go#L31-L66)
- [runtime class](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/admission/webhook/v1alpha2/runtimeenforcement/runtime_enforcement.go#L33-L51)
- [Mi conversion](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/common/resources/gpu_sharing.go#L245-L247)

Resource-isolator is independently CREATE-only. Its JSONPatch adds three DirectoryOrCreate hostPaths and four main mounts: /usr/local/vgpu, its read-only ld.so.preload subPath at /etc/ld.so.preload, /usr/local/vgpu/containers, /tmp/vgpulock. It adds POD_UID downward field, CONTAINER_NAME=main, CONTAINER_VGPU_MOUNT=/usr/local/vgpu. It does not mutate LD_PRELOAD. Both webhooks patch the original CREATE; their own service accounts are **not** the authenticated creator of that request. Relative ordering between the two webhook configurations is not established by saved receipts.
- [isolator rule](https://github.com/Project-HAMi/KAI-resource-isolator/blob/b7058586fe75e7c5a1addc553f408575bb31647f/chart/kai-resource-isolator/templates/mutatingwebhookconfiguration.yaml#L35-L46)
- [patch](https://github.com/Project-HAMi/KAI-resource-isolator/blob/b7058586fe75e7c5a1addc553f408575bb31647f/cmd/webhook/main.go#L160-L268)
- [env](https://github.com/Project-HAMi/KAI-resource-isolator/blob/b7058586fe75e7c5a1addc553f408575bb31647f/cmd/webhook/main.go#L314-L358)

## Naming and duplicate behavior

KAI accepts an existing runai/shared-gpu-configmap annotation verbatim, including an empty value. If absent, it uses ownerReferences[0].name, otherwise Pod name; truncates base to 33 chars for single-digit regular index; TrimRight(".-"); appends "-" + random7 + "-shared-gpu". random7 alphabet is bcdfghjklmnpqrstvwxz2456789. Capability CM suffix is the **actual regular container index**, or i+init index; evar adds -evar, volume adds -vol. Regular containers [wait,main] mean **-1**, not -0. Named selection scans init containers first; mismatched nvidia.com/container.* annotation targets are rejected.
- [naming/prefix reuse](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/binder/common/gpusharingconfigmap/config_map.go#L111-L164)
- [target/index](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/common/resources/gpu_sharing_container_ref.go#L30-L101)
- [alphabet](https://github.com/kubernetes/apimachinery/blob/v0.36.2/pkg/util/rand/rand.go#L80-L116)

KAI AddEnvVarToContainer removes all matching name duplicates and appends its trusted ref. envFrom skips when that ConfigMap name already exists, without verifying its optional/prefix fields. Isolator skips an existing volume by **name only**, mount by name/path/subPath only, and metrics env by **name only**. Wrong sources, readOnly variants, duplicate metrics env and unrelated LD_PRELOAD survive those predicates. Final validation must enforce exact unique source/shape, rather than assume upstream injection proves origin.
- [KAI env replacement](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/binder/common/env_vars.go#L28-L37)
- [isolator skip predicates](https://github.com/Project-HAMi/KAI-resource-isolator/blob/b7058586fe75e7c5a1addc553f408575bb31647f/cmd/webhook/main.go#L370-L395)

## Post-CREATE sequence and staged data

Pod grouper creates/updates PodGroup, then PATCHes pod-group-name and optional subgroup label. Binder syncs/reserves GPU, PATCHes runai-gpu-group, calls ordered PreBind plugins, PATCHes binding annotations, then CREATEs pods/binding.

gpusharing PreBind upserts capability CM **empty**, upserts evar CM **empty**, PATCHes NVIDIA_VISIBLE_DEVICES, PATCHes RUNAI_NUM_OF_GPUS and GPU_PORTION; hamicore next PATCHes CUDA_DEVICE_MEMORY_LIMIT. Saved binder config confirms gpusharing priority100 before hamicore50, CDI true and NRI false. Thus capability key stages are {}, {device}, {device,portion,legacy portion}, all4; evar stays empty.
- [grouper](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/podgrouper/pod_controller.go#L137-L213)
- [reservation label PATCH](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/binder/binding/resourcereservation/resource_reservation.go#L295-L347)
- [PreBind then annotation PATCH then binding](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/binder/binding/binder.go#L42-L93)
- [CM creation/device/portion order](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/binder/plugins/gpusharing/gpu_sharing.go#L49-L88)
- [Hami memory](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/binder/plugins/hamicore/hami_core.go#L33-L51)

CM ownerReferences contains one {apiVersion:v1, kind:Pod, name, UID}; no controller/blockOwnerDeletion fields. Upsert with identical owner preserves existing data and merges nonempty desired values, so retries retain final all4 data. Upsert with different owner can overwrite it upstream; a downstream guard must reject owner/UID changes or collisions. Actual quota updates are separate ConfigMap PATCH requests, not executable Pod updates.
- [CM owner/create/upsert behavior](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/binder/common/gpusharingconfigmap/config_map.go#L30-L108)
- [quota PATCH](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/binder/common/gpu_access.go#L63-L179)

With `gpuDevicePluginUsesCdi`, gpusharing PreBind rewrites each reserved device
as `k8s.device-plugin.nvidia.com/gpu=<device>` before the visible-device PATCH;
otherwise it uses the reserved device directly. A reviewed selector must preserve
that observed representation. An indexed selector does not itself prove physical
GPU identity. [CDI conversion](https://github.com/kai-scheduler/KAI-Scheduler/blob/bdf434e5e9201cccf4e05fad04d814363653f692/pkg/binder/plugins/gpusharing/gpu_sharing.go#L56-L59)

## SDK40 and proposed gate

Read-only SDK source commit40b9525 rejects caller annotations: policy.py:128 allows only metadata name/generateName; :130 excludes podMetadata; :138 excludes template metadata/podSpecPatch. Four focused negative cases against wheel SHA2568321127b... passed for workflow annotations, spec podMetadata, template metadata and template podSpecPatch. Baseline accepted; output annotations are only gpu-memory5120 and gpu-fraction-container-name main. Policy module SHA25607cb86d2d34cd80d63d19856fb43008e37976be6f8b9113c5e53bc0e2a328893.

The proposed protected registry is fail-closed and retry-compatible **provided** it binds exact namespace/Pod name/UID, immutable reviewed parent/compiled executable shape, actual main index, generated prefix and both exact CM names, profile-fixed data/device/node, trusted measured request actors, and a fresh review version. Before registry exists, CM writes/binding remain denied; binder retries must admit idempotent same-owner complete data and exact staged prefixes, not only empty initial state. evar remains empty permanently; unknown keys, binaryData, UID/owner changes, alternate actors and cross-Pod references must be rejected.

An exact-prefix pre-CREATE registry is not yet wired to the actual SDK pipeline: SDK40 emits no runai/shared-gpu-configmap, and KAI generates a new random7 during each CREATE admission. Dry-run or rejected retries do not supply a stable prefix. Actual execution requires a trusted deterministic prefix injection/controller hook after Policy.validate, or a separately reviewed admission-registry protocol. Synthetic preregistration establishes neither that hook nor actual controller materialization.

A registry created after Pod creation needs an explicit controller retry/readback protocol. No lookup of parent/Pod/CM bytes is possible from CEL alone; a username or syntactically valid prefix does not prove parent trust or actual mutator origin. Binding should be gated only after complete reviewed CM UID/resourceVersion/data evidence, and future changes must remain constrained. A source-code order does not prove a particular admitted request followed it. Configuration shows expected binder SA, not authenticated userInfo.

Historical dyn071542c/dyn071552c confirm source-compatible final shapes and UID10001 runs. They do not qualify fresh UID1000 Argo lifecycle or dynamic mixed-profile isolation. Restricted PSA still rejects required hostPaths; source review does not activate namespace exceptions, replace production bindings, alter NFS, or enable GPU profiles.
