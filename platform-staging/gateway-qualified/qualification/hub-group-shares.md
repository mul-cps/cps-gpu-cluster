# Hub 5 native group Share qualification

Status: isolated compatibility qualification passed; production collaboration qualification remains open.

JupyterHub 5.5.2 includes group Shares when resolving a user, but omits them when resolving that user's API token. An actual single-user OAuth login therefore returned HTTP 403 for a visitor with a native group Share. The compute adapter provides an explicit, version-checked compatibility hook that intersects requested token scopes with the owner's current effective scopes, including native group Shares. Service tokens receive no additional permission. Unsupported Hub versions fail activation.

## Qualified artifacts

- Compute source: `d87dd25ceb11f16b11b1d5cdcefe39accc8cfb4f` on `feat/gateway-release-qualification`; integrated as `a7f408c39fbd77d35c66776338ac29d27dc134f4` on `feat/platform-end-to-end`.
- Operator-built wheel: `cps_compute-0.1.0-py3-none-any.whl`, SHA-256 `204ce7c606697a253e2ce624950239209cfa8e8be7dfa3cfcd8a343b19a5d25b`. This is a qualification build, not a published release.
- Installed-wheel suite: 208 passed, with 22 existing dependency deprecation warnings.
- Private operator evidence: `/home/bjoern/cps-platform-evidence/2026-10-06/hub-shares-api/installed-report.json` and `installed-tests.log`. Credentials and Hub logs must not be committed.

The fixture used actual Hub 5.5.2, its API, native group Shares, OAuth consent and a single-user JupyterLab server. The admin Hub adapter created a named workspace, confirmed its shutdown, created a group Share and restarted it. Two synthetic visitors independently opened JupyterLab and `/api/me` with HTTP 200 and retained their own identities. Removing one member removed shared access from that visitor's existing token. Share revocation and confirmed workspace shutdown passed. The owned fixture was stopped and all three loopback listener ports were verified closed.

## Deployment and remaining gates

The hook is explicit opt-in (`groupShareTokenCompatibility` in the enabled Hub adapter, or the documented installer). It has not been deployed to either production Hub. Do not enable it on Hub 6 without separate review and qualification.

This test used SimpleLocalProcessSpawner and synthetic identities. It does not qualify production KubeSpawner, NFS mounts, RTC shared notebook state, termination of an already-open removed-member connection, cross-Hub reservations, grant migration or production authentication. Those remain release gates. Production activation must consume the exact reviewed SDK artifact and repeat the full collaboration scenario before declaring it qualified.

References: [Hub 5.5.2 Shares](https://jupyterhub.readthedocs.io/en/5.5.2/reference/sharing.html), [Hub 5.5.2 scope implementation](https://github.com/jupyterhub/jupyterhub/blob/5.5.2/jupyterhub/scopes.py).
