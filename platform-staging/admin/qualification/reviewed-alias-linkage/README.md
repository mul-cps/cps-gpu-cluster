# Reviewed own-account identity handover

The exact user-authorized accounts are CPS `bjoern` and CIT `akadmin`. Email
verification is optional. Their unchanged usernames and storage are preserved.
The console image is source `f5c005ca8b36995c6b4221873d3d0b4d334be3d4`, digest
`sha256:735f891ba008c58a9d3f4d324c22893d13b094dabe7ea39f80c776ffb6c89767`, schema 6.

`capture.py` reads the exact owning Hub accounts through existing console service
credentials, compares the current mounted gateway configuration with its Secret,
and exports only email-free alias UUID/audit references. Optional `--backup` uses
the previously qualified SQLite online backup helper with read-only live data and
reopens the exact copies under the qualified console image. Database bytes,
original Secret contents and rollback evidence stay in an operator-owned 0700
directory outside Git; files are 0600. This probe intentionally requires the
before-seed alias table to be empty. Post-seed snapshots use the same supported
backup CronJobs without the empty-table precondition.

The handover is explicit operator review, not automatic directory claim discovery.
`handover.select_person` preserves any existing UUID reference on either exact
account or its current runtime mapping, including a legacy reference that does
not itself provide membership authority. Conflicting UUIDs abort. Only when both
accounts have no existing UUID does it generate one UUID for a reviewed proposal.
The proposal is not a database record or runtime identity activation.

Seed each owning console through its existing authenticated
`/services/<console>/api/identities` POST endpoint. The authorized operator may
issue a native Hub user token limited to own-name reading and access to that
console for 900 seconds. This does not bypass the unchanged Hub federation
freshness check, console authentication or server-issued CSRF protection. Tokens
are revoked in `finally`; uncertain mint outcomes use exact user/note/scope
cleanup, and the actual Hub must reject the revoked token. The API verifies the current actor is an
owning Hub administrator and the unchanged target account exists. It owns the
review timestamp and truthful Hub audit actor (`bjoern` or `akadmin`). The review
reason separately records Rancher operator `u-vhm9n/cpsadmin`; a caller cannot
spoof `review_actor` or `reviewed_at`. Payloads contain no email, verification
claim, issuer or subject. Re-read all UUID references immediately before mutation.

`handover.compile_runtime` requires independently captured exact source aliases
and matching successful API audit records from both consoles. It adds only
`hubs.cps.canonical_people.bjoern` and `hubs.cit.canonical_people.akadmin` with the
explicit preserved UUID. Wrong owners, foreign aliases, reassignment, duplicate
same-Hub aliases, missing audit proof and mismatched review provenance abort.
The projected audit `id` and `new` fields come from SQLite `target` and `current`.
The evidence is an operator-reviewed protected artifact, not a signature or
proof that an arbitrary supplied JSON document is authentic.

The CLI reads/writes only private files outside the checkout and refuses replacing
existing evidence. It prints mapping/checksum metadata only, never credentials.
It does not apply configuration, restart services, create grants or activate GPU
profiles. Before any gateway config update/restart, coordinate with the personal
Argo owner and recheck the original Secret resourceVersion/hash. Publish a separate
immutable runtime Secret from the freshly captured config, then let the agreed
gateway owner adopt that reference without discarding independently reviewed
Argo/config changes. Confirm both mappings from the actual mounted runtime after
restart, not only the staged Secret or Deployment specification.

## Grant and rollback boundaries

Existing Hub groups are inventory evidence, not automatic global entitlements.
The current Hub API model has no group expiry. The reviewed catalog defines
entitlement bundle shapes but the observed runtime has no reviewed group-to-bundle
assignment/source/expiry table and zero global grants. There is therefore no valid
global grant to migrate. Do not synthesize an admin override or use equal group
names across Hubs to join membership. Identity activation alone yields zero
allowance and no profiles until a separately authoritative grant is provided.
Authenticator-managed groups remain unchanged; federation issuer/subject and
direct Dex integration remain disabled pending ICT review.

Retain matching before-seed snapshots of both schema-6 console databases and the
original runtime Secret/configuration. A runtime rollback must compare the entire
current configuration with the exact activated candidate; independent later
changes require reconciliation. `rollback_runtime` refuses those conflicts.
For a console restore, stop only that console, verify there are no subsequent
records/identity/grant changes, restore its matching snapshot through SQLite's
backup API, reopen schema 6 under the same qualified image, then restart. Do not
erase subsequent audit or operational state to force rollback. The previous
schema-5/image downgrade procedure is separate and intentionally refuses newly
created alias records. Never run the older schema-5 application against schema 6.

## Verification and published partial checkpoint

The compiler/operator's 23 tests include real schema-6 provider/SQLite capture, source audit
matching, UUID preservation/conflicts, unverified-email ineffectiveness, private
evidence permissions, idempotency and concurrent rollback rejection:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/e2x-reviewed-alias-installed \
  python -m unittest discover \
  -s platform-staging/admin/qualification/reviewed-alias-linkage -v
```

The live checkpoint is partial. CPS `bjoern` has one separately reviewed alias for
`d98fbadd-d9a0-4981-8d20-1ab58bb75745`. Its actual authenticated CSRF-protected API
POST returned 200 with actor `bjoern`; the persisted row and successful audit were
re-read. Explicit retries after a lost HTTP receipt preserved that UUID and added
truthful review audit entries. Two earlier CSRF denials are retained in the audit.
No email row was created and no verification claim was made.

CIT `akadmin` remains unlinked. Its otherwise valid narrow native token is rejected
by the unchanged owning Hub before reaching the console: OAuthenticator refresh
contacts Dex userinfo with an expired stored token (expiry
`2026-07-25 08:42:05 UTC`) and fails with HTTP 403. A fresh owning login is required;
operator issuance does not replace federation freshness. No auth_state,
authenticator setting, persistent role, group or credential was modified. All
owned temporary tokens were revoked, including reconciliation of one uncertain
initial mint; the final native inventory contains zero matching tokens.

The original gateway runtime Secret and mounted configuration remain unchanged,
with both `canonical_people` maps empty and zero global grants/workspaces. The
compiler rejects this partial source proof, so no immutable runtime candidate
Secret was created and no gateway configuration/image/restart occurred. The
content-hashed `handover-receipt.json` seals the partial, unqualified handover; it
must not be used as a two-Hub activation receipt. `observed.json` records fresh
post-operation online snapshots, exact row/checksum preservation and qualified
schema-6 reopen/startup checks for both consoles. Private database/Secret evidence
stays outside Git. Root stopped identity work at this bounded checkpoint; grant
migration and later activation remain separate reviewed tasks.
