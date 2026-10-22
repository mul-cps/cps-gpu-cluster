# Combined current and binding candidate

Published and verified; not deployed or production qualified.

SDK runtime commit: `53b7174ab48e18f1a0f3bdf7ee0db9cac1c54684`.
Canonical application contract documentation: `895a3b473ba61ba0c273f953c51a4ed27699446d`.

The combined POST carries all seven fields: fence_id, pod, node, bind_request,
binding_state, ack and binding. The Gateway executes the complete existing
current proof once before unchanged binding validation and custody CAS.
Actual Binder ACK and fresh snapshot reads remain; other fence implementations
retain the old two-step interface. Errors/cancellation hold custody without
fallback or Kubernetes Binding. Execution fence remains 60 seconds.

Validation: 723 SDK regression tests, five affected Go package suites,
46 packaging/handover tests and23 endpoint/permission tests passed. Independent
SDK/Go source review CLEAR. Repeated static builds are byte-identical.

Deploy compatible Gateway and explicit POST path permission before enabling
the new Binder. Existing clients and routes remain supported; new clients fail
closed against an older Gateway. Normal shared startup and performance remain
unqualified. This change removes one measured repeated proof pass, not the
separate Node publication delay.
