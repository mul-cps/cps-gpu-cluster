# Longhorn Storage Recovery Design

## Goal

Restore safe Longhorn capacity, establish a functioning off-cluster backup
target, and allow JupyterHub power users to start without the failed shared
workspace while preserving the failed volume for recovery.

## Current Incident

`jupyterhub/jupyterhub-shared-storage` is the 500 GiB RWX Longhorn volume
`pvc-b774d9f7-54fc-4fa1-954c-90f7692402de`. It is `faulted` and detached.
Longhorn recorded an unsuccessful replacement-replica precheck on 2026-08-16;
its remaining replica failed on 2026-08-20. Automatic salvage finds no usable
replicas. The volume must not be deleted, recreated, force-detached, or used
as a source of new writes.

The existing Longhorn backup target is unavailable because its configured NFS
directory no longer exists. No Longhorn Snapshot or Backup CR for the failed
shared volume is present in the cluster.

## Scope and Safety Constraints

- Do not mutate or delete the faulted shared-workspace PV, PVC, Longhorn
  Volume, replica, or its stale VolumeAttachment.
- Preserve the current two-replica Longhorn policy and the global 100 percent
  provisioning ceiling. Raising that ceiling is not a recovery mechanism.
- Treat the scratch NFS export as the preferred backup destination, as
  explicitly selected by the operator. If it cannot be created and validated,
  stop before changing the backup target and use the persistent share only
  after a separate live validation.
- All declarative changes belong under the Longhorn/JupyterHub Fleet bundles;
  no hand-applied replacement manifests.

## Design

### 1. Restore Longhorn scheduling capacity

Re-enable the live Longhorn node `k3s-wk-gpu2` by setting
`spec.allowScheduling=true` and `spec.evictionRequested=false`. Its two disks
are healthy and have substantial free space, but the node is currently
disabled and cannot accept a replacement replica. Verify the node becomes
schedulable and re-check all volume robustness afterward.

This is a live Longhorn control-plane operation rather than a new
StorageClass policy. Record the intervention and its verification in the
operations troubleshooting runbook. Do not change the global over-provisioning
or minimum-free-space settings.

### 2. Replace the unavailable backup target with a GitOps-owned NFS target

Use the existing scratch export at
`193.170.30.58:/mnt/scratch1/cps_scratch1_tmp` with a dedicated child
directory, `longhorn-backups`. Create the child directory through a one-shot,
idempotent NFS-mounted Kubernetes Job and verify it is writable before updating
Longhorn's target.

Declare the Longhorn `BackupTarget` named `default` in the Longhorn Fleet
bundle with:

```
nfs://193.170.30.58:/mnt/scratch1/cps_scratch1_tmp/longhorn-backups?nfsOptions=nfsvers=4.2,proto=tcp,hard,timeo=150,retrans=3,rsize=1048576,wsize=1048576,noresvport
```

Retain the existing five-minute polling interval and no credential secret.
Verify `.status.available=true`, then take and confirm an on-demand backup of
a healthy Longhorn volume before considering the target operational. The
existing `backup-all` recurring job then resumes protecting its labeled
volumes.

### 3. Decouple Jupyter availability from the failed shared workspace

Add a power-user spawn option for the Longhorn shared workspace. It defaults
to disabled while recovery is in progress. When disabled, the spawner does not
add the `jupyterhub-shared-storage` PVC or `/home/jovyan/shared` mount. The
existing personal Longhorn home and the independently selectable external NFS
mounts are unchanged.

This makes a power-user CPU or GPU session launchable without the faulted
volume. Selecting the option remains an explicit request for the shared
workspace and will fail until it is recovered, which is safer than silently
switching users to empty storage.

### 4. Recovery boundary

Only an independently verified external backup or original data source may be
used to restore the failed workspace. If none exists, recreating an empty
workspace is a separate destructive approval. This work creates the backup
protection and service bypass but does not claim data recovery.

## Verification

1. `k3s-wk-gpu2` is `allowScheduling=true`, not evicting, and its disks remain
   schedulable.
2. The bootstrap Job creates and writes the dedicated scratch NFS directory.
3. Longhorn reports the GitOps-owned target as available and an on-demand
   backup completes successfully.
4. A focused configuration test proves a power-user spawn without the shared
   option does not contain the shared PVC/mount; the opted-in case retains it.
5. Fleet reports both modified bundles ready, and a real Jupyter power-user
   spawn without the shared workspace reaches Running.

## Rollback

- Revert the JupyterHub option through Git; this restores the former mandatory
  mount behavior but should only be done after the workspace is healthy.
- Revert the BackupTarget only to another validated NFS path; never revert to
  the known-missing persistent-share directory.
- If GPU2 scheduling causes an unexpected issue, set only that Longhorn node
  back to its previous disabled/evicting state after replicas are safe.
