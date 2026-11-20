# Qualified native group runtime target — 2026-10-09

The qualified no-MIG pilot is available for the two approved workspaces.
Normal starts, real CUDA controls and normal shutdown cleanup passed. The
qualification fixtures are stopped and their reservations are released.

The target is policy `0.1.1`, hash
`sha256:78fb2d7ca42585a000e58b52c297d072a11dfbc466b19f50aa9d276d567a413f`.
Only `cps:native-group-b` in `jupyterhub` and `cit:native-group-a` in `cit-jhub`
are approved for `interactive-shared-5`: 4 CPU, 16 GiB host memory and a native
5120 MiB cap per workspace. The pool admits at most two workspaces on
`k3s-wk-gpu2`, physical A100
`GPU-16128952-b438-556a-00bb-93039ee24e56`, without MIG. Ordinary GPU
qualification remains false; the eight-GPU catalog capacity and other profiles
do not extend this approval.

The [sanitized evidence summary](../../../../compute-policy/qualification/native-groups-v1.json)
pins the real Root-published proof and all six passing gate reports:
cap assignment, OOM with peer continuity, aggregate accounting, memory import,
restart cleanup and MPS. The notebook is digest `91678610…`, the cap gate is
`bc5b128f…`, and the restart/current gateway is `85f2fbd3…`; the summary contains
the full digests. The five non-restart gates observed the bc5 gateway. The
restart gate observed 85f2, and that difference is retained in the evidence.

The genuine SDK validated the reviewed `NativeGroupDeployment` and registry
authorization for exactly these two scopes. The proposal preserves existing
owner, server, principal, course, term, member, ceiling and complete registered
storage identities, including storage version and read-only paths. Source
grants preserve their original identities and allowances; their profile change
alone grants no additional workspace approval. Historical immutable enrollment,
cleanup and terminal ledger records remain retained. The actual source handovers and live readbacks passed; the final receipt below records their limits.

CIT authorization evidence comes from its controlled owning source service.
It does not establish human CIT OAuth or browser collaboration. Retirement
evidence is limited to the original Pod UID/native cgroup and zero charge; it
does not establish a process-wide orphan inventory.

## Final Root receipt

The [sanitized runtime receipt](qualified-runtime-receipt-20261009.json) binds
the actual results. Raw source captures, credentials, member identifiers and
full Pod objects remain in protected private storage.

| Acceptance item | Actual receipt/status |
| --- | --- |
| Normal source-owned six-grant handover and readback | Passed: four CPS and two CIT profile-only updates; complete readbacks preserved all other grant fields. |
| Normal local/registry profile handover for the two approved scopes | Passed: both normal stopped handovers to `interactive-shared-5`; full storage records unchanged. |
| Live policy/runtime, gateway image and node authority match reviewed pins | Passed: both Hubs on `c4f703…`, gateway `85f2…`, canonical policy; controller retains 14 earlier completed Pod lifetimes. |
| Both approved normal starts, native cap/device gates and real kernel execution | Passed: CPS authenticated console Start HTTP200 (49.86 s); CIT controlled source Start; exact 5 GiB caps and real 64 MiB/256-element CUDA controls on both. |
| Original storage identities and retained historical records preserved | Passed: both registration identities preserved; CPS PVC/PV UID+spec and sentinel retained. Both fixtures stopped normally; native reservations released with immutable zero-charge proofs. CIT first 409 required the same normal Close resume.  |
| Final Root review time and sanitized receipt SHA256 | 2026-10-09T21:28:09.230649Z; `sha256:51985393f2ff538d90f0e6ecef3d81c9b0b79f3ee98ec05a01e28e2627af33cd` |

Follow the [activation runbook](../qualified-activation-runbook.md). The
committed node proposal remains disabled by default and outside Fleet.
