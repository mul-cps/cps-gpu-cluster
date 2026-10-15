R580 firmware preload passed on GPU2. Driver rollback has not run. This package
prepares a return to the original GPU Operator driver DaemonSet, with MIG current
and pending Disabled on both A100s. Root owns every live maintenance action.

The old cached image is pinned to index
`nvcr.io/nvidia/driver@sha256:41515698692bd5e192186e620b65717af960a66d22dbb5a06e3656575a5d9148`,
linux/amd64 child `6b0c39167b5b4c50aa40ac5a4e756078844906038abe6ba6c94912606ea6ae60`.
Its cache is complete and unpacked. The image has no source/revision label, so no
Git revision is inferred. Its actual cached `/usr/local/bin/nvidia-driver` script
SHA256 is `8787e41ce52a418c252c9388b573a5238dbc3fbd421834ef6d7d6bfd4deafb43`.
Lines248–269 retain an existing nonempty firmware search path; init lines588–601
unmount the old driver root, run the ordinary installer, load modules, then mount
the root. Preloading firmware in an independent directory avoids relying on a
firmware mount underneath that disappearing driver-root bind.

The cached `/drivers/NVIDIA-Linux-x86_64-580.95.05.run` is 396,658,958 bytes,
SHA256 `849ef0ef8e842b9806b2cde9f11c1303d54f1a9a769467e4e5d961b2fe1182a7`.
Its actual header lines508–511 implement `--extract-decompress` as decoder output
followed by exit; payload starts at line1019. A read-only listing of that exact
payload found `firmware/gsp_tu10x.bin` and `firmware/gsp_ga10x.bin`.

The first root-reviewed CPU-only Job failed in nine seconds, exit143/Error, after
archive integrity passed. Its wrapper's lines753–756 hide tar stderr and send
SIGTERM to the wrapper on tar failure. The exact underlying tar error cannot be
recovered from that log. Kernel journal14:26:15–32Z has no OOM/killed-process
entry; its cgroup was already gone. Restoring archive ownership without
CAP_CHOWN is a plausible cause, not a proved diagnosis. The first proposal and
actual failed receipt are preserved.

The v2 Job keeps capabilities dropped and extracts only the two named members,
using `--no-same-owner --no-same-permissions`, with pipefail and visible errors.
It never executes nvidia-installer. It stages files through exclusive hardlinks
and refuses symlinks, ambiguous source matches, archive hash mismatch, or
different preexisting destination bytes. Four tests exercise these safety and
copy behaviors; Kubernetes server dry-run also passed. Root created it, and
`r580-firmware-preload-receipt.json` records actual image ID and successful exit0.
Actual host files in `/run/nvidia/firmware-r615-canary/nvidia/580.95.05/` are:

| File | Bytes | SHA256 |
| --- | ---: | --- |
| gsp_tu10x.bin | 30311512 | 2eb1c5015cec34a7b43e0c390139d2ad2f8fc2ad8ce7813ed4c38f6c626e5aea |
| gsp_ga10x.bin | 74835952 | aca0afdf6587afa641639f555fbe148b2fe1b1138445731d5dfce05a87acb021 |

Root's concrete rollback sequence after finishing the bounded canary is:

1. Capture fresh CPU/PVC Pod UIDs, Ready/restart counts, node UID and actual
   k3s/containerd PIDs. Stop owned CUDA clients; zero fixture soft reservations
   while their cgroups still exist, then delete only owned fixtures. Remove the
   registered CDI file and stray file only after matching their recorded hashes.
2. Verify the two staged580 file hashes and the current independent firmware
   search path. Delete only `gpu2-r615-driver-canary`; wait for its Pods to disappear,
   then verify actual NVIDIA modules and device FD holders are absent. Do not
   force unload, reset, reboot, drain, or restart K3s/containerd.
3. Preserve `/run/nvidia/firmware-r615-canary` as the firmware search path through
   cold R580 bootstrap. Do not prematurely restore the original journaled
   `/run/nvidia/driver/lib/firmware` path. Fresh-check GPU2 node UID
   `3336cdd5-d245-436e-b57c-2f66c6dcaa41`, original driver DS UID
   `7347875f-1243-4b54-9fe7-8aed76a75a05`, and unchanged original spec SHA256
   `20ca4ceadc4adcc59b87e4dcedde724af0383b57ca38415d212ccba96460ab8e`.
   Apply a fresh UID/resourceVersion CAS patch only to GPU2's
   `nvidia.com/gpu.deploy.driver=true` label. Keep consumer exclusions/cordon.
4. Inspect the original580 Pod's actual installer result, actual image ID,
   loaded580.95.05 version and both original UUIDs/current+pending MIG Disabled.
   Preloading protects firmware lookup but does not prove installer/bootstrap
   success in advance. Abort restoration of consumers if these checks fail.
5. Only after the original driver is Ready and the actual GPU checks pass, use
   `node_journal.py restore` with the private baseline journal to emit a fresh
   GPU2-only CAS restoration patch. This refuses a live canary or missing/foreign
   driver. Root reviews/applies it and verifies restored operand health.
6. Recheck protected CPU/PVC health, runtime PIDs and other GPU nodes. Restore
   the original firmware path only if both580 GSP files are reachable there and
   hash-match the staged files. Otherwise retain the independent firmware path
   as a documented temporary node deviation; do not remove its required files.
   Remove only owned completed extraction Jobs after preserving their receipts.

Normal legacy ownership can cause a brief runtime interruption. The old manager
always recycles GPU2 toolkit and MIG-manager Pods, without changing MIG device
state. Current toolkit is still in driver-validation, so its main has not run
and termination cannot invoke main Cleanup. Once580 validation permits the new
toolkit main, [v1.18.0 Setup](https://github.com/NVIDIA/nvidia-container-toolkit/blob/v1.18.0/cmd/nvidia-ctk-installer/container/runtime/containerd/containerd.go#L89-L111)
unconditionally configures and restarts containerd, using default SIGHUP. The
earlier actual K3s restart makes runtime continuity an explicit failed/pending
gate, not a promise. No shared toolkit runtime/DaemonSet changes are proposed.

At14:32:43Z all GPU2 protected CPU/PVC UIDs and Ready states still matched. Its
historical Spegel restart difference remained. All other retained GPU1/3/4
baseline Pods matched, but GPU1 `cit-jhub/jupyter-m12113877` baseline UID
`791a82ec-66df-40e4-8b75-f371642dc3c4` was absent; the cause was not established by
this worker. Broad claims that every protected Pod stayed unchanged are withheld.
Dynamic sharing remains disabled; root's actual managed-memory bypass evidence
does not qualify R615 for tenant isolation.
