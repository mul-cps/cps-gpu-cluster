# VS Code Remote-SSH Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make native VS Code Desktop + Remote-SSH work against JupyterHub notebook servers over the existing `jupyterhub.dshl.unileoben.ac.at:22` entrypoint, while preserving auto-spawn-on-cold-connect, `user+servername` targeting, agent forwarding, and plain interactive terminal access.

**Architecture:** The existing `jupyterhub-ssh` gateway (`asyncssh`, port 22) keeps doing auth + auto-spawn exactly as today. A real, minimal OpenSSH sidecar is added to every notebook pod, sharing the user's home-directory volume. After auth+spawn succeeds, the gateway opens an inner `asyncssh` *client* connection to that pod's sidecar (authenticated with a per-pod generated key the gateway fetches from a Kubernetes Secret) and relays every subsequent channel (session/exec/subsystem/direct-tcpip/agent-forwarding) between the real client and the sidecar, replacing the current Terminado-bridging path.

**Tech Stack:** Python 3 / `asyncssh` (gateway, existing image), OpenSSH (new sidecar image), Helm/Fleet-managed Kubernetes manifests, KubeSpawner `pre_spawn_hook`.

Full design: `docs/superpowers/specs/2026-08-03-vscode-remote-ssh-design.md`

## Global Constraints

- Every change to `cluster-maintenance/` only takes effect via Fleet sync from git — never apply by hand (per `CLAUDE.md`).
- The sidecar's internal SSH port (2200) must never be exposed via a Service or Ingress — reachable only pod-to-pod, and only from the `jupyterhub-ssh` gateway pod.
- The per-pod credential is generated fresh at spawn time and known only to that pod's sidecar and the gateway; it must never be readable by the notebook user's own code running in the singleuser container.
- Named-server syntax (`user+servername@...`) and the existing auto-spawn progress banner behavior must be preserved unchanged.
- `agent_forwarding=False` in the gateway's `asyncssh.listen(...)` call must become `True` only as part of Task 5, after the relay path exists — never enable it while the gateway still only bridges to Terminado (Terminado has no agent-forwarding concept and today's comment `# The cause of so much pain!` flags this deliberately disabled).
- Do not remove the Terminado-bridging code (`_handle_client`, `Terminado` import) until Task 6 confirms the relay path works end-to-end.

---

### Task 1: Sidecar SSH image

**Files:**
- Create: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/sidecar/Dockerfile`
- Create: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/sidecar/sshd_config`
- Create: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/sidecar/entrypoint.sh`
- Create: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/sidecar/README.md`

**Interfaces:**
- Produces: an image (referenced later as `<registry>/jupyterhub-ssh-sidecar:<tag>`) that, given `AUTHORIZED_KEY` env var (the public half of the per-pod credential) and a shared home-directory volume mounted at `/home/jovyan`, listens on `0.0.0.0:2200`, accepts only key auth for UID 1000, and allows agent forwarding + TCP forwarding.

- [ ] **Step 1: Write the Dockerfile**

```dockerfile
# cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/sidecar/Dockerfile
FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends openssh-server && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /run/sshd /etc/ssh/sidecar_host_keys

COPY sshd_config /etc/ssh/sshd_config.sidecar
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 2200
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
```

- [ ] **Step 2: Write `sshd_config`**

```
# cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/sidecar/sshd_config
Port 2200
ListenAddress 0.0.0.0
Protocol 2

HostKey /etc/ssh/sidecar_host_keys/ssh_host_ed25519_key

PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile /etc/ssh/sidecar_authorized_keys/authorized_keys

PermitRootLogin no
AllowUsers jovyan

AllowAgentForwarding yes
AllowTcpForwarding yes
X11Forwarding no
PermitTTY yes
Subsystem sftp /usr/lib/openssh/sftp-server

UsePAM no
StrictModes no
```

- [ ] **Step 3: Write `entrypoint.sh`**

The per-pod public key arrives via the `AUTHORIZED_KEY` env var (populated
from the Kubernetes Secret created in Task 3). The host key is generated
fresh on container start — it doesn't need to be stable across restarts,
since the gateway re-resolves the pod's connection details on every new
SSH session.

```bash
#!/bin/sh
# cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/sidecar/entrypoint.sh
set -eu

if [ -z "${AUTHORIZED_KEY:-}" ]; then
  echo "entrypoint: AUTHORIZED_KEY env var is required" >&2
  exit 1
fi

mkdir -p /etc/ssh/sidecar_authorized_keys
echo "$AUTHORIZED_KEY" > /etc/ssh/sidecar_authorized_keys/authorized_keys
chmod 0644 /etc/ssh/sidecar_authorized_keys/authorized_keys

if [ ! -f /etc/ssh/sidecar_host_keys/ssh_host_ed25519_key ]; then
  ssh-keygen -q -t ed25519 -N "" -f /etc/ssh/sidecar_host_keys/ssh_host_ed25519_key
fi

exec /usr/sbin/sshd -D -e -f /etc/ssh/sshd_config.sidecar
```

- [ ] **Step 4: Write `README.md`**

```markdown
# jupyterhub-ssh sidecar

Real OpenSSH server injected as an `extra_container` into every notebook
pod by `apply_profile_settings()` in
`cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml`.
Listens on internal port 2200, never exposed via a Service or Ingress —
reachable only from the `jupyterhub-ssh` gateway pod. Shares the pod's
home-directory volume (mounted at `/home/jovyan`) so exec/SFTP/SCP/agent
forwarding operate against the user's real notebook filesystem.

See `docs/superpowers/specs/2026-08-03-vscode-remote-ssh-design.md` for
the full design.

Build and push (adjust registry/tag to match this repo's existing custom
image build pattern for `incluster-image-builder`-managed images):

    docker build -t <registry>/jupyterhub-ssh-sidecar:2026-08-03 .
    docker push <registry>/jupyterhub-ssh-sidecar:2026-08-03
```

- [ ] **Step 5: Build and push the image locally to verify it builds**

Run: `docker build -t jupyterhub-ssh-sidecar:test cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/sidecar/`
Expected: build succeeds with no errors.

- [ ] **Step 6: Smoke-test the image standalone**

Run:
```bash
docker run -d --name sidecar-test -e AUTHORIZED_KEY="$(cat ~/.ssh/id_ed25519.pub)" -p 2200:2200 jupyterhub-ssh-sidecar:test
ssh -p 2200 -o StrictHostKeyChecking=no jovyan@localhost whoami
docker rm -f sidecar-test
```
Expected: `whoami` prints `jovyan` (or the container's actual running user — add `USER jovyan` / `useradd` step to the Dockerfile if `AllowUsers jovyan` rejects the connection because no such user exists in this minimal image; the real deployment relies on the shared home volume for identity, not a matching local `/etc/passwd` entry, so add a matching `jovyan` UID 1000 user in the Dockerfile if this step fails).

- [ ] **Step 7: Commit**

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/sidecar/
git commit -m "feat(jupyterhub-ssh): add real sshd sidecar image for VS Code Remote-SSH"
```

---

### Task 2: Push the sidecar image via this repo's existing image build pipeline

**Files:**
- Modify: whichever GitHub Actions workflow already builds/pushes custom images for this cluster (search first — do not assume a path).

**Interfaces:**
- Consumes: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/sidecar/Dockerfile` (Task 1).
- Produces: a pushed, pullable image reference to use as `sidecarImage` in Task 3.

- [ ] **Step 1: Find the existing custom-image build pattern**

Run: `ls .github/workflows/` and `grep -rl "docker build\|buildx" .github/workflows/`
Read whichever workflow already builds a custom image for this cluster (this repo has done this before for other in-cluster components — follow that exact pattern for registry, tagging, and trigger paths, rather than inventing a new one).

- [ ] **Step 2: Add (or extend) a workflow job to build and push the sidecar image**

Mirror the found pattern's job structure exactly, pointing `context:`/`file:` at
`cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/sidecar/`,
triggered on changes to that path, tagging the image with the git SHA (and
`latest` if the existing pattern does so).

- [ ] **Step 3: Push the workflow change and confirm it runs**

Run: `gh workflow run <workflow-file> --ref main` (or push and let the path
trigger fire), then `gh run watch`.
Expected: the build-and-push job succeeds and the image appears in the
registry the existing pattern uses.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/
git commit -m "ci: build and push jupyterhub-ssh sidecar image"
```

---

### Task 3: Per-pod credential + sidecar container wiring in the KubeSpawner hook

**Files:**
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml` (inside `apply_profile_settings`, after the UID override block around line 1661, before the `postStart`/`tmux` block at line 1667)

**Interfaces:**
- Produces: a Kubernetes Secret named `ssh-sidecar-<safe-username>` in the `jupyterhub` namespace containing an ed25519 keypair (`private_key`, `public_key` fields), and a sidecar container (`ssh-sidecar`) added to `spawner.extra_containers` with `AUTHORIZED_KEY` set from the public key, sharing the pod's home volume, listening on container port 2200 (not exposed by any Service).
- Consumes: `spawner` (KubeSpawner instance, already in scope in `apply_profile_settings`), `spawner.api` (KubeSpawner's own in-cluster Kubernetes API client, already used implicitly by KubeSpawner itself for Secret/Pod management — use the same `kubernetes_asyncio` client library KubeSpawner itself depends on, importing it directly: `from kubernetes_asyncio import client as k8s_client`).

- [ ] **Step 1: Add the credential-generation and Secret-creation code**

Insert directly after the UID override block (after line 1661, `if cfg.get('uid'): spawner.uid = cfg['uid']`):

```python
          # --- SSH sidecar credential (VS Code Remote-SSH support) ---
          import base64
          import re
          from cryptography.hazmat.primitives import serialization
          from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
          from kubernetes_asyncio import client as k8s_client
          from kubernetes_asyncio.client.rest import ApiException

          safe_username = re.sub(r'[^a-z0-9-]', '-', spawner.user.name.lower())[:40]
          sidecar_secret_name = f"ssh-sidecar-{safe_username}"

          priv_key = Ed25519PrivateKey.generate()
          priv_pem = priv_key.private_bytes(
              encoding=serialization.Encoding.PEM,
              format=serialization.PrivateFormat.OpenSSH,
              encryption_algorithm=serialization.NoEncryption(),
          )
          pub_openssh = priv_key.public_key().public_bytes(
              encoding=serialization.Encoding.OpenSSH,
              format=serialization.PublicFormat.OpenSSH,
          )

          secret_body = k8s_client.V1Secret(
              metadata=k8s_client.V1ObjectMeta(
                  name=sidecar_secret_name,
                  namespace="jupyterhub",
                  labels={"app.kubernetes.io/component": "ssh-sidecar-credential"},
              ),
              string_data={
                  "private_key": priv_pem.decode(),
                  "public_key": pub_openssh.decode(),
              },
              type="Opaque",
          )

          core_api = k8s_client.CoreV1Api(spawner.api_client)
          try:
              await core_api.replace_namespaced_secret(sidecar_secret_name, "jupyterhub", secret_body)
          except ApiException as e:
              if e.status == 404:
                  await core_api.create_namespaced_secret("jupyterhub", secret_body)
              else:
                  raise

          spawner.extra_containers = spawner.extra_containers or []
          spawner.extra_containers.append({
              "name": "ssh-sidecar",
              "image": "<registry>/jupyterhub-ssh-sidecar:2026-08-03",
              "env": [{"name": "AUTHORIZED_KEY", "value": pub_openssh.decode()}],
              "ports": [{"containerPort": 2200, "name": "ssh-sidecar", "protocol": "TCP"}],
              "volumeMounts": [{"name": "home", "mountPath": "/home/jovyan"}],
              "securityContext": {"runAsUser": 1000, "allowPrivilegeEscalation": False},
          })
          # --- end SSH sidecar credential ---
```

Replace `<registry>/jupyterhub-ssh-sidecar:2026-08-03` with the actual
pushed image reference from Task 2.

- [ ] **Step 2: Confirm the notebook pod already has a volume named `home` that maps to `/home/jovyan`**

Run: `grep -n "volumeMounts\|storage:" cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml | head -30`
If the singleuser home volume has a different name in this chart's KubeSpawner config (KubeSpawner's default volume name is typically `volume-{username}` or a fixed name set via `c.KubeSpawner.volume_mounts`), update the `volumeMounts` `name` field in Step 1 to match it exactly — do not guess; the volume name must be identical to what KubeSpawner already generates for the main `notebook` container, or the sidecar will fail to mount.

- [ ] **Step 3: Add `cryptography` and `kubernetes_asyncio` as available in the hub image**

Run: `grep -n "cryptography\|kubernetes-asyncio\|kubernetes_asyncio" cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml`
`kubernetes_asyncio` is already a KubeSpawner dependency (KubeSpawner itself is built on it) — no action needed if the hub image already includes KubeSpawner. If `cryptography` is not already present in the hub image (check `pip show cryptography` inside a running hub pod: `kubectl exec -n jupyterhub deploy/hub -- pip show cryptography`), add it to whatever mechanism this chart uses to extend the hub image's Python packages (search `values.yaml` for an existing `pip install` / `hub.extraConfig` / custom hub image pattern and follow it).

- [ ] **Step 4: Commit**

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml
git commit -m "feat(jupyterhub): provision per-pod ssh-sidecar credential and container"
```

---

### Task 4: RBAC + NetworkPolicy for the gateway to reach the sidecar

**Files:**
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/rbac.yaml`
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml` (singleuser networkPolicy, around line 1913)

**Interfaces:**
- Produces: the `jupyterhub-ssh` ServiceAccount can `get` Secrets named `ssh-sidecar-*` in the `jupyterhub` namespace; notebook pods accept ingress on port 2200 from pods carrying the `jupyterhub-ssh` gateway's label.

- [ ] **Step 1: Extend the Role to allow reading sidecar credential Secrets**

```yaml
# cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/rbac.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: jupyterhub-ssh-pod-reader
  namespace: jupyterhub
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: []
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: jupyterhub-ssh-pod-reader-binding
  namespace: jupyterhub
subjects:
- kind: ServiceAccount
  name: jupyterhub-ssh
  namespace: jupyterhub
roleRef:
  kind: Role
  name: jupyterhub-ssh-pod-reader
  apiGroup: rbac.authorization.k8s.io
```

Note: `resourceNames` is left empty (meaning: any secret) rather than
enumerated, since secret names are dynamic (`ssh-sidecar-<username>`,
generated per spawn) — Kubernetes RBAC `resourceNames` can't do prefix
matching. This does widen the gateway's read access to all Secrets in the
`jupyterhub` namespace; if this is unacceptable, narrow the label
selector isn't possible via RBAC, so as a mitigation put sidecar-credential
secrets in their own dedicated namespace instead. Flag this trade-off to
the user in the task review rather than silently picking one.

- [ ] **Step 2: Verify the `ssh/deployment.yaml` template already sets `automountServiceAccountToken: true`**

Run: `grep -n automountServiceAccountToken cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/chart/templates/ssh/deployment.yaml`
Expected: already `true` (confirmed at Task-brief time — line 28 of that
file). No change needed; this step is a pre-flight check only.

- [ ] **Step 3: Allow gateway → notebook-pod ingress on port 2200**

In `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml`,
change the `singleuser.networkPolicy.ingress` list (currently empty, line
1915) to:

```yaml
  networkPolicy:
    enabled: true
    ingress:
      - from:
          - podSelector:
              matchLabels:
                app.kubernetes.io/name: jupyterhub-ssh
                app.kubernetes.io/component: ssh
        ports:
          - port: 2200
            protocol: TCP
```

Verify the label values match what `jupyterhub-ssh.ssh.labels` actually
renders (`grep -n "jupyterhub-ssh.ssh.labels" -A5 cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/chart/templates/_helpers.tpl`)
and correct the `matchLabels` values if they differ from
`app.kubernetes.io/name: jupyterhub-ssh` / `app.kubernetes.io/component: ssh`.

- [ ] **Step 4: Commit**

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/rbac.yaml cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub/values.yaml
git commit -m "feat(jupyterhub-ssh): RBAC + netpol for gateway-to-sidecar access"
```

---

### Task 5: Gateway relay logic — replace Terminado bridging with inner-SSH-connection relay

**Files:**
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/chart/templates/patch-configmap.yaml`

**Interfaces:**
- Consumes: `self.user_ip` (already set by `get_user_server_url`, line 105 of the current file), `self.username` (set in `validate_password`, line 174).
- Produces: `NotebookSSHServer.session_requested()` now opens/reuses an inner `asyncssh` client connection to the resolved pod's sidecar and returns a relay handler instead of `_handle_client`.

- [ ] **Step 1: Add sidecar-credential lookup and inner-connection helper**

Add this method to `NotebookSSHServer`, near `start_user_server`:

```python
        async def _get_sidecar_connection(self):
            """
            Lazily establish (and cache) an inner asyncssh client connection
            to this session's notebook pod's ssh-sidecar container.
            """
            if getattr(self, "_sidecar_conn", None) is not None:
                return self._sidecar_conn

            import base64
            username = self.username.split("+", 1)[0]
            safe_username = "".join(c if c.isalnum() or c == "-" else "-" for c in username.lower())[:40]
            secret_name = f"ssh-sidecar-{safe_username}"

            headers = {"Authorization": f"Bearer {self._k8s_token()}"}
            url = f"https://kubernetes.default.svc/api/v1/namespaces/jupyterhub/secrets/{secret_name}"
            async with ClientSession(headers=headers) as session:
                async with session.get(url, ssl=self._k8s_ssl_context()) as resp:
                    resp.raise_for_status()
                    secret = await resp.json()
            private_key_pem = base64.b64decode(secret["data"]["private_key"]).decode()

            self._sidecar_conn = await asyncssh.connect(
                self.user_ip,
                port=2200,
                username="jovyan",
                client_keys=[asyncssh.import_private_key(private_key_pem)],
                known_hosts=None,
            )
            return self._sidecar_conn

        def _k8s_token(self):
            with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
                return f.read().strip()

        def _k8s_ssl_context(self):
            import ssl
            ctx = ssl.create_default_context(
                cafile="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
            )
            return ctx
```

- [ ] **Step 2: Replace `session_requested` to relay into the sidecar instead of Terminado**

Replace the existing `_handle_client`-based `session_requested` (current
lines 223-277) entirely with a generic relay handler:

```python
        async def _relay_session(self, stdin, stdout, stderr):
            """
            Relay this SSH session's stdio into an equivalent session opened
            against the pod's ssh-sidecar, preserving PTY/exec/subsystem
            semantics transparently.
            """
            sidecar_conn = await self._get_sidecar_connection()
            channel = stdin.channel

            term_type = channel.get_terminal_type()
            command = channel.get_command()
            subsystem = channel.get_subsystem()

            kwargs = {}
            if term_type:
                rows, cols, width, height = channel.get_terminal_size()
                kwargs["term_type"] = term_type
                kwargs["term_size"] = (cols, rows, width, height)

            if subsystem:
                inner_process = await sidecar_conn.create_process(subsystem=subsystem, **kwargs)
            elif command:
                inner_process = await sidecar_conn.create_process(command, **kwargs)
            else:
                inner_process = await sidecar_conn.create_process(**kwargs)

            async def pump(reader, writer):
                try:
                    while True:
                        data = await reader.read(65536)
                        if not data:
                            break
                        writer.write(data)
                        await writer.drain()
                except Exception:
                    pass
                finally:
                    try:
                        writer.close()
                    except Exception:
                        pass

            tasks = [
                asyncio.create_task(pump(stdin, inner_process.stdin)),
                asyncio.create_task(pump(inner_process.stdout, stdout)),
                asyncio.create_task(pump(inner_process.stderr, stderr)),
            ]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            self._conn.close()
            for t in tasks:
                t.cancel()

        def session_requested(self):
            return self._relay_session
```

Remove the now-unused `_handle_ws_recv`, `_handle_stdin`, `_handle_client`
methods and the `from .terminado import Terminado` import — but only after
Task 6 confirms the relay path works end-to-end (per the Global
Constraints section). For this step, leave the old methods in place but
unreferenced; delete them in Task 6 once verified.

- [ ] **Step 3: Enable agent forwarding on the outer listener**

In `JupyterHubSSH.start_server`, change:

```python
                agent_forwarding=False,  # The cause of so much pain! Let's not allow this by default
```

to:

```python
                agent_forwarding=True,
```

This is safe now because the gateway only relays agent-forwarding channel
opens through to the sidecar's real `sshd` (which itself declares
`AllowAgentForwarding yes`), rather than trying to interpret them itself.

- [ ] **Step 4: Commit**

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/chart/templates/patch-configmap.yaml
git commit -m "feat(jupyterhub-ssh): relay SSH sessions into per-pod sidecar instead of Terminado"
```

---

### Task 6: End-to-end verification, cleanup of dead Terminado code, docs update

**Files:**
- Modify: `cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/chart/templates/patch-configmap.yaml`
- Modify: `docs/jupyterhub-ssh-access.md`

**Interfaces:**
- Consumes: a live cluster with Tasks 1-5 synced via Fleet.

- [ ] **Step 1: Sync and wait for Fleet**

Run: `kubectl get bundles -n fleet-local | grep jupyterhub`
Expected: relevant bundles reach `Ready`.

- [ ] **Step 2: Verify plain terminal access still works**

Run: `ssh <username>@jupyterhub.dshl.unileoben.ac.at` (password = JupyterHub API token)
Expected: lands in an interactive shell inside the notebook pod (now via
the real sidecar sshd, not Terminado) — confirm with `whoami` and `pwd`
inside the session (`pwd` should be `/home/jovyan`, the real notebook home
directory).

- [ ] **Step 3: Verify non-interactive exec works**

Run: `ssh <username>@jupyterhub.dshl.unileoben.ac.at echo hello`
Expected: prints `hello` and exits immediately — this is the capability
that was structurally impossible before this change.

- [ ] **Step 4: Verify SFTP works against the real home directory**

Run: `sftp <username>@jupyterhub.dshl.unileoben.ac.at` then `ls`, `pwd`
Expected: connects successfully, `pwd` shows `/home/jovyan`.

- [ ] **Step 5: Verify named-server targeting still resolves correctly**

Run: `ssh <username>+<servername>@jupyterhub.dshl.unileoben.ac.at whoami`
(using a real named server configured for the test account)
Expected: succeeds against the correct named server's pod, not the default
one — confirm via a file uniquely present in that server's home directory,
or by checking `NVIDIA_VISIBLE_DEVICES`/profile-specific env if the named
server uses a different profile.

- [ ] **Step 6: Verify auto-spawn-on-cold-connect still works**

Stop the test user's server (`kubectl delete pod -n jupyterhub jupyter-<username>` or via the Hub UI), then immediately:
Run: `ssh <username>@jupyterhub.dshl.unileoben.ac.at whoami`
Expected: the auth banner shows "Starting your server..." with progress
dots before the command runs, exactly as it did pre-change.

- [ ] **Step 7: Verify agent forwarding works**

Run: `ssh -A <username>@jupyterhub.dshl.unileoben.ac.at 'ssh-add -l'`
(with a local agent running and a key added)
Expected: lists the locally-forwarded key, confirming agent forwarding
reaches through both hops.

- [ ] **Step 8: Connect with VS Code Desktop Remote-SSH**

Add to local `~/.ssh/config`:
```
Host jupyter-vscode-test
  HostName jupyterhub.dshl.unileoben.ac.at
  User <username>
```
Use VS Code's "Remote-SSH: Connect to Host..." command targeting
`jupyter-vscode-test`, authenticate with the JupyterHub token as password
when prompted.
Expected: VS Code Server installs and starts inside the pod, the remote
file explorer shows the real home directory, and a new integrated
terminal opens a working shell.

- [ ] **Step 9: Remove the dead Terminado-bridging code**

In `patch-configmap.yaml`, delete `_handle_ws_recv`, `_handle_stdin`, and
`_handle_client` (superseded by `_relay_session` in Task 5), and delete
the `from .terminado import Terminado` import line.

- [ ] **Step 10: Update the docs**

In `docs/jupyterhub-ssh-access.md`, replace the VS Code Remote-SSH section
with accurate, verified instructions matching Steps 8 above (host config
snippet, auth-with-token note, mention that named-server syntax and agent
forwarding both work). Remove any language implying the old
Terminado-based path supported this.

- [ ] **Step 11: Run this repo's docs build to confirm no broken links/nav**

Run: `pip install mkdocs-material && mkdocs build` (from repo root)
Expected: builds with no errors.

- [ ] **Step 12: Commit**

```bash
git add cluster-maintenance/clusters/cit-cps-gpu/user/jupyter/jupyterhub-ssh/chart/templates/patch-configmap.yaml docs/jupyterhub-ssh-access.md
git commit -m "cleanup(jupyterhub-ssh): remove dead Terminado bridge, document verified VS Code Remote-SSH flow"
```
