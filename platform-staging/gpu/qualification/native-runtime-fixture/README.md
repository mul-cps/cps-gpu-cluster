# Native cap authority qualification fixture

Status: trusted operator qualification only / production disabled.

This proposal consumes the reviewed no-MIG SDK startup contract and its private
CPU cap gate. It does not apply objects, enroll intents, set/release native
caps, execute CUDA, change drivers or enable group profiles. GPU2 ownership,
R615/guard preparation, rollback and every live operation remain with the
supervising operator.

The proposal has one trusted namespace, one immutable source ConfigMap and two
5GiB Pods on `k3s-wk-gpu2`, nodeUID
`3336cdd5-d245-436e-b57c-2f66c6dcaa41`, exact GPU
`GPU-16128952-b438-556a-00bb-93039ee24e56`. `native-cap-main` uses restartPolicy
Never; `native-cap-peer` uses Always for a controlled restart exercise. Both
main processes first validate/copy the reviewed import binary and then idle
for 900 seconds by default. `--idle-seconds` accepts integers from 60 through
3600 for a longer bounded qualification window. The selected duration changes
the immutable ConfigMap payload/name, policy hash and bound Pod spec hash.
They execute no CUDA automatically. All images are immutable
and use imagePullPolicyNever; both gate and main use the already-cached compute
qualification40b9525 image.

The package/probe/binary snapshots in `proposal.json` have fixed SHA256 pins.
The renderer checks available canonical source files first. In environments
without the local build paths it verifies the committed immutable snapshot,
so CPU checks need no download or GPU. Explicit changed source paths fail.
Application maintenance stays in `cps-compute`; this is a byte snapshot of its
reviewed qualification artifact, never an independent application fork.

## Explicit operator exceptions

The normal SDK contract stays disabled and rejects host-mounted data and
arbitrary executable mutations. This fixture records a small set of reviewed
qualification additions before its spec hash and dry-run finalization:

- An immutable ConfigMap provides only the reviewed package to the gate at
  `/opt/native/cps_compute`; gate PYTHONPATH is `/opt/native`.
- Main receives the reviewed CUDA/session probes and native import binary
  read-only at `/qualification`, with a bounded128Mi emptyDir at `/tmp`.
- RuntimeClass is nvidia, main visibility is the one trusted GPU UUID, and gate
  visibility is void. Actual device binding must still be inspected by the
  privileged backend.
- Main receives only the temporary empty test host directory
  `/run/cps-native-gpu/exchange` at `/exchange`. Only this empty exchange
  directory is mode0755; the authority parent stays root0700. The operator creates private children for sockets/imports as
  UID1000/GID100 mode0700. No production filesystem, dataset or credential may
  be placed there.
- The namespace permits hostPath for these trusted objects. User containers
  still run UID1000/GID100 with all capabilities dropped, no escalation,
  read-only root filesystem, no tokens and no host namespaces.

Main never mounts private receipts, authority epochs, cgroups, CRI sockets or
driver metadata. Only the first root CPU gate receives the read-only private
authority/receipt directories and module health metadata. No MPS pipe, HAMi
preload or MIG configuration is supplied.

## Operator workflow

1. Verify GPU2/node ownership, required R615 native cap/managed-deny health,
   protected root0700 authority/receipt directories, root0600 maintenance
   epoch, safe test exchange and rollback evidence.
2. Review the rendered namespace/immutable CM. Apply those objects only; do not
   submit a workload with an unregistered or mutable spec.
3. Obtain an API server dry-run for each proposed Pod and call
   `render_fixture.finalize(proposed, dryrun)` before creation. The SDK accepts
   only reviewed API defaults (including omission of an empty constant EnvVar
   value and the identical deprecated serviceAccount alias). It rejects
   changed/new executable, environment, device, security, volume or token data.
4. Create the finalized Pod. Get its actual API UID and require the complete
   admitted spec hash to equal the finalized hash; compare the independent
   registered intent, not a workload annotation. A post-create hash annotation
   patch cannot refresh the gate's snapshotted environment.
5. Register the exact PodUID/nodeUID/GPUUUID/policy/spec/cap intent with the
   authority. It resolves the blocked first-gate host PID and Pod parent
   cgroup, applies/reads native soft=hard=5120MiB and delivers its root0600 seal
   only after durable authorization. Gate receipt/epoch validation releases
   user startup; no manual release-file fallback exists.
6. After each main reports `native-fixture-ready`, the supervising operator may
   run the pinned `/qualification/session_probe.py` heartbeat/OOM/managed
   checks and `/tmp/native-imports` importer/exporter cases explicitly. Pair
   them with peer coverage, actual cap/device/cgroup identity and lifecycle
   observations. Test a stale seal/restart/controller recovery without
   weakening cap or maintenance fences.
7. Preserve evidence, stop every fixture client and confirm GPU context and
   Pod/cgroup shutdown before retiring caps/receipts and deleting the owned
   namespace/exchange. Expiry alone is never release proof. Restore the
   recorded driver/node state through the existing runbook.

CLI rendering writes JSON only:

```bash
python3 render_fixture.py > proposal-review.json
python3 render_fixture.py --proposed-pod proposed.json --dryrun-pod dryrun.json > finalized-review.json

# Use the same explicit window during rendering and finalization.
python3 render_fixture.py --idle-seconds 3600 > proposal-review.json
python3 render_fixture.py --idle-seconds 3600 --proposed-pod proposed.json --dryrun-pod dryrun.json > finalized-review.json
```

The Python `render()` and `finalize()` APIs accept the same `idle_seconds`
keyword, defaulting to 900. Finalization rejects a proposal rendered with a
different window. The default proposal remains unchanged.

The finalization wrapper also accepts `--pod-uid` for constructing a detached
intent after the matching actual Pod has been created and independently
validated. It never treats this supplied UID as evidence of API identity.

CPU verification:

```bash
python3 -m unittest discover -s platform-staging/gpu/qualification/native-runtime-fixture -p 'test_*.py'
```

CPU rendering and source checks do not qualify live startup, native imports,
restart, pooled group accounting or MPS. The normal Hub/Argo/JobSet paths and
group GPU access remain disabled/unmodified by this fixture.
