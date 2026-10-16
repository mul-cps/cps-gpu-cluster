# Fresh operator workspace Source handover

`source_handover.py` adds the fresh CPU-workspace case to the existing operator
migration. It does not manufacture a historical GPU enrollment for a workspace
that has never run one. The legacy Source implementation and its stopped-GPU
migration remain unchanged.

`migrate_fresh(context, review, contract_raw=..., contract_sha256=...)` validates
the same independently pinned Root contract used by Node and Gateway planning.
It requires the exact two CPS notebook531 scopes, disjoint reviewed nonstudent
people, fixed 5/20 profiles and 25 GiB measured pool. The selected record must be
a stopped local CPU workspace with its dedicated neutral owner, original course
and active provisioned storage. The never-enrolled proof identifies the actual
existing ledger UID and contains no invented attempt.

Every fresh stop check uses read-only backend GETs. It validates the full bounded
allocation ledger with the released measured-authority model, requires every
previous allocation to be released, rejects any prior claim for this workspace,
and checks actual Pod absence twice. Neither a timeout nor lease expiry counts
as cleanup.

The adapter requires the exact frozen Source migration file (SHA256
`53c5ed41ad95729a6f4248cf9d3f384c4c5c834b0bbef92134fe25c9ede8f870`).
It executes that migration's unchanged code with a private globals dictionary
replacing only the CPU previous-profile constant, review validator and fresh
stop verifier. It does not modify the frozen file, module globals, genuine
provider/service types, audit writes, Source/Hub ownership checks, repeated
external-freeze checks, grants validation, sibling-course checks, normal HTTP
registration path or storage-preservation checks.

The caller must use the verified configured Source application and current
16-module manifest, provide fresh Root callbacks, and enforce the external writer
freeze. Local Python locks alone do not exclude other application processes.
Required time-bounded operator grants are a separate audited operation: this
helper creates or modifies no grants, performs no Start/Stop, touches no storage
and never releases the freeze. Qualification profiles remain globally disabled.

The result is a stopped migrated record and an audited central registration.
Partial failures retain the frozen migration's explicit failure phase and audit;
there is no automatic rollback over potentially changed records. A reviewed
Source restoration path and coordinated execution are still required before the
hardware test. This helper is not a deployed user-facing API or a production
qualification claim.

CPU tests use the actual LocalCourseProvider, WorkspaceService, ControlStore and
ASGI registration/policy endpoints for fresh5 and fresh20. They cover missing
members/grants, incorrect scope/profile/ceiling, non-admin actor, missing freeze,
live Pod, held reservation, replaced ledger, prior attempt and another active
claim. Both local and central profiles remain unchanged in those denied cases.
