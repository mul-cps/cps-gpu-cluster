# CPS-only qualification Hub handover

`hub_transition.py` derives inert forward and inverse artifacts for the CPS Hub.
It first validates the exact prospective Gateway plan and Root contract. It
creates a new immutable native configuration, an owning Hub Secret CAS and a
full-spec Deployment CAS. It makes no Kubernetes, credential or GPU calls.

Both qualification targets belong to CPS. CIT is deliberately absent from the
mutation plan: the released qualification installer requires nonempty source-owned
scopes and cannot install an empty CIT qualification deployment. No CIT Hub
configuration, Secret, Deployment or personal CPU profile is changed.

The planner projects the two Source-approved profiles, owners, scopes, writable
PVCs and read-only mounts. Its `profiles` list contains only qualification profiles:
this is the neutral-account adapter's capability list, not the ordinary personal
profile list. The actual released qualification installer validates those projected
capabilities in the CPU test. Personal behavior remains chained through the
released adapter and original pre-spawn hook.

The original CPS hook must match reviewed SHA256
`bd3a50f7e581ebf84fdcb7527a3cdd50105c81b866a997137d5b4c87a929e1ef`.
That hash was rechecked read-only against the live CPS Hub Secret on 16 October.
Only the installer prefix and the exact AST-identified `_native_pull_owners`
expression change. The private pull wrapper includes the two actual approved
operator owners, so a new neutral owner does not depend on cached private images.
The remaining wrapper source, unrelated Hub YAML, other Secret data and Deployment
fields remain exact. YAML duplicate keys and unreviewed source are rejected.

The inverse recomputes the forward plan, verifies actual immutable configuration
readback and current full Secret/Deployment data/specs, then restores the original
Secret data and Deployment spec using fresh UID/resource-version preconditions.
Unrelated authentication, code, image, volume or ownership drift causes refusal.

The Gateway qualification plan also disables `nativeGroupApprovals` when the
original dynamic reader is enabled and removes only its owning Gateway container's
explicit `CPS_NATIVE_APPROVAL_PUBLISHER_PATH`. The released runtime rejects
qualification with a dynamic group reader, and rejects that heartbeat bootstrap
without its reader. All other environment entries and credentials remain unchanged;
the inverse restores the exact original reader and heartbeat configuration.

All outputs remain disabled, unapplied and unqualified. These are qualification
window artifacts, not a production promotion. Source application adoption and
normal Source operations/restoration, complete fresh released-claim/physical
captures and coordinated application/readback remain required before GPU execution.

Validation on 16 October 2026: **17 Hub tests** passed, including actual released
capability validation, generated async hook execution, full restoration and drift
refusal. The complete pilot suite passed **697 tests and 851 subtests**, with 14
skips. No live configuration was changed and no hardware run is claimed.
