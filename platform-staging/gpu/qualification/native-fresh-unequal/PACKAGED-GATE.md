# Packaged147 gate fixture

`prepare_packaged_gate.py` is a separate default-inert adapter. It preserves all
previous frozen producers and evidence. It uses only the exact published image
`ghcr.io/mul-cps/cps-native-node@sha256:81aac20157965ed5503b0d208b0326fef1ba10d71089d9e635128cea48dafe82`
as the actual installed SDK gate. Expected installed runtime/health SHA256 pins
are `035fa640…` and `fc9dd634…`, matching the local6360 compiler. These are
expected software pins from Root's publication qualification; this tool does not
claim to have inspected a running container or qualified hardware.

The request retains the closed seven-field format: version1, QA namespace and
UID, a new canonical nonzero cohort UUID, exact gate image above, actual Source332
policy hash and pair `5-10`. The old a9fc cohort is rejected. Root independently
reviews and pins the complete request bytes.

```sh
python -I -B prepare_packaged_gate.py --prepare \
  --inputs ROOT_REQUEST --inputs-sha256 RAW_SHA --output NEW_PRIVATE_DIRECTORY \
  --approve-qa-hostpaths
```

The actual compiler gate command remains
`python -m cps_compute.native_gpu_runtime wait-for-cap …`. The adapter removes
only the QA source ConfigMap, its package volume/mount and command override. It
emits no gate-source ConfigMap artifact. Local source pins still authenticate the
compiler before import. Container code comes from the installed immutable image,
with the normal authority and receipt mounts. Root-only CPU gate exceptions,
notebook UID1000/GID100, verified notebook542 tini entrypoint,300-second cap gate
and1800-second idle child are unchanged. This remains an explicitly controlled
QA fixture, not a production deployment composer.

Root follows the existing genuine dry-run/finalize/create/readback sequence using
the emitted renderer and original raw-pinned request. Only actual Pod UID and
complete admitted spec readback can produce the two intents. The controller and
observer CLI stay unchanged, with the new UUID, actual intent raw hashes, exact
bundle/tool paths and complete reviewed v2 retirement descriptor.

After the preceding5/10 cohort, that descriptor contains eight original records
across four original protected state roots, including one10GiB parent. Historical
admission now permits typed original5/10GiB records only. Each record retains its
own original intent and finite cap, complete actual journal equality and fresh
SDK Pod-name/cgroup/receipt absence, epoch, identity, pinned-offline zero-charge
entry proofs. The fresh proofs repeat; no record or physical observation is
cached. No global either-cap active-Pod allowance is introduced. Active A5/B10
UID/native-parent mappings and the exact15360MiB budget remain unchanged.
Unknown rows, changed old charge, missing journals, stale epoch,20GiB history or
replacement identities still fail closed. No old state is reset or regenerated.

Root verifies actual packaged gate imageID, successful gate exit and installed
runtime/health bytes independently before treating this as packaged execution.
Original controlled stop/UID-preconditioned deletion and controller `--cleanup`
are still mandatory. Preparation emits no acceptance flags or current-boot
production authority. Lost historical custody remains declared unproven.
