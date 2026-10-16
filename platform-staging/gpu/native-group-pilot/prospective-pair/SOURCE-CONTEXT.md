# Genuine guarded Source context

`source_context.build_context` composes the released application loader, the
Root pair contract, the actual Kubernetes writer observation and the scoped
Gateway reader. It is an operator utility, not a replacement service or API.

Inputs are explicit: `forward` requires the pair policy; `restore` requires a
different current policy. Both require the same independently pinned notebook531
qualification, exact canonical members and 5/20 GiB caps. The frozen migration
helper and all sixteen installed application module hashes are verified.

Before reading application configuration or initializing providers, the loader
observes the pinned Gateway process, both Source Deployments and a complete
namespace PodList. It verifies the actual operator UID/spec, zero console
replicas and absence of other PVC writers using `source_maintenance.verify_freeze`.
Root's fresh review must independently attest service-token custody and exclusion
of alternate starts. Kubernetes reads cannot prove that custody by themselves.

Only existing source-owned local databases/configuration and exact captured API
endpoints are accepted. Moodle must be disabled. The real `CourseServiceApp` is
constructed without listening or creating the workflow runtime. A second freeze
check follows construction. Every registration callback rechecks the freeze and
uses the actual reader, restricted to the selected workspace. No cached fallback.

The caller must keep the returned application alive (retained in `APPS`) until
the operation finishes, then close its provider. Failed post-construction checks
also leave the application retained for explicit cleanup. This module never
acquires the freeze, scales frontends, edits grants, starts/stops servers or
releases the freeze.

CPU tests use real application/provider construction with temporary existing
SQLite/server configuration and synthetic Kubernetes observations. They do not
constitute live Source handover or GPU isolation qualification. Live execution
still requires the observer permissions, fresh Root review, actual freeze and
coordinated Gateway/Hub/Node transition.
