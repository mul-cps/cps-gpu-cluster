The Argo UI is served at [https://jupyterhub.dshl.unileoben.ac.at/argo/](https://jupyterhub.dshl.unileoben.ac.at/argo/) using the existing Argo release in `cps-argo`. This Fleet bundle contains raw UI access manifests only, which Fleet manages through its own bundle release. The existing `cps-argo` Helm release remains the owner of the Argo application; this bundle does not install another Argo application or take ownership of its controller/server/executor resources.

The existing `jupyterhub/jupyterhub` Ingress owns TLS for `jupyterhub.dshl.unileoben.ac.at` through its `dshl-wildcard` Secret. The Argo UI bundle deliberately shares that hostname without copying the wildcard private key. The existing ingress and TLS configuration must remain available.

The existing `cps-argo` release must use chart `0.45.26` with `server.baseHref=/argo/`. Before upgrading, compare the rendered chart with the captured current release: its 15 objects must remain identical except for the intended server base path. Set the archive placeholder to the reviewed, pinned local chart archive and capture the deployed revision:

```sh
ARGO_CHART_ARCHIVE=/absolute/path/to/pinned/argo-workflows-0.45.26.tgz
ARGO_PREVIOUS_REVISION="$(helm list -n cps-argo --filter '^cps-argo$' -o json |
  python3 -c 'import json,sys; rows=json.load(sys.stdin); assert len(rows)==1 and rows[0]["status"]=="deployed"; print(rows[0]["revision"])')"
helm upgrade cps-argo "$ARGO_CHART_ARCHIVE" -n cps-argo --reuse-values \
  --set-string server.baseHref=/argo/ --wait --timeout 120s
```

Retain `ARGO_PREVIOUS_REVISION` with the operator change record. If rollback is needed, restore that captured revision, rather than a fixed revision copied from an earlier run:

```sh
helm rollback cps-argo "${ARGO_PREVIOUS_REVISION:?set the captured prior revision}" \
  -n cps-argo --wait --timeout 120s
```

Preserve the `argo-ui-viewer` ServiceAccount and existing tokens during rollback. If retiring operator viewer authorization, remove only the UI-specific `cps-argo-ui-viewer` ClusterRoleBinding and ClusterRole. These UI resources are separate from the Helm release; do not delete the viewer account or token resources as part of the Helm rollback.

This native Argo UI is for trusted cluster operators. The `argo-ui-viewer` account can read workflows, workflow templates, cron workflows, cluster workflow templates, Pod metadata/logs and events across the cluster, and list namespaces. This is cluster-wide visibility, not personal or course isolation. It has no write permissions or access to Kubernetes Secrets, ConfigMaps or Nodes. The account has automatic token mounting disabled.

Ordinary users access their personal or group workspace workflows through the compute addon and its scoped gateway authorization. Do not distribute this operator viewer token as ordinary user access.

After the ingress and viewer account are applied, log in from your own trusted terminal and browser:

1. Using your authorized Kubernetes context, request a short-lived viewer token:

   ```sh
   kubectl -n cps-argo create token argo-ui-viewer --duration=1h
   ```

   Kubernetes may grant a different lifetime. Token creation requires your existing Kubernetes identity to be authorized to request tokens for this account.
2. Open [the Argo UI](https://jupyterhub.dshl.unileoben.ac.at/argo/). At the client token login, paste the returned token with the prefix `Bearer `, for example `Bearer <token>`. This uses Argo client authentication, separate from a JupyterHub login.
3. Open [workflows in cps-workflows](https://jupyterhub.dshl.unileoben.ac.at/argo/workflows/cps-workflows), or use the namespace picker and global lists. The operator viewer includes read-only namespace listing and the Argo resources required by the native UI.

Request a new token when it expires. Keep the token in your own terminal/browser; do not commit or share it. The manifests contain no token or long-lived ServiceAccount token Secret. This README describes the configured route and login flow; live ingress and login verification are separate integration checks.

References: [Argo client authentication](https://argo-workflows.readthedocs.io/en/release-3.7/argo-server-auth-mode/), [kubectl create token](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_create/kubectl_create_token/).

## Notebook artifact downloads

Native Argo client-auth artifact downloads resolve the repository credential and CA Secrets using the request identity. The operator viewer has no Secret access, so this native download path fails even when the viewer can read the Workflow. `artifact-downloads.yaml` adds a bounded proxy for the longer `/argo/artifact-files/` route. Native Argo login and its `authorization=Bearer <Kubernetes JWT>` cookie remain unchanged; the proxy also accepts a Bearer header. It verifies the caller's Kubernetes GET permission on the exact Workflow before fetching and again before returning buffered bytes.

The separate `argo-artifact-reader` ServiceAccount has only Workflow GET in `cps-workflows` and GET on the named `cps-artifact-credentials` and `cps-artifact-ca` Secrets. Its rotating projected token is used with the fixed native Argo backend, which performs the S3 download. The Python proxy does not call a Secret API, and reader credentials are not returned to the browser. Viewer permissions remain unchanged. `artifact-relay-access.yaml` adds port 8333 access only from the native Argo server pods in `cps-argo`; it preserves the existing relay policy. There is no fallback that grants storage privileges to the viewer or switches native Argo authentication modes.

Supported downloads are canonical notebook `inputs/snapshot` and `outputs/executed-notebook` from `cps-workflows`, bound to the exact Workflow, node and object descriptor. Each file is capped at **100 MiB**, with **60 seconds** for authorization and buffering and at most **two active downloads**. Changed or revoked Workflow access fails before buffered bytes are disclosed. A Workflow record can remain visible after a retention qualification fixture has deleted its files; those requests return an explicit storage-unavailable 404. General workflow artifacts and archived logs are not served by this route yet. Canonical behavior, configuration and qualification requirements are documented in [cps-compute artifact downloads](https://github.com/mul-cps/cps-compute/blob/27e0bbfb303bcdaadcfcbc242c0565a52206ddcf/docs/artifact-downloads.md)..

The Deployment pulls the private GHCR image using the kubelet-only `argo-artifact-image-pull` Secret. Its SOPS-managed GitOps resource contains only the existing gateway credential for `ghcr.io`; the application does not mount it and its reader account cannot read it. The digest pins the reviewed download-service source. Source manifests and image publication alone do not verify authenticated public downloads: readiness, supported downloads, negative authorization, native-cookie behavior and unchanged viewer RBAC require integration checks.

To roll back, remove only these three artifact manifests from the Fleet desired state and reconcile. For manually applied resources, after removing them from the desired state, delete the exact additions:

```sh
kubectl -n cps-argo delete ingress argo-artifact-downloads
kubectl -n cps-argo delete deployment,service argo-artifact-downloads
kubectl -n cps-argo delete networkpolicy \
  argo-artifact-downloads-from-ingress argo-server-from-artifact-downloads
kubectl -n cps-artifacts-relay delete networkpolicy artifacts-from-argo-server
kubectl -n cps-workflows delete rolebinding,role argo-artifact-reader
kubectl -n cps-argo delete serviceaccount argo-artifact-reader
kubectl -n cps-argo delete sopssecret argo-artifact-image-pull
```

Preserve the original `argo-ui` Ingress, `argo-ui-from-ingress` policy, upstream CA, viewer account and its authorization resources, and the existing `cps-argo` Helm release. Removing the proxy restores the native artifact route and its viewer Secret denial; it does not qualify an alternative artifact access path.
