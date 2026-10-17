# Gateway and disabled binder rollout proposals

`gateway_rollout.py` composes full Deployment specifications and guarded JSON
patches from a reviewed `endpoint.render` result and actual captured objects.
It has no client, CLI, credential access or executor. Call it with independently
reviewed identity pins, not identities inferred from an untrusted replacement:

```python
gateway = compose_gateway(captured_gateway, reviewed_endpoint_proposal,
                          created_seed_readback, expected=reviewed_gateway_identity)
binder = compose_binder(captured_binder, reviewed_endpoint_proposal,
                        expected=reviewed_binder_identity)
```

Each identity is exactly `{namespace, name, uid, resourceVersion}`. Results
contain `prospective`, `target`, the complete desired `spec`, and a `patch`
testing the actual UID, resourceVersion and complete old spec before replacing
the spec. A changed preimage or reapplication fails; Root must recapture and
recompose after any intentional scale or configuration change.

Gateway composition requires the actual immutable seed CREATE readback with a
canonical UID/resourceVersion, exact expected data, ownerless identity and the
renderer content-addressed name. Root obtains that readback from the API; this
pure helper does not manufacture or independently fetch it. The main and init
images agree, fsGroup10001 is already present, and the initializer shares the
same complete writable data PVC mount. Only the emitted environment entry,
three volumes, two main mounts and initializer are appended. Other spec fields,
including replicas, placement, images, resources and existing init containers,
remain unchanged.

Binder composition accepts one existing reservation image flag in either split
or equals form and replaces it with the exact proposal digest. It preserves
unrelated arguments/plugins and appends only missing members of the exact six
emitted flags. Existing native values must agree; a true bridge is rejected.
The two token/CA volumes and mounts are appended, and fsGroup10000 is explicit
without replacing other security-context fields. The binder image and service
account remain unchanged. No enable-true proposal is returned.

Duplicate named volumes/environment entries, initializer collisions, duplicate
mount paths and new mounts shadowing existing paths fail. Existing legal uses
of one volume at distinct mount paths remain intact. New name collisions and
reapplication fail rather than silently adopting previous changes.

Root separately owns immutable seed/CA staging, RBAC, backups, full-template
review, prospective and actual observer captures, and actual fresh ACK2 process
proof after rollout. These composers do not alter NodeConfig, heads, Node,
images, personal workloads or permissions and do not establish live readiness.
