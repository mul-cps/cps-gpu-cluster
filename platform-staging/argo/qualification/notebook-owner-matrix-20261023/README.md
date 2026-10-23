# Current notebook and workflow ownership matrix — 23 October 2026

Controlled CPS /v1 calls used ordinary Armin and Mikasa Hub `inherit` credentials,
with no role changes. Both temporary tokens were revoked. Tests ran in the console
container over verified private TLS, using only each student's own credential and
CPS realm. They do not constitute a fresh notebook-kernel SDK or browser GUI run.
The scripts expect the existing trusted CourseServiceApp/asyncio/json/time harness
and an operator-supplied temporary `tokens` dictionary; no credentials are included.

Armin submitted one successful and one deliberately failing CPU notebook. Both
terminal states matched expectations. Every request included selected Python
helper bytes and typed bool/int/float/string/list/dict/null parameters. Executed
assertions passed before the intentional failure. Input artifacts stripped stale
outputs and execution counters and preserved exact helper/parameter data. Logs,
immutable snapshots and successful/failed executed notebooks were downloaded
through authenticated endpoints. Duplicate submissions returned the same UID;
a changed request under the same key was rejected. Test workflows/artifacts remain
retained under normal platform retention, with no active test workload remaining.

Mikasa could not list either workflow and received 403 for inspection, logs, input
and output artifact bytes, and termination. Nine crafted requests received 422
without creating workflows: service account, scheduler, priority, queue metadata,
Pod patch, namespace, unapproved image, resource mismatch and mount override.
The payload command was an approved-image CPU noop; no arbitrary external code
or GPU stress ran. 178 focused Gateway/artifact/submission tests also passed.

The separate shared GPU workspace stayed running and its member reservation
remained active; the same student's CPU batch entitlement remained usable. The
idle deadline was unchanged by these API checks. Equivalent CIT, distributed
launchers and fresh GUI/SDK acceptance retain their separate scope.
