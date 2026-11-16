# Real CIT 5 GiB workspace: retained Prometheus history PASS

This read-only follow-up qualifies memory and SM attribution for the actual Source QA notebook after the earlier 900-second observer ended. No workloads, Pods, nodes, runtime settings, scrape configuration or membership were changed.

The query covers **2026-11-16 22:12:45–22:14:30 UTC**, selecting exact `pod_uuid="5c168368-66a3-4c50-b26f-0a05d1b9c7f1"`. Both the requested `query_range` response and a raw stored-sample matrix query are retained. The range query's ten evaluation points are resampled values: there are **two independent stored scrapes per metric**, one positive and one zero.

| Stored scrape UTC | GPU memory bytes | SM utilization | Normalized SM |
| --- | ---: | ---: | ---: |
| 22:13:44.871 | 5,268,045,824 (4.90625 GiB) | 83% | 100% |
| 22:14:14.871 | 0 | 0% | 0% |

The positive sample lies inside the exact app-recorded raw allocation/progress interval **22:13:10.141744–22:13:55.242873 UTC**. The workload allocated/fill-tested **4.5 GiB**, completed 803,762 progress operations on a 64 MiB window over 45 seconds, observed typed CUDA OOM 2 above the hard cap, freed/destroyed the raw context, then passed a 262,144-element PyTorch CUDA/CPU-reference comparison. NVML process memory includes context/runtime overhead, so the sampled 4.90625 GiB need not equal the 4.5 GiB explicit allocation; it remains below the 5 GiB annotation. The subsequent zero scrape follows context release.

## Exact identity join

| Identity | Retained value |
| --- | --- |
| Workspace namespace / Pod | `cit-jhub/jupyter-cit-ws-4f8bebfab68c2dc3f8cea6df357d874c--rtc` |
| Pod UID | `5c168368-66a3-4c50-b26f-0a05d1b9c7f1` |
| Notebook CID | `095de7db2b2a67a8b44a3c7b9b49fffa92d2565cc6dd2d6e77a1b1b18287e903` |
| Image | `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:4a03fe381c6f32f8e056ac05aad27abc64defa2f63128c53511a24d37fb5c194` |
| GPU UUID | `GPU-16128952-b438-556a-00bb-93039ee24e56` |
| Protected request / limit | `5120Mi` / `5120Mi`, required plugin `gpu-fractioning` |
| Node / node UID | `k3s-wk-gpu2` / `3336cdd5-d245-436e-b57c-2f66c6dcaa41` |
| Boot ID | `8874dcda-ced2-4aa4-b5cb-71a0871abdd5` |
| Stock exporter | `gpu-fractioning/gpu-fractioning-fractiond-p57lq`, endpoint `10.42.7.231:2112` |

The metrics' `exported_namespace` and `exported_pod` identify the notebook. Their `namespace`, `pod` and `container=metricsd` identify the exporter; these label collisions must not be mistaken for workload identity. `pod_uuid` and `gpu_uuid` match directly. CID is joined through the exact Pod evidence; it is **not** itself a metric label.

`cit5-history-join.json` retains the exact app artifacts' SHA256 identities, Pod/container/annotation evidence, workload stages, all metric labels and independent stored sample counts. The source artifacts are `/home/bjoern/artifacts/cps-upstream-sharing-20261116/registry-qa-cit-5-final-{pod,jupyter}-evidence.json`. No credentials are copied. The workspace agent confirmed that no exact kernel cgroup-leaf/limit file was retained before normal Pod stop. A bounded fractiond log search (since 22:05Z, last 1,200 lines) found no matching exact CID/PodUID lines; `cit5-fractiond-identity-log.json` retains that empty result. Typed OOM 2 is a separate hard-cap behavior witness, not a leaf-path/file read. No exact leaf or lease-store witness is inferred from annotations or invented after Pod deletion.

The qualified CIT Pod UID was absent at the final read-only check, and both stock targets were UP with no lastError. Its metric series had already reached zero after context release. This proves **1/1 sampled CIT workspace with nonzero memory and SM**, followed by a zero sample. It does not establish a dense performance trace, full teaching observability, or retroactively fill the earlier short CPS5 capture's missing samples.

## Reproducible read-only queries

- `cit5-query.json` → `query_range`, exact UID selector, start/end above, five-second evaluation step. Response: `cit5-pod-uid-range.json`.
- `cit5-stored-samples-query.json` → instant query of the same selector with `[105s]` at `22:14:30Z`, preserving stored scrape timestamps. Response: `cit5-stored-samples.json`.
- All queries use the existing authenticated Kubernetes service proxy to the stock `cattle-monitoring-system/rancher-monitoring-prometheus:9090` API. No Prometheus configuration was changed.


## Later authoritative Source CPS10 history

At the workspace agent's request, the exact CPS10 Pod UID `5f8a0685-1cd0-4ac0-8e71-ca134755503b` was queried over 22:42:30–22:45:00 UTC using a raw stored-sample matrix. The actual recorded raw stage was 22:43:17.606444–22:44:02.722505 UTC. One independent positive scrape at **22:43:44.871Z** measured **10,636,754,944 bytes (9.90625 GiB), 82% SM, normalized SM 100%** on GPU-A. Two subsequent stored scrapes at 22:44:14.871 and 22:44:44.871 were zero, after the raw context was freed. Exact exported namespace/Pod, Pod UID, GPU UUID and public workload stages match; `cps10-history-join.json` retains source hashes and the CID through the Pod artifact. Root separately captured the active kernel leaf; its retained path is pending explicit cross-reference. No new workload or observer was started for this historical query.
