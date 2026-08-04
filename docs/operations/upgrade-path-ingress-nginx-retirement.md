# Migration Path: ingress-nginx Retirement (2026)

**Status: research and planning only. No migration has been executed. Do
not deploy anything from this doc without a separate, deliberately
scheduled follow-up piece of work.**

## Why this exists

The upstream `kubernetes/ingress-nginx` project — what this cluster
currently runs as its ingress controller (chart 4.11.3 / app 1.11.3,
Fleet bundle `system/networking/ingress-nginx`) — has been retired.
Kubernetes' own announcement
([Nov 11, 2025](https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/))
and a follow-up Steering/Security Committee statement
([Jan 29, 2026](https://kubernetes.io/blog/2026/01/29/ingress-nginx-statement/))
confirm: the project was kept alive by 1–2 unpaid volunteers despite an
estimated ~50% of cloud-native environments depending on it, and
best-effort maintenance ended **March 2026** — no further releases, CVE
fixes, or bugfixes. **The `Ingress` API resource itself is not
deprecated** — only this specific controller implementation is dead. Our
existing `Ingress` objects remain valid Kubernetes API objects regardless
of which controller we point them at.

Kubernetes' own recommendation is deliberately generic: "consider
migrating to Gateway API." No single successor project is officially
blessed. A planned direct fork/successor ("InGate") never matured and is
itself being retired. A **Chainguard fork**
(`chainguard-forks/ingress-nginx`,
[background](https://www.chainguard.dev/unchained/keeping-ingress-nginx-alive))
exists but is CVE-patching only with no free public images/charts — a
stopgap for buying time, not a real long-term destination, and is not
evaluated further here as a target.

## What this cluster depends on ingress-nginx for

- HTTP/HTTPS ingress for JupyterHub, Rancher UI, and other apps
- A wildcard TLS cert issued/renewed by cert-manager (Fleet bundle
  `wildcard-cert`)
- TCP passthrough via the `tcp-services` ConfigMap mechanism:
  - port 22 → `jupyterhub-ssh` service
  - port 2222 → `jupyterhub-sftp` service
- Annotations: `nginx.ingress.kubernetes.io/proxy-body-size`,
  `proxy-read-timeout`, `proxy-send-timeout` (JupyterHub large-file
  uploads)
- MetalLB for the LoadBalancer IP ingress-nginx binds to

Any replacement must cleanly cover all of the above, since JupyterHub
SSH/SFTP access and Rancher UI access both run through it — these are the
two things a botched cutover would break for real, active users.

## Candidate comparison

| | Traefik (K3s-bundled) | HAProxy Ingress | F5 NGINX Ingress Controller (OSS) | Gateway API (Envoy Gateway / Cilium) |
|---|---|---|---|---|
| TCP/UDP passthrough | New `IngressRouteTCP`/`IngressRouteUDP` CRDs — resource-model change | ConfigMap-based, **nearly 1:1 with our current `tcp-services`/`udp-services` mechanism** | `TransportServer` + `GlobalConfiguration` CRDs — new but OSS-covered | Native `TCPRoute`/`TLSRoute` (experimental in the Gateway API spec) — full resource-model change |
| Wildcard TLS / cert-manager | Works fine | Works fine, standard `Ingress` `tls:` block | Works fine, `Ingress` TLS block or `VirtualServer` | Works fine — cert-manager supports Gateway API listener `certRefs` |
| Existing `Ingress` objects reusable? | Mostly — `IngressClass` swap, but known `proxy-body-size` compatibility gaps ([traefik/traefik#12407](https://github.com/traefik/traefik/issues/12407)), and K3s's own bundled Traefik instance must be disabled/isolated to avoid collision | **Yes** — `IngressClass` swap plus an annotation-prefix rename; body-size/timeout annotations have direct equivalents | Mostly — `IngressClass` swap, annotation prefix changes to `nginx.org/*` (direct equivalents exist for body-size/timeouts), but TCP passthrough needs two new CRDs | **No** — full rewrite to `Gateway`/`HTTPRoute`/`TCPRoute` objects. The `ingress2gateway` tool ([reached 1.0 in March 2026](https://kubernetes.io/blog/2026/03/20/ingress2gateway-1-0-release/)) auto-converts ~30 common annotations, but TCP passthrough still needs manual authoring |
| Maintenance / maturity signal | Huge adoption, K3s-bundled, not a CNCF project itself | Two active, independent projects (`haproxy-ingress/haproxy-ingress` community fork, `haproxytech/kubernetes-ingress` official) — neither is CNCF but both ship regularly | F5-backed, steady release cadence; OSS edition confirmed **not** gated on TCP/UDP passthrough or the annotations we need (only active health-checks and a few other features require the paid NGINX Plus-backed edition) | Envoy Gateway: CNCF-graduated lineage, reached GA mid-2025; CNCF's own internal services cluster migrated to it in April 2026 ([CNCF blog](https://www.cncf.io/blog/2026/04/13/ingress-nginx-to-envoy-gateway-migration-on-cncf-internal-services-cluster/)) — the single strongest project-health signal here. Cilium Gateway API: also CNCF-graduated, but using it requires **replacing Flannel as this cluster's CNI** — a large, unrelated architectural change |
| Cost | Free | Free | Free (OSS edition covers our needs) | Free |

## Recommendation

**Migrate to HAProxy Ingress.** It is the lowest-risk path for this
specific cluster for one dominant reason: its TCP-services ConfigMap
model is nearly a direct match for the exact mechanism we already use for
SSH/SFTP passthrough — the single riskiest, most user-facing piece of
this migration. Existing `Ingress` objects need only an `IngressClass`
swap and an annotation-prefix rename (no CRDs, no new resource model), and
it requires no CNI change.

**F5 NGINX Ingress Controller (OSS)** is a strong second choice — its
annotation model and general mental model are the closest match to
ingress-nginx of any candidate, and its OSS edition is confirmed to cover
everything we need at no cost. It loses out to HAProxy Ingress only
because TCP passthrough there requires adopting two new CRDs
(`TransportServer`/`GlobalConfiguration`) rather than reusing a ConfigMap
pattern we already operate.

**Traefik**, despite being "free" via K3s's bundled instance, is not
actually lower-effort: TCP passthrough still needs new CRDs, there's a
known `proxy-body-size` compatibility gap relevant to JupyterHub uploads,
and there's an operational trap in that K3s ships its own Traefik
instance that must be explicitly disabled/isolated to avoid a collision
with a separately-deployed one.

**Gateway API (Envoy Gateway)** is the architecturally "correct" long-term
direction per Kubernetes' own migration guidance, and has the strongest
project-health signal of any candidate (CNCF-graduated, CNCF's own
internal migration in April 2026). But it is the highest-effort,
highest-risk path here: a full rewrite from `Ingress` to
`Gateway`/`HTTPRoute`/`TCPRoute` objects, with TCP passthrough still
requiring manual authoring even with `ingress2gateway` tooling. Treat this
as a deliberate future architectural project, not a reaction to
ingress-nginx's retirement. (Cilium Gateway API is not viable here at all
without first migrating off Flannel as the CNI — out of scope, unrelated
cost.)

## Staged cutover plan (HAProxy Ingress)

This keeps ingress-nginx running throughout until the replacement is
proven, with a rollback point at every stage. None of these steps are to
be executed as part of this research task — this is the plan for the
separate, deliberately scheduled migration.

### Stage 0 — Preparation (no live traffic impact)
1. Add the `haproxy-ingress` bundle under
   `cluster-maintenance/clusters/cit-cps-gpu/system/networking/haproxy-ingress/`
   (new Fleet bundle, following the existing `ingress-nginx`/`metallb`
   bundles as the template).
2. Deploy it with its own dedicated MetalLB `LoadBalancer` IP (a second,
   new IP — not the one ingress-nginx currently holds), so it comes up
   fully isolated with zero effect on live traffic.
3. Do not point any DNS or the wildcard cert at it yet.
4. Verify the HAProxy Ingress controller pods come up healthy and its
   `IngressClass` (e.g. `haproxy`) registers, via `kubectl get ingressclass`.

### Stage 1 — TCP passthrough parity check (isolated)
1. Configure HAProxy Ingress's TCP-services ConfigMap equivalent for a
   **test** SSH/SFTP-like TCP service (not the real
   `jupyterhub-ssh`/`jupyterhub-sftp` services yet) bound to the new,
   isolated LoadBalancer IP/port.
2. Confirm TCP passthrough actually works end-to-end against the test
   service before trusting it with real SSH/SFTP traffic.

### Stage 2 — Canary: one non-critical Ingress resource
1. Pick a low-traffic, non-critical `Ingress` resource (not JupyterHub,
   not Rancher) and add a second copy of it (or switch its
   `ingressClassName`) pointed at the HAProxy Ingress `IngressClass`,
   still served from the new isolated IP.
2. Rewrite its `nginx.ingress.kubernetes.io/*` annotations to the
   HAProxy Ingress equivalents (documented in
   [HAProxy Ingress's configuration keys reference](https://haproxy-ingress.github.io/docs/configuration/keys/)).
3. Verify: request routing, TLS termination against a copy of the
   wildcard cert, and any body-size/timeout annotation behavior if the
   canary resource uses them.
4. Leave this running in parallel for a real observation period (days,
   not minutes) before treating the canary as proven.

### Stage 3 — Wildcard cert and DNS cutover rehearsal
1. With the canary proven, prepare (but do not yet apply) the DNS/MetalLB
   IP change that would move production traffic from the ingress-nginx
   LoadBalancer IP to the HAProxy Ingress one — likely by re-pointing the
   existing service's IP or updating the wildcard DNS `A`/`CNAME` record,
   whichever this cluster uses today (check current DNS config before
   this stage; not re-derived here).
2. Confirm cert-manager can issue/renew the same wildcard cert against
   HAProxy Ingress's TLS termination path without a rekey/reissue that
   would cause a visible outage.

### Stage 4 — Migrate remaining Ingress resources, in order of increasing criticality
1. Migrate low/medium-criticality app Ingresses first, verifying each
   after cutover (same pattern as Stage 2).
2. Migrate JupyterHub's `Ingress` (HTTP/HTTPS) — verify a real JupyterHub
   session spawn and login through the new controller, and specifically
   verify the body-size/timeout equivalents by testing a large file
   upload.
3. Migrate the SSH (`jupyterhub-ssh`) and SFTP (`jupyterhub-sftp`) TCP
   passthrough definitions from ingress-nginx's `tcp-services` ConfigMap
   to HAProxy Ingress's equivalent, pointing at the **real** production
   LoadBalancer IP only after the isolated test in Stage 1 already proved
   the mechanism. Verify with a real SSH login and a real SFTP file
   transfer, not just a TCP connect check.
4. Migrate the Rancher UI `Ingress` last among the "real" workloads,
   since Rancher UI access is itself how you'd manage a cluster mid-crisis
   — verify UI login and that Fleet/GitRepo status is still visible
   through it.

### Stage 5 — Decommission ingress-nginx
1. Only after every `Ingress`/TCP-passthrough resource has been migrated
   and independently verified, and after a further observation period
   with the new controller as the sole active path (recommend at least
   one full week of normal teaching/research traffic).
2. Remove the `ingress-nginx` Fleet bundle
   (`system/networking/ingress-nginx/`) from this repo and let Fleet
   reconcile its removal.
3. Reclaim/release the old ingress-nginx MetalLB LoadBalancer IP only
   after DNS has fully cut over and propagated (respect old DNS TTLs).

## Rollback plan, per stage

- **Stages 0–2 (isolated/canary)**: trivial — nothing production-facing
  has changed. Delete the HAProxy Ingress bundle or the canary
  `Ingress`/annotation change; ingress-nginx was never touched.
- **Stage 3 (DNS/cert rehearsal)**: revert the DNS/IP change back to the
  ingress-nginx LoadBalancer IP; cert-manager continues issuing against
  the original path since it was never repointed for real traffic.
- **Stage 4 (per-resource migration)**: each `Ingress`/TCP-service
  migration is independently revertible — flip `ingressClassName` back
  (or restore the ConfigMap entry in ingress-nginx's `tcp-services`) for
  just the resource that broke, without needing to unwind the whole
  cutover. This is why migrating in increasing-criticality order matters:
  a failure on a low-criticality resource is cheap to revert and doesn't
  block the rest of the plan; a failure on JupyterHub or Rancher is
  reverted immediately and in isolation.
- **Stage 5 (decommission)**: do not treat this as reversible without
  effort — re-adding the `ingress-nginx` Fleet bundle after removal is
  possible (it's all in Git history), but plan for it to take real time to
  reconcile again. This is why Stage 5 waits for a full observation
  period first and is explicitly the last, most conservative step.

## Sources

- [Kubernetes ingress-nginx retirement announcement (Nov 2025)](https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/)
- [Kubernetes Steering/Security Committee follow-up statement (Jan 2026)](https://kubernetes.io/blog/2026/01/29/ingress-nginx-statement/)
- [Chainguard's ingress-nginx fork writeup](https://www.chainguard.dev/unchained/keeping-ingress-nginx-alive)
- [ingress2gateway reaches 1.0 (March 2026)](https://kubernetes.io/blog/2026/03/20/ingress2gateway-1-0-release/)
- [Gateway API: migrating from ingress-nginx](https://gateway-api.sigs.k8s.io/guides/getting-started/migrating-from-ingress-nginx/)
- [CNCF's own migration from ingress-nginx to Envoy Gateway (April 2026)](https://www.cncf.io/blog/2026/04/13/ingress-nginx-to-envoy-gateway-migration-on-cncf-internal-services-cluster/)
- [HAProxy Ingress configuration keys reference](https://haproxy-ingress.github.io/docs/configuration/keys/)
- [F5 NGINX Ingress Controller migration guide](https://www.f5.com/company/blog/nginx/migrating-from-community-ingress-controller-to-f5-nginx-ingress-controller)
- [NGINX Ingress Controller TransportServer resource docs](https://docs.nginx.com/nginx-ingress-controller/configuration/transportserver-resource/)
- [Traefik proxy-body-size compatibility issue](https://github.com/traefik/traefik/issues/12407)
