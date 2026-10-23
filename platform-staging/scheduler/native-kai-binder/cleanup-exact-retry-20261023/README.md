# Exact deployed binder plus cleanup retry

Apply `full-native-binder.patch` to the pinned upstream revision in verification.json.
It combines the exact deployed patch (verified against its OCI label) and only
`cleanup-retry.patch`. This supersedes the rejected operator-working-tree candidate.
The existing Source custody and UID/resource-version deletion guards remain intact.
The elected native binder reconciles reservations every five seconds so cleanup
holds are retried after the final Pod event. Non-native startup is unchanged.

All five affected CPU test packages passed. The image inherits the deployed image
and replaces only `/workspace/app`. Two live sequential starts/stops passed with the same binder Pod and automatic
cleanup, CUDA enforcement/recovery and persistence readback. See
`live-qualification.json`. This is bounded 5 GiB workspace evidence, not a
whole-platform production qualification.
