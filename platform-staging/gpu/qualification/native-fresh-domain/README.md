# Fresh guarded147 qualification cohort

These explicit operator tools are independent of Source, approval heads and
NodeService. They use the reviewed6360ab1 SDK controller, backend, CRI, NVML
adapter and exact147 health source. Defaults are inert. No tool installs or
loads a module, resets a driver, reconstructs lost custody, or marks production
qualified. The historical29 missing journals remain unproven.

The dedicated QA namespace is `cps-native-qa147-20261022`, UID
`1f7d941a-872d-4453-a1ba-fd489d8aff14`. Root must independently verify that
identity, loaded driver authority, actual boot/generation, all excluded writers,
physical device and zero unexpected clients before execution. Root owns API
credentials and every live action. The QA namespace needs the explicitly
reviewed privileged hostPath exception; notebook containers remain UID1000/GID100.

## Prepare and bind

`render_fixture.py --prepare --inputs REQUEST --inputs-sha256 RAW_SHA --output
NEW_DIRECTORY --approve-qa-hostpaths` produces two proposed Pods and an immutable
source ConfigMap. It invokes the actual pinned compiler. The gate uses cached
`bc5b128f…` only as an isolated Python interpreter: `-I -S` and an explicit
immutable source package exclude installed SDK and notebook/CWD imports.
The notebook image is exact `5427088986bc…`. Its independently verified OCI
entrypoint is `tini -g -- start.sh`; the renderer leaves `command` absent and
supplies the same isolated Python idle process as `args`, preserving PID1
reaping without CUDA allocation or extending the original1800-second lifetime.
This changes newly rendered cohorts only; old admitted specs and evidence remain
unchanged.

The closed request has `version:1`, `namespace`, `namespace_uid`, `gate_image`,
`policy_hash`, and optionally `cohort_uid` (canonical nonzero UUID). New cohorts
use distinct names with the first eight UUID characters and a separate
`/var/lib/cps-native-gpu/qualification/<namespace-UID>/cohorts/<cohort-UUID>/state`.
Old requests retain their original state path. Never reuse or clear a previous
cohort's journal to make a new one pass.

Root creates and verifies the source ConfigMap, server-dryruns each proposed
Pod, then calls `--finalize` with `--proposed-pod` and `--dryrun-pod`. Root
dryruns the finalized Pod again, creates it, and calls `--finalize` with its
actual full `--actual-pod` readback. Only that final call emits a UID-bound
intent. No proposed UID substitutes for an actual API identity. Gate timeout
remains300 seconds; expired Pods must fail closed and get new actual identities.

## Cap transaction and cleanup

`controller.py --prepare-bundle NEW_DIRECTORY` copies only six exact-hash SDK
source dependencies. Run the transferred script with `python3 -I -B`; it checks
every source before executing any of those exact bytes. It imports no installed
SDK. On the selected host, Root explicitly supplies the actual CRI binary/socket,
private dedicated API token/CA directory, endpoint environment and NVML search
path. The dedicated API identity needs only named GET/DELETE on the exact cohort
Pods, GET on the selected Node and GET on the exact QA namespace.

The execution arguments are `--execute --approve-qa-hostpaths --bundle BUNDLE
--cohort-uid UUID --intent-a FILE --intent-a-sha256 RAW --intent-b FILE
--intent-b-sha256 RAW --crictl ACTUAL_BINARY --service-account PRIVATE_DIRECTORY
--nvidia-smi ACTUAL_BINARY`. Root stages private0700 state, authority, bootstrap,
receipts and journal directories and a protected0600 QA driver-generation file.
The separate actual guarded-load authority remains read-only. No journal is
copied from another domain. Reconcile retains the SDK's actual API/CRI/process,
Pod-parent inode, health, epoch, descendant, cap readback and seal checks.

Add `--cleanup` to the same reviewed invocation after independently stopping
the actual Pods. It invokes the original `NativeCapController.cleanup` and
preserves original journals, identity, receipts provenance and distinct cleaned
versus retired-inert-cap states. It cannot reset or invent a missing record.
A partial bootstrap without a matching journal fails closed and requires
separate explicit operator review.

If physical inventory retains a previous cohort's finite retired entries,
Root supplies `--retirement FILE --retirement-sha256 RAW`. Its closed JSON is
`{version:1,state_root:ORIGINAL_QA_STATE,records:[ORIGINAL_CAP_RECORDS]}`.
For multiple original state roots use the closed version2 shape
`{version:2,states:[{state_root:ORIGINAL_QA_STATE,records:[ORIGINAL_CAP_RECORDS]}]}`.
The independent raw SHA covers the complete descriptor, including every state
and record. At most8 distinct canonical original QA states and16 total records
are allowed. Original and current directory identities, Pod UIDs and native
parent inodes must not alias; arbitrary paths, extra fields and symlinks fail
closed. Each complete protected original journal must equal its reviewed records;
every record must already be retired-inert-cap in this exact epoch. Fresh SDK
retirement proofs must establish old Pod-name and cgroup absence, no receipt,
exact offline pinned zero-charge entry, original identity and original cap.
The complete physical inventory permits only current cohort parents and those
specifically proven entries. Unknown entries remain fatal. The previous state
is not changed and the historical full-inventory hash is not relabeled as a
new observation. All original-state proofs repeat after admission and again in every fresh
observer invocation. No successful proof or inventory observation is cached.

## Observe and run the first5GiB probe

`observe.py --execute` takes the same bundle, actual intent paths/raw hashes,
cohort and retirement inputs, plus `--controller` and `--service-account`.
It verifies the exact controller hash, enables a read-only audit guard before
API/NVML access, and never calls cleanup, set-limit or a Node service. Actual
notebook542 Pod/status and CRI/PID/start/cgroup checks bracket original sealed
journals/receipts, live caps, guarded147 health and complete physical inventory.
It correctly refuses a notebook that has not become Running/Ready.

`physical_samples.py --execute --nvidia-smi PATH --nvidia-smi-sha256 RAW
--nvml-library REAL_VERSIONED_PATH --nvml-library-sha256 RAW` produces four
Root physical memory samples,0.5 seconds apart. It verifies root-owned original
binaries, actual SONAME resolution and current boot/generation. It calls no
CUDA API and cannot substitute capped container totals for physical headroom.
Full147 health remains part of the enclosing observer bracket.

`run_peer_oom.py` reuses the original reviewed `peer_probe.py`, transport,
watchdogs and assessment. It supports only the explicit kubectl transport, not
the old optional kernel transport. An independently reviewed private0600 manifest
contains exactly:

```text
version:1, cohort_uid, namespace_uid,
pods:{a:{namespace,name,uid,cap_mib:5120,spec_sha256},b:{same exact fields}},
observer_argv:[Root-reviewed split ssh/kubectl arguments invoking observe.py],
physical_argv:[Root-reviewed split arguments invoking physical_samples.py]
```

These vectors are a trusted Root transport boundary, not authorization inferred
from a JSON name. Root must separately review their exact scripts, hashes,
credentials, remote target and arguments. The raw manifest SHA pins the complete
reviewed vectors. The observer vector must bind this exact cohort UUID.

Run `python -I -B run_peer_oom.py --execute --manifest FILE --manifest-sha256 RAW
--output NEW_DIRECTORY --probe-sha256 RAW --preflight-sha256 RAW
--runner-sha256 RAW [--direction a-to-b|b-to-a]`.
The runner requires successful overlap, at least4096MiB held before typed OOM,
eight seconds of retained pressure, peer kernels inside that hold and bracketing
recovery, repeated physical samples with more than6GiB free, unchanged actual
Pods and processes, original journals/seals and charge recovery. Local transports
are bounded and cleaned; remote probes have their own watchdogs. Failures never
delete Pods or remove caps. Root must still perform actual stop and the original
cleanup transaction and retain the resulting proofs.

Passing this first5GiB measurement does not establish aggregate accounting,
memory-import isolation, restart-cleanup, MPS,10GiB behavior, six-gate policy
qualification, production readiness or restoration of missing historical custody.

## Recorded controlled result (2026-10-22)

Both directions of the 5 GiB peer/OOM test passed on the guarded kernel147
deployment. Each allocator held 4608 MiB before a typed PyTorch OOM, recovered
its kernel, and left its peer progressing throughout the eight-second hold.
Each run captured four physical-memory samples with more than 33 GiB free;
actual processes, original seals and journals were unchanged, and charges
returned to baseline. See `qualification-20261022.json` for exact scope and
artifact hashes. The remaining qualification families above are still open.
