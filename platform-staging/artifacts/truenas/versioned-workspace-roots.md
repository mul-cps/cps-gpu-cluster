# Versioned workspace roots

Status: dual-version integration and bounded live fixture qualification passed; production handover remains pending.

The forced RPC retains its exact request fields. Version 1 preserves the existing
root `persistent1/cps_persistent1_shared/compute`; version 2 selects only
`persistent1/cps_compute_workspaces`. Both use the same source/group SHA256
identifier. No request can supply an arbitrary path. Booleans, strings and
unknown versions are rejected. Execute independently checks version/path
consistency before calling middleware.

Fresh version 2 provisioning creates only the sibling root, source dataset and
hashed group dataset. Existing dataset permission, archive and export gates
remain mandatory. Version 1 status/archive/provision semantics remain compatible;
this does not move, rename or rewrite existing data or records.

The sibling dataset was absent on TrueNAS during the 2026-10-07 inventory and
had no active ancestor mount in the cluster inventory. These observations are
prerequisites, not isolation acceptance. Recheck before live qualification.

Rollout order:

1. Integrate trusted version selection in SDK/controller/runtime with fail-closed
   handling for existing binding/version mismatches. Browsers must not choose paths.
2. Qualify both legacy preservation and isolated new-group provisioning with real
   NAS, Kubernetes bindings, mounted read/write and archive verification.
3. Update the forced NAS script with a content-hash backup before deploying a
   matching gateway candidate. Keep production configuration at version 1 until
   compatibility and lifecycle gates pass.
4. Inventory existing references and backups. Review any legacy-group handover
   explicitly; stop associated writers before moving or archiving data. Preserve
   home paths, group IDs and retained datasets.
5. Prevent future broad parent mounts through Hub policy and applicable admission
   constraints; the inventory guard alone is a point-in-time check.

Thirteen NAS storage tests pass, including version 1 path preservation, version 2
parent creation, unsupported versions and rejection before middleware on mismatches.
The initial source-only stage kept the installed version 1 forced command
unchanged and created no sibling datasets or exports. The later dual-version
deployment and fixture qualification are recorded below.

Gateway integration commit `342d047` passes 253 compute tests. Trusted
`storage.storageVersion` is passed consistently to SSH, Kubernetes and controller
components. Existing legacy version/path mismatches are rejected before NAS
operations, and read-only mount checks exclude both compute trees. The dual-version forced NAS script is now installed with a private backup;
the production gateway remains unchanged. See isolated-v2-live-qualification.md
for the bounded live controller/mount/archive checks and remaining gates.

The matching 6bb6a57 gateway now also passes the bounded V2 HTTPS lifecycle;
see gateway-6bb6a57-v2-http-qualification.md. Production configuration remains
V1 and legacy bindings have not been migrated.
