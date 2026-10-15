# Provisioning parent mount gate

Status: source and live inventory check passed; production rollout pending.

The previous positive provisioning test demonstrated that a broad parent mount
could coexist with a newly provisioned compute group. The controller now
checks cluster-wide Pod/PVC/PV inventory before its NAS call and refuses any
active strict ancestor NFS mount. Exact group mounts remain compatible with
idempotent provisioning. Subpaths/read-only mounts are treated conservatively;
unresolved active claims fail closed.

Regression tests reproduced actual provisioning before the guard, then passed
with no NAS or binding side effects. Both PVC and direct NFS parent access
are covered, along with exact group mounts, completed Pods and sibling prefixes.
All 243 compute tests passed. A source-level probe with real cluster inventory
also rejected provisioning before invoking the NAS. No workload was stopped
and no storage mutation was performed by that probe.

This point-in-time guard does not prevent subsequent mounts and cannot replace
a reviewed layout/mount migration. Current production and the published
qualification-permissions-a8426ed candidate lack this guard. Do not promote that
candidate for production group storage activation. A matching new image and
controlled lifecycle qualification remain required.
