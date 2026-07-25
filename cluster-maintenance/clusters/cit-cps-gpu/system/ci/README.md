# In-cluster GitHub Actions CI

See `docs/superpowers/specs/2026-07-25-github-actions-runners-design.md`
for the full design.

## Status

- **`actions-runner-controller/`** -- deployed. The ARC operator/CRDs,
  cluster-wide. No GitHub credentials needed for the controller itself.
- **`buildkit-pool/`** -- deployed and verified live (2026-07-25) with a
  real `buildctl build --push` + registry cache export/import against
  the running pool. Shared, persistent rootless-BuildKit pool (`ci`
  namespace, 2 replicas) that CI workflows connect to via
  `docker buildx create --driver remote tcp://buildkit-pool.ci.svc.cluster.local:1234`,
  instead of each runner pod running its own Docker-in-Docker daemon.
  Registry cache goes to Harbor's `ci-build-cache` project; built images
  go to `ci-images` (both created via the Harbor API, robot account
  `robot$ci-buildkit`).

  **Important, verified live:** the pool Deployment's own `DOCKER_CONFIG`
  only authenticates the *daemon's* own pulls (e.g. a Dockerfile's `FROM`
  referencing a private Harbor image) -- it does **not** authenticate
  `--push`/`--export-cache` operations. With the buildx "remote" driver,
  registry auth for those is forwarded from the **client's own session**
  (whatever's invoking `docker buildx build`/`buildctl`), not the
  long-running daemon's environment. Every CI workflow that pushes or
  exports cache needs its own login step first, e.g.:

  ```yaml
  - name: Set up buildx against the shared pool
    run: |
      docker buildx create --name ci-pool --driver remote \
        tcp://buildkit-pool.ci.svc.cluster.local:1234 --use
      echo "${{ secrets.HARBOR_ROBOT_PASSWORD }}" | \
        docker login harbor.dshl.unileoben.ac.at -u '<robot-account>' --password-stdin
  - uses: docker/build-push-action@v7
    with:
      push: true
      tags: harbor.dshl.unileoben.ac.at/ci-images/<name>:${{ github.sha }}
      cache-from: type=registry,ref=harbor.dshl.unileoben.ac.at/ci-build-cache/<name>:cache
      cache-to: type=registry,ref=harbor.dshl.unileoben.ac.at/ci-build-cache/<name>:cache,mode=max
  ```
- **Runner scale set -- NOT YET DEPLOYED.** Needs a GitHub App installed
  on the `mul-cps` org (App ID, Installation ID, private key) -- a
  web-UI-only step that can't be done via `gh` CLI/API, done by the
  cluster operator separately. Once the credentials exist:
  1. SOPS-encrypt them into a `githubConfigSecret` Secret (same pattern
     as `ci-harbor-builder` in `buildkit-pool/harbor-builder-sopssecret.yaml`).
  2. Add a `gha-runner-scale-set` Fleet bundle here (namespace
     `arc-runners` -- already referenced by `buildkit-pool`'s
     NetworkPolicy, so no changes needed there), `containerMode:
     kubernetes`, `githubConfigUrl: https://github.com/mul-cps`.
  3. GPU-requesting workflow jobs should set
     `priorityClassName: kai-ci-lowest` and `schedulerName: kai-scheduler`
     (queue label per KAI's usual `runai/queue: ci` annotation -- see
     `system/gpu/kai-scheduler/kai-policy/queues.yaml`).

## Harbor GC (out-of-band, not Helm-managed)

Harbor's garbage collection schedule is a runtime API setting, not a
Helm value -- configured directly via the Harbor API on 2026-07-25:
nightly at 02:00, `delete_untagged: true`. This was **globally false
before** (affecting the pre-existing `build-cache` project from
`incluster-image-builder` too, not just this CI addition) -- meaning no
superseded BuildKit registry-cache blobs were ever actually being swept.
If Harbor is ever redeployed from scratch, re-set this:

```bash
curl -u "admin:$HARBOR_ADMIN_PASSWORD" -X PUT \
  "https://harbor.dshl.unileoben.ac.at/api/v2.0/system/gc/schedule" \
  -H "Content-Type: application/json" \
  -d '{"schedule": {"type": "Daily", "cron": "0 0 2 * * *"}, "parameters": {"delete_untagged": true}}'
```

A tag-count-based retention policy on `ci-build-cache` was deliberately
**not** configured: BuildKit's registry cache always overwrites the same
tag per image (`naming.cache_ref`-style), so there is never more than one
tag per repository to retain among -- `delete_untagged` GC is what
actually bounds this project's storage growth, not a retention policy.
