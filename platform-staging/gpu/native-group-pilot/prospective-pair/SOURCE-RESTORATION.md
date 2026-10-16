# Source restoration after notebook531 qualification

`source_restoration.restore` is an application operation, not a database repair.
It uses the genuine LocalCourseProvider, WorkspaceService, Hub adapter and normal
ComputePolicyClient preview/register API. It restores CPU profile, original
course ceiling, original registration and storage references under an external
CPS/CIT writer freeze. It performs no Start, Stop, reservation release, grant
change, filesystem operation or freeze release.

The trusted executor must first restore Gateway to the original policy. It must
supply the original reviewed forward handover and independently hash-pinned Root
pair contract. Local and central records may be original, forward-migrated or in
one of the partially committed states. Every guard rereads actual records,
current administrator identity, canonical members, Hub stopped state, reservations,
native ledger and physical proof. Unrelated local/course/storage changes fail.

A normal Stop changes notice to null and can add `archive_pending=false`. This
specific lifecycle state is accepted; the original notice is restored and the
inactive archive flag is explicitly false. The provider merges records, so an
absent archive flag cannot be made absent through a normal PUT. No other
unreviewed field is normalized or removed.

After an enrolled GPU lifetime, the complete actual ledger must be released,
the immutable enrollment must match its lifetime, and a typed immutable cleanup
receipt must match binding, attempt and intent. An independent Root-owned
`verify_physical_release` asynchronous callback must actually measure current
zero charge for the entire selected pool and validate its complete physical
archive. Its closed result contains version 1, qualification policy hash,
original ledger UID, exact node/boot/driver/device identity, `zero_charge=true`
and observation time no older than 30 seconds. This module verifies the result
but does not implement that hardware collector. A cached released flag, expired
lease or fabricated callback is not acceptable execution evidence.

25 focused tests exercise both 5/20 scopes, unstarted/course-only/complete
handover, normal Stop metadata, valid completed enrollment, active ledger,
missing cleanup, altered enrollment, expired membership, missing CPU grant,
unrelated edits, administrator/freeze/Pod/reservation/physical/policy denials,
and recovery after either local commit fails. Kubernetes and physical hardware
are simulated; local SQLite provider and authenticated ASGI registration are real.

No live restoration or notebook531 hardware qualification is claimed. The next
step is composing this operation with the existing Node/Gateway/Hub transitions,
actual freeze, fresh capture and independent physical collector.
