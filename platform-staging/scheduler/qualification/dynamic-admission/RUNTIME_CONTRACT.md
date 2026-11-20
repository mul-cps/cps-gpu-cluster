# Dynamic runtime admission contracts

Status: **source implemented and offline tested; not integrated, applied or live qualified**.

Dynamic KAI/HAMi/MPS packing remains the selected direction. No MIG operation or
configuration is introduced. The fixed 5/10/20 GiB profiles remain disabled in
the canonical catalog. These contracts do not repair the earlier deliberate
software-enforcement bypass; ordinary quota OOM and hostile tampering are distinct
qualification gates.

## Three admission surfaces

`render_runtime.py` composes three fail-closed candidates in a new
`cps-dynamic-admission-*` namespace. Creator/writer restrictions are validations
on every request, never identity filters that could skip the policy. No current
production/staging policy, Pod Security label, workload RBAC, MPS cap or storage
path is changed. Applying the YAML would be an activation step requiring real
Kubernetes qualification first; the annotation alone does not disable a policy.

| Surface | Protected operator inputs | Allowed source shape |
| --- | --- | --- |
| Pod CREATE/UPDATE | Original authenticated creator and permitted updater identities; exact Workflow name/UID; exact Pod name, quota prefix, main index and profile | Compiler cache/MPS contract plus pinned KAI/isolator injection; executable fields and quota references retained during binding updates |
| ConfigMap CREATE/UPDATE/DELETE | Binder writer identity; exact per-Pod names, Pod UID, physical GPU and observed device selector, portions and quota; optional independently observed ConfigMap UID | Empty capabilities map → device → device and both portion aliases → complete HAMi limit; evar permanently empty; same-stage retries and exact binder rollback deletion |
| pods/binding CREATE | Binder identity; exact Pod name/UID and node; completed capabilities/evar names, UIDs and resource versions; compiled-Workflow and review digests | KAI's actual UID-bearing `v1.Binding`, targeted at exactly the reviewed node |

The Pod policy uses the **original request actor** after CREATE-time mutation;
neither the KAI nor isolator service account is substituted as creator. The main
container can be index 0 or 1: `[wait, main]` requires the `-1` quota suffix.
Writable isolator mounts accept absent or false `readOnly`, matching Go's
`omitempty` serialization; the preload file must stay explicitly read-only.

Both quota records must agree on Pod UID, physical GPU, advertised physical
memory, visible device selector, portion and KAI limit. The unindexed injected
limit is computed by KAI from advertised GPU memory times received portion; it
can exceed the nominal indexed compiler limit. The historical 5 GiB run has
`CUDA_DEVICE_MEMORY_LIMIT_0=5120m`, but KAI's `CUDA_DEVICE_MEMORY_LIMIT=5324m`
from 40960 MiB × 0.13. These must not be equated. The Pod boundary preserves the
nominal indexed limit; the quota registry validates the separate source-derived
calculation against explicitly reviewed inputs. Actual overhead/packing and
node-label accuracy remain live qualification gates. With CDI enabled KAI writes
`k8s.device-plugin.nvidia.com/gpu=<reserved-device>`; the non-CDI selector is also
supported as an explicitly observed record. An indexed CDI selector requires an
independently reviewed node/index-to-physical-UUID mapping. A string format cannot
prove which physical GPU it selects.

Quota updates advance one stage or repeat the current stage. KAI's same-owner
empty upsert preserves populated data, so a repeat after a complete write is
allowed. Replacing an owner, changing a GPU/quota or resetting data is denied.
Rollback DELETE is checked against `oldObject`, not an absent DELETE `object`.
Garbage-collector and cleanup identities are not inferred; their real requests
must be reviewed before adding writers.

## Concrete missing coordination

The current SDK rejects caller workflow/template annotations and emits no
`runai/shared-gpu-configmap`. KAI generates a fresh random prefix during CREATE
and preserves a supplied prefix verbatim. The exact preregistration candidate
therefore **cannot admit the current SDK-to-Argo path yet**. A dry-run or rejected
retry generates a new random suffix. A trusted per-Pod coordinator must assign
and register unique references without introducing user-controlled annotations
or collisions among repeated DAG templates. This hook is not implemented here.

CEL cannot GET a Pod, parent Workflow or ConfigMap. It cannot attest that a
referenced map is current or complete. The records are manual qualification
attestations and must be protected by actual RBAC; registry synchronization and
production lineage enforcement are not implemented here.

KAI's binder deletes both maps after a failed bind. Waiting for asynchronous
approval of their first observed UIDs can therefore deny a bind, trigger deletion,
and recreate different map generations on retry. The binding candidate models
exact approved generations but **does not solve this race or establish liveness**.
A synchronous pre-bind coordination protocol that preserves or atomically
reviews the current maps must be implemented and qualified. Broadening actor or
prefix checks is not a substitute for that protocol.

The runtime renderer checks correspondence between Pod, map and binding records,
including that the independently reviewed KAI limit covers the nominal budget.
When binding records are present, their map UIDs must match explicitly UID-bound
quota records. Source order, supplied hashes and matching YAML do not establish
the authenticity, current state or freshness of those records.

## Verification and remaining gates

The literal CEL interpreter executes the rendered expressions. Notebook fixtures
execute the released SDK's actual APIs. Both use clearly synthetic controller or
transport inputs. No source-inferred Pod is described as controller-generated.
The [source trace](SOURCE_TRACE.md) pins official KAI and isolator commits and
records exact fields and ordering; installed-image correspondence remains a gate.

Real API-server CEL schema typing, defaulting, cost limits, webhook ordering,
denied-request propagation and authenticated actor capture remain pending. No
usable API-server/etcd/k3s/envtest artifact was found in the inspected local
caches. The CLI and interpreter cannot replace those checks.

Executor security is a detached proposed patch. Actual Argo init/wait/cache Pod
materialization, writable init `/tmp`, artifact readability across UID10001
executors and UID1000 main, and fresh GPU execution remain unqualified. Restricted
Pod Security still rejects the hostPaths. No shared-runtime-class exemption or
existing-namespace relaxation is introduced.

After the coordination and admission gates, run the fresh mixed 5/10/20 GiB
qualification with all five simultaneous CUDA children, resource limits and
recovery, protected-session checks, revocation/reservations and scheduling gates.
Keep the production flags false until their distinct acceptance evidence exists.

## Renderer registry

Top-level JSON keys are `createCreators`, `updateCreators`, `owners`,
`reviewedPods`, `quotaWriters`, `quotaRecords`, `bindingWriters` and
`bindingRecords`. Unknown keys fail. The renderer validates canonical namespace,
identity, name, UID, digest and bounded allocation formats; individual modules
document their exact fields. Every list defaults empty and denies its surface.

Outputs are exclusive new YAML files. The standalone generators and three
policies remain outside Fleet. Generated evidence belongs outside Git; durable
qualification checkpoints retain checksums and source commits separately.
