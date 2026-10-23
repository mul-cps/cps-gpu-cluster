# Console archive identifiers — live acceptance, 23 October 2026

The actual console-to-Gateway archive request failed with 409 because Source
workspace records use `id`, while the Gateway accepted strings or dicts with
`workspace`. The HTTP filesystem adapter now serializes canonical identifier
strings and rejects conflicting dict identifiers. The regression test calls the
real Gateway endpoint via ASGI and verifies trusted registry data reaches storage.

The console SDK baseline was identified by byte-comparing all 49 installed Python
modules to revision de90610. Exact-base fix ea97d60 changes only storage.py;
105 other distributions, the admin app and frontend remain identical. Both
consoles run the new immutable image. Storage tests: 111 passed.

A separate operator-owned CPU fixture used Mikasa and Armin's existing canonical
identities, a new course/group/assignment, and retained version-2 workspace storage.
It started normally in 20.24 seconds. The initial archive request failed before
NAS mutation; read-only diagnostics confirmed neutral ownership, shutdown and
zero active writers. After deployment, the normal close_assignment retry succeeded
in 8.43 seconds. ZFS readonly evidence and an actual RW-client verification Job
proved server-side EROFS enforcement. The assignment is closed and the workspace
archived; a normal restart was rejected before spawning. Dataset/files are retained.
The test does not demonstrate populated-data recovery or connected visitor revocation.
The service correctly denied minting visitor tokens; no service privileges changed.
The independent GPU idle-expiry run was not stopped or modified.
