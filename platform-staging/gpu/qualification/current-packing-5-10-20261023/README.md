# Current cross-Hub 5+10 GiB packing — 23 October 2026

Two ordinary Source lifecycle starts selected the released shared notebook image
on the attested GPU2 A100. A fresh CPS fixture contains Mikasa; the existing CIT
student fixture contains Armin. Scoped approvals and two-hour temporary grants
selected 5 and 10 GiB. No MIG, driver, kernel or device reset was used.

Sequential starts reached Ready in 128.063 and 143.558 seconds. Both workspaces
then ran simultaneously on GPU UUID 16128952-b438-556a-00bb-93039ee24e56.
Each direction rejected an over-cap ordinary PyTorch allocation (cap +256 MiB)
and recovered with a new 64 MiB allocation. Its peer completed 990 synchronized
GPU progress iterations over 25 seconds, with the rejection/recovery timestamps
inside that interval. These are fresh automatic-cap and two-peer packing checks,
not a rerun of every IPC/import/MPS scenario or eight-GPU pool qualification.

The initial simultaneous starts did not reach CUDA: the native coordinator
rejected one lease at its nonblocking durable execution fence, while the other
lost current Node acknowledgment readiness. Normal confirmed cleanup completed;
sequential starts separated the packing test from this unresolved concurrency bug.
Concurrent-start admission and representative bursts therefore remain open.

Both test servers were stopped normally, temporary grants expired, temporary
approvals revoked and both original CPU ceilings/profiles restored. Four-component
readiness returned. No member reservation, binding or KAI reservation Pod remains.
The earlier archived CPS fixture correctly rejected the attempted profile change;
it was not reopened. No research-workload stop/reset was issued by this test.

## Startup performance is now an explicit objective

The user rejects 128-second warm starts as the desired experience. Receipts split
CPS/CIT starts into pre-Pod work (41/45 s), creation-to-node assignment (48/56 s),
init/start (12/14 s), and notebook-start-to-Source-ready (27/28 s). Image retrieval
was already warm (CPS 104 ms). Coordinator preparation itself took 33/44 seconds,
including enrollment-publication stages of 20/26 seconds. Nested timing totals
are not additive. This evidence is a baseline, not a speed improvement.
