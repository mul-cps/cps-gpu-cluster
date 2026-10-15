# CIT through Dex: refresh-token configuration

Status: source and offline render qualified; not deployed or refreshed live.

The CIT Hub requests tokens from Dex, and Dex's `cit` connector requests tokens
from CIT Authentik. Both exchanges need an explicit offline-access request.
Dex's downstream scope does not automatically append the upstream OIDC scope:
Dex2.44.0 constructs upstream scopes from `config.scopes` and separately adds
its consent/offline request options. The connector change preserves profile and
email defaults and adds only offline_access; OpenID is added by Dex. Existing
client IDs, secret references, redirect URIs and group-claim setting remain.
[Dex tokens](https://dexidp.io/docs/configuration/tokens/),
[Dex 2.44.0 OIDC source](https://github.com/dexidp/dex/blob/v2.44.0/connector/oidc/oidc.go)

The corresponding Hub scope change is in the CIT teaching-platform repository,
`bundles/20-jupyterhub/values/jupyterhub-values.yaml`, with a scope-only live delta
and acceptance procedure in `docs/auth/oauth-refresh.md`. OAuthenticator requires
encrypted auth state to persist its refresh token, and requires login if it
cannot retrieve fresh authentication. Preserve its normal auth refresh checks.
[OAuthenticator refresh](https://oauthenticator.readthedocs.io/en/latest/how-to/refresh.html)

## Existing Authentik client: separately reviewed prerequisite

Metadata-only readback on2026-10-15 identified CIT provider3, named
`Provider for Dex (Rancher broker)`, for the exact existing confidential client
`qlPmVf0I9embINVWrDqSjWIjoD6HrTwx6TbEUYXq` and issuer
`https://auth.dshl.unileoben.ac.at/application/o/dex-rancher-broker/`.
It currently selects only OpenID/profile/email mappings. Its existing default
OpenID offline-access mapping is available but not selected. Authentik2025.12.4
has no provider model grant-type field to toggle; refresh grants are supported.
The observed validity settings remain hours1 for access and days30 for refresh.

Root must freshly GET `/api/v3/providers/oauth2/3/`, verify the same client and
all existing metadata, then use its supported PATCH endpoint to append only the
existing offline mapping to property_mappings. The observed desired list is:

```json
{"property_mappings":[
  "dbaff8c9-4583-453a-9d31-6baf754a5a05",
  "87d942a1-ec12-480c-8ba5-241b37b68bbc",
  "263e8a21-bb38-430f-8c05-05b56ece6aae",
  "1a1136f0-a2c9-41de-90c3-cf94c58c69fa"
]}
```

These are observed mapping identities, not a live capture or executable patch.
Recheck that the first three exactly match the current selection and the last
is the existing default mapping with scope_name offline_access. If anything
changed, stop for review. Preserve every other provider field, all policy/flow
bindings, client secret, redirect URI and token-validity settings; reread the
provider afterward and audit the actor/outcome. No provider update was executed.
Authentik requires both the request scope and provider mapping for refresh-token
issuance. [Authentik OAuth provider](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/)

The `cps` upstream connector/provider47 is unchanged and has not been qualified
by this change. Verify its own offline scope/mapping before claiming the CPS
connector route refreshes. Do not copy the CIT provider IDs to CPS.

## Acceptance and rollback

Activate only through reviewed configuration controls, accounting for Fleet's
automatic deployment. After both upstream/provider and downstream/Hub changes,
use a fresh controlled login/consent; existing auth state has no retroactive
refresh token. Inspect presence/expiry metadata without recording token values.
Prove real OAuthenticator renewal and rotation with unchanged identity/scopes,
then confirm revoked or rejected refresh still denies access and requires login.
No TTL extension, auth-refresh disablement or auth-state overwrite is a fix.

The source checks and Helm rendering only prove that the two requested scope
lists reach their chart-generated configuration. They are not real refresh,
revocation, all-user migration or production acceptance. Rollback restores only
the two scope changes and any separately approved mapping addition using their
exact captured preimages; it does not rotate credentials or erase user state.
