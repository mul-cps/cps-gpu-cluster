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
| Rancher OIDC (Authentik) clientSecret | `rancher-oidc-secret` Secret in `cattle-system`, applied/patched by hand outside Fleet (`rancher/` had no `fleet.yaml`) | `rancher/oidc-sopssecret.yaml` | done, reused live value (not rotated) — see "Note on the Rancher AuthConfig sync mechanism" below |
| JupyterHub OAuth (Authentik) client_secret | `jupyterhub-oauth-secret` Secret in `jupyterhub`, applied out-of-band outside Fleet | `jupyterhub/oauth-sopssecret.yaml` | done, reused live value (not rotated) — rotating would break the live Authentik-registered client unless updated there too |
| Open WebUI OAuth (Authentik) client_id/client_secret | N/A — no such Secret exists anywhere (git or live); see "Open WebUI OAuth: not migrated" below | N/A | **NOT MIGRATED — genuine gap, flagged for human decision** |

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

### Note on the Rancher AuthConfig sync mechanism

Rancher's `AuthConfig` CRD (`management.cattle.io/v3`) has no
`secretKeyRef`-style field — `clientSecret` must be a literal value on the
object itself, so a `SopsSecret` alone can't reach it. `rancher/` now ships
an `oidc-sync-job.yaml` (ServiceAccount + ClusterRole + ClusterRoleBinding +
Job) that reads the decrypted `rancher-oidc-secret` Secret and
`kubectl patch`es it into the live `genericoidc` AuthConfig.

**Re-run mechanism — Helm hooks, not a bare Job + `apply-once`, and not a
CronJob.** Fleet applies every bundle — even a pure `kustomize.dir: .`
raw-manifest bundle with no `helm:` chart block, like `rancher/` — as a
synthetic Helm release under the hood, so `helm.sh/hook: post-install,
post-upgrade` annotations fire on every Fleet reconcile. This is not a new
pattern in this repo: `system/gpu/gpu-operator/node-labeler.yaml` and
`system/observability/monitoring/crds-and-namespace.yaml` (the latter is
the exact structural match — a pure `kustomize.dir: .` bundle with no
external chart) both already use this mechanism, and `node-labeler.yaml`'s
comments record it as confirmed re-running live on 2026-07-06. The task
brief's suggested `fleet.cattle.io/apply-once: "false"` annotation does not
appear anywhere else in this repo and its semantics for the deployed Fleet
version were not independently verifiable, so the Helm-hook approach (with
in-repo, live-confirmed precedent) was used instead; a CronJob was not
needed once the Helm-hook path was confirmed viable.

The Job's `hook-delete-policy` deliberately omits `hook-succeeded` (uses
`before-hook-creation` only) so the most recent run stays inspectable via
`kubectl get job rancher-oidc-sync -n cattle-system` rather than vanishing
immediately on success — only cleaned up right before the next reconcile's
run. The sync script also refuses to patch (exits 1, Job retries via
`backoffLimit`) if the decrypted `clientSecret` comes back empty, rather
than silently patching an empty string into the live AuthConfig — a shell
`set -eu` without `pipefail` does not catch a failed `kubectl get | base64
-d` pipe on its own.

The `clientSecret` value committed in `oidc-sopssecret.yaml` is the actual
live value retrieved from the running cluster (`kubectl get secret
rancher-oidc-secret -n cattle-system -o jsonpath='{.data.clientSecret}' |
base64 -d`), not a newly generated one — reusing it avoids breaking the
existing Authentik OAuth provider registration. Rotation, if desired, is a
separate follow-up requiring a matching change in Authentik.

### Open WebUI OAuth: not migrated (no live value found)

Task 9 investigated `cluster-maintenance/clusters/cit-cps-gpu/user/llm/open-webui/`
looking for the OAuth client_id/client_secret referenced by
`values.yaml`'s `# Secrets injected via patch` comment. Conclusion: there
is nothing to migrate — no real value exists in git or on the live
cluster.

- `fleet.yaml` has a `targetCustomizations` patch that adds
  `envFrom: [{secretRef: {name: openwebui-oidc}}]` to the `open-webui`
  StatefulSet container, but **no Secret named `openwebui-oidc` (or
  anything else with OAuth creds) exists** in the `openwebui` namespace
  or anywhere else in the cluster — confirmed via `kubectl get secrets -n
  openwebui` (only two Helm release-tracking secrets present) and
  `kubectl get secret -A | grep -i oidc` (no match).
- The live `open-webui-0` StatefulSet pod has no `envFrom` and no
  `OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET` env vars — only
  `WEBUI_URL`, `ENABLE_OAUTH_SIGNUP=true`, `OAUTH_PROVIDER_NAME=authentik`,
  `OAUTH_SCOPES`. Checked the `open-webui-pipelines` and `open-webui-redis`
  Deployments too — no OAuth config on either.
- Git history shows this integration existed once and was **deliberately
  removed**: commit `d49bad0` ("chore: delete Open WebUI OIDC patch...")
  deleted the old `oidc-patch.yaml` that wired a Secret named
  `open-webui-oidc` (namespace `ai-llm`, the pre-restructure layout) into
  the container. The patch present in today's `fleet.yaml` was
  reintroduced later, pointing at a *renamed* Secret (`openwebui-oidc`,
  no hyphen, namespace `openwebui`) that was never created — i.e. the
  patch is aspirational/stale, matching the `values.yaml` comment.
  Key names also differ: the old (deleted) Secret used
  `OIDC_CLIENT_ID`/`OIDC_CLIENT_SECRET`/`OIDC_PROVIDER_URL`; the current
  `extraEnvVars` use the chart's `OAUTH_*` convention instead, so even if
  the old Secret still existed its keys wouldn't match what the
  `envFrom` patch needs downstream.
- **Do not reuse the historical values.** Commit `9f9f8ff` (2025-12-10)
  briefly committed real-looking `OIDC_CLIENT_ID`/`OIDC_CLIENT_SECRET`
  values in plaintext to this Secret before it was deleted. That
  credential has been sitting in git history in plaintext ever since —
  it must be treated as already compromised. Re-encrypting the same
  value into SOPS would be security theater (still recoverable from git
  history) and does not constitute a real migration. **Recommended
  follow-up regardless of the decision below: revoke/rotate that
  specific OAuth client in Authentik.**

**Human decision needed** — three possibilities, pick one and follow up:
1. OAuth login for Open WebUI is *not* actually working right now (most
   likely, given `ENABLE_OAUTH_SIGNUP=true` with no client creds present
   — Authentik would reject any login attempt) and nobody has noticed or
   it's simply not finished being set up. Fix: register a real OAuth
   client in Authentik, create the Secret (name/keys matching what the
   `envFrom` patch and chart expect), then encrypt it into a
   `SopsSecret` following the Task 8 pattern.
2. OAuth was intentionally abandoned for Open WebUI (e.g. reverted to
   built-in auth) and the `fleet.yaml` patch + `values.yaml` comment are
   stale docs debt that should be deleted, not fulfilled.
3. Something else is providing OAuth outside this repo's view (unlikely,
   given the live pod spec has no evidence of it) — worth a quick check
   with whoever manages Authentik client registrations.

No file changes were made to `open-webui/` for this task — no
`oauth-sopssecret.yaml` was created, since there is no genuine value to
put in it.

## Credential rotation checklist

- [x] JupyterHub Postgres password — rotated 2026-07-23 (was jhub-secure-db-password-2025, plaintext in git)
- [ ] JupyterHub LDAP bind-service-account password — NOT rotated by this migration; the existing `ldapservice` credential value was reused as-is when encrypting into `jupyterhub-ldap-credentials`/`ldap-sopssecret.yaml`. This is a centrally-managed LDAP directory account (`cn=ldapservice,ou=users,dc=ldap,dc=goauthentik,dc=io`), not an app-generated password, so rotation is flagged as a manual follow-up requiring coordination with whoever administers the Authentik/LDAP directory before changing it here.
