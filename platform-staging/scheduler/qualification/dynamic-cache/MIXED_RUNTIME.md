# Dynamic mixed-profile qualification candidate

Status: **prepared offline / not deployed or live qualified**. Dynamic KAI/HAMi/MPS
sharing remains the selected architecture. This fixture uses no MIG and changes
no GPU mode, daemon, node, admission policy or production profile.

The candidate comprises one immutable ConfigMap and three **suspended Jobs** on
`k3s-wk-gpu2` in `cps-gpu-qualification`: a 5 GiB independent peer, a 10 GiB workspace
and a 20 GiB workspace. Each uses the packaged compiler's private emptyDir cache
initializer, UID 1000/GID 100 and its own cache inode. The indexed HAMi limits are
5120/10240/20480 MiB. Trusted KAI device selection must place all three on the same
observed physical card; the renderer supplies no GPU placement override.

The exact package tuple is:

- Source: `40b9525097776e0d5927242ca625a27dadbd797c`.
- Image: `ghcr.io/mul-cps/cps-compute:qualification-40b9525@sha256:b3802a7f70077ff56adbc060d1177409eeff76c8b3cf8ccf9f39047c1e6716bf`.
- Wheel SHA256: `8321127b7db5f6554ddde60f9bb916a7414d570a3405c209632dd142210fe0f4`.
- Runtime compiler module SHA256: `93f4e01c3682e52192d43c130073b3daf50c59ea7bd06342971f5f4add0a2b68`.

KAI's proposed global limits/portions are 5324m/0.13, 10240m/0.25 and 20480m/0.5.
The 20 GiB injector strings have **not** been observed in a live run. These are
explicitly unqualified candidates: unexpected actual strings fail evaluation;
a passing synthetic fixture is no live proof of the candidates or packing.
The known 5 GiB rounding remains separate from the canonical indexed limit.

## Required independent receipts

`mixed_render.py` accepts the existing preflight shape plus node `ready:true`,
`mpsReference` and `mpsMaintenanceReview`. `mixed_contract.py` defines the closed
schemas. The reference must describe a fresh idle ACTIVE **UID 1000** MPS server,
its actual PID/start ticks, unchanged root controller and pinned daemon identity,
and separate UID compatibility evidence. Both physical-card inventory entries
must refer to that same server PID. The original active ceilings/defaults must
remain 5 GiB/thread 12 in this reference.

A separate review binds candidate/review hashes to that new server and proposes
only temporary active-server 40 GiB ceilings on both cards and thread 100 with
unchanged daemon defaults. The maintenance window is bounded to 180 seconds.
**The existing historical UID 10001 planner cannot release this fixture.** A new
UID 1000 maintenance candidate, genuine MPS startup/compatibility proof, consumed
candidate/review evidence bytes, fresh node/process/default readbacks, safe
cleanup/rollback, and admission/Pod Security exception qualification remain
pending. The hashes here are operator receipt declarations, not signature checks
or execution authorization. No maintenance writer or release controller is
implemented in these files.

The CPU gate checks the exact source set/hash, private cache and 0600 approval
marker. Release requires an independent readback of the approved active ceilings,
PID/start ticks, daemon UID/resourceVersion, unchanged defaults, all three actual
Pod UIDs, selected card, runtime identity, source/wheel hashes and a readback at
most 15 seconds old. It refuses the old server, a replacement server, stale marker,
changed review hashes or an expired window. The main process checks again before
creating CUDA children; later children check the same marker and unexpired window.
It never reapplies settings automatically.

## Bounded protocol and evidence

The simultaneous 20 second hold writes 4 GiB in the peer, 9 GiB + 64 MiB in the 10 GiB
workspace and 19 GiB + 64 MiB in the 20 GiB workspace: 32.125 GiB payload inside 35 GiB
nominal budgets. There are five actual CUDA child contexts during this hold
(one plus two plus two); the peer creates its second child afterwards.
Forty actual CUDA write ticks per held child retain full-payload allocations.
All holds use a common reviewed timestamp and must overlap for at least 18 seconds.

Ordinary 3+3, 6+6 and 12+12 GiB allocations then require actual CUDA OOM 2 for the
second process, continued writes by the first, and successful recovery after
freeing. The peer holds 256 MiB and performs CUDA heartbeat writes for 45 seconds across both
larger workspaces' denial/recovery windows. Every report operation must match
its individual child receipt, installed module, HAMi bytes/quota, PID, GPU and
private cache inode. This protocol does not qualify deliberate hook tampering,
process-crash cleanup, distributed workloads or actual MPS client membership.
A separate daemon/process/cgroup observation is required for MPS proof.

## Offline commands

Keep real inventories/logs and outputs in a private directory outside Git. The
following commands only read local evidence and render/evaluate files:

```bash
python mixed_render.py --preflight "$EVIDENCE/preflight.json" \
  --run-id mix0710a --compiler-wheel "$WHEEL" --output "$EVIDENCE/fixture.json"
python mixed_evaluate.py --preflight "$EVIDENCE/preflight.json" \
  --fixture "$EVIDENCE/fixture.json" --compiler-wheel "$WHEEL" \
  --node "$EVIDENCE/node.json" --pods "$EVIDENCE/pods-by-role.json" \
  --configmaps "$EVIDENCE/configmaps-before-after.json" \
  --peer5-log "$EVIDENCE/peer5.log" --workspace10-log "$EVIDENCE/workspace10.log" \
  --workspace20-log "$EVIDENCE/workspace20.log" --output "$EVIDENCE/evaluation.json"
python -m unittest discover -s . -p 'test_mixed_*.py' -v
```

The pods/logs objects use keys `peer5`, `workspace10`, `workspace20`; each log combines
its CPU gate receipt and main child/report events. ConfigMap receipts use
`before.items`/`after.items` with exact stable UID/resourceVersion and actual Pod
ownership. All executable main/init imageIDs must match the pinned manifest.
The evaluator reconstructs the trusted compiler fixture before comparing whole
Pod execution fields; matching forgeries in both original Job and Pod fail.
Only fixed API defaults and exact owned KAI additions are permitted.

A successful offline evaluation reports `bounded-mixed-candidate-cases-passed`.
`productionQualified`, `hostileIsolationQualified`, `mpsThreeClientQualified`,
`mixedPackingQualified`, `schedulerQuotaCandidatesLiveQualified` and
`temporaryMpsMutationImplemented` remain **false**. Synthetic regression evidence
and earlier 5 GiB runs must never be presented as this pending mixed live run.
