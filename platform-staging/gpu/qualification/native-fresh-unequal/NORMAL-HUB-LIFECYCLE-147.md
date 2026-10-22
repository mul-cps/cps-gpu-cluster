# Normal Hub lifecycle qualification, 2026-10-22

Status: bounded two-workspace Start/CUDA/Stop/restart checks passed; remaining
production gates are open.

The isolated CPS/CIT path uses the canonical control/reservation databases and
normal service-authenticated APIs. No MIG, device reset, driver/module update,
or manual Pod creation was used for the notebook workloads.

## Verified in this run

- Both neutral accounts and central workspace registrations were created by their
  owning Source services. Fresh group storage was provisioned through the normal
  API, with NAS permission evidence and both PV/PVC pairs observed Bound.
- The storage Gateway permits provisioning only, for exactly the two reviewed
  source/workspace/group targets. Actual-service-account admission checks accepted
  four intended dry-run objects and rejected 26 altered objects. No dry-run object
  persisted. The temporary parent PV admission exception was restored afterward.
- Both Hubs run the owner-scoped adapter image
  `sha256:6dd145ada0670c2217f5ef89bba35bf88252a74a0dbc1e09c76a79a269e45c5d`.
  TLS from each Hub to the isolated Gateway and active storage/owner bindings passed.
- Normal Source-console service requests started both named servers. The node
  controller automatically programmed, read back and sealed 5120 MiB per cgroup;
  each notebook became Ready. PyTorch reported exactly 5368709120 usable bytes.
- CPS rejected a 6442450944-byte CUDA allocation and subsequently executed CUDA
  successfully. Concurrent CIT CUDA completed 100 checks over 25 seconds.
- CIT normal Hub Stop returned HTTP 204; its Pod disappeared and the controller
  published `cleanup-confirmed`. CPS executed CUDA successfully during that stop.
- CIT restarted through the same normal API with new Pod UID
  `5be16447-a9ce-4b9d-b7df-387c78a769fd`, a fresh sealed 5120 MiB allocation,
  successful CUDA and an unchanged saved-file SHA-256.
- Final normal stops returned HTTP 204 for both workspaces. Both Pods were absent,
  all three allocation records were `released`, both member reservations were
  inactive, and all three journals were terminal `retired-inert-cap`. These inert
  records were preserved, not erased through a GPU reset.

The two first-start Pod UIDs were
`aa72af7b-66a4-4235-b53e-6ec686decf99` (CIT) and
`c0faef49-9fc7-4573-83af-fe3b957fb5a9` (CPS).

## Runtime integration findings

The host's k3s `data/current` is an absolute symlink. Under a `/host` mount,
`/host/var/lib/rancher/k3s/data/current/bin/crictl` does not resolve to the host
binary. This run selected and tested the actual versioned host path instead:
`/host/var/lib/rancher/k3s/data/65415f7708224bbfc7865f032e84da4a5123a3acebef70c8ee40fa991aa68555/bin/crictl`.
Production deployment must resolve and verify its own current version; this hash
is evidence for this host, not a portable default.

The node image also requires the host driver's read-only `usr/bin` directory on
PATH for `nvidia-smi`. This run used `/host/run/nvidia/driver/usr/bin` and the
separately mounted NVML library, without adding the whole driver library directory
to LD_LIBRARY_PATH. CRI version and both GPU UUID/driver queries passed.

The journal context currently wraps nested OS errors as a journal-lock error.
Error-chain diagnosis distinguished the missing binaries from lock permissions.
A transient stop-time error was followed by successful cleanup on reconciliation;
its exact cause has not been established and must not be represented as a lock
failure or ignored as a passed robustness test.

## Remaining acceptance

- Membership removal, access revocation and cross-Hub reservation conflicts.
- Persist and qualify runtime-tool discovery in the deployment configuration.
- 20 GiB, memory import, MPS, broader packing/scheduling and all remaining original
  production/recovery/release gates. The two 5 GiB results do not close those gates.

Private evidence is held under the operator lifecycle preflight directory:
`normal-hub-two5-oom-peer-recovery.actual.private.json`,
`cit-first-normal-start-cuda-storage.actual.private.json`,
`cit-first-normal-hub-stop.actual.private.json`,
`node-stop-cleanup-diagnostic.actual.private.json`,
`cit-normal-restart-cuda-storage.actual.private.json`,
`post-stop-gpu-ledger-all-released.actual.private.json`,
`post-stop-member-reservations.actual.private.json`, and
`fresh-storage-bindings-verified.actual.private.json`.
Credentials and raw Secret captures are deliberately excluded from Git.
