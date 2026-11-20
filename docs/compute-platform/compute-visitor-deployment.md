# Compute visitor deployment

Status: staged / disabled by default. These manifests have not activated either
service or registered OAuth clients. They do not establish production readiness.

The two frontends provide ordinary Hub users with a dedicated Compute OAuth
session. They run the same released `cps-compute-visitor` artifact with separate
configuration and credentials. See the canonical [application configuration and
authentication contract](https://github.com/mul-cps/cps-compute/blob/84d7c93/packages/visitor/README.md).
Application version 0.1.0 qualifies Hub 5.5.2; Hub 6 qualification is separate.

## Rendered resources

| Source | Deployment and Service | Hub proxy namespace | Public service prefix |
|---|---|---|---|
| CPS | `cps-compute-ui` | `jupyterhub` | `/services/cps-compute-ui/` |
| CIT | `cit-compute-ui` | `cit-jhub` | `/services/cit-compute-ui/` |

All new workloads, Services and NetworkPolicies live in `cps-compute`. Each
frontend has one replica with a Recreate strategy, a ClusterIP Service on 8080,
no database, no mounted service-account token and no Kubernetes permissions.
It receives only its two dedicated OAuth/cookie Secret keys and public CA
ConfigMaps. It does not receive console, policy, Hub administration, storage or
Argo credentials. Its image must contain the `cps-compute-visitor` entry point.

The memory request is 2 GiB and limit is 4 GiB per frontend. These values reserve
space for the released eight active upstream requests, 72 MiB request and 100 MiB
response limits, copied buffers and Python/TLS overhead. The application buffers
payloads in memory. This sizing is a staging default; concurrent load and excess
incoming connections still require runtime qualification before promotion.
Changing the application's bounds requires reviewing these resource values.

## Required existing configuration

Set both the chart's existing `enabled` switch and `computeVisitor.enabled` to
true only in a reviewed activation. Each selected source additionally needs its
own `enabled: true`; a disabled source creates no resources or network grants.
The chart's existing policy, Gateway and console artifact requirements continue
to apply. The example below is incomplete until the image and address placeholders
are replaced with reviewed values:

```yaml
computeVisitor:
  enabled: true
  image: ghcr.io/mul-cps/cps-compute-visitor@sha256:<reviewed-64-hex-digest>
  port: 8080
  gatewayCaConfigMapRef: cps-compute-gateway-ca
  sources:
    cps:
      enabled: true
      publicOrigin: https://jupyterhub.dshl.unileoben.ac.at
      hubApiUrl: https://jupyterhub.dshl.unileoben.ac.at/hub/api
      secretRef: cps-compute-ui-oauth
      hubCaConfigMapRef: cps-hub-public-ca
      hubHttpsCidrs: ["<reviewed-CPS-public-IPv4>/32"]
    cit:
      enabled: true
      publicOrigin: https://hub.dshl.unileoben.ac.at
      hubApiUrl: https://hub.dshl.unileoben.ac.at/hub/api
      secretRef: cit-compute-ui-oauth
      hubCaConfigMapRef: cit-hub-public-ca
      hubHttpsCidrs: ["<reviewed-CIT-public-IPv4>/32"]
```

Each Secret must already exist in `cps-compute`, with `oauth-client-secret` and
`cookie-secret` keys. Keep its randomly generated cookie secret stable across
restarts and at least 32 characters long. Both secrets and their contents must
be distinct between CPS and CIT. Never reuse a console or control credential.
The chart rejects known existing console/control Secret references and reuse
between the two enabled frontends. It cannot inspect existing Secret contents;
the application validates required secrets at startup. Secret material belongs
in the existing secret-management system, outside Git.

Each CA ConfigMap must already exist in `cps-compute` with a `ca.crt` key. The
Gateway CA reference must exactly match the existing `gateway.caConfigMapRef`.
The fixed Gateway URL is the existing
`https://compute-gateway.cps-compute.svc.cluster.local:8000` endpoint. Gateway
port changes require separate network qualification; the template rejects them
while this visitor boundary is enabled.
The Hub API must be the source's exact public HTTPS origin plus `/hub/api`.
The authorization endpoint is derived from that URL. Both upstream connections
retain certificate and hostname verification.

## Network and Hub integration gates

The frontends listen only on 8080. Ingress is restricted to Pods labelled
`app: jupyterhub, component: proxy` in that source's Hub namespace. Both the
service landing page and `oauth_callback` pass through the existing Hub proxy;
this component creates no standalone Ingress.

Egress permits the labelled cluster DNS service on TCP/UDP 53, `compute-gateway`
Pods on the existing Gateway port and only the reviewed public Hub host CIDRs
on TCP 443. IPv4 entries must be individual `/32` hosts and IPv6 entries `/128`
hosts. Resolve the actual public Hub endpoint addresses at activation; retain
only reviewed addresses and update them with DNS changes. Verify how the actual
CNI applies these IP rules around ingress VIP DNAT/hairpin routing. Rendered
NetworkPolicies alone do not prove that path works. Additional policies narrowly
permit these visitor Pods into the Gateway, which the existing namespace-wide
ingress policy otherwise excludes.

Root's separate Hub integration must complete all of the following before use:

1. Register `cps-compute-ui` and `cit-compute-ui` as dedicated services, pointing
   at `http://<source>-compute-ui.cps-compute.svc.cluster.local:8080`.
   Use OAuth clients `service-cps-compute-ui` / `service-cit-compute-ui` and exact
   callbacks `https://<source-public-host>/services/<source>-compute-ui/oauth_callback`.
2. Set each client's allowed scopes to
   `access:services!service=<source>-compute-ui` and `read:users:name!user`.
   Add only its own service access scope to the ordinary user role, preserving
   `self`. Do not grant admin-console access or unfiltered user scopes.
3. Verify the existing Hub proxy's effective egress policy permits the matching
   visitor Service on TCP 8080. These manifests do not alter proxy egress or
   existing Hub/API policies, since doing so can affect unrelated Hub traffic.
   Verify the public ingress accepts the 72 MiB framed request limit and has
   read/send timeouts longer than the application's 90-second download timeout.
   Retain the qualified OAuth callback header-buffer configuration.
4. Update the released Hub adapter's trusted browser URL and the addon prefix
   validation together to `/services/<source>-compute-ui/api/compute/v1/`.
5. Qualify certificate-verified Hub/Gateway connectivity, the proxied OAuth
   callback and ordinary human login on each Hub. Exercise account/profile/
   session reads, snippets, workloads and notebook submission; verify two users
   retain separate identities and cannot read each other's jobs or artifacts.
   Test revocation, XSRF, unauthorized paths and concurrent payload limits.
6. Publish and record immutable release/qualification artifacts before promoting
   this disabled staging chart through the controlled GitOps deployment path.

The chart neither registers Hub services nor changes role grants, live secrets,
application settings, personal notebooks, GPU policy or native allocation state.

## Local verification

```sh
python -m pytest -q tests/compute_platform/test_compute_visitor_chart.py
helm lint platform-staging/chart
helm template compute platform-staging/chart
```

The final command renders nothing with the default disabled values. Render tests
use deliberately synthetic immutable images and documentation-only address
ranges; those fixtures are not deployable artifacts or live qualification.
