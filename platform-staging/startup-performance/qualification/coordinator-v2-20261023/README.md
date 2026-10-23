# Corrected coordinator and Node pilot — 23 October 2026

Gateway fc77489e…4f6392 and Node 88fa54cb…eacd81 are active. The installed
packages passed the actual protected driver-manifest/kernel and immutable-policy
preflight before deployment. The supported journal rotation preserved its
original anchor and all four prior rotations; there are now five, with no
transition pending. The normal writer resumed and four-process readiness passed.
Capture's pinned Node process image was updated; credentials and scope were kept.
No kernel, driver, GPU mode, NFS path or research notebook was changed.

The fresh CPS5/CIT10 CUDA run passed ordinary over-cap rejection and recovery in
both directions while the peer completed 991/990 GPU progress iterations. This
is the current two-peer pilot, not eight-GPU, distributed, import or MPS requalification.

Startup did **not** improve: CPS took 193.09 seconds and CIT 146.82, compared with
128.06/143.56 earlier. A traced CPS restart took 154.21 seconds. Its account setup
was 0.13 seconds, storage verification 15.23, and Hub spawn/readiness 132.16.
Images were cached; three read-only full context loads took 1.022 seconds.
The earlier KAI Scheduled event precedes actual binding, so the breakdown uses
PodScheduled condition timestamps, not that event message. More samples and
critical-path work are required; these are not a burst or p95 qualification.

QA workspaces were stopped through normal cleanup and restored to CPU. Temporary
grants were read back expired, temporary approvals removed, original course
ceilings restored, and all member/binding/KAI reservation counts returned to zero.
One CPU-profile reset was initially rejected; after current neutral provenance,
clean custody and writer availability were checked, the normal idempotent Source
API succeeded. No manual reservation deletion or forced authority bypass was used.

The corrected fixture uses the real bounded RawKubernetesAPI over MockTransport;
16 focused tests pass. A full-suite attempt then passed 3427 tests and 49 subtests,
skipped 3, and stopped at five failures in final-enrollment/fence-diagnostic cases.
Unexecuted tests remain. Those failures and startup performance keep broader
production qualification open. See the machine-readable receipts in this directory.
