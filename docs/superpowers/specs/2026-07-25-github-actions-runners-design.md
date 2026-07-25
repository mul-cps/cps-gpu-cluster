# In-Cluster GitHub Actions Runners

**Status:** Approved, implementing.
**Date:** 2026-07-25
**Repo:** `mul-cps/cps-gpu-cluster` (Fleet bundle) + a shared BuildKit pool
(location TBD during implementation — likely a new `ci` namespace, see
Open Questions).

## Problem

CI for `mul-cps` org repos (`cps-gpu-cluster`, `cps-jupyter-notebook`,
`incluster-image-builder`, ...) currently runs on GitHub-hosted runners.
Some of that CI needs things GitHub-hosted runners can't provide at all
(A100 GPU access for smoke-testing GPU workloads) or can only provide
slowly/expensively (Docker image builds without any shared layer cache).
Self-hosted runners on `cit-cps-gpu` solve both, and can reuse
infrastructure this session already built and verified: Spegel (P2P
registry mirroring, transparent to any pod), Harbor (private registry +
registry-backed BuildKit cache), and the rootless-BuildKit-in-Kubernetes
fixes from `incluster-image-builder` (setuid `newuidmap`/`newgidmap`,
AppArmor `Unconfined`, non-ALL-dropped capability bounding set,
`fast-scratch` NVMe scratch).

## Design

### 1. Runner control plane

GitHub's official Actions Runner Controller (`gha-runner-scale-set` Helm
chart, `actions/actions-runner-controller`), deployed as a new Fleet bundle
under `cluster-maintenance/clusters/cit-cps-gpu/system/ci/`, following the
same `fleet.yaml` + `values.yaml` pattern as every other bundle in this
repo. Runners are **ephemeral**: one pod per job, destroyed after — no
residue accumulates by construction, matching the pattern already
established for `incluster-image-builder`'s build Jobs.

### 2. GitHub identity

A GitHub App installed on the `mul-cps` org (App ID, Installation ID,
private key), stored as a SopsSecret referenced by the runner scale set's
`githubConfigSecret` — same secret-handling pattern as the Harbor
admin/robot credentials and API static token from this session. Registers
as an **org-level** runner scale set (`githubConfigUrl:
https://github.com/mul-cps`), usable by any repo in the org without
per-repo registration.

**Requires manual, human action:** creating a GitHub App is a web-UI
flow (org Settings → Developer settings → GitHub Apps → New GitHub App,
or the manifest-flow shortcut) that cannot be done via `gh` CLI or API
alone. This is the one step in this design the operator must do by hand.

### 3. Runner mode

`containerMode: kubernetes`, not `dind`. No privileged sidecar, no local
Docker daemon inside the runner pod. Plain CI (test suites, linters,
non-container build steps) runs directly in the runner container. This is
a deliberate deviation from GitHub-hosted-runner defaults, consistent with
this repo's established no-privileged-containers posture.

### 4. Docker image builds

Workflows that build images (e.g. `docker/build-push-action`, already used
in `cps-jupyter-notebook`) add one `docker buildx create --driver
kubernetes ...` setup step pointing at a shared, persistent rootless
BuildKit pool, instead of each runner pod running its own Docker-in-Docker
daemon. The pool:

- reuses `ghcr.io/mul-cps/buildkit-rootless-k8s:v1` (the exact image built
  and verified working this session) and its proven securityContext
  (`allowPrivilegeEscalation: true`, `appArmorProfile: Unconfined`,
  `seccompProfile: Unconfined`, capabilities **not** dropped to `ALL` —
  see `incluster-image-builder`'s `kubernetes.py` for the full rationale);
- mounts `fast-scratch` (NVMe-backed, now confirmed working after this
  session's `local-path-provisioner` ConfigMap fix) for local build state;
- imports/exports a registry-backed BuildKit cache against Harbor, same
  mechanism as `incluster-image-builder` (exact project TBD, see Open
  Questions).

Existing `docker/build-push-action`-based workflows need only the one
`buildx create` step added, not a rewrite.

**Verified live, important:** registry authentication for `--push`/
`--export-cache` operations against the pool is forwarded from the
**client's own session** (whatever invokes `docker buildx build`/
`buildctl`), not the long-running daemon's own environment/credentials.
Each CI workflow needs its own `docker login` step before pushing --
see `system/ci/README.md` for the exact pattern. The daemon's own
mounted credentials only cover its own pulls (e.g. a Dockerfile `FROM`
referencing a private Harbor image).

### 5. Registry mirroring

No new configuration needed. Spegel already mirrors pulls transparently
for any pod on any node — runner pods' own image, any base images
referenced in CI Dockerfiles, and the BuildKit pool's own pulls all
benefit automatically.

### 6. GPU-dependent CI jobs

Request `nvidia.com/gpu` and schedule through the existing KAI Scheduler
at the **lowest priority tier**, preemptible by real training/inference
workloads — consistent with `docs/gpu-scheduling-architecture.md`'s
existing three-tier design. CI should never be able to starve real
cluster users.

### 7. Pruning (two independent, unrelated layers)

- **BuildKit pool's local NVMe scratch:** bounded by buildkitd's own
  built-in GC policy (`--oci-worker-gc-keepstorage=<N>GB` in
  `BUILDKITD_FLAGS`), which evicts LRU content automatically. No cron job
  needed for this layer.
- **Harbor registry storage:** Harbor's own built-in garbage collection,
  scheduled (via Harbor's GC API/UI, or a CronJob calling that API), plus
  a tag-retention policy on the cache project(s) specifically — cache
  images have no natural expiry otherwise, and CI will push substantially
  more of them than the manual `incluster-image-builder` alone did.
- **Runner pods themselves:** ephemeral by construction (ARC default),
  so no accumulation risk here — nothing to prune.

## Open Questions (resolve during implementation)

1. **Namespace for the BuildKit pool:** new `ci` namespace, or reuse
   `image-builds`? Leaning toward a new `ci` namespace to keep CI-runner
   infra and the manual image-builder API cleanly separated, but the two
   could reasonably share the BuildKit pool itself to avoid running two
   separate pools.
2. **Harbor project split:** does CI push to the same `cps-research`/
   `cps-base`/`cps-users` projects and `build-cache` cache project as
   `incluster-image-builder`, or get its own (e.g. `ci-images`,
   `ci-build-cache`) to keep retention policies and permissions separate?
3. **BuildKit pool sizing:** replica count / concurrency limits, informed
   by expected CI concurrency across `mul-cps` repos.
4. **Runner image:** stock ARC runner image plus `docker buildx` +
   `kubectl` preinstalled (for the buildx-kubernetes-driver step), or a
   custom image built the same way `incluster-image-builder`'s own images
   are.

## Testing

- Deploy ARC + a runner scale set, confirm a real GitHub Actions workflow
  (a small test workflow in one of the `mul-cps` repos) picks up and runs
  on the self-hosted runner.
- Confirm an unmodified `docker/build-push-action` workflow builds
  successfully via the buildx-kubernetes-driver pool and pushes to Harbor.
- Confirm cache reuse across two runs of the same workflow (same
  `CACHED` verification pattern used for `incluster-image-builder`).
- Submit a GPU-requesting test job, confirm it lands in the lowest KAI
  priority tier and is preemptible.
- Verify pruning: force the BuildKit pool's scratch near its GC threshold
  and confirm eviction; confirm Harbor GC actually reduces registry
  storage usage after a scheduled run.
