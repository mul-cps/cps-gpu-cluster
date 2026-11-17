# Rancher Turtles memory override — 2026-11-17

The existing manager repeatedly OOMKilled with exit137 at its 300Mi memory limit after normal GPU3 infrastructure relocation. GPU2 had MemoryPressure=False and about377.6GiB allocatable memory. Root approved one narrowly scoped resource override; no application/chart version upgrade was performed.

At14:19:09Z, a single UID/RV/image/container-name/replicas/strategy/full-old-resource guarded JSON Patch changed **only manager memory limit300Mi→1Gi and request128Mi→256Mi**. CPU limit500m/request10m and every other Deployment spec field remained exact. Local full-object patch comparison passed before the live patch. No matching PDB existed; normal Deployment rollout/grace was used, with no direct Pod deletion or forced action. Memory cap increased724Mi and reservation128Mi for one controller.

New Pod `rancher-turtles-controller-manager-c5c4f486-n6wt8`, UID `fd3060e2-7837-448a-98ab-ff308004bdb8`, became Ready on GPU2. At14:21:26Z it was Ready with zero restarts,136seconds after container start, exceeding the observed26second failed cold start. Same image/version: `rancher/turtles:v0.25.4`; actual imageID is recorded in the memory receipt. Metrics-server reported296Mi/2mCPU. Its actual container cgroup reported memory.max1Gi, current310726656B, peak317591552B (~302.9Mi, above the former300Mi cap), and zero memory.events max/oom/oom_kill. GPU2 MemoryPressure remainedFalse. This is bounded startup evidence, not an indefinite stability claim.

## Ownership and explicit drift

Owner remains the Helm/Rancher App `rancher-turtles` in `cattle-turtles-system`, release revision2, chart `108.0.4+up0.25.4`, app0.25.4. There is no discovered platform Fleet manifest, HelmChart or HelmChartConfig owner. The exact released chart's `templates/deployment.yaml:67–73` hardcodes the old memory amounts; **there is no resource values knob**. Adding an ignored `--set resources...` value would not fix it.

An ordinary same-chart render also introduces unrelated capability/lookup-dependent CAPIProvider and ConfigMap differences, besides upgrade hooks. Root therefore rejected that broader Helm operation and explicitly chose this temporary Deployment-only override. No Helm release/values/manifest, CRD, RBAC or Secret was changed by the override. The complete decoded Helm release/config/stored-manifest was privately compared exact before/after. Secret references and all environment/configuration fields in the Deployment remained exact. No claim is made that Helm's stored resource values were repaired.

**Owner normalization remains open.** A future manual Rancher/Helm operation can restore the hardcoded300Mi limit. Until a supported chart resource knob or a reviewed resource-only post-render workflow is adopted, every owner operation must check the actual manager resources and replay this reviewed override if it reset them. Do not create a competing Deployment reconciler. Helm4 supports a named `postrenderer/v1` plugin; a future post-render workflow must prove the complete object/Secret content diff is resource-only before use. It was not applied here. See the [official Helm plugin documentation](https://helm.sh/docs/plugins/overview/).

## Replay and incident reverse

`applied-guarded-patch.json` is the exact applied receipt. Its resourceVersion is historical and **must be refreshed after a fresh identity/image/replicas/strategy/current-resource check**; do not remove the tests or blindly retry a conflict. Its only writes are the two memory values. Reuse it only when the original current resources match300Mi/128Mi and CPU remains500m/10m. Verify local full-object comparison, current PDB allowance, normal rollout and new Ready/restart/memory observations again.

`incident-reverse-patch.json` is unapplied incident recovery only, with fresh RV and current1Gi/256Mi/image guards required. It restores the old known-OOM resource amounts, so it is not routine post-maintenance cleanup. No automatic rollback was performed. Permanent normalization belongs to the existing Helm/Rancher owner.

Safe receipts: `drift-receipt.json`, `local-diff-proof.json`, `startup-memory-observation.json`. Original Helm values, full release/render and private diffs remain only in the0600 private case under `gpu3-maintenance-preparation-20261117/turtles-oom-review`; none are committed here.
