# Coordinator-owned Hub admission candidate

Status: published source only. No live database, Hub or Gateway was changed.

Compute branch `pool-hub-client-20261028`, commit
`3ecca89d93489f8156bfeb61e206ede514b04b5c`, contains:

- A fixed-origin HTTPS client with projected credentials, pinned CA, bounded
  requests and three closed operations. Malformed mutation responses or lost
  replies report an unknown outcome; they are not automatically retried.
- Schema v7 admission custody: exact request UUID/hash/bytes, finalized plan,
  head and original response are committed in the same SQLite transaction as
  member reservations and the CREATE outbox. Exact retries recover the original
  response; conflicting requests fail before additional effects.
- Independent runtime successor checks for the exact admission row and the
  original member/attempt/outbox changes. These do not authorize installation.

Root independently ran 37 client tests and 46 attempt/successor tests. The latter
use real SQLite transactions and include fenced v6 migration, conflict, reopen,
rollback and substituted retained-field cases. These are software tests, not a
live two-Hub race or installed-authority qualification.

The prepare contract is finalized on the coordinator after Kubernetes dry-run
and before durable admission. The client refuses unfinalized responses. Pod
creation registration must independently read the original actual Pod UID and
spec and compare them to this retained finalized contract.

Still absent: the authenticated service routes, genuine coordinator-side grant
and roster authority, installed runtime preflight support and distributed
installation assembly. Current installed runtime deliberately refuses the new
write action. Do not activate it with a fake producer or a configuration flag.
An idempotent response alone never authorizes creating a new Pod after terminal
cleanup. Root and an independent worker reviewed the bounded atomic delta; no
bypass was identified within that tested scope.
