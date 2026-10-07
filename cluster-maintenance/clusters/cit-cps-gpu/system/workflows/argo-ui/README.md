The Argo UI is served at [https://jupyterhub.dshl.unileoben.ac.at/argo/](https://jupyterhub.dshl.unileoben.ac.at/argo/) using the existing Argo release in `cps-argo`. This Fleet bundle contains raw UI access manifests only. The existing `cps-argo` Helm release remains the owner of the full Argo release; this bundle neither installs another release nor takes ownership of its controller/server/executor resources.

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
