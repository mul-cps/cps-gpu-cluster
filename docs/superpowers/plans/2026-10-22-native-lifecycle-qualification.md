# Native GPU lifecycle qualification

## Goal and boundary

Close the normal Hub/API lifecycle acceptance gate on the released SDK and
current guarded driver without repeating the passed CUDA isolation matrix.
This is a prerequisite to production activation, not production completion.

Use the historical plain, prebound two-workspace 5 GiB pilot. Derive a separate
disabled pilot catalog and its real hash from the current policy. Use canonical
control/reservation databases, explicit temporary neutral workspace approvals,
and a separate qualification namespace, ledger and host state root. Do not
activate the production Source or claim that the KAI pending path was exercised.

## Implementation and verification

1. Adapt only the legacy direct agent's source loading to reviewed released
   modules. Preserve enrollment, admitted Pod identity, CDI/device identity,
   native inventory, cap sealing, cleanup and publication checks. Reject any
   unexpected module bytes. Test mismatches and unchanged guard definitions.
2. Add a pure configuration builder using explicit actual workspace/pool inputs.
   Validate its outputs with the released policy and authority contracts. Test
   policy hashing, fixed 5 GiB caps, source ownership and malformed inputs.
3. Review both changes and run the qualification helper suite. Capture actual
   canonical database and Hub baselines privately before any live mutation.
4. Provision only the two approved temporary workspaces. Exercise Hub/API
   Start, CUDA, Stop, reservation release, member removal and reinstatement.
   Require fresh Pod UIDs and seals, original Pod absence, preserved PVC/data,
   revoked access, and confirmed cleanup before reservation reuse.
5. Preserve actual evidence and restore pilot-specific configuration. Only
   then complete the six-gate evidence and prepare coherent production activation.

## Protected state

Do not touch the running `jupyterhub/jupyter-muslim` Pod, NFS paths, MIG mode,
GPU modules or production Source history. Do not fabricate API UIDs or recreate
missing journals. Existing retired qualification entries remain pinned.

## Progress

- Live preflight: protected Pod UID unchanged and Running; GPU2 still cordoned.
- Pure configuration builder implemented; 11 isolated SDK contract tests pass.
- Runtime review found legacy CDI pins, new cleanup terminal compatibility and
  full prior-inventory validation require a bounded adapter; loader-only swap rejected.
- Canonical baseline captured read-only: 9 workspaces, 31 grants, 0 reservations.
- Hardware lifecycle run and production activation remain pending.

## Temporary Gateway placement

The runtime rejects simultaneous pilot and production-group modes. Use a separate
Gateway process; do not disable or rewrite the production Source. The actual
`compute-state` PVC is ReadWriteOnce in `cps-compute`, attached on `k3s-wk-gpu1`.
The temporary Gateway must use that namespace/node and the same `/data` mount:
`control.sqlite` and `reservations.sqlite` are fixed runtime filenames, not
arbitrary caller-selected DB names. Its authority ledger remains in a separate
qualification namespace with a dedicated service account and scoped grants.

The existing server certificate covers only the production Service DNS. Give the
temporary internal Service its own matching certificate and pin its CA only in
operator Hub settings. Omit production publisher/coordinator/bootstrap settings.
Register temporary neutral workspaces with the derived policy hash and grant
that exact pilot alias to the reviewed members. Unchanged production workspace
rows must fail authorization against the derived catalog. Preserve existing data
and prove storage bindings rather than inventing storage evidence.

## Verified implementation and live startup

- Root verified 187 tests and 118 subtests across the qualification helpers and
  historical Node-agent suite. Both independent source reviews cleared the
  installed-SDK adapter, including terminal cleanup and Pod-name reuse checks.
- The isolated released Gateway started on GPU1 with the canonical PVC. Both
  Hubs verified its private TLS endpoint: OpenAPI returned 200 and unauthenticated
  `/v1/me` returned 401. No workspace grants or GPU-control roles are installed.
- Direct service-account SelfSubjectReview plus access reviews over the
  CA-verified Kubernetes API denied ConfigMap creation, Pod creation and Secret
  reads. Rancher-proxied `kubectl --as` reported the administrator's permissions
  and is not accepted as this service account's authorization evidence.
- Fresh SSH reads matched all twelve original terminal journals. Current CDI
  selected-device and device-plugin documents match the hardware-tested capture;
  the complete CDI search/configuration inputs are separately pinned.
- Live Node authority/receipt mounts, physical inventory preflight, workspace
  registration/grants and the actual Hub lifecycle remain pending.

## Node preflight and scoped permissions verified

The separate durable cohort is projected read-only at the compiler's fixed host
receipt/authority aliases. The existing authority directory inode is preserved;
no custody keys or old journals were recreated. The inert Node Pod uses the
released SDK image, a dedicated SA, and only the actual NVML library, avoiding
host glibc injection. Its read-only probe verified all nine module pins, current
CDI resolution and all twelve physical retirement rows, with native SET and Pod
deletion explicitly forbidden. The actual controller loop has not started.

The two admission policies compiled without warnings. Direct, CA-verified checks
confirmed both actor identities and all 32 expected RBAC outcomes; empty-ledger
server dry-run succeeded and unrelated ConfigMap writes were rejected by the
specific policies. These checks did not persist a ledger or completion proof.
Actual neutral workspace registration/grants, Hub overlay and Start/Stop/member
lifecycle execution remain pending.

## Existing Hub composition boundary

Fresh live Secret inspection confirms lifetime enforcement is enabled on both
Hubs. CIT's additional existing-secret has no values.yaml override. A second
ordinary native installer is not a supported overlay: lifetime installation
rejects an already installed controller, and chained post-stop/environment
hooks can reach the previous authority for a temporary owner.

Implement an explicit owner-scoped overlay: non-test owners delegate unchanged;
the two temporary owners exclusively use their selected adapter. Register their
lifetime provider with the existing API and polling loop, preserving expiry.
Do not reset installation markers or disable lifetime enforcement. Qualify this
composition before changing either live Hub Deployment.

Both selected existing workspace PVCs are currently Bound and each PV claimRef
UID matches the actual PVC UID. This proves Kubernetes binding only; storage
reuse still requires an exact guarded canonical-record binding and the runtime
file-preservation check. No storage records have been changed by this inspection.

A read-only cold-load of SDK768 in a fresh subprocess in each actual Hub, with
original mounts/environment and Kubernetes non-GET calls forbidden, rejected
both existing production configurations with `Complete reviewed v3 qualification
proof required`. Therefore a direct replacement by the SDK768 Hub image is not
a valid deployment step. Preserve the distinction between historical evidence
and current qualification; do not relax proof validation to make startup pass.
The deployment composition must resolve this before either Hub is restarted.

The retained-storage reuse planner has passed 19 focused tests and independent
source review. It is proposal-only. Actual registration, guarded canonical DB
transaction, audit, grants, and runtime preservation remain to be performed.

## Hub-only package compatibility route

The installed SDK production-configuration constructor control passes on both
actual Hubs with Kubernetes writes forbidden. All 78 installed SDK modules in
base image0aeb match commit2f13 exactly. Its policy and native Pod compiler are
byte-identical to SDK768, so the temporary plain pilot does not require an SDK
upgrade. Build only the updated Hub adapter wheel over image0aeb, preserve the
SDK and every other distribution, then verify existing configuration cold-load
and the owner-scoped overlay together. The SDK768 Node/Gateway remain separate.
This preserves original historical qualification handling without broadening
proof acceptance; it does not assert that the old hardware epoch is current.

## Packaged owner overlay and real account provisioning

Hub-only sourcecf2589d is pushed; immutable image6dd145ada067 was published and
its registry manifest/config digest verified independently. Root repeated 81
focused lifetime tests against SDK2f13. Actual current-Hub subprocesses loaded
both the original dynamic-owner production adapter and new exact-owner overlay
with lifetime enabled and Kubernetes writes forbidden. Both passed. The image
contains 20 exact committed Hub modules; all 136 other distributions, inherited
runtime config, SDK labels and base-layer prefix are preserved. No live Hub
Deployment has changed.

Ordinary account provisioning derives source-ws-hash principals and requires
server rtc; the original arbitrary-name/shared proposal was corrected before
creation. Existing unregistered course-group custody correctly returned409.
Use fresh pilot groups instead of inventing legacy custody. Both fresh neutral
accounts/groups were then created successfully through their actual Source
services (HTTP200), with identity/group/role receipts checked. Their storage is
not provisioned and no GPU server has started.

Next use normal authenticated fresh-group storage provisioning, not manual
set_storage or copied active evidence. The isolated Gateway currently disables
storage. A bounded opt-in must preserve actual provider refs and add exact PV/PVC
admission plus required read inventory permissions. Merely omitting archive Job
RBAC is insufficient: NAS archive runs first. Require an explicit provision-only
SDK configuration that denies archive before metadata/NAS changes. NAS server,
exports and existing data configuration remain unchanged.

The inert Node test Pod reached its declared deadline without running its
controller. Recreate only that owned terminal test Pod when the actual lifecycle
run is ready; retain all host custody, retirement evidence and state.
