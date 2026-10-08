# Dynamic GPU admission qualification

Status: **offline candidate; not applied or production qualified**.

The selected runtime remains dynamic KAI/HAMi/MPS packing of ordinary fixed
5/10/20 GiB profiles on shared physical GPUs. MIG is excluded. This package
prepares the admission boundary needed by that runtime; it does not enable GPU
profiles or change an MPS daemon, scheduler, storage path or namespace policy.

`compiled_fixtures.py` calls `Policy.validate` from the verified SDK wheel at
commit `40b9525097776e0d5927242ca625a27dadbd797c`. It produces real compiled Argo
workflows and GPU runtime projections for all three profiles. Its subsequent Pod
projection is explicitly synthetic: no Argo executor, KAI webhook or Kubernetes
controller was executed. Fixture-only catalog qualification overrides are
labelled as test inputs; the canonical catalog must remain disabled and unchanged.
Distinct deterministic fixture parent UUIDs are synthetic, not observed identities.

`render_policy.py` clones the existing executor boundary into a separate
`cps-dynamic-admission-*` namespace and a separate parameter API group. It splits
the exact compiler cache initializer from credentialed Argo `init`/`wait`
containers. The initializer receives only its 64 MiB private cache volume; the
main receives the fixed `private/usage.cache` subPath and two exact MPS mounts.
The candidate binds main resources to actual compiler output and executor
resources to the Argo values file. It rejects extra GPU/DRA resources, arbitrary
host mounts, credentials in user containers, control/loader environment changes,
unsafe security settings, extra executables, debug containers and resource
resize overrides.

Creator restrictions are validations for every matched request. They never
appear in a creator match condition that could skip unauthorized requests. Empty
creator and parent registries deny all requests. The parameter registry must be
protected from ordinary users and filled only after verifying actual request
identities and parent Workflow name/UID records against trusted submissions.
CEL cannot fetch parents, traverse ancestry, inspect ConfigMap ownership/data,
or prove the origin of a copied ownerReference. This fixed qualification registry
is not a completed production lineage controller. Existing user permissions to
create/patch/bind/exec Pods, create arbitrary parents or change parameters and
injector maps must be checked separately.

The original `render_policy.py` supports only the **pre-KAI-injection shape**.
`injected_policy.py` adds a separate source-inferred candidate with the exact
pinned KAI/isolator hostPaths, metrics, device/quota references and actual regular
main-container index. Its exact protected Pod registry prevents copied quota
names from granting authority. `quota_policy.py` protects both referenced maps
and their population stages; `binding_policy.py` models the UID-bearing binding
request against separately reviewed completed-map generations. These are inactive
contracts, not a working submission-to-binding integration. See
[the exact source trace](SOURCE_TRACE.md) and [the coordination gaps](RUNTIME_CONTRACT.md).

`notebook_fixtures.py` also executes the actual released NotebookSubmissions,
snapshot, S3NotebookLauncher and ArgoBackend APIs with in-memory transport
responses. The fixtures preserve selected files and JSON-compatible typed
parameters, strip saved outputs, enforce 50 MiB, and exercise idempotence and
first-UID provenance binding. Their controller, executor and webhook fields remain
unmaterialized; an executor-hardening patch is a detached proposal only.

A final Pod snapshot does not prove the admission sequence. Actual CREATE,
mutation, UPDATE and binding observations remain required. Hub and JobSet
surfaces remain separate pending contracts; a generic controller identity is not guessed.

The credentialed-executor fixture is also synthetic. The candidate requires
explicit UID10001/GID10001, read-only root and RuntimeDefault seccomp on the
executor. Current Argo values do not declare all those fields. Trusted controller
configuration and actual executor Pods must be qualified against that stricter
contract before compatibility can be claimed.

No Namespace object is emitted. Existing production/staging bindings, the
four-string production parameter schema, restricted Pod Security labels and
GPU-disabled catalog remain unchanged. Restricted Pod Security independently
rejects these hostPaths; CEL does not override it. A scratch namespace exception
must be reviewed and qualified after fail-closed enforcement is demonstrated.
Do not exempt the shared `nvidia` runtime class or relax an existing namespace.

## Offline verification

Use an environment with the SDK dependencies, PyYAML and the pinned
`cel-python==0.4.0` interpreter. Supply the reviewed wheel; imports are executed
from its verified ZIP bytes rather than the editable SDK checkout. This session
used the existing SDK venv plus the existing cached CEL interpreter site-packages;
no packages were installed and no network or cluster calls were made.

```sh
python -B -m unittest discover \
  -s platform-staging/scheduler/qualification/dynamic-admission \
  -p 'test_*.py' -v

python -B platform-staging/scheduler/qualification/dynamic-admission/compiled_fixtures.py \
  --wheel /path/to/reviewed/cps_compute-0.1.0-py3-none-any.whl \
  --output /tmp/new-compiled-admission-fixtures.json

python -B platform-staging/scheduler/qualification/dynamic-admission/render_policy.py \
  --wheel /path/to/reviewed/cps_compute-0.1.0-py3-none-any.whl \
  --namespace cps-dynamic-admission-review \
  --executor-image 'registry.example/argoexec@sha256:<reviewed-digest>' \
  --output /tmp/new-dynamic-admission-candidate.yaml

python -B platform-staging/scheduler/qualification/dynamic-admission/render_runtime.py \
  --executor-image 'registry.example/argoexec@sha256:<reviewed-digest>' \
  --output /tmp/new-dynamic-runtime-candidates.yaml
```

Without `--registry`, the rendered creator and owner lists are empty. A review
registry is JSON with only `createCreators`, `updateCreators` and `owners` keys;
owners contain exactly `name` and `uid`. Rendering is not deployment or proof
that those declarations were verified. Outputs are created exclusively and never
overwrite prior evidence.

The runtime renderer emits three separate CRDs, parameter resources, policies
and bindings (12 objects). All registries default empty. Its additional registry
fields are documented in [RUNTIME_CONTRACT.md](RUNTIME_CONTRACT.md); records are
operator attestations, not live API reads. No renderer emits a Namespace, grants
RBAC permissions or deploys an application.

`cel_evaluate.py` executes the literal expressions with a reported CEL
parser/interpreter. It has no Python policy mirror or custom policy functions.
It records expression hashes and sanitized parse/evaluation failures. Tests cover
the real compiler projections, crafted changes and synthetic executor credentials.

**These are not Kubernetes conformance tests.** The available interpreter lacks
Kubernetes extensions such as `split`, and has a measured missing-field
comparison difference. It does not run API-server schema typing/defaulting, CEL
cost limits, admission propagation, authorizer checks or webhook ordering. Every
match condition is evaluated without skipping subsequent validations. Genuine
server type checking and denied-request propagation barriers remain mandatory.

## Remaining activation evidence

1. Fresh UID1000 runtime and authenticated creator observations, exact protected
   parent records, and reviewed scratch enforcement/Pod Security arrangement.
2. Actual Argo init/wait/cache Pods, parameter/schema typing without warnings,
   positive and crafted-negative server requests, including subresources.
3. Implement trusted per-Pod prefix coordination and synchronous quota/binding
   approval without the rollback/recreated-map race, then qualify complete KAI
   injection, owned ConfigMaps and binding ordering with
   unauthorized parent, Pod, exec/bind and configuration mutations denied.
4. Separate Hub/JobSet contracts and shared-workspace lifecycle/reservations.
5. The live [mixed 5/10/20 GiB experiment](../dynamic-cache/MIXED_RUNTIME.md),
   packing/reclaim/startup gates and isolation evidence. The prior software
   tampering failure is not resolved by an admission test or an ordinary OOM.

The historical [compiled runtime receipts](../dynamic-cache/COMPILED_RESULTS.md)
remain separate runs, with their recorded UID, image and evidence limits. This
package does not promote them into UID1000, mixed packing or hostile-isolation
qualification. All production and live qualification flags remain false.

References: [Kubernetes Validating Admission Policy](https://kubernetes.io/docs/reference/access-authn-authz/validating-admission-policy/)
and [Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/).
