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
`rancher/oidc-sync-job.yaml`: `secrets-sync-cronjob.yaml` patches the
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

## Live cutover incidents and fixes (2026-07-23)

Three real issues hit during Task 6's actual cutover, all resolved:

1. **Dex served ingress-nginx's fake default cert, not `dshl-wildcard`.**
   Fixed by adding `dex` to the existing Reflector allow-list (see
   `system/networking/wildcard-cert/README.md`'s updated live-reality
   section). `curl -k` masks this failure mode — always verify with a
   plain `curl` or `openssl s_client`.

2. **Helm's post-upgrade hook Job didn't re-fire on a Fleet-triggered
   Helm upgrade with unchanged hook manifest content.** `helm history`
   confirmed a new revision was created for the repoint commit, but
   `rancher-oidc-sync-job`'s Job object's `creationTimestamp` was still
   from the original Task 7 deploy — it never re-ran, leaving the OLD
   Authentik-issued `clientSecret` live in the AuthConfig after the
   repoint (Dex expects its own 64-char shared secret, not Authentik's
   128-char one). Fixed with a direct `kubectl patch authconfig
   genericoidc` using the known Dex secret value as an immediate
   unblock. **Root cause not yet fully understood or fixed** — flagged
   as a follow-up: either Helm hooks need an explicit forcing mechanism
   on Fleet-triggered upgrades, or the sync-Job pattern needs a
   different re-run trigger than relying on "hook fires on every
   upgrade" (which apparently doesn't hold reliably here).

3. **Authentik connector providers (CPS pk 47, CIT pk 3) had no Signing
   Key set, defaulting to HS256** — Dex only accepts RS256 ID tokens
   from upstream connectors (`id_token_signing_alg_values_supported`
   in Dex's own discovery confirms `RS256` only). Fixed by setting a
   Signing Key (Authentik's self-signed certificate) on both providers
   in the Authentik UI.

4. **After fixing #3, a second Authentik gotcha surfaced**: an
   `Encryption Key` set on a provider makes Authentik issue encrypted
   JWE tokens instead of plain signed JWTs — Dex (like Rancher before
   it, see `docs/rancher-authentik-sso-plan.md`'s original SAML→OIDC
   migration notes) can't parse those (`failed to unmarshal claims:
   invalid character ... looking for beginning of value`). Fixed by
   confirming Encryption Key was unset (None) on both providers, Signing
   Key only. **This is the second time this exact Authentik gotcha has
   bitten an OIDC integration in this cluster** — leave Encryption Key
   unset on every Authentik OAuth2 provider used for OIDC (JupyterHub,
   Rancher-direct, Rancher-via-Dex's connectors) unless a specific
   reason requires JWE.

Confirmed working end-to-end: real browser login through Rancher via
Dex, `local` admin fallback still functional, all Fleet bundles healthy
except pre-existing unrelated drift (`knative-serving`, `ollama`).

## `insecureEnableGroups` was missed — groups silently didn't flow (RESOLVED 2026-07-24)

**This was flagged in the very first research pass that led to choosing
Dex** (the pasted analysis at the start of this whole design, before any
implementation): *"Dex can forward groups from an upstream OIDC provider,
but its current documentation warns that OIDC connector groups may
become stale and are disabled by default unless
`insecureEnableGroups` is enabled."* That warning got lost between
design and implementation — the CPS/CIT connector configs in
`system/auth/dex/values.yaml` never set it, and nobody noticed until
JupyterHub's Dex cutover (this doc's earlier section) made group-based
behavior (power-user NFS mounts, admin role) visibly break.

**Symptom**: every login through Dex succeeds, but the issued token has
no `groups` claim at all — confirmed via a temporary
`modify_auth_state_hook` debug log showing Dex's userinfo response
contains only `iss/sub/aud/exp/iat/at_hash/email/email_verified/name/
preferred_username`, despite `scope=openid+profile+email+groups` being
requested. `manage_groups: true` group-sync in JupyterHub then correctly
sees an empty group list and strips the user of every group membership
on every login — including `app_jupyterhub_poweruser`, which silently
disabled the persistent1_shared/scratch NFS mount options in the spawn
form (unrelated to the separate, genuine LDAP-outpost connectivity issue
found at the same time — two independent bugs surfaced by the same
symptom).

**Root cause**: confirmed against `dexidp/dex` source
(`connector/oidc/oidc.go`): `InsecureEnableGroups bool` — "disabled by
default until https://github.com/dexidp/dex/issues/1065 is resolved."
Requesting the `groups` scope alone is not sufficient; the connector
must explicitly opt in.

**Fix**: `insecureEnableGroups: true` added to both the `cps` and `cit`
connector configs. "Insecure" here refers to Dex's own caveat about
potentially-stale group membership on long-lived tokens/sessions, not a
security downgrade of the OIDC flow itself — accepted, since this
cluster already depends on live group-based RBAC working correctly
(Rancher's `groupsClaim`, JupyterHub's `admin_groups`/power-user gating).

**Lesson**: when a design's own research phase flags a specific,
named configuration gotcha, carry that exact flag through to a
verification checklist at implementation time — don't rely on it being
remembered. This is now the second time in this session a config
detail correctly identified during design got silently dropped by
implementation.

## `cit-teaching-platform` JupyterHub cutover (2026-07-24, confirmed live)

Extended the Dex broker to the second, separate JupyterHub instance —
`bjoernellens1/cit-teaching-platform`'s `cit-jupyterhub` Fleet bundle
(namespace `cit-jhub`, ~300 real student/staff users, existing PVCs
named `claim-<username>`), previously talking to CIT Authentik directly.
This is a different repo/tenant from this repo's own JupyterHub instance
(already cut over — see the sections above), sharing only the same
physical cluster and the same Dex broker/connectors.

**Changes**:
- `cps-gpu-cluster` PR #17: added a third Dex `staticClients` entry, id
  `cit-jupyterhub`, redirect URI
  `https://jhub.dshl.unileoben.ac.at/hub/oauth_callback`. New SopsSecret
  `dex-cit-jhub-client` (namespace `dex`); `secrets-sync-cronjob.yaml`
  extended (RBAC `resourceNames`, `get_secret` call, `sed` substitution,
  placeholder grep alternation) to patch this third client's secret into
  the live Dex config, same self-healing pattern as `rancher`/`jupyterhub`.
  No Authentik-side changes needed — reused the existing `cps`/`cit`
  connectors, which already had `insecureEnableGroups: true` set from the
  fix above.
- `cit-teaching-platform` PR #5: `bundles/20-jupyterhub/values/
  jupyterhub-values.yaml`'s `GenericOAuthenticator` repointed from
  `auth.dshl.unileoben.ac.at` (direct CIT Authentik) to
  `dex.dshl.unileoben.ac.at` (Dex); `client_id` → `cit-jupyterhub`;
  `username_claim: preferred_username` and all group-based logic
  (`admin_groups`, `manage_groups`, `pre_spawn_hook`/`profile_list_hook`
  keying off `jhub-admins`/`jhub-powerusers`/`course-*` groups) left
  **unchanged** — Dex passes these claims through unprefixed and
  identically to how CIT Authentik issued them. `jupyterhub-sopssecret.yaml`'s
  `jupyterhub-oauth-secret.client-secret` rotated to match Dex's new
  static-client secret (re-encrypted with the same shared SOPS age key
  used by both repos' operators).

**Verification**: both repos' Fleet GitRepos force-synced
(`forceSyncGeneration`) to pick up the merge immediately rather than
waiting for the default poll interval; confirmed `dex-cit-jhub-client`
SopsSecret `Healthy`; confirmed the `dex-secrets-sync` CronJob patched
the real secret into the live `dex` config Secret (placeholder gone) and
triggered a `dex` Deployment rollout; confirmed the `cit-jhub` `hub` pod
picked up the new secret and Dex endpoints via a rolling restart; **real
browser login through Dex confirmed working** with an existing
`cit-jhub` user — user-confirmed. No separate incident this time: the
`insecureEnableGroups` and TLS-cert lessons from the first cutover were
already in place cluster-wide, so this second instance came up clean.

**Rollback**: documented inline in `cit-teaching-platform`'s
`jupyterhub-values.yaml` (restores the direct-Authentik
`authorize_url`/`token_url`/`userdata_url`/`client_id`/`login_service`
block and notes to restore `jupyterhub-oauth-secret` to the CIT Authentik
"Provider for cit-jhub" (pk 2) client secret).
