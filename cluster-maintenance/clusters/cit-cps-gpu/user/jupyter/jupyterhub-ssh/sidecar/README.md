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

Built and pushed manually (no CI wiring for this image — the repo's only
documented image-build CI path, Harbor + the self-hosted ARC runner
pool, is unreachable from this public repo's default runner group and has
no `HARBOR_ROBOT_PASSWORD` secret configured; see `system/ci/README.md`).
Pushed to `ghcr.io/mul-cps`, where this GitHub account has admin access:

    docker build -t ghcr.io/mul-cps/jupyterhub-ssh-sidecar:2026-08-03 .
    gh auth token | docker login ghcr.io -u <your-github-username> --password-stdin
    docker push ghcr.io/mul-cps/jupyterhub-ssh-sidecar:2026-08-03

Current live tag: `ghcr.io/mul-cps/jupyterhub-ssh-sidecar:2026-08-03`
