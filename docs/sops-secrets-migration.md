# SOPS secrets migration

Date: 2026-07-23
Spec: docs/superpowers/specs/2026-07-23-sops-secrets-design.md
Plan: docs/superpowers/plans/2026-07-23-sops-secrets-migration.md

## Shared operator

This repo reuses the `sops-secrets-operator` deployed by the
`cit-teaching-platform` repo into this cluster. This repo never deploys
its own instance.

- Namespace: `sops-system`
- CRD: `sopssecrets.isindir.github.com` (`v1alpha3`)
- Age recipient key: `age1h05qj66un22scwapuhyl76skls7ll235vlu27cjwkk5tpav6sqmsx3zp6a`

Verified live 2026-07-23 via `kubectl get pods -n sops-system` (operator
`Running`), `kubectl get crd sopssecrets.isindir.github.com`, and
`kubectl get secret sops-age-key -n sops-system` (public key matches the
design spec exactly).

## Secrets migrated

| Secret | Old location | New location | Status |
|---|---|---|---|
| Grafana admin password | system/observability/monitoring/values.yaml:51 (plaintext) | system/observability/monitoring/grafana-sopssecret.yaml | done |
