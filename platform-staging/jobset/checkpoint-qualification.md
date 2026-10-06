# Distributed checkpoint implementation and qualification

The compute launcher now supports an operator-owned, project-scoped checkpoint
PVC mapping, optionally selecting a canonical relative subdirectory. The fixed
mount is `/checkpoints`; descriptor requests cannot choose claims, subpaths or
volume manifests. Authorization checks project membership before the mount is
compiled. Malformed configuration fails startup; settings are copied at startup.
Canonical application documentation is in the compute repository README at
`1a71bc713aac8b9ea263860b8b7ca0c878892619`. All 234 compute tests pass, including
claim/path overrides, cross-project access and invalid subpath cases.

A trusted four-exclusive-GPU fixture passed functional checkpoint recovery on
2026-10-06. See [checkpoint-report.json](checkpoint-report.json):

- Four DDP ranks train a scalar linear model using SGD with momentum 0.9.
- Rank zero writes model and optimizer state after step two; all four ranks
  report the same saved SHA256 before the operator forces one child Job failure.
- Replacement ranks load that identical checkpoint, including momentum -49.875,
  complete steps three/four and agree on weight 2.1297342777252197.
- This matches the uninterrupted analytic SGD reference 2.129734375 within
  1e-5; final momentum matches its reference within 1e-4.
- Both attempts also perform ten successful four-rank NCCL reductions.
- Termination/reconciliation remove child Jobs, Pods and KAI PodGroups while
  retaining the idempotency tombstone; the fixture namespace/admission objects
  are then deleted. The existing interactive reservation remains running.

This is a bounded scalar-model functional test, not large-model throughput,
real gateway HTTP authorization, eight-GPU or production user qualification.
The operator generates JobSets from the new source locally. The production
compute image still contains the earlier source; this feature is not deployed
there, and distributed/GPU qualification remains disabled.

## NFS observations and permissions gate

The test uses the existing server **193.170.30.58**, preserving its address and
all human storage paths. A dedicated directory lies within the existing retained
qualification workspace, with a project PVC referring to its mountable export
root and a trusted `subPath` exposing only the new checkpoint directory.

Directly mounting the child directory was denied by the server, including a
fresh CPU-only probe with default NFS negotiation. That fixture was explicitly
suspended and removed before retrying through the mountable root/subpath. Kubelet
subpath preparation required read/execute access on these test directories.
Only the qualification parent/directory permissions were temporarily adjusted;
a final capture restored the parent to its original **2770** and the checkpoint
directory to **0700**. No production share or export rule was changed.

An initial recovery run restarted before the intended injection; all replacement
ranks restored successfully, but incomplete initial logs did not establish the
failure cause. It is not the controlled acceptance result. The corrected fixture
captures partial/error logs, performs bounded checkpoint visibility retries and
requires an actual injected failure. Its complete four-rank saved/restored/final
records are the acceptance evidence above. NFS atomic publication does not by
itself establish immediate visibility across clients or crash-safe persistence.

**Private-file creation qualification failed:** although the worker set umask
0077, both retained files appeared as mode **0777**. The capture corrected only
those test files to 0600, verified their modes and checksums, and preserved their
contents. This does not prove why creation permissions differed or that future
files will be private. Before production use, qualify the export/dataset ACL and
creation behavior, approved atomic checkpoint writers, and unauthorized-client
access. Do not replace that gate with an assumption about umask.

The final retained checkpoint is 2621 bytes with SHA256
`331972f0a0628f5fa1d618fea46c979e6bd6ad941082c22b7fb8b4eed5e4b4e5`.
The checkpoint and final result JSON remain on NFS and in the private evidence
bundle, with mode 0600 at capture. The fixture PV uses Retain and is Released;
namespace removal does not delete this data. Its nominal PV capacity is not an
NFS quota or off-host backup.

Private evidence, captured files and executable fixtures are under
`cps-platform-evidence/2026-10-06/jobset-checkpoint/`. Outstanding gates include
private creation permissions, real project provisioning/authorization, deployment
of matching application artifacts, eight-GPU recovery and broader scheduling.
