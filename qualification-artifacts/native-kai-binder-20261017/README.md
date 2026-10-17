# KAI binder package and bounded live adoption, 17 October 2026

The pinned native terminal binder is built, published and installed. Its native
Coordinator bridge remains explicitly disabled. This verifies the replacement's
ordinary CPU path, not dynamic GPU placement or the native pre-Bind protocol.

- The static binary passed four affected Go package suites and two byte-identical
  builds. The OCI package preserves the stock runtime configuration and every
  filesystem entry except that binary; installed ELF/hash/help checks passed.
- 45 recipe, OCI and operator-handover checks passed. Independent review checked
  the exact upstream ownership/pruning semantics before live mutation.
- Root paused only the KAI operator, confirmed its Pods absent, transferred the
  four actual binder operands without replacing their UIDs, disabled only the
  stock binder operand and resumed the operator. The same single Recreate binder
  Deployment received the digest-pinned successor with its native bridge off.
- The initial image pull failed because the namespace had no GHCR credential.
  An existing cluster pull credential was verified against the exact manifest,
  scoped to GHCR and provisioned without logging its contents. The replacement
  then became Ready with zero restarts.
- A trusted CPU-only Job requested 100m CPU/128Mi RAM, had no GPU request or API
  token, and had all network traffic denied. Actual KAI placement, BindRequest
  success and process exit zero were observed. The Job, Pod, BindRequest,
  PodGroup and NetworkPolicy are all absent after UID-guarded cleanup.
- Both actual Hubs independently completed verified TLS handshakes to the existing
  Gateway origin with its correct SAN. No TLS proxy or second Gateway was added.

The final receipt records the immutable image, process identity and preserved
invariants. All four personal notebook UIDs and all 117 released ledger claims
were unchanged; GPU2 remains cordoned. No GPU/driver action was performed.

Keep the stock binder operand disabled in future Helm/Fleet configuration:
re-enabling it permits operator ownership takeover. The staged handover helper
and its README specify the reversible sequence. Protected Coordinator activation,
coordinated application-image adoption, signed Hub pending calls and real native
KAI lifecycle/cancellation remain open, as do broader production acceptance gates.
