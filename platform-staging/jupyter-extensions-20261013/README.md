# Jupyter extension packages and current admin UI

Delivery: 2026-10-13. See [receipt.json](receipt.json) for source revisions,
wheel checksums, immutable image references and Ready Pod receipts.

The revised application UI is deployed to both `cps-admin` and `cit-admin`.
Only the container image changed. Both Deployments retained their UID, one
replica, Recreate strategy, SQLite volume, configuration and credentials. The
CPS ingress serves the verified new bundle; CIT's internal HTTP endpoint serves
the same verified bundle. Unauthenticated CPS protected API requests still
redirect to login. Real browser OAuth remains a separate qualification gate.

The previous image inherited an `e368055` OCI label, but all 46 installed backend
Python files actually match `901a885`. The new full application wheel preserves
those exact bytes and every installed dependency version. It owns all three UI
static assets through RECORD; no loose-file overlay or database migration was
used. Both running Pods were checked again after rollout. Existing revision-
guarded GPU approvals, exact workspace grants and stopped-workspace profile
changes remain supported; backend readbacks determine availability.

`admin-values.yaml` is an image-only overlay for the existing reviewed console
runtime values. Do not deploy it alone, or merge/promote unrelated Fleet values.
The currently deployed admin image is pinned by digest in the overlay.

The compute application now builds three co-released distributions:
`cps-compute` (lean SDK with explicit runtime extras), `cps-compute-hub`
(registered `cps-kubernetes` Spawner and typed operator configuration), and
`cps-compute-jupyterlab` (sole owner of the prebuilt Lab extension). Gateway and
Hub qualification images are published, but not deployed. Notebook consumers
require the separate Lab owner, runner, RTC and Hera 7.1.0 in a hash-pinned
offline dependency closure. The ComfyUI proxy package owns its nonprivileged
launcher; no duplicate copied shell launcher remains.

Both Lab 4.5.7 and 4.6.4 passed the full thirteen-check installed-bundle browser
probe. The actual RTC-enabled notebook environment passed too. Chromium needed
localhost-only permission for intercepted local WebSockets; no production
browser/server security setting changed. The updated notebook closure has 112
pinned packages and passes the runtime verifier, including ordinary Hera
template rendering. Fixture base digests are not production release inputs.

Canonical application instructions:

- [Compute package guide](https://github.com/mul-cps/cps-compute/blob/feat/modular-jupyter-extensions-20261013/docs/extension-packaging.md)
- [Admin UI source](https://github.com/mul-cps/e2x-course-hub/tree/deploy/ui-settings-20261013)
- [Notebook consumers](https://github.com/mul-cps/cps-jupyter-notebook/tree/feat/modular-extension-consumers-20261013)
- [Passing distribution CI](https://github.com/mul-cps/cps-compute/actions/runs/38449234944)

Rollback uses the previous admin image digest from the receipt, with the same
application/database versions. Preserve the current deployment UID and test the
current image before replacing only the image field; do not replace the whole
Deployment or delete data. This rollout made no schema changes.

This is not production qualification of the full platform. Remaining gates
include package-image migration of Hub/gateway/notebooks, existing neutral-
account ownership migration, two-visitor Hub OAuth/RTC, start/stop/restore,
concurrent GPU-cap enforcement and scheduling/load qualification. No GPU driver,
MIG setting, access policy, email verification requirement or storage path was
changed. Stable production release tags and all notebook image variants remain
subject to those gates.
