# Cluster storage and monitoring operations

Open Rancher → Monitoring → Grafana. **Cluster overview** is the home dashboard.
Its worker, storage, service and alert drill-downs share the current time range.
Grafana groups operational views in **00 Cluster Operations**, **10 Kubernetes
and Nodes**, **20 GPU and Scheduling**, **30 Storage and Backups**, **40 Services
and Teaching**, **50 Monitoring and Delivery**, and **90 Community References**.

Dashboards and Prometheus rules in the monitoring directory belong to
`nvidia-monitoring-addons`. Use the chart overlay with the installed version of
`rancher-monitoring` and its existing values. Installing that overlay rolls the
single Grafana Pod and can briefly interrupt its endpoint while Longhorn moves
the data volume. Check the release diff and endpoint before and after. Use
`operations/monitoring/organize-grafana.py` to preview the folder mapping and
`--apply` to set annotations on compatible ConfigMaps. Run it from a private
operations directory to retain the rollback inventory.

## Incidents and warning reviews

Open or update a record in the existing issue tracker. Record service impact,
detection time, acknowledgement, assigned owner, mitigation, recovery evidence,
and follow-up. Put links to the incident and the change record on any narrowly
matched, expiring maintenance silence. Resolve the incident after Prometheus
has cleared the condition and operators have verified recovery. Review recurring
alerts weekly.

Use `severity=critical` when the impact requires immediate administrator email
during staffed hours. Include a component, owner, concise summary, concrete
operator action and dashboard UID on new rules. The protected administrator
route sends both firing and resolved notifications. The companion Loki route keeps
incident events searchable. Apply router changes via
`operations/monitoring/route-admin-mail.py` using the existing SMTP settings.

Warning digests query Prometheus alert history at 09:00 Europe/Vienna Monday
through Friday. Monday covers the weekend. A warning that cleared within the
window remains in the digest. The digest counts distinct firing time series,
which can represent the same incident. Record holidays separately in the staffed
hours calendar. To validate delivery, create an explicitly named one-off Job from
`cps-warning-digest` and set its argument to `--test-delivery`. For a read-only
review use `--preview`. A missed scheduled run appears in Alerts and Fleet.
After checking the mail and Prometheus paths, preview the exact window with
`--preview --business-date YYYY-MM-DD`, then run a one-off digest Job with that
date. Confirm SMTP outcome before replaying an ambiguous delivery. Review alert counts and repeated rule names over seven
days after changing thresholds. Keep controlled tests identifiable by the
`test=true` label and match that label out when doing review calculations.

Use the `component`, `service` and `deployment_revision` Loki labels to narrow an
incident. Where a service emits a JSON `request_id` or `attempt_id`, filter the
structured metadata on the selected streams. For example:

```logql
{namespace="cps-compute",service="compute-gateway"} | request_id = "<request-id>"
```

A successful Hub route probe reaches the public identity challenge. Measure
authenticated sign-in separately using an approved account and its scoped secret.
Use real JupyterHub successful and failed spawn counts and p95 duration when
traffic exists. Report absent credentials, quiet traffic, unsampled gateway HTTP
status and missing backing-storage data explicitly.

## Capacity and restores

Guest root and scratch percentage, Longhorn scheduled capacity and physical
available bytes, and mounted PVC filesystem space are separate measurements.
For Longhorn 1.9.2, the allocation limit is
`(storageMaximum - storageReserved) * overProvisioningPercent / 100`.
Subtract `storageScheduled` for allocation headroom. The available bytes must
also exceed the disk's minimum free floor. Existing replica placement decides
which disks must pass the expansion gate.

For Gottam's active home, request 10–20 GiB of owner-selected inactive output
be copied to an approved project allocation. Verify the copy and permissions
before removing the originals. Retain the 100 GiB claim until both replica
disks have at least 25 GiB in allocation headroom and healthy physical floors.
Record the Pod UID and mounted size, expand the existing claim to 120 GiB,
then observe the same filesystem mount and Pod UID, two healthy replicas, and
recovery in the alert. Treat `server1` as a separate ownership decision.

Use Longhorn v1 with two healthy replicas for live durable data. Confirm the
physical Proxmox host, disk pool and power topology before treating placement
across VMs as independent. Migrate durable replicas off guest roots only as
measured capacity permits. Use `fast-scratch` for reproducible datasets and
caches, with durable checkpoints. Record ICT-confirmed Proxmox datastore,
thin-pool data and metadata, drive health, and NFS backing pool or export quota.
The Longhorn backup-target connection check does not report pool capacity.

Use the ICT-managed project NFS or object-storage quota for verified archives
and an independent backup copy. If ICT cannot supply the quota, size the
smallest CMR mirror to 12 months of measured growth and retention. Confirm bays,
controller, UPS, network and current quotes before ordering. A 2×4 TB mirror
budgets roughly 2.9 TiB at 80% fill, and a 2×8 TB mirror roughly 5.8 TiB, before
filesystem overhead. Monitor ZFS scrubs and SMART and test restores.

### Claim archival

Keep the exact PVC UID, PV, volume, replica disks, owner, activity evidence,
backup/restore ticket and proposed retention in the private review inventory.
Absence of a Pod is only a candidate signal. Confirm Hub, project and course
history for at least 90 days. Exclude dependencies, active courses, holds and
unknown activity. Notify the owner 30 days ahead, remind them in the final week,
and keep a restore route open for at least 180 days subject to university policy.

Use an owner-scoped, checksummed archive preserving permissions and prove a
restore in an isolated claim. Document the recovery route before release. Install
an exact namespace and name admission hold on `CREATE` for each archived
home before deleting its claim. The admission message should refer the user to
the private restore ticket. Test that the Hub service account cannot create an
empty replacement, and allow only the authorized restore path. Verify the
restored claim and permissions before lifting the hold. For infrastructure test
fixtures, confirm the owning test and expected retention, inspect workload
references and volume attachments, and restore-test before releasing. Measure
the allocation delta on each target disk and the separate change in physical
bytes.

Ollama remains a service dependency while revisions reference its PVC. Test
a smaller isolated copy with content checks and a cold start before considering
a switchover. Keep the recent A100 workspace available. For Released BuildKit
PVs, verify their exact host paths are absent and archive their records. These
records contribute zero reclaimed physical GiB.

### Test Jobs

Put a TTL on new standalone test Jobs so history age cannot drive paging.
Create them with explicit owners and record terminal diagnostics before expiry.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: example-qualification
  labels:
    cps.unileoben.ac.at/purpose: test
spec:
  ttlSecondsAfterFinished: 86400
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: test
          image: registry.k8s.io/pause:3.10
```

## Workload allocations

Use **Workload allocations** from the Cluster overview for side-by-side
CIT JupyterHub, CPS JupyterHub and compute workloads. Each section shows
running, bound and unbound Pods, NVIDIA device slots, declared fractional MiB,
CPU and RAM requests, and the appropriate PVC scope. Compute includes
CPS Argo Workflows and non-CronJob Kubernetes Jobs in `cps-workflows` and
`cps-compute`. That includes historical standalone Jobs that remain in Kubernetes.

Notebook home allocations include detached `claim-*` PVCs. Compute storage
counts distinct claims currently referenced by bound compute Pods. GPU
requests and limits come from admitted Pod declarations. Runtime-only
allocations must be verified through the scheduler and GPU telemetry.
