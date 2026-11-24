# Compute gateway HTTP handoff relay

This staging configuration uses HAProxy 3.2.25 to retain API requests during a
bounded transfer of the compute-state writer. The gateway API listener verifies
upstream TLS against the existing gateway CA and DNS name. The capture listener
passes TLS through to the read-only standby independently of the API route. The
health listener checks that HAProxy is serving and stays ready during a hold.

Render `haproxy.cfg.in` with `render.py` and the verified incumbent, candidate
and capture IPv4 endpoints. Mount the rendered config, Lua source, and writer
map at `/handoff-config`. Mount the gateway CA at `/trust/ca.crt` and provision
`/handoff-tls/server.pem` from the existing gateway TLS Secret with owner-only
permissions. Keep `/run/handoff/runtime.sock` private to the relay and its
authorized controller. Check the rendered configuration with `haproxy -c`
using the same image and mounts as the running relay.

The map starts in `hold`. `traffic_gate.py` changes the route through the local
runtime socket and reads it back. During a hold, each newly accepted API request
waits for up to 4.7 seconds before receiving HTTP 503 with `Cache-Control:
no-store`. Once forwarded, a request stays with its selected writer. HAProxy
uses fresh upstream connections and disables retries to avoid replaying writes.

Set every serving replica to `hold` and read back each route before relying on
backend drain counts. Confirm that direct callers have drained and that every
serving replica reports zero in-flight requests to the outgoing writer. The
database and native execution fences independently establish when the incoming
writer can activate. Select that writer only after its readiness has been
verified. Recheck relay identity and route state throughout the handoff because
a restarted relay starts in `hold`. Apply the same sequence in reverse for a
rollback on the authoritative store.

The production Service, writer activation, and multi-replica coordination each
have a separate rollout gate. Mount and validate this configuration through a
shadow Service first.
