# Dex OIDC broker for Rancher

Date: 2026-07-23
Spec: docs/superpowers/specs/2026-07-23-dex-idp-broker-design.md
Plan: docs/superpowers/plans/2026-07-23-dex-idp-broker.md

## Chart

- Chart: `dex/dex` (repo `https://charts.dexidp.io`), version `0.24.1` (app version 2.44.0).
- `config: {}` in the chart's values is a raw passthrough into Dex's own `config.yaml` — `storage: { type: kubernetes, config: { inCluster: true } }` goes directly under `.Values.config.storage`.
- CRDs for `storage: kubernetes`: **not** chart-bundled and **not** a separate manifest to apply — confirmed via the chart's own `templates/rbac.yaml`, which grants `apiGroups: ["apiextensions.k8s.io"], resources: ["customresourcedefinitions"], verbs: ["list", "create"]`. Dex creates its own CRDs at startup when RBAC permits it. `rbac.create: true` and `rbac.createClusterScoped: true` (both chart defaults) are required for this — do not disable them.

## Pre-change baseline (2026-07-23, confirmed live)

- `genericoidc` AuthConfig confirmed live matching git exactly: `enabled: true`, `issuer: https://auth.cps.unileoben.ac.at/application/o/rancher/`, `clientId: oMCe0WAjKAIadGyOHz5ok4Lv5iMxEVlXYGHS36z8`, all endpoints pointing at CPS Authentik directly.
- `local` admin login confirmed working by the operator (2026-07-23), before any Dex-related change.
- `https://rancher.dshl.unileoben.ac.at/v3-public/authProviders` returns both `genericOIDCProvider` and `localProvider`.

This is the exact state Task 6 will diff against and the rollback target if Dex needs to be backed out.
