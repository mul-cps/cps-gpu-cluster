Below is an **end-to-end, code-agent-friendly runbook** to integrate **vcluster → Juju → Charmed Kubeflow (CKF)** into a **Fleet GitOps** repo on your **k3s** host cluster, assuming:

* Host cluster already has **MetalLB + NGINX Ingress**
* Host default/available StorageClass: **Longhorn**
* You want CKF **inside a vcluster** first (test / easy cleanup)

This follows CKF’s “general installation” approach (Juju-managed) and vcluster’s standard configuration model. ([Ubuntu Documentation][1])

---

## 0) Target architecture

**Host k3s**

* Fleet manages:

  * `vcluster` (virtual API server + sync)
  * optional: a “juju-toolbox” pod to run Juju commands from inside cluster

**Inside vcluster**

* Juju controller bootstrapped *to the vcluster kube-apiserver*
* CKF deployed in a Juju model

Why this is GitOps-friendly:

* Fleet declaratively installs/updates vcluster (and toolbox)
* Juju declaratively manages Kubeflow components and their lifecycle (deploy/upgrade/remove)

---

## 1) Repo structure (Fleet bundles)

Add a new bundle folder:

```
cluster-maintenance/
  clusters/
    <your-cluster>/
      apps/
        vcluster-ckf/
          fleet.yaml
          values-vcluster.yaml
          rbac-host.yaml
          juju-toolbox.yaml
          README.md
```

### `fleet.yaml` (Fleet bundle entry)

Use Fleet’s Helm integration to install the vcluster chart. (If you already use a different Fleet pattern for Helm, adapt accordingly.)

```yaml
defaultNamespace: vcluster-ckf

helm:
  repo: https://charts.vcluster.com
  chart: vcluster
  version: "0.28.0"   # pin a version
  valuesFiles:
    - values-vcluster.yaml

dependsOn: []
```

> Pin versions so upgrades are deliberate.

---

## 2) vcluster values: storage + ingress/service exposure

### `values-vcluster.yaml`

Key goals:

* **Sync StorageClasses from host** so vcluster can use Longhorn (vcluster requires SC sync; it will delete SCs created inside vcluster to avoid conflicts). ([vcluster.com][2])
* Expose vcluster API via an internal service (default is fine). You can optionally expose it externally if you want Juju from your laptop without `vcluster connect`.

```yaml
# vcluster chart values (high-level; confirm fields match your chosen chart version)
vcluster:
  image: ghcr.io/loft-sh/vcluster:0.28.0

  # Sync host StorageClasses into the virtual cluster so PVCs can use Longhorn
  sync:
    storageClasses:
      enabled: true
      # optional: only sync SCs with a label selector (recommended to avoid clutter)
      # selectors:
      #   matchLabels:
      #     vcluster-sync: "true"

  # Useful defaults
  securityContext:
    allowPrivilegeEscalation: false

service:
  type: ClusterIP
  # If you want to access vcluster API from outside cluster, set LoadBalancer
  # type: LoadBalancer

# Optional: create an Ingress for the vcluster API (rarely needed; usually vcluster connect is enough)
# ingress:
#   enabled: true
#   ingressClassName: nginx
#   host: vcluster-ckf-api.<your-domain>
```

### Label your Longhorn StorageClass for syncing (optional but recommended)

If you use selectors above, label the host Longhorn SC:

```bash
kubectl label storageclass longhorn vcluster-sync=true
```

Also ensure **Longhorn is default inside the vcluster**, because CKF expects a default SC. ([Ubuntu Documentation][1])
Easiest: keep Longhorn as host default, and it will appear default when synced. If not, patch default annotation inside host SC (preferred) or adjust your sync strategy.

Default SC annotation (host side):

```bash
kubectl patch storageclass longhorn -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

---

## 3) Host RBAC needed by vcluster

### `rbac-host.yaml`

Grant vcluster the minimal cluster-wide permissions it needs for syncing. (Exact RBAC depends on your vcluster mode; start with the chart’s defaults if available. If your environment is restricted, you’ll tighten later.)

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: vcluster-ckf
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: vcluster-ckf
  namespace: vcluster-ckf
```

> In many setups the vcluster chart creates its own RBAC; keep this file only if your Fleet policies require explicit SA/NS creation.

---

## 4) Deploy vcluster via Fleet

Commit + let Fleet reconcile. Verify:

```bash
kubectl -n vcluster-ckf get pods
kubectl -n vcluster-ckf get svc
```

---

## 5) Access the vcluster kubeconfig (for Juju bootstrap target)

From an admin shell (or from a toolbox pod), get a vcluster context. Typical method:

```bash
vcluster connect vcluster-ckf -n vcluster-ckf -- kubeconfig > /tmp/vcluster-ckf.kubeconfig
export KUBECONFIG=/tmp/vcluster-ckf.kubeconfig
kubectl get nodes
kubectl get sc
```

You should see StorageClasses (incl. Longhorn) inside the vcluster now. ([vcluster.com][2])

If your ops environment doesn’t have the `vcluster` CLI, you can also read the kubeconfig from the secret that the chart creates (name varies by version/release; commonly something like `vc-<release>-kubeconfig`).

---

## 6) Fleet-managed “juju-toolbox” pod (recommended)

This lets you run `juju` against the vcluster from inside the host cluster (no laptop dependencies).

### `juju-toolbox.yaml`

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: juju-toolbox
  namespace: vcluster-ckf
  labels:
    app: juju-toolbox
spec:
  restartPolicy: Always
  containers:
    - name: toolbox
      image: ubuntu:24.04
      command: ["/bin/bash","-lc"]
      args:
        - |
          apt-get update
          apt-get install -y ca-certificates curl bash jq
          # Install juju (pin major/minor in real setups)
          snap install juju --classic
          # Optional: install vcluster cli (or mount kubeconfig another way)
          curl -L -o /usr/local/bin/vcluster https://github.com/loft-sh/vcluster/releases/download/v0.28.0/vcluster-linux-amd64
          chmod +x /usr/local/bin/vcluster
          echo "Toolbox ready. Sleeping..."
          sleep infinity
      securityContext:
        runAsUser: 0
```

Apply via Fleet by including it in the bundle (either in `resources:` for kustomize-based bundles or as a plain manifest in the bundle folder).

---

## 7) Bootstrap Juju into the vcluster

Exec into toolbox:

```bash
kubectl -n vcluster-ckf exec -it juju-toolbox -- bash
```

Inside the pod:

```bash
# 1) Get vcluster kubeconfig
vcluster connect vcluster-ckf -n vcluster-ckf -- kubeconfig > /tmp/vcluster-ckf.kubeconfig
export KUBECONFIG=/tmp/vcluster-ckf.kubeconfig

# 2) Register this k8s cluster with Juju
juju add-k8s vcluster-ckf --client

# 3) Bootstrap a Juju controller into the vcluster
juju bootstrap vcluster-ckf ckf-controller

# 4) Create a model for kubeflow
juju add-model kubeflow
```

`juju add-k8s` is the supported way to add a Kubernetes cluster definition from kubeconfig, and then bootstrap onto it. ([Ubuntu Documentation][3])

---

## 8) Deploy Charmed Kubeflow (CKF) into that model

CKF is deployed/managed by Juju; follow the bundle/channel you want (pin this).

Example pattern:

```bash
# Always confirm the currently recommended channel + deploy command in CKF docs for your desired version
juju deploy kubeflow --channel=1.9/stable
```

CKF’s docs explicitly describe this “general installation” approach and the requirement that the cluster has working storage (default SC). ([Ubuntu Documentation][1])

Then watch:

```bash
juju status --watch 5s
```

---

## 9) Ingress: expose Kubeflow Dashboard via your existing NGINX Ingress

CKF (Juju charms) often manage ingress through an integrator charm (instead of you manually writing Ingress YAML). If you want “clean integration” with your existing NGINX Ingress controller, Canonical provides an **nginx-ingress-integrator** charm used for routing integration. ([Charmhub][4])

High-level approach:

1. Deploy `nginx-ingress-integrator` in the same Juju model
2. Relate it to the Kubeflow dashboard / gateway charm(s)
3. Configure hostname + TLS settings via charm config

Because the exact relations depend on the CKF bundle version and which gateway components are used, implement this step by following the integrator charm docs and the CKF version docs you pin. ([Charmhub][5])

Pragmatic testing shortcut:

* Use `kubectl port-forward` inside vcluster to validate the UI first, then do ingress “properly”.

---

## 10) Day-2 operations and cleanup (the big win of vcluster)

### Upgrade CKF

```bash
juju refresh kubeflow --channel=1.9/stable
juju status
```

### Remove CKF (clean)

```bash
juju switch kubeflow
juju remove-application kubeflow --force
juju destroy-model kubeflow --destroy-storage --force
```

### Nuke the whole sandbox

Delete the vcluster release (Fleet will do it when you remove bundle), then:

* all CKF resources are gone with it (since they lived inside vcluster)

---

# Notes specific to your environment (Longhorn + GPU cluster)

* **Storage performance** inside vcluster is basically your **normal Longhorn behavior**; vcluster doesn’t add an extra storage data path—just the control plane mapping. (So “Longhorn tuning” still matters more than vcluster.)
* **GPU scheduling:** for CKF test, keep it simple (one node pool). Later, you can decide whether you want Kubeflow training operators to request MIG slices vs full GPUs—this is orthogonal to vcluster.

---

## What to hand your code agent

Tell it to implement:

1. The repo folder + Fleet bundle files above
2. vcluster chart deployment pinned to a specific version
3. StorageClass sync + “Longhorn is default” inside vcluster
4. A `juju-toolbox` pod (or a Kubernetes Job) that runs `juju add-k8s / bootstrap / deploy`

If you want, paste your existing Fleet repo conventions (how you do `fleet.yaml`, helm, and per-cluster overlays), and I’ll adapt the files to match your *exact* structure (prod/testing, bundle naming, sops secrets pattern, etc.).

[1]: https://documentation.ubuntu.com/charmed-kubeflow/how-to/install/general-installation/?utm_source=chatgpt.com "General installation - Charmed Kubeflow"
[2]: https://www.vcluster.com/docs/vcluster/0.29.0/configure/vcluster-yaml/sync/from-host/storage-classes?utm_source=chatgpt.com "Storage classes - Virtual Clusters for Kubernetes"
[3]: https://documentation.ubuntu.com/juju/3.6/reference/juju-cli/list-of-juju-cli-commands/add-k8s/?utm_source=chatgpt.com "juju add-k8s"
[4]: https://charmhub.io/nginx-ingress-integrator?utm_source=chatgpt.com "Nginx Ingress Integrator"
[5]: https://charmhub.io/nginx-ingress-integrator/docs/getting-started?utm_source=chatgpt.com "Deploy the Nginx ingress integrator charm for the first time"
