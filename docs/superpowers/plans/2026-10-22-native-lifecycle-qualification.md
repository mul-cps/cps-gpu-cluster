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
