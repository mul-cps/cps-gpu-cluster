# Versioned observer head rendering, 17 October 2026

The offline renderer now supports explicit ObserverRelease v2 with stable NodeConfig v4 and four matching namespace-local head bindings. It uses the SDK's actual immutable-head/history validation to derive exact named GETs, while preserving seven Role UIDs, static baseline privileges, own ACK PATCH rows, and existing Pod/ReplicaSet reconciliation.

Four regressions were reproduced before fixes: missing operator head reads, rejection of legitimate reconciled names, acceptance of mismatching component heads, and rejection of valid retained history above the old 32-ConfigMap limit. V2 now permits 544 captured ConfigMaps (four 128-name head sets plus 32 static entries); v1 and other inventory bounds remain unchanged. Unexplained names, missing immutable records, mixed registries and oversized captures are rejected.

Verification:115 integration tests and 25 subtests pass; independent 35 renderer tests pass with the new SDK, and 29 legacy renderer tests pass against 7f3f6d6. Two integration dependency deprecation warnings remain. This is synthetic CPU source evidence only.

The producer must pregrant the operator's own exact named reads before promoting each new head. The renderer adds no wildcard or unnamed ConfigMap GET/LIST, and does not implement or qualify that producer phase. No live operator rollout, automatic delivery or production qualification is claimed.
