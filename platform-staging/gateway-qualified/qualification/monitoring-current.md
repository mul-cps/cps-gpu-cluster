# Current scraping and Descheduler safety audit

At 2026-10-06, live Prometheus targets were up for both Hubs, Argo, KAI admission/binder/scheduler/queue controller, the resource-isolator monitors, both gateway metrics endpoints and DCGM. The 22 relevant active targets include duplicate monitor discovery; this is a transport inventory, not 22 independent components or proof of correct aggregation. Evidence: `/home/bjoern/cps-platform-evidence/2026-10-06/monitoring-current/report.json`.

Descheduler had no scrape target. Its live five-minute CronJob used v0.34.0 and a policy with priority threshold 11 and PVC protection, but lacked the candidate's restartable-batch opt-in and four gang/JobSet label exclusions. The fallback was suspended; there were no active Jobs at suspension. KAI was neither changed nor stopped. This is a temporary safety measure, not completion of the fallback-removal performance comparison.

Git values now explicitly keep the CronJob suspended. Rendering the pinned 0.34.0 chart confirms the pause, required `descheduler-eligible=true` label and all four DoesNotExist gang exclusions. Both scope tests pass. Candidate rendered manifests, the live before-state and suspension report are retained under `descheduler-scope/` in the private operator archive.

Before resuming, qualify the narrow policy with controlled, non-mutating runtime probes, confirm live policy alignment and implement reliable Descheduler metrics. Short-lived CronJob targets must not be reported as continuous telemetry. The required KAI-with/without-fallback churn comparison, physical free-GPU measurement, startup/wait thresholds and protected-session checks remain open. Do not resume the legacy broad policy or remove the fallback permanently based on scrape health or static scope tests alone.

## Actual Descheduler binary dry-run

The exact deployed image `registry.k8s.io/descheduler/descheduler@sha256:18ecceedd6096627d9e496f5332e9d2431587f53699802d35393f40a5a7b7239` completed a real-cluster run with the candidate policy and `--dry-run --secure-port=0 --disable-metrics`. The process exited zero and reported zero evictions. The policy SHA256 was `2a3e9f8f4fa5acc17d34bc11acfda547cdecf02d0832fb9aaa97cceb24caf3c6`.

The temporary service account had read-only resource permissions. SubjectAccessReviews confirmed permitted Pod/Node reads, denied Pod updates/patches, denied Node changes/event creation and denied eviction creation separately in all 82 namespaces. Its Pod had a read-only root filesystem, no extra capabilities, bounded CPU/memory/deadline and only policy plus short-lived projected API identity mounts. Namespace egress was restricted to the Kubernetes API addresses. ClusterRole/Binding and namespace were deleted afterward. Production Descheduler remained suspended; KAI was unchanged.

Evidence: `descheduler-scope/readonly-probe-inputs.json`, `readonly-probe-report.json`, the controlled probe script and mode-0600 runtime logs in the private archive. Logs may contain workload identifiers and must not enter Git. Git now pins this tested image digest using the chart's supported `image.tag` field; rendered image integrity and suspension are checked.

This confirms binary/policy compatibility and read-only operation against the current cluster. Zero evictions under current inventory does not prove adversarial opt-in/gang classification, correct real eviction, protected-session behavior or defragmentation performance. These gates and reliable metrics remain open before resumption.
