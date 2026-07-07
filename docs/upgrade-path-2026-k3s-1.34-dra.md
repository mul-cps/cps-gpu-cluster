# Upgrade Path: K3s 1.34 + DRA-capable GPU Operator (2026)

## Goal

Move the cluster to a current-stable stack so NVIDIA's DRA (Dynamic Resource
Allocation) driver for GPUs becomes usable, without breaking Rancher
management, Fleet GitOps, storage, ingress, or GPU workloads along the way.

DRA requires **Kubernetes v1.34.2+** (confirmed from NVIDIA's DRA install
docs). We are currently on K3s v1.33.5+k3s1 — one minor version behind.

**Important caveat, already established separately:** DRA's `DynamicMIG`
feature (pod-triggered automatic MIG repartitioning) is alpha and explicitly
supports **H100 and newer only** — NVIDIA's release notes exclude A100. This
upgrade gets us onto the modern DRA allocation model (`ResourceClaim` /
`DeviceClass` instead of extended resources) with **static** MIG geometry,
not automatic workload-driven A100 repartitioning. Do not sell this
internally as "MIG now rebuilds itself" — it doesn't, for this hardware.

## Scope / change mechanism

Almost everything in this cluster's `cluster-maintenance/` day-2 layer is
Fleet-managed from this repo — those components get their version bumped in
Git (`fleet.yaml`/`values.yaml`), never via a direct `helm upgrade`. Two
things in this plan are legitimate exceptions, since they either predate
Fleet or aren't sourced from this repo at all:

- **Rancher itself** — bootstrapped via Ansible/`helm install` before Fleet
  exists to manage anything; its upgrades stay a direct Helm operation.
- **K3s** — the base OS/kubelet layer, upgraded via Ansible against the
  provisioned VMs, not a Kubernetes object Fleet can reconcile.
- **cert-manager** is Fleet-managed, but from a *different* GitRepo
  (`cit-teaching-platform`), not this one — see step 4 below.

Everything else (Longhorn, ingress-nginx, MetalLB, GPU Operator, KAI
Scheduler, JupyterHub, etc.) must be changed by editing this repo and
letting Fleet reconcile.

## Status update (2026-07-07)

The K3s upgrade described in this plan has since been **executed**: all 7
nodes are now running **v1.34.9+k3s1** (confirmed live). The
`bootstrap-cluster/ansible/group_vars/all.yml` drift noted below has also
been fixed to match.

The GPU Operator bump to **v26.3.3** was attempted and then **reverted**
back to **v25.10.0** (confirmed live) — do not treat v26.3.3 as deployed.
The bundle vendors the chart tree locally, so `fleet.yaml`'s `version`
field does not necessarily reflect the real deployed version; always
cross-check the live pod image (`kubectl get pods -n gpu-operator -o
jsonpath='{.items[*].spec.containers[*].image}'`).

The table below is the **pre-upgrade snapshot** from when this plan was
written and is otherwise unchanged/still accurate for everything else
(Rancher, cert-manager, Longhorn, ingress-nginx, MetalLB). Note Fleet is
actually **v0.14.3** (chart drifted since this table was written), not the
v0.14.0 shown below.

## Current live versions (confirmed via kubectl/helm, 2026-07-06)

| Component | Current | Notes |
|---|---|---|
| K3s | v1.33.5+k3s1 | all 7 nodes |
| Rancher | v2.13.0 | Helm release `rancher-2.13.0` |
| Fleet | v0.14.0 | chart `fleet-108.0.0+up0.14.0` |
| cert-manager | v1.16.1 | |
| Longhorn | v1.9.2 | |
| ingress-nginx | chart 4.11.3 / app 1.11.3 | |
| MetalLB | chart 0.14.9 | |
| rancher-monitoring | 108.0.0+up77.9.1-rancher.6 | |
| NVIDIA GPU Operator | v25.10.0 | Fleet bundle `system/gpu/gpu-operator` |
| Node OS | Ubuntu 24.04.3/24.04.4 LTS, kernel 6.8.0-124 | |

**Known drift**: `bootstrap-cluster/ansible/group_vars/all.yml` still pins
`k3s_version: v1.31.2+k3s1`. The live cluster was upgraded to v1.33.5 out of
band without updating this file. Fix this as part of the plan below — it's
what the next Ansible run would silently disagree with otherwise.

`system-upgrade-controller` is already installed in `cattle-system` and idle
(no active Plan). The cluster is **registered/imported** into Rancher (an
existing `management.cattle.io` cluster named `local` with no
`provisioning.cattle.io` version field), not Rancher-provisioned — so K3s
version changes are driven by us (Ansible re-run or a `system-upgrade-controller`
Plan), not by Rancher's cluster-management upgrade UI.

## Compatibility findings

- **Rancher v2.13.6** (latest patch of the *currently installed minor*,
  v2.13.0) already supports **K3s 1.32, 1.33, and 1.34**. Source: SUSE
  Rancher support matrix. This means **no Rancher minor upgrade (2.13→2.14)
  is required** to reach K3s 1.34 — a same-minor patch bump is enough, which
  is much lower risk.
- Rancher's own documented upgrade policy: only patch-to-patch within a
  minor, or one full minor step at a time (never skip a minor). Since we're
  staying within 2.13.x, this is the simple case.
- **K3s** upgrades must also be sequential, one minor at a time (1.33 → 1.34,
  not skipping to 1.35). Latest stable K3s 1.34 patch as of now: **v1.34.9+k3s1**.
  Note: the K3s 1.34 series bumps the bundled Traefik chart to v40.x, which
  renames the ingress class provider from `kubernetesIngressNginx` to
  `kubernetesIngressNGINX` — irrelevant here since Traefik isn't used
  (ingress-nginx is the deployed controller), but worth knowing if that ever
  changes.
- **GPU Operator v26.3.3** is the current stable (GA) release and is the
  version NVIDIA's docs pair with DRA Driver v0.4.0 at Kubernetes v1.34.2+.
  This is a large jump from v25.10.0 (25.10 → 26.3) — treat it as its own
  tested step, not bundled with the K3s upgrade.
- **cert-manager v1.16.1** was released before 1.34 existed and isn't tested
  against it. cert-manager v1.19.x lists tested Kubernetes versions 1.31–1.34
  — bump to the latest 1.19.x patch.
- **Longhorn v1.9.2**: reported compatible with K8s up to 1.34. (Longhorn
  v1.11.x explicitly *requires* 1.34+ due to a CSI external-provisioner bump —
  we're not going that far yet. Recommend the latest 1.9.x patch release for
  bug fixes, not a jump to 1.10/1.11 in this pass.) Verify against Longhorn's
  own support matrix page before executing, since this claim was based on
  secondary sources, not the primary matrix table.
- **ingress-nginx 4.11.3 / MetalLB 0.14.9**: no known incompatibility with
  K8s 1.34; low risk, no forced bump required, but check current chart
  release notes right before executing in case that's changed.
- **rancher-monitoring**: version is tied to the Rancher minor release train;
  since Rancher itself isn't jumping minors here, no forced bump.

## Recommended order

Rancher's own guidance: you can upgrade Kubernetes without upgrading
Rancher, provided the target Kubernetes version is already in Rancher's
supported matrix for the *currently installed* Rancher version — which is
the case here (2.13.6 supports 1.34). So: **patch Rancher first (cheap,
same minor), then upgrade K3s, then upgrade downstream components, then GPU
Operator — with the existing GPU/MIG breakage fixed before any of this
starts.**

1. **Pre-flight** (do this regardless of which step you're on):
   - `git tag pre-upgrade-2026-07` on this repo for a rollback point.
   - Take an etcd snapshot on the K3s control-plane (`k3s etcd-snapshot save`)
     on all 3 CP nodes, or confirm the automated snapshot schedule is current.
   - Take a Rancher backup via the `rancher-backup` operator if installed,
     or `kubectl get all -A -o yaml` dump as a fallback.
   - Snapshot/backup Longhorn volumes for anything stateful (JupyterHub user
     PVCs, Postgres).
   - **Fix the currently-broken GPU/MIG state first** (ClusterPolicy error,
     failed MIG state on gpu1/gpu3, gpu4's missing operator daemonsets) —
     do not layer a K3s/GPU-Operator upgrade on top of a cluster that's
     already mid-failure; you won't be able to tell which problem caused
     what.

2. **Rancher: v2.13.0 → v2.13.6** (patch only, same minor — low risk):
   - `helm upgrade rancher rancher-stable/rancher --namespace cattle-system --version 2.13.6 --reuse-values`
   - Verify: `kubectl -n cattle-system rollout status deploy/rancher`, log
     into the UI, confirm Fleet/GitRepo sync still healthy
     (`kubectl get gitrepo -n fleet-local`).
   - Also bump `rancher-webhook` if the chart requires a matching version
     (check `helm show chart` output / release notes for 2.13.6).

3. **K3s: v1.33.5+k3s1 → v1.34.9+k3s1** (single minor hop):
   - Update `bootstrap-cluster/ansible/group_vars/all.yml`:
     `k3s_version: v1.34.9+k3s1` (this also fixes the existing drift from
     v1.31.2 — the file was already stale even for the current live 1.33.5).
   - Upgrade control-plane nodes **one at a time**, verifying HA/etcd health
     between each (`kubectl get nodes`, `kubectl get pods -n kube-system`):
     `ansible-playbook -i inventory.ini playbooks/02-k3s-cluster.yml --limit k3s-cp1`,
     then cp2, then cp3 — or drive it via a `system-upgrade-controller` Plan
     if you prefer the automated in-place mechanism already installed.
   - Then upgrade GPU worker nodes one at a time (cordon → upgrade → verify
     GPU capacity restored → uncordon) — GPU workers are more disruptive to
     get wrong, don't batch them.
   - After each node: `kubectl get nodes -o wide` to confirm the new
     `v1.34.9+k3s1` version and `Ready` status before moving to the next.

4. **Downstream components** (can be done in parallel with each other, after
   K3s is fully on 1.34). **Everything under `cluster-maintenance/` in this
   repo is Fleet-managed — bump the version field in the relevant
   `fleet.yaml`/`values.yaml`, commit, and let Fleet reconcile. Do not
   `helm upgrade` these by hand; a manual out-of-band change here is exactly
   the kind of drift that caused the `k3s_version` mismatch this doc already
   found, and Fleet will fight or silently mask a manual change on the next
   sync.**
   - **cert-manager is NOT managed by this repo.** Its Helm release
     (`cit-crds`) is deployed by the separate `cit-teaching-platform`
     GitRepo (`https://github.com/bjoernellens1/cit-teaching-platform.git`,
     confirmed via `kubectl get gitrepo -A`). Bumping it to v1.19.x for 1.34
     compatibility must happen in that repo, coordinated separately — out
     of scope for this document beyond flagging that it needs doing.
   - Longhorn v1.9.2 → latest v1.9.x patch: bump the `version:` in
     `system/storage/longhorn/fleet.yaml` (re-check Longhorn's own support
     matrix for the exact target patch before committing).
   - ingress-nginx / MetalLB: bump `version:` in
     `system/networking/ingress-nginx/fleet.yaml` and
     `system/networking/metallb/fleet.yaml` to latest patch in their current
     minor, as routine hygiene — not a hard requirement for 1.34.
   - After each Fleet commit: `kubectl get bundles -n fleet-local` to confirm
     it actually reconciled (`0/1 NotReady` means the version bump broke
     something — don't move to the next component until it shows Ready),
     then re-run `scripts/verify.sh`.

5. **GPU Operator: v25.10.0 → v26.3.3** (its own tested step, only after
   step 3-4 are stable and GPU state is confirmed healthy again). This is
   already the Fleet-managed pattern above, spelled out because it's the
   highest-risk bump in this plan:
   - Bump `version: v26.3.3` in
     `cluster-maintenance/clusters/cit-cps-gpu/system/gpu/gpu-operator/gpu-operator/fleet.yaml`,
     commit, let Fleet reconcile — do not `helm upgrade` this namespace
     directly, the whole point of the ClusterPolicy drift found earlier was
     Fleet and live state disagreeing.
   - Do **not** enable the DRA driver in this step — land on v26.3.3 using
     the existing classic device-plugin + MIG Manager path first, confirm
     all 8 GPUs report correctly (`kubectl get nodes -o json | jq
     '.items[].status.allocatable'` matches the target layout from the MIG
     fix work), then treat DRA enablement as a separate, later, opt-in change.

6. **Later/optional: enable DRA** (separate initiative, not required for
   cluster health):
   - Requires `nvidia.com/dra-kubelet-plugin=true` node labels and
     `driver.manager.env[0].name=NODE_LABEL_FOR_GPU_POD_EVICTION` set in
     GPU Operator values.
   - Known A100-specific caveat: the MIG Manager does **not** automatically
     evict the DRA kubelet plugin during MIG config changes — manual pod
     restart required. Static MIG geometry only; do not attempt
     `DynamicMIG` on this hardware.
   - Migrate JupyterHub `PROFILE_CONFIGS` from extended resources
     (`nvidia.com/gpu`, `nvidia.com/mig-*`) to `ResourceClaim`/`DeviceClass`
     only after this is validated in isolation (e.g. a single GPU worker) —
     it changes the pod spec shape KubeSpawner needs to emit.

## Rollback notes

- Rancher patch and downstream component bumps: standard `helm rollback`.
- K3s minor upgrade: K3s supports rolling back a server to the previous
  minor via the saved etcd snapshot taken in step 1 — practice this on
  one control-plane node in isolation if possible before touching the
  whole HA set.
- GPU Operator: Fleet bundle version pin means reverting `fleet.yaml` to
  `v25.10.0` and letting Fleet reconcile is the rollback path; confirm no
  CRD schema changes between 25.10 and 26.3 block a clean downgrade before
  relying on this.
