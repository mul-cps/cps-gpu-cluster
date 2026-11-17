# GPU3 Source E5 evidence — 2026-11-17

Five resumed real Source GPU profiles passed notebook execution on GPU3: CPS 10/20 GiB and CIT 5/10/20 GiB. This is a scoped lifecycle and telemetry receipt, **not GPU3 worker acceptance**. The earlier CPS 5 GiB result remains separate. Source CPU/member/fault completion, human SSO, and burst latency percentiles are not claimed here; E6 continued separately.

## Actual notebook execution and cleanup

[Lifecycle summary](five-profile-lifecycle.safe.json) joins each actual PodUID, containerID, GPU UUID and probe. All five saw one CUDA device, filled profile minus 0.5 GiB, made useful 64 MiB memset/synchronize progress for 45 seconds, received CUDA result 2 for an over-cap allocation, freed/destroyed the raw context, then matched a 262,144-element PyTorch CUDA result against its CPU reference. The notebook SDK reported workspace identity and catalog `2b2ad6ce…`; the retained-file sentinel hash matched across all five.

| Source/profile | Fill GiB | Progress steps | Start → Pod Ready (s) | Probe |
|---|---:|---:|---:|---|
| CPS 10 | 9.5 | 797,585 | 14.758 | [actual result](gpu3-cps10-resume-e5-probe.safe.json) |
| CPS 20 | 19.5 | 792,564 | 12.570 | [actual result](gpu3-cps20-resume-e5-probe.safe.json) |
| CIT 5 | 4.5 | 794,089 | 12.299 | [actual result](gpu3-cit5-resume-e5-probe.safe.json) |
| CIT 10 | 9.5 | 793,692 | 14.100 | [actual result](gpu3-cit10-resume-e5-probe.safe.json) |
| CIT 20 | 19.5 | 794,371 | 13.142 | [actual result](gpu3-cit20-resume-e5-probe.safe.json) |

These five individual timings are not a distribution or percentile qualification. All Pods had zero recorded restarts, the immutable notebook image `4a03fe38…`, runtime class `nvidia`, exact 5/10/20 GiB assignment annotations and mandatory `gpu-fractioning`. NodeUID was `7b3b5113-158d-4e0d-bd63-898a508fe806`, boot `1fcf5b3e-c7c6-4d47-9a28-88a9a36be95a`. Both GPU UUIDs occur in the linked Pod/probe receipts.

The [operator attestation](root-execution-and-closure.safe.json), explicitly not a raw process transcript, records matrix session 42092 terminating with exit 0 after every cycle's probe and normal-stop assertions. The helper overwrote its stop receipt per Source, so this directory does **not** present five separately retained lease-zero receipts. The final [CPS stop](cps-confirmed-stop.safe.json) at 20:58:08 UTC and [CIT stop](cit-confirmed-stop.safe.json) at 21:02:47 UTC independently record Source stopped, Pod absent, lease inactive and attempt null.

[E5 credential closure](credential-closure.safe.json) records CPS `a1425` and CIT `a735` revoked and rejected by authentication, with no errors. [Local closure verification](credential-local-closure.safe.json) confirms the done marker and absence of both raw token handoffs; watchdog inactivity is attributed to the operator's separate terminal/unit verification. No credentials or private logs are published.

## Stored metrics

[Five-profile summary](metrics-five-profile-summary.safe.json) and [sanitized original samples](metrics-original-samples.safe.json) show nonzero stored memory and SM values for **5/5 profiles**. Each profile has exactly **one distinct original Prometheus scrape** inside its measured raw allocation/progress/free window, for memory, SM and normalized SM. Query evaluation points were deduplicated by original timestamp; they are not extra scrapes. Each sample was independently joined to exact PodUID/GPU UUID/exported namespace and Pod, and the event/Pod source hashes were checked against the per-profile metrics receipt.

| Source/profile | Memory used bytes | SM % | Independent memory / SM scrapes |
|---|---:|---:|---:|
| CPS 10 | 10,636,754,944 | 82 | 1 / 1 |
| CPS 20 | 21,374,173,184 | 82 | 1 / 1 |
| CIT 5 | 5,268,045,824 | 83 | 1 / 1 |
| CIT 10 | 10,636,754,944 | 76 | 1 / 1 |
| CIT 20 | 21,374,173,184 | 82 | 1 / 1 |

This is sampled usage coverage, not continuous tracing or an allocation-limit gauge. Physical usage includes context overhead and differs from the explicit raw allocation. No performance percentile, universal telemetry coverage or human teaching observability claim follows.

## Source fix and permanent Gateway read access

The [published Source pin](source-published-pin.safe.json) is `ghcr.io/mul-cps/e2x-course-hub@sha256:478ec4f55f4a10ae9b04c7ddb7792c041cbe36556911a3661e64f59e2527f126`, source `10d4a8e82225c60d4455c572c25c62d9a27b964b`, module SHA `4fc27138f79d4054f1bf7aaa9f5da436a9f0ee83c1df9824934da6b23054eeeb`. [Image closure](source-one-module-closure.safe.json) preserves 51 other Python modules, all 70 base layers and all non-label image configuration. [Installed causal tests](source-installed-tests.safe.json) record old failure/new success. Both [CPS](source-cps-postroll.safe.json) and [CIT](source-cit-postroll.safe.json) were Ready at Deployment generation 122, with all other specification fields, Source DB tables/schema/state and PVC/PV identities preserved.

The fix permits an exact native “No such server” Shares response only during confirmed-stopped member removal, followed by a fresh exact-owner read proving the named server absent. Normal start remains strict. The actual supported retry [cleared the reconciliation barrier and removed A](source-barrier-reconciled.safe.json); normal CPU restart [restored the native group Share for B](source-group-share-restored.safe.json). Those service-identity observations do not authenticate a human member or qualify the separate E6 CPU/member/fault matrix.

Permanent Gateway node-read source was adopted in platform commit `76188661b59ec4c29823102f366f32604f691dde`, under `cluster-maintenance/clusters/cit-cps-gpu/system/gpu/gateway-node-observer/`. The [actual access receipt](gateway-permanent-access.safe.json), taken after the temporary grant and binding were absent, records the real Gateway service account receiving GET 200 for GPU2/GPU3, 403 for GPU1/GPU4, and 403 for node listing. This is the bounded permanent access proof; no broader node read/write authority is claimed.

## Separate quota and error-presentation results

**Canonical quota enforcement passed; the expected Source HTTP status check failed.** [Gateway audit 9265](canonical-denial-audit.safe.json) records CIT `reservation_conflict`, unchanged CPS ownership and an inactive/null-attempt CIT lease. The [CIT Hub trace](canonical-denial-cit-hub.safe.json) shows acquire HTTP 409 in the pre-spawn hook before CREATE. Source instead returned generic HTTP **503**, failing the fixture's expected 400/409 check. That user-facing error-propagation bug remains open; the resumed five-profile matrix did not rerun or relabel it as passing.

`manifest.safe.json` hashes every public file in this directory except itself. All preparation here was local evidence processing; no workload, authority or configuration actions were performed by this evidence writer.
