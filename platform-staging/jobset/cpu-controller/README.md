# CPU JobSet controller qualification

This checked-in harness covers the bounded **success / one-failure recovery /
exhausted retries** matrix using two tiny CPU workers. Each case checks synthetic
SDK ownership denials, timer-driven cleanup, observed UID-owned KAI gang,
retained tombstone and idempotency replay. It uses the reviewed historical
retry-fixture contract (SHA256
`20a1afe64976dd45f7c8e8629686bdb1277100e1335c69d686ef0ab04d88c712`)
without executing or copying its historical live configuration.

The JobSet 0.12.0 global restart key is `jobset.sigs.k8s.io/restart-attempt`,
matching `status.restarts`; it is distinct from the per-Job attempt key.
[Upstream constants](https://github.com/kubernetes-sigs/jobset/blob/v0.12.0/pkg/constants/constants.go)
lines 31–39 define the distinction. The source was independently reviewed by the
parent task; the harness does not fetch it at runtime. The observed controller
must match the reviewed version before execution.

The local SDK drives real Kubernetes adapters only with explicit `--execute`.
By default the script prints `enabled:false,api_calls:false`, imports no SDK or
Kubernetes modules, and makes no requests. This work has been tested offline;
there is no live qualification receipt.

## Preconditions

Use an existing qualified SDK environment, reviewed kubeconfig context and pinned
JobSet controller. The historical chart/image pins are in [values.yaml](../values.yaml).
Confirm JobSet v1alpha2, KAI v2alpha2 PodGroup compatibility and actual controller
health separately. Having CRDs alone is insufficient. The context must be able
to create/delete one disposable namespace, its token-disabled service account and
its deny-all NetworkPolicy, and
access JobSets/Jobs/Pods/PodGroups there. Never change production RBAC, gateway
flags or catalogs to run this fixture. It uses the existing batch queue and
priority, making two 250m CPU/128Mi workers per attempt (controller replacement attempts
can briefly overlap while old Pods terminate).

Prepare and review a **separate synthetic fixture policy JSON**, compatible with
the installed SDK. Pin the exact file bytes in the packet. Starting from the
reviewed policy template, use:

- A unique `cps-jobset-qa-` namespace followed by sixteen lowercase hexadecimal
  digits for both `trusted.namespace` and `trusted.jobsets.namespace`.
- `trusted.schedulerName:kai-scheduler` and the existing `cps-batch` queue and
  priority in `workloadScheduling.batch`.
- `trusted.jobsets`: administrator command `["python"]`, maxWorkers 2,
  maxRetries 2, ttlSecondsAfterFinished at least the entire observation timeout,
  empty checkpointClaims, and a reviewed service account name. No token mounts
  are generated. The harness creates that token-disabled service account only in its new
  disposable namespace; it does not alter existing accounts.
- An enabled batch profile with CPU `250m`, memory `128Mi`, GPU mode `none`,
  one digest-pinned approved Python image and a walltime ceiling at least as large as
  timeoutSeconds. The image needs Python; it runs only the fixed checked-in code
  refusing exposed GPU device paths, printing a marker and sleeping ten seconds.
  It checks `/dev/nvidia*`, `/dev/kfd` and `/dev/dri/renderD*` by glob only,
  without opening or querying devices. Packet fields cannot supply code.
- Fixture-only `distributedQualification` with qualified true, policyVersion
  equal to that fixture's version and evidence exactly
  `["synthetic-cpu-controller-fixture-only"]`. Remove any stale policyHash and
  let the SDK recompute it, or provide the correct recomputed value. Do not feed
  this fixture back into the production policy compiler: its production guard
  correctly rejects distributed qualification assertions.

This policy deliberately uses synthetic identity/qualification authority, not
Hub OAuth. Fixture namespace Pod Security is restricted and network traffic is
denied both ways. The harness does not clone or change central admission policy;
passing does not prove production admission, deployed gateway packaging, OAuth,
checkpoint/project provisioning, distributed GPU execution or production cleanup
latency. It never modifies nodes, host paths, devices, mounts, production
namespaces or running user Pods. The scheduler chooses placement; CPU-only
requests do not guarantee placement on a machine without GPU hardware.

## Reviewed packet and execution

Example shape (replace placeholders with reviewed fixture values):

```json
{
  "version": 1,
  "enabled": true,
  "context": "reviewed-fixture-context",
  "namespace": "cps-jobset-qa-0123456789abcdef",
  "policyPath": "/absolute/path/to/reviewed-fixture-policy.json",
  "policySha256": "sha256-of-exact-policy-file-bytes-without-prefix",
  "profile": "batch-cpu",
  "image": "reviewed-registry/python@sha256:64-lowercase-hex-digits",
  "timeoutSeconds": 180,
  "cleanupIntervalSeconds": 10
}
```

Use the intended SDK environment, recording its source/image provenance with the
receipt. The receipt includes the loaded JobSet launcher source SHA256. The SDK is loaded from that environment; the worker image pin does not
prove the local SDK's provenance.

```bash
python platform-staging/jobset/cpu-controller/qualify.py
python platform-staging/jobset/cpu-controller/qualify.py --execute /absolute/path/to/reviewed-packet.json
```

The namespace must not already exist: the harness never adopts one. All offline
packet/policy/generated-manifest checks run before the first cluster request.
The namespace has an ownership label and its observed UID guards deletion.
UID-owned JobSet children and KAI gang objects are checked on every observation;
replacement UIDs or unexpected foreign children fail the run. An unobserved KAI
gang fails qualification even if workers complete. The interval task alone calls
`launcher.cleanup`; the observer never forces a sweep. The receipt records actual
monotonic sweep start/end timestamps and **observed** terminal-to-clean latency,
which includes polling uncertainty and is only for this fixture interval.

The matrix runs sequentially with separate idempotency keys: success requires
Completed/restarts 0; recover injects attempt 0 and requires Completed/restarts 1;
exhaust injects attempts 0, 1 and 2 and requires Failed/restarts 2. Injection only
shortens a running, non-terminating worker's currently observed child Job deadline.
The Pod's global restart annotation (or label) must match current parent
status.restarts. The Job is re-read and its UID, parent UID, deletion state and
resourceVersion checked before a UID/version-preconditioned deadline patch. A
replacement target or unknown result aborts; no failure-patch retry occurs.
This is controller deadline recovery, not application checkpoint recovery.

Before success is reported the harness checks cross-owner get/log/terminate
permission denials and empty listing, expected controller terminal state/restart count, retained suspended
tombstone, complete child absence, same-key replay retaining the original UID,
and verified namespace deletion. A timeout or uncertain cleanup exits nonzero
with `failed-or-cleanup-pending`. Namespace cleanup is attempted on all paths
once creation returned an observed UID. A lost namespace-create response has no
trusted UID; inspect the exact requested namespace manually before retrying.
No run auto-retries under a fresh name. Each of the three scenarios has its own observation timeout. Normal requests
use a ten-second API
request timeout; cleanup gets its own bounded timeout, so failure cleanup can
extend overall elapsed time beyond observation timeout.

## Offline tests

```bash
PYTHONPATH=/path/to/sdk/packages/hub/src:/path/to/sdk/src /path/to/sdk/.venv/bin/python -m pytest -q -p no:cacheprovider tests/jobset_cpu_controller/test_qualify.py
```

These tests cover default inertness, scope/hash/resource guards, the actual SDK
manifest contract, timer cleanup and failure propagation, the retry scenario
matrix and expected terminal counts, failure-patch attempt/UID/version guards,
timeout cancellation, foreign-child/parent UID rejection and UID-guarded namespace
deletion. They do not substitute for a live controller run.
