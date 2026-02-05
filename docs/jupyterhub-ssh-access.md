# JupyterHub SSH Access

You can access your JupyterHub environment via SSH. This allows you to use your preferred local terminal, IDEs (like VS Code Remote SSH), and transfer files using SFTP/SCP.

**Authentication:** You authenticate using your **JupyterHub API Token** as the password.

## Prerequisites

1.  **Get Your API Token**:
    *   Go to: [https://jupyterhub.dshl.unileoben.ac.at/hub/token](https://jupyterhub.dshl.unileoben.ac.at/hub/token)
    *   Log in if requested.
    *   Request a new API token (or use an existing one).
    *   **Copy this token. It is your password for SSH.**

## Connecting via SSH

### Default Server
To connect to your default (primary) server:

```bash
ssh <username>@jupyterhub.dshl.unileoben.ac.at
```

*   When prompted for the password, paste your **API Token**.
*   **Note**: Your JupyterHub server must be running for the connection to succeed. If it is stopped, the connection will fail.

### Named Servers (Multi-GPU / Specialized Profiles)
If you are running multiple named servers (e.g., you have a "gpu-large" profile running alongside your default server), you can target them specifically.

**Syntax:**
```bash
ssh <username>+<servername>@jupyterhub.dshl.unileoben.ac.at
```

**Example:**
If your username is `abcd123` and you have a named server called `gpu-work`, connect using:
```bash
ssh abcd123+gpu-work@jupyterhub.dshl.unileoben.ac.at
```
Use your **API Token** as the password.

## SFTP / File Transfer
You can also use SFTP to transfer files.

**Default Server:**
```bash
sftp <username>@jupyterhub.dshl.unileoben.ac.at
```

**Named Server:**
```bash
sftp <username>+<servername>@jupyterhub.dshl.unileoben.ac.at
```

## VS Code Remote SSH

1.  Install the "Remote - SSH" extension in VS Code.
2.  Add a new host:
    *   Host: `jupyter-dshl`
    *   HostName: `jupyterhub.dshl.unileoben.ac.at`
    *   User: `<your-username>`
3.  Connect to the host.

## Deployment Configuration

The Kubernetes manifests for the SSH service are managed via GitOps and located in:
`cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/`

This includes:
- `values.yaml`: Helm chart values
- `netpol.yaml`: Network policies
- `rbac.yaml`: Service account permissions
- `allow-ingress-nginx.yaml`: Ingress allow rules

