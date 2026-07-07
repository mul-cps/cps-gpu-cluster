# Scoping: real SFTP against the user's home directory (not just shared storage)

**Status: research/design only. No code changed, no cluster touched.**

## Background

Today there are two separate SSH-family components under
`cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/`:

- **`jupyterhub-ssh` (port 22)**: a custom `asyncssh`-based Python server
  (upstream `github.com/yuvipanda/jupyterhub-ssh`, patched in this repo's
  `chart/templates/patch-configmap.yaml` to add Terminado-based terminal
  forwarding, plus a local-port-forward patch). Auth: `validate_password()`
  treats the SSH password as a JupyterHub API token, calls
  `start_user_server()`, which **actively spawns the user's notebook server
  via a `POST` to the Hub API if it isn't already running** (sending a live
  "Starting your server..." auth banner while polling), then proxies
  stdin/stdout into that notebook's terminal over a Terminado websocket. It
  never touches the filesystem directly — no chroot, no bind mount, no NSS.
- **`jupyterhub-sftp` (port 2222)**: a vendored `quay.io/jupyterhub-ssh/sftp`
  image (plain OpenSSH, `ForceCommand internal-sftp`) that bind-mounts the
  **shared storage** PVC (`jupyterhub-shared-storage`) per-user and chroots
  there. Two bugs in this were just fixed (a NetworkPolicy blocking ingress,
  then a missing auto-create-directory-on-first-login step — see
  `docs/troubleshooting.md`, 2026-07-07 entries). It works now, but only
  gives access to shared/collaborative storage — **not** the user's real
  personal home directory (the `claim-<username>` PVC the actual notebook
  pod mounts, which SFTP never touches).

The unmet need: users want SFTP against their **real personal home
directory**, not just shared storage.

This document scopes two candidate designs against that baseline and
recommends a path.

## Option A: `asyncssh` SFTP subsystem in `jupyterhub-ssh`, bridged to the Jupyter Contents API

### Idea

Add a native SFTP subsystem to the existing port-22 `asyncssh` server via
`sftp_factory=`, alongside the existing `server_factory=partial(NotebookSSHServer, self)`.
Instead of touching a local filesystem, the SFTP handler would translate
each SFTP operation into an HTTP call against the user's own notebook's
Contents REST API (`/user/<username>/api/contents/<path>` — the same API
the Jupyter web UI itself uses), reusing the already-authenticated
`notebook_url`/`token` state that `validate_password()` already establishes
per-connection.

### `asyncssh` SFTPServer API (confirmed from `asyncssh/sftp.py` source,
`ronf/asyncssh` master, class `SFTPServer` starting at line ~6980)

Wiring: `asyncssh.listen(..., server_factory=..., sftp_factory=<SFTPServer subclass>, ...)`
— `sftp_factory` is a constructor callable taking `(chan, chroot=None)`, the
`SSHServerChannel` for the SFTP subsystem request. This is an independent,
additive keyword — it does not require restructuring the existing
`NotebookSSHServer(asyncssh.SSHServer)` / `session_requested()`
session-handling code at all. One connection can carry both a `session`
(shell) channel and an `sftp` subsystem channel; asyncssh picks the right
factory per-channel-request based on what the client asks for. **This part
is genuinely additive, not invasive** — the existing terminal-forwarding
code is untouched.

One correction to be precise about: the `SFTPServer` instance is a
*different object* from the `NotebookSSHServer` instance that ran
`validate_password()`/`start_user_server()`, and `chan.get_environment()`
only exposes client-set environment variables, not the token or notebook
URL the auth flow already resolved. There's no built-in public path from
the SFTP channel back to the `SSHServer` object that authenticated the
connection. The token/notebook URL have to be handed across explicitly —
e.g. `NotebookSSHServer` calls `self._conn.set_extra_info(jupyter_token=...,
notebook_url=...)` once auth succeeds, and the `SFTPServer` subclass reads
it back via `self.channel.get_connection().get_extra_info(...)`. So the
auth *logic* (token validation, auto-spawn-if-not-running) is fully
reusable as-is, but this small connection-scoped handoff bridge is
genuinely new, if minor, work — it doesn't move the effort estimate much,
but "reuse as-is" slightly overstates it if left unqualified.

Methods to implement, all `def` or `async def`, any can optionally be a
coroutine (asyncssh awaits if `inspect.isawaitable`):

| Method | Signature | Notes |
|---|---|---|
| `open` | `(path: bytes, pflags: int, attrs: SFTPAttrs) -> file_obj` | `pflags` is a bitmask: `FXF_READ`/`FXF_WRITE`/`FXF_APPEND`/`FXF_CREAT`/`FXF_TRUNC`/`FXF_EXCL`. Returns an **opaque object** you fully control — asyncssh never inspects it, just passes it back into `read`/`write`/`close`/`fstat`. |
| `close` | `(file_obj) -> None` | |
| `read` | `(file_obj, offset: int, size: int) -> bytes` | **Arbitrary byte offset + length — true random access**, not sequential/streaming. Default local impl does `file_obj.seek(offset); file_obj.read(size)`. |
| `write` | `(file_obj, offset: int, data: bytes) -> int` | Same: **arbitrary offset**. Default impl: `seek(offset); write(data)`. |
| `lstat`/`fstat`/`setstat`/`fsetstat` | path or file_obj → `SFTPAttrs`/`os.stat_result` | |
| `listdir`/`scandir` | `(path) -> Sequence[SFTPName]` / `AsyncIterator[SFTPName]` | Directory listing, each entry needs `SFTPAttrs` (size, permissions, mtime, etc.) |
| `remove`, `rename`, `posix_rename`, `mkdir`, `rmdir` | as named | |
| `realpath`, `readlink`, `symlink` | as named | `realpath`/`readlink` also used to enforce a virtual chroot via `map_path`/`reverse_map_path` if desired |
| `statvfs` | `(path) -> SFTPVFSAttrs` | filesystem-level stats, optional |

**The critical finding**: `read`/`write` are specified with **arbitrary
`offset` + `size`/`data` parameters** — this is the real SFTP wire protocol
contract (clients routinely issue reads/writes at arbitrary offsets,
including out-of-order and overlapping ones, and rely on pipelined
concurrent requests for throughput). This is **not a sequential/streaming
API** — it is a POSIX-like random-access file API. `open()` is expected to
return a handle that later `read`/`write`/`close` calls operate on
statelessly per-call, which needs to be mapped onto whatever storage
mechanism sits behind it.

### Jupyter Contents API (confirmed via `jupyter-server` REST API docs)

`/api/contents/{path}` supports `GET` (read file or list directory),
`PUT` (create/save — full-content), `PATCH` (rename), `POST` (create/copy),
`DELETE`. Content format: plain text for `format=text`, **base64 for
`format=base64`** (binary), JSON for notebooks. Directory `GET` returns an
array of child items with `type`/`size`/`last_modified`/`name`/`path`/
`mimetype`/`writable`/`created`. **`PUT` requires the full file content in
one request — there is no partial/byte-range write.** Conflict detection is
limited to a `last_modified` timestamp field/header; **there is no ETag or
optimistic-locking mechanism** — a `PUT` will silently clobber the file
regardless of what the notebook UI (or anything else) wrote in the
meantime.

### The mismatch, stated plainly

asyncssh's `SFTPServer.read`/`write` contract is genuinely random-access
(arbitrary offset, partial reads/writes, no assumption content is fetched or
flushed once). The Contents API is genuinely whole-resource (`GET` fetches
the entire file, `PUT` replaces the entire file). Bridging them requires
picking a strategy — realistically: **buffer the whole file in memory on
`open()` (a `GET`), serve all subsequent `read`/`write` calls against that
in-memory buffer by slicing/patching at the requested offset, and flush the
whole buffer back via `PUT` on `close()`** (or on `fsync`, if the client
issues one). This is workable but has real costs:

- **Memory ceiling**: the whole file lives in the `jupyterhub-ssh` pod's
  memory for the duration of the SFTP session, and — since this is a
  single shared Deployment serving *all* users, not a per-user process —
  concurrently-open large files from multiple users stack up in the same
  pod's memory. Model checkpoints and datasets (this cluster is a GPU/ML
  workload cluster) are exactly the files most likely to be multi-GB;
  a single central pod buffering several of those concurrently is a real
  resource-exhaustion risk that a per-user process or a real filesystem
  would not have.
- **No incremental/streaming transfer**: a large upload cannot start
  landing on the notebook's disk until the client finishes sending and the
  connection closes (or an explicit fsync happens) — turnaround time is
  "whole transfer, then whole flush" rather than pipelined-as-you-go.
- **Lost-update risk**: since Contents API has no ETag/conditional-write
  mechanism, a user editing a notebook in the browser while SFTP has the
  same file buffered open is a real, unguarded race — whichever `PUT`
  lands last (SFTP's whole-buffer flush on close, or the notebook's
  autosave) silently wins, with no conflict signal to either side. This is
  a strictly worse conflict story than direct concurrent filesystem access
  would have (where at least OS-level file locking is available, imperfect
  as that also is for concurrent editors).
- **Directory listings become N HTTP round-trips-worth of work** condensed
  into 1 (Contents API directory GET does return full listing+metadata in
  one call, so this one is actually fine) — but per-file operations
  (`stat`, `open`, `remove`) are each their own HTTP round trip to the
  user's own notebook pod, which will be measurably slower than direct
  filesystem access for anything with many small files (e.g. an
  `ls -la`-heavy client walking a `site-packages`-like tree, or `rsync`
  with many small files).

### What's reusable vs. new

Reusable: the entire `validate_password()` → `start_user_server()` auth
logic (token validation + auto-spawn-if-not-running). `sftp_factory` is
additive at the `asyncssh.listen()` call site — no restructuring of
`NotebookSSHServer` needed, since asyncssh already separates "session" and
"sftp" subsystem requests into separate factories on the same connection.
The one piece of new (small) glue: since the `SFTPServer` instance is a
different object than `NotebookSSHServer`, the resolved token/notebook URL
must be explicitly handed across via `SSHServerConnection.set_extra_info()`/
`get_extra_info()` rather than being available for free.

New work: the entire `SFTPServer` subclass — realistically comparable in
size to (probably larger than) the existing Terminado-forwarding code,
since it needs an HTTP-backed virtual filesystem layer (open/read/write/
close with the buffer-and-flush strategy above), full attribute mapping
(Contents API's `size`/`last_modified`/`type`/`writable` → `SFTPAttrs`),
path-traversal protection (Contents API paths are relative to the user's
home by construction via the URL, which is actually a structural
advantage — a request can't easily escape upward outside `map_path`
misuse, unlike a bind-mount chroot which needs explicit enforcement), and
directory operations (`mkdir`/`rmdir`/`rename` map fairly directly onto
Contents API `PUT type=directory`/`DELETE`/`PATCH`).

### The auto-spawn advantage (significant, not a wash)

`NotebookSSHServer.start_user_server()` doesn't just check whether the
notebook is running — it `POST`s to the Hub API to spawn it if not, with a
live progress banner while polling, exactly as it does today for plain
`ssh` terminal access. Because Option A would live in the *same* connection/
auth path, it inherits this **for free**: a user could `sftp` in cold, with
no browser session ever opened, and their notebook would auto-spawn before
the SFTP session goes further. This is a genuine, meaningful capability —
"drop a file in without first opening the web UI" is plausibly a real part
of what users want from SFTP in the first place — and it is **not**
available to Option B (below).

## Option B: SFTP as a sidecar container in the user's own notebook pod

### Idea

Add a lightweight, single-tenant SFTP server (e.g. a plain OpenSSH
`internal-sftp`-only container — much simpler than the current
`jupyterhub-sftp` image since there is no multi-tenant bind-mount/chroot
complexity to speak of) as an additional container in each user's own
singleuser notebook pod, via KubeSpawner's `extra_containers`/profile
mechanism — the same mechanism `apply_profile_settings()` in
`cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml`
already uses to add MPS-related volumes/mounts/env vars per profile
(confirmed present, e.g. around lines 1419–1663).

Because the sidecar shares the pod, it automatically shares the same
already-mounted `/home/jovyan` (`claim-<username>` PVC) — zero bind-mount/
chroot/NSS-all-to-one machinery needed. Auth can be much simpler: since
this container only ever serves one already-authenticated user for the
pod's lifetime, a single fixed credential or a per-pod secret injected at
spawn time suffices — no need to re-derive the multi-tenant
token-verification dance the current `jupyterhub-sftp` needs.

### Comparison against Option A

| Dimension | Option A (Contents API bridge) | Option B (sidecar) |
|---|---|---|
| Implementation complexity | New HTTP-backed virtual-FS layer against asyncssh's random-access contract — the buffer/flush mismatch described above is the core complexity | Low — a real, battle-tested SFTP server (what it's actually built for) against a real local mount. No protocol-mismatch layer to build at all |
| Performance | Every stat/open/remove is an HTTP round trip to the notebook pod; large files fully buffered in the shared `jupyterhub-ssh` pod's memory | Direct filesystem access — strictly faster, handles arbitrary file sizes/streaming naturally, no memory ceiling shared across users |
| Auth model | Reuses existing multi-tenant token-validate + auto-spawn flow as-is | Needs a new (simpler) per-pod credential/secret mechanism, since it's a different process per user |
| Auto-spawn-on-cold-connect | **Yes** — inherited from the existing auth path for free | **No** — the sidecar container doesn't exist until the pod is already running; nothing listens to trigger a spawn, so a cold SFTP attempt with no running session just times out/connection-refused |
| Access/routing model | Centralized: one port (22), one Service, no per-user routing needed | Needs a reachable endpoint **per running pod** — either a per-user Service or extending the existing ingress TCP-passthrough pattern to route dynamically to N live pods. This is real added complexity the centralized options don't have |
| Resource cost | One shared process; risk concentrates as memory pressure in that one pod under concurrent large transfers | One extra small container per active notebook pod — likely negligible per-pod, but N times the container count cluster-wide |
| Both share | Both only work while the user's notebook pod is actually running (Contents API needs the live notebook process; sidecar needs the pod to exist) — but this is *not* symmetric in practice: Option A's auto-spawn covers the "no session yet" case, Option B's does not, so this shared limitation lands harder on Option B |

### Baseline for comparison: Option C, today's `jupyterhub-sftp` (already working)

Already deployed, already working for shared storage as of the two bug
fixes this session. Zero additional engineering to get *this* working — the
only gap is that it doesn't reach the personal home directory PVC. Worth
stating explicitly: if "shared storage over SFTP" is all that's actually
needed operationally, no further work is required at all.

## Risks and open questions common to both new options

- **Path traversal / auth scoping**: Contents API path resolution is
  relative to the authenticated user's own server by construction (a
  structural advantage for Option A); a sidecar (Option B) needs to make
  sure its own chroot/mount setup doesn't accidentally expose paths outside
  `/home/jovyan` — likely fine given it's a dedicated container with a
  single bind mount, but should be verified in an implementation, not
  assumed.
- **Concurrent-edit conflicts**: Option A has no protection at all (no
  ETag/If-Match support in the Contents API); Option B is exactly as safe
  (or as unsafe) as any two processes writing the same POSIX file
  concurrently — i.e. no worse than today's shared-storage SFTP already is.
- **Large file / model checkpoint transfers**: a known real workload on
  this cluster (GPU/ML). Option A's whole-file-buffer-in-shared-pod-memory
  strategy is the single most concerning risk of the two designs for this
  specific access pattern; Option B has no such ceiling.

## Effort estimate

- **Option A**: not small. The auth/session wiring is genuinely reusable
  and trivial to add (`sftp_factory=` alongside `server_factory=`), but the
  `SFTPServer` subclass itself is a new subsystem roughly comparable in
  size to the existing Terminado-forwarding code, with a structural
  protocol mismatch (random-access SFTP vs. whole-resource HTTP) that has
  to be worked around, not just implemented — this is where most of the
  real complexity and risk lives, not in boilerplate method-count.
- **Option B**: smaller and lower-risk in absolute engineering terms (reuse
  a real SFTP server as-is, wire it into the pod spec the same way MPS
  volumes already are), but it introduces a genuinely new operational
  problem this cluster doesn't currently have to solve: **per-pod-reachable
  networking for N live pods**, rather than one centralized, already-solved
  ingress path. That's not a coding-effort cost so much as a design/ops
  cost (dynamic Service-per-pod or TCP-passthrough routing logic).
- **Option C (do nothing further)**: zero effort; already working for
  shared storage today.

## Recommendation

Worth pursuing, but not urgently, and not Option A as currently scoped.
Given the auto-spawn advantage is real but the memory-buffering /
whole-file-vs-random-access mismatch in Option A is a structural (not
incidental) risk for exactly this cluster's workload profile (large model
checkpoints, GPU/ML datasets), **Option B (sidecar) is the safer default
recommendation if "SFTP to the real home directory" becomes an actual
near-term requirement** — it avoids the hardest technical risk entirely at
the cost of solving a bounded, well-understood infra problem (per-pod
routing) that this cluster's existing ingress/networking patterns can
likely be extended to cover. Option A remains attractive specifically
*because* of the cold-start auto-spawn behavior, so if that capability
turns out to be a hard requirement (not just a nice-to-have), it tips the
choice back toward Option A despite the memory risk — that requirement
should be confirmed with actual users before committing either way.

**Recommended next step**: no code yet. Before picking a path, confirm with
actual users (1) whether "home directory access via SFTP" is even wanted
now that shared storage works, and (2) whether "connect cold, no running
session" is an important use case (favors Option A) versus most users
already having a running session when they'd want to transfer files
(removes Option A's main structural advantage, favors Option B on
simplicity/performance/risk grounds alone).
