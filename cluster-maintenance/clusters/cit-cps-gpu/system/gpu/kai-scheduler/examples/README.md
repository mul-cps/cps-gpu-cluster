# KAI scheduler example workload templates

These are illustrative templates (placeholder image/script) for submitting
training jobs to the `batch` KAI queue on this cluster. Copy and adapt --
don't apply them as-is.

## Files

- **`pytorch-single-gpu-training-job.yaml`** -- single-GPU PyTorch job. Uses
  MPS-shared GPU allocation via the `gpu-memory` pod annotation (fractional,
  can co-exist with other MPS workloads on the same physical GPU). No gang
  scheduling needed since it's one pod.
- **`pytorch-multi-gpu-training-job.yaml`** -- distributed multi-GPU PyTorch
  DDP job (2 pods x 2 GPUs). Uses an explicit `PodGroup` CR
  (`scheduling.run.ai/v2alpha2`) with `minMember` for real gang scheduling,
  a headless Service + Indexed Job for `torchrun` rank/master discovery, and
  whole/exclusive GPU allocation (`nvidia.com/gpu`, no `gpu-memory`) since
  distributed training needs real GPU-to-GPU NVLink/P2P that MPS sharing
  precludes.
- **`tensorflow-single-gpu-training-job.yaml`** -- TensorFlow counterpart of
  the single-GPU PyTorch template; same MPS-sharing and storage conventions.
- **`tensorflow-multi-gpu-training-job.yaml`** -- TensorFlow counterpart of
  the multi-GPU PyTorch template, using
  `tf.distribute.MultiWorkerMirroredStrategy` with a `TF_CONFIG` cluster
  spec built from the Indexed Job's per-worker headless Service DNS names,
  instead of torchrun's `MASTER_ADDR`/`RANK`/`WORLD_SIZE`. Same explicit
  `PodGroup` gang scheduling and whole-GPU allocation reasoning as the
  PyTorch multi-GPU example.

## When to use single- vs multi-GPU

- Use the **single-GPU** templates for anything that fits on one GPU (or a
  fraction of one via MPS) -- most fine-tuning, small/medium model training,
  inference-adjacent workloads. These bin-pack better (MPS sharing lets
  several jobs share a physical GPU) and don't need gang scheduling.
- Use the **multi-GPU / distributed** templates only when a single job
  genuinely needs multiple GPUs working together (data-parallel or
  model-parallel training across processes/nodes). These consume whole GPUs
  exclusively (no MPS sharing) and require gang scheduling (all pods start
  together or none), so they're more expensive to schedule and should only
  be used when the workload actually needs cross-GPU collectives
  (NCCL all-reduce, etc).

Both single- and multi-GPU templates split storage into two separate
mounts: a read-only `/data` mount for input datasets and a writable
`/checkpoints` mount for training progress, backed by distinct PVCs
referencing the `nfs-client` StorageClass name in these example manifests.

<!-- TODO(unverified/stale): `nfs-client` does NOT exist as a live
StorageClass on this cluster (confirmed 2026-07-06 -- see CLAUDE.md and
docs/troubleshooting.md's "NFS mount failed" entry). The comment in
`system/storage/storageclasses/storageclasses.yaml` claiming "Both
nfs-client and fast-scratch storage classes exist and are working
properly" is also stale. These example job templates
(batch-gang-job.yaml, pytorch-single-gpu-training-job.yaml) will leave
their PVCs permanently Pending if applied as-is; a real deployment should
substitute `longhorn`, `longhorn-fast`, or `fast-scratch` depending on the
access mode needed. Left unfixed here since editing the example
manifests themselves is out of scope for this documentation pass. -->
Checkpointing
to shared storage matters because the cluster's descheduler
(`system/descheduler/`) may evict `batch`-queue pods for consolidation at
any time; only progress written to shared storage survives an eviction to a
different node.
