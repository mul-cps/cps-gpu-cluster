# Connected-member removal and populated archive — live acceptance

A dedicated CPS CPU-only fixture used the existing Mikasa/Armin canonical people,
a new course, assignment and group, and a fresh neutral workspace owner. It did
not modify their original project group or the separate GPU idle-expiry test.

Ten-minute `inherit` tokens for the two non-admin students were created using
JupyterHub's ORM under operator access, with no role or service-scope changes.
The console correctly cannot mint student tokens. Both tokens were explicitly
revoked after the test. No credentials are included here.

Both students first received HTTP 200 from the notebook contents API. Armin's
terminal WebSocket was opened without executing any commands. Normal
remove_member stopped the workspace, closed that existing connection, removed
only the fixture membership and updated Shares. After normal restart, the same
student credentials returned Armin 403 and Mikasa 200. The original project
membership was untouched. Requests used the normal internal Hub proxy with the
external Host/Origin and ordinary Hub token validation; public HTTPS trust from
the console client was not qualified (missing issuer trust), and no TLS check was
disabled. A client argument error was corrected before membership mutation.

Mikasa then wrote and read a uniquely owned test file through the notebook API.
Normal close_assignment stopped the active CPU writer and archived the dataset.
An independent unprivileged Job mounted the retained claim as writable, verified
the exact test-file SHA-256, and required EROFS from a new write. This proves
populated-file retention and server-enforced readonly storage after writer stop;
it is not a backup/restore exercise. Owned verifier Jobs were cleaned up after
their evidence was captured. The archived dataset/test file remain retained.

This is CPU connected-user revocation. Native GPU cleanup during membership
removal, equivalent CIT visitor access and production-scale bursts retain their
separate qualification scope.
