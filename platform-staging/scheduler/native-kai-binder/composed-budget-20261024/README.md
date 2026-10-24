# Combined native binder and scheduler source

This candidate combines the pinned KAI 0.18.1 upstream source with the existing
qualified native binder cleanup/retry overlay, advertised GPU inventory accounting,
the opt-in native-qualified budget plugin and observed reservation deletion identity
protection. It changes no deployment or scheduler configuration.

The binder overlays share a deletion call. The composition retains the uncached
native custody readback, exact observed UID/resourceVersion check and MayDelete
hold/error behavior. UID/resourceVersion API preconditions now apply to every
actual deletion, including the ordinary cleanup path. Native custody is never
inferred from Pod expiry or terminal status.

## Reproduce

Use a clean checkout of upstream commit
`bdf434e5e9201cccf4e05fad04d814363653f692`, then run:

```bash
git apply --check /absolute/path/to/composed.patch
git apply /absolute/path/to/composed.patch
```

The patch is complete against that upstream revision; do not apply the component
patches again. `verification.json` records the component patch hashes, exact
composed source hashes, test outcomes and static binary identities. The original
component artifacts remain available for provenance.

Run the upstream non-E2E Go package boundary using Go 1.26.8 and local Kubernetes
1.35.0 envtest assets. Set `USE_EXISTING_CLUSTER=false`,
`ENVTEST_USE_EXISTING_CLUSTER=false` and a nonexistent `KUBECONFIG`; this
qualification must not reach the production cluster. The plugin tests and
reservation cleanup tests also run under Go's race detector.

Build `./cmd/binder` and `./cmd/scheduler` with `CGO_ENABLED=0`, `GOOS=linux`,
`GOARCH=amd64`, `GOFLAGS=-mod=readonly`, `-trimpath`, `-buildvcs=false` and
`-ldflags=-buildid=`. Repeat builds must have identical SHA256 values. Build
output remains private; no container image is published by this directory.

## Remaining activation work

This is software composition evidence, not full-pool or production acceptance.
The budget plugin remains opt-in and existing configuration is unchanged. Trusted
budget/request/claims producers, fresh Source/head/ACK admission, atomic native
retirement fencing and confirmed-zero release, immutable image qualification,
controlled hardware tests and operator rollout remain mandatory. The existing
native binder protocol is preserved; this artifact does not claim that its
runtime already implements every v2 producer or admission path.
