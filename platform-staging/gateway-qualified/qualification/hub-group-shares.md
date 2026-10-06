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

## Kubernetes and NFS fixture, 2026-10-06

The isolated `cps-hub-rtc-qualification` namespace now repeats the Shares scenario with JupyterHub 5.5.2 and KubeSpawner 7.1.0. The operator-built Hub image is `ghcr.io/mul-cps/cps-compute-hub@sha256:952a621db1aa4d152e3b061cdc4016b05044947ae9076863752c3db8bba39777`, containing compute source `5771df5e3db86a59b20fcf965cc3ce273df0c503`. All 20 OCI blobs, the non-root image user and included SLSA provenance were verified. Full SPDX and Syft documents were attached to that digest and their remote manifest subject and document hashes verified. These are qualification artifacts, not released production images.

Actual Kubernetes SubjectAccessReviews allow the fixture Hub service account to create pods in its own namespace and deny that operation in both `jupyterhub` and `cit-jhub`. An impersonated `kubectl auth can-i` check misleadingly returned yes; the explicit SubjectAccessReviews are the recorded authorization evidence. Notebook pods have service-account token automount disabled and no projected credential volume. The fixture has no public ingress and uses ClusterIP services, loopback port forwarding and a namespace NetworkPolicy.

A dedicated synthetic-data directory on the existing TrueNAS NFS export (`193.170.30.58`) passed mounted write/read checks from a restricted UID 1000 notebook pod. Group-only access initially failed, including with the matching primary group. Setting ownership of this new test directory to UID 1000/GID 100 through the TrueNAS filesystem API resolved the failure; no human home or course directory was changed. This qualifies the fixture path, not a diagnosis or repair of general production NFS identity mapping.

The actual admin adapter then passed named-server startup, rejection of a running server as stopped, confirmed shutdown, creation of a native group Share, restart, synthetic OAuth consent and HTTP access for Alice and Bob. Each visitor's `/api/me` returned their own identity. Removing Bob from the group removed shared-server access from his existing API token. Share revocation and final confirmed shutdown passed. These clients used HTTP requests, not rendered browser automation.

Evidence remains private under `/home/bjoern/cps-platform-evidence/2026-10-06/hub-kubespawner-rtc`: `shares-api-report.json`, `rbac-scope-verification.json`, `nfs-fixture.json`, `notebook-pod-security-report.json`, `image-integrity-report.json`, `publication.json` and `sbom-publication.json`. Fixture credentials are excluded from Git. The Hub and proxy remain running for the next RTC checks; the notebook server and bounded NFS test jobs have stopped.

Still required: two RTC clients observing shared notebook edits, revocation of an already-open connection through the workspace removal sequence, retained data across workspace restart, cross-Hub reservations, grant migration and real production authentication. Neither production Hub has received the compatibility hook.

## Two-client RTC qualification, 2026-10-06

The Kubernetes fixture subsequently passed two authenticated Python RTC clients using the notebook image's Jupyter collaboration WebSocket protocol. Alice edited a notebook cell; Bob's independent CRDT document observed the same edit. This is live protocol evidence, not a rendered browser/UI check.

The member-removal sequence confirmed workspace shutdown before changing membership. Both already-open RTC transports reached EOF within the bounded wait. Shutdown produced no WebSocket close code, so the test asserts observed transport EOF rather than requiring a graceful close frame. Alice's edit was retained in the NFS notebook after restart. Bob's existing token no longer carried shared-server access, and his server request was denied or redirected to authentication. The final server shutdown was confirmed.

Private evidence: `hub-kubespawner-rtc/rtc-report.json` and `qualify-rtc.py` under the operator evidence root above. This establishes the fixture's shared-state, connection closure and restart retention checks. It does not prove the production membership API invokes this sequence, production browser behavior, cross-Hub reservations, grant migration or production authentication. Those remain gates.

The owned Hub/proxy deployments, ClusterIP services and Kubernetes fixture authentication/pull secrets were removed after testing. The dedicated retained NFS test directory, PV/PVC and private evidence remain for review; no human data was removed.
