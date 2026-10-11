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

```sh
PYTHONDONTWRITEBYTECODE=1 /home/bjoern/git/cps-compute/.venv/bin/python prepare_harness.py \
  --prepare --binding "$ROOT_ACTUAL_BINDING" --binding-sha256 "$ROOT_ACTUAL_BINDING_SHA" \
  --source-root /home/bjoern/.local/state/cps-group-native-20261009/group-probes \
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
4. Exact original same-parent VMM-direct/IPC/VMM positive controls on CIT10;
   both-direction cross-parent IPC and VMM use the same valid opaque handle,
   same-parent positive control, independent kernels, recovery, actual importer
   PID/cgroup attribution and marked kernel denial witnesses. Endpoint/collector
   bytes are retained unchanged. No API error alone qualifies import isolation.
5. MPS on CIT10: the original two clients and private non-root control/server
   must share the exact workload cgroup. An untouched10496MiB allocation and
   alternating held allocations must produce CUDA error2, both clients recover,
   and Root attribution proves all four original process lifetimes and cleanup.
   The CPS5 peer brackets registration, OOM, recovery and daemon cleanup.
6. Creator-exit retention uses the exact original helper, with Root's fresh
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
`enrollments,cleanups`, each as `{path,sha256}`. It binds full immutable enrollment
to the exact released allocation, attempt, actual cap intent and original UID;
typed cleanup to original enrollment UID/hash/journal; zero-charge retirement to
the exact original identity/proof. Every prior retirement must remain identical,
with exactly the two new terminal lifetimes added. Paginated Pod absence is
rejected. Its receipt stays `stop-witnesses-consistent-awaiting-Root-review`; the
orphan claim is limited to original Pod UID/cgroup.

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

The24 methods exercise changed cap/scope/policy/UID/budget/pins, duplicate JSON,
inert default and every generated argv, exact retained endpoint/collector bytes,
oversized success without touch, typed OOM/recovery, MPS stale receipts/cleanup/
peer windows, NVML64-bit ABI and negative results, and Stop pagination/changed
history/foreign cleanup/nonreleased ledger. Hardware boundaries use explicit CPU
doubles; their data and results are never published as hardware evidence.
