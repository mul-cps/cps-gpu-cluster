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
- **`gha-runner-scale-set/`** -- deployed and verified live (2026-07-26):
  the org-level runner scale set (`githubConfigUrl:
  https://github.com/mul-cps`, scale set name `cit-cps-gpu`), namespace
  `arc-runners` (already referenced by `buildkit-pool`'s NetworkPolicy),
  successfully registered with GitHub and its listener pod is running.
  Auth via a GitHub App (App ID 4397759, Installation ID 149124630,
  private key SOPS-encrypted in `github-config-sopssecret.yaml`).
  `containerMode: kubernetes` -- `minRunners: 0`/`maxRunners: 10`, scales
  to zero when idle. GPU-requesting workflow jobs should set
  `priorityClassName: kai-ci-lowest` and `schedulerName: kai-scheduler`
  (queue label per KAI's usual `runai/queue: ci` annotation -- see
  `system/gpu/kai-scheduler/kai-policy/queues.yaml`).

  **GitHub App permission gotcha, hit live:** a GitHub App needs the
  **organization**-level "Self-hosted runners" permission (Read and
  write) to issue runner registration tokens -- this is a *separate*
  permission category from the repository-level "Actions"/
  "Administration" permissions, easy to miss on the App's settings page.
  Even after saving that permission on the App, the *installation*
  itself doesn't pick it up automatically -- the org owner must visit
  the installation's settings page
  (`https://github.com/organizations/mul-cps/settings/installations/<id>`)
  and explicitly accept the new permission grant there. Symptom before
  fixing: controller logs show `403 Forbidden: Resource not accessible
  by integration` when requesting a runner registration token, even
  though App-level JWT auth succeeds.

## Monitoring

Prometheus metrics are enabled for both the controller-manager and
listener pods (`system/ci/actions-runner-controller/values.yaml`), a
`Service`+`ServiceMonitor` scrapes the controller, and a `PodMonitor`
scrapes listener pods directly (they're ephemeral, one per
AutoscalingRunnerSet, not behind a stable Service -- selector confirmed
live against a real listener pod's labels,
`app.kubernetes.io/component: runner-scale-set-listener`).
`listenerMetrics` in `gha-runner-scale-set/values.yaml` matches the
metric names the official ARC sample dashboard expects.

The dashboard itself (`actions-runner-controller/dashboard-configmap.yaml`)
is imported from the upstream
[`actions/actions-runner-controller` sample](https://github.com/actions/actions-runner-controller/blob/master/docs/gha-runner-scale-set-controller/samples/grafana-dashboard/ARC-Autoscaling-Runner-Set-Monitoring.json),
with its templated `${DS_PROMETHEUS}` datasource resolved to `null`
(Grafana's default datasource) to match this cluster's existing
`gpu-dash-*.yaml` convention -- picked up automatically by the Grafana
sidecar via the `grafana_dashboard: "1"` label, same as every other
dashboard in `system/observability/monitoring/`.

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
