# Reviewed CPS personal-spawn UI persistence

Source persistence matches the applied live script exactly: SHA256 `b048ab982036edc8fc3d21ea1afd9d7978f4aee429e99c3ad149ea353afaee0e`.

The 1909-line Fleet addition is the complete reviewed live `02-profiles` Python string plus its YAML wrapper. `helm.values` was previously absent from this Fleet file; the referenced legacy `values.yaml` still contained an older 8c script. The inline override therefore preserves the live hardening while persisting the two approved UI hunks. It does not restore the stale override-capable parser or mutable image tags.

The functional UI change filters the custom form using the existing `legacy_shared_intent` predicate and links to the existing CPS Shared workspaces UI. CPUdefault/desktop and exclusive choices remain intact. Legacy personal shared starts remain rejected; no3→5 mapping, entitlement, membership, role or gateway change is made by this commit.

The reviewed Deployment patch adds only `cps.unileoben.ac.at/personal-spawn-ui-sha256`. Its full template matches the current live Deployment exactly. Image 0bbe, Recreate strategy, policy2b, environment, volumes, Secret references and retained custody remain unchanged.

The running Hub mounts `cps-fixed-launch-16fa767-20261028`, not chart Secrethub. Current Secret data equals the approved live candidate byte-for-byte. Only the decoded `hub.extraConfig.02-profiles` leaf changed from the preserved pre-UI snapshot; all other data keys, decoded values, encryption/cookie/proxy material are unchanged. Cryptographic-key hashes and all Secret payloads remain private and are not included here.

Verification:

- 43 focused offline tests pass:12 form/parser/filter cases plus 31 registry/custody cases; one preexisting Traitlets deprecation warning.
- Actual installed resource-card AST render removed only guarded legacy choices; CPU remains selected even with stale Tiny options, and the parser and all non-form AST nodes are unchanged.
- Official chart 4.4.2/app 5.5.2 Helm+Kustomize comparison changes only the new UI annotation in the final Deployment/Pod. Existing encryption/cookie/proxy values were supplied privately for deterministic rendering and compared exactly.
- Local JSON-patch verification accepts the approved candidate and rejects wrong UID, RV and old data. No Secret content is exposed in this proof.
- Fresh source/live checks in `proof.json` verify the live applied state, exact decoded script and Pod template; no user spawn/start/stop was attempted by the commit verifier.

Eight whitespace-only Python lines were inherited from the reviewed live script and retained to preserve the exact approved byte hash. YAML parsing/decoding and compilation pass; these opaque literal-data lines explain default Git whitespace warnings.

This commit does not mutate the live Fleet pin. Other service usability and managed-workspace lifecycle acceptance remain separately recorded by root.
