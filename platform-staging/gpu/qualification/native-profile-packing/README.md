# Controlled native5+10GiB qualification preparation

This package prepares the successful Oct9 probes for a new controlled pair:
CPS `native-group-b` with `interactive-native-qualification-5` (5120MiB), and
CIT `native-group-a` with `interactive-native-qualification-10` (10240MiB).
The selected A100, healthy driver generation, cap gate `bc5b128f…`, notebook
`91678610…`, raw CUDA paths and MPS process model remain pinned. Oct9's existing
two-scope5GiB qualification remains historical evidence. This preparation does
not qualify10GiB or production packing.

All commands default to inert. `prepare_harness.py --prepare` performs local
CPU checks and creates a fresh owned0700 private tree with0600 files. It never
starts a Pod, invokes Kubernetes, executes CUDA, sets a cap or releases a
reservation. Root performs normal Source Start/Stop and reviews measurements.
No workload manifest or bypass start fixture is generated.

## Current approved group bindings

`prepare_current_group_harness.py` is the separate entry point for the existing
approved CPS `native-group-b` / `interactive-shared-5` and CIT
`native-group-a` / `interactive-shared-10` groups. It retains their canonical
profile names throughout preparation. The historical `prepare_harness.py`
entry point continues to accept only the retired operator qualification profiles.
The probe source pins, CUDA protocols, kernel witnesses, deadlines, fixed caps,
15GiB budget, two slots, selected GPU/epoch and normal Source lifecycle remain
unchanged. This adapter does not add a workspace or a20GiB profile.

Root supplies an owned0600 private manifest with this closed schema:

```json
{
  "version": 1,
  "state": "Root-reviewed-current-group-plan",
  "binding": {"path": "/private/current-binding.json", "sha256": "<raw SHA256>"},
  "policy": {"path": "/private/actual-current-policy.json", "sha256": "<raw SHA256>"},
  "native_groups": {"path": "/private/actual-enabled-native-groups.json", "sha256": "<raw SHA256>"},
  "sealed_targets": [
    {"pod_uid": "<actual CPS Pod UID>", "journal": {"path": "/private/cps-journal.json", "sha256": "<raw SHA256>"}, "gate_receipt": {"path": "/private/cps-gate.json", "sha256": "<raw SHA256>"}},
    {"pod_uid": "<actual CIT Pod UID>", "journal": {"path": "/private/cit-journal.json", "sha256": "<raw SHA256>"}, "gate_receipt": {"path": "/private/cit-gate.json", "sha256": "<raw SHA256>"}}
  ]
}
```

`binding` retains the fields documented below, using the canonical profiles and
new actual Pod UID/spec/raw Pod captures after normal Source Start. The current
policy and enabled group configuration must agree; the typed v2 deployment
proof and exact reviewed approval subtree are required. Both protected journals
must be `sealed`, match the actual Pod intent/cap/epoch, and equal their public
gate receipts. Changed membership, storage, owners or scopes require another
review. An arbitrary rehashed configuration is insufficient.

```sh
python prepare_current_group_harness.py --prepare \
  --manifest /private/current-group-manifest.json --manifest-sha256 "$MANIFEST_SHA" \
  --source-root /private/exact-oct9-source-root --output /private/fresh-current-group-harness \
  --native-import-binary /private/actual-native-imports --native-import-binary-sha256 "$ELF_SHA" \
  --native-import-build-receipt /private/actual-cpu-build.json --native-import-build-receipt-sha256 "$BUILD_SHA"
```

This command only prepares files. Root still checks actual current Source
provenance, runs the unchanged live host preflight and exact kernel witness
protocol for IPC and VMM in both directions, then normally stops/reconciles both
participants. A fresh start invalidates old UID/spec/seal bindings. The original
private probes are explicit inputs, not published or reconstructed here.
The current adapter pins the actual reviewed controller model SHA `630d43cc…`;
the historical entry point retains `f40ef40f…` (SDK commit `aa3152b`). It adapts
only that dependency pin in the rendered preflight and updates dependent
preflight hashes. All original probe/witness source pins remain unchanged.
Preparation does not authorize changing the active controller or driver.
A protected current capture or controller compatibility mismatch fails clearly
and must be reviewed before execution.
The receipt stays `fresh_cross_pod_hardware_qualified: false`.

## Actual inputs

`prepare_harness.validate_binding` is the closed schema. Supply an owned0600
private JSON object with these fields; derive values from actual captures:

| Field | Required value/source |
| --- | --- |
| `version`, `state` | `1`, `Root-reviewed-controlled-plan` |
| `policy_hash` | Exact qualification policy; current proposal is `sha256:02316f90f705f5550ab54d1d514ed48f73aa6a13324eea7d4aeaaef959af2fd5` |
| `observer_uid` | Actual existing `gpu-operator/cps-native-driver-control` Pod UID |
| `pool` | `node`, `node_uid`, `boot_id`, `gpu_uuid`, `driver_generation`, `budget_mib`, `measured_free_bytes`, `headroom_bytes`, `measurement_sha256` |
| `pool_measurement` | `{path,sha256}` raw pin for the fresh NVML capture |
| `retired_capture` | `{path,sha256}` raw pin for the complete explicit original retirement journals |
| `targets` | Ordered CPS5 then CIT10; each has `source`, `workspace`, `namespace`, `name`, `cap_mib`, `profile`, `pod_uid`, `spec_sha256`, `pod_capture:{path,sha256}` |

Pool identities are selected node `k3s-wk-gpu2`, node UID
`3336cdd5-d245-436e-b57c-2f66c6dcaa41`, boot
`209f8bc9-a478-48e4-925a-6e07ffa56f7a`, GPU
`GPU-16128952-b438-556a-00bb-93039ee24e56`, driver generation
`b10498fc-9153-4394-875a-ea7cfb498625`. The budget is15360MiB and must fit actual
free bytes minus positive headroom. `measurement_sha256` equals the raw NVML
capture pin. The capture must be at most one hour old, match the selected
device/boot, have coherent memory values, and current/pending MIG both disabled.
`capture_nvml.py` uses the original primary NVML header
`c9b494b7c8015b6ae7aca62b2ce98e6b13f3277a2bec80de528371e725d54012` v1 memory ABI.
It checks the returned UUID and records that it does not verify driver generation;
the protected host observer independently verifies that epoch before/after.

Target namespaces/names are `jupyterhub/jupyter-cpsnativegroupb--rtc` and
`cit-jhub/jupyter-citnativegroupa--rtc`. Preparation checks actual Ready Pod
image IDs, ordinary UID1000/GID100/no preload, successful first cap gate,
successful second device identity initializer and its exact source, canonical
spec SHA and exact5120/10240 policy-bound gate arguments. Live preflight repeats
those checks against fresh Core reads and protected native journals/gates.

`retired_capture` uses the existing closed version1 retired-caps schema:
`version,node,node_uid,boot_id,gpu_uuid,driver_generation,controller_sha256,records`.
Each record is `{pod_uid,journal_sha256,record}` from actual protected original
journal bytes. The exact controller model `f40ef40f…` validates finite typed
retirement proofs. Every retained row must be offline/zero charge with its
original cgroup and gate absent. The complete inventory must equal the explicit
retired records plus the two active targets. The count is supplied from current
captures; historical six-retired inputs are not treated as current.

## Preparation and execution recipe

Use the unchanged frozen SDK controller and dependencies:

```sh
export PYTHONPATH=/tmp/cps-native-authority-test-deps-20261009:/home/bjoern/git/cps-compute-worktrees/native-profile-packing-20261011/src
PYTHONDONTWRITEBYTECODE=1 /home/bjoern/git/cps-compute/.venv/bin/python prepare_harness.py
```

Root supplies the actual binding path/raw SHA and fresh private output path:

The original native-import ELF accepts only the old caps. First emit the narrowly
adapted C source (only the closed parser adds10240) into a fresh private directory:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/bjoern/git/cps-compute/.venv/bin/python prepare_harness.py \
  --emit-native-import-source --output "$ROOT_PRIVATE_BUILD_SOURCE"
```

Root compiles that source offline with the approved Ubuntu CPU image
`sha256:9720ec70a8a903914d26fd6a6aa3dec9eb11524ea4fac6f6ebc81827b8e18773`,
the pinned original CUDA header `7a79d67ca888061b1dfbe4739b51ad64f85a2f3ad874947ce09b2c635b4c7072`,
and the original `-std=c11 -Wall -Wextra -Werror -O2 -I/headers ... -ldl` flags.
The compile recipe must use no network or devices, a read-only container, all
capabilities dropped and no new privileges. Root captures the actual compile
exit/logs, inert no-argument readback and ELF ABI version information.
`validate_native_build` binds those actual source/header/ELF/log/ABI pins, exact
offline argv/image identity, zero exits and false GPU/hardware flags. The maximum
required glibc version must fit the pinned Ubuntu notebook's2.39. This preparation
does not emit a build receipt or treat a CPU build as a hardware result.

```sh
PYTHONDONTWRITEBYTECODE=1 /home/bjoern/git/cps-compute/.venv/bin/python prepare_harness.py \
  --prepare --binding "$ROOT_ACTUAL_BINDING" --binding-sha256 "$ROOT_ACTUAL_BINDING_SHA" \
  --source-root /home/bjoern/.local/state/cps-group-native-20261009/group-probes \
  --native-import-binary "$ROOT_ACTUAL_NATIVE_ELF" --native-import-binary-sha256 "$ROOT_ACTUAL_NATIVE_ELF_SHA" \
  --native-import-build-receipt "$ROOT_ACTUAL_CPU_BUILD_RECEIPT" \
  --native-import-build-receipt-sha256 "$ROOT_ACTUAL_CPU_BUILD_RECEIPT_SHA" \
  --output "$ROOT_PRIVATE_HARNESS"
```

`preparation-receipt.json` pins all25 original artifacts, rendered files,
actual inputs, policy, target caps/spec/UID and measured pool. Its state is
`prepared-awaiting-Root-controlled-execution`; all qualification flags are false.
`operator-argv.json` contains exact generated argv for Root review. Root creates
the owned0700 `measurements` directory and confirms the existing marked kernel
witness collector/validator/transport and VMM bridge match the generated pins
before executing import trials. No collector staging or publication is performed
by this package. The original `managed/run_managed.py` is a pinned library for
`run_kernel_controls.py`; use the new control wrapper rather than its historical CLI.
The generated VMM bridge uses a fresh path ending in the actual CIT Pod UID's
first12 hexadecimal characters; stage only the generated bridge/endpoint there.
Endpoint and host native-cap guards map only the exact CPS5/CIT10 lifetime UIDs
to their respective finite caps. Kernel witness sources and attribution fences
remain unchanged, and every original input source remains pinned.

The controlled measurements are:

1. Both actual parents: unchanged raw64MiB vector kernels, typed managed801
   denial, ordinary recovery, explicit context/staged-file cleanup, final native zero.
2. CIT10 exhaustion while the CPS5 peer runs verified kernels. An untouched
   10496MiB allocation must return typed CUDA OOM. Then held256MiB steps reach
   at least9216MiB, fail within the finite10GiB bound, and recover64MiB. Peer
   kernels must bracket OOM and completed recovery without an excessive gap.
3. CIT10 same-Pod aggregate: unchanged2048MiB holder plus64MiB working peer;
   victim held at least6656MiB. Both cases hold the meaningful allocation for30s
   while fresh native inventory verifies charge and the15360MiB aggregate bound.
   Seals, Pod lifetimes, epochs and all prior retirements must remain unchanged;
   both active parent charges must return to zero.
4. Original same-parent VMM-direct/IPC/VMM positive controls adapted to CIT10;
   both-direction cross-parent IPC and VMM use the same valid opaque handle,
   same-parent positive control, independent kernels, recovery, actual importer
   PID/cgroup attribution and marked kernel denial witnesses. Endpoints and host
   observers bind each actual lifetime's5/10GiB cap; kernel collector/validator/
   transport bytes remain unchanged. No API error alone qualifies import isolation.
5. MPS on CIT10: the original two clients and private non-root control/server
   must share the exact workload cgroup. An untouched10496MiB allocation and
   alternating held allocations must produce CUDA error2, both clients recover,
   and Root attribution proves all four original process lifetimes and cleanup.
   The CPS5 peer brackets registration, OOM, recovery and daemon cleanup.
6. Creator-exit retention uses the original helper with target-specific cap guards,
   with Root's fresh
   actual singleuser cohort baseline pin supplied separately. Its generated base
   argv intentionally omits those pending arguments.

These measurements do not establish maximum-profile runtime overhead or safe
production capacity for every profile. Those capacity receipts remain separate.

## Stop and restart witnesses

Root uses normal Source Stop (including a normal explicit resume if it returns
409), captures both immutable enrollment/cleanup ConfigMaps, the released ledger,
and a complete unpaginated actual PodList. Root captures all newly retired
protected journals with raw pins. `run_retirement_witness.py --execute` accepts
that updated capture and streams only the protected read-only observer; it
requires both original controlled UIDs be retired and all inventory rows bound.
Its source pin, preflight pin, actual binding pin, updated retirement pin and
private output are mandatory CLI inputs. It performs no cap or cleanup writes.

`inspect_stop.py --inspect --manifest PATH --manifest-sha256 RAW_SHA` runs offline.
The closed manifest pins `binding,before,ledger,pods,physical` and ordered lists
`enrollments,cleanups,journals`, each as `{path,sha256}`. Each list contains exactly
two entries ordered CPS5 then CIT10. `journals` pins the complete original terminal
journal files as raw bytes, including their actual whitespace and final newline;
do not normalize these files before pinning them. It binds full immutable enrollment
to the exact released allocation, attempt, actual cap intent and original UID;
typed cleanup to original enrollment UID/hash/journal; zero-charge retirement to
the exact original identity/proof. Every prior retirement must remain identical,
with exactly the two new terminal lifetimes added. Paginated Pod absence is
rejected. Its receipt stays `stop-witnesses-consistent-awaiting-Root-review`; the
orphan claim is limited to original Pod UID/cgroup.

The physical observer's `journal_sha256` is the SHA256 of the raw protected file.
The immutable cleanup's `retirement.journal_sha256` is the SHA256 of canonical JSON
for the complete typed terminal record. These digests can differ. The inspector
checks both against the supplied full record, including its original seal,
intent, identity, exact finite readback and retirement proof. The output preserves
both digests as `journal_raw_sha256` and `journal_canonical_sha256`. A missing raw
journal, stale file pin, swapped lifetime or rehashed replacement seal fails.
The earlier frozen inspector's direct comparison of these two digest conventions
can fail on a valid newline-terminated journal; preserve that failed output and
its frozen source. A later offline replay is a separate inspector result, never
a replacement hardware observation or a completed restart gate. If Root
reconstructs bytes from a protected capture's full record, the reconstruction
must match the captured raw SHA exactly and be identified as an offline byte
reconstruction, rather than a fresh journal capture.

Root then performs normal Source Start, captures new actual UID/spec bindings,
and prepares a fresh harness against the complete updated retired capture. Run
the new kernel controls and keep the same prior terminal records. Root separately
reviews Source authorization/attempts, storage/PVC/PV/sentinel continuity and normal
API lifecycle evidence; this package does not fabricate that evidence or a six-gate
passed artifact.

## CPU verification

```sh
PYTHONDONTWRITEBYTECODE=1 /home/bjoern/git/cps-compute/.venv/bin/python \
  -m unittest discover -s . -p test_prepare_harness.py -q
```

The33 methods exercise changed cap/scope/policy/UID/budget/pins, duplicate JSON,
inert default and every generated argv, exact retained kernel witness bytes,
both target-cap guards and swapped-cap/old-lifetime rejection, actual CPU build
receipt/source/header/ELF/offline-recipe mutations, oversized success without touch,
typed OOM/recovery, generated MPS allocation/free methods through41 stepped calls,
direct untouched CUDA denial, MPS stale receipts/cleanup/
peer windows, NVML64-bit ABI and negative results, and Stop pagination/changed
history/foreign cleanup/nonreleased ledger, raw versus canonical journal pins,
full-record drift, duplicate keys, swapped journals and stale CLI file pins.
Hardware boundaries use explicit CPU doubles; their data and results are never
published as hardware evidence.

For the current canonical adapter, use the reviewed SDK source containing the
`630d43cc…` controller model on `PYTHONPATH` and discover
`test_current_group_harness.py`. Its eight self-contained CPU tests cover exact
group approvals, both durable seals and actual Pod spec bindings, denied scope/
profile/membership/cap/epoch changes, the separate historical profile contract,
inert preparation, and unchanged witness/protocol bytes during controller
dependency repinning. They do not execute the private original probe closure.
When that closure is unavailable, the corresponding original test classes skip;
a passing CPU result must not be reported as hardware or full render acceptance.
