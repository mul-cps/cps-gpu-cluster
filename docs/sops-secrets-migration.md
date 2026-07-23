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
| Postgres password | postgresql.yaml (plaintext) + values.yaml db_url (duplicate) | postgres-sopssecret.yaml | done, rotated |
| LDAP bind-service-account password | values.yaml extraConfig/02-profiles get_ldap_info() (plaintext `LDAP_PASSWORD = 'ldapservice'`) | ldap-sopssecret.yaml | done, not rotated (value reused as-is) |
| JupyterHub proxy auth token | values.yaml `proxy.secretToken` (placeholder literal `GENERATE_WITH_openssl_rand_-hex_32`, never a real secret) | proxy-sopssecret.yaml | done |

### Note on the proxy auth token mechanism

Unlike the other three secrets above, `proxy.secretToken` (aka
`hub.config.ConfigurableHTTPProxy.auth_token`) has no existing-Secret
reference field in jupyterhub chart 4.3.1 — the chart only accepts it as
a literal in values, or auto-generates one into its own chart-managed hub
Secret. `hub.existingSecret` would swap that whole secret and require
re-implementing every other chart-managed key (cookie_secret,
CryptKeeper.keys, etc.), which is out of scope here. Instead, both
`hub.extraEnv` and `proxy.chp.extraEnv` inject `CONFIGPROXY_AUTH_TOKEN`
from the `jupyterhub-proxy-token` Secret (produced by
`proxy-sopssecret.yaml`), appended after the chart's own hardcoded
`CONFIGPROXY_AUTH_TOKEN` entry in both the hub and proxy Deployments.
Verified via `helm template` (chart 4.3.1) that both Deployments render
two `CONFIGPROXY_AUTH_TOKEN` env entries per pod, with our SopsSecret
reference last, consistent with k8s duplicate-env-name last-wins
semantics. This was not confirmed against a live cluster (no kubectl
access during this change) — if the hub and proxy pods ever authenticate
against different tokens, check
`kubectl logs -n jupyterhub deploy/proxy` for auth-token mismatch errors
first.

This was a placeholder being replaced with a real generated value, not a
credential rotation, so it has no rotation-checklist entry below.

## Credential rotation checklist

- [x] JupyterHub Postgres password — rotated 2026-07-23 (was jhub-secure-db-password-2025, plaintext in git)
- [ ] JupyterHub LDAP bind-service-account password — NOT rotated by this migration; the existing `ldapservice` credential value was reused as-is when encrypting into `jupyterhub-ldap-credentials`/`ldap-sopssecret.yaml`. This is a centrally-managed LDAP directory account (`cn=ldapservice,ou=users,dc=ldap,dc=goauthentik,dc=io`), not an app-generated password, so rotation is flagged as a manual follow-up requiring coordination with whoever administers the Authentik/LDAP directory before changing it here.
