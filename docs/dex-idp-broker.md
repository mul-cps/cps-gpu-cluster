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

## Upstream connector client registrations (2026-07-23)

Both registered via the Authentik API, mirroring each instance's own
existing authorization_flow/invalidation_flow/property_mappings
conventions (verified against each instance's pre-existing providers
before creating these — CPS: `Provider for Rancher OIDC`; CIT:
`Provider for cit-jhub`), both with redirect URI
`https://dex.dshl.unileoben.ac.at/callback` and app slug
`dex-rancher-broker`.

| Instance | Provider pk | client_id | Issuer |
|---|---|---|---|
| CPS (`auth.cps.unileoben.ac.at`) | 47 | `iGjkHeZPoMrpWsw5TZ3RY368DDJa2d8TwOnR1EVS` | `https://auth.cps.unileoben.ac.at/application/o/dex-rancher-broker/` |
| CIT (`auth.dshl.unileoben.ac.at`) | 3 | `qlPmVf0I9embINVWrDqSjWIjoD6HrTwx6TbEUYXq` | `https://auth.dshl.unileoben.ac.at/application/o/dex-rancher-broker/` |

Both issuers' `.well-known/openid-configuration` confirmed live and
resolving correctly. client_secrets are SOPS-encrypted in Task 4's
`SopsSecret`s — never recorded here in plaintext.

The API tokens used to register these (one CPS, one CIT) should be
revoked by the operator now that registration is complete, same handling
discipline as every Authentik token used during the SOPS migration.
