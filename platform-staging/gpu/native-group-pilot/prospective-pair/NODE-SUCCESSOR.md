# Prospective CPS531 pair: finite Node source successor

This directory contains the byte-exact published Node8c source and a pure source
transformer for its historical validator and a matching successor of its exact
flat operator-epoch helper. Both successors use one independently pinned Root
contract; the emitted Node source pins the exact emitted helper SHA256.
It creates no accounts, registrations, Pods, driver allocations,
images, configuration or live authority. No real future target capture or Root
contract is included. The current D48 qualified-group behavior remains intact.

The actual Node8c validator rejects a prospective operator-qualification config
when reading retained39ef terminal history: its current-policy predicate permits
only D48 with the original CPS5/CIT10 scopes. The regression first reproduced
that rejection against `node8c.py`. The successor permits one additional finite
configuration bound to an independently reviewed raw contract SHA256. It changes
only `validate_historical_configuration` in the historical-only output. The paired
output additionally replaces the single exact helper SHA256 in Node main and
only `node_configuration` in the flat helper. All other source bytes remain exact.

The contract is a closed JSON object with these fields:

| Field | Required value |
| --- | --- |
| `version` | Integer 1 |
| `policy_hash` | Nonzero canonical SHA256, distinct from D48 and 39ef |
| `workspaces` | Exactly two bounded `cps:operator-qualification-531-*` scopes; qualification5/5120MiB and qualification20/20480MiB |
| `terminal_history_sha256` | Canonical SHA256 of the complete verified baseline authority mapping used as prospective history, including released D48 lifetimes |
| `operator_people` | Independent Root allowlist of canonical nonstudent UUIDs |
| `operator_members` | Exact scope keys; nonempty disjoint UUID lists whose union equals that allowlist |

The prospective configuration must additionally be enabled version 2,
`operator-qualification`, with max 2 workspaces, budget 25600 MiB, headroom
1024 MiB and measured free memory at least 26624 MiB. The original immutable 39ef
configuration, its raw data reference, original5/20 scopes, nonrecursive history,
physical node/device/boot/driver epoch and original25GiB budget are still checked.
The unchanged enrollment path still verifies retained enrollment/completion UIDs,
full hashes, released ledgers, inert journals and absent historical Pods.

The same successor permits the finite return to the exact D48 qualified-group
policy and its 15360 MiB pool. A retained pair configuration must match the
independently reviewed Root policy, complete terminal-history hash and exact
two CPS qualification5/20 scopes, remain enabled in operator-qualification mode,
and retain the measured 25600 MiB budget, max 2, 1024 MiB headroom and at least
26624 MiB free memory. Only this exact pair may supply historical capacity after
return; all immutable-reference, physical-epoch and terminal-custody checks remain
in force. A current D48 workspace requesting 20480 MiB still fails the unchanged
active-cap validator. This adds no general recursive authority or new contract
fields.

The Node config itself has no people or workload-image fields. Contract membership
is provenance for this finite source output; it does not establish Directory or
Source identity. Before any runtime use, Root must independently review the real
two Source snapshots, disabled531 catalog/policy, complete current authority and
history, dedicated neutral owners/PVCs, disjoint actual operator people and
matching Gateway/Hub approvals. The historical916 evidence is retained as
historical evidence; this transformation establishes no new hardware gate.

Default invocation is inert and reads no files:

```sh
python3 node_successor.py
```

Only after an independently reviewed real contract exists may Root emit the
matched two-file source map as JSON:

```sh
python3 node_successor.py --emit-bundle --contract /reviewed/root-contract.json \
  --contract-sha256 <independently-reviewed-bare-64-character-raw-sha256> \
  > /reviewed/candidate-node-sources.json
```

The raw SHA256 must be supplied before any input file is opened. Duplicate keys,
nonfinite JSON, unknown fields, students, overlapping people, arbitrary source
bytes and unknown historical/pair configurations fail closed. The transformer
does not run the emitted source. `--emit` retains the historical-only output for
the previous source review; it does not update the helper pin and is insufficient
for the protected pair. A later separately reviewed runtime release must preserve
the remaining flat bundle/process pins and package the matched pair together.
No dynamic approval consumer upgrade is implied by this source-only result.

## Protected epoch: actual baseline RED and finite source successor

The same published image's `opt/native/native_operator_epoch.py`, SHA256
`890cebd7c1903a680e4dc836ec6f81f097198c2fed438ade6b2fa62157864bbd`,
has an independent guard at lines 75–96: `node_configuration` permits only
qualification10/cap 10240 and a budget at most 15360 MiB. Its
`OperatorNodeEpochPublisher._actual` (166–170) calls that guard;
`build_installed` (273–303) immediately calls the publisher. The new regression
reproduces that exact failure through actual Node main, source pin validation,
`build_installed` and the publisher before its first CAS.

`successor_bundle` admits exactly the same Root-pinned pair policy, complete
terminal-history hash, scopes and pool bounds in the helper's `node_configuration`.
The existing qualification10 predicate is retained as the other branch. Immutable
config UID/RV/full data, process/controller/ReplicaSet/ServiceAccount provenance,
current node/boot/driver/device epoch, the three-observation publisher path and
exact UID/RV/data CAS/readback are unchanged. No helper import is redirected to a
Core package. The helper hash increment is derived from the actual emitted bytes.

The coordinator-side `cps_compute.native_scheduler_node_epoch` observer also
requires the qualification10 profile in its constructor and a 10240 MiB cap in
`observe`; `native_scheduler_coordinator_server` selects it for operator-only
configuration. Future work must qualify both the selected Node publisher and
matching coordinator observer. These history-transformer tests qualify neither
protected execution path.

The selected Node publisher does not invoke `NativeGroupQualification.from_config`.
The separate `OperatorNodeEpochObserver` (119–155) imports that type only inside
its constructor. The Node's operator branch (1040–1043) constructs the publisher,
and its main guard (1010–1011) forbids overlapping dynamic approval inputs. This
supports retaining old Core modules on this path; it does not qualify arbitrary
future caller changes.

The selected-factory tests load all six exact flat snapshot sources plus the
sealed `native_approval_revision.py` and `native_approval_process.py` references.
They run real Node main, exact helper pin loading and immediate publisher ACK.
Only private-file loading, Kubernetes transport and hardware access are replaced
by synthetic boundaries. They prove legacy10 compatibility, pair admission,
drift rejection before CAS and no replay after an ambiguous CAS response. These
are offline source tests, with no hardware or production-readiness claim.

Offline regression command:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/bjoern/git/cps-compute/.venv/bin/python -m pytest \
  -q -p no:cacheprovider \
  platform-staging/gpu/native-group-pilot/prospective-pair/test_node_successor.py \
  platform-staging/gpu/native-group-pilot/prospective-pair/test_node_epoch_successor.py
```

## Complete retained history capacity (16 October 2026)

The prospective Node generator and offline candidate mapper now accept at most
128 terminal entries and 128 complete allocation records. The frozen Node8c
source and ordinary legacy validator remain unchanged at 64 entries. The only
additional generated Node difference is the exact terminal collection bound;
entry validation, physical/source pins, member limits and custody checks remain
unchanged. Overflow, active ledger records and changed claim checksums fail.

An offline replay retained all 85 released allocations and 75 enrolled terminal
entries from the 15 October capture. Its authority list omitted the referenced
immutable configuration; the replay retrieved it read-only and verified its
original UID and canonical data hash before validating any historical entry.
The original capture bytes remain unchanged. This replay is not a fresh capture,
a GPU test, a live deployment, or evidence of production qualification.

The legacy configuration inverse still describes CPS+CIT qualification. This
capacity change does not turn it into a fresh CPS+CPS pair inverse. A reviewed
finite pair restoration path remains required before the hardware run.

Validation: the native-group pilot suite passed with **631 tests and 851
subtests**, with 14 explicitly private-input skips. The test environment uses
the compute and Hub adapter source paths, the admin release-integration source
and isolated `cel-python==0.4.0` test dependencies. No cluster mutation or
hardware run was performed by this change.

The separate [fresh-pair Node inverse](NODE-PAIR-INVERSE.md) now derives a
complete terminal archive and Node configuration/Deployment restoration for
the exact CPS+CPS pair. Coordinated Gateway policy/runtime and Source restoration
remain separate execution prerequisites; the legacy CPS+CIT inverse is unchanged.

The operator file reader also changes for the reviewed pair: full preserved
history can exceed32 KiB, so it permits up to256 KiB only after matching the
pinned contract policy/workspaces/history. Other modes retain32 KiB. The original
root0400/no-follow/link-count guards remain. Tests execute this reader with large,
oversized and wrong-mode files, including unchanged small legacy behavior.
