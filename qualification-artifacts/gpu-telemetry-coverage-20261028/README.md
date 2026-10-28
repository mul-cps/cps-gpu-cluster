# GPU telemetry coverage restored — 28 October 2026

The live cluster advertised eight GPUs, while fresh DCGM UUID telemetry covered only six. GPU2 had `nvidia.com/gpu.deploy.dcgm-exporter=false`, a manual exclusion from the R615 canary work. The operator DaemonSet selects this label's `true` value, so no exporter Pod or Service endpoint existed on that node. This was not evidence that a physical GPU was absent.

An isolated Pod using the currently deployed DCGM exporter image (`nvcr.io/nvidia/k8s/dcgm-exporter:4.4.1-4.6.0-distroless`) reported two distinct GPUs on GPU2 for free/used framebuffer memory, utilization and temperature. It was excluded from the exporter Service, then deleted with exact UID/resourceVersion preconditions and observed absent. GPU2 had no assigned GPU workloads before this bounded monitoring probe.

Only GPU2's exporter deployment label was changed to `true`, using node UID/resourceVersion preconditions; every other label was checked unchanged. No driver, kernel, MIG, toolkit or device-plugin setting was changed. The operator then supplied its ordinary exporter Pod.

The reviewed `ComputeGPUCollectorCoverageIncomplete` alert was appended to the existing `cps-compute-observability` PrometheusRule with UID/resourceVersion checks; all existing rules were preserved. Prometheus loaded it automatically, first reported the missing GPU2 coverage as pending, then resolved the condition after the fourth exporter became available. No manual Prometheus reload or Pod restart was required.

`verification.json` records four ready exporter Pods/endpoints, two fresh UUID series per GPU node (8/8), sample ages, an empty coverage condition and an inactive healthy alert. This proves current telemetry coverage and rule evaluation, not memory-isolation qualification, scheduling eligibility, physical free GPUs, or notification delivery. No raw UUIDs, IP labels, credentials or Secret payloads are included.

The rule source is committed on the compute qualification branch but is not yet on Fleet's watched `main`. The current live change is therefore not unattended GitOps durability. Source promotion remains part of the final deployment/release work, with the existing native overlays preserved.
