# Architecture review reconciliation — 28 October 2026

The supplied review describes a useful legacy baseline, but it is not a current
production inventory. The application repositories, mounted Secret overlays and
installed image must be considered alongside Fleet source. Findings below are
scoped; source fixes do not imply deployed or end-to-end qualification.

## Findings and present boundary

| Review finding | Reconciled state | Remaining work |
| --- | --- | --- |
| Profile filtering alone permits unauthorized GPU selection | KubeSpawner validates selected slugs; that finding alone does not establish a bypass. The CPS compatibility backport additionally validates final server-owned profiles and rejects freeform GPU/image/NFS overrides before launch side effects. | Complete deployed role/API negative matrix, including CIT. |
| Default notebooks receive Dask management credentials | Future CPS notebooks use `jupyter-notebook` with token automount disabled. A controlled actual launch confirmed no token volume. | Preserve existing research Pods; verify each other runtime and legitimate Dask migration separately. |
| Arbitrary NFS and CPU-to-GPU overrides | Fixed CPS request policy rejects these overrides rather than deriving an unsafe mixed allocation. | Verify approved storage presets and project-specific access across both Hubs. |
| Synchronous LDAP on every spawn | Packaged positive UID/GID cache runs blocking lookup off the event loop; it does not cache permissions or failed lookups. | Measure repeated successful lookups. The bounded launch encountered a five-second directory timeout. |
| Implicit optional NFS on Quick Start | CPS defaults optional mounts off; actual controlled CPU Pod mounted only its home PVC. | Role-specific storage controls and failure behavior. |
| Always-pull/mutable images; wrong pre-pull reference | Source pullers now include supported exact source references, exclude Dask and include the CPU digest. Live image overrides were preserved. | Pin remaining mutable references and align actual production pullers with actual spawn references. |
| Runtime Dask/Slurm installation and unsupported choices | Unsupported legacy choices are filtered from the CPS launch path. | Dedicated supported distributed/batch runtime qualification; do not call hidden legacy features production ready. |
| Arbitrary proxy hosts | Actual CPS mounted notebook configuration now permits only localhost/127.0.0.1/::1. Existing notebook processes were not restarted. | Verify remaining images and CIT configuration. |
| Xpra globally advertised | Capability-gated CIT registration is tested in CIT PR 20, source-only. | Deploy safely and exercise compatible/incompatible image matrix. Rino's restored exclusive MuJoCo desktop already passes bounded CUDA/EGL/Xpra checks. |
| Student queue and custom-image UI mismatch | CPS student-priority selection requires real student membership; unsupported custom overrides are rejected. | Verify actual federated claims, grants and displayed choices for each role. |
| Stale SSH link | `/hub/ssh` returned 404; source guide now points to canonical SSH instructions. | Verify the documented supported gateway flow. |
| Inconsistent culling | Both Hubs have the profile lifetime controller. Independent global cullers remain: CPS 48-hour idle/no max-age; CIT 24-hour idle/24-hour max-age including admins. | Reconcile effective deadlines, warnings and all cullers; a controller protection entry does not override another culler. |
| Private compute application not reviewed | Local compute/admin source and focused package/TLS tests are available; their presence is not complete live functional acceptance. | Deployed ordinary-user workflows, sharing, assignment closure, recovery and release matrix. |

## Fresh checks in this reconciliation

Read-only cluster checks confirmed the CPS Hub is Ready with zero restarts at
image `sha256:f00f8c5b63bdce6348153aab6e11c1fd5cbf638ed1b50ef27bdda346ad202b75`,
using mounted values `cps-fixed-launch-16fa767-20261028`. The notebook account
reports token automount false, and the actual `singleuser` Secret contains the
loopback-only proxy predicate. Gateway and both admin Deployments each report
one ready replica. Rino's `cit-jhub/jupyter-m12113877` is Ready, zero restarts.
Readiness is not an authenticated application integration test.

The prior controlled CPU launch reached Jupyter in **50.37 seconds**. Its
Longhorn attachment took about 25 seconds; image retrieval took 381 ms. This
sample supports prioritizing storage attachment and directory latency over
claiming image pre-pulling will remove the measured delay. It is not a p95 or
burst result. See the [rollout receipt](../../qualification-artifacts/fixed-launch-rollout-20261028/README.md).

## Production gate correction

The new managed selected-node installation framework is an optional replacement
lane, not independently an original production requirement. Its incomplete
assembly must not automatically block the existing v3 coordinator. Conversely,
existing v3 code is not proof that the deployed configuration covers every
required device, cross-Hub reservation or lifecycle case. Establish that coverage
from the actual deployment and retained qualification evidence first.

Keep the original gates: backend authorization and canonical identity, measured
GPU cap/peer/restart/import behavior for the deployed tuple, cross-Hub accounting,
shared access revocation, notebook snapshots/results, scheduling/reclaim and
cleanup, measured startup bursts, matching restore, and a reviewed release.
Do not repeat already valid hardware tests without a changed tuple or an
identified coverage gap. Hub 6 and deferred university federation/Moodle are
not prerequisites for fixing or qualifying those paths.

## Controlled current-group lifecycle check

The existing CPS `shared-gpu-lab` workspace was started through the deployed
Hub API at the fixed `interactive-shared-5` profile. Hub readiness and a real
CUDA allocation passed: one A100 was visible, the reported memory ceiling was
5,368,709,120 bytes, and the GPU tensor sum returned 65,536. This exercises the
current deployed group path; it does not extend the retained isolation scope
to other devices or profiles.

This single launch took about 169 seconds: approximately 52 seconds before Pod
creation, 100 seconds from creation to scheduling, and 17 seconds to readiness.
The Gateway prepare diagnostic reported 72.943 seconds, including 26.760 seconds
in registered readiness and 31.798 seconds in enrollment publication. These
measurements overlap the scheduling interval and must not be added to it. They
identify coordinator waits as a concrete optimization target; this is not a
p95 or burst measurement.

The controlled Pod UID `4586fa27-c0d0-4615-a881-46e490b3bb75` was checked before
stopping through Hub REST (HTTP 204). A fresh Kubernetes read found the Pod
absent and the reservation API returned `active: false`, `attempt: null`. The
original Aditya, Gottam, Muslim and Rino Pod UIDs remained unchanged, all with
zero restarts. No candidate archive image was deployed during this check.
