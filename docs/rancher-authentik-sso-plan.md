# Rancher + Authentik SSO: current state and OIDC migration plan

Status: **research/planning only — nothing in this document has been applied.**
Date: 2026-07-07. Cluster checked live via `kubectl get authconfig` against the
`cit-cps-gpu` API server (v2.13.3).

## TL;DR

- **Rancher is already connected to Authentik today**, via **SAML** (Rancher's
  generic-SAML "ADFS" provider type), not OIDC. It is live and `enabled: true`.
- **Generic OIDC is supported** by Rancher v2.13.3 and could replace the SAML
  integration, but a previous attempt to configure OIDC on this cluster was
  abandoned as broken (see History below). Recommendation: **keep SAML**
  unless there's a concrete reason (e.g. a feature only OIDC provides) to
  revisit OIDC, and if migrating, treat it as a **cutover**, not a
  parallel-run, for the reason in the next bullet.
- **Rancher cannot run two external providers at once.** Local auth plus
  *one* external provider (SAML or OIDC) is supported; a second external
  provider cannot be active simultaneously. This is unchanged in v2.13.3.

## 1. Is Rancher + Authentik OIDC feasible?

Yes. Rancher v2.13.3 ships a **Generic OIDC** auth provider
(`docs.rancher.com` calls this "Configure Generic OIDC"), which is a
protocol-generic integration (not tied to a named vendor like Okta/AzureAD) —
any spec-compliant OIDC IdP, including Authentik, can be used as the backing
identity provider.

Source: [Configure Generic OIDC — Rancher docs (v2.13)](https://ranchermanager.docs.rancher.com/how-to-guides/new-user-guides/authentication-permissions-and-global-configuration/authentication-config/configure-generic-oidc), mirrored at [SUSE Rancher Manager v2.13 docs](https://documentation.suse.com/cloudnative/rancher-manager/v2.13/en/rancher-admin/users/authn-and-authz/configure-generic-oidc.html).

Rancher v2.13 notes: it no longer stores user tokens for Generic OIDC/Cognito
(tokens are cleaned up on upgrade), and Generic OIDC supports custom claim
mapping for name/email/groups when the IdP doesn't use Rancher's default
claim names — directly relevant to Authentik, which by default emits
`preferred_username` rather than a bare `username` claim (see the JupyterHub
integration below, which already had to set `username_claim`).

Rancher also supports **SAML** as a functionally-equivalent alternative
protocol (its docs describe OIDC and SAML integrations as "functionally
equivalent" for Rancher's purposes) — and that's the protocol this cluster
already uses for Authentik.

## 2. Current live Rancher auth state (checked 2026-07-07)

Rancher tracks *every* possible provider as an always-present `AuthConfig`
resource (one per supported type), regardless of whether it's configured or
enabled — so `kubectl get authconfig` lists ~17 entries
(`activedirectory`, `adfs`, `azuread`, `cognito`, `freeipa`, `genericoidc`,
`github`, `githubapp`, `googleoauth`, `keycloak`, `keycloakoidc`, `local`,
`oidc`, `okta`, `openldap`, `ping`, `shibboleth`). Only the ones actually
filled in and flipped on matter:

| AuthConfig | type | enabled | Notes |
|---|---|---|---|
| `local` | `localConfig` | **true** | Always active; built-in Rancher users (admin fallback). |
| `adfs` | `adfsConfig` | **true** | **This is the live external provider.** Rancher uses its generic-SAML "ADFS" config type for any SAML 2.0 IdP, including Authentik — despite the name, this is not Microsoft ADFS. IdP metadata (`idpMetadataContent`), SP cert/key, and claim field mappings all point at `auth.cps.unileoben.ac.at` (Authentik). |
| `oidc` | `oidcConfig` | false, `management.cattle.io/auth-provider-cleanup: rancher-locked` | Leftover from a prior attempt (see History). Not the "Generic OIDC" provider — this is Rancher's older/Keycloak-style OIDC config type. |
| `genericoidc` | `genericOIDCConfig` | false, same `rancher-locked` annotation | **This is the actual "Generic OIDC" provider** referenced in Rancher's docs. Present but empty/disabled — never successfully configured on this cluster. |
| all others | various | false, unset | Never touched. |

Rancher version confirmed live: `kubectl get settings server-version` →
`v2.13.3`; the `rancher` pod image in `cattle-system` is `rancher/rancher:v2.13.3`,
matching the version assumed in the task.

Config source of truth: `cluster-maintenance/clusters/cit-cps-gpu/rancher/saml.yaml`
(applied by hand — the `rancher/` directory has no `fleet.yaml`, consistent
with `CLAUDE.md`'s note that Rancher itself is a Fleet exception).

### History (from git log on this path)

1. `5c16d55` — Rancher install playbook originally included OIDC config.
2. `6f40dcb` "feat: add Rancher OIDC and SAML authentication configurations" —
   added `oidc.yaml`, `dummy-oidc.yaml`, and `saml.yaml`.
3. `4ecb806` "fix(rancher): remove broken OIDC configuration" — the two OIDC
   manifests were deleted from the repo; only `saml.yaml` remains.

The `rancher-locked` cleanup annotation on both `oidc` and `genericoidc`
live AuthConfigs is Rancher's own bookkeeping for "a provider was configured
and then disabled/cleaned up" — consistent with an OIDC attempt having been
made and rolled back in favor of the SAML/`adfs` config, which is the one
that ended up working and is live today.

**Anyone picking up OIDC again should first find out *why* the original
attempt was called "broken"** (no root cause is recorded in the commit or
in `docs/`) before assuming a fresh Generic OIDC config will succeed where
the old one didn't.

## 3. Can Rancher run two external OAuth/OIDC sources at once?

**No.** Rancher's architecture supports local authentication plus exactly
**one** external provider at a time. Enabling a second external provider
requires disabling/replacing the first — you cannot have, e.g., SAML/Authentik
and Generic OIDC/Authentik (or SAML/Authentik and AzureAD) both active
simultaneously. This has been a long-standing, unresolved limitation.

Source: [rancher/rancher issue #24323 — "Feature Request: enabling multiple authentication methods simultaneously"](https://github.com/rancher/rancher/issues/24323) (open feature request, confirming the limitation persists); corroborated by [Rancher's Configuring Authentication docs](https://ranchermanager.docs.rancher.com/how-to-guides/new-user-guides/authentication-permissions-and-global-configuration/authentication-config), which describe local users coexisting with a single external provider, not multiple.

Practical implication for this cluster: **you could run two separate
Authentik Applications/Providers** (e.g. one SAML, one OIDC) on the Authentik
side without any Authentik-side limitation, but **only one of them could ever
be wired up as Rancher's active external `AuthConfig` at a time** — so
"two Authentik apps for two user populations, both live in Rancher
simultaneously" is not achievable; only one Rancher login path (besides
local) can be enabled at any given moment, no matter how many Authentik-side
providers exist.

## 4. Recommendation

Given that:
- SAML/Authentik is live, working, and already handles group-based access
  (`groupsField`) today,
- a prior OIDC attempt was explicitly rolled back as "broken" with no
  recorded root cause,
- Rancher treats OIDC and SAML as functionally equivalent — migrating buys
  no new capability by itself,

**stay on the current SAML/`adfs` integration.** Only pursue Generic OIDC
if a concrete need arises (e.g. consolidating on OIDC everywhere including
JupyterHub for operational consistency, or a SAML-specific bug/limitation
is hit). If that need arises, follow the plan below as a **replacement**
of SAML, not an addition to it — mirror the JupyterHub `GenericOAuthenticator`
pattern in `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml`
for consistency of claim names (`username_claim: preferred_username`,
`scope: [openid, profile, email, groups]`, `claim_groups_key: groups`).

## 5. If migrating to Generic OIDC anyway: step-by-step plan

### 5.1 Authentik-side setup

1. In Authentik admin, create a **new OAuth2/OpenID Provider** (Applications →
   Providers → Create → "OAuth2/OpenID Provider") dedicated to Rancher —
   do not reuse the JupyterHub provider's client ID/secret.
   - Redirect URI: `https://rancher.dshl.unileoben.ac.at/verify-auth`
     (Rancher's OIDC callback path — confirm exact path in the docs page
     above before configuring, it differs from JupyterHub's `/hub/oauth_callback`).
   - Scopes: `openid`, `profile`, `email`, `groups` (mirrors JupyterHub's
     scope list for consistency).
   - Signing key: reuse Authentik's existing signing certificate (same one
     used for the SAML provider is fine, different protocol).
2. Create a new **Application** in Authentik bound to that provider (e.g.
   "Rancher (OIDC)"), with an appropriate access policy (likely mirroring
   whatever group/policy currently gates the SAML `Rancher` application,
   so the same user population is authorized).
3. Note down: Issuer URL, Authorization/Token/UserInfo/JWKS endpoints,
   Client ID, Client Secret. These map directly to Rancher's `genericoidc`
   AuthConfig fields (`issuer`, `authEndpoint`, `tokenEndpoint`,
   `userInfoEndpoint`, `jwksEndpoint`, `clientId`, `clientSecret`).
4. Claim mapping: Authentik's default `username` claim is not
   `preferred_username` unless a custom scope mapping sets it — confirm
   which claim Authentik emits by default in this Authentik version and
   set Rancher's `userNameField`/`displayNameField`/`groupsField`
   accordingly (this exact mismatch is called out as a solved problem in
   JupyterHub's config, `username_claim: "preferred_username"` — reuse
   that same custom scope mapping if it exists in Authentik already).

### 5.2 Rancher-side configuration

Rancher's `genericoidc` AuthConfig is a `management.cattle.io/v3` CRD (same
kind as the existing `saml.yaml`/`adfs` config), so it can be applied the
same way this repo's `saml.yaml` was — a direct `kubectl apply` against the
live cluster (this path has no `fleet.yaml`; Rancher config is a documented
exception to the "everything goes through Fleet" rule in `CLAUDE.md`).

Fields for `AuthConfig`/`name: genericoidc`, `type: genericOIDCConfig` per
the docs above: `clientId`, `clientSecret`, `issuer`, `authEndpoint`,
`tokenEndpoint`, `userInfoEndpoint`, `jwksEndpoint`, `scopes`,
`displayNameField`, `userNameField`, `userIDField`, `groupsField`,
`rancherURL`, `enabled`. (This is close to, but not identical to, the
deleted `oidc.yaml`'s shape from commit `6f40dcb` — confirm current field
names against the live docs page before writing the manifest, since that
prior config was the one later marked "broken.")

Configuration can be done via the Rancher UI (☰ → Users & Authentication →
Auth Provider → Generic OIDC) or by applying the CRD directly; prefer
applying the CRD and committing it to this repo (as `saml.yaml` is),
keeping secrets out of git the same way `jupyterhub-oauth-secret` is
handled for JupyterHub (a k8s Secret referenced via env var, not a plaintext
value committed to the manifest).

### 5.3 Safe testing procedure (no admin lockout)

Because Rancher only allows one active external provider, switching to
`genericoidc` **disables** the current `adfs` SAML config — this is not an
additive change, it's a cutover. Do not attempt to enable both at once
(Rancher's UI/API itself won't allow it, per §3).

1. **Before touching anything**: confirm at least one **local** Rancher
   admin account exists, has a known-working password, and is not disabled
   (`kubectl get authconfig local -o yaml` already shows `enabled: true` —
   confirm there's also an actual local user with `admin` cluster-role, not
   just the AuthConfig being enabled).
2. Create the Generic OIDC provider/application in Authentik (§5.1) but do
   **not** enable `genericoidc` in Rancher yet.
3. Test the OIDC flow end-to-end *outside* Rancher first if possible (e.g.
   a throwaway OIDC debugger/Postman against Authentik's token endpoint)
   to confirm claims come back as expected before ever pointing Rancher at
   it.
4. Enable `genericoidc` in Rancher (this will disable `adfs`). Immediately
   test login with a **non-admin** test account via the OIDC flow in a
   separate browser/incognito session, while keeping an existing
   authenticated Rancher admin session (SAML-based, from before the switch)
   open in another window — Rancher sessions are typically only invalidated
   on next login, not instantly, so this open session is not guaranteed to
   survive, treat it as a bonus, not the safety net.
5. **Rollback plan**: if OIDC breaks or locks out real users, re-apply
   `saml.yaml` (`kubectl apply -f cluster-maintenance/clusters/cit-cps-gpu/rancher/saml.yaml`)
   to re-enable `adfs` — since local auth (`local`, `enabled: true`) never
   gets disabled by this change, a known-good local admin account (step 1)
   remains a hard fallback throughout, independent of both SAML and OIDC
   state.
6. Only after non-admin login via OIDC is confirmed working, and admin
   access is confirmed to still work either via OIDC or local fallback,
   consider the cutover complete and remove/archive `saml.yaml`.

## 6. Known repo hygiene issue found during this research (out of scope, flagging only)

`cluster-maintenance/clusters/cit-cps-gpu/rancher/saml.yaml` currently commits
the SAML Service Provider's **RSA private key in plaintext** (`spKey:` field).
This mirrors a previously-fixed issue in `jupyterhub/values.yaml` (OAuth
client secret committed, later rotated and moved to a k8s Secret — see that
file's inline comment). The same remediation should be applied here:
rotate the SP key/cert pair in Authentik's SAML provider config, move the
new key to a k8s Secret, and stop committing it in the manifest. This is
**not** addressed by this document and requires no action as part of the
OIDC research task — noted here only so it isn't lost.
