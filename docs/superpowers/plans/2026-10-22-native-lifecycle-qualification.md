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
