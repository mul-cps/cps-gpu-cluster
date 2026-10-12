# Root recipe: personal Argo activation

This package prepares the existing owner-filtered Argo frontend. Root owns
fresh captures, credentials, live validation and rollouts. `prepare.py` is
offline only: it runs local Helm, creates a fresh private output directory and
never calls Kubernetes or any HTTP API. The gateway and both administrative
console images remain unchanged.

The frontend image is pinned to
`ghcr.io/mul-cps/e2x-course-hub@sha256:fd8ba6c022497f06b6f4b42fc0b37b9cf164f3136ac204d753d82a20fdef3a7a`,
published by Root from admin source `fb6262f7d5d4799c9dca0a2e5d868e05978a4321`.
The full admin CPU suite passed 179 tests. This source accepts the private
native asset backend at its HTTPS root; `/argo/main...js` on that native server
returns the SPA fallback instead of JavaScript. Installed source SHA256:
`argo_service.py` = `6934f389d653218bfbc1d00c3c06e2df2af3128ec92a0e7d74c89728466f6ee0`,
`argo_app.py` = `d59166c3023920ebf2bce2f4d3f82caf5e25836b635e2425d290943ffb54b06f`.

## Prepare from current captures

Root stages the following fresh JSON objects with mode `0600`, in a private
directory. Individual objects or Kubernetes `List` captures are supported:

| Input key | Actual resource |
| --- | --- |
| `policy_configmap` | `cps-compute/compute-policy` ConfigMap |
| `gateway_deployment` | `cps-compute/compute-gateway` Deployment |
| `gateway_runtime_secret` | `cps-compute/cps-compute-runtime` Secret |
| `cps_hub_secret` | `jupyterhub/hub` Secret |
| `cps_hub_deployment` | `jupyterhub/hub` Deployment |
| `cit_hub_secret` | `cit-jhub/hub` Secret |
| `cit_hub_deployment` | `cit-jhub/hub` Deployment |
| `cit_existing_secret` | `cit-jhub/jupyterhub-secrets` Secret, required when mounted |
| `ca_files` | Root-supplied public Hub, compute and native Argo trusted CA PEM bundles |

Copy `inputs.example.json` to a private `argo-inputs.json`, set its absolute
paths, and give it mode `0600`. `ca_files` must include the public trust bundle
needed by both Hub HTTPS endpoints, the gateway CA and the native Argo CA.
The preparer validates PEM syntax and deduplicates the certificates into a
separate `cps-personal-argo-upstream-ca` ConfigMap; it does not change the
gateway's existing CA ConfigMap. Root verifies the actual upstream trust.

From this worktree:

```sh
python platform-staging/argo/personal-activation-20261012/prepare.py \
  --inputs /private/argo-inputs.json --output /private/argo-prepared
```

The fresh output directory is mode `0700`; every file is mode `0600`. Stdout
contains a sanitized receipt. Raw parser input and private values are never
printed on failure. No credential files are generated or printed. Outputs:

| File | Purpose |
| --- | --- |
| `resources.yaml` | Separate CA ConfigMap, narrow NetworkPolicies, two private frontends/Services, named reader-rotation RBAC and suspended CronJob; no Ingress |
| `reader-rbac.yaml` | New `cps-argo/cps-personal-argo-reader` SA and read-only Role/Binding in `cps-workflows`; no Secret permissions |
| `cps-hub-secret.patch.json`, `cit-hub-secret.patch.json` | CAS replacement of only `hub` Secret `data["values.yaml"]` |
| `cps-hub-deployment.patch.json`, `cit-hub-deployment.patch.json` | CAS append of only the named OAuth environment entry to the `hub` container |
| `gateway-runtime.patch.json` | CAS replacement of only `data["runtime.json"]`, merging only `argoUi` |
| `gateway-deployment.patch.json` | CAS append of only the reader volume and mount to the named gateway container |
| `cps-hub-values.yaml`, `cit-hub-values.yaml` | Private merged values for review and persistence through the owning Hub release |
| `render-values.yaml`, `receipt.json` | Captured-policy render input and sanitized preparation receipt |

The generated policy is taken from the captured ConfigMap, and its name must
match the gateway's actual `policy` volume. The rotator reuses the captured
immutable gateway image, while frontend Deployments use the dedicated `fd8`
image. Do not apply the complete platform chart or historical activation tool.

Hub persistence uses `hub` Secret `data["values.yaml"]`, parsed by the existing
z2jh loader, then sorted `hub.extraConfig`. The preparer merges one
`99-personal-argo-service` key and one environment entry, preserving all native
hooks, services, roles and other values. CPS `extraEnv` remains a list; CIT
remains a dictionary. CIT's later-loading `existing-secret/values.yaml` is
rejected if present, so it cannot silently override this merge. Deployment
environment entries also need the separate patches: editing stored Helm
values alone does not inject an environment variable into a running Pod.

All mutation patches test captured UID and resource version. Secret patches
also test the original encoded data value. A conflict requires fresh captures
and a new output directory. The preparer rejects existing owned keys, mounts
or registrations. Existing services created by another custom extraConfig
snippet are also rejected by the appended Hub code at startup. Root checks
new resource names are unused before `kubectl create`.

## Root apply order

1. Review the private merged files and patches. Preserve originals for
   rollback. Verify actual native TLS/index/base href/JavaScript MIME and the
   existing gateway `artifacts` and `argo_ca_file` prerequisites. The preparer
   does not qualify live trust, Kubernetes permissions or browser access.
2. Root creates independent OAuth/cookie files for each Source. Cookies must
   be stable and at least 32 characters. Frontend Secrets are
   `cps-compute/cps-argo-ui-oauth` and `cps-compute/cit-argo-ui-oauth`, with keys
   `oauth-client-secret` and `cookie-secret`. Mirror only the matching OAuth
   file into the owning Hub's `personal-argo-oauth`, key `oauth-client-secret`.
   Create `cps-compute/cps-argo-ui-reader` from an initially empty private token
   file. Example Root commands (all referenced files are supplied by Root):

   ```sh
   kubectl -n cps-compute create secret generic cps-argo-ui-oauth \
     --from-file=oauth-client-secret=/private/cps-argo-oauth \
     --from-file=cookie-secret=/private/cps-argo-cookie
   kubectl -n jupyterhub create secret generic personal-argo-oauth \
     --from-file=oauth-client-secret=/private/cps-argo-oauth
   kubectl -n cps-compute create secret generic cit-argo-ui-oauth \
     --from-file=oauth-client-secret=/private/cit-argo-oauth \
     --from-file=cookie-secret=/private/cit-argo-cookie
   kubectl -n cit-jhub create secret generic personal-argo-oauth \
     --from-file=oauth-client-secret=/private/cit-argo-oauth
   kubectl -n cps-compute create secret generic cps-argo-ui-reader \
     --from-file=token=/private/empty-reader-token
   ```

3. Create the focused resources, then run one bounded rotation while the
   schedule remains suspended:

   ```sh
   kubectl create -f /private/argo-prepared/reader-rbac.yaml
   kubectl create -f /private/argo-prepared/resources.yaml
   kubectl -n cps-compute create job personal-argo-initial-rotation-20261012 \
     --from=cronjob/argo-ui-token-rotator
   kubectl -n cps-compute wait --for=condition=complete \
     job/personal-argo-initial-rotation-20261012 --timeout=120s
   ```

   Verify the **actual token's** identity, audience, expiry and permissions
   privately using in-cluster SelfSubjectAccessReview, including forbidden
   mutation and Secret reads. The new reader allows workflow get/list/watch,
   pod get/list and pod logs get only in `cps-workflows`. It does not modify
   `argo-artifact-reader`; artifact authorization remains separate. Do not
   accept an impersonation `kubectl auth can-i` result as token qualification.
4. Apply each freshly fenced Hub patch. These Deployment patches trigger a
   rollout while retaining all native volumes, hooks and images:

   ```sh
   kubectl -n jupyterhub patch secret hub --type=json \
     --patch-file=/private/argo-prepared/cps-hub-secret.patch.json
   kubectl -n cit-jhub patch secret hub --type=json \
     --patch-file=/private/argo-prepared/cit-hub-secret.patch.json
   kubectl -n jupyterhub patch deployment hub --type=json \
     --patch-file=/private/argo-prepared/cps-hub-deployment.patch.json
   kubectl -n cit-jhub patch deployment hub --type=json \
     --patch-file=/private/argo-prepared/cit-hub-deployment.patch.json
   ```

   Persist the reviewed merged Hub values through the owning release/GitOps
   path so reconciliation retains them. Verify Hub clients and source-specific
   user scopes after restart before enabling the gateway adapter.
5. After validating the rotated credential, apply only the gateway runtime
   and mount patches. The mount patch triggers the required gateway rollout:

   ```sh
   kubectl -n cps-compute patch secret cps-compute-runtime --type=json \
     --patch-file=/private/argo-prepared/gateway-runtime.patch.json
   kubectl -n cps-compute patch deployment compute-gateway --type=json \
     --patch-file=/private/argo-prepared/gateway-deployment.patch.json
   kubectl -n cps-compute rollout status deployment/compute-gateway --timeout=120s
   ```

   Verify installed runtime bytes and readiness, then enable the schedule and
   verify renewed tokens are reread through the directory mount:

   ```sh
   kubectl -n cps-compute patch cronjob argo-ui-token-rotator --type=merge \
     --patch '{"spec":{"suspend":false}}'
   ```

6. Verify private frontend startup and native asset MIME, then publish only
   the reviewed `/argo` routes to the owning personal frontends. Require real
   human OAuth, owner versus foreign workflow/log/artifact access, absent
   object/write/issuer negatives, SSE and actual artifact bytes. Empty lists
   and unauthenticated redirects do not complete own-user acceptance.

The browser entry for each Hub is `/argo/workflows/cps-workflows?limit=50` on
`https://jupyterhub.dshl.unileoben.ac.at` or `https://jhub.dshl.unileoben.ac.at`.
Ingress forwards `/argo` unchanged to `cps-argo-ui:8080` or `cit-argo-ui:8080`
in `cps-compute`. OAuth callbacks are `<owning-public-origin>/argo/oauth_callback`.
The operational Argo server remains the private asset/backend service;
browser APIs use the gateway owner adapter. The frontend requires its signed
OAuth cookie, a human user of the owning Hub and the dedicated
`access:services!service=cps-argo-ui` or `access:services!service=cit-argo-ui`
scope. Native asset requests carry no credentials. No service `url` is needed
in Hub registration because the explicit client and callback register the
external service.

Rollback restores only owned fields from current resources: suspend rotation,
restore the prior `argoUi` key, remove the reader mount and added Hub keys/env,
and restore the prior public route. Preserve concurrent native/runtime changes.
Fleet persistence and real browser privacy remain Root's live gates.
