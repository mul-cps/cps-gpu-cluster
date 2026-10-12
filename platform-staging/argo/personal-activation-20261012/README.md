# Root recipe: personal Argo activation

This package prepares the existing owner-filtered Argo frontend. Root owns
fresh captures, credentials, live validation and rollouts. `prepare.py` is
offline only: it runs local Helm, creates a fresh private output directory and
never calls Kubernetes or any HTTP API. The gateway and both administrative
console images remain unchanged.

The current private frontend image is
`ghcr.io/mul-cps/e2x-course-hub@sha256:7e1509969062bc3b0855671c12f181548494cb6095669b949e0426a5e74c2b2e`
from admin source `0e4f433d19c4b6ca1f0e26ab5293ab34a064eb40`.
The gateway inventory is
`ghcr.io/mul-cps/cps-compute@sha256:d3f744bd6b0982587be1dbaf0bae3dccd507be6b05ca9d5e7ebbbf8d8695622e`
from compute source `918b5a1df996bdc57cf0af2bb95fb4ed20892971`.
Root captured their dated deployment in
[current-deployment-receipt.json](current-deployment-receipt.json).
The separate Source54 console image remains
`ghcr.io/mul-cps/e2x-course-hub@sha256:0b48372b05346adfe3e2c018bcfb75c4914b111f44ac59be36f1bcd14f6cdd5f`.
These values are an inventory and focused render input. The preparer retains
its captured gateway image and never replaces a console image. Both prepared
public ingress settings remain false. Do not apply the complete platform chart
or rerun the fresh-activation preparer against already registered resources;
it deliberately rejects existing owned settings. Current image rollouts need
Root's fresh fenced changes preserving every other field.

The reviewed package at `fe59e035c151fcc919be1ec8c31d6e906ea60109` supplied
the preparer and historical empty-list acceptance. Its historical fixture was
a Root-signed cookie containing a real Hub user token; it was not human browser
OAuth. The current [partial private acceptance](current-private-partial-acceptance.json)
records owned list/detail 200 and artifact HEAD 200, but artifact GET 502 and
logs 503 for both notebook runs. Foreign and missing detail/log/artifact
requests returned 404. HEAD success does not qualify artifact byte delivery.
This is a dated observation from Root's protected receipt, not a current
availability assessment. Actual output bytes, logs, human browser OAuth and
public personal routing remain open. See [source-acceptance.json](source-acceptance.json).

The current policy is `0.1.2`,
`sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0`,
with the locally qualified immutable CPU runner `1fab0663…` permitted only by
`batch-cpu`. The [CPU policy package](../../gpu/native-group-pilot/qualification/cpu-runner-policy-20261012/README.md)
preserves the original hardware reports and exact two-group GPU approvals.
The [historical custody receipt](cpu-policy-historical-custody-receipt.json)
records Root's node ConfigMap `cps-native-node-cpu-v2-d48f6553ed03-h32`:
all 28 prior history pins plus four actual released lifetimes, without runtime
source changes or old-policy relabeling. Ledger and journal contents are not
part of this source inventory and must never be overwritten by it.
General GPU access, wider fleet qualification and the full release stay
unqualified.

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
immutable gateway image, while frontend Deployments use the current dedicated private
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
