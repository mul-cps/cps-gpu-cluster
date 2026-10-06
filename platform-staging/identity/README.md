# University identity transition — inactive qualification candidate

Status: prepared / not deployed. Existing CPS and CIT Dex connectors, Hub
usernames, home directories, groups and admin flags remain authoritative during
migration. Optional email verification remains optional. Email is not the
primary university linkage key.

## ICT client registration request

Register one dedicated university Keycloak OIDC client for Dex:

- Issuer: `https://login.unileoben.ac.at/realms/unileoben`
- Exact redirect URI: `https://dex.dshl.unileoben.ac.at/callback`
- Standard authorization code flow, S256 PKCE and TLS.
- Scopes: `openid profile email`; no privileged group or role mapping.
- A stable subject for this single relying party, with documented public/pairwise
  subject configuration and lifecycle/reassignment policy.
- Deliver credentials through an approved secret channel, then SOPS; never Git
  plaintext or a browser client.

The existing Authentik university client rejects the Dex callback with
`Invalid parameter: redirect_uri` (HTTP 400 even with S256). It cannot safely be
reused without registration. Do not enable a placeholder connector.

Keep connector ID `university` stable. Preserve `cps` and `cit` connector IDs.
Use Dex's authenticated `federated:id` scope to retrieve `federated_claims`
(`connector_id`, `user_id`); downstream Dex `sub` is not the university subject.
The connector's upstream issuer is operator-pinned provenance; these claims do
not carry the upstream issuer. Qualify the complete trusted connector path.

## Reviewed aliases

Run `scripts/compute-platform/link-identity-subjects.py` on a private reviewed
export containing `hub`, unchanged `username`, exact `issuer`, exact `subject`,
`upstreamVerified: true`, `reviewed: true`, and optionally an existing `personId`.
Output is private, mode 0600, outside Git and never overwrites a file. Matching
emails or names does not link people. Subjects are case-sensitive.

Inspect Authentik's native source identifier derivation before treating stored
connection identifiers as raw upstream subjects. Compare both existing source
clients' subject modes; pairwise subjects can differ. Resolve differences in an
explicit reviewed migration. The confirmed legacy account names are CPS
`bjoern` and CIT `akadmin`; their equivalence is not sufficient subject evidence.

## Permission migration gates

1. Back up matching Hub and console database/application versions. Preserve the
   read-only inventory of all existing users, groups, admin flags and storage
   associations; inventory alone is not a permission import.
2. Import reviewed grants into the owning CPS/CIT console, with actor/provenance,
   expiry, audit and ownership. Preserve legacy access while reviewing mappings.
   Never infer new roles from generic `admin`, `sudo` or GPU group names.
3. Qualify console-to-Hub reconciliation with narrowly scoped service access,
   course-scoped instructor operations and expiry. Seed before relinquishing
   authenticator group ownership.
4. Install a released `cps_compute.federation.university_post_auth_hook` on both
   Hubs, with private subject-to-existing-username maps. Its disabled default
   performs no change. Enabled configuration must use TLS-verified pinned Dex
   userdata, no redirects, header token transport, `oauth_user` auth state,
   `manage_groups: false`, `manage_roles: false`, and empty `admin_groups`.
   Request `federated:id` on legacy routes too; missing claims fail closed.
5. Test both old login routes before adding the university route. Test existing
   names/homes/admin grants, unknown subjects, login survival of local grants,
   expiry and overlapping cross-Hub allowances without duplicate reservations.
6. Only after these gates enable the registered University connector and promote
   the same qualified artifacts through GitOps. Keep rollback backups and old
   routes. Never switch usernames to university `preferred_username`.

Compute entitlement authority belongs to the shared policy service, administered
through separate CPS/CIT consoles. Authentik can retain infrastructure access
and local account lifecycle. Hub groups are synchronized enforcement views.

The adapter and compiler are source-tested; no direct University route, group
ownership transition or global subject mapping is activated by this candidate.
