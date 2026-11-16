# Released metrics repair candidate — review only

Observed 2026-11-16 19:25–19:27 UTC on selected k3s-wk-gpu2 (10.21.0.43). No cluster changes, restart or GPU fixture was executed for this proposal. Monitoring acceptance remains open and NRI failure-policy qualification separately blocks promotion.

## Minimal proposed change

1. **No GpuFractioningConfig, ClusterPolicy, runtimeClass or CDI configuration change is needed in the current mode.** ClusterPolicy cluster-policy has cdi.enabled=true, default=false, nriPluginEnabled=false; RuntimeClass nvidia exists with handler nvidia. The default CR already has runtimeClassName=nvidia and metricsAgent.enabled=true, restricted to GPU2 plus the upstream-runtime label. metricsd already receives NVIDIA_VISIBLE_DEVICES=all and NVIDIA_DRIVER_CAPABILITIES=utility.
2. At the root-coordinated quiescent NRI window, verify the driver and nvidia runtime are ready, then gracefully recreate **only** the selected fractiond Pod (currently gpu-fractioning-fractiond-d7j6f, UID 83ff65f5-b48d-4637-80b1-d924174446a6) using a UID precondition. Re-read UID immediately before deletion. This replaces its colocated fractiond+metricsd together; do not roll the operator, mpsd, peers, or GPU driver. It interrupts the NRI connection, so it must be coordinated with the NRI test owner and no workload creation. Restart is proposed, not performed. Recreating only a process inside the existing container cannot add missing OCI devices/libraries.
3. Persist the two **unmodified released** objects in stock-monitors.yaml through the existing Fleet operand bundle: add that file beside cluster-maintenance/clusters/cit-cps-gpu/system/gpu/gpu-fractioning/resources.yaml and add `- stock-monitors.yaml` to that directory's kustomization.yaml resources. Keep existing fleet.yaml and resources.yaml. The bundle currently renders raw resources with kustomize, so merely adding a Helm value elsewhere has no effect. Do not re-render the entire default chart/CR and accidentally widen GPU2 selection.

No bespoke exporter or legacy monitor removal. If later deliberately enabling GPU Operator toolkit NRI mode, v0.1.9 automatically substitutes management CDI annotations and removes the RuntimeClass; that separate mode would require toolkit env NRI_MANAGEMENT_CDI_DEVICE_NAMESPACES=gpu-fractioning. It is irrelevant while nriPluginEnabled=false and is not proposed here.

## Current evidence and cause

- metricsd logs at its 18:33:39 start: `nvidia driver modules are not yet loaded, invoking runc directly`; then `NVML unavailable; GPU process metrics will be zero (pod labels still reported)`, error `initialize NVML: ERROR_LIBRARY_NOT_FOUND`.
- Allowlisted exec verified /dev/nvidiactl, /dev/nvidia0, /dev/nvidia1 and /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1 are all **missing inside metricsd**. Its HTTP2112 /metrics still returns zero bytes, even though the CR reports Ready. Host now has /run/nvidia/driver/dev/nvidiactl and matched libnvidia-ml.so.620.70.06. This supports creation-time runtime fallback, rather than a namespace allowlist issue.
- Released newCollector chooses a NoopCollector on initialization failure, not a later NVML retry: fractioning-manager/metricsd/internal/metrics/nvml_collector.go:268-282. fractiond.go:323-378 documents/sets the existing all+utility injection; :159-178 adds CDI only in toolkit NRI mode.
- Host /var/run/cdi/management.nvidia.com-gpu.yaml: kind management.nvidia.com/gpu, device all, mapped nvidiactl and R620 NVML. /var/run/cdi/k8s.device-plugin.nvidia.com-gpu.json: kind k8s.device-plugin.nvidia.com/gpu, devices GPU-16128952-b438-556a-00bb-93039ee24e56 and GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6. /etc/cdi absent; /var/run/cdi contains both specs.
- Prometheus rancher-monitoring-prometheus selectors for SM, PM and both namespaces are `{}`; additionalScrapeConfigs null. Targets: 71 active, 520 dropped, zero gpu-fractioning in either set. There are no SM/PM objects in gpu-fractioning. Pod scrape annotations alone are therefore not discovery.
- Controller HTTP8080 /metrics previously returned daemon desired/ready and reconcile families. It is a distinct scrape target from metricsd2112. Released mpsd has no separate metrics port; controller daemon gauges report readiness, and metricsd reports per-pod GPU activity.

## Reproducible stock render

Official v0.1.9 source commit fb75540adca3392ab4b51d03e6c0da9b393fa842. Archive /tmp/cps-upstream-20261116/gpu-fractioning-0.1.9.tgz SHA256 238c08d45f1087b07b2793e7ee9e9e6b2f23a12e0bdbd680e37e3ab1b5479e58.

```sh
helm template gpu-fractioning /tmp/cps-upstream-20261116/gpu-fractioning-0.1.9.tgz \
  --namespace gpu-fractioning --api-versions monitoring.coreos.com/v1 \
  --set prometheus.enabled=true --show-only templates/monitors.yaml > stock-monitors.yaml
```

Rendered SHA256 59e3881f32f4e503ba800f1f5b81e6bbc87eb407e1e5e9bd36823cc898013bfc. Stock SM selects controller service labels/name+instance, HTTP port http, /metrics, 30s interval/10s timeout. Stock PM selects operator-managed fractiond labels, port metrics, /metrics, 30s interval; it has no explicit scrapeTimeout. Existing Prometheus selectors admit both without extra release labels.

Released README:114-140 explains management CDI mode; :314-325 lists observability options. Chart prometheus.enabled defaults false, metrics.enabled and metricsAgent.enabled true; metric names may be overridden through spec.metricsAgent.metricNames. Defaults are retained.

## Measurement proposal and acceptance evidence (not yet run)

After approved recreation, require fresh log `NVML initialized; GPU process metrics enabled`, injected NVML/device presence, no new fallback warning, and both SM/PM target health=up. Retain the replacement UID/container IDs and metrics raw text; Ready alone is insufficient. Then use one root-owned selected-GPU2 mandatory-NRI fixture, host memory budget16GiB, annotated standard 5GiB GPU request/limit, explicit GPU UUID. Hold a known in-budget allocation while sampling; do not overlap another GPU test or rely on idle empty output.

During the active hold retain three independent witnesses keyed by exact namespace/Pod UID/container ID/GPU UUID:

- admitted Pod annotation `nvidia.com/container.main.gpu-memory.request` and `.limit` (5GiB), plus actual leaf/container memory-limits output for soft/hard enforcement, using the existing mixed-profile witness method;
- raw metricsd and scraped Prometheus `gpu_fractioning_gpu_memory_used_bytes{namespace,pod,pod_uuid,gpu_uuid,gpu}` while the allocation is held; compare with fixture allocation and physical PID/NVML witness, accounting for actual context overhead without inventing a new tolerance;
- controller ready/desired metrics plus Prometheus target labels/time and successive timestamps for this owned Pod. If a compute fixture is used, also retain nonzero gpu_fractioning_gpu_sm_utilization_percent and its normalized counterpart alongside independent progress. An allocation-only hold does not prove SM utilization.

Stock v0.1.9 exposes usage and SM utilization, **not standalone GPU memory request/limit series**. Request/limit evidence must remain joined to Pod annotations and actual driver leaf limits; do not claim all three are Prometheus series or reuse CPU-memory kube-state-metrics as GPU limits. Confirm correct Pod UID attribution, bounded release/zero-after-cleanup, no orphan mapping/client, and both cards back to the prior 1MiB/no-client baseline with UID-guarded graceful cleanup.

This first usable monitoring cycle cannot retire the old cps-gpu-isolator/kai-resource-isolator monitors or close all eight profile-equivalence requirements. Preserve them until corresponding ordinary/distributed/teaching/recovery evidence is accepted. Any missing attribution or unavailable requested/limit dashboard remains an explicit gap.

## Safe evidence commands used

```sh
kubectl get clusterpolicy -ojson # filter only cdi and named management-namespace toolkit env
kubectl get gpufractioningconfig default -ojson # filter runtimeClass/metricsAgent/nodeSelector/conditions
kubectl get runtimeclass nvidia -ojson # filter name/handler
kubectl logs -n gpu-fractioning gpu-fractioning-fractiond-d7j6f -c metricsd --tail=12
kubectl get --raw /api/v1/namespaces/gpu-fractioning/pods/http:gpu-fractioning-fractiond-d7j6f:2112/proxy/metrics
kubectl get servicemonitor,podmonitor -A -ojson # filter gpu-fractioning metadata only
kubectl get prometheus -A -ojson # filter monitor selectors/additionalScrapeConfigs only
kubectl get --raw '/api/v1/namespaces/cattle-monitoring-system/services/http:rancher-monitoring-prometheus:9090/proxy/api/v1/targets?state=any' # count/filter fractioning only
```

Host/CDI inspection used read-only SSH to ubuntu@10.21.0.43, allowlisted CDI kind/device names and NVML/nvidiactl paths only. Container inspection checked the four named paths above; no full environment, Secrets or credentials were read or retained.
