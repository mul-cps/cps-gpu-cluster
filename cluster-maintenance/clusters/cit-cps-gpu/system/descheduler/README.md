# Descheduler (GPU capacity consolidation)

Deploys the upstream [kubernetes-sigs/descheduler](https://github.com/kubernetes-sigs/descheduler)
Helm chart (v0.33.0, matching Kubernetes 1.33 per the project's own
compatibility matrix) as a `CronJob` running every 5 minutes.

## What it does

Evicts long-running, low-priority `batch`-queue GPU jobs
(`kai-batch-low`, priority value `1000`) so KAI Scheduler can immediately
requeue them elsewhere, freeing GPU capacity for interactive workloads
(`kai-phd-interactive`, `kai-course-high`) whenever they're pending. Two
strategies are enabled in the `batch-only` profile:

- **`LowNodeUtilization`** — consolidates/bin-packs pods off underutilized
  nodes toward capacity, using `cpu`, `memory`, `pods`, and the extended
  resource `nvidia.com/gpu` as utilization signals.
- **`RemovePodsViolatingNodeAffinity`** — evicts pods that no longer satisfy
  their node affinity (e.g. after node labels change).

True GPU workload live-migration doesn't exist; this relies on the
"checkpoint + evict + requeue" model. Batch job submitters are expected to
checkpoint periodically to shared storage — see
`system/gpu/kai-scheduler/docs/batch-job-submission.md` for submitter-facing
guidance (not duplicated here).

## Safety guarantee: interactive/student sessions are structurally unreachable

Every plugin above runs behind the chart's `DefaultEvictor` filter plugin,
which is configured with:

```yaml
priorityThreshold:
  value: 1001
```

`DefaultEvictor` gates *every* eviction decision made by the profile against
this threshold before any strategy plugin runs. Verified from the
descheduler source
(`pkg/framework/plugins/defaultevictor/defaultevictor.go`,
`IsPodEvictableBasedOnPriority`): the comparison is
`pod.Spec.Priority < priorityThreshold.value` — strictly less-than.

Because of that strict inequality, the threshold is set to `1001`, not
`1000`. Setting it to exactly `1000` (the `kai-batch-low` PriorityClass
value) would have excluded `kai-batch-low` pods themselves, since `1000` is
not `< 1000` — defeating the bundle's purpose. With `1001`:

| PriorityClass          | Value | `value < 1001`? | Evictable? |
|-------------------------|-------|------------------|------------|
| `kai-batch-low`          | 1000  | yes              | **yes**    |
| `kai-phd-interactive`    | 5000  | no               | no         |
| `kai-course-high`        | 10000 | no               | no         |

This is enforced structurally by the descheduler's own policy config, not by
convention — no combination of labels, queues, or scheduling behavior can
cause an interactive or student JupyterHub session to be evicted by this
bundle, short of someone re-editing `values.yaml`.

PodDisruptionBudgets are respected by default (the descheduler evicts via
the standard Kubernetes eviction subresource, which honors PDBs) — no
additional configuration was needed for that.

## Layout

- `fleet.yaml` — pins the official `descheduler` chart
  (`https://kubernetes-sigs.github.io/descheduler/`) at `0.33.0`.
- `values.yaml` — `CronJob` schedule (`*/5 * * * *`, chart default is every
  2 minutes — widened slightly to reduce API churn at this cluster's scale),
  `DeschedulerPolicy` (API `descheduler/v1alpha2`) with the `batch-only`
  profile described above.

## Verifying it's working

```bash
# Descheduler pods/jobs
kubectl get pods -n descheduler
kubectl get cronjob -n descheduler

# Eviction decisions and dry-run/real evictions get logged per run
kubectl logs -n descheduler -l app.kubernetes.io/name=descheduler --tail=200

# Confirm no interactive/course pods were ever touched: cross-check evicted
# pod names/namespaces in the logs above against the `phd-interactive` /
# `courses` KAI queues — none should appear.
kubectl get pods -A -l kai.scheduler/queue=batch
```

Eviction events are also visible via `kubectl get events -n <pod-namespace>
--field-selector reason=Evicted` for evicted batch pods.
