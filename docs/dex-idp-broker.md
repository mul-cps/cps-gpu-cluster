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

## Deployment (Task 5, 2026-07-23)

Dex deployed as Fleet bundle `dex-idp-broker` (`system/auth/dex/`),
chart `dex/dex` 0.24.1, `storage: kubernetes` (CRDs auto-created by Dex
itself at startup, per its own RBAC — no separate CRD manifest needed).

**Real-world snag**: a genuinely separate, ~6-month-old orphaned Dex
deployment attempt already existed in this cluster — a `ClusterRole`/
`ClusterRoleBinding` named `dex` and `dex.coreos.com` CRDs dated January
2026, referencing a `ServiceAccount` in a namespace (`auth`) that no
longer exists. This blocked our install with a Helm ownership-metadata
error. Confirmed genuinely orphaned (no namespace, no pods referencing
it) and deleted directly rather than worked around. Dex's own startup
gracefully reused the pre-existing CRDs ("already available, skipping
create").

**`staticClients[].secret` does not support Dex's own `$ENV_VAR`
expansion** (connectors do; confirmed against `dexidp/dex` source,
tracked upstream as issue #4212). An initial fix used a Fleet
`targetCustomizations[].patches` JSON-patch — this turned out to be
**invalid Fleet syntax entirely** (confirmed against Fleet's Go source:
`TargetCustomizations` has no `patches` field, only `diff.comparePatches`,
which only affects drift comparison). This is also why Open WebUI's
pre-existing OAuth `envFrom` injection never actually worked (a
pre-existing, separate bug — partially addressed in a follow-up PR
correcting its `clusterSelector`, but the whole `patches:` mechanism it
relied on needs the same redesign, not yet done). See
`docs/troubleshooting.md` for the full incident writeup.

Fixed by reusing the Helm-hook sync-Job pattern already proven live for
`rancher/oidc-sync-job.yaml`: `rancher-secret-sync-job.yaml` patches the
real Rancher static-client secret into the chart-rendered config Secret
after Helm creates it, then restarts the Dex Deployment. Confirmed live:
Job `Complete`, pod `1/1 Running`, config Secret's `staticClients[0].secret`
holds the real value (not the placeholder), and
`https://dex.dshl.unileoben.ac.at/.well-known/openid-configuration`
resolves correctly.

## Rancher repoint (Task 6, 2026-07-23)

`rancher/genericoidc.yaml` now points at Dex instead of CPS Authentik
directly. Endpoints confirmed against Dex's own live discovery document,
not assumed:

| Field | Value |
|---|---|
| `issuer` | `https://dex.dshl.unileoben.ac.at` |
| `authEndpoint` | `https://dex.dshl.unileoben.ac.at/auth` |
| `tokenEndpoint` | `https://dex.dshl.unileoben.ac.at/token` |
| `userInfoEndpoint` | `https://dex.dshl.unileoben.ac.at/userinfo` |
| `jwksUrl` | `https://dex.dshl.unileoben.ac.at/keys` |
| `clientId` | `rancher` (Dex's static client id, not an Authentik client) |

**`endSessionEndpoint` is intentionally omitted** — Dex's discovery
document has no `end_session_endpoint` at all; Dex does not support
RP-initiated logout out of the box. `local` logout and Rancher's own
session invalidation are unaffected; only the "also log out of the
upstream IdP" hop is unavailable. `endSessionEndpoint` is optional on
the `AuthConfig` CRD (only `rancherUrl` is `required,notnullable`).

`rancher/oidc-sopssecret.yaml`'s `clientSecret` now holds Dex's static
client secret (the value generated in Task 4, shared between Dex's
`staticClients` config and this Secret) instead of the old
Authentik-issued one.

### Rollback

Pre-Dex values (CPS Authentik direct) are preserved in git history —
the commit immediately before this repoint. To roll back: revert
`rancher/genericoidc.yaml` and `rancher/oidc-sopssecret.yaml` to that
commit, keeping `rancher/oidc-sync-job.yaml` as-is (it just patches
whatever `clientSecret` the current `SopsSecret` holds, so no change
needed there for either direction).
