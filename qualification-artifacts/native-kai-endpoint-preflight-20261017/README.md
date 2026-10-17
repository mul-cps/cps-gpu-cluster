# Current-group endpoint preflight, 17 October 2026

Fresh live capture authenticates the current NodeConfiguration and all five qualified workspace scopes. The generated proposal passes the current SDK constructor and closed configuration parser using an offline backend; this is not runtime activation.

All 30 impersonated Gateway service-account permission checks returned yes. No resource RBAC broadening is needed for these calls. The separately required route/authentication grants, token/CA projections and network-policy configuration remain unapplied.

Pinned KAI source and current binder arguments establish the exact reservation template. The current binder still uses the v0.18.1 image tag. The proposal now emits the same immutable reservation image digest as the Coordinator template in both disabled and opt-in flag sets. Merge by replacing the existing flag, never adding a duplicate.

Regression test failed before the source fix and passed after it. Focused verification: 108 tests and 25 subtests pass, with two dependency deprecation warnings. No live rollout, Coordinator operation, test workload or GPU mutation occurred. GPU2 remains cordoned; native KAI lifecycle and production qualification remain open.
