# Live pooled-member acceptance — 23 October 2026

The deployed gateway at source `8bdacc4` started the existing QA workspace on
`interactive-shared-10` using two distinct, reviewed canonical members. Each
member had only an existing 5 GiB shared-GPU grant; no grant was added or changed.
The ordinary Source approval/profile/start path succeeded. A read-only query
verified exactly those two global member reservations and one workspace binding.
The ready notebook completed a 64 MiB PyTorch CUDA allocation/write/synchronize
on the A100. This is a functional pooling smoke, not another isolation stress
or concurrent cross-Hub race qualification.

Startup took 184.86 seconds: 53.30 before Pod creation, 83 to actual PodScheduled,
21 from assignment to notebook-container start, and 27.57 until Source readiness.
Storage verification took 6.36 seconds. No startup improvement or burst/p95
qualification is claimed.

Normal close confirmed native shutdown and released reservations. The QA fixture
is stopped on CPU, with its original single membership, course ceiling and notice
restored. The temporary Armin membership and GPU approval were removed. Original
grants were read back unchanged. Global member reservations and workspace bindings
are zero, all 26 native allocation records are released, and the QA Pod is absent.
The original research Pod remains Running with the same UID. No manual reservation
release, SQL mutation, TTL-based release, driver or storage change was used.
