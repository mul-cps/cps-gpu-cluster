# Explicit cleared offline CPS recovery

This helper is source-tested operator recovery, not a passed normal Stop or a
finite-retirement proof. The failed original journal is retained unchanged.
No cap SET, reset, path recreation, gate mutation, driver reload, SQL or ledger
release is performed. The gateway must first run SDK commit `9d6f4680` (model
`630d43cc…`, authority `babeb6ee…`) and verify the distinct immutable audit.

## Source installation and credentials

Root alone stages/runs the helper on the actual GPU2 host in the existing
reviewed privileged node execution context. Keep `/run/cps-native-gpu` and its
original files; do not create a substitute journal or physical inventory.
The node code includes the new `node_agent.py`, `cleared_offline_recovery.py`
and `source-snapshot.json`. Only the embedded controller model changes; every
other embedded dependency stays byte-identical. Materialize the existing six
bundle modules with their `SOURCE_PINS`; use the new exact `630d43cc…` model.
Normal node polling retains the prior wait-for-cgroup-absence guard.

For the explicit CLI, copy the exact source helper and node agent beside the
exact new source snapshot into one Root0700 directory, with source files0600.
The config is a genuine unchanged enabled v2 node config, Root0400. The bundle
directory contains the six pinned source modules. The helper verifies its own
and the agent's supplied raw checksums before importing either dependency.

Use a new transient service account named
`cps-native-cleared-offline-recovery` in the actual authority namespace. Root
creates a restricted sleeping credential-custody Pod, obtains a finite TokenRequest
bound to its **actual** name/UID, and retains it throughout completion. Copy
the actual token bytes and namespace CA into a separate Root0700 directory as
`token` and `ca.crt`, both Root0600/single-link regular files. No default Pod
token, ambient kubeconfig, administrator token, insecure TLS, proxy or redirect
is accepted. The explicitly reviewed HTTPS endpoint and raw CA/token hashes
are in `review.credential`. Signature/authentication is established by an actual
SelfSubjectReview; decoding JWT claims alone is insufficient.

Required narrowly scoped permissions are:

* GET the three named `cps-admin`, `cit-admin`, `compute-gateway` Deployments in
  `cps-compute`, and LIST Pods there (the code requests exact selectors and
  denies pagination or any remaining Pod).
* GET node `k3s-wk-gpu2`; GET the exact original twelve physical Pod names in
  their recorded CPS/CIT namespaces; GET the credential-bound Pod and its SA.
* GET the named original enrollment, allocation ledger, recovery audit and
  cleanup ConfigMaps in the authority namespace; CREATE ConfigMaps there.
  Kubernetes RBAC cannot constrain CREATE by `resourceNames`; this Root-only
  pinned helper creates only the exact two immutable names. No UPDATE/PATCH/
  DELETE, Pod execution, driver control or grant rights are needed.
* CREATE `authentication.k8s.io/v1` SelfSubjectReview (authentication inspection).

## Actual plan and explicit review

Root freshly quiesces all three writers, captures their full zero-replica
Deployment objects/current observed generations and complete empty Pod lists,
then captures unchanged actual ledger/enrollment, all original journals and
the complete physical inventory. Do not mark the ledger all released: the
required preimage is **23 records, 22 released and the exact CPS releasing**.
The plan preserves all seventeen journals and explicitly selects the twelve
current-epoch physical lifetimes; the five older terminal journals stay pinned.

`plan_from_captures(agent, models, config, host, inventory, enrollment, ledger,
writers, operation_uuid)` is a pure offline assembler using the existing
Root `host-records.json` schema. It emits no review or passed proof. Here
`writers` maps the three literal names to their fresh full Deployment JSONs;
`config` is decoded genuine v2 config; all remaining objects are decoded actual
Root captures. Load the helper/agent from verified source bytes, call the
assembler, write its canonical JSON to a new Root0600 `plan.json`, then review
the captured originals and operation scope before creating `review.json`.

The existing Root capture base is
`restart-session-20261011T190822Z/recovery-current-capture-20261011T1954`.
Its `host-records.json` has `bootId`, `driverGeneration`, `healthPassed`, and
`directories.journal = {ownerUid, mode, records}`. `records` maps each
`<podUID>.json` to `{uid, mode, nlink, rawSha256, value}`; `value` is the complete
genuine CapRecord. Preserve all seventeen entries, including their actual raw
writer checksums. `physical-inventory.json` is the original closed SDK inventory
document `{version, backend, gpu_uuid, gpu_id, entries}`; each of its twelve
entries carries the complete inode/kernfs/cgroup ID, flags, soft/hard and used.
`enrollment.json` and `ledger.json` are complete actual Core/v1 ConfigMap
objects, not just decoded data strings. `writers` uses fresh actual Apps/v1
Deployment objects collected **after** Root's new quiescence; the old capture
is context, and every live input is checked again under the locks.

For offline inspection, call `validate_plan(agent, models, plan, config)`, then
`validate_review(agent, review, plan)` and `make_proof(agent, models, plan,
review)`. These functions do not contact an API or GPU and do not emit passed
acceptance. There is no `--inspect` mutation mode. Running the source helper
with no arguments prints the default-inert receipt without reading any input.
Root may use `/host/run/cps-native-gpu` as the explicit state-root inside the
actual existing native-agent Pod; the recorded cgroup path root remains
`/sys/fs/cgroup`. Stage source copies, snapshot, input JSON and credentials in
separate new Root0700 directories; never copy a journal to those directories
and substitute it for actual host state. Token `exp` must cover `expires_at`;
choose the review expiry from the actual TokenRequest expiry, allowing for
the time spent staging rather than adding another full600seconds afterward.

The closed review fields are:

```json
{
  "version": 1,
  "operation_id": "ACTUAL_NEW_UUID",
  "plan_sha256": "sha256:CANONICAL_PLAN_HASH",
  "issued_at": "ACTUAL_UTC_Z",
  "expires_at": "ACTUAL_UTC_Z_AT_MOST_600_SECONDS_LATER",
  "approved": false,
  "exclusive_operator_custody": false,
  "no_alternate_writer_or_release": false,
  "normal_stop_passed": false,
  "production_qualified": false,
  "credential": {
    "namespace": "ACTUAL_AUTHORITY_NAMESPACE",
    "service_account": "cps-native-cleared-offline-recovery",
    "service_account_uid": "ACTUAL_SA_UUID",
    "pod_name": "ACTUAL_CREDENTIAL_POD_NAME",
    "pod_uid": "ACTUAL_CREDENTIAL_POD_UUID",
    "pod_spec_sha256": "sha256:CANONICAL_FULL_POD_SPEC_HASH",
    "api_server": "https://ACTUAL_PINNED_ENDPOINT:PORT",
    "audience": "ACTUAL_SINGLE_TOKENREQUEST_AUDIENCE",
    "token_sha256": "sha256:RAW_TOKEN_FILE_HASH",
    "ca_sha256": "sha256:RAW_CA_FILE_HASH"
  }
}
```

This disabled example fails validation. Root explicitly approves the three
custody/exclusion flags only after fresh evidence is reviewed. Keep the two
qualification flags false. Token lifetime is at most one hour and covers the
review interval. Save exact Root0600 plan/review bytes in a Root0700 directory;
provide their **raw** hashes on the CLI (different from canonical plan/review
hashes embedded in the typed proof). All SHA CLI arguments are bare64hex.

## Execution

All paths below are explicit Root-staged actual paths, not defaults. No live
operation occurs without `--execute`:

```sh
python3 /ROOT_PRIVATE_CODE/cleared_offline_recovery.py \
  --execute \
  --self-sha256 ACTUAL_RAW_HELPER_SHA \
  --node-agent /ROOT_PRIVATE_CODE/node_agent.py \
  --node-agent-sha256 ACTUAL_RAW_AGENT_SHA \
  --config /ROOT_PRIVATE_INPUTS/node-config.json \
  --bundle /ROOT_PINNED_BUNDLE \
  --state-root /run/cps-native-gpu \
  --service-account /ROOT_PRIVATE_CREDENTIALS \
  --plan /ROOT_PRIVATE_INPUTS/plan.json --plan-sha256 ACTUAL_RAW_PLAN_SHA \
  --review /ROOT_PRIVATE_INPUTS/review.json --review-sha256 ACTUAL_RAW_REVIEW_SHA \
  --crictl /host/var/lib/rancher/k3s/data/current/bin/crictl \
  --cri-socket unix:///host/run/k3s/containerd/containerd.sock
```

The SDK acquires `journal/.writer.lock` first; the helper then acquires the
existing `authority/.driver-loader.lock` and `operator/.teardown.lock` in that
order. It checks held fd/path identities throughout. It repeats full physical
map equality, all eleven exact retained finite peer caps, selected CPS0/MAX,
zero charge, old PID lifetimes, original cgroup2 mount/device, Pod/cgroup/gate
absence, driver epoch/health, SA custody, writer-zero and complete ledger CAS
preimage. All three locks stay held through terminal and immutable publication.

The SDK exclusively archives the failed raw bytes at
`journal/recovery-originals/<podUID>.<operationUUID>.json` (Root0600), then writes
the distinct `recovered-cleared-offline-cap` terminal. The callback creates
`cps-native-recovery-<binding[:40]>` with `recovery.json`, then the existing
`cps-native-cleanup-<binding[:40]>` with the exact six-field `recovery` extension.
Both ConfigMaps are immutable, independently owned and read back. Finally the
existing Root0600 `published-cleanup/<podUID>.json` marker binds enrollment UID,
cleanup UID and the entire receipt, including audit UID/hash. Exact original
plan/review bytes are retained under
`operator/cleared-offline-recovery/<operationUUID>/`.

Do not unfreeze writers/release on a nonzero exit. Partial failure may leave
an original archive, distinct terminal or immutable audit/cleanup, but creates
no successful completion claim. Retain custody and review validity; only the
identical operation/proof can resume. Conflicting operation, review, receipt,
archive or expired review fails. If the window expires, stop for explicit
inspection rather than substitute approval. Normal node polling retains an
unpublished recovery for explicit operator completion. Durable recognition
requires the full archive/plan/review/terminal/audit/cleanup/marker chain and
does not demand an old complete map after legitimate future Starts.

Only after Root verifies that chain may the genuine configured gateway consume
the trusted cleanup during normal Source Close. That later release/Stop
acceptance is a live gate. The historical failed normal Stop remains failed;
future finite retirement/hardware qualification remains separate.

CPU validation from this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/bjoern/git/cps-compute/.venv/bin/python \
  -m unittest -q test_cleared_offline_recovery test_node_agent test_node_agent_finite_cleanup
```
