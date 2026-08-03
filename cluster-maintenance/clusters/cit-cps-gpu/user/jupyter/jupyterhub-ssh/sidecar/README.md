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
