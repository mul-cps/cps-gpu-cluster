# Workspace bootstrap and bounded GPU startup

Status: controlled integration and exclusive CUDA startup passed; production
qualification and formal release remain pending.

The [source-bound report](../../network/workspace-bootstrap-startup-report.json)
records admin `c91a24d` and compute `34d519d`, test counts, artifact digests and
checksums of private execution evidence.

Matching gateway and admin qualification images were built and pushed by digest.
The gateway passed a nonroot source-hash and dependency check. The admin image
passed registry digest/revision verification, UID/GID 10001, dependency checks,
and all 42 admin plus 21 compute Python module hashes in a container with
networking disabled. These are candidate artifacts; SBOM/release qualification
and deployment remain pending.

The admin previously provisioned storage before registration and omitted the
registered principal and policy hash during strict validation. First starts
failed, and roster or ceiling changes could prevent registration refresh.
The corrected order is prospective validation, registration, provisioning,
strict registered validation, then Hub spawn. Prospective validation is an
authenticated read-only API; it cannot authorize a spawn or reserve capacity.
The Hub adapter retains reservation ownership. Bootstrap rejection before a Hub
spawn attempt restores the local stopped state without releasing an unknown
reservation.

The actual admin HTTP client and gateway ASGI routes passed fresh-start,
removed-member restart, course-ceiling restart, source/group rejection and safe
bootstrap-retry scenarios. Central grants, workspace records and reservations
use real SQLite stores. Identity, GPU qualification, Hub spawn and storage are
controlled fixtures. These results do not qualify human login, NAS permissions,
actual Hub spawning, RTC or live cross-Hub reservation release. Deploy the
additive gateway preview endpoint before the matching admin application.

Four trusted, pinned-image exclusive-GPU Pods ran only on GPU2 and GPU3. Each
observed a different physical GPU, completed 60 bounded CUDA heartbeat ticks and
exited successfully. UID-precondition cleanup removed the exact created Pods;
the post-run check found no owned GPU allocations/processes, and idle MPS
servers had zero clients. The recorded user-Pod baseline was unchanged. GPU1
was excluded for active workloads and GPU4 for an unconfirmed MPS query.

This four-device, 1 MiB synthetic probe qualifies bounded placement and CUDA
startup only. It does not qualify shared-memory isolation, teaching reclaim,
protected sessions, whole-pool fairness or representative classroom bursts.
GPU profiles remain disabled until their required acceptance scenarios pass.
