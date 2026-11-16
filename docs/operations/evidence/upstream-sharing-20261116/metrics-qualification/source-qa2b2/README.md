# Real Source QA runtime metrics capture

This read-only, 900-second observation follows the actual CPS/CIT notebook QA on GPU2 boot `8874dcda-ced2-4aa4-b5cb-71a0871abdd5`, after the successful metrics driver-ready cold-boot gate. It creates no workload, changes no workload timing, invokes no CUDA calls, and changes no node, Pod or configuration.

Authorized owners:

- CPS: `cps-ws-2114b8e3a15e8913cb98083bd5673e45`, server `rtc`.
- CIT: `cit-ws-4f8bebfab68c2dc3f8cea6df357d874c`, server `rtc`.

The immutable notebook image is `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:4a03fe381c6f32f8e056ac05aad27abc64defa2f63128c53511a24d37fb5c194`; the coherent catalog identity is `sha256:2b2ad6ce656db38a0e9cc2a0d3365c48d6061a835d317236a322776c11dc3fcb`. Deployment/configuration acceptance is owned by the root and workspace agents; this capture checks actual runtime telemetry.

The stock exporter is `gpu-fractioning/gpu-fractioning-fractiond-p57lq`, Pod UID `9e2e3161-2b79-43d9-89cd-f959e107abc1`, on GPU2. `observe.py` checks this UID on every iteration and stops if it is replaced. It records actual notebook Pod UID, container ID/image, KAI assignment, protected memory and mandatory-plugin annotations, raw exporter output, Prometheus instant-query results, and both stock target health records. It does not retain container environment variables or credentials. Read errors are retained explicitly; ten read errors end the capture early.

The first actual notebook observed is CPS `jupyterhub/jupyter-cps-ws-2114b8e3a15e8913cb98083bd5673e45--rtc`, Pod UID `2ae294e8-e8f9-47b0-abbc-4eaf6d37f0c3`, notebook container `2e8254e22dfce6c56afb561732c0bc0ce9ee382f347011973706e18dddbe2056`. It has the exact image above, KAI scheduler, GPU UUID `GPU-1e6145d5-8ee2-43e2-a0d5-6d345909e8a6`, protected request/limit `5120Mi`, and required plugin `gpu-fractioning`.

Coverage must distinguish Pod assignment from actual GPU usage. A Ready Pod with annotations alone is not usage proof. Raw observations occur approximately every five seconds, while Prometheus scrapes at its configured interval; short kernels can be absent from Prometheus even when visible in a direct read. Memory and SM series presence, nonzero values, exact Pod UID attribution and cleanup are reported separately. CPU-only profiles are not expected to emit GPU series. Lease/kernel-leaf evidence comes from the workspace agent and is joined by exact Pod/container/GPU identity rather than inferred from similar names.

The final finite coverage and any remaining limitations will be recorded alongside the retained `capture/observations.jsonl` and `capture/capture-summary.json`.


## Finite result

The observer completed normally at 21:58:47Z: **156 observations, zero read errors, both targets UP in 156/156 observations**, unchanged exporter Pod UID and restartCount 1. It observed **one CPS notebook and zero CIT notebooks**. Exact metadata attribution covers 1/1 observed GPU-assigned Pod, but raw/Prometheus memory and SM usage coverage are each **0/1**. Every direct exporter response in this interval was empty. This is a telemetry coverage gap, not a positive per-Pod GPU usage result.

`cps5-workspace-proof-join.json` links the exact Pod UID/container/GPU annotation identities to SHA256-identified workspace-agent evidence. That separate evidence records 4.5 GiB fill, 89,314 progress steps over 5.0002 seconds, typed OOM 2 above the hard cap, and a 262,144-element PyTorch CPU-reference match. It records no exact UTC allocation/free interval; file mtime is explicitly only an upper bound. The stock collector's default interval is five seconds (`metricsd/internal/metrics/exporter.go:385`), direct observations averaged approximately 5.8 seconds, and Prometheus has its own slower scrape interval. Missing these short-lived samples is possible, but the cause of the missed coverage is not proved. No workload was repeated or extended by this observer.

CPS was last observed at 2026-11-16T21:57:22.267139+00:00; its normal stop was visible as Pod absence by 2026-11-16T21:57:28.029319+00:00. The final matching Pod set is empty, raw output is empty, and both targets remain UP. No CIT or later 10/20/CPU profile ran within the observed set in this finite window. Those require separate observation. Lease/kernel-leaf witnesses were not present in the supplied public app artifacts and are not inferred here. See `summary.json`, `coverage.json` and the complete retained observations for exact identities and counts.
