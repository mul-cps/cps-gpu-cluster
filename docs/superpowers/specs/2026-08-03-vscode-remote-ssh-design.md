# VS Code Remote-SSH support for JupyterHub notebooks

Status: design approved, not yet implemented.

## Problem

`jupyterhub-ssh` (port 22, `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/chart/templates/ssh/`)
is an `asyncssh`-based gateway (`patch-configmap.yaml`) that authenticates
with a JupyterHub API token as the SSH password, auto-spawns the user's
notebook server via the Hub REST API if it isn't already running, and then
bridges the SSH session into a Terminado (JupyterLab's browser-terminal
backend) websocket. This works for interactive terminal use only.

Live testing (2026-07-23) confirmed this is a structural limitation, not a
config gap:

- `NotebookSSHServer.session_requested()` is hard-wired to one handler
  (`_handle_client`, which bridges into Terminado) regardless of what the
  client actually requested. There is no `exec_requested` or
  `subsystem_requested` override.
- A client requesting `RequestTTY=no` plus an explicit command still lands
  in an interactive bash shell (confirmed via the bracketed-paste escape
  sequence `\x1b[?2004h` appearing in the output) — the server cannot run
  a single non-interactive command and return.
- SFTP/SCP both fail on port 22 (`subsystem request failed on channel 0`).
  A separate real-OpenSSH server exists on port 2222
  (`.../jupyterhub-ssh/chart/templates/sftp/`) but it bind-mounts the
  shared-storage PVC (`/mnt/home/<user>`), not the user's actual notebook
  home directory, and has no auto-spawn behavior at all.
- Port forwarding (`connection_requested()`, rewriting `localhost` to the
  pod IP) already works and is real, general TCP forwarding — this is the
  one piece of non-terminal functionality the gateway already has.

VS Code Remote-SSH requires non-interactive exec (to bootstrap and run its
server-side component) and file access, neither of which the port-22
gateway can provide, and does not benefit from the port-2222 server since
that path has no auto-spawn and isn't the notebook home directory.

A prior, narrower design (`docs/sftp-via-contents-api-scoping.md`, research
only) scoped two options for SFTP specifically: extending the gateway to
speak SFTP against the Jupyter Contents API (fundamentally mismatched —
Contents API is whole-file, SFTP is random-access, a real risk for large
model checkpoints), or a real sshd sidecar per pod (loses auto-spawn as
scoped there). This design supersedes that scoping for the exec+SFTP case
by combining both approaches instead of choosing one.

## Requirements

- Native VS Code Desktop + Remote-SSH must work (not just the existing
  browser-based code-server at `/user/<name>/vscode/`, which already works
  today and remains available as a lighter-weight alternative).
- Auto-spawn-on-cold-connect must be preserved: connecting to a
  not-yet-running server should trigger the same Hub API spawn + poll +
  progress-banner behavior the port-22 gateway has today.
- Named-server targeting (`user+servername@...`) must be preserved.
- SSH agent forwarding must work (e.g. `git push` from inside the remote
  session using the local machine's keys).
- Terminal (`ssh user@...` for an interactive shell) must keep working.

## Design: gateway-as-bastion + real per-pod sshd

Split responsibilities instead of extending one existing component to do
everything:

- **The port-22 gateway keeps doing exactly what it's good at today**:
  token authentication (`validate_password`) and auto-spawn-if-not-running
  (`start_user_server`, including the live progress banner over
  the auth exchange) — unchanged.
- **Each notebook pod gains a real, minimal OpenSSH sidecar container**,
  added via the same `extra_containers` mechanism `apply_profile_settings()`
  in `.../jupyterhub/values.yaml` already uses for MPS/Xpra. Because it's
  genuine OpenSSH, exec/SFTP/SCP/port-forwarding/agent-forwarding all work
  natively — no protocol code to write.
- **After auth succeeds, the gateway becomes an SSH client itself**
  (asyncssh supports being both server and client in one process), opens an
  inner connection to that pod's sidecar, and from that point on relays
  every channel type (session, exec, subsystem, direct-tcpip, and
  agent-forwarding channel-opens) 1:1 between the real client and the inner
  connection, in both directions, as raw pipes. The gateway does not need
  to understand SSH channel semantics beyond relaying them.

One external entrypoint (`jupyterhub.dshl.unileoben.ac.at:22`) is
preserved; `user+servername` syntax needs no new logic since it already
resolves to a specific pod today — that same resolved pod's sidecar is
simply what the inner connection targets.

### Credential provisioning (gateway → sidecar)

At pod-spawn time, a per-pod credential (generated key pair or random
token) is created and made available to both the sidecar (mounted/env,
used as its `AuthorizedKeysFile` source) and the gateway (retrievable via
a Kubernetes Secret named after the pod, or an annotation — the gateway
already runs with in-cluster API access). This mirrors KubeSpawner's
existing per-user secret injection; no new distribution mechanism is
needed. The end user never sees this credential.

### Sidecar image/config

- Real `sshd`, added via `extra_containers`.
- Runs as UID 1000 (`jovyan`), sharing the user's actual home-directory
  volume already mounted into the notebook pod — this closes the
  home-directory gap the existing port-2222 SFTP server has (that server
  uses the separate shared-storage PVC instead).
- `sshd_config`: password auth disabled; only the per-pod generated key is
  accepted; `AllowAgentForwarding yes`; `AllowTcpForwarding yes`; listens
  only on the pod's internal address — never exposed via a Service or
  Ingress, reachable only from the gateway.
- No PAM/multi-tenant chroot complexity needed (unlike the port-2222
  server) since there's exactly one user per pod.

### Data flow

1. Client connects to `jupyterhub.dshl.unileoben.ac.at:22`, authenticates
   with a JupyterHub API token as the password (`user` or
   `user+servername`).
2. Gateway resolves the target server, calls the Hub API to spawn if
   needed, polls until ready — unchanged, including the progress banner.
3. Gateway looks up the pod's sidecar credential and pod IP, opens an
   inner asyncssh client connection to `<pod-ip>:2200`.
4. Gateway relays every subsequent channel request/data from the real
   client into the inner connection and back, transparently.
5. VS Code Remote-SSH proceeds as if talking to a normal SSH server.

### Error handling

- Spawn failure/timeout: unchanged from today (403/400 handling, banner
  message, connection refused before any inner connection is attempted).
- Sidecar not yet ready (pod running, sshd inside still starting): brief
  retry/backoff on the inner connection before failing, surfaced similarly
  to today's spawn-wait banner.
- Sidecar crash/restart mid-session: inner connection drop closes the
  outer session cleanly rather than attempting a transparent silent
  reconnect — VS Code's own reconnect logic is better placed to handle
  re-establishing than the gateway faking continuity.

### Migration / rollout

1. Add the sidecar container and credential wiring first, inert/unused.
   Verify reachability from a debug pod.
2. Cut the gateway's session-handling over from Terminado-bridging to the
   relay path.
3. Test against real users, including named-server targets and VS Code
   Remote-SSH itself.
4. Remove the now-dead Terminado-bridging code path
   (`_handle_client`/Terminado websocket bridging in
   `patch-configmap.yaml`) once the relay path is confirmed working —
   plain `ssh user@...` terminal access keeps working with no special
   casing, since that's just what a normal interactive session over real
   sshd looks like.

## Explicitly out of scope

- The existing port-2222 SFTP-to-shared-storage server is untouched by
  this design; it serves a different use case (shared storage, not the
  notebook home directory) and is not superseded by this work.
- The browser-based code-server path (`/user/<name>/vscode/`) is untouched
  and remains available as-is.
