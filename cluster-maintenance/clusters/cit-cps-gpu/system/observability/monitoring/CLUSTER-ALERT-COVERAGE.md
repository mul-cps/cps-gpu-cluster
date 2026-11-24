# CPS/CIT cluster alert coverage

The monitoring add-on bundle supplies the `cps-cluster-health` and
`nvidia-gpu-alerts-fleet` rules in `cattle-monitoring-system`. The
Rancher Monitoring Prometheus selects rules across namespaces and evaluates
them every 30 seconds. Warnings and critical alerts enter the cluster's
administrator digest through the existing Alertmanager route.

## Coverage and first checks

| Area | Existing live coverage | Fleet rule and trigger |
| --- | --- | --- |
| Node health | Rancher covers node readiness, unreachable nodes, readiness flapping, exporter targets, available memory, major faults, and disk I/O. Kubernetes node pressure and eviction rules are informational. | `CPSNodeMemoryStall` warns after 15 minutes of over 10% full memory pressure measured in five-minute windows. Check reclaim and workloads on the reported host. Linux reports full pressure when all non-idle tasks are stalled on memory. [Linux PSI](https://docs.kernel.org/accounting/psi.html) |
| GPU driver and runtime | GPU rules cover temperatures, utilization, framebuffer use, and exporter reachability. Compute collector alerts track missing DCGM samples relative to the currently advertised inventory. Kubernetes deployment, pod, and DaemonSet rules cover persistent rollout failures. | `CPSGPUAllocatableCapacityLost` is critical after 10 minutes below two allocatable NVIDIA GPUs on a Ready, schedulable worker. An absent allocatable resource is treated as zero. Review driver, toolkit, and device plugin together. `GPUXIDErrors` now checks the last nonzero XID code for one minute and deduplicates by GPU UUID across workload labels. Use the node kernel journal to establish the event time. [NVIDIA DCGM metrics](https://docs.nvidia.com/datacenter/dcgm/latest/reference/dcgm-exporter-metrics.html) |
| Container launch and image path | Kubernetes warns on persistent waiting pods and slow pod startup. | `CPSKubeletRuntimeFailures` warns when sandbox creation, container creation/start, or image pulls exceed both 10 errors and a 25% failure ratio in ten minutes, sustained for five minutes on a node. For `pull_image`, check registry health, network, image references and runtime authentication. |
| Storage | Rancher tracks mounted PVC space/inodes, PV phase, and host filesystem space. Hub and gateway database backup rules cover stale and failed jobs. The old standalone `prometheus-longhorn-rules` manifest was absent live on November 24. | `CPSScratchMountMissing` and `CPSHostFilesystemReadOnly` are critical after five minutes. Longhorn volume faults are critical after five minutes, and degraded redundancy warns after ten minutes. Backing disk readiness warns after ten minutes, and less than 12% physical free space warns after 30 minutes. Check the Longhorn disk or volume condition, replica placement, snapshots, and the host mount. [Longhorn 1.9.2 volume collector](https://github.com/longhorn/longhorn-manager/blob/v1.9.2/metrics_collector/volume_collector.go), [Longhorn 1.9.2 disk collector](https://github.com/longhorn/longhorn-manager/blob/v1.9.2/metrics_collector/disk_collector.go) |
| Services | Rancher covers workload replicas and scrape targets. Existing CPS/CIT Hub probes cover public routes and notebook lifecycle. | `CPSCriticalServiceNoReadyEndpoints` is critical after five minutes without a ready DNS endpoint, NGINX HTTPS endpoint, or compute gateway HTTP endpoint while kube-state-metrics is up. `CPSManagedIngressErrorSpike` warns after ten minutes above both 5% HTTP 5xx and 25 errors in a ten-minute window per CPS/CIT Hub or Harbor route. Check readiness, upstream routing, and deploy events. [Ingress NGINX metrics](https://kubernetes.github.io/ingress-nginx/user-guide/monitoring/) |
| Cache pressure | Node and container page-cache metrics and CoreDNS cache counters are scraped. | `CPSCoreDNSCacheDegraded` requires higher than 70% DNS cache misses and over 100 ms p95 DNS latency at two or more cache requests per second, sustained for ten minutes. Check upstream latency, query mix, and CoreDNS restarts. The alert reports co-occurring cache misses and slow responses. The kernel full-stall and image-pull rules cover workload impact from host memory pressure and image delivery failures. [CoreDNS cache metrics](https://coredns.io/plugins/cache/), [CoreDNS DNS latency metrics](https://coredns.io/plugins/metrics/) |

`KubePersistentVolumeFillingUp` evaluates filesystem capacity reported by
kubelet. A nearly empty PVC can lose Longhorn replica redundancy and trigger
`CPSLonghornVolumeDegraded`. A backing disk shared by several healthy PVCs
can fall below 12% free and trigger `CPSLonghornDiskHeadroomLow` while every
mounted PVC has ample room. A healthy Longhorn volume with a nearly full
mounted filesystem remains covered by `KubePersistentVolumeFillingUp`.
The Longhorn scheduler's live minimum free-space setting was 10% during the
audit. Keep the disk headroom threshold aligned with that setting.

The scratch and allocatable GPU alerts use the four two-GPU worker names
from the current cluster inventory. Update their selectors and expected GPU
count when adding or reprovisioning workers. The scratch mount rule expects
a reporting node exporter. The Longhorn robustness expressions use Longhorn
1.9's numeric states. Recheck them with each Longhorn upgrade.

A stable nonzero XID remains open until its value clears or its series
disappears. The code gauge cannot count repeated incidents with the same
value. GPU inventory and kubelet signals cover schedulability and
container starts. CUDA workload execution requires a GPU workload probe.
Endpoint readiness covers the Kubernetes Service backends. The low-volume
Harbor route relies on readiness and workload rules when it has too few
requests to evaluate the ingress error condition. Registry cache
hit/miss telemetry and direct host page-cache churn telemetry were absent
from the current scrape set.

## Verify the rules

Run from the repository root with `kubectl`, Python 3 with PyYAML, and
`promtool` matching the running Prometheus version.

```sh
PROMTOOL=promtool tests/monitoring/test-cluster-health-rules.sh
```

The fixture suite tests the rendered Fleet manifests with missing and
healthy GPU inventory, a persistent XID across workload label changes,
DCGM sentinel samples, storage faults independent of PVC capacity,
critical Service port availability, and minimum request floors for
ingress and CoreDNS.

On November 24, 2026 the live reference metrics showed seven Ready nodes,
eight allocatable A100 GPUs, four scratch mounts, four Longhorn exporters,
and ready backend addresses on the relevant service ports. Over the previous
seven days, sampled five-minute memory full-stall rates peaked at 0.57%,
Longhorn physical disk utilization at 86.6%, and managed ingress 5xx counts
at about 18 per ten minutes. CoreDNS peaked at 57.4% misses and 1.56 ms p95.
