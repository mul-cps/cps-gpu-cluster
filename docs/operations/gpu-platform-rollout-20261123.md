# CPS/CIT GPU platform rollout on 2026-11-23

## Course profiles and controller backup

The live CIT Hub uses the immutable `cit-student-shared5-rino-20261123` Secret
and retains the scoped `cps-rino-mujoco-exception` reference. The CIT candidate
is on `work/approved-gpu-platform-rollout` in the CIT teaching platform repo,
based on the active Fleet revision `b68a5cfa`. Rendering JupyterHub 4.4.2
with the reviewed patch matches the live Hub pod template after normalizing
the restart timestamp and Kubernetes volume defaults. The home claim
`claim-m12113877` is Bound.

The [Gateway and backup render](../../platform-staging/compute-checkpoint-authority/current-rollout/)
matches the live Deployment, CronJob and backup ConfigMap. It references the
immutable runtime Secret containing the reviewed identity link. Secret
contents stay in the protected configuration. The render passed server-side
dry run. Both GitOps candidates still need reconciler adoption.

The live scheduled backup now uses `compute-state-timed-gpu3-20261119` with
a digest-pinned runner and the gateway image and upstream policy hash recorded
in the CronJob. Snapshot `20261123T083647.220371Z` was restored onto
`compute-state-restore-pin-1123083635`, whose PV has reclaim policy Retain.
All four database content hashes, schema digests, integrity and foreign-key
checks passed. The isolated allowance check verified both CPS/CIT acquisition
orders and reacquisition after release. All 116 custody records were clean,
with one retained delete record. The allowance check used a synthetic
canonical identity on a copy of the restored data.

A second backup ran successfully with the new schema guard. A local fixture
verified that the guard rejects schema drift and leaves no partial snapshot.
The scheduled job now mounts that exact immutable guard. Both gateway
Deployments were available after the change.

The earlier 43.72-second handoff remains the last measured production
handoff. A new live recovery and rollback timing rehearsal is open.
Alertmanager's effective configuration has only the `null` receiver.
External firing and resolved acknowledgement awaits the approved destination.
Ordinary account, current-course, MuJoCo/Xpra and ambiguous CREATE/STOP
qualification remains open.

## KAI and workload admission

The [KAI staging package](../../platform-staging/gpu/upstream-sharing/kai-019/)
contains the chart and enabled-image digest locks. The candidate render uses
KAI 0.19.0, whose Chart.lock resolves Fractioning 0.1.9. Six KAI CRDs changed
and each still declares all of its live stored versions. Both default queues
match live. The rollback chart, live admission webhooks, queues, installed
image IDs, and separately installed Fractioning configuration were captured
before any promotion. The staging hardware matrix and rollout are open.
All four workers report Ready and advertise eight allocatable GPU devices.

The 16-start burst still requires eight verified canonical people per Hub.
GPU batch remains disabled. Interactive-first shared allowance, durable waiting
and checkpoint/resume, and normal-user and CI pilot qualification remain open.
The tenant guide documents the gateway submission path and current NvFractions
runtime. Production SM sharing, GPU4 eviction recovery, elastic VRAM and
superseded component retirement remain open.

Evidence is stored in the rollout artifact directories
`backup-cron-pin-zbeVH2Bo`, `cit-gitops-readback-TffSraGk`, and
`kai-019-render-20261123` under
`/home/bjoern/artifacts/cps-upstream-sharing-20261116/`.
