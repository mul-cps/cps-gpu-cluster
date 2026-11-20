# Identity linkage and optional email verification

Authentik remains the authoritative directory for CPS/CIT account mappings. Email verification is available but is not mandatory, following the later operator decision. An explicitly reviewed directory identity can be linked without an email challenge. This does not authorize automatic linkage by matching names or unverified addresses.

Retain the existing Hub username, home directory, PVC and NFS path. Link the exact reviewed directory account to a stable canonical person UUID, recording its directory identifier and provenance. An upstream subject must be paired with its validated issuer; matching display names or usernames is insufficient. University OAuth registration remains deferred to ICT. Store directory exports and compiled mappings outside Git with mode 0600.

Email comparison can identify candidate accounts for review. The email-based tool `scripts/compute-platform/link-identity-emails.py` retains its verification and collision checks; optional verification does not relax that tool's protections. Use the reviewed directory-identity route for accounts without an email challenge.

When email verification is recorded, it must identify the exact directory account, normalized address, verification method and time. Evidence must come from a successful controlled email challenge or a trusted upstream assertion whose signature, issuer, audience and verification semantics have been checked. An absent `email_verified` claim is not verified. Changing an email invalidates evidence for the previous address; do not silently relink the person. Preserve an existing person UUID only through reviewed migration.

Review missing addresses, multiple directory accounts using the same address, duplicate Hub accounts, unmatched Hub usernames and conflicting person IDs. Exclude unresolved records from global allowances. Never match display names or infer mappings from equal usernames.

Reviewed canonical mappings are active for the pilot accounts documented in the [current completion ledger](production-completion-20261013.md). This does not establish linkage for every CPS/CIT account or prove an email-verification claim. Keep unresolved accounts excluded from global allowances, while preserving local CPU access and independently authorized operations.
