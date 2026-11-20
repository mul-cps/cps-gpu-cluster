# Live compute monitoring read check

The [2026-10-07 report](monitoring-live-rules-report.json) compares the deployed
compute PrometheusRule with Git and queries the actual Prometheus API through a
temporary operator port-forward, which was closed afterward. No monitoring
configuration or workloads were changed.

The rule specification matches Git. All five rules evaluate with health `ok` and
no evaluation errors. CPS and CIT Hub targets and KAI admission, scheduler, binder
and queue-controller targets report `up=1`. DCGM provides eight device series;
the oldest observed sample is approximately 13.4 seconds old.

Both Hub spawn-p95 recordings return `NaN`; they provide no usable latency
qualification at this observation. Eight observed VRAM series are eight observed
devices, not eight physically free GPUs. Placement-eligible capacity still needs
the qualified accounting exporter, and collector failure/staleness behavior was
not induced in the live cluster. Promtool regression tests cover those expression
cases separately.

This evidence qualifies the read path and rule deployment comparison only.
Representative startup bursts, teaching protection, physical free-GPU accounting,
hardware scheduling and rendered Grafana behavior remain independent gates.
