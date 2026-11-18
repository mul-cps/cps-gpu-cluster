# GPU1 final Source shared-GPU evidence, 2026-11-18

Six serial CPS/CIT shared-GPU cycles passed on the deployed final Source `d52d0a7a…` image: 5, 10 and 20 GiB in each service. Both physical A100 cards were exercised. Every cycle confirmed normal stop and returned capacity, retained files, SDK workspace identity, raw CUDA progress, above-cap OOM and Torch reference arithmetic. This snapshot ends with the independent GPU credential closure at **05:07:18 UTC**; CPU/member, strict fault and worker acceptance remain open at this boundary.

The full immutable Source/driver/fractiond/notebook image references, reviewed Source commit/module hashes and hardware/runtime hash joins are in `runtime.safe.json`. Hardware UUIDs and workload/process identifiers remain private; public card A/B labels consistently join all six measurements. The deployed driver artifact is identified exactly; these results do not claim an unmodified upstream driver or broader fleet acceptance.

| Service | GiB | Card | START→Pod Ready (s) | CUDA progress (s) | Independent stored scrapes per metric |
|---|---:|---|---:|---:|---:|
| CPS | 5 | A | 12.130 | 45.000 | 2 |
| CPS | 10 | A | 13.129 | 45.000 | 2 |
| CPS | 20 | B | 15.066 | 45.000 | 2 |
| CIT | 5 | A | 12.331 | 45.000 | 2 |
| CIT | 10 | B | 13.491 | 45.000 | 2 |
| CIT | 20 | A | 13.232 | 45.000 | 1 |

These are six individual serial startup observations, **not the startup-burst gate**, p95 qualification, or controller-cutover measurement. Requested/limited annotations and the actual driver leaf both matched 5120/10240/20480 MiB. The unchanged probe filled `(profile GiB − 0.5) GiB`, repeatedly updated/read a 64 MiB window for at least 45 seconds, freed it, then attempted `(profile GiB + 1) GiB` and required CUDA result 2. Context destruction preceded the real Torch CUDA calculation over 262,144 elements compared with the CPU formula. No threshold was reduced. Fixed-profile success here does not replace simultaneous-user contention or the other rollout acceptance cases.

All three fractiond metrics have original stored nonzero samples joined to the exact new Pod/container/GPU and the actual raw-allocation window: memory used, SM utilization and normalized SM utilization. `six-profiles-and-metrics.safe.json` retains every sample timestamp, independent scrape count, min/max, zeros and missing/invalid exclusions. CIT20 has one independent stored scrape per metric; the other five profiles have two. Repeated query evaluation points are not counted as independent scrapes. Prior-window and post-free samples are excluded.

Canonical duplicate allowance was denied: the existing CPS reservation stayed unchanged, the rejected CIT request created neither a Pod nor an active reservation, and the central audit recorded `reservation_conflict` at 04:58:09.152189 UTC. The Source-facing response was **HTTP503**, a remaining presentation/UX issue. A backend HTTP409 was not retained in this case and is not claimed; the exact central cause is measured directly. No second allowance was acquired.

The independent GPU-cohort closure verified owned native credentials absent and authentication denied, raw handoffs removed, ledger closed/done, and the supervisor inactive with exit status0. No credential IDs or raw token material are included.

CPU/member lifecycle on the final image, both strict ACTIVE first-backend200 STOP-response-loss cases, final cleanup/normal Hub restoration, GPU1 acceptance and explicit next-worker promotion remain open in this snapshot. All-eight-GPU acceptance, controller cutover ≤60 seconds and startup bursts p95≤180 seconds/max≤300 seconds remain separate gates.

`private-evidence-hashes.safe.json` is a whitelist of private file references and hashes only. No raw specs, environments, secret data, log bodies or human identities are published. `manifest.safe.json` freezes the public payload; hashes were independently re-read and validated before handoff. This directory alone was written; no commit or live action was performed by its producer.
