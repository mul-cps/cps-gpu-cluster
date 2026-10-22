# Remaining fresh5/10 import gates

Offline preparation only; Root alone stages helpers and executes. No caps,
Source records, policies or production consumers are changed by this generator.
It authenticates all11 historical sources and the exact reviewed fresh preflight
before loading code. The required actual manifest is not fabricated: Root must
create the new cohort and provide its fresh admitted UID/spec/cap references.

```text
python -I -B fresh_import_closure.py --prepare \
 --manifest ACTUAL_MANIFEST --manifest-sha256 ACTUAL_RAW_SHA \
 --preflight ACTUAL_GENERATED_FRESH_PREFLIGHT \
 --preflight-sha256 5ce86051f1a9bd435abc14a8633f273e03e1af086658de7fad8b8d5dcceb3cc0 \
 --output NEW_PRIVATE_DIRECTORY
```

The cohort is fixed to3b217fe8-5750-4ead-954a-09286afd7d3f with A5120/B10240MiB.
The emitted shared bracket rereads the original fresh API/host observer each time,
requires both actual protected Source332 intents, and maps actual inventory rows
without caching observations. Legacy `cps`/`cit` CLI labels mean QA Pod A/B only;
no request targets either production Hub namespace.

Use emitted managed and creator-exit wrappers twice (`--side cps`, `--side cit`):

```text
python -I -B managed/run_managed.py --execute --side cps \
 --cps-pod-uid ACTUAL_A_UID --cit-pod-uid ACTUAL_B_UID \
 --driver-generation 4ebffc96-e25e-4583-a3b8-0d853fd90efd \
 --source-sha256 EMITTED_WRAPPER_SHA --output NEW_PRIVATE_RUN_DIRECTORY
```

Creator-exit uses `vmm-owner-exit/run_owner_exit.py` with those same arguments.
The original host observer's existing `singleuser_cohort=None` branch requires
an empty QA compute-client baseline and then exactly the actual participants.
No historical Jupyter-singleuser lifetime is fabricated. Original35s managed
watchdog/typed801/64MiB vector controls, creator-reaped0,20s retained hold,
64MiB backing-charge drop while importer context stays live, final PID absence,
zero charge and source/context cleanup remain mandatory. The probe's existing
exact libcuda SHA guard also remains; a different library fails rather than
being accepted by version alone.

For marked VMM FD tests, stage emitted `vmm_bridge.py` and `vmm_endpoint.py` under
Root700 `<cohort-root>/vmm-bridge`, both Root400. Stage emitted collector and
validator Root400 under Root700 `<cohort-root>/vmm-kmsg-witness`, with a separate
Root700 `sessions` directory; no overwrite. `<cohort-root>` is
`/var/lib/cps-native-gpu/qualification/1f7d941a-872d-4453-a1ba-fd489d8aff14/cohorts/3b217fe8-5750-4ead-954a-09286afd7d3f`.
Run `vmm-cross-parent/run_vmm_cross_parent.py` with `--execute`,
`--direction cps-to-cit` then `cit-to-cps`, `--output NEW_PRIVATE_DIRECTORY`,
and independently reviewed emitted hashes in the original six flags:
`--wrapper-source-sha256`, `--endpoint-source-sha256`, `--bridge-source-sha256`,
`--witness-collector-sha256`, `--witness-validator-sha256`,
`--witness-transport-sha256`. The Root-approved SSH/stdin vector is fixed in the
shared bracket; it does not impersonate a retired Observer Pod. Same valid FD,
same-parent positive control, exact actual processes/namespaces, protected
source, correlated kernel sequence and explicit endpoint cleanup remain intact.

All endpoint/Root cap checks use exact actual Pod UID→one cap, never a5|10
allowlist. Full production qualification remains false. Missing actual manifest,
preflight bytes, protected host source staging or reviewed output hashes blocks
execution; offline preparation is not hardware acceptance.
