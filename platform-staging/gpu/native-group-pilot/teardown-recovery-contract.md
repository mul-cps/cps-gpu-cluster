# Qualification teardown recovery

This tool is inert by default. It never unloads/loads modules, calls NVML,
changes a device cap, writes SQL, patches the allocation ledger, or releases a
reservation. Root performs module maintenance separately. A SHA-pinned Root
helper derives observations and holds the journal, driver-loader and maintenance
locks throughout publication. A supplied JSON document alone is not authority.

All objects below have **exactly** the listed keys. Hashes are `sha256:` plus 64
lowercase hex characters. UUIDs are canonical. JSON hashes use sorted keys,
compact separators, UTF-8 and no newline; `journal.sha256` hashes actual file
bytes, including their newline. Tool/module/source/load-manifest/gate hashes
also hash actual file bytes. Proof counters must be exact integers, not bools.

## Reviewed plan

```
{version:1, qualification_only:true, operation_id:UUID,
 authority_namespace:"cps-native-system", binding_id:HEX60, attempt:STRING,
 ledger_uid:UUID, allocation_sha256:SHA, enrollment_uid:UUID,
 enrollment_sha256:SHA, fence_command_sha256:SHA, tool_sha256:SHA,
 journal:{record:ORIGINAL_CAP_RECORD, sha256:RAW_FILE_SHA},
 scope:{node:"k3s-wk-gpu2", node_uid:UUID, boot_id:UUID,
        driver_generation:UUID, loaded_modules:[SORTED_NVIDIA_MODULE_NAMES],
        module_sha256:{EXACT_LOADED_MODULE_NAME:SHA,...},
        nvidia_gpus:[{gpu_uuid:"GPU-UUID", pci_bdf:"0000:06:10.0"},...],
        pilot_pods:[{namespace:STRING,name:STRING,pod_uid:UUID},...],
        journal_directory:{device:POSITIVE_INT,inode:POSITIVE_INT}},
 review:{operator:"root",reason:"legacy-cap-after-confirmed-driver-teardown",
         old_module_source_sha256:SHA,load_manifest_sha256:SHA}}
```

The complete node-wide NVIDIA module/GPU lists must be derived by the pinned
helper, including GPU1 and GPU2. The plan must cover every registered pilot Pod
UID on the selected node. Old generation, boot, original journal identity/cap,
actual immutable enrollment, and actual ledger allocation must all agree.
The helper must independently match the actual protected old manifest raw SHA
to `review.load_manifest_sha256` and its loaded module tuple to `scope`.
Only original `sealed` or `cleaned` records qualify; no retirement proof is
fabricated. An already-cleaned journal is preserved byte for byte.

## Root JSONL RPC

The CLI starts the pinned argv without a shell and writes
`{op:"acquire",nonce:FRESH_UUID,plan:PLAN,plan_sha256:SHA}`. The helper acquires
the existing `journal/.writer.lock`, `authority/.driver-loader.lock`, and
`operator/.teardown.lock`. It must verify Root ownership, protected permissions,
matching open-fd/path identity, and exclusive locks, and derive all facts.

Every response is `{event:STRING,nonce:SAME_NONCE,observed_at:UTC_Z,proof:OBJECT}`.
Responses older than 30 seconds, extra fields, mismatched nonce, or lost helper
process fail closed. No unsolicited response is accepted.

`fence-acquired` returns the **before** proof:

```
{stage:"before",operation_id:UUID,plan_sha256:SHA,scope:EXACT_PLAN_SCOPE,
 journal_sha256:ORIGINAL_RAW_SHA,
 locks:{journal:{device:INT,inode:INT},driver:{device:INT,inode:INT},
        maintenance:{device:INT,inode:INT}},
 native_writers_quiesced:true,locks_held:true,driver_healthy:true,
 gpu_memory_bytes:{EVERY_SCOPE_GPU_UUID:0,...},gpu_fd_clients:0,
 compute_apps:0,pod_runtime_tasks:0,gate_sha256:SHA_OR_NULL}
```

CLI then sends `{op:"verify-teardown",nonce:UUID}`. The helper invalidates the
old protected generation while holding the driver lock and waits boundedly for
Root's **external** unload. It must not run module actions itself. It derives
`fence-teardown-verified` with the **teardown** proof:

```
{stage:"teardown",operation_id:UUID,plan_sha256:SHA,node_uid:UUID,boot_id:UUID,
 old_driver_generation:UUID,old_generation_invalidated:true,
 sysfs_modules:[],proc_modules:[],pci_unbound:[EVERY_SORTED_SCOPE_BDF],
 gpu_fd_clients:0,pod_runtime_tasks:0,locks:EXACT_BEFORE_LOCKS,
 journal_sha256:CURRENT_RAW_SHA,gate_sha256:SAME_BEFORE_SHA_OR_NULL,
 native_writers_quiesced:true,locks_held:true,new_load_absent:true}
```

`sysfs_modules` and `proc_modules` must independently inventory **all** `nvidia*`
modules, not merely test two filenames. Each previously recorded GPU PCI BDF
must exist and have no bound driver. Same boot and node identity are mandatory.
No NVML call is made after unload. Physical memory/app zero was proven before
unload; actual module absence and no FDs/tasks prove destruction of old state.
The CLI independently verifies fresh Kubernetes Node UID and Pod absence before
and after publication; host node UID assertion cannot replace those reads.

After actual immutable audit/cleanup ConfigMap create **and GET readback**, CLI
sends `{op:"publish-local",nonce:UUID,plan_sha256:SHA,audit:ACTUAL_CM,
cleanup:ACTUAL_CM}`. Under the same locks the helper calls:

```
complete_local(state_root, plan, audit_cm, cleanup_cm,
               before=before_proof, teardown=teardown_proof,
               lock_fds={"journal":fd,"driver":fd,"maintenance":fd},
               trusted_uid=0)
```

This helper performs no API/device/module action. It preserves original bytes
in a no-overwrite Root0400 archive, removes only an exact owned gate, preserves
an already-cleaned journal or truthfully marks a sealed record cleaned, and
persists the ordinary node-agent completion tombstone pinned to actual immutable
receipt/enrollment UIDs. `state_root` is a fixed Root-helper setting, never an
untrusted RPC path. The helper retains the original before/teardown observations
in memory and never substitutes request assertions.

`fence-local-published` returns the **completion** proof:

```
{stage:"complete",operation_id:UUID,plan_sha256:SHA,
 teardown:FRESH_TEARDOWN_PROOF_WITH_CURRENT_JOURNAL_SHA_AND_GATE_NULL,
 journal_record:EXACT_EXPECTED_FINAL_RECORD,journal_raw_sha256:CURRENT_RAW_SHA,
 archive_sha256:ORIGINAL_RAW_SHA,tombstone:EXACT_NODE_TOMBSTONE,
 gate_absent:true}
```

CLI verifies actual Kubernetes identities again, then sends
`{op:"verify-completion",nonce:UUID}`; `fence-completion-verified` returns the
same completion facts freshly re-read. Finally `{op:"release",nonce:UUID}` must
release locks and exit 0. Root must not resume the node agent or load replacement
modules before this transaction completes. Partial failures preserve audit,
receipt and journal evidence and require Root review; replay is not an automatic
repair path.

The audit ConfigMap is `cps-native-teardown-<binding-prefix40>`, immutable, with
exact binding label and `teardown.json` containing the reviewed plan plus both
verified before/teardown proofs. The ordinary cleanup v1 payload is unchanged.
Its immutable annotations pin audit ConfigMap name, actual UID and payload SHA.
Existing gateway/node consumers trust the Root issuer; they do not interpret
these audit annotations. This tool validates them and persists the protected
ordinary completion tombstone before releasing the fence.

## Integration

Install `teardown_recovery.py` and its existing dependencies
`abort_before_gate.py`, `node_agent.py`, and `source-snapshot.json` in a protected
Root-owned directory visible to the host helper. Pin the complete dependency
closure in that helper's reviewed bootstrap. The embedded SDK models are loaded
from their existing snapshot hashes; no metadata/source pin is changed here.

The helper can import `validate_plan(plan, expected_sha256)`,
`validate_before(proof, plan, plan_sha256)`,
`validate_teardown(proof, plan, plan_sha256, before, *, journal_sha256=None,
gate_sha256=<original-before-gate>)`, `canonical(value)`, `sha256(value)`, and
`raw_sha256(bytes)`. Validators raise `RecoveryError`, a `ValueError`, and never
provide a source-pin bypass. The helper's final observation must call
`read_local_completion(state_root, plan, audit_cm, cleanup_cm, trusted_uid=0)`
to reread protected files, rather than reuse the return of `complete_local`.
Both local APIs return the five completion fields below `teardown`; the host
helper adds the fresh hardware/lock proof and the three operation fields.

CPU verification, without credentials or GPU access:

```sh
python3 -m unittest discover -s platform-staging/gpu/native-group-pilot -p test_teardown_recovery.py
```

After independent source/evidence review, **Root alone** runs the publisher in
one terminal and performs the external module unload in another only after the
helper has acquired locks and verified the before proof:

```sh
python3 platform-staging/gpu/native-group-pilot/teardown_recovery.py \
  --execute --qualification \
  --plan /private/reviewed-teardown-plan.json \
  --plan-sha256 sha256:EXACT_CANONICAL_PLAN_SHA \
  --fence-command-file /private/pinned-root-fence-argv.json \
  --output /private/teardown-publication-receipt.json \
  --kubeconfig /private/root-kubeconfig
```

The argv file is an exact JSON string array, not shell text. Its canonical SHA
must equal `fence_command_sha256`. The plan's `tool_sha256` must equal the actual
recovery Python file byte SHA on both client and host. Default invocation, even
with other supplied flags or nonexistent paths, makes no calls and reads no plan.
An existing audit/cleanup is rejected before teardown; no replay waiver exists.

## Resume an existing first-teardown audit

A failed original publication may have created the immutable audit before the
cleanup receipt. The qualification-only resume mode accepts **only** the original
reviewed publisher source
`sha256:c6902334c25d90acb2f4c55853fc81aa03e38df2d5e4b90534351f7801ddab0e`.
It requires the actual audit ConfigMap UID and canonical payload SHA, preserves
its original plan/before/first-teardown bytes, and never recomputes old health or
memory observations. It rejects any existing cleanup receipt. This is a narrow
continuation, not an arbitrary historical-source or receipt-replay waiver.

The caller first GET-validates the actual immutable audit, selected Node UID,
enrollment/ledger tuple and all registered Pod absence. It then starts a **new**
pinned Root argv and sends this exact request:

```
{op:"resume-after-audit",nonce:FRESH_UUID,plan:ORIGINAL_PLAN,
 plan_sha256:ORIGINAL_PLAN_SHA,audit:ACTUAL_IMMUTABLE_AUDIT_CM,
 resume:{audit_uid:ACTUAL_UID,audit_sha256:CANONICAL_PAYLOAD_SHA,
         fence_command_sha256:NEW_ARGV_SHA,publisher_sha256:NEW_REVIEWED_SOURCE_SHA}}
```

Host helper API `validate_historical_plan(plan, expected_sha256)` accepts only
the fixed original source above. `validate_historical_audit(audit_cm, plan,
audit_uid=..., audit_sha256=...)` returns the validated **original** payload;
`validate_resume(resume, plan, audit_cm)` additionally validates closed new pins
and current publisher bytes. The helper verifies its protected copied audit
and actual reacquired locks, without invoking old health. It emits
`fence-resumed` with a **fresh teardown proof**, including identical historical
lock device/inodes, same boot/node, all NVIDIA modules absent, all prior PCI
functions unbound, old authority absent, unchanged journal, and zero clients/
tasks. Current host proofs must be derived afresh; the old audit establishes the
historical before and first teardown facts, not current driver health.

The helper must accept **repeated** `verify-teardown` requests until
`publish-local`. Original publication sends two such requests, the second after
audit GET readback; resume sends at least one after `fence-resumed`. The remaining
local/confirmation/release sequence is unchanged. Existing local APIs retain
the original audit, validate fresh physical proof independently, and preserve
an already-cleaned journal exactly. New Node/Pod/authority GETs follow before
success. Root must keep modules unloaded until completion is acknowledged.

All four resume pins below are required together and checked before process or
transport initialization. The immutable original plan retains its old command
and source SHA; those fields must **not** be edited to match new code.

```sh
python3 platform-staging/gpu/native-group-pilot/teardown_recovery.py \
  --execute --qualification \
  --plan /private/original-reviewed-teardown-plan.json \
  --plan-sha256 "$ORIGINAL_PLAN_SHA256" \
  --fence-command-file /private/new-pinned-root-resume-argv.json \
  --resume-audit-uid "$ACTUAL_AUDIT_UID" \
  --resume-audit-sha256 "$ACTUAL_AUDIT_PAYLOAD_SHA256" \
  --resume-fence-command-sha256 "$REVIEWED_RESUME_ARGV_SHA256" \
  --resume-publisher-sha256 "$REVIEWED_NEW_PUBLISHER_SHA256" \
  --output /private/new-resume-publication-receipt.json \
  --kubeconfig /private/root-kubeconfig
```

The output directory must be owned private0700. Root RPC stderr is retained in
a uniquely named0600 `.stderr.log` there, including EOF/timeout failures. An
execution exception writes a0600 `<output>.failure.json` with operation/plan,
error and diagnostic path. Neither log is automatically deleted. The host must
also persist its validated Root proofs and diagnostics under protected paths
before sending them, while holding the locks. Historical completion without an
actual immutable audit is outside this resume mode.
