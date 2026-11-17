# GPU3 Source E6 lifecycle and closure — 2026-11-17

Both CPS and CIT completed the bounded Source CPU/member-removal/restart and duplicate-start/STOP-response-loss cases. [Independent evidence checks](independent-evidence-check.safe.json) bind the six actual notebook executions and verify grant cleanup. This is **not worker promotion, original Hub restoration, human SSO, or general fault-tolerance acceptance**. Those boundaries remain separate; original Hub restoration was still pending when this packet was assembled.

## CPU isolation, member removal and retained restart

Each Source started `interactive-cpu` with ABCD, opened one owned kernel WebSocket and two RTC WebSockets, then used supported Source member removal for A. Both RTC connections received initial synchronization frames. All three held sockets closed automatically; before any manual STOP, Source was stopped, the Pod absent, and the lease inactive with a null attempt. Source membership and the native Hub group then contained exactly BCD, with the reconciliation barrier cleared.

| Source | Initial CPU PodUID | BCD restart PodUID | All held sockets closed (UTC) |
|---|---|---|---|
| CPS | `6be85442-6aa2-4404-86e2-6ef1798c207c` | `d75d02ac-2d1b-4c92-98a8-0eabd9b1b636` | 21:05:24 |
| CIT | `b0bd4898-7ae2-4705-9358-8f728dae73ed` | `b5d93a96-3300-484e-a58f-de114981bd9b` | 21:07:40 |

All four CPU Pods ran on **GPU1**, with no NVIDIA runtime class or GPU assignment annotations. Notebook probes saw no GPU device nodes, no loadable `libcuda`, and `torch.cuda.is_available() == false`. The same retained-file sentinel hash `95976f0f…` and workspace SDK identity/catalog `2b2ad6ce…` were observed before and after restart. This proves CPU isolation on the actual scheduled node, not CPU placement on GPU3. The original image `4a03fe38…` and zero recorded notebook restarts are retained in each Pod receipt.

- CPS: [automatic removal and socket events](cps-automatic-held-removal.safe.json), [Source membership/barrier](cps-source-membership.safe.json), [native group Share](cps-hub-group-share.safe.json), [central BCD roster after normal restart](cps-central-roster-after-restart.safe.json), [restart notebook](gpu3-cps-cpu-after-remove-e6-jupyter.safe.json).
- CIT: [automatic removal and socket events](cit-automatic-held-removal.safe.json), [Source membership and native Share](cit-source-hub-membership-share.safe.json), [central BCD roster after normal restart](cit-central-roster-after-restart.safe.json), [restart notebook](gpu3-cit-cpu-after-remove-e6-jupyter.safe.json).

The central roster was observed **after supported normal re-registration**, not assumed to update at the instant of removal. The two RTC sockets used the same neutral workload-owner identity. Service reads verify native membership/Share state; neither two-human collaboration nor human member authentication is claimed.

## Concurrent start and complete STOP-response loss

Each Source sent two concurrent START requests and observed HTTP **400 and 200**, one actual Pod and one current attempt. The resulting `interactive-shared-5` notebook ran on GPU3 with the mandatory fractioning annotation, filled 4.5 GiB for 45 seconds of useful CUDA progress, returned CUDA result 2 above the hard cap, then passed the PyTorch CPU-reference check.

| Source | Actual PodUID | Attempt | Raw progress steps | STOP backend / caller |
|---|---|---|---:|---|
| CPS | `99408346-56d4-4801-9248-39c57a9ffb04` | `d7f4f959-7fe7-4a5a-9b55-3bfcfb506749` | 786,645 | 200 / EOF, zero bytes |
| CIT | `4ada2d7d-9a26-4a4c-9930-45f1f17f6ccc` | `4838915b-64f7-469f-8538-9cf83751286d` | 791,221 | 200 / EOF, zero bytes |

The selected PodUID and containerID were matched to the probe immediately before the fault, and the reservation was unchanged. A one-shot loopback proxy consumed the entire actual backend **200** response and forwarded **zero HTTP bytes**, producing `RemoteDisconnected`. Fresh observations established Source stopped, Pod absent and lease inactive/null **before** one idempotent STOP replay returned 200. Both inherited fault helpers exited 0. This is actual complete STOP-response loss, not dropped START-response acceptance or every possible disconnect race.

[CPS fault receipt](cps-duplicate-stop-loss.safe.json) and [CIT fault receipt](cit-duplicate-stop-loss.safe.json) retain the exact request count, response hashes, timing, PodUID/attempt and cleanup ordering. The [operator execution attestation](execution-and-local-closure.safe.json) records terminal session 76841 exit 0; it is explicitly not a raw process transcript. Both fault notebooks used GPU `GPU-0a9f2da8-59f5-1cb0-9ead-d9fce56b69e5`, GPU3 NodeUID `7b3b5113-158d-4e0d-bd63-898a508fe806`, boot `1fcf5b3e-c7c6-4d47-9a28-88a9a36be95a`.

## Final closure

Supported removal of the remaining BCD memberships completed for both Sources. [CPS final cleanup](cps-final-source-cleanup.safe.json) and [CIT final cleanup](cit-final-source-cleanup.safe.json) record zero QA memberships, stopped Source state, absent Pod, inactive/null-attempt lease, normal STOP replay 200 and no owner-file deletion.

[Five-grant closure](five-grants-closed.safe.json) records only the four CPS QA grants and CIT QA-A grant disabled: profiles/projects empty, allowance zero and expiry in the past. All 58 records remain, the other 53 raw rows are identical, and the authorized original-49 guard passed. The independent reader verified the before/after raw snapshots without publishing their contents.

[Credential closure](credential-closure.safe.json) records CPS `a1430` and CIT `a740` revoked and rejected by authentication, with no errors. The reader independently confirmed the done marker and absence of both raw token handoff files. Watchdog inactivity and terminal completion are explicitly attributed to the operator's [execution/closure attestation](execution-and-local-closure.safe.json).

At 21:18:51 UTC, [post-cleanup physical readback](both-card-postcleanup-idle.safe.json) showed both GPU3 cards at 1 MiB, 0% utilization, no compute processes and MIG disabled, with driver 620.70.06. This is a point-in-time idle witness, not a worker-promotion decision.

The deployed Source fix remains image `478ec4f55f4a10ae9b04c7ddb7792c041cbe36556911a3661e64f59e2527f126`, module `4fc27138…`; [E5 delivery evidence](../gpu3-source-e5-20261117/README.md) records its single-module scope and both Source Deployment generations 122. E6 introduced no new GPU runtime patch. The separate canonical-quota enforcement PASS versus Source HTTP-503 presentation failure remains as documented in E5; these fault passes do not change that UX result.

No original Hub-template restoration, temporary QA-object deletion, maintenance-taint removal, or worker promotion is asserted here. `manifest.safe.json` hashes all public files except itself. Only sanitized receipts and observed notebook metadata/results are included; no credentials, raw configuration, private logs or raw grant data are published.
