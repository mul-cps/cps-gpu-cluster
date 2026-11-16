# Stock Fractioning telemetry observation

Read-only observation; no node, Pod, exporter, Prometheus, Fleet, or chart
configuration changes are made by this capture.

At 2026-11-16 20:33 UTC, both stock monitoring targets are **up**, with empty
`lastError`: `podMonitor/gpu-fractioning/gpu-fractioning-metricsd/0` at
`10.42.7.155:2112`, and `serviceMonitor/gpu-fractioning/gpu-fractioning/0` at
`10.42.3.203:8080`. Both scrape every 30 seconds. Prometheus selectors include
both monitors without extra release-label restrictions. See
`prometheus-targets.json`, `prometheus-selectors.json`, and the live monitor JSONs.

The actual exporter Pod is `gpu-fractioning-fractiond-sdf6w`, UID
`c9cf5712-6c7a-4d74-a6e0-09e47c05d265`, on GPU2. Its retained startup log says
NVML initialized and GPU process metrics enabled. At idle, `/metrics` emits
no GPU series; Prometheus contains only target/scrape bookkeeping for this
job. Target health alone therefore does **not** demonstrate per-Pod usage or
SM measurements.

Fleet Bundle `fleet-local/gpu-fractioning` is Ready=True with 1/1 deployments
ready. Its BundleDeployment is Ready/Installed/Deployed/Monitored=True,
`modifiedStatus=[]`, and desired/applied deployment IDs match. Ownership
remains Fleet GitRepo `cluster-maintenance`, Helm `gpu-fractioning` v0.1.9,
and objectset `default-gpu-fractioning-cattle-fleet-local-system`. The actual
Pod is owned by the stock fractiond DaemonSet, which is owned by
`GpuFractioningConfig/default`. See `bundle-scalar.json`,
`bundledeployment-scalar.json`, and `ownership-chain.json`.

`observe.py` captures bounded five-second observations during the separately
coordinated KAI fixtures: exact exporter UID, fixture Pod UID/container IDs,
KAI annotations, raw `/metrics`, Prometheus instant vectors, and target scrape
timestamps. It performs only Kubernetes GET/proxy GET requests. The maximum
capture duration is 900 seconds; three read failures stop it. It never creates
a Pod or runs CUDA. `kai-live-2035/observations.jsonl` is the initial capture.
Its first interval overlaps a KAI fixture preflight correction, so empty
observations at that point are expected and are not workload-metric evidence.

## KAI workload attribution result

`workload-joins.json` joins all 12 payload Pod UIDs from the two KAI arrival
orders to their assigned physical GPU UUID, CDI annotation, container ID, and
the independently retained driver leaf limits in
`../kai-placement/actual-watchfix/summary.json`. All 12 identity joins agree; leaf limits are exactly 5120, 10240,
or 20480 MiB for the requested profiles. `profile-coverage.json` aggregates
those two orders into six physical GPU × profile combinations.

| Observed nonzero measurement | Coverage |
| --- | --- |
| Exporter memory, distinct payload Pod UIDs | 12/12 |
| Prometheus memory, distinct payload Pod UIDs | 9/12 |
| Exporter memory, physical GPU/profile groups | 6/6 |
| Prometheus memory, physical GPU/profile groups | 6/6 |
| Exporter raw SM, physical GPU/profile groups | 6/6 |
| Prometheus nonzero raw SM, physical GPU/profile groups | 4/6 |

Peak attributed memory is 4512, 9632, and 19872 MiB for the 5/10/20 GiB
profiles on both cards. These measurements include context/driver overhead;
they are not the nominal quota. The raw SM activity bursts are 1%. All six
groups have SM series in Prometheus, but its 30-second scrape misses the brief
nonzero bursts for GPU `GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6` / 10 GiB and
GPU `GPU-16128952-b438-556a-00bb-93039ee24e56` / 5 GiB. Allocation holds generally
show zero SM activity. No scrape settings or workloads were changed to force
positive samples. The omitted nonzero per-Pod memory samples are r0-b-20,
r1-a-10, and r1-a-5; coverage is not claimed for all 12 Prometheus lifetimes.

**Prometheus identity mapping:** use `exported_namespace`, `exported_pod`, and
`pod_uuid` for the workload; `namespace` and `pod` identify the exporter.
`gpu_uuid` is the physical assignment. The raw endpoint uses `namespace` and
`pod` directly, before Prometheus resolves its scrape-label collisions.

This result covers stock Fractioning runtime attribution and ingestion. It
does not establish Hub/gateway service metrics, teaching dashboards, alerts,
or full teaching observability. Any notebook series incidentally observed by
the remaining bounded capture are separate from the completed KAI joins.

## Final state

The bounded capture completed after 480 seconds with **90 observations and
zero read errors**. Exporter UID remained unchanged. Both targets were up with
empty scrape errors throughout all observations and in a fresh final query.
The final raw endpoint was empty and no KAI fixture Pods remained. No notebook
usage witness appeared within this capture; no Hub coverage is claimed.

`bundle-final-scalar.json` reconfirms Bundle Ready=True, deployment Ready=True,
1/1 ready, `modifiedStatus=[]`, and equal desired/applied deployment IDs under
the same Fleet owner. `summary.json` records the exact coverage limits and
empty mutation list. Observation has stopped; directory ownership returns to
the root coordinator for its requested commit.
