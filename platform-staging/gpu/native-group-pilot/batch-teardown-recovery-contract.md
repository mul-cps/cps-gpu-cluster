# Two failed pilot journals, one physical teardown

Status: qualification only; not a general driver maintenance or release tool.
The default command is inert and performs no Kubernetes, private host, GPU,
module, or allocation action. Nothing here enables ordinary group GPU sharing.

This transaction is restricted to these original sealed 5120 MiB journals:

| Hub | Pod name | Original Pod UID |
| --- | --- | --- |
| CIT | `cit-jhub/jupyter-citnativegroupa--rtc` | `9c4c2743-60ce-4ccc-81e7-4e7dbadeaf2c` |
| CPS | `jupyterhub/jupyter-cpsnativegroupb--rtc` | `cf045797-f4d4-4d17-9c1a-82a8837a2bc5` |

The ordered plan array is CIT then CPS. Each plan is the existing, fully
validated v1 plan. Both preserve the actual original journal bytes, complete
six-Pod registered scope, immutable enrollment UID/hash, binding/attempt,
allocation hash, ledger UID, complete GPU PCI inventory and journal-directory
identity. Both share the same pinned Root command. Its hash must replace the
draft's pending zero placeholder before execution.

The only permitted host is `k3s-wk-gpu2`, node UID
`3336cdd5-d245-436e-b57c-2f66c6dcaa41`, boot
`209f8bc9-a478-48e4-925a-6e07ffa56f7a`, driver generation
`35423d5e-5a08-4bc8-a555-1a3be83c3038`, GPU
`GPU-16128952-b438-556a-00bb-93039ee24e56`. The reviewed module bytes are
Core `194a10d24c64eea9240b86845659936f1051b184c63c471f8ebeda2c5bf4495c`
and UVM `b2ae67722e9e21a70c319aeed2184f5b2d1f23b8e32dea00816cfd5cd2c3ee61`;
the healthy original probe source is
`e326581c158ff192fed55cc62012c22179cece2216a500c4ed59499296643376`.

## External release freeze is required

Host locks do not fence a gateway release API. Root must pause the node agent,
temporarily scale the shared `cps-compute/compute-gateway` Deployment to zero,
wait for every selected gateway Pod to disappear and all Service endpoints to
become empty, and prevent other operator release calls. Preserve this
freeze through both local completions and the final batch success receipt. Do
not restore the gateway after a partial failure until both bindings' actual
state and proof have been reviewed.

The publisher requires an actual API freeze observer before any host operation,
before each immutable audit/cleanup creation, before local publication and in
both final API/host readback rounds. The observer pins the Deployment UID,
immutable image, complete selector and Service UID/selector; requires observed
zero replicas, no gateway Pods, and completely empty EndpointSlice backends.
It never scales or patches anything. These repeated observations detect a
broken maintenance freeze; they cannot replace Root's exclusive maintenance
ownership or make ConfigMap creation atomic with Deployment changes.

The private `--release-freeze-config` JSON has these exact keys:

```json
{
  "version": 1,
  "namespace": "cps-compute",
  "deployment": "compute-gateway",
  "deployment_uid": "f5f9b266-433d-4825-83de-d51e31c71648",
  "service": "compute-gateway",
  "service_uid": "402a4453-127e-43fb-a2b9-1b6bc9f316de",
  "pod_selector": "app=compute-gateway",
  "images": ["THE-ROOT-REVIEWED-CURRENT-IMAGE@sha256:ACTUAL-DIGEST"]
}
```

## One shared lock interval

The Root helper is the same new source in `--execute --qualification
--root-fence` mode. Stage it, its pinned source dependencies, and review files
as Root-owned, regular, single-link mode 0400 files in Root mode 0700 directories.
Existing journal/driver/maintenance lock files must already be Root mode 0600;
the helper never creates replacement locks. The review pins the exact source,
dependency manifest, current modules/health/epoch, two allowed UIDs, and actual
Root release-freeze evidence. No secret belongs in any plan, review or proof.

The observation dependency is unchanged `teardown_fence.py`
`d2fa70fba12428a35fc0665981fb4d33136e7ee75625f8de417a15bde80afeb0`.
The v1 publisher is unchanged `teardown_recovery.py`
`930bb1ad283526779da3e5c868b9e701b4d1d2df1cc2aac36a3ee5321e992eb0`.
`dependencies.json` pins exactly `node_agent.py`, `abort_before_gate.py`, and
`source-snapshot.json`; every byte hash is checked before those modules load.

1. The publisher verifies the actual Node, absence of every scoped Pod, current
   immutable enrollments and both held ledger allocations. It freezes the
   entire ledger UID/resourceVersion/raw state for later equality checks.
2. One Root process acquires the existing journal, driver-loader and maintenance
   locks once. It collects both genuine healthy-driver before proofs: actual
   original journal/gate bytes, exact module/manifest/health, zero GPU memory,
   zero compute apps, complete NVIDIA character-device FD scan, no runtime
   tasks or native writers, and identical actual lock identities. It durably
   writes the original plans/before proofs to a new Root-only batch evidence
   directory. Existing evidence is never overwritten.
3. An explicit `verify-batch` request collects both before proofs again and
   requires exact equality. Only then does this helper invalidate the exact
   current generation and load manifest, with directory fsync. The legacy
   helper's earlier-generation invalidator is never used or reconfigured.
4. Root separately unloads the original modules. This helper performs no unload,
   GPU reset, reboot, MIG change, cap unset or native driver operation. Within
   a bounded 120-second wait, it requires no new client/writer. Positive fresh
   teardown proofs require every NVIDIA module absent in both sysfs and proc,
   every prior NVIDIA PCI function present and unbound, old authority absent,
   no replacement load, and stable original journal/gate/locks/quiescence.
5. Still under the same locks, the publisher creates both existing v1 immutable
   audits using each original before and first genuine teardown. It GETs each
   and checks the actual created UID. After fresh physical/API/freeze checks it
   creates both ordinary v1 cleanup receipts and verifies actual UIDs again.
6. Both actual audit/cleanup objects are validated before either local update.
   Existing `complete_local` archives each original, truthfully marks its
   journal cleaned, revokes its gate and publishes its exact receipt-UID
   tombstone. Each receives a fresh positive teardown and the same held locks.
7. Two independent final rounds re-observe the unchanged ledger/enrollments,
   Pod/Node identities, release freeze and immutable audit/cleanup UIDs, and
   fresh physical/local completion proofs. The Root process releases locks only
   after two completion requests and an exact final release request.

The JSONL exchange is nonce-bound and ordered:
`acquire-batch` → `batch-acquired` → `verify-batch` →
`batch-teardown-verified` → optional repeated verification → `publish-batch` →
`batch-local-published` → two `verify-batch-completion` /
`batch-completion-verified` rounds → `release`. The existing RootFence transport
provides bounded JSONL reads, freshness/deadline and process-liveness checks.

## Explicit operator entry points

The normal publisher runs with exact private plan/command/freeze JSON files:

```text
python batch_teardown_recovery.py --execute --qualification
  --plans ACTUAL-FINAL-TWO-PLANS.json --plans-sha256 sha256:CANONICAL-PLAN-ARRAY-HASH
  --batch-id FRESH-CANONICAL-UUID --fence-command PINNED-ROOT-ARGV.json
  --release-freeze-config ACTUAL-PINNED-GATEWAY-SCOPE.json
  --diagnostics-dir PRIVATE-0700-DIRECTORY
```

Its pinned Root command must invoke the protected copy with:

```text
python3.12 /run/cps-native-gpu/operator/batch_teardown_recovery.py
  --execute --qualification --root-fence
  --batch-source-sha256 sha256:ACTUAL-PROTECTED-SOURCE-HASH
  --review-sha256 sha256:ACTUAL-ROOT-REVIEW-RAW-HASH
```

The Root review file is `operator/batch-review.json`, with exact keys `version`,
`qualification_only`, `allowed_pod_uids`, `node`, `node_uid`, `boot_id`,
`driver_generation`, `core_path`, `uvm_path`, `health_path`, `health_sha256`,
`publisher_sha256`, `observation_source_sha256`, `dependency_manifest_sha256`,
`release_writers_paused`, `release_freeze_evidence_sha256`. Current protected
module/health paths are explicit reviewed `/run/cps-native-gpu/...` paths.
The last hash pins `operator/batch-release-freeze.json`, containing the actual
Root maintenance evidence. This file records a verified condition, not a
promise that a future scale-down will work.

Any error stops publication, closes helper-owned lock descriptors and leaves
allocation mutations to the existing authoritative release protocol. Some
immutable receipts or truthful local completions may already exist after a
partial failure. Keep release writers paused, preserve all original evidence,
and obtain a reviewed continuation; this batch tool refuses replay and does
not invent a before proof after unload. There is no automatic reservation
release, manual ledger edit, TTL bypass or retry that discards partial evidence.

Success means `batch-teardown-cleanup-published`, `allocation_released=false`,
`device_calls=false`, `production_qualified=false`. Root must then qualify the
coherent replacement driver, native cap lifetime behavior, notebook startup,
shared-memory isolation/OOM recovery and normal shutdown/release separately.
