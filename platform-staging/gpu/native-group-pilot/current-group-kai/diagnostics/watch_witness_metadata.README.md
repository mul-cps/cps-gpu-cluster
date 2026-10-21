# Bounded Node witness metadata sampler

Default invocation is inert: no Kubernetes import, kubeconfig access, API call or output file. This is an operator-local Root-authorized diagnostic; it does not require host UID0. It uses that operator's kubeconfig only after `--execute`. It never writes Kubernetes resources, acquires a lease, starts a workload or touches Node private state, drivers or Source SQL.

Baseline command, from this directory, using a Python environment with the Kubernetes client installed (choose an unused filename):

```sh
python -I -B watch_witness_metadata.py --execute --seconds 10 --output /absolute/private-0700-directory/witness-baseline-10s.jsonl
```

For the separately controlled next normal Start, use a distinct exclusive output and a duration10..420 seconds. The existing output parent must be owned by the invoking operator and mode0700. The script opens the file via the parent directory FD with O_EXCL/O_NOFOLLOW and mode0600; existing files and symlinks fail. No credential or private ledger/enrollment body is printed or written.

There are exactly two initial exact-name ConfigMap LISTs and at most two concurrent watch streams, both in cps-native-system: cps-native-approval-ack-node and cps-native-gpu-allocations. Each watch uses metadata.name field selection and the initial collection resourceVersion, then last actual event/bookmark resourceVersion. Server timeouts are1..30s and bounded by the remaining sample duration; normal EOF/disconnect resumes at that same version. Explicit timeout_seconds disables the installed Kubernetes SDK's implicit410 retry. HTTP410 fails the whole sample as history_lost; no relist, new initial LIST, guessed continuity or silent gap is allowed. UID replacement or deletion also fails. Authentication/404 failures are terminal; other transport failures are marked and retried only within the original deadline.

Each record has local UTC observed_at and monotonic_elapsed since sampling began. INITIAL/ADDED/MODIFIED/DELETED contain actual CM UID/RV and raw state/ACK SHA256. ACK output includes only checked timestamp, process UID, safe immutable head-reference fields and whitelisted generation-witness metadata. Custody witness retains ledger UID/RV/state hash and opaque enrollment name/UID/pod UID/hash; pending witness retains pod UID/document hash. No membership, owner/principal, token, arbitrary annotations, error body, binding IDs, journal body or full ACK/ledger data is exported. Invalid annotation content yields only its SHA256 plus valid:false. A witness valid flag means metadata parsing succeeded; it is not authorization or hardware qualification. matches_ack binds the annotation's ACK digest to the observed canonical ACK.

Ledger output contains only actual UID/RV/raw state hash, allocation count and fixed state-name counts. Every watch record is flushed immediately. END reports complete and threads_drained. On exit both worker stop flags are set and all threads are joined within one35-second drain bound; network requests have explicit bounded connect/read timeouts. A non-drained worker is a terminal error, never a successful receipt. A failed initial LIST cannot produce complete:true.

These observer receipt times measure arrival at this client. ACK ack_observed_at is the producer's earlier timestamp, not PATCH completion. Two streams are not an atomic cross-object snapshot. Watches can show a matching witness appear and be withdrawn; a10-second baseline or quiet trace alone does not prove stable future readiness. Compare final ledger publication to the first stable matching ledger+enrollment witness across the separately authorized next Start.

Offline verification:24 tests cover inert startup, no credential/body export, parsed witness fields, UID replacement, private exclusive output, last-RV reconnect/bookmark behavior, terminal410, actual two-worker cleanup, initial-LIST failure and duration bounds. No live sampler run was performed by the implementation agent.

Initialization fix: each MostRecent named LIST must contain exactly one actual matching name/namespace/canonical UID, a valid collection RV, and no pagination/remaining items. The object resource_version remains recorded independently; INITIAL.collection_resource_version is the watch cursor. An unchanged ledger object may have a compacted old modification RV even though it is present in a fresh consistent collection snapshot. This is initial snapshot establishment, never a recovery relist after410. The existing regression reproduces stale object RV1/fresh collection RV100, plus nine fail-closed LIST-shape cases.

Typed-list compatibility: after validating v1/ConfigMapList and complete exact-name membership, absent item apiVersion/kind are supplied as v1/ConfigMap on a copy. Present conflicting values are rejected. Standalone watch ConfigMaps still require their explicit GVK.
