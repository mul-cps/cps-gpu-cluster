# Rancher + Authentik SSO: migration from SAML to Generic OIDC (completed 2026-07-07)

Status: **superseded 2026-07-23.** Rancher no longer authenticates
against CPS Authentik directly — it now goes through a Dex broker
(`dex.dshl.unileoben.ac.at`), which fans out to both CPS and CIT
Authentik. See `docs/dex-idp-broker.md` for the current setup; this
document is kept for history (the SAML→OIDC migration this file
originally covered, and the direct-to-CPS-Authentik period that followed
it, both still explain real field-name/config gotchas relevant to the
`AuthConfig` CRD in general).

The SAML integration described in earlier revisions of this document has
been retired. The direct-to-CPS-Authentik Generic OIDC setup described
below was live from 2026-07-07 to 2026-07-23.

## Summary

Rancher's SAML integration (`adfs` AuthConfig) was found broken in
production on 2026-07-07: both the git-committed and live `spCert` had a
corrupted trailing character, and Rancher was continuously logging
`SAML: failed to parse PEM block containing the private key, requeuing`.
The same manifest also committed the SP RSA private key in plaintext — a
live credential exposure independent of the corruption bug.

Rather than repair and continue maintaining SAML's cert/key lifecycle,
Rancher was migrated to **Generic OIDC** against the same Authentik
instance, reusing the pattern already proven for JupyterHub's OAuth
integration. This is a **cutover**, not an addition — Rancher only supports
one active external auth provider at a time, alongside `local`.

## What's live now

| AuthConfig | type | enabled | Notes |
|---|---|---|---|
| `local` | `localConfig` | **true** | Always active; built-in Rancher admin fallback. Never disabled at any point during this migration. |
| `genericoidc` | `genericOIDCConfig` | **true** | **The active external provider.** Config lives at `cluster-maintenance/clusters/cit-cps-gpu/rancher/genericoidc.yaml`. As of 2026-07-23 this directory is Fleet-managed like the rest of the repo — the "no `fleet.yaml`, applied by hand" exception documented here previously no longer applies. `clientSecret` is SOPS-encrypted (`rancher/oidc-sopssecret.yaml`) and patched into the live `AuthConfig` object by an in-cluster Helm-hook Job (`rancher/oidc-sync-job.yaml`), since the `AuthConfig` CRD has no `secretKeyRef`-style field. See `docs/sops-secrets-migration.md` for the full mechanism and rationale. |
| `adfs` | — | deleted | The live `AuthConfig` object was deleted from the cluster once OIDC login was confirmed working. Its manifest (`saml.yaml`) was removed from git in the same change. |

## Field-name pitfalls hit during setup (useful if this is ever redone)

Rancher's `AuthConfig` CRD has no structural schema
(`x-kubernetes-preserve-unknown-fields`), so a wrong field name is silently
accepted and just... does nothing, or does something subtly wrong. Verified
against `pkg/apis/management.cattle.io/v3/authn_types.go`
(`OIDCConfig`/`GenericOIDCConfig` structs):

- `rancherUrl` (lowercase `url`), **not** `rancherURL`. This field is
  `required,notnullable` — leaving it effectively unset (via the wrong key)
  produced a Go nil-formatting bug in Rancher's post-login redirect handling:
  the browser landed on a URL literally containing `%!s(<nil>)`.
- A separate `rancherApiHost` field is also required (base URL for reaching
  Rancher through the web) — distinct from `rancherUrl`.
- `jwksUrl`, not `jwksEndpoint`.
- `scope` is a **single space-delimited string** (`"openid profile email groups"`),
  not a YAML list under `scopes`.
- `endSessionEndpoint`, not `logoutEndpoint`.
- There is no `displayNameField`/`userNameField`/`uidField`/`groupsField` —
  those are SAML-only field names left over from copying `saml.yaml`'s shape.
  The OIDC equivalents are `nameClaim`, `emailClaim`, `groupsClaim` (all
  optional; defaults already match `name`/`email`/`groups`).

**Authentik-side gotcha**: the OIDC provider had an **Encryption Key**
configured, which made Authentik issue encrypted ID tokens (JWE) instead of
plain signed JWTs (JWS). Rancher's OIDC library only understands signed
tokens — it tried to unmarshal the encrypted payload as JSON claims and
failed with `oidc: failed to unmarshal claims: invalid character '¨'...`.
This is a known pattern affecting multiple OIDC clients against Authentik
(oauth2-proxy, headscale, wg-portal, Vikunja hit the same bug). Fix: leave
**Encryption Key** unset/disabled on the provider.

**Signing keypair is shared**: Authentik's `rancher-saml-key` signing
keypair is used by *both* the (now-retired) SAML provider and the OIDC
provider (for ID token signing / JWKS). When retiring the SAML application
in Authentik, only the SAML application/provider object was removed — the
`rancher-saml-key` signing keypair itself was left intact, since removing
or rotating it would have broken the OIDC login too.

## Secondary secret exposures found and fixed during this work

While researching the SAML break, two additional live plaintext secrets
were found and cleaned up (see `docs/troubleshooting.md` for the dated
entry):

- `bootstrap-cluster/ansible/group_vars/all.yml` had a `rancher_oidc`
  variable block with a plaintext `client_secret` from an earlier, abandoned
  2025 OIDC attempt (endpoints matched the live Authentik provider exactly,
  so this was very likely the *current* live credential, not a stale one —
  it should be rotated in Authentik regardless of git cleanup) and a weak
  hardcoded `rancher_bootstrap_password: "admin"`. Both removed from git;
  `rancher_bootstrap_password` now generates a random value per Ansible run
  instead of defaulting to a fixed weak value.
- The corresponding `bootstrap-cluster/ansible/playbooks/05-rancher.yml`
  task templated an AuthConfig under the **wrong name entirely**
  (`oidc`/`oidcConfig`, Rancher's legacy Keycloak-oriented provider) instead
  of `genericoidc`/`genericOIDCConfig` — almost certainly why that original
  attempt was recorded as "broken" with no further explanation. The task was
  removed; the playbook now just prints a reminder to apply
  `genericoidc.yaml` by hand post-bootstrap.

## Local users are not auto-linked to OIDC identities

Rancher does **not** match local and external-provider users by username.
Local auth (`local` AuthConfig) and `genericoidc` each produce distinct
Principals; a Rancher `User` object is bound to whichever principal it was
created from. Rancher's dashboard has no self-service "link my external
identity" option for local users -- the only automatic linking Rancher does
is a one-time side effect of *Rancher's own UI* "enable provider" flow,
applying only to whichever local user is logged in and clicks that button
at the moment a provider is enabled. Since `genericoidc` was enabled here
via `kubectl patch` rather than through the UI, this did not happen for
anyone.

Practical implication: existing local admin accounts (`admin`, `bellensohn`,
`acatic`, `mantenreiter`, `cpsadmin`, `mlackner`) remain fully separate from
their OIDC identities. The supported way to grant OIDC users permissions is
binding Rancher roles (Global Permissions, or a Cluster/Project's Members
tab) to **Authentik group names** directly -- `groupsClaim: "groups"` is
already set in `genericoidc.yaml`, so any group present in a user's ID
token automatically gets a Rancher group Principal, and permissions bound
to that group name apply on every login. `groupSearchEnabled: false` means
Rancher's UI won't autocomplete group names when binding a role -- type the
exact Authentik group name manually. This mirrors JupyterHub's existing
`claim_groups_key`/`admin_groups` pattern.

## Not addressed by this migration

- `jupyterhub/postgresql.yaml`'s plaintext Postgres password is a separate,
  still-open exposure — out of scope here, flagged as a follow-up.
- NetworkPolicy gaps in `cit-auth`/`kai-scheduler`/`longhorn-system` and a
  set of stale ClusterRoleBindings referencing non-existent namespaces
  (old Kubeflow/Slurm/NFS-provisioner attempts) were found during the
  broader security sweep that prompted this work, but are unrelated to
  Rancher auth and were not touched.
