# In-Cluster Image Builder: Storage Strategy

**Status:** Approved, implementing.
**Date:** 2026-07-25
**Repo:** `mul-cps/incluster-image-builder` (deployed to `cit-cps-gpu` via its own Fleet GitRepo, `defaultNamespace: image-builds`)

## Problem

Today, each build Job's `workspace` volume (git-clone output + BuildKit's own
internal content store/snapshots during the build) is a plain `emptyDir`,
backed by whatever the node's default ephemeral storage happens to be — not
necessarily the fast NVMe scratch already provisioned on every worker node
(`fast-scratch` StorageClass, `rancher.io/local-path`, backed by
`/mnt/nvme/scratch`). The cross-run BuildKit layer cache, meanwhile, is
already registry-backed (Harbor `build-cache` project via
`--import-cache`/`--export-cache type=registry,...,mode=max`) — proven working
this session (a second identical build showed a real `CACHED` hit).

## Design

**Ephemeral tier (per-build, NVMe-backed):** replace the `workspace`
`emptyDir` with a Kubernetes *generic ephemeral volume*
(`volumes[].ephemeral.volumeClaimTemplate`) on `fast-scratch`, mounted at
`/workspace` in both the `git-clone` init container and the `buildkit`
container. BuildKit's own internal state directory gets redirected onto the
same volume via `--root=/workspace/.buildkit-root` added to
`BUILDKITD_FLAGS`, so the heavy layer-extraction I/O also lands on NVMe
instead of the container's writable layer.

Because it's a *generic ephemeral volume* (not a separately-managed PVC),
the PVC is owned by the Pod itself: the ephemeral-volume controller creates
it automatically when the pod starts, and deletes it automatically when the
pod is deleted (via existing Job `ttlSecondsAfterFinished` cleanup or
explicit Job deletion). `fast-scratch`'s `reclaimPolicy: Delete` means
`local-path-provisioner` actually removes the on-disk directory under
`/mnt/nvme/scratch`, not just unbinds it — so build residue is fully,
automatically cleaned with no new RBAC and no separate reaper process.
`volumeBindingMode: WaitForFirstConsumer` binds the PV to whatever node the
scheduler picks for the pod, which is fine since every worker node has NVMe
scratch.

**Persistent tier (cross-run cache): unchanged.** BuildKit's registry-backed
cache against Harbor's `build-cache` project stays exactly as implemented.
No PVC is involved in cache persistence at all — it's OCI push/pull over
HTTP, which is inherently safe across concurrent builds landing on different
nodes (a shared-PVC local cache would need Longhorn RWX, which was
considered and rejected as unnecessary complexity given the registry cache
already works).

## Config surface

New `Settings` fields (`config.py`, `deploy/configmap.yaml`):
- `BUILD_SCRATCH_STORAGE_CLASS` (default `fast-scratch`)
- `BUILD_SCRATCH_PVC_SIZE` (default `20Gi`) — global default scratch size
- `MAX_SCRATCH_PVC_SIZE` (default `100Gi`) — upper bound for per-request override

New `BuildResources` field (`models.py`): `scratch_pvc_size: str | None`,
validated in `validation.py` (`_validate_resources`, using the existing
`_memory_to_bytes` unit parser) against `MAX_SCRATCH_PVC_SIZE`, same pattern
as the existing `ephemeral_storage_request`/`ephemeral_storage_limit`
per-request overrides.

`DEFAULT_EPHEMERAL_STORAGE_REQUEST`/`DEFAULT_EPHEMERAL_STORAGE_LIMIT` (today
`10Gi`/`50Gi`, governing the container's own writable-layer quota) shrink to
`1Gi`/`4Gi` — that quota now only needs to cover `/tmp` and small transient
files, since the actual build I/O moves to the PVC.

## Known unverified step

Redirecting BuildKit's root via `--root=<path>` on a mounted PVC has **not**
been tested. A full `buildctl build` was verified working this session with
BuildKit's *default* root; whether `--root` pointed at a `fast-scratch` PVC
mount interacts badly with the rootless setuid/AppArmor/capability fixes
from `images/buildkit-rootless-k8s` is unknown. This is the first
implementation step, with an explicit pass/fail check, not an assumption.

## Testing

- `test_job_generation.py`: PVC template shape (storageClassName, `ReadWriteOnce`,
  size from default vs. per-request override), `BUILDKITD_FLAGS` includes `--root=...`.
- `test_validation.py`: `scratch_pvc_size` bounds/format validation.
- Live verification against the cluster: run a real build, watch
  `kubectl get pvc -n image-builds -w` during the run to confirm the PVC is
  created and then deleted, confirm `buildkitd` starts successfully with the
  redirected root, and confirm cache import/export from Harbor still works
  unchanged (no regression from the persistent tier).

## Docs

README gets a new "Storage strategy" section explaining the ephemeral
NVMe/persistent registry-cache split, referencing this design doc.
