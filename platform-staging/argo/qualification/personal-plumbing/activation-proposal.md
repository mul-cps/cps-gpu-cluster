# Personal Argo activation proposal

Status: concrete private-backend preparation plan; **not executed**. Public route
takeover is blocked. The operator's default invocation only reads Deployment
metadata and renders focused resources. `activation-plan.json` records the exact
live resource versions, images, Secret references, callbacks, scopes and review
hash. `activation-resources.yaml` contains no credential values and no Ingress.

## Verified current boundary

- Gateway: single `compute-gateway` replica, `Recreate`, image digest
  `627f093c3c96038c7ecd9e9b99f0138198c23c9460cabb7bd11b19e94f465096`;
  runtime is mounted from `cps-compute-runtime`, with no `argoUi` configuration or
  reader projection. Both CPS/CIT canonical mapping counts are zero. Both
  workspace mapping counts and grant/workspace database row counts are zero.
- Proposed SDK: source `40b9525`, image digest `74cfb93dcf0078c116b88662b19b6ef14611f616e34ae3141f1fd24ceb3e12ce`.
- Dedicated frontend: source `373dc09c34e0add10cad1a3f52ae6cb593955d01`,
  image `ghcr.io/mul-cps/e2x-course-hub:qualification-native-assets-373dc09@sha256:c4df863a35a46d598cb319508b7d4e45caae3d1f9b71e24b2f1692c65e5f07bc`.
  Its installed module matches source, 118 source tests and 36 installed
  Argo/OAuth tests pass, UID is 10001 and `pip check` passes. The unchanged
  dedicated Dockerfile intentionally includes no SDK; the gateway SDK is separate.
  The earlier full-console startup receipt is supporting history only.
- CPS/CIT Hubs run JupyterHub 5.5.2. Their mounted `jupyterhub_config.py` loads
  `/usr/local/etc/jupyterhub/jupyterhub_config.d/*.py` after chart service/role
  setup and before `hub.extraConfig`. Existing configured console, observer and
  metrics API roles are preserved. CPS's SSH extraConfig appends a service;
  neither inspected Hub overwrites `load_roles` later.
- Normal-user service access is a filtered `access:services!service=<name>`
  scope; service OAuth requests no extra scopes. A service registration with
  explicit OAuth client ID/callback can omit a proxy URL. The frontend keeps its
  own `/argo` routes. [JupyterHub service documentation](https://jupyterhub.readthedocs.io/en/latest/reference/services.html).
- Installed `OAuthAuthorizeHandler` has `_accept_token_auth=False` and
  `_accept_cookie_auth=True`. An API token can authenticate Hub `/hub/api/user`
  for gateway HTTP qualification; it cannot replace a normal Hub session cookie
  at `/hub/api/oauth2/authorize`.

## Minimal compatible private preparation

1. Preserve the existing runtime Secret and create
   `cps-compute-runtime-personal-argo` from it in memory, adding only
   `argoUi={enabled:true,readerTokenFile:"/argo-reader/token",temporaryDirectory:"/tmp"}`.
   Existing canonical identities, grants, policy/GPU flags, storage and services
   are unchanged. Zero current mappings remain zero; they fail closed.
2. Use the qualified named TokenRequest/named Secret PATCH roles and unchanged
   rotator script. The existing `argo-artifact-reader` has only Workflow GET and
   GET of `cps-artifact-credentials`/`cps-artifact-ca` in `cps-workflows`. Precreate
   the reader Secret, run a bounded initial rotation, and start the gateway only
   after it succeeds. Rotate continuously after backend preparation succeeds.
3. Change only the gateway image, runtime Secret reference and reader mount.
   Preserve its current resource limits, PVC, projected API CA/token, policy,
   TLS, environment references and service identity.
4. Generate independent CPS and CIT OAuth credentials/cookies in memory. Store
   each OAuth credential in its Hub's new `personal-argo-oauth` Secret and the
   matching frontend Secret in `cps-compute`; keep cookies only in the frontend
   Secret. No admin console credential is reused.
5. Mount a new `personal-argo-registration` ConfigMap module and dedicated Secret
   in each Hub. Append the external service to existing services, and extend
   the default normal-user role with only that Hub's exact filtered access scope.
   Preserve existing scopes and roles, including idle culling and SSH. Register:

   | Source | Client ID | Callback | Added user scope |
   |---|---|---|---|
   | CPS | `service-cps-argo-ui` | `https://jupyterhub.dshl.unileoben.ac.at/argo/oauth_callback` | `access:services!service=cps-argo-ui` |
   | CIT | `service-cit-argo-ui` | `https://jhub.dshl.unileoben.ac.at/argo/oauth_callback` | `access:services!service=cit-argo-ui` |

   Registration survives a restart while these mounts remain. **Fleet durability
   is not qualified**: both Hub Deployments are Fleet-managed, so an independent
   mount patch can be reconciled away. No Fleet change is included in this scope.
6. Deploy both personal frontends privately. Add separate, narrow NetworkPolicies
   allowing only `cps-argo-ui`/`cit-argo-ui` to gateway TCP8000 and to the exact
   native Argo server TCP2746. Existing policies need no edits.

## Native asset compatibility qualified

Existing public CPS ingress strips `/argo` before sending requests to the native
server. Its internal certificate verifies for
`cps-argo-argo-workflows-server.cps-argo.svc.cluster.local`, using the existing CA.
Native JavaScript is served at `/main.f0ae7e3350b22f5d6dbf.js`;
`/argo/main.f0ae7e3350b22f5d6dbf.js` returns an HTML SPA fallback.

The new source/image and chart accept only explicit HTTPS root or `/argo`
backend paths, preserving the public `/argo` prefix and existing asset allowlist.
Seven chart tests pass. The live installed-image asset handler retrieved the
actual internal root index (200, base href `/argo/`) and JavaScript (200,
`text/javascript; charset=utf-8`) with CA and hostname validation and no upstream
credential headers. An arbitrary `/argo/private.txt` request returned 404 without
forwarding. The unmodified launcher independently returned unauthenticated 302
for page/API requests with the exact CPS client and callback.

This asset transport used an explicitly labeled loopback test fixture identity;
it proves no real Hub OAuth or normal-user ownership. The sole temporary narrow
Argo NetworkPolicy allowed only the exact scratch namespace AND QA frontend app
into TCP2746. It was deleted and absence verified after the receipt. The private
scratch frontend remains running with no public Ingress; backend asset access
requires a separately reviewed policy again. See `native-assets-qualified.json`.
The dry operator's existing-gateway TLS/index/base-href/JavaScript MIME preflight
also passed; it runs before any operator mutation.

## Public route takeover, only after privacy qualification

Keep `cps-argo/argo-ui` and `cps-argo/argo-artifact-downloads` unchanged until the
frontends are ready and actual normal-user owner tests pass. The current CPS
routes are `/argo(/|$)(.*)` and a more-specific artifact-download regex. Both must
be removed/replaced in the reviewed takeover; adding a Prefix ingress alone
leaves a bypass. Preserve the complete old ingress objects/UIDs for rollback.

The replacement route must forward `/argo` unchanged to `cps-argo-ui` on the CPS
host and `cit-argo-ui` on the CIT host, including callback/login, page/assets,
`/argo/api/*`, and `/argo/artifact-files/*`. Do not strip the prefix, inject any
operational bearer token, or forward raw native APIs. The native asset backend
must be an independent internal HTTPS URL; using public CPS `/argo` after
takeover would recurse. TLS stays on the existing Hub origins; no DNS is added.

Existing source-managed route reconciliation can resurrect the bypass. Therefore
takeover also requires reviewed reconciliation persistence and negative tests of
the exact legacy URLs after reconciliation. This proposal contains no route
mutation, public ingress or Fleet change.

## Qualification and rollback

`fixture_hub_users.py` prints exact proposed CPS Hub API requests by default. A
reviewed run may create two disposable normal users, no servers or homes, and
900-second normal-user API tokens stored only in a scratch Secret. It requires an
operator-supplied private admin token file for fixture administration; that token
is never used as a visitor. Cleanup deletes only the reviewed fixture names after
confirming no active servers and requiring its matching sanitized creation receipt.
Actual Hub `add_user` hooks must be reviewed for home-provisioning side effects
before the script permits creation. No fixture operation has been executed.

`ownership_http.py` first verifies each visitor's actual Hub `/user` response is
a matching non-admin user, then tests own list/detail and foreign/unknown 404 via
actual gateway HTTP. Its `qa_runtime` function clones configuration for an empty
`/tmp/qa-state` database, maps only fixture users in QA, disables JobSet/lifecycle/
shutdown/storage Kubernetes clients, and uses a separately provisioned read-only Argo
token file. QA must run with 1 CPU/512MiB, a 300-second Pod deadline, no API token
automount or Pod-creation RBAC, no PVC/production database, and no public ingress.
The read-only Argo credential needs Workflow GET/LIST only for controlled fixture
records; no operational Argo credential is cloned. Use suspended, annotated,
CPU-only fixture Workflow records if real owner records are needed, and remove
only their exact created UIDs after tests. Creation of Hub users or Workflow
fixtures remains a separate root-reviewed step. `ownership_http.py --extended` requires actual own log content and HEAD/GET
artifact bytes matching a controlled fixture hash, foreign/unknown 404, and
read-only terminate denial even for an owner. It first verifies actual normal
Hub identity, rejects admin substitution, bounds responses and refuses HTTP
redirects so bearer tokens cannot be forwarded to another URL. Missing own
artifacts/provenance fail qualification rather than producing a passing receipt.
Actual HTTP tests and the complete bounded QA runtime startup remain pending.
On 2026-10-08, two real normal CPS Hub fixture users and visitor tokens were
verified without servers/homes. Two snapshot and intent pairs were stored in
the actual S3 service. Both CPU Workflows were denied before Pod creation by
the existing executor mount-path admission boundary. The task stopped when
isolation became the user priority; all new fixtures, users, tokens and objects
were removed. `real-native-stopped-receipt.json` records this incomplete gate. The published SDK fixes
artifact access to its reviewed native Argo/S3 endpoints, bucket and Secret names;
a separate fake artifact backend cannot qualify that integration. Service-side
Secret references may be consumed by a separately approved real fixture run,
without printing or cloning production credential data.
The configuration helper is preparation code, not a qualified live QA gateway.

Preparation requires verified, matching gateway-state and Hub database/config
backup evidence, a new sanitized preparation journal, and root-reviewed actual
normal-Hub-token owner privacy plus canonical/optional alias inventory evidence.
Private preparation creates the registration needed for later real browser
verification and does not require that prior OAuth result. Public activation
remains separate and requires actual browser Hub OAuth, full owner/foreign
logs/artifacts/write-denial coverage and reviewed route/Fleet persistence.
The user explicitly skipped browser verification this session, then prioritized
isolation before this preparation ran. No production Hub/gateway/ingress changes
occurred. The browser gate remains false. Original runtime Secret remains untouched. On rollout failure,
the operator restores only its owned gateway image/config/reader fields and Hub
mounts from fresh objects with resourceVersion CAS; unrelated edits are retained.
New resources remain private/dormant for explicit cleanup. After a completed preparation, `--rollback-reviewed-sha256` with the matching
journal suspends the rotator, restores owned fields and verifies Hub/gateway restart.
The journal contains only images, source labels and changed-resource names. Concurrent
changes to the owned gateway image/runtime cause rollback to stop for review. Database restore is a separate controlled action if needed.

Before public takeover, qualify separate real normal Hub sessions, client access
after restart, cookie expiry/logout, PKCE/callback replay, own-only list/detail/
watch/logs/downloads, foreign/unknown denial, SSE reconnect and slow-client/shared
transfer bounds. Gateway token HTTP evidence does not complete the human-browser
gate. No production canonical identities, grants, GPU flags or Moodle settings
are changed by these preparation scripts.

```sh
# Read-only proposal generation:
python -B platform-staging/argo/qualification/personal-plumbing/activation_operator.py

# Only after root reviews the exact plan hash, compatible assets and backups:
python -B platform-staging/argo/qualification/personal-plumbing/activation_operator.py \
  --prepare-reviewed-sha256 <reviewed-hash> --backup-evidence /private/verified-backups.json \
  --receipt-file /private/personal-argo-preparation-receipt.json
```
