# GPU3 next-worker pre-acceptance refresh — read-only

Observed 2026-11-16 approximately21:57–22:00UTC, while GPU2 remains in controlled Source QA and is **not accepted**. No cluster writes, maintenance, node nomination, eviction, backup, attachment, source edit or HPA-stage change occurred. GPU3 remains next only after GPU2's actual cycle passes and root accepts it. This report is an inventory and proposed later procedure, not authorization or evidence that a rebuild happened.

## GPU3 jobs and drain blockers

No active selected-node Pod declares a GPU resource or fractional/mandatory-NRI GPU annotation. Host nvidia-smi (driver-mounted binary, not the absent host-PATH command) independently reports R615.71.09, both40GiB cards at1MiB and **no compute clients**:

- GPU-0a9f2da8-59f5-1cb0-9ead-d9fce56b69e5
- GPU-e7a56fad-ce29-f7d7-380a-3b5ae62a0b2a

GPU3 has62 active Pods:25 DaemonSet and37 other. All37 non-DaemonSet Pods are currently Ready; exact UID, controller, PVC and matching PDB inventory is in gpu3-workloads.json. This does not reserve future idleness; recheck for new work immediately before root's later window.

Critical CPU/stateful placement includes Authentik PostgreSQL+worker; CPS Hub PostgreSQL; Harbor database/Redis/Trivy; Prometheus/Grafana/Loki; both CPS/CIT admin consoles; artifact relay; Rancher/monitoring/cert-manager components; GPU Operator and Fractioning operator; Knative activator/autoscaler/kourier; and Longhorn controllers/instance manager. Several are singleton PVC-backed services with **no matching PDB**. Permitted eviction does not prove continuous database/login/registry/monitoring availability. Their normal controller replacement, volume attachment and actual readiness must be observed; no direct Pod deletion or active-user-work interruption is proposed. The vcluster CoreDNS Pod has Service ownership, and the ARC listener has custom AutoscalingListener ownership; retain their owner reconciliation behavior in the drain review rather than assuming a standard Deployment controller.

Actual PDBs matching GPU3 Pods:

| Workload | disruptionsAllowed | Note |
|---|---:|---|
| Knative activator |0| Sole ready replica;80% minimum. The existing HPA minimum5 source stage remains unapplied/unchanged. Apply only at root's approved point; require5 Ready, sufficient ready endpoints off GPU3 and allowance>=1. |
| Longhorn GPU3 instance manager |0| Existing minAvailable1; let Longhorn migrate/quiesce and reconcile protection. Do not delete its PDB. |
| Authentik PostgreSQL |1| Single replica with maxUnavailable1; this permits eviction but does not guarantee uninterrupted authentication. |
| Authentik worker |1| Honor actual budget during drain. |
| Longhorn CSI attacher/provisioner |2 each| Normal controller replacement with PDB honored. |

CIT PostgreSQL's budget allows1 but that Pod is not currently on GPU3. Knative webhook also has a zero-allowance budget but is not currently a selected-node drain blocker. The prepared HPA change and its restore-to1-after-GPU3-acceptance procedure are untouched.

## Detached exceptions remain unresolved

Both volumes are detached/robustness unknown,10GiB logical, desired replicas3; no live data consumer or frontend is currently attached. Each has two active, nonfailed, stopped replicas with healthy metadata, **only one outside GPU3**. Stopped metadata is not a current RW engine witness or an integrity/restore test.

| PVC / Longhorn volume | Replica locations | Existing backup metadata |
|---|---|---|
| cps-compute/cps-admin-backup / pvc-a54296d7-4a5b-4050-a0a6-fbf1aae6594d | GPU3 r-38d22df5; GPU4 r-8cce6169; both lastHealthyAt21:11:39UTC | lastBackupAt2026-11-16 09:26:26UTC; actualSize1,027,387,392bytes |
| cit-jhub/claim-mikasa / pvc-e3ebd8c5-6b5a-4ddc-86b8-0bc30509a7ac | GPU3 r-0d35e95c; GPU1 r-cd50bb32; both lastHealthyAt21:13:46UTC | lastBackupAt2026-10-16 21:03:48UTC; actualSize239,747,072bytes |

No GPU2 copy exists for either. Last successful backup timestamps have not advanced by this read. In particular, claim-mikasa's old recovery point is still a separate freshness concern; replica replenishment does not make its backup newer. Full replica details/VolumeUIDs are in detached-exceptions.json. No backup target scan, new backup or filesystem read was performed.

## GPU2 capacity: still disabled

Actual installed Longhorn manager is **v1.9.2**. GPU2 Longhorn node allowScheduling=false, evictionRequested=false. Both disk-level allowScheduling flags and Ready/Schedulable conditions are true, but the node-level false prevents new scheduling. Restore only after root accepts GPU2.

| Disk | Maximum GiB | Available GiB | Reserved GiB | Scheduled logical GiB |
|---|---:|---:|---:|---:|
| /var/lib/longhorn |483.295|85.938|144.988|0|
| /mnt/nvme/scratch |983.231|947.656|100|500|

These are Longhorn's observed byte counters, not a new guarantee of schedulable capacity or permission to count reserved space as free. Existing storage over-provisioning200%, minimal available10%, replica soft anti-affinity=false and replenishment wait600s remain unchanged. Offline replica rebuilding is globally false; both volumes inherit it. Each missing replica reserves10GiB logical (20GiB total), though actual transfer can be much smaller. Keep all existing reserved/free/provisioning gates; let the scheduler confirm capacity and actual placement. Do not extrapolate full94-replica evacuation from this small repair.

## Supported later procedure: maintenance attach, no user frontend

There is no `readOnly` field in the installed v1.9.2 AttachInput. The supported equivalent for **preventing user access** is Longhorn UI **Maintenance mode**, which attaches with `disableFrontend=true`: neither block device nor iSCSI frontend is exposed. It is not a promise of a physically read-only engine: the engine/rebuild writes replica metadata and new copies. Do not create a consumer Pod, mount a filesystem (even read-only), run fsck/revert/salvage, change replica count/selectors or delete stopped copies for this repair. The [v1.9.2 concepts](https://longhorn.io/docs/archives/1.9.2/concepts/#22-reverting-volumes-in-maintenance-mode) explain maintenance mode and automatic rebuilding below desired count. The [v1.9.2 AttachInput](https://github.com/longhorn/longhorn-manager/blob/v1.9.2/client/generated_attach_input.go#L6) and [manager Attach/Detach](https://github.com/longhorn/longhorn-manager/blob/v1.9.2/manager/volume.go#L207) implement a named attachment ticket with disableFrontend and removal of only that ticket.

Proposed root procedure, one volume at a time **after GPU2 acceptance**:

1. Restore GPU2 Longhorn node scheduling through the existing owner. Confirm Ready engine image/instance manager, unchanged capacity gates and the actual two exception VolumeUIDs. Re-read that each volume remains detached, nodeID/currentNodeID empty, no running consumer/CSI attachment ticket and no recurring job in flight. Root must coordinate a short exclusive volume window; do not race a new user start or backup job.
2. Use the supported UI Maintenance attach to GPU2 or the equivalent API action with a unique per-volume attachmentID. Example **review only**, not executed:

```text
POST /v1/volumes/<volume>?action=attach
{"hostId":"k3s-wk-gpu2","disableFrontend":true,
 "attachedBy":"cps-gpu3-prerequisite","attacherType":"longhorn-api",
 "attachmentID":"cps-gpu3-prerequisite-<volume>"}
```

3. Verify the exact ticket belongs to this operation, volume attaches to GPU2 with frontend disabled, and existing copies become current RW/nonfailed. Keep desired replicas3 and allow normal replenishment (existing600s wait may apply). Observe the new replica schedule/build to completion. With hard node anti-affinity and existing GPU3+GPU4 or GPU3+GPU1 placements, a successful distinct-node third replica is outside GPU3. The engine attachment target does **not** itself pin the replica destination: the new copy may be GPU2 or another eligible distinct node. Require actual evidence, not presumed GPU2 placement.
4. Before declaring the exception repaired, require3 current engine RW replicas, no WO/ERR or rebuild in progress, healthy volume, and specifically **two non-GPU3 copies on distinct healthy nodes** with current healthy timestamps. Retain volume/engine/replica UIDs, mode map, placement and scheduler/capacity evidence. If scheduling fails, a source copy fails, a conflicting CSI ticket appears or progress stalls, stop for root review; do not loosen gates or salvage/delete the remaining originals.
5. Detach only this test's named ticket through the normal API/UI; never forceDetach or clear other attachment tickets. API equivalent: POST same volume `?action=detach` with the same attachmentID and `forceDetach:false`. Wait for detached state/currentNodeID empty and all copies stopped normally, preserving three healthy metadata copies and two outside GPU3. Recheck no exposed frontend, no consumer and no lingering operation ticket. Do not claim backup freshness or a restore test from this result.
6. Only after both exceptions meet this gate, the HPA/PDB prerequisite is live and verified, CPU consumers can be safely rescheduled, and root opens GPU3's serial window, begin the normal PDB-respecting drain. Longhorn IM protection must resolve under the existing drain policy; no bypass.

API type/path proof comes from the installed release's [VolumeAttach handler](https://github.com/longhorn/longhorn-manager/blob/v1.9.2/api/volume.go#L208), [DetachInput](https://github.com/longhorn/longhorn-manager/blob/v1.9.2/client/generated_detach_input.go#L6) and manager implementation. This plan uses those supported interfaces rather than direct Replica CR edits. It has not been executed.

## Evidence boundary

Four files accompany this report: selected-node workload/PDB inventory, two-volume replica/backup metadata, GPU2 Longhorn disk counters and SSH physical GPU readout. Reads used kubectl get for selected-node Pods/PDBs and Longhorn Volume/Replica/Node/settings, plus host nvidia-smi on10.21.0.40. Initial nvidia-smi PATH absence was resolved to /run/nvidia/driver/usr/bin/nvidia-smi. No Secrets, full Fleet status, environment dumps or credentials were retained. HPA source stage and all live settings remain unchanged.
