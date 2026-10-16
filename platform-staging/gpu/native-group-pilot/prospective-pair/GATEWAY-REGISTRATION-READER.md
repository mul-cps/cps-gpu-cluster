# Current-pair Gateway registration reader

`gateway_registration_reader.reader_source` accepts only the frozen reader SHA
bc16a767 and the independently raw-hash-pinned Root pair contract. It changes
exactly the single legacy scope guard, with a contract-hash comment. Every other
byte, including projection-rotation checks, module/config hashes, configured
SQLite device/inode/UID, normal ControlStore method and mode=ro connection, stays
unchanged. Legacy/unreviewed scopes are refused before runtime file access.

`GatewayReader` binds the current Gateway namespace/Pod UID/full spec/container
image and running readiness before and after each read. It accepts only the two
contract scopes and rejects foreign registrations, invalid/duplicate JSON and
oversize output. `sdk_exec` uses a separate Kubernetes client, fixed short argv
and length-framed UTF-8 stdin. The Python child reads the explicit byte count;
it needs neither shell nor stdin EOF nor bulky exec-URL arguments. Source/output,
stderr and wallclock duration are bounded, nonzero status/stderr fails, and the
websocket closes on every path. The genuine Source factory can call this reader
from a worker thread without blocking its event loop.

22 tests cover byte preservation, both real SQLite registrations without file
changes, old/foreign scopes, changed source/contract, UID/spec/image changes,
post-read process replacement, invalid/foreign output, byte-length framing,
stdout bounds, stderr/nonzero exits, deadlines and connection cleanup. The
original projected-config filesystem tests remain unchanged in the full suite.

The actual maintenance Pod received one namespace Role/RoleBinding allowing GET
of only the current named Gateway Pod and its exec subresource. RBAC limits the
target; the pinned trusted operator program enforces read-only command behavior.
No browser receives this permission or transport. Own-token access reviews
confirmed the target reads/exec were allowed and other-Pod exec, Secret get and
Deployment patch denied. Both actual Gateway registrations were read over the
SDK websocket and matched the complete captured Source records, including
retained storage provenance. No Source application/provider was instantiated,
no Source SQLite database was opened and neither frontend was paused.

Role, RoleBinding, operator Pod and helper objects have private recorded UIDs.
Root must inspect current process/UID before reuse, rebind only an explicitly
reviewed replacement Gateway after rollout, and remove owned temporary reader
permissions when the maintenance operation finishes. The Pod has a one-hour
active deadline; a previous receipt is not evidence that it is still running.
No policy rollout, Source handover, GPU Start or hardware qualification is claimed.
