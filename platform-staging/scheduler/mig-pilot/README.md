# Disabled single-card MIG pilot preparation

Status: **offline review only; activation permission pending; all qualification gates open**.
The reviewed scope is one explicitly identified A100 40GB card on `k3s-wk-gpu2`.
`k3s-wk-gpu1` and `jupyter-bjoern` UID
`a663ab6b-e927-418f-9671-fc0b36a27b3a` are excluded. No production catalog,
Fleet path, node label, running workload, GPU mode, or MPS setting is changed by
this package. The renderer reads local JSON and writes stdout; it has no cluster
client, command execution, network access, or apply option.

The operator's October 6 combined-stack report
`combined-mps-reproducible.json` records `runtimeOverridesDenied: false`:
bypassing the MPS pipe allowed a 6144 MiB allocation against a nominal 5 GiB
assignment. Two CUDA processes also used 6144 MiB in aggregate, above 5120 MiB.
Those findings motivate this preparation; they do not qualify MIG or authorize
reconfiguration. See [the current isolation boundary](../qualification/runtime-isolation.md).

## Profile and packing contract

Use one GPU instance and one full-size compute instance per resource allocation.
The selected static geometry is one `3g.20gb`, one `2g.10gb`, and two `1g.5gb`
instances. These profiles dedicate separate memory/compute slices; splitting a
single GPU instance into multiple compute instances would share its memory and
is outside this pilot. [NVIDIA MIG concepts](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/concepts.html)

| Resource requested by one workspace | Count on this card | Physical SM fraction per instance | Physical memory fraction per instance |
| --- | ---: | ---: | ---: |
| `nvidia.com/mig-1g.5gb: 1` | 2 | 1/7 | 1/8 |
| `nvidia.com/mig-2g.10gb: 1` | 1 | 2/7 | 2/8 |
| `nvidia.com/mig-3g.20gb: 1` | 1 | 3/7 | 4/8 |

The geometry occupies seven SM slices and eight memory slices, totaling one
physical card in each dimension. A `3g.20gb` instance therefore has a different
compute fraction from the existing 0.5 GPU profile. The A100 40GB profiles also
permit homogeneous geometries of seven `1g.5gb`, three `2g.10gb`, or two
`3g.20gb` instances; changing the selected geometry requires another review.
[NVIDIA A100 profile table](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/supported-mig-profiles.html#a100-mig-profiles)

Names encode nominal GB, not guaranteed 5/10/20 GiB usable limits. NVIDIA's
example reports roughly 4.75/9.62/19.50 GiB for the chosen profiles; actual
CUDA-visible bytes must be recorded on the selected driver/card. The documented
3-2-1-1 creation order starts with `3g.20gb`; placement/fragmentation can prevent
otherwise plausible combinations. Preserve the driver-reported profile and
placement inventory rather than assuming memory arithmetic proves fit. On
A100, a mode transition can reset the card, and MIG mode persists across reboot.
[NVIDIA profile inventory, geometry and Ampere reset guidance](https://docs.nvidia.com/datacenter/tesla/mig-user-guide/latest/getting-started-with-mig.html)

The device-plugin candidate uses `mixed`, which exposes the distinct
`nvidia.com/mig-*` resource names. It contains no MPS or time-slicing replicas.
One group workspace would request exactly one such resource and all of its
kernel child processes would share that hardware instance. Device enumeration,
privilege, host-device access, and escape resistance still require validation.
[NVIDIA device-plugin configuration](https://github.com/NVIDIA/k8s-device-plugin/blob/v0.17.3/README.md#configuration-option-details)

## KAI and allowance accounting boundary

KAI `v0.18.1` recognizes MIG resource names as scalar resources. Its
`GetTotalGPURequest` path sums the integer `g` values parsed from those names;
the selected geometry sums to seven there, while a full-GPU request is one.
This source observation does not establish every queue/fairness accounting path.
Audit the deployed queue usage, quota enforcement, reservation ledger, reclaim,
and gang behavior before adopting a physical-card conversion.
[Pinned KAI resource accounting](https://github.com/kai-scheduler/KAI-Scheduler/blob/v0.18.1/pkg/scheduler/api/resource_info/resource_info.go#L202-L217),
[pinned KAI MIG parser](https://github.com/kai-scheduler/KAI-Scheduler/blob/v0.18.1/pkg/scheduler/api/common_info/resources/mig.go#L11-L29)

The review report deliberately preserves SM and memory fractions separately.
It neither maps MIG counts into the production `gpu-fraction` catalog nor
implements an entitlement charge. A reviewed conversion must count physical
parent UUIDs once, account for the second unchanged GPU2 card, reserve both
dimensions across all members atomically, and avoid treating four MIG devices
as four full GPUs. The affected node is excluded from whole-GPU batch jobs
until mixed-node placement is qualified. Exclusive batch, burst, fairness,
reclaim, protected-session preservation, and gangs remain unqualified.

## Offline rendering

1. Copy `pilot.json` and `preflight.example.json` into the private operator
   evidence directory. Keep every `activation` field false.
2. Fill the exact fresh node UID, selected physical GPU UUID, and observed GPU
   index in both documents. `cards` must describe every card on GPU2 with unique
   UUID/index associations. Record a UTC snapshot at most 15 minutes old.
3. Replace the `REVIEW-ALL-WHOLE-GPU-TEMPLATES` marker with every observed
   whole-GPU workload template name and its actual selector. Every selector
   must require `compute.cps.unileoben.ac.at/gpu-mode=full-gpu`; the separate
   planned pilot label is `mig-pilot`. These labels are only planned here.
   Confirm the inventory is complete before setting its completeness flags.
4. Record that the entire GPU2 node has no active GPU workload/reservation or
   GPU process and that the exact GPU1 protected session remains untouched.
   Keep raw inventory evidence alongside the JSON. Completeness/idle flags
   are operator declarations, not verified by this offline tool.
5. Render and inspect the artifact locally:

   ```sh
   python3 platform-staging/scheduler/mig-pilot/render.py \
     --config /private/operator-evidence/mig-pilot.json \
     --preflight /private/operator-evidence/mig-preflight.json \
     > /private/operator-evidence/mig-review.json
   python3 -m unittest discover -s platform-staging/scheduler/mig-pilot -p 'test_*.py'
   ```

Unfilled examples intentionally fail with no manifest output. Stale inventory,
missing/mismatched UUIDs, GPU1 targeting, multiple-card/all-card selectors,
activation flags, incompatible exclusive selectors, active GPU use, or an
already enabled target are refused. The output is only an inert review
ConfigMap in `cps-compute-qualification`, with candidate and rollback geometry,
device-plugin settings, inventory hash, and false qualification fields.
Candidate data deliberately uses `mig-parted-candidate.yaml` rather than GPU
Operator's required `config.yaml`. There is no Node, Job, DaemonSet, Fleet bundle,
ClusterPolicy, workload, or controller reference. JSON candidate values are
valid YAML. Rendering must never be confused with applying the configuration.

## Manual activation checklist — blocked pending explicit permission

This is a review checklist, not an activation procedure or executable runbook.
No switch in this package enables activation. Each mutation below needs a
separately reviewed operational change; do not bypass earlier review boundaries.

- [ ] Obtain explicit permission for the exact GPU2 node/card UUID, maintenance
  window, reset/client disruption, scoped plugin changes, acceptance probes,
  and rollback. Keep GPU1 and its protected workload excluded throughout.
- [ ] Immediately refresh the node UID, physical UUID/index mapping, all-card
  inventory, GPU workloads/reservations/processes, current modes, driver/toolkit
  versions, plugin/GFD/MIG Manager configuration, and protected session UID.
  A reviewed stale render does not authorize use of its integer index.
- [ ] Save exact GPU2 baseline modes, topology, node labels/taints, plugin
  configuration references, and any MPS/HAMi client state. Verify that no
  existing full-GPU job, reservation, or service will be disrupted implicitly.
- [ ] Review node-scoped isolation of scheduling and device discovery. Do not
  patch the global ClusterPolicy strategy or enable MIG Manager fleet-wide.
  NVIDIA MIG Manager stops node GPU clients when reconfiguring, including
  operator services; single-card geometry does not eliminate that node-wide
  operational effect. Any second-card client disruption needs explicit review.
  [NVIDIA MIG Manager behavior](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-operator-mig.html#managing-host-gpu-clients)
- [ ] Prove whole-GPU batch templates require the full-GPU pool and cannot
  enter the pilot node. Review existing queues and reservation exclusion before
  admitting any pilot workspace; do not rewrite already running work.
- [ ] Review the exact one-card mode/geometry change and node-only mixed plugin
  configuration, with no all-card selector, automatic mode-change job, global
  reset, or reboot fallback. Leave every other physical card unchanged.
- [ ] After the separately approved change, retain parent and MIG UUIDs,
  GI/CI placement and SM counts, allocatable resources, actual usable bytes,
  and evidence that each workspace sees only its assigned instance. Validate
  one full-size CI per GI and no MPS/time-slicing sharing on MIG resources.
- [ ] Run separately approved single-process and aggregate child-process OOM
  probes for all three profiles, override/pipe/host-device escape attempts,
  peer progress, churn, protected-session preservation, placement, fairness,
  quota/reclaim, gangs, and full-GPU batch exclusion. Record failures honestly;
  no hardware-isolation claim follows from successful manifest rendering.
- [ ] Qualify atomic all-member group reservation/release and a reviewed
  physical-fraction accounting conversion. Catalog activation/Fleet promotion
  is a later independent gate, after measured limits and rollback pass.

## Manual rollback checklist

- [ ] Stop admitting new pilot work; preserve files/checkpoints and wait for
  confirmed pilot workspace/job shutdown. Do not evict the GPU1 session.
- [ ] Refresh the exact physical UUID/index mapping again. Remove only the
  selected card's pilot CIs/GIs and restore its recorded disabled MIG baseline
  through the separately approved procedure. The rendered rollback candidate
  targets one index only; it is not executed here. Do not use `all-disabled`,
  all-node selectors, global driver restarts, or reboot as a silent fallback.
- [ ] Restore only the recorded GPU2 labels/taints and node-specific discovery
  references/client state. Restore baseline compute modes only if separately
  approved; the previous HAMi/MPS stack remains unqualified for hard quotas.
- [ ] Verify physical UUIDs, modes, allocatable resources, second-card state,
  service readiness, whole-GPU batch placement, ledger release, and unchanged
  GPU1 protected UID. Retain before/after evidence and any failed gate.
- [ ] Keep all GPU catalog profiles disabled until their independent acceptance
  gates pass. If rollback is incomplete, keep pilot admissions closed and ask
  for the exact additional recovery action; do not broaden device scope.
