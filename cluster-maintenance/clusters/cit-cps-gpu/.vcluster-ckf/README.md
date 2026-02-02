# vcluster-ckf Bundle

This bundle deploys a `vcluster` dedicated to Charmed Kubeflow (CKF).

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
