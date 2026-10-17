# Dynamic approval delivery runtime (staging)

This pure renderer stages the installed SDK dynamic-head producer. It performs no
API calls, reads no credentials, and always emits a zero-replica Deployment.
Actual bootstrap, migration, admission qualification, image qualification, and
activation remain separate release gates.

Load `render.py` and call:

```python
objects = render(config, configuration=actual_typed_node_configuration,
                 image=qualified_sdk_image_digest,
                 config_secret=existing_private_input_secret_name,
                 journal_pvc=existing_delivery_journal_pvc_name)
```

`configuration` is the actual SDK `NodeConfiguration` v4 authenticated from the
captured immutable object. Its six-field reference must equal both the closed
producer config and `ObserverRelease` v2 reference. The four namespace-local
head bindings, actual component Deployment/ServiceAccount names, and four actual
observer-own Role UID/rule baselines supply the generated permissions. The
renderer never invents API identities or modifies these inputs.

The protected `delivery.json` wire format is exactly:

```text
{version:1, enabled:true, policy_path, node_configuration:<6ref>,
 observer_release:<Release2>,
 pregrant_roles:[EXACTLY FOUR {namespace,name,uid,index,rules}],
 capture:{origin,ca_file,token_file}, ttlSeconds}
```

The existing private input Secret must contain `delivery.json` plus the basenames
of `policy_path`, `capture.ca_file`, and `capture.token_file`. Those three distinct
absolute paths must be direct children of `/inputs/delivery`; the capture origin
must be a bare HTTPS origin with a valid port and no trailing slash. Init copies only those four files to an owned `0700` directory,
with file mode `0600`. No Secret object or Secret API permission is emitted.

The routine command uses only the installed package:

```text
python -I -B -m cps_compute.native_approval_delivery \
  --config /inputs/delivery/delivery.json \
  --state-dir /journal/delivery --execute
```

The Deployment uses `Recreate`, nonroot UID/GID 1000, a read-only root filesystem,
all capabilities dropped, and no privilege escalation. Its provided PVC must
already support this identity. Init validates the recognized owned journal
inodes before repairing modes under the new `head-delivery` child only; accepted
entries are `lock`, `state.json`, `anchor.json`, the byte-identical adoption
archives `legacy-state.json` and `legacy-seed.json`, and exactly the four
corresponding `.json.new` temporary files. No suffix wildcard is accepted. The
SDK consumes recognized interrupted-write temporaries under its exclusive lock;
init leaves their bytes intact. A create-only hardlink crash that leaves two
names with link count two remains a fail-closed manual-review boundary; init
does not unlink or silently repair it. It does not read, rewrite,
unlink, or reset state or alter the PVC root. Main mounts only that child at
`/journal/delivery`. The old PVC `delivery` child is outside the routine process
mount view. Kubernetes fsGroup behavior and existing PVC ownership must also be
verified during the actual rollout.

Legacy adoption is an explicit SDK migration operation, not a routine Pod mode.
This renderer does not mount old state/seed or invent their hashes. Root must
retain them read-only and separately review the SDK `--adopt-legacy`,
`--legacy-state`, `--legacy-seed`, and exact SHA-256 arguments before migration.
Never replace or reset a journal to recover a partial publication.

The four namespace Roles allow ConfigMap GET/CREATE, PATCH only the four pinned
pointer names, exact named Deployment/ServiceAccount GET, Pod/ReplicaSet GET
without LIST, and GET/PATCH/escalate only the four actual observer-own Role
names. There is no Deployment PATCH, Node access, Secret access, or wildcard
resource grant. The seven component Roles remain the observer's responsibility.

Three fail-closed admission policies bound pointer UPDATE, immutable approval
CREATE, and the four observer-own pregrant Role UPDATE targets. Protected
targets also match foreign actors; foreign actors on unrelated objects are
unmatched. Pointer updates pin namespace/name/UID and preserve static metadata.
Approval creates permit only four namespaces and canonical hash-name syntax,
one bounded `approval.json` value, immutability, and empty application metadata.
The selected Role row may gain only unique approval names while all original
names and all other rules remain fixed. Initial anchor/pointer creation and the
reviewed initial permission set must be bootstrapped before these policies are
bound; routine approval documents use `cps-native-approvals-<16 lower hex>`.

CEL bounds document form, character length, actor, and target identity. It does
not JSON-decode a head, authenticate a document hash, prove monotonic generation,
or inspect JSONPatch test operations. The installed SDK must enforce typed
history/Source/ACK validation, canonical byte limits, full UID/RV/data/rules CAS,
readback, journal custody, and restart continuity. The observer's future exact
ConfigMap GET names must be pregranted before pointer promotion. No broad GET or
LIST grant is added to hide that ordering requirement.

`test_render.py` exercises the actual official Go CEL evaluator for positive and
negative CREATE/pointer/pregrant decisions, input drift, inert entrypoint,
runtime security, and the private initializer. Supply the qualified SDK source
and its tests on `PYTHONPATH`, and set `CPS_NATIVE_PENDING_CEL_EVALUATOR` to the
reviewed offline `cel-evaluate` executable. Without that variable CEL cases skip;
such a run is not the complete local matrix. Actual K3s compilation and isolated
admission decisions, exact image-installed behavior, legacy adoption, genuine
ACK2 publication, and activation remain Root's live gates. No GPU qualification
is implied by these CPU tests.

The default CPS deployment also needs `capture-network-policy.yaml` before
activation. The existing `native-approval-capture-private` policy admits only
the old delivery Pod label. This separate policy admits the new continuous
controller and adoption Job label, only from the same `cps-compute` namespace
to the selected Gateway's private TCP/8001 capture listener. Authenticated TLS
and the protected export token remain mandatory. It does not expose a public
endpoint or alter the old policy. A non-default namespace/origin requires a
separately reviewed policy; do not widen this file to all Pods or ports.

## One-time legacy adoption Job

`adoption_job.py` exposes a pure `render(...)` helper with the same validated
runtime inputs plus required `job_name`, `legacy_state_sha256`, and
`legacy_seed_sha256`. Both pins must be explicit canonical `sha256:<64 lower
hex>` values for the exact original bytes. It returns only a Job and reuses the
runtime's existing ServiceAccount, Pod security, private initialization, mounted
inputs, and permission contract; it emits no grants or credentials. `render.py`
and the default-zero continuous Deployment are unchanged.

```python
job = adoption_job.render(
    config, configuration=actual_typed_node_configuration,
    image=qualified_sdk_image_digest, config_secret=existing_adoption_secret,
    journal_pvc=existing_delivery_journal_pvc, job_name=explicit_reviewed_name,
    legacy_state_sha256=reviewed_original_state_hash,
    legacy_seed_sha256=reviewed_original_seed_hash)
```

The existing adoption input Secret must contain the four routine keys plus
`legacy-seed.json`, whose value is the exact original raw seed bytes. Init
preserves the reviewed initializer and appends only a copy of this fixed key,
verifying the seed hash before creating its owned private `0600` copy. No seed
bytes, Secret contents, or token values are embedded in the Job. The SDK also
checks both original hashes and retained custody during adoption.

The installed command adds:

```text
--adopt-legacy --legacy-state /legacy/delivery/state.json \
--legacy-seed /inputs/delivery/legacy-seed.json \
--legacy-state-sha256 <explicit original byte hash> \
--legacy-seed-sha256 <explicit original byte hash>
```

The same PVC's `head-delivery` child remains writable at `/journal/delivery`.
Its original `delivery` child is separately mounted **read-only** at
`/legacy/delivery`; the SDK opens the existing old lock read-only and takes an
exclusive flock without changing old file bytes or inodes. The Job uses
`backoffLimit: 0`, `restartPolicy: Never`, one completion and one parallel Pod,
and a default 300-second deadline (explicit integer overrides must be 1–900).
Failure remains available for review; no automatic retry or reset is emitted.

Before Root applies this Job, both the old writer and the new continuous
Deployment must be stopped. Root must verify the qualified installed image,
actual four v4 head bindings and genuine ACK2s, exact protected Role baselines,
all-released actual ledger, matching backups, and zero SQL reservations/bindings.
The pure helper cannot establish those live conditions. Initial pointer/anchor
bootstrap and admission qualification remain separate gates. A failed Job must
be reviewed with retained journal evidence before an explicitly named successor
attempt; deleting state or archives is not a retry procedure.
