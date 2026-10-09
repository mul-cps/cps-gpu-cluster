This overlay pins both administration consoles to the published status and
workspace-readiness image from admin commit
`1e3f6d12c9814325a4f5dc9f0949685c8e060a72`. Add `values.yaml` after the
approved platform chart values. It selects the existing operator-owned
`cps-platform-status` ConfigMap through `consoleStatus.configMapRef`.

The [canonical admin status documentation](https://github.com/mul-cps/e2x-course-hub/blob/1e3f6d12c9814325a4f5dc9f0949685c8e060a72/docs/platform-status.md)
defines the version 1 JSON contract. Root owns the ConfigMap in the chart's
namespace, with `data.status.json`. The chart mounts its directory read-only at
`/platform-status` and sets `CPS_PLATFORM_STATUS_PATH=/platform-status/status.json`.
A directory mount allows ConfigMap updates to reach running consoles.

Root must refresh the assessment and UTC RFC3339 `updatedAt` timestamp ending in
`Z` before 15 minutes elapse. Older records, future timestamps beyond 30 seconds,
missing or invalid JSON, and incomplete `enabled` checks display `unavailable`.
The closed record contains `version`, `state`, `title`, `detail`, `updatedAt`, and
`checks`; states are `qualification`, `limited-pilot`, `enabled`, or `unavailable`.
Each check has `id`, `label`, and `state` (`pending`, `passed`, or `blocked`).

The authenticated `GET /api/platform-status` endpoint rechecks current Hub
administrator authorization. Browser query/body fields cannot select a file,
change checks, or enable sharing. Compute access and Shared workspaces show the
operator's blocker and remaining checks, poll every 20 seconds, and use an
8-second request timeout.

The same image reports a workspace as `running` only after Hub readiness is
confirmed; failed startup retains cleanup guards until shutdown and central
release are confirmed. Offline validation
passed 137 backend tests on host and image, 24 browser tests, production
TypeScript/Vite build, and dependency checks. The live rollout and authenticated
live checks remain pending at this commit.

This display records an operator assessment. Real GPU group-sharing
qualification still requires the actual startup, memory-limit, peer isolation,
restart, cleanup, and cross-Hub gates. The overlay does not enable or qualify
GPU profiles.
