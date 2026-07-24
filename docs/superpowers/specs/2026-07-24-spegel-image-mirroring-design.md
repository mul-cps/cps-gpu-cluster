# Cluster-wide Image Mirroring via Spegel

**Status:** Deployed and verified live on 2026-07-24. All 7 nodes running Spegel v0.7.4, peer-to-peer mirroring confirmed working with real traffic (see "Live verification results" below).
**Date:** 2026-07-24

## Problem

Every node in the `cit-cps-gpu` cluster pulls container images independently from their origin registries (GHCR, Docker Hub, NVIDIA NGC, etc.) over the internet, even when another node on the same 10.21.0.0/16 cluster network already has that exact image layer cached locally. This repo builds and pushes large multi-GB images regularly (e.g. the `cps-jupyter-notebook` desktop variants, 30-40GB), and with 4 GPU worker nodes (`k3s-wk-gpu1..4`) that can each independently schedule the same JupyterHub profile pod, redundant full-image pulls from the internet are wasteful when the cluster's internal network is much faster than the path to GHCR.

No image-mirroring or caching solution exists in the cluster today (confirmed: no `registries.yaml` on nodes, no Spegel/registry-mirror pods running).

## Decision

Deploy [Spegel](https://github.com/spegel-org/spegel) — a stateless peer-to-peer OCI image mirror. Each node's containerd, on a cache miss, asks Spegel (running as a DaemonSet) whether ANY other node in the cluster already has the needed layer; if so, it streams it over the cluster network from that peer instead of the origin registry. No central registry, no PVC/shared storage — peer discovery and layer lookup use Kubernetes itself (a distributed hash table) rather than a stateful backing store.

### Why Spegel over a central pull-through registry mirror (the alternative considered)

Both were viable at this cluster's size (7 nodes); a central mirror (`registry:2` in proxy mode + Longhorn PVC) is simpler to reason about but is a single component to size/scale/keep available, and doesn't remove the "first pull is still slow" case per cache-cold image — every image still transits through one place. Spegel has zero storage footprint, no single component to keep healthy, and gets faster as more nodes have pulled a given image (more peers to source layers from). The user chose Spegel explicitly after this tradeoff was presented.

## How it works (mechanism)

1. Spegel runs as a DaemonSet (one pod per node, `hostNetwork: true`), with each pod running a local OCI-registry-compatible endpoint.
2. It configures containerd's registry mirror settings (via the `hosts.toml` drop-in files under `/var/lib/rancher/k3s/agent/etc/containerd/certs.d/`, which k3s's containerd reads automatically — this repo's k3s version needs to be confirmed to read this path without extra config, see Task 1) to route pulls through the local Spegel endpoint first.
3. Spegel pods discover each other and advertise which image digests/layers they have via a peer-to-peer protocol (built on containerd's own content store introspection — no separate database).
4. On a pull, if a peer has the needed layer, Spegel streams it node-to-node over the cluster network; otherwise it transparently falls through to the real upstream registry (GHCR, Docker Hub, etc.), same as today.

## Scope

- Applies cluster-wide, to every node (control-plane nodes get it too for consistency/simplicity, even though they don't run GPU workloads — Rancher/system images benefit too).
- No changes to how images are built/pushed (this repo's `mul-cps/cps-jupyter-notebook` CI is untouched).
- No changes to any existing Fleet bundle other than adding a new one.

## Implementation risk and required first task

k3s's exact default containerd registry-config-path behavior needs to be confirmed empirically against the live cluster's actual k3s version (`v1.34.9+k3s1`, confirmed via `kubectl get nodes`) before writing the Helm values — **Task 1 of the plan is to verify this live** (check whether `/var/lib/rancher/k3s/agent/etc/containerd/certs.d/` is read by default, or whether `/etc/rancher/k3s/config.yaml`'s `containerd-registry-config-path` needs to be set first) rather than assume from general Spegel documentation, matching this session's established pattern of verifying infra assumptions live instead of guessing.

## Rollout plan

1. Verify containerd registry-config-path behavior live (Task 1, above).
2. New Fleet bundle `cluster-maintenance/clusters/cit-cps-gpu/system/utils/spegel/` (alongside `node-tuning`/`reflector` in the same `system/utils/` category), using Spegel's official Helm chart (`oci://ghcr.io/spegel-org/helm-charts/spegel`).
3. Deploy via Fleet (same GitOps flow as every other bundle in this repo — no manual `helm install`).
4. Verify live: confirm the DaemonSet is Running on all 7 nodes, then prove peer-to-peer pull actually works — e.g. delete a large image's local cache on one GPU node (`crictl rmi` / `ctr -n k8s.io images rm`) while it's still present on another, force a re-pull, and confirm (via Spegel's own metrics/logs, not just "it worked") that the pull came from a peer, not the origin registry.
5. Document in `docs/troubleshooting.md`'s style if any incident occurs during rollout, matching this repo's established documentation discipline.

## Live verification results (2026-07-24)

**Task 1 (containerd config path):** Confirmed live against `k3s-wk-gpu1` (v1.34.9+k3s1) — `config_path` is already set to `/var/lib/rancher/k3s/agent/etc/containerd/certs.d` by default in `/var/lib/rancher/k3s/agent/etc/containerd/config.toml`. No node-level k3s config changes were needed. Also confirmed the real k3s-specific containerd socket path (`/run/k3s/containerd/containerd.sock`) and content-store path (`/var/lib/rancher/k3s/agent/containerd/io.containerd.content.v1.content`), both different from the chart's generic upstream-containerd defaults and both required as explicit `values.yaml` overrides.

**Task 3 (DaemonSet health):** All 7 pods (3 control-plane + 4 GPU workers) reached `Running`/`1/1 Ready` within ~20s of Fleet sync. Startup logs showed transient `failed to run bootstrap` errors from all pods simultaneously trying to resolve the `spegel-bootstrap` headless service before its DNS records were populated — self-healing, resolved within ~15s (`bootstrap completed connectivity is reached`), not a real problem.

**Task 4 (peer-to-peer pull proof):** Verified with concrete evidence, not just "the pod is Running":
- Confirmed `ghcr.io/mul-cps/cps-jupyter-notebook:latest-desktop-ros2-xpra` (19.2GB) was present on `k3s-wk-gpu4` but not `k3s-wk-gpu1`.
- Forced a pull on `k3s-wk-gpu1` via `crictl pull`.
- Confirmed via Spegel's own Prometheus metrics (`kubectl port-forward` directly to gpu1's Spegel pod, port 9090 — **not** the ClusterIP Service, which load-balances to a random pod and gives a misleading aggregate view) that `spegel_mirror_requests_total{cache="hit",registry="ghcr.io"}` was 71 (one per image layer) and `spegel_mirror_last_success_timestamp_seconds` matched the test window exactly (2026-07-24 16:20:16 CEST).
- Note: many of the image's ~70+ layers were already locally present on gpu1 from other already-pulled sibling images sharing the same CUDA/PyTorch/ROS base layers (this repo's images share a lot of common base layers) — this is expected layer deduplication, not a flaw in the test, but it means "the pull finished quickly" alone wasn't proof by itself; the Prometheus cache-hit counter was the actual proof.
- Debugging pitfall hit along the way: Spegel writes a single `_default/hosts.toml` wildcard mirror config when `mirroredRegistries: []` (all registries), not a per-registry file like `ghcr.io/hosts.toml` — looking for the wrong filename gave a false "mirror config missing" impression initially.

**Rollback safety note** (from PR #27 review): Spegel's chart has a `helm uninstall` hook (shipped since v0.2.0) that cleanly removes the containerd mirror config it wrote. This depends on the hook actually running — **never force-delete the `spegel` namespace or its resources**; let Fleet/Helm uninstall complete normally if this bundle is ever removed, and verify `certs.d/` is empty afterward.

## CRITICAL incident: first-time pulls were completely broken (found and fixed same day, 2026-07-24)

**This corrects a wrong claim made above** ("Spegel's generated mirror config includes the real upstream registry as a fallback, so a crash-looping Spegel DaemonSet degrades to normal direct pulls") — that was **not true** for the initial rollout config and was never actually verified before being written; it was an unverified assumption carried over from the PR #27 review discussion. The real, verified behavior:

- With `mirroredRegistries` left at the chart default (`[]`, meaning "mirror all registries"), Spegel writes a single wildcard `_default/hosts.toml` containing **only its own two local endpoints, with no fallback host entry for the real origin registry at all**.
- Per containerd's documented `hosts.toml` semantics, once a custom hosts.toml exists for a registry, it is the *complete* set of hosts to try — there is no implicit fallback to the real registry hostname.
- Result: **every first-time pull of any image not already cached on some cluster node failed outright** with `NotFound`, cluster-wide, immediately upon rollout. Confirmed live: `crictl pull docker.io/library/alpine:3.19.7` (a real, common image, definitely not cached anywhere in this cluster) failed in under a second with zero corresponding Spegel log lines — the request never even reached Spegel's registry handler.
- This was caught the same day as rollout, before it caused a real incident for a user, by deliberately testing the fallback path (not just the peer-hit path) after the initial "it works" verification.

**Fix**: explicitly list `mirroredRegistries` (docker.io, ghcr.io, quay.io, gcr.io, registry.k8s.io, nvcr.io — the registries actually observed in use via Spegel's own metrics and containerd OCI event logs) instead of leaving it as the wildcard default. This makes Spegel generate **per-registry** `hosts.toml` files, each of which correctly includes the real origin as an explicit fallback host (confirmed live: `docker.io/hosts.toml` now includes `server = 'https://registry-1.docker.io'`, Docker Hub's actual API hostname, which Spegel resolves automatically once the registry is explicitly named).

**Verified after the fix, both paths, with Prometheus metrics as proof (not just "the pull succeeded")**:
- Fallback-to-origin: `spegel_mirror_requests_total{cache="miss",registry="docker.io"}` incremented on the node doing a genuine first-time pull, pull succeeded.
- Peer-to-peer: `spegel_mirror_requests_total{cache="hit",registry="docker.io"}` incremented on a second node pulling the same (now cluster-cached) image, sourced from the first node as a peer.

**Deliberately excluded from `mirroredRegistries`**: the one private/authenticated registry seen in cluster traffic (`git.unileoben.ac.at:5050`). Mirroring it would require `basicAuthSecretName` configured correctly; getting that wrong could break it worse than simply leaving it to bypass Spegel and pull directly, as it did before Spegel existed.

**Lesson**: when a review or design doc asserts a safety property ("X falls back to Y"), verify that specific claim empirically before relying on it — the same discipline already established elsewhere this session (TurboVNC/Xpra fixes), applied here to a claim from a different agent's PR review rather than my own reasoning. An unverified safety claim written down confidently is exactly as dangerous as no claim at all.

## Explicitly out of scope

- A central pull-through registry mirror (the alternative considered and rejected).
- Any change to image build/publish pipelines.
- Backing Spegel with persistent storage (Longhorn or otherwise) — it is deliberately stateless by design; a PVC would be working against the tool's architecture, not with it.
