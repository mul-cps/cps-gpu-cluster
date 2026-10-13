# Automatic installed approval revision delivery

`native_group_approval_delivery.py` is a separate operator controller. It does
not replace the gateway/Hub/node `cps_compute.native_group_publisher` heartbeat
writers. The existing reviewed installed publication is its prerequisite. The
default invocation is inert; `--run` explicitly enables Kubernetes delivery.
No Hub Helm Python block or browser activation input is involved.

## Trusted interfaces

The reviewed seed is an operator-owned regular `0600` JSON file with exactly:

```text
version: 1
policy: complete current catalog
qualification: unchanged qualified NativeGroupDeployment configuration
previous_publication: complete reviewed installed renderer publication
previous_publication_sha256: independently pinned canonical packet SHA
baselines: four renderer baseline entries, including actual prior document/reference objects
ttlSeconds: unchanged installed publisher TTL
```

Each baseline retains its full Deployment, container, previous immutable
document and previous immutable reference. At the first new revision the
controller refreshes actual objects through named API GETs, then retains those
snapshots and old process records in its journal before any mutation. It does
not require old loaded-head acknowledgment freshness to initiate a new head.
Named refresh checks the saved immutable document/reference UID and complete
data before replacing any readback fields. An identical-content reference under
a foreign UID is rejected both in the initial seed and completed journal.

Two separate `0600` JSON argv files select trusted capture executables. Commands
run directly with `subprocess`, without a shell, and must finish within 25s.
The Source command returns exactly `version: 1`, `source_raw` (exact UTF-8
document string), `source_sha256`, `trusted_revision`, and aware `captured_at`.
It must execute through the authorized server interface; browser data and an
untrusted document's self-declared digest establish no provenance.

The SDK's separate read-only server command supplies this Source payload:

```sh
python -m cps_compute.native_group_export \
  --database /server/control.sqlite \
  --policy-json /server/policy.json \
  --qualification-json /server/qualified-template.json
```

The export opens the existing SQLite DB with `mode=ro`, enables connection
`query_only`, reads head plus immutable revision in one transaction, and calls
`ApprovalSnapshot.from_document`. It constructs no ControlStore/registry/runtime,
creates no schema or missing DB, changes no Source state, and returns no driver
epoch. The caller must protect its complete administrative export. The existing
source-filtered native-group-approvals discovery endpoint is not this interface.

The separate epoch command returns exactly `node_uid`, `boot_id`,
`driver_generation`, `gpu_uuid`. Its implementation must freshly observe the
qualified node, or validate the actual node acknowledgment against the current
qualified node process and observed pool; it must not read the epoch from the
Source DB or simply echo configuration. Delivery checks exact equality with the
reviewed pool before mutation and passes that independent observation to the
strict final readiness helper. Deployment of this protected observer and the
canonical server export transport remains Root integration work.

## Run and recover

```sh
python native_group_approval_delivery.py
python native_group_approval_delivery.py --run --once \
  --config /operator/seed.json --state-dir /operator/delivery \
  --capture-command /operator/source-command.json \
  --epoch-command /operator/epoch-command.json --context reviewed-context
```

Omit `--once` for the persistent loop; the poll interval defaults to 5s and is
bounded to 1–60s. Metadata-only output reports phase, revision and actual
readiness; failures report blocked/pending without dumping Source contents or
kubectl stderr. Each API request has a 20s deadline and each subprocess a 25s
deadline. A transient failure is retried by the next bounded iteration.

Use a persistent local/PVC journal supporting POSIX flock, atomic rename and
fsync. The controller requires an owned `0700` directory and `0600` state file,
holds an exclusive flock, and pins the original reviewed seed hash. Do not
remove or replace the journal to repair a partially applied rollout. Supply the
same seed on restart. Different configuration or foreign mutated objects fail
closed for operator review.

The journal saves immutable candidates, actual created UIDs, prior full
process records and every complete renderer patch before delivering it. A
crash after an API mutation but before its checkpoint is recovered through
actual named readback. Existing CMs must have exact complete data, immutable
identity and no owner; previously bound UID replacement is rejected. No
ConfigMap apply/update/delete is performed.

Each guarded patch tests the original UID and complete previous spec/rules.
Status-only resourceVersion churn is accepted only after a fresh exact
UID/full-value comparison, followed by JSON patch with the fresh RV test. An
already exact target is idempotent. The full guarded stage is preflighted
before its first mutation. Concurrent changes still fail the server CAS.

The stages create four identical immutable documents, bind actual API UIDs,
create four immutable reference maps, deliver seven named document GET Role
changes, then four full-spec guarded Deployment patches. Bootstrap maps,
acknowledgment identities/data and existing RoleBindings are retained. New
Pod/ReplicaSet GET permissions are derived from actual owner/template/security
observations. Pending Pods may receive permissions; no Pod status or successful
acknowledgment is created. Replacement Pending Pods receive fresh named GET
targets from the same bundled renderer's permission-only validation.

If a Source head is superseded mid-rollover, finish its structural guarded
delivery and permissions, retain its actual documents and references, and plan
the newest head from that actual baseline. Pending structurally valid Pods are
allowed in this permission-only prior path; their Ready status and acknowledgments
are never fabricated. Final current-head readiness uses unchanged
`readiness_intent` with all four genuine fresh loaded-process proofs. A rendered,
structurally completed or superseded revision cannot claim current readiness.
Idle readiness is re-observed instead of replaying a cached successful receipt.
The completed journal retains the exact seven Role UIDs/full rules and last
actual Pod/ReplicaSet names. Ordinary same-template process turnover triggers
the same permission-only guarded name updates, including Pending replacements,
without a new Source generation or any acknowledgment write. A durable saved
permission intent resumes a partially patched Role set before refreshing the
next observed names. Foreign Role UID/rules or controller/executable changes
fail closed; genuine fresh replacement acknowledgments restore readiness.

This bounded controller retains immutable history and never rewrites custody,
policy, driver configuration, hardware qualification, images, credentials, or
enrollment state. A history-bound failure requires a reviewed retention plan.

## Disabled runtime template

`native_group_approval_delivery_runtime.py` renders a standalone Kubernetes
List; it does not contact Kubernetes. The Deployment has `replicas: 0` and a
dedicated ServiceAccount. The immutable image must include the compatible SDK,
`kubectl`, and these files at `/opt/cps-native-delivery/`:

```text
native_group_approval_delivery.py
native_group_approval_renderer.py
qualification_transition_proposal.py
node_agent.py
```

The final two files supply existing reviewed pure guard helpers; delivery does
not instantiate or run the node-agent service. Runtime packaging, image build
and release pinning remain separate integration work.

```sh
python native_group_approval_delivery_runtime.py --seed /operator/seed.json \
  --image 'registry/delivery@sha256:<reviewed-64-hex-digest>' \
  --config-secret reviewed-delivery-input --journal-pvc reviewed-delivery-journal \
  --context reviewed-context > /operator/disabled-runtime.json
```

Root provisions the named private input Secret and persistent journal PVC. The
Secret has `config.json`, `source-command.json`, `epoch-command.json`, and
`kubeconfig`. The kubeconfig selects the supplied context and ordinarily refers
to this dedicated Pod's mounted ServiceAccount token/CA files; it contains no
reused gateway/Hub credentials. An unprivileged init container copies files into
an owned private directory with mode `0600`. The main container runs as UID/GID
1000 with no capabilities, no privilege escalation, a read-only root filesystem,
and no GPU devices. Actual input/credential values never belong in Git.

The four namespace Roles allow GET/PATCH on only the four exact Deployments
and GET/PATCH/ESCALATE on seven exact approval Roles. The named `escalate`
permission is required by Kubernetes' Role-update anti-escalation check because
the target publisher Roles retain own-acknowledgment PATCH that this controller
does not receive. They contain no Secret access, exec, RoleBinding
mutation, Pod mutation, acknowledgment PATCH, update, delete, or wildcard verb.
Dynamic content-addressed ConfigMaps require namespace GET/CREATE, and process
discovery requires namespaced label-filtered Pod LIST and ReplicaSet GET.
The dedicated CREATE-only admission policy restricts that ServiceAccount to
the four namespaces and exact immutable document/reference name/key forms.
The dedicated Role UPDATE policy/binding applies exclusively to that
ServiceAccount and admits only the seven exact namespace/name targets with the
original UID. It preserves rule count/order, API groups, resources, verbs,
nonResourceURLs and every non-GET row (especially own-acknowledgment PATCH)
exactly. Only nonempty GET resourceNames may change to previously allowed names,
qualified document/reference prefixes, or the relevant reviewed Deployment's
Pod/ReplicaSet name prefix. It rejects new verbs/groups/resources/rows, arbitrary
names, Role identity changes and rule reordering. The controller receives no
admission policy/binding mutation privilege. Root must install and validate both
fail-closed bindings before activation; named escalation without these protected
policies is not an authorized runtime configuration.

Root must validate admission support/enforcement before activating the controller.
Offline tests evaluate the generated literal expressions with the cached
`cel-python==0.4.0` engine, including allowed renderer Role patches and denied
permission expansions. They do not establish API-server schema typing,
authorization, cost budgets or binding enforcement. Its existing
controller identity receives no credentials or privilege until Root installs it.

The default manifest gives no Pods/exec permission. A protected canonical
server-export endpoint is the durable integration: named-Pod exec becomes stale
on gateway rollout and broad Deployment-based exec would enlarge authority.
Root owns that transport, live persistent automatic delivery qualification,
and any activation. No live/production readiness is claimed by this packet.
