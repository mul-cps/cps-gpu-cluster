# JupyterHub SSH Access

You can access your JupyterHub environment via SSH. This allows you to use your preferred local terminal, IDEs (like VS Code Remote SSH), and transfer files using SFTP/SCP.

**Authentication:** Two methods are supported, and you can use either one:

- **SSH public key** (recommended): run `ssh-copy-id <username>@jupyterhub.dshl.unileoben.ac.at` once (you'll be prompted for your API token the first time, since your server needs to be reachable to install the key into it). After that, `ssh`/`sftp`/`scp` connect without any prompt. Your key is checked against `~/.ssh/authorized_keys` **inside your own running notebook pod** -- exactly like a normal SSH server, just proxied through the gateway. Because it lives in your pod's home directory, an already-installed key survives pod restarts (persisted on your home PVC), but **your server must be running** the first time you install a key, and the gateway needs a few seconds after a fresh pod starts before the in-pod sshd is ready (see Troubleshooting below if a key-based login unexpectedly falls back to a password prompt right after a fresh spawn).
- **JupyterHub API Token as password** (fallback): always available, no setup required. Useful for a first connection, scripting, or if you haven't set up a key yet.

## Prerequisites

**For key-based login (recommended, one-time setup):**
```bash
ssh-copy-id <username>@jupyterhub.dshl.unileoben.ac.at
```
This will prompt for your password once (see "Get Your API Token" below) to install your public key. After that, no more prompts.

**For token/password login:**

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

*   If you've set up key-based login, you'll connect straight away with no prompt.
*   Otherwise, when prompted for the password, paste your **API Token**.
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
You can also use SFTP to transfer files, on the same default port and with
the same authentication (key-based or API token) as `ssh` above:

```bash
sftp <username>@jupyterhub.dshl.unileoben.ac.at
```

This proxies into your running singleuser notebook pod, the same way `ssh`
does -- you get your **personal JupyterHub home directory**, not shared
storage.

**Named Server:** the SFTP server is not aware of per-notebook named servers
-- there's no `<username>+<servername>` variant for SFTP.

## VS Code Remote SSH

1.  Install the "Remote - SSH" extension in VS Code.
2.  Add a new host:
    *   Host: `jupyter-dshl`
    *   HostName: `jupyterhub.dshl.unileoben.ac.at`
    *   User: `<your-username>`
3.  Connect to the host.

## Troubleshooting

**Key-based login falls back to a password prompt right after a fresh pod
spawn.** The in-pod sshd that key auth is checked against is started by a
background `postStart` hook, not before your pod is marked ready -- there's
a short window (typically a few seconds) after a fresh spawn where the
gateway can't yet reach it, and it correctly falls back to password auth
for that one attempt rather than failing outright. Wait a few seconds and
retry; it will normally succeed the next time without you doing anything
else.

**Key-based login stopped working after not using a profile for a while.**
Your server was likely culled (stopped due to inactivity) and respawned on
a new pod. If you installed your key via `ssh-copy-id` while an *older* pod
was running, that key lives on your home directory PVC and survives across
respawns -- but the very first connection to a freshly (re)spawned pod may
hit the same brief startup window described above. Retry once.

## Deployment Configuration

The Kubernetes manifests for the SSH service are managed via GitOps and located in:
`cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/`

This includes:
- `values.yaml`: Helm chart values
- `netpol.yaml`: Network policies
- `rbac.yaml`: Service account permissions
- `allow-ingress-nginx.yaml`: Ingress allow rules

