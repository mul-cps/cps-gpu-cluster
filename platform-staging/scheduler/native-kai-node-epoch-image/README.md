# Node507 derivative qualification

Published **inert only**, never applied to the cluster:

`ghcr.io/mul-cps/cps-compute@sha256:8c2c456b90330622645d509f94882a11a465ac208a6fa7fc824900d6320e5c0b`

The Dockerfile extends exact Node507 (`5079458…`) with only the frozen sixteen-file764 bundle. It installs no wheels or dependencies. All79 distributions, 15,863 installed recorded file hashes, thirty Core modules, absent Hub package, and runtime image configuration are unchanged. The candidate config is `sha256:88b67945c3f182cfc230c60463a08edf105e72ccc16902be1f6f637b0837e332`. All eleven original507 compressed layer descriptors and DiffIDs are retained, followed by one bundle layer. `verification.json`, `oci-closure.json`, and `payload-comparison.json` record the measured results.

Node startup uses stdlib and exact vendored helpers. The only Core-relative import in the new epoch file belongs to its unused Gateway observer class; Node does not instantiate that observer. Gateway/Hub reconciliation with current CPU/neutral fixes remains a separate release gate. No full58 Core wheel or Hub module is installed here.

## Offline build and evidence

Run from this directory with a **new private evidence directory**. Existing exact507 must already be pulled. These commands never use Kubernetes or GPU devices.

```sh
podman build --network none --pull=never --format oci -t localhost/cps-native-node-epoch:qualification-76460b3-20261014 -f Dockerfile .
podman run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --tmpfs /tmp:rw,size=64m,mode=1777 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/opt/native:/tests/legacy -v "$PWD/tests:/tests:ro,z" --entrypoint python3 localhost/cps-native-node-epoch:qualification-76460b3-20261014 /tests/run_legacy.py
podman run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --tmpfs /tmp:rw,size=64m,mode=1777 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/opt/native -v "$PWD/tests:/tests:ro,z" --entrypoint python3 localhost/cps-native-node-epoch:qualification-76460b3-20261014 /tests/test_installed.py
python3 -m unittest discover -s tests -p test_plan.py -v
```

The installed suites passed36 selected unchanged legacy runtime tests and10 installed tests without skips. They cover actual pinned loading, default-off/noAPI/noGPU startup, pre-initialization operator/v2 mutual exclusion, unchanged v2 process and protected health observers, operator current UID/RV/data CAS and unknown outcomes, local TLS redirect denial and token rotation. CPU fixtures do not qualify physical health, GPU caps, live authenticated identity, CRI, CDI or cleanup.

One **source-generator golden check** imports the original SDK producer, which is intentionally absent from Node507. It passed separately on the host against original `dc72f653da935bf60d563430b643f18c2852417c138fdb281df563f79da4b772` in reviewed7d source. `run_legacy.py` names this separation explicitly; no SDK module is injected into Node. The copied three legacy test files are byte-exact, with `legacy-test-provenance.json`. Test symlinks point to the installed image bundle; Dockerfile copies only `bundle/`.

Podman initially exported one inherited compressed layer as its identical uncompressed tar. `retain_base_blobs.py` first checks every downloaded base/candidate blob and DiffID, then restores the original507 compressed descriptors without changing config or filesystem bytes. The earlier53 manifest is **not the final candidate**. To reproduce full remote closure, download official507 and the final8c2 manifest by immutable digest with `skopeo copy --preserve-digests ... oci:<private-directory>:qualified`, then run:

```sh
python3 verify_oci.py --base "$E/base-oci" --candidate "$E/final-remote-oci" --digest sha256:8c2c456b90330622645d509f94882a11a465ac208a6fa7fc824900d6320e5c0b --output "$E/oci-closure.json"
```

`verify_payload.py` inventories every recorded installed package file in either image. Independent base/candidate inventories must match exactly outside `/opt/native`; the base runtime config must match outside labels. Full private inventories and logs are under `/home/bjoern/.local/state/cps-full-project-20261013/native-kai-node-epoch-image-20261014`.

## Honest staged cutover packet, no executor

`plan.py` only reads supplied JSON and writes prospective JSON. It imports no Kubernetes client, invokes no process and sends no requests. Every output is `enabled:false/live_applied:false`. Root owns authorization, writes, rollout, maintenance and normal Source actions. `cutover-readback.json` is a timestamped read-only observation, never a freshness assertion.

An **image-only patch is unsuitable**. Current immutable code CM458e mounts over `/opt/native`; immutable bootstrap e371 pins tagged image507. Existing `cps-native-approval-node` Role also pins exactly the old Pod and ReplicaSet names. The smallest retained-v2 path is:

1. Establish fresh maintenance/no-writers and native-zero gates: normal Source Close, confirmed affected Pod absence, ledger/reservation/enrollment/custody reconciliation, no unmanaged consumers, current physical generation. Preserve complete terminal history and all preimages.
2. `plan.py v2 --inputs <actual deployment/code/bootstrap> --output <plan>` produces new immutable bootstrap with **only process.image changed**, plus a Deployment UID/RV/**full-spec** guarded patch changing image, removing the masking code volume/mount and referencing that bootstrap. Every v2 argument, node configuration, host mount, privilege, grant and capacity stays exact. The private actual proposal is `retained-v2-plan.json` (path above). Re-read every UID/RV/data/spec before executing; old ConfigMaps are retained.
3. After actual new ReplicaSet/Pod CREATE, read both raw objects. `process-rbac` requires the actual controller UID chain and exact current template/image/SA, then proposes existing Role UID/RV/full-rules CAS changing only exact Pod/RS GET names. Names are never predicted and permissions never broaden to namespace-wide Pod/RS reads. A temporary fail-closed restart before this exact RBAC update is possible; do not admit Starts meanwhile.
4. Require exact current Deployment/image/generation, actual v2 process/driver health and fresh node ACK, then all four existing approval ACKs. `inverse` requires fresh current Deployment RV and complete prospective spec; revert to retained507/code/bootstrap. Restore exact Role rules under fresh UID/RV/rules CAS, then require fresh original four ACKs before reopening Starts. Any unknown mutation outcome stays fenced and requires raw readback, not a guessed inverse.

The **operator10 path is separate and mutually exclusive**, after the retained-v2 path has been verified and closed again:

1. Reuse the single reviewed764 whole catalog/compiler/policy/inverse and `operator-qualification.json`. `operator-creates` rejects an altered qualification document, epoch/pool drift or anything beyond exact `cit:native-group-a` / `interactive-native-qualification-10` /10240MiB. It derives an immutable operator node configuration retaining **all current terminal history**, and a dedicated mutable empty `cps-native-kai-epoch-node`. Nothing is created by this tool.
2. After actual Node config/epoch CREATE readbacks, `operator-settings` derives immutable settings using actual config UID/RV/full-data hash, target UID, retained Deployment UID, exact8c2 image and current signed node SA UID. It cannot manufacture references. After actual settings CREATE/readback, `operator` validates these closed references and produces the separate Deployment patch: replace node config ref, remove all dynamic-v2 arguments/projections, add the explicit operator argument and Downward API own Pod identity. A bounded init container materializes the exact hashed settings into root-owned0700 memory volume/0600 regular file; direct projected symlinks are not accepted as private authority. The installed-image materializer fixture passed valid input and denied corrupt input **before output creation**.
3. Observe actual new Pod/RS and compile exact-name `process-rbac` with `operator_mode:true`: old v2 ACK patch permission becomes **only** dedicated epoch ACK patch; add only exact own SA GET. Preserve the original Role for inverse. No new cleanup/enrollment/grant permissions are added. Require fresh operator ACK consumed by reconciled Gateway58; do not claim the ordinary four v2 ACKs apply during this isolated mode.
4. Actual end-to-end gates remain: reconciled Gateway/Hub coordinator and signed lease/created hook, canonical Source grant/profile binding, protected auth/fence currentness, actual NodeUID post-Bind, CRI/cgroup/CDI identity, cap-before-CUDA and maintenance-generation fence. Use only normal audited Source Start/Close, exact UID/RV Pod absence/map cleanup and genuine native-zero receipts. Unknown CREATE/Bind/delete outcomes retain custody. No expiry release or fabricated cleanup.
5. Close through normal Source, prove exact native-zero and no writers, then render inverse from fresh exact prospective spec and restore retained v2 node config/bootstrap/Role. Require fresh original process/health and all four approval ACKs. New test ConfigMaps remain inert until separately reviewed exact-UID cleanup; do not delete old authority/history.

There is no v2/5/20GiB expansion, driver/module replacement, native cleanup modification, Hub/Source/Gateway live change or hardware acceptance claim in this package.
