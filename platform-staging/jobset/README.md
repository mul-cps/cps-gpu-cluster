# Controlled JobSet qualification

Use chart 0.12.0 and the immutable controller image in `values.yaml`, outside
Fleet. The reviewed install runs one controller in `jobset-system`, internal
webhook TLS, no host networking or public endpoint. Official installation guide:
https://jobset.sigs.k8s.io/docs/installation/.

The 2026-10-05 cluster had an orphan CRD and webhook configuration referring to
absent `kubeflow-system/jobset-webhook-service`, with no JobSets or controller.
Before replacement, CRD/webhook objects were backed up privately. Its sole served
version is v1alpha2, so the obsolete conversion webhook was replaced by strategy
None. The new chart CRD schema was applied server-side after server dry-run.
The existing webhook objects were adopted into release `cps-jobset`; old named
webhook entries were removed only after new entries/controller were healthy.
Helm's keyed-list merge otherwise preserves the obsolete entries and blocks
submissions even when the replacement controller is ready.

Fresh installations can use the ordinary pinned Helm chart. Existing installs
require an inventory and reviewed migration; do not apply adoption or conversion
changes blindly. Keep backups with matching application/CRD versions. Never
remove the CRD as an upgrade or rollback shortcut: it deletes JobSets.

Live qualification: the compute launcher's two-worker CPU JobSet completed under
restricted Pod Security and central admission. Both child Pods succeeded. Driver
termination suspended the parent, retained its idempotency tombstone and removed
UID-owned Jobs, Pods and the KAI PodGroup. Private evidence is in
`cps-platform-evidence/2026-10-05/jobset-live`. This does not qualify four/eight GPU
distributed execution, retry/checkpoint behavior or real user authorization.

JobSet names reserve room for child Job/Pod suffixes; generated names use 128-bit
hashes. Old 192-bit identifiers remain recognizable for termination/cleanup.
Pod templates explicitly set RuntimeDefault seccomp; controller defaults are not
relied upon to satisfy admission.

The bounded CPU retry and cleanup gate is documented separately in
[retry-qualification.md](retry-qualification.md). It does not enable distributed
GPU access or replace the four/eight-GPU acceptance scenarios.

A controlled four-exclusive-GPU NCCL collective and single retry also passed;
see [four-gpu-qualification.md](four-gpu-qualification.md). Checkpoint recovery,
eight-GPU execution and production qualification remain open.

Project-scoped checkpoint mounting and controlled four-GPU model/optimizer
recovery are documented in [checkpoint-qualification.md](checkpoint-qualification.md).
Functional recovery passed; private-file creation permissions failed and remain
a production gate. The production compute image has not gained the new feature.
