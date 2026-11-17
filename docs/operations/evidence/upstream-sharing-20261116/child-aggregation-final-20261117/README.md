# Final-artifact child aggregation / environment / MPS bypass witness

**ACTUAL PASS on both GPU2 cards, with cleanup PASS.** Root released the fenced idle window after CIT GPU stop/returned custody; Source cleanup continued independently on GPU4 CPU only. No runtime, driver, scheduler, user Pod or host policy change is performed by this fixture.


## Actual final-artifact result

Executed once under root release `gpu2-child-final-20261117-root-4b3f436e`, UTC **2026-11-17T08:37:26.349904+00:00 → 2026-11-17T08:38:16.790500+00:00**, elapsed **50.441s**, executor exit0. See [actual summary](actual/summary.json). Both cards returned the expected aggregate OOM2 for parent3GiB+child3GiB under the altered child environment/nonexistent MPS pipe, accepted/fill/synchronized child1GiB, denied tenant nested-cgroup mkdir with errno30, and freed/destroyed contexts successfully. Actual driver readback recorded5120MiB soft/hard on each exact CID leaf.

- Card A PodUID `d88559dd-67bd-40fb-9589-9fc4b0b3155e`, CID `b4d6c76df1d7f1668be5d706d129dfb8958ec5691e594ea6954b4c339f4373b2`.
- Card B PodUID `2d85ddff-cc38-4711-98d6-b391ee39b18f`, CID `ff724b4bb6c7b2d967463bdb49b6dfbbc0a25e7315342a8029d0cf0c3a8dd68c`.

Card A normal deletion, disappeared retired cgroup and empty physical baseline were confirmed before B. Final summary has zero ambiguous creates, cleanup errors or remaining owned objects. Both retired cgroups are absent; both GPUs are1MiB with no compute clients. `final-cleanup-node.json` retains GPU2 Ready/cordoned/maintenance/unqualified. Final driver and runtime evidence verifies boot8874, unique c3b driver imageID, source5648, loaded UVMsrcversion10301D70B8ED1758BC717E9, both policyflagsY, outer6ce and both running agent/containerd inner0ca from archive2277. No NRI fault/restart, config change or production Pod deletion occurred. Hardware window returned immediately after completion.

This closes the **final-artifact attribution of the retained environment/MPS/nested-cgroup probe**. It is not cross-container IPC, numeric host PID reuse, or complete worker promotion. Prior root custody of broader acceptance remains unchanged.

The executor uses the exact historical `../child-aggregation/probe.py`, SHA256 `88c81166cfe2aa44c6a8e932ff81468e9e3f870054b8c9349c3a044b16b72b8f`. It does not substitute the simpler raw allocation probe. Parent3GiB remains held while child3GiB must get typed OOM2 and child1GiB must fill successfully, with changed memory-limit env and nonexistent MPS pipe. Tenant nested-cgroup creation must be denied. Original payload frees/destroys normally. This checks the measured ordinary hard limit; it does not reverse the user's idle-borrowing policy or qualify every possible escape.

Existing `nri_candidate_hotfix` **read-only** validators and host snapshots check the actual node UID/boot/IP/fences, unique Ready c3b driver/imageID, loaded module/source/Y/Y, outer6ce and both running inner0ca identities. Its main/hang/fault routines are never called. The historical Pod template retains nonroot/no-capability security, runtime nvidia, exact image503 and mandatory Fractioning annotations. Changes are unique names, exact selected GPU, immutable ConfigMap,240s active deadline and a210s CPU sleeper enabling pre-exec CID/leaf observation. Only `kubectl exec ... python3 -u /probe/probe.py` starts CUDA; this is bounded75s. Actual5120MiB soft/hard limit readback must match the recorded cgroup and physical UUID.

Cards A and B run sequentially. Before B, original Pod UID must disappear, its recorded cgroup must be absent, both physical GPUs must have no compute clients and ≤1MiB use, and candidate identity is checked again. CREATE replies establish custody. Ambiguous CREATE is recorded and never adopted/replayed; replacement UID is never deleted. All normal removal uses original UID/current resourceVersion preconditions and15s grace/45s disappearance. Finally removes owned Pods before the immutable ConfigMap and rechecks retired cgroups, physical baseline and final artifact identity. Stop at first unexpected failure; no automatic probe rerun.

Local verification: initial missing executor failed first; initial missing exact-limit validator failed first; final5 safety tests pass, covering exact payload/two bounded manifests, wrong limit/leaf rejection, replacement UID refusal, original UID/RV cleanup, and unknown-create custody refusal. Python syntax passes. Default offline render at `/tmp/child-final-render-20261117` has status `prepared-only`, payload hash exactly88c81166, two240s Pods and no kubectl/SSH calls. Its boot8874 is a rendering input, not a refreshed live observation.

After the explicit root release, use a **fresh** evidence output subdirectory and root-confirmed current boot. From repository root:

```sh
python3 docs/operations/evidence/upstream-sharing-20261116/child-aggregation-final-20261117/executor.py \
  --output docs/operations/evidence/upstream-sharing-20261116/child-aggregation-final-20261117/actual \
  --run-id child-final-20261117 \
  --expected-boot-id ROOT_CONFIRMED_CURRENT_BOOT_UUID \
  --ssh-key /home/bjoern/.ssh/id_ed25519 \
  --release-reference ROOT_EXPLICIT_RELEASE_REFERENCE \
  --execute
```

Omit `--execute`/`--release-reference` for render-only; supplying `--execute` without release fails before any API call. Do not reuse an existing output or object name after an uncertain run. Reconcile its summary/owned UIDs first.
