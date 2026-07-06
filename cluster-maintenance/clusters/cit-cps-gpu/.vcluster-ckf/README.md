# vcluster-ckf Bundle

This bundle deploys a `vcluster` dedicated to Charmed Kubeflow (CKF).

## Current real state (verified live, 2026-07-06)

**Kubeflow is NOT installed.** The vcluster itself is healthy and reachable
(`vcluster-ckf-0` pod Running, API server responds, storage syncing from
host Longhorn works) -- but the manual bootstrap below was never
completed. Checked directly inside the vcluster: only the 4 default k8s
namespaces exist (`default`, `kube-system`, `kube-public`,
`kube-node-lease`), no `kubeflow` namespace, no Juju controller.

**Root cause of why this stalled: this bundle's `fleet.yaml` never
actually deployed `juju-toolbox.yaml`/`juju-toolbox-rbac.yaml`/
`rbac-host.yaml`.** It only had a `helm:` block (the vcluster chart
itself) with no `kustomize:` stanza, so Fleet was only tracking/applying
the vcluster Helm release -- the toolbox pod and its RBAC (needed to run
`juju bootstrap`/`juju deploy kubeflow`) never existed, despite the bundle
showing "ready" in Fleet (it was only reporting on the one thing it was
actually deploying). **Fixed 2026-07-06**: added `kustomize: dir: .` to
`fleet.yaml` plus a `kustomization.yaml` listing the three raw manifests,
matching the proven-working pattern from this repo's
`user/jupyter/jupyterhub-test` bundle. Verified live: after applying
manually, the `juju-toolbox` pod actually starts and runs its setup
script correctly (apt packages install fine, `vcluster`/`kubectl` binary
downloads work).

**Known blocker in the bootstrap script itself**: the `juju-toolbox.yaml`
setup script downloads the Juju client from
`https://launchpad.net/juju/3.6/3.6.1/+download/...`, which 303-redirects
to `launchpadlibrarian.net`. Confirmed live: that specific host times out
(`curl` exit 28, connection hangs) from inside this cluster's pod network
-- an external network reachability issue with Launchpad's CDN from this
cluster's egress path, not a bug in this repo. Before continuing the
bootstrap, whoever picks this up should either (a) retry -- this may be a
transient CDN/regional routing issue, not a permanent block, (b) try an
alternate Juju install method (the `snap install juju --classic` line the
script already has commented out, if snap can be made to work in this
container, or a different binary mirror), or (c) download the Juju binary
from a host with working network access to Launchpad and inject it via a
ConfigMap/initContainer instead of relying on in-pod `curl`.

**No Kubeflow install was attempted this pass** -- deploying a full
Charmed Kubeflow stack is a real capacity/scope decision (Juju controller
+ Kubeflow's own resource footprint, whether the 1.10/stable channel is
still the right target, whether it's even still wanted) that needs a
human call, not something to do unilaterally. This session only fixed the
Fleet-wiring gap and confirmed the vcluster itself is healthy and ready
for the bootstrap to actually be attempted.

**Separate flag, not yet checked**: this cluster's Longhorn storage is
currently under real capacity strain (see `docs/troubleshooting.md` --
`default-disk` mid-eviction on all 4 GPU nodes, `nvme-scratch` scheduled
beyond 100% capacity on 3/4 nodes). A future Kubeflow install would add
meaningful new PVC demand (pipeline artifacts, Katib experiments, notebook
servers) on top of that -- worth resolving the capacity issue first, or at
minimum sizing Kubeflow's storage requests with that constraint in mind.

## Components

- **vcluster**: Version 0.28.0, syncing storage classes from host (Longhorn).
- **juju-toolbox**: A pod with `juju`, `vcluster`, and `kubectl` to perform the manual bootstrap.

## Manual Installation Steps (After Fleet Sync)

Once Fleet has deployed this bundle:

1.  **Access the Toolbox**:
    ```bash
    kubectl -n vcluster-ckf exec -it juju-toolbox -- bash
    ```

2.  **Connect to vcluster**:
    ```bash
    # Get kubeconfig
    vcluster connect vcluster-ckf -n vcluster-ckf --server https://vcluster-ckf.vcluster-ckf --silent --print > /tmp/vcluster-ckf.kubeconfig
    export KUBECONFIG=/tmp/vcluster-ckf.kubeconfig
    
    # Verify connection
    kubectl get nodes
    ```

3.  **Bootstrap Juju**:
    ```bash
    # Add the vcluster as a cloud
    juju add-k8s vcluster-ckf --client
    
    # Bootstrap the controller
    juju bootstrap vcluster-ckf ckf-controller
    ```

4.  **Deploy Charmed Kubeflow**:
    ```bash
    # Create model
    juju add-model kubeflow
    
    # Deploy (adjust channel as needed, e.g., 1.10/stable)
    juju deploy kubeflow --channel=1.10/stable --trust
    ```

## Cleanup

To remove everything, simply remove this bundle from Git or modify Fleet to uninstall it.
