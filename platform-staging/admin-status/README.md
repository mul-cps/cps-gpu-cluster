This display overlay selects the existing operator-owned
`cps-platform-status` ConfigMap for both administration consoles. Add
`values.yaml` after the approved platform release values. Application image pins
come from those base release values; a display refresh uses the already
qualified console application and database versions.

The [canonical admin status documentation](https://github.com/mul-cps/e2x-course-hub/blob/1e3f6d12c9814325a4f5dc9f0949685c8e060a72/docs/platform-status.md)
defines the version 1 JSON contract, retained by Source revision `d49dec7c`.
Root owns the ConfigMap in the chart's
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
TypeScript/Vite build, and dependency checks. Both consoles rolled out on their
existing SQLite volume node on 2026-10-09. CPS authenticated status and shipped
UI bundle returned 200; anonymous status redirected to login and POST returned
405. Both mounted status records were verified. CIT human authentication still
requires renewal of the existing upstream login and is not claimed verified.

This display records an operator assessment. Real GPU group-sharing
qualification still requires the actual startup, memory-limit, peer isolation,
restart, cleanup, and cross-Hub gates. The overlay does not enable or qualify
GPU profiles.

The current operator assessment separates approved workspace availability from
broader production qualification. The live access result comes from the
source-owned approval registry and fresh component readiness. The display
record can report a passed bounded behavior while the complete hardware gate
remains pending. Refresh the record from retained evidence; its timestamp alone
does not establish a new qualification result.
