# CPS JupyterHub deployment

This directory owns the CPS Helm/Fleet deployment and the remaining legacy launch form. The application integrations are released in `cps-compute-hub`; the shared catalog, qualification records and operational documentation live in [the compute platform guide](../../../../../../docs/compute-platform/index.md). CIT has its own deployment repository and independent admin/database credentials.

## Source and running-state boundary

The watched GitOps branch, mounted values Secret, Hub image and native approval references must be checked together. A Ready Fleet bundle does not prove that an out-of-band values overlay or a new application branch is deployed. The [28 October checkpoint](../../../../../../docs/compute-platform/current-state-20261028.md) records current bounded results and remaining production work.

`PROFILE_CONFIGS` remains the legacy profile definition used by this form. The new managed adapters and shared policy catalog are separate until their production activation is qualified. Do not describe this legacy path as fully migrated to the central policy service. Existing fixed research GPU profiles are retained; legacy freeform overrides are removed.

## Fixed profiles and authorization

- KubeSpawner validates selected slugs against the server's resolved profile list. The packaged `validate_legacy_profile_request` additionally rejects unsupported freeform GPU, image and custom NFS values before the legacy hook performs directory, storage or SSH effects.
- Ordinary default REST starts must continue to work. A missing profile uses only the server-resolved default; an explicit invalid profile is rejected.
- The final resolved list must include approved profiles supplied by the installed native adapter. Do not validate against an earlier UI-only subset.
- Profile resources, runtime image, queue and priority are fixed by the server. A power-user group is not permission to request an arbitrary GPU count or override those fields.
- Dask and Slurm entries are unavailable until their backing route and authorization boundary are provisioned and qualified. The ordinary notebook ServiceAccount is `jupyter-notebook`, with token automount disabled and no Dask role binding.
- Native shared-workspace grants, membership and global reservations retain their own independent admission checks. A visible profile alone does not reserve capacity.

The existing `dask-sa` binding is retained for compatibility with existing running workloads; changing the default notebook identity does not retroactively remove those Pods or their mounted credentials. Review any remaining Dask capability separately before enabling that feature.

## Storage and Quick Start

The persistent home and existing PVC/NFS bindings must be preserved. Quick Start leaves optional network mounts unchecked. Advanced options expose only approved PVC-backed presets, with their existing role checks. There is no freeform server/export/mount-path input.

NFS remains on the existing cluster-network address. Do not substitute an internal TrueNAS management address or an unverified new filer export. Selected NFS mounts can still delay startup during an outage; making them optional does not make an attached NFS volume nonblocking. Keep archives and research data after workspace removal.

## Directory lookup and startup

The released `DirectoryIdentityCache` runs the existing blocking LDAP UID/GID lookup off the Hub event loop. Positive entries have a five-minute TTL and a 256-entry LRU bound; concurrent requests for one username share a lookup. Missing users and errors are not cached. Existing UID/GID fallback and mount behavior remain unchanged. This cache never supplies group, entitlement or canonical-person authority.

Images and the continuous pre-puller must use the same approved digest. Prefer `IfNotPresent` for immutable images; do not pre-start GPU allocations to hide cold-pull latency. Measure policy, Pod creation, scheduling, volume, image, container and Jupyter readiness separately. Existing startup targets and actual measurements belong in the qualification ledger rather than a duplicated limit table here.

## Deployment and verification

The values file imports released Hub helpers. Build and verify the matching Hub wheel/image before applying it. Older images lack those modules and cannot evaluate the configuration. Preserve the actual mounted config, original native custody, Hub database/PVCs, neutral account bindings and existing user Pods during promotion. Review the rendered delta; do not apply a broad Helm/Fleet reconciliation as an isolated-fix shortcut.

Focused source checks live in `tests/compute_policy/test_spawn_directory_lookup.py`; package checks live with `cps-compute-hub`. Render this directory with the pinned chart/Kustomize and verify the tokenless default ServiceAccount. Source tests and local image checks do not establish live GPU isolation, end-user desktop acceptance or production readiness.

SSH instructions are in [the gateway guide](../../../../../../docs/jupyterhub/jupyterhub-ssh-access.md). `/hub/ssh` is not a key-registration page. The mounted notebook guide must not advertise unsupported controls or MIG sharing.
