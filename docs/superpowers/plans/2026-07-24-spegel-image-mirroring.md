# Spegel Image Mirroring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy Spegel as a cluster-wide DaemonSet so nodes pull already-cached image layers from peer nodes over the fast cluster network instead of re-fetching from origin registries.

**Architecture:** New Fleet bundle at `cluster-maintenance/clusters/cit-cps-gpu/system/utils/spegel/`, deployed via Spegel's official Helm chart, following this repo's standard bundle pattern (`fleet.yaml` + `values.yaml`). No PVC, no central component — Spegel is a stateless DaemonSet using containerd's own registry-mirror hook.

**Tech Stack:** Rancher Fleet GitOps, Helm (`oci://ghcr.io/spegel-org/helm-charts/spegel`), K3s v1.34.9+k3s1 / containerd 2.2.5-k3s2.

## Global Constraints

- All `cluster-maintenance/` changes go through Fleet GitOps (PR → merge → Fleet reconcile) per this repo's standing rule — no manual `helm install`/`kubectl apply` for the deployment itself.
- Verify infra assumptions live against the actual cluster before writing config, not from general documentation alone (this session's established pattern — see the TurboVNC/Xpra incidents this same session for why).
- No PVC/persistent storage for Spegel — it is deliberately stateless.
- Spec: `docs/superpowers/specs/2026-07-24-spegel-image-mirroring-design.md`.

---

### Task 1: Verify k3s containerd registry-config-path behavior live

**Files:** None (research/verification task, no code changes).

**Interfaces:**
- Produces: confirmed answer (documented in the task's commit/PR description) on whether `/var/lib/rancher/k3s/agent/etc/containerd/certs.d/` is read by k3s's containerd by default on this cluster's version, or whether `containerd-registry-config-path` must be explicitly set in `/etc/rancher/k3s/config.yaml` first. This answer determines whether Task 2's Helm values need any extra containerd-config wiring beyond what Spegel's chart does automatically.

- [ ] **Step 1: Check the live containerd config on one GPU worker node**

Run (via the documented hypervisor bypass path if `kubectl exec` access is available, prefer direct kubectl):

```bash
kubectl debug node/k3s-wk-gpu1 -it --image=busybox -- chroot /host cat /var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl 2>/dev/null || \
kubectl debug node/k3s-wk-gpu1 -it --image=busybox -- chroot /host cat /var/lib/rancher/k3s/agent/etc/containerd/config.toml
```

Look for a line like `config_path = "/var/lib/rancher/k3s/agent/etc/containerd/certs.d"` under `[plugins."io.containerd.grpc.v1.cri".registry]`.

Expected: PASS if `config_path` is already set to that directory (k3s versions since ~v1.21 set this by default — confirm for `v1.34.9+k3s1` specifically since we're relying on it, not assuming).

- [ ] **Step 2: Record the finding**

Note the result (in the Task 2 dispatch/PR description) — if `config_path` is NOT set by default, Task 2 must additionally configure `/etc/rancher/k3s/config.yaml` (via the bootstrap Ansible playbook, not Fleet, since this is a node-level k3s config file, not a cluster-deployed resource) with `containerd-registry-config-path: "/var/lib/rancher/k3s/agent/etc/containerd/certs.d"` and restart k3s on each node — a much bigger change than if it's already the default. Do not proceed to Task 2's Helm values until this is confirmed either way.

- [ ] **Step 3: Commit finding as a comment/note**

No file changes for this task — carry the finding forward into Task 2's dispatch context.

---

### Task 2: Create the Spegel Fleet bundle

**Files:**
- Create: `cluster-maintenance/clusters/cit-cps-gpu/system/utils/spegel/fleet.yaml`
- Create: `cluster-maintenance/clusters/cit-cps-gpu/system/utils/spegel/values.yaml`

**Interfaces:**
- Consumes: Task 1's finding on containerd registry-config-path (determines whether `values.yaml` needs to set `spegel.containerdRegistryConfigPath` explicitly or can rely on the chart's default).
- Produces: a Fleet bundle that, once synced, deploys Spegel's DaemonSet to all 7 nodes.

- [ ] **Step 1: Write fleet.yaml**

```yaml
# Spegel -- peer-to-peer OCI image mirror. Nodes pull already-cached
# image layers from peer nodes over the cluster network instead of
# re-fetching from origin registries (GHCR, Docker Hub, etc.) on every
# pull. Stateless -- no PVC, no central component.
# See docs/superpowers/specs/2026-07-24-spegel-image-mirroring-design.md
name: spegel
defaultNamespace: spegel
helm:
  repo: oci://ghcr.io/spegel-org/helm-charts
  chart: spegel
  version: "v0.0.29"  # NOTE: verify this is the latest stable tag at
                       # implementation time (`helm show chart oci://ghcr.io/spegel-org/helm-charts/spegel --version <x>`
                       # or check https://github.com/spegel-org/spegel/releases)
                       # -- do not blindly trust this pinned value written
                       # during planning.
  releaseName: spegel
  createNamespace: true
  valuesFiles:
    - values.yaml
```

- [ ] **Step 2: Write values.yaml**

Start from the chart's defaults (`helm show values oci://ghcr.io/spegel-org/helm-charts/spegel --version <confirmed-version>` -- read the real default values before writing this file, do not guess the schema). At minimum, confirm/set:

```yaml
# Confirm these keys against the actual chart schema before finalizing --
# Spegel's Helm values schema may differ from this sketch; this is a
# starting point, not a verified final file.
spegel:
  # Only set this explicitly if Task 1 found containerd's config_path
  # is NOT already the k3s default -- otherwise omit and rely on the
  # chart's own default.
  containerdRegistryConfigPath: "/var/lib/rancher/k3s/agent/etc/containerd/certs.d"
  containerdSock: "/run/k3s/containerd/containerd.sock"
  containerdNamespace: "k8s.io"
```

- [ ] **Step 3: Self-review against the chart's real schema**

Run `helm template` locally against the written `values.yaml` (using the pinned chart version) and confirm it renders without error and produces a DaemonSet spec targeting all nodes (no nodeSelector restricting it to GPU-only or control-plane-only). Fix any schema mismatches found.

- [ ] **Step 4: Commit**

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/system/utils/spegel/
git commit -m "feat(spegel): add cluster-wide P2P image mirroring bundle"
```

---

### Task 3: Deploy via Fleet and verify DaemonSet health

**Files:** None (deployment/verification task).

**Interfaces:**
- Consumes: Task 2's merged bundle.
- Produces: confirmed-healthy Spegel DaemonSet across all 7 nodes.

- [ ] **Step 1: Open PR, get it reviewed (independent review given this touches every node's containerd config path), merge**

Follow this repo's standard PR + review process (see `docs/troubleshooting.md` for the class of incident that justifies this rigor for anything touching shared/node-level config).

- [ ] **Step 2: Force Fleet sync**

```bash
CM_GEN=$(kubectl get gitrepo cluster-maintenance -n fleet-local -o jsonpath='{.spec.forceSyncGeneration}')
kubectl patch gitrepo cluster-maintenance -n fleet-local --type merge -p "{\"spec\":{\"forceSyncGeneration\": $((${CM_GEN:-0}+1))}}"
```

- [ ] **Step 3: Verify DaemonSet is Running on all 7 nodes**

```bash
kubectl get daemonset -n spegel
kubectl get pods -n spegel -o wide
```

Expected: `DESIRED == READY == 7` (3 control-plane + 4 GPU workers), one pod per node.

- [ ] **Step 4: Check for containerd-side errors on at least one node**

```bash
kubectl logs -n spegel -l app.kubernetes.io/name=spegel --tail=50 | grep -iE "error|fail"
```

Expected: no fatal errors. If containerd's `config_path` wasn't already correctly wired (Task 1's finding), this is where it would surface — a mirror registration failure.

---

### Task 4: Verify peer-to-peer pull actually works (not just "pods are Running")

**Files:** None (empirical verification task).

**Interfaces:**
- Consumes: Task 3's healthy DaemonSet.
- Produces: concrete proof (logged in the task report) that a cross-node pull actually sourced layers from a peer, not the origin registry.

- [ ] **Step 1: Pick a large already-pulled image present on one GPU node but not another**

e.g. `ghcr.io/mul-cps/cps-jupyter-notebook:latest-desktop-ros2-xpra` (confirmed ~37GB, pulled onto whichever node most recently ran the `gpu-desktop-xpra` profile).

```bash
kubectl get pods -n jupyterhub -o wide | grep desktop-xpra  # find which node has it
```

- [ ] **Step 2: Force a pull of that same image on a DIFFERENT node that doesn't have it cached**

Easiest: spawn the `gpu-desktop-xpra` profile again and let KAI/kube-scheduler place it on a different GPU node (or use `nodeSelector`/`nodeAffinity` in a throwaway test pod to force placement), with `imagePullPolicy: Always`.

- [ ] **Step 3: Confirm via Spegel's logs/metrics that the pull was peer-sourced**

```bash
kubectl logs -n spegel -l app.kubernetes.io/name=spegel --since=5m | grep -i <image-digest-or-name>
```

Expected: log lines indicating the requested layer was resolved from a peer node's address, not proxied through to `ghcr.io` directly. Also compare wall-clock pull time against a known cold-pull baseline (e.g. this session's earlier ~30min desktop-ros2-xpra pulls) — a peer-sourced pull over the cluster's fast internal network should be dramatically faster.

- [ ] **Step 4: Record the result**

If peer-sourcing is NOT observed, this is a real gap — return to Task 1/2 and re-diagnose rather than declaring done. Do not accept "pods are Running" alone as proof this feature works.

---

### Task 5: Document

**Files:**
- Modify: `docs/troubleshooting.md` (only if any incident occurred during rollout — this repo's established discipline; skip if genuinely clean)
- Modify: `docs/superpowers/specs/2026-07-24-spegel-image-mirroring-design.md` (update with final confirmed chart version, containerd-config-path finding, and verification results)

- [ ] **Step 1: Update the spec doc's status and record the real outcome of Tasks 1 and 4**

- [ ] **Step 2: Commit**

```bash
git add docs/
git commit -m "docs(spegel): record rollout verification results"
```
