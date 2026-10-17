# Captured binder deployment source

These four sanitized resources reflect the verified 17 October live image-only
adoption. They contain no Secret values, API-generated identities, status or
Service IP allocations. The native Coordinator flag is explicitly false.

This directory is staging, outside Fleet's reconciled production path. It does
not assert production promotion. During release integration, make the independent
binder resource set and `binder.service.enabled: false` part of the same reviewed
GitOps change; retain every other actual KAI Config field. The merge-patch document
expresses only that Config delta. Never replace the complete Config with it or
apply the resource list over an operator-owned binder before the guarded ownership
handover in the parent README.

The namespace-local `cps-native-kai-image-pull` Secret must already contain a
reviewed pull credential for GHCR. Its contents are intentionally absent here.
Existing ServiceAccount UIDs must be preserved because the protected Coordinator
will pin them; use in-place reconciliation, never delete/recreate these accounts.

Before promotion, refresh the live preimages, qualify the signed native bridge
and add its reviewed token/CA/config fragments. The ordinary CPU Job gate proves
only the explicitly disabled-bridge configuration captured here. Rollback and
operator ownership recovery are described in the parent handover procedure.
