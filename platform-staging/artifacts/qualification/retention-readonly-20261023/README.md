# Current retention read path — 23 October 2026

Two owned Jobs used the live suspended CronJob template in default read-only
mode. The unchanged controller examined 89 objects, skipped 82 and reported
seven errors, with zero deletions or metadata reconciliation. A second bounded
run used Python exception tracing without modifying the controller: all seven
errors were HTTP 404 while obtaining Argo proof. Missing workflow proof preserves
objects and leaves the sweep unsuccessful; this is not permission to delete them.
Diagnostic identifiers are hashed; credentials and response bodies are omitted.

The scheduled template remains on image `7a9caff2…0d15ea` and policy provenance
`d48f6553…511b0`, older than the current Gateway deployment. The current ordinary
workflow TTL is 8,035,200 seconds (93 days), longer than the 90-day output window;
two historical controlled workflows retain 14-day TTLs. This observation does not
establish how the seven missing workflows were removed.

The focused controller/legacy CLI suite passes 20 tests and four subtests.
Automatic deletion remains suspended pending current Gateway lifecycle mutation
qualification, reviewed orphan disposition, and exact deployment alignment.
No production retention setting or storage object was changed.
