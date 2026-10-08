# Verified identity linkage

Authentik is the authoritative directory for candidate CPS/CIT account mappings. Email verification is mandatory before linkage, by explicit operator decision on 2026-10-05. Administratively protected email fields alone do not satisfy this gate.

Retain the existing Hub username, home directory, PVC and NFS path. Normalize only directory email addresses for comparison. Create a stable canonical person UUID through `scripts/compute-platform/link-identity-emails.py` only after verification and collision review. Store exports and compiled mappings outside Git with mode 0600.

A verification record must identify the exact directory account, normalized address, verification method and time. Evidence must come from a successful controlled email challenge or a trusted upstream assertion whose signature, issuer, audience and verification semantics have been checked. An absent `email_verified` claim is not verified. Changing an email invalidates evidence for the previous address; do not silently relink the person. Preserve an existing person UUID only through reviewed migration.

Review missing addresses, multiple directory accounts using the same address, duplicate Hub accounts, unmatched Hub usernames and conflicting person IDs. Exclude unresolved records from global allowances. Never match display names or infer mappings from equal usernames.

Current CIT directory inspection found no email-verification stage or explicit verification claims. No canonical linkage has been activated. Provision and test verification before importing mappings. Keep local CPU access and independently authorized operations available while linkage is pending.
