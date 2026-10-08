# Personal Argo deployment boundary

Status: packaged source and deployment wiring; production activation pending.

The optional `personalArgo` chart feature creates independent CPS and CIT Hub
OAuth services. Each accepts its actual browser visitor and forwards only the
existing owner-filtered compute API. It requires the compute gateway's explicit
`argoUi` configuration and stays disabled by default. Existing operational Argo
ingress is unchanged by these defaults.

Application behavior and configuration are documented in
[`cps-compute` personal access](https://github.com/mul-cps/cps-compute/blob/feat/gateway-release-qualification/docs/argo-user-access.md)
and [the dedicated Hub service](https://github.com/mul-cps/e2x-course-hub/blob/feat/personal-argo-launcher/docs/argo-user-service.md).
The launcher image uses `python -m e2x_course_hub.cps.argo_app`; it has no course
database, Kubernetes token or administrative console credential.

## Activation sequence

1. Qualify and pin the compute and dedicated service image digests. Leave both
   production GPU qualification flags and Moodle unchanged.
2. Verify the existing `argo-artifact-reader` ServiceAccount in `cps-argo` has
   only Workflow GET and GET of the two artifact credential/CA Secrets in
   `cps-workflows`. The chart never grants new reader privileges.
3. Precreate the `cps-argo-ui-reader` Secret in `cps-compute`, with key `token`.
   Apply the optional `argo-ui-reader.yaml` objects, then run a one-off Job from
   its CronJob and verify success before starting the gateway. The rotator can
   request a 900-second token only for that named reader and patch only that
   named Secret. It has no general Secret read/create or workload privileges.
   Tokens rotate every five minutes and are never written to logs or Git.
4. Set the operator-owned runtime JSON's `argoUi` to
   `{"enabled":true,"readerTokenFile":"/argo-reader/token","temporaryDirectory":"/tmp"}`.
   Enable `gateway.argoUi` and retain the existing Kubernetes CA projection.
   Backup the current runtime/database and verify the new packaged gateway
   before deploying either personal frontend. Changing a Helm flag alone does
   not alter the separately managed runtime JSON.
5. Register `cps-argo-ui` and `cit-argo-ui` on their respective Hubs, using
   separate generated service tokens, exact HTTPS callbacks ending in
   `/argo/oauth_callback`, and no additional OAuth allowed scopes. Grant only
   each Hub's `access:services!service=<name>` scope to its reviewed normal-user
   role/group. The JupyterHub service registration must survive restart.
6. Precreate distinct `cps-argo-ui-oauth` and `cit-argo-ui-oauth` Secrets, each
   containing `oauth-client-secret` and `cookie-secret`. Each cookie secret is
   independently generated and at least 32 characters. Deploy one replica per
   frontend with its public HTTPS origin and public Hub HTTPS API URL.
7. Verify the pinned native Argo 3.7.18 asset backend serves `/argo/` and
   `<base href="/argo/">`. Use its explicit trusted CA file. For the current
   public asset backend, set `nativeCaFile` to
   `/etc/ssl/certs/ca-certificates.crt`; private operator-signed Argo uses
   `/trust/ca.crt`. No raw native API is forwarded through a frontend.
8. Qualify separate normal-user browser sessions, OAuth login/logout/expiry,
   callback replay, native assets/navigation, own-only list/detail/watch/logs
   and input/output downloads, and foreign/unknown API denial. Check SSE
   reconnect, slow clients and shared transfer capacity before routing normal
   users to the service. A port-forward or crafted server fixture is supporting
   evidence, not a completed human-browser privacy gate.

The chart validates image digests, exact ingress/origin correspondence, fixed
CPS/CIT client identities, HTTPS backend paths, and the gateway-adapter flag.
Its read-only frontend root and absent API token mount do not replace application
authorization tests. Public DNS, TLS, Hub registration and canonical person
mapping remain explicit operator dependencies. Do not reuse the operational
viewer token as a personal login.

Deployment checks:

```sh
python -B scripts/compute-platform/test_personal_argo_chart.py -v
helm lint platform-staging/chart
```
