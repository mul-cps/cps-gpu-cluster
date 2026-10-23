# GPU member revocation — 23 October 2026

This controlled run uses the deployed 5 GiB CPS shared-GPU lab on the selected
GPU2 A100, fixed policy hash `2054ee32…e1a1fb` and notebook image `fb9872bf…d32a45`.
It does not qualify the eight-GPU pool, other profiles or distributed workloads.

Both ordinary students exchanged edits in separate named Lab workspaces. Editing
used No Kernel because the test notebook's generic kernel name differs from the
GPU image's Conda kernel. CUDA was tested independently in the actual container.
The test measured current-document, open, frame-receiving collaboration sockets;
all two sockets per student closed after normal member removal.

Native cleanup initially returned its typed 409 and retained reservations. The
same lifecycle operation resumed only after cleanup; no reservation or cap was
manually released. The reduced group failed preview under the previous approval.
The console's normal CPU-registration and scoped GPU approval workflow published
the reduced membership through the normal four-component delivery writer. GPU
restart, CUDA, remaining-member access, removed-member 403 and saved edits passed.

The exact original membership record/group and approval body were restored using
audited provider and policy APIs. A final normal GPU start restored both students'
access; final normal close left no active reservation or KAI reservation Pod.
Approval readiness briefly lagged final stop, then converged. The original journal
anchor and all four configuration rotations were retained; dynamic approval heads
advanced to generation 4 (`4248ec94…547c80`). No images, global policy, drivers,
kernels, MIG state or storage addresses were changed during this run.

Individual warm starts took 103.643, 129.344 and 124.333 seconds. These are not the
representative CPS/CIT burst qualification required for production.
