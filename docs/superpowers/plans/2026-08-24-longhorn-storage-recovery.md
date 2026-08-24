# Longhorn Storage Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore Longhorn backup protection and GPU2 scheduling while allowing JupyterHub power users to start without the faulted shared workspace.

**Architecture:** A raw resource Job creates and proves a dedicated directory on the selected scratch NFS export, and a GitOps-owned Longhorn BackupTarget consumes that directory. A focused JupyterHub option controls whether the shared Longhorn PVC is added to a power-user pod. GPU2 scheduling is restored through the live Longhorn Node CR, then documented as an operational intervention.

**Tech Stack:** Kubernetes CRDs and Jobs, Rancher Fleet, Longhorn 1.9.2, JupyterHub/KubeSpawner Python configuration embedded in Helm values, POSIX shell validation.

**Spec:** `docs/superpowers/specs/2026-08-24-longhorn-storage-recovery-design.md`

## Global Constraints

- Never delete, recreate, force-detach, or write to `pvc-b774d9f7-54fc-4fa1-954c-90f7692402de`.
- Keep Longhorn `defaultReplicaCount=2`, `storageOverProvisioningPercentage=100`, and `storageMinimalAvailablePercentage=10` unchanged.
- The preferred backup target is `193.170.30.58:/mnt/scratch1/cps_scratch1_tmp/longhorn-backups`; only fall back to persistent storage after independently validating it.
- Deploy Git-managed files only through Fleet. Live Longhorn Node CR changes are an explicitly verified operational step.

---

### Task 1: Define and validate the scratch-NFS backup target resources

**Files:**
- Create: `cluster-maintenance/clusters/cit-cps-gpu/system/storage/longhorn/backup-target-bootstrap.yaml`
- Create: `cluster-maintenance/clusters/cit-cps-gpu/system/storage/longhorn/backup-target.yaml`
- Create: `tests/longhorn/validate-backup-target-manifests.sh`

**Interfaces:**
- Consumes: NFS server `193.170.30.58` and export `/mnt/scratch1/cps_scratch1_tmp`.
- Produces: Job `longhorn-backup-target-bootstrap` and `backuptarget.longhorn.io/default` in `longhorn-system`.

- [ ] **Step 1: Write the failing manifest-contract test**

Create `tests/longhorn/validate-backup-target-manifests.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
bootstrap="$root/cluster-maintenance/clusters/cit-cps-gpu/system/storage/longhorn/backup-target-bootstrap.yaml"
target="$root/cluster-maintenance/clusters/cit-cps-gpu/system/storage/longhorn/backup-target.yaml"

test -f "$bootstrap"
test -f "$target"
rg -F 'mountPath: /backup' "$bootstrap"
rg -F 'server: 193.170.30.58' "$bootstrap"
rg -F 'path: /mnt/scratch1/cps_scratch1_tmp' "$bootstrap"
rg -F 'mkdir -p /backup/longhorn-backups' "$bootstrap"
rg -F 'name: default' "$target"
rg -F 'nfs://193.170.30.58:/mnt/scratch1/cps_scratch1_tmp/longhorn-backups?' "$target"
rg -F 'nfsvers=4.2,proto=tcp,hard,timeo=150,retrans=3,rsize=1048576,wsize=1048576,noresvport' "$target"
```

- [ ] **Step 2: Run the test and verify it fails because the manifests do not exist**

Run: `bash tests/longhorn/validate-backup-target-manifests.sh`

Expected: non-zero exit from `test -f` for `backup-target-bootstrap.yaml`.

- [ ] **Step 3: Add the minimal bootstrap Job and BackupTarget CR**

Create `backup-target-bootstrap.yaml` with an idempotent Job that mounts the scratch NFS export directly:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: longhorn-backup-target-bootstrap
  namespace: longhorn-system
spec:
  backoffLimit: 2
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: create-and-verify-target
          image: busybox:1.37
          command: ["/bin/sh", "-ec"]
          args:
            - |
              mkdir -p /backup/longhorn-backups
              test -d /backup/longhorn-backups
              touch /backup/longhorn-backups/.longhorn-backup-target-check
              rm /backup/longhorn-backups/.longhorn-backup-target-check
          volumeMounts:
            - name: backup-root
              mountPath: /backup
      volumes:
        - name: backup-root
          nfs:
            server: 193.170.30.58
            path: /mnt/scratch1/cps_scratch1_tmp
```

Create `backup-target.yaml` with `kind: BackupTarget`, metadata name `default`, a five-minute poll interval, and the exact scratch-NFS URL required by the test.

- [ ] **Step 4: Run focused validation and server dry-run**

Run:

```bash
bash tests/longhorn/validate-backup-target-manifests.sh
kubectl apply --dry-run=server -f cluster-maintenance/clusters/cit-cps-gpu/system/storage/longhorn/backup-target-bootstrap.yaml
kubectl apply --dry-run=server -f cluster-maintenance/clusters/cit-cps-gpu/system/storage/longhorn/backup-target.yaml
```

Expected: validation passes and both server dry-runs are accepted without mutation.

- [ ] **Step 5: Commit the target resources and test**

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/system/storage/longhorn/backup-target-bootstrap.yaml \
  cluster-maintenance/clusters/cit-cps-gpu/system/storage/longhorn/backup-target.yaml \
  tests/longhorn/validate-backup-target-manifests.sh
git commit -m "fix(storage): configure scratch NFS backup target"
```

### Task 2: Make the Longhorn shared workspace an explicit power-user option

**Files:**
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml:1113-1121,1225-1234,1611-1631,1665-1671`
- Create: `tests/jupyterhub/validate-shared-workspace-option.sh`

**Interfaces:**
- Consumes: form field `mount_shared_longhorn`.
- Produces: a power-user-only checkbox and a pod mount only when `mount_shared_longhorn` is true.

- [ ] **Step 1: Write the failing configuration-contract test**

Create `tests/jupyterhub/validate-shared-workspace-option.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
values="$root/cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml"

rg -F 'name="mount_shared_longhorn"' "$values"
rg -F "opts['mount_shared_longhorn'] = form_bool(formdata, 'mount_shared_longhorn', False)" "$values"
rg -F "mount_shared_longhorn = bool(spawner.user_options.get('mount_shared_longhorn', False))" "$values"
rg -F 'if is_power_user(spawner.user) and mount_shared_longhorn:' "$values"
```

- [ ] **Step 2: Run the test and verify it fails because the option does not exist**

Run: `bash tests/jupyterhub/validate-shared-workspace-option.sh`

Expected: non-zero exit because `mount_shared_longhorn` is absent.

- [ ] **Step 3: Add the checkbox, parse it, and gate the mount**

In `get_options_form`, add a power-user-only checkbox named `mount_shared_longhorn`, unchecked by default, explaining that it mounts the currently recovering `/home/jovyan/shared` workspace.

In `options_from_form`, parse it with `form_bool(..., False)`. In `apply_profile_settings`, read it from `spawner.user_options`, include it in the structured spawn log, and replace the mandatory shared-volume branch with:

```python
if is_power_user(spawner.user):
    spawner.storage_capacity = '100Gi'
    if mount_shared_longhorn:
        shared_vol = {'name': 'shared', 'persistentVolumeClaim': {'claimName': 'jupyterhub-shared-storage'}}
        shared_mount = {'name': 'shared', 'mountPath': '/home/jovyan/shared'}
        append_volume_mount(spawner, shared_vol, shared_mount)
        requested_storage_mounts.append('shared-longhorn')
```

Keep the larger power-user home capacity outside this condition so disabling the optional workspace does not shrink a user’s personal home PVC.

- [ ] **Step 4: Run focused validation and render the Helm chart**

Run:

```bash
bash tests/jupyterhub/validate-shared-workspace-option.sh
helm template jupyterhub https://jupyterhub.github.io/helm-chart --version 4.3.1 \
  --namespace jupyterhub --values cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml >/tmp/jupyterhub-rendered.yaml
kubectl apply --dry-run=client -f /tmp/jupyterhub-rendered.yaml
```

Expected: the contract passes and the chart renders valid Kubernetes YAML.

- [ ] **Step 5: Commit the spawn bypass and contract test**

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml \
  tests/jupyterhub/validate-shared-workspace-option.sh
git commit -m "fix(jupyterhub): make shared workspace optional"
```

### Task 3: Restore GPU2 Longhorn scheduling and document the live intervention

**Files:**
- Modify: `docs/operations/troubleshooting.md:1948-1972`

**Interfaces:**
- Consumes: `nodes.longhorn.io/k3s-wk-gpu2`.
- Produces: a schedulable GPU2 Longhorn node with eviction disabled.

- [ ] **Step 1: Write the failing operational precondition check**

Run:

```bash
kubectl -n longhorn-system get nodes.longhorn.io k3s-wk-gpu2 \
  -o jsonpath='{.spec.allowScheduling}{" "}{.spec.evictionRequested}{"\n"}'
```

Expected before repair: `false true`.

- [ ] **Step 2: Apply the single live Longhorn Node patch**

Run:

```bash
kubectl -n longhorn-system patch nodes.longhorn.io k3s-wk-gpu2 --type=merge \
  -p '{"spec":{"allowScheduling":true,"evictionRequested":false}}'
```

Do not patch disks, storage classes, capacity thresholds, replica counts, or the faulted volume.

- [ ] **Step 3: Verify the repair and capacity state**

Run:

```bash
kubectl -n longhorn-system get nodes.longhorn.io k3s-wk-gpu2 \
  -o jsonpath='{.spec.allowScheduling}{" "}{.spec.evictionRequested}{"\n"}'
kubectl -n longhorn-system get nodes.longhorn.io k3s-wk-gpu2 -o json | jq '.status.diskStatus'
kubectl -n longhorn-system get volumes.longhorn.io -o wide
```

Expected: `true false`, both GPU2 disks ready/schedulable, no attempt to resurrect the faulted shared workspace.

- [ ] **Step 4: Update the capacity runbook**

Replace the stale recommendation that GPU2 might need re-enabling with the observed cause, exact patch, verification command, and a warning that it must not be disabled again without a completed drain plan.

- [ ] **Step 5: Commit the runbook update**

```bash
git add docs/operations/troubleshooting.md
git commit -m "docs(storage): record GPU2 scheduling recovery"
```

### Task 4: Verify Fleet reconciliation, target health, backup, and Jupyter availability

**Files:**
- Modify: `docs/operations/troubleshooting.md`

**Interfaces:**
- Consumes: committed Longhorn/JupyterHub Fleet resources, the `backup-all` recurring-job group, and the new `mount_shared_longhorn` option.
- Produces: live evidence for backup protection and a power-user session that does not depend on the faulted workspace.

- [ ] **Step 1: Push the reviewed branch and observe Fleet**

Run:

```bash
git push -u origin fix/longhorn-storage-recovery
kubectl get gitrepo,bundle -n fleet-local | rg 'longhorn|jupyterhub'
```

Expected: the GitRepo reaches the committed revision and both relevant bundles are ready.

- [ ] **Step 2: Verify the NFS bootstrap and BackupTarget**

Run:

```bash
kubectl -n longhorn-system wait --for=condition=complete job/longhorn-backup-target-bootstrap --timeout=120s
kubectl -n longhorn-system logs job/longhorn-backup-target-bootstrap
kubectl -n longhorn-system get backuptarget.longhorn.io default \
  -o jsonpath='{.status.available}{"\n"}'
```

Expected: Job complete and target output `true`.

- [ ] **Step 3: Prove an off-cluster backup completes**

Use the known healthy attached volume `pvc-e6258a24-de2e-4321-a6eb-945dc2a53eb7`, never the faulted shared workspace. Create a preflight Snapshot and wait for it to be ready:

```bash
kubectl -n longhorn-system apply -f - <<'EOF'
apiVersion: longhorn.io/v1beta2
kind: Snapshot
metadata:
  name: storage-recovery-preflight
spec:
  volume: pvc-e6258a24-de2e-4321-a6eb-945dc2a53eb7
  createSnapshot: true
EOF
kubectl -n longhorn-system wait --for=jsonpath='{.status.readyToUse}'=true \
  snapshot.longhorn.io/storage-recovery-preflight --timeout=300s
```

Then create and wait for the Backup CR:

```bash
kubectl -n longhorn-system apply -f - <<'EOF'
apiVersion: longhorn.io/v1beta2
kind: Backup
metadata:
  name: storage-recovery-preflight
  labels:
    backup-target: default
    backup-volume: pvc-e6258a24-de2e-4321-a6eb-945dc2a53eb7
spec:
  backupMode: incremental
  snapshotName: storage-recovery-preflight
EOF
kubectl -n longhorn-system wait --for=jsonpath='{.status.state}'=Completed \
  backup.longhorn.io/storage-recovery-preflight --timeout=1800s
kubectl -n longhorn-system get backuptarget.longhorn.io default \
  -o jsonpath='{.status.available}{"\n"}'
```

Expected: the Backup reaches `Completed` and target availability remains `true`.

- [ ] **Step 4: Prove Jupyter bypasses the faulted workspace**

Spawn a power-user server with `mount_shared_longhorn=false`. Verify its Pod reaches `Running` and its volumes do not include `jupyterhub-shared-storage`. Stop only that test server after verification.

- [ ] **Step 5: Record evidence and commit the final runbook outcome**

Document the target URL, target availability time, completed backup name, GPU2 scheduling state, and Jupyter bypass result without tokens or user secrets. Commit:

```bash
git add docs/operations/troubleshooting.md
git commit -m "docs(storage): verify backup and Jupyter recovery path"
```

### Task 5: Request review and preserve the data-recovery boundary

**Files:**
- No source change required unless review identifies a defect.

**Interfaces:**
- Consumes: all commits and live verification evidence.
- Produces: a reviewable branch and an explicit decision point for the faulted workspace data.

- [ ] **Step 1: Review the diff and evidence**

Run:

```bash
git diff origin/main...HEAD --check
git log --oneline origin/main..HEAD
kubectl -n longhorn-system get volumes.longhorn.io pvc-b774d9f7-54fc-4fa1-954c-90f7692402de -o wide
```

Expected: clean diff and the faulted volume remains intact, faulted, and unmodified by this work.

- [ ] **Step 2: Request review**

Open a PR that separates: completed scheduling/backup/Jupyter-bypass evidence from the still-unresolved shared-workspace data recovery. Do not characterize the underlying data as recovered unless an independent backup/original-data restoration has been proven.
