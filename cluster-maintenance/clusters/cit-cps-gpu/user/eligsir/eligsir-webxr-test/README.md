# EliGSiR WebXR test instance

Frontend and Mission Control broker built from eligsir-webxr f038ac4f (v0.3.2). Images are pinned by digest. The full built-in lab asset tree is included; no GPU allocation or mapper is required for browser-side rendering.

URL: https://eligsir-webxr-test.dshl.unileoben.ac.at/viewer.html
Mission Control: https://eligsir-webxr-test.dshl.unileoben.ac.at/mission.html

The test GitRepo tracks only this directory on branch deploy/eligsir-webxr-test. Existing production bundles are unaffected.

## Bootstrap dependencies

- Source ingress-nginx/dshl-wildcard must allow automatic reflection into eligsir-webxr-test. Preserve every existing namespace in both Reflector lists. Do not copy the TLS Secret manually.
- Provision eligsir-registry as a namespace-local registry pull Secret. Never commit its data.
- Campus/VPN clients need DNS mapping this hostname to 10.21.0.50.
- WebRTC currently uses host ICE candidates, so the single pod uses hostNetwork on k3s-wk-gpu4 (10.21.0.41). Clients must be able to reach its UDP candidates. No TURN service is configured. This is a test deployment, not an internet/NAT traversal solution.

## Runtime boundaries

Nginx serves the production bundle on 18089 and proxies public APIs to the broker's loopback 8787. Internal simulator ingest routes are blocked at the public proxy. The broker runs with external-core mode; without a publisher, live map data is empty while the reference lab remains usable.

One broker replica owns in-memory session/lease state. Recreate releases the fixed port on updates; restarting loses pairings. Scene uploads use bounded temporary storage and are not persisted. Quest native view capture is unavailable in the cluster without a separately configured capture relay.

## Verification

Run kubectl kustomize on this directory, then server dry-run after namespace exists. Confirm Fleet readiness, Deployment rollout, TLS validation, HTML/JS and representative lab byte ranges, blocked internal routes, and an actual WebRTC Mission handshake. HTTPS readiness alone is insufficient.

Rollback: revert the deployment image digests on the test branch and observe Fleet; remove the dedicated GitRepo to remove the test installation. Do not modify the production cluster-maintenance GitRepo.
