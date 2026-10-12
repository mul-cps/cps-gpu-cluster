# Root recipe: personal Argo activation

This package prepares the existing owner-filtered Argo frontend. Nothing here
has been applied. Root owns credentials, image publication, live reads and
rollouts. The gateway and both administrative console images remain unchanged.

The browser entry for each Hub is `/argo/workflows/cps-workflows?limit=50` on
`https://jupyterhub.dshl.unileoben.ac.at` or `https://jhub.dshl.unileoben.ac.at`.
Ingress must forward `/argo` unchanged to `cps-argo-ui:8080` or
`cit-argo-ui:8080` in `cps-compute`. OAuth callbacks are exactly
`<owning-public-origin>/argo/oauth_callback`. The operational Argo server stays
the private HTTPS asset/backend service; browser API requests go through the
existing gateway owner adapter.

The frontend accepts its signed OAuth cookie, a human user of the owning Hub,
and the dedicated `access:services!service=cps-argo-ui` or
`access:services!service=cit-argo-ui` scope. It forwards the visitor's token to
the gateway. Browser Authorization headers cannot replace the user. Native
asset requests contain no credentials. No service backend `url` is needed in
Hub registration: the explicit OAuth client and callback register an external
service, and the public ingress handles routing.

## Build the personal-only frontend

The deployed admin image `5c13c292...` contains the launcher, but its native URL
validator rejects the existing internal asset server's root URL. The patch in
`/tmp/e2x-personal-argo-native-root-20261012` restores the reviewed HTTPS root
or `/argo` backend paths. It changes no administrative application or GPU code.
Twenty-two service tests and ten launcher tests passed with JupyterHub 5.5.2.

Root builds and publishes this worktree with the existing dedicated Dockerfile:

```sh
cd /tmp/e2x-personal-argo-native-root-20261012
podman build --file Dockerfile.argo-service \
  --build-arg SOURCE_REVISION="$(git rev-parse HEAD)" \
  --tag ghcr.io/mul-cps/e2x-course-hub:personal-argo-native-root-20261012 .
podman push ghcr.io/mul-cps/e2x-course-hub:personal-argo-native-root-20261012
```

Record the registry digest, installed `argo_service.py` hash, launcher help and
`pip check` from that exact image. Fill `personalArgo.image` with the resulting
digest reference. It is intentionally empty in `values.yaml`, so rendering
fails until a new frontend pin is supplied. Do not reuse the existing `5c` pin.
The source commit is `fb6262f7d5d4799c9dca0a2e5d868e05978a4321`; expected file
SHA256 values are `6934f389d653218bfbc1d00c3c06e2df2af3128ec92a0e7d74c89728466f6ee0`
for `argo_service.py` and
`d59166c3023920ebf2bce2f4d3f82caf5e25836b635e2425d290943ffb54b06f` for the unchanged
`argo_app.py` launcher.

The rotator image alone uses the existing gateway digest
`05fcb594db96642d8aab5556e6fa5cedaad2329773668fd03e6866b1aba1a39b`, observed in
`native20-controlled-cycle-20261012/status-after-hardware-v1/cps-compute-compute-gateway.json`
at October 12 11:02 UTC. Its pin is unrelated to the node-agent image.

## Render the small nonpublic resource set

From the cluster worktree, with `ARGO_FRONTEND_IMAGE` set to the reviewed new
digest, render only these two existing templates. The generated repository
policy is a render prerequisite; these output resources contain no policy or
native runtime replacement.

```sh
helm template personal-argo platform-staging/chart \
  --values platform-staging/argo/personal-activation-20261012/values.yaml \
  --set-file policyJson=compute-policy/generated/policy.json \
  --set-string policyHash=sha256:051cd754210af2830d67968eea898f674a55ff66f5c88b3db95dff205f04e33d \
  --set-string personalArgo.image="$ARGO_FRONTEND_IMAGE" \
  --show-only templates/argo-ui-reader.yaml \
  --show-only templates/personal-argo.yaml \
  > /private/personal-argo-resources.yaml
```

Review the output and `network-policies.yaml`. No public Ingress is rendered;
the rotator is suspended. Reject name collisions rather than overwriting an
existing registration, Secret, rotator, frontend or NetworkPolicy. The focused
set consists of the reader rotator's named RBAC, its ServiceAccount/CronJob, two
frontends and Services, and narrow ingress policies. Do not apply the complete
platform chart or the historical `activation_operator.py prepare` command.

## Protected setup and activation order

1. Freshly capture the actual gateway runtime and template, both Hub service/role
   models and reconciled Hub values. Verify the current pins, namespaces, CA
   contents, native asset TLS/index/base href/JavaScript MIME, and the existing
   `cps-argo/argo-artifact-reader` read-only authorization. The older root asset
   receipt is supporting evidence, not a current live acceptance claim. Confirm
   the adapter prerequisites `artifacts` and `argo_ca_file` already exist in the
   actual gateway runtime. Preserve private originals for rollback.
2. Root provisions independent OAuth and cookie files for each Source in private
   custody. Cookie secrets are stable and at least 32 characters. Create
   `cps-argo-ui-oauth` and `cit-argo-ui-oauth` in `cps-compute` with keys
   `oauth-client-secret` and `cookie-secret`. Mirror only the matching OAuth file
   into each owning Hub's `personal-argo-oauth` Secret, key `oauth-client-secret`.
   For example, using Root's staged files:

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

   The reader token file starts empty. Create it privately; it is populated only
   by the existing bounded TokenRequest rotator. These commands print object
   names, not credential values. Keep raw Secret captures private.
3. Root creates the reviewed nonpublic resources and narrow NetworkPolicies,
   leaving the schedule suspended. Run one bounded initial rotation and verify
   the actual token's identity, audience, expiry, permissions and readable mount
   privately before enabling the gateway adapter:

   ```sh
   kubectl create --filename /private/personal-argo-resources.yaml
   kubectl create --filename platform-staging/argo/personal-activation-20261012/network-policies.yaml
   kubectl -n cps-compute create job personal-argo-initial-rotation-20261012 \
     --from=cronjob/argo-ui-token-rotator
   kubectl -n cps-compute wait --for=condition=complete \
     job/personal-argo-initial-rotation-20261012 --timeout=120s
   ```

4. Merge `cps-hub-values-fragment.yaml` and `cit-hub-values-fragment.yaml` into
   the owning Hub's current reconciled values. **Append the one `extraEnv` entry
   by name and merge the one `extraConfig` key; do not pass the fragment as a
   standalone Helm override that replaces the existing environment list.**
   Preserve all prior services, roles, environment, volumes, native reservation
   hooks and image pins. Reject existing `99-personal-argo-service`, conflicting
   env names or duplicate service names. Publish/apply through Root's existing
   reviewed Hub configuration path and verify both Hubs register their dedicated
   clients after restart. This uses the baseline's `hub.extraConfig` mechanism
   and does not depend on an unverified `jupyterhub_config.d` loader.
5. On freshly read actual resources, add only the gateway reader volume/mount
   from `gateway-reader-template-patch.json`; use a strategic merge with a fresh
   metadata resourceVersion precondition. The patch does not set an image,
   remove existing mounts or replace the Pod spec. Privately merge only the
   `argoUi` key from `runtime-argo-fragment.json` into the actual runtime JSON,
   verify every other decoded value equals the original, and CAS the current
   runtime Secret. Do not apply the October 11 copied runtime proposal. Root
   starts a reviewed gateway rollout only after the reader credential is valid.
   Verify installed runtime bytes and readiness before unsuspending rotation.
6. With both Hub clients and the gateway adapter healthy, Root enables the
   schedule and verifies renewed tokens are reread from the directory mount:

   ```sh
   kubectl -n cps-compute patch cronjob argo-ui-token-rotator --type=merge \
     --patch '{"spec":{"suspend":false}}'
   ```

7. Qualify private frontend startup, actual native asset MIME and same-origin
   routes. Then root publishes/replaces only the reviewed public `/argo` routes
   to the personal frontends; do not expose the operational Argo API directly.
   Require real human owning-Hub OAuth, owner versus foreign workflow/log/artifact
   access, absent-object/write/issuer negatives, and actual artifact bytes. An
   empty list or unauthenticated redirect does not complete own-user acceptance.

Rollback restores only owned fields from current resources: suspend rotation,
restore the prior `argoUi` key and reader mount, remove the added Hub config/env
keys and restore the prior public route. Preserve concurrent runtime/native
changes and all credential originals. Fleet reconciliation and browser privacy
acceptance remain Root's live gates; local CPU tests do not establish them.
