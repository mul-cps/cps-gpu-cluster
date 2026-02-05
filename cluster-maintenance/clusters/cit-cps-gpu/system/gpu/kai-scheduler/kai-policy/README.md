# KAI Scheduler Policy

This bundle defines the queues and priority classes for the NVIDIA KAI Scheduler.

## Usage

To route a workload through KAI and assign it to a queue:

1. Set `spec.schedulerName: kai-scheduler` in the Pod spec.
2. Add the label `kai.scheduler/queue: <queue-name>` to the Pod.
3. (Optional) Set the `priorityClassName` to one of the following:
   - `kai-course-high`
   - `kai-phd-interactive`
   - `kai-batch-low`

## Queues

| Queue | Quota (GPU) | Weight | Description |
|-------|-------------|--------|-------------|
| `courses` | 4 | 1 | Reserved for courses, strongest access. |
| `phd-interactive` | 1.5 | 2 | Interactive research work. |
| `batch` | 0 | 10 | Reclaim-first background tasks. |
| `default` | Unlimited | 10 | Fallback for non-specific tasks. |
