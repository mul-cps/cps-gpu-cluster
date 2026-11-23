# Current Gateway and backup render

This Kustomize package renders the production gateway and the scheduled
four-database backup as observed on 2026-11-23. The gateway reads the existing
protected runtime Secret. The Secret payload is managed separately.

The backup uses the existing pinned runner and records the authoritative
gateway image and policy hash in every snapshot manifest. It validates the
four approved SQLite schemas before publishing the snapshot. The content-addressed
ConfigMap is immutable. A schema change requires a new backup script pin and a
one-off qualification job before updating the CronJob.

`kubectl kustomize .` renders the package. The Deployment and CronJob specs
and ConfigMap data were compared directly with the live resources. Run that
comparison again before promoting this package to a GitOps reconciler.
