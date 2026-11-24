# Current Gateway and backup render

This Kustomize package contains the gateway and the scheduled four-database
backup, based on the production configuration recorded on 2026-11-23.
The gateway reads a protected runtime Secret whose payload is managed separately.

The backup uses the existing pinned runner and records the authoritative
gateway image and policy hash in every snapshot manifest. It validates the
four approved SQLite schemas before publishing the snapshot. The content-addressed
ConfigMap is immutable. A schema change requires a new backup script pin and a
one-off qualification job before updating the CronJob.

`kubectl kustomize .` renders the package. The Deployment and CronJob specs
and ConfigMap data were compared directly with the live resources. Run that
comparison again before promoting this package to a GitOps reconciler.

## RC7 staging

The RC7 staging branch pins the gateway and backup provenance to the same
published OCI image. The content-addressed backup schema accepts both the
incumbent and RC5 through RC7 database layouts. The backup runner image, policy hash
and source claim use the current production pins.

The active gateway runtime and the approval publisher use paired immutable
objects in the `cps-compute` namespace. The staged Secret preserves the
production runtime configuration and leaves GPU batch dispatch disabled.
Its gateway publisher declaration and the staged ConfigMap both identify
the existing Deployment UID and the RC7 image.

Keep the live Fleet GitRepo pinned until the timed traffic handoff,
writer fence and rollback are ready. This Deployment uses `Recreate`.
A direct Fleet revision update would stop its only gateway before
a replacement could serve. Verify the protected references and the live
authority pin again immediately before any cutover.
