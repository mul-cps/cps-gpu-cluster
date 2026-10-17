# Dynamic head bootstrap and mount qualification

The pure bootstrap/mount renderer and existing observer rendering passed 48 CPU checks (11 + 37). Independent review caught divergent initial v3 history and a binding path through symlinked `/var/run`; both were reproduced and corrected before publication.

The actual reviewed predecessor Gateway and Hub images were probed at UID/GID 10001:10001 and 1000:1000 using the exact released SDK protected-reader module, no network, read-only filesystems, dropped capabilities and no GPU/CRI/authority mounts. Both rejected the symlinked parent path and accepted the direct root-owned, read-only fixture at `/etc/cps-native-head-binding.json`. The required anchor mount path remains unchanged. These probes verify filesystem compatibility; they do not qualify GPU isolation or a complete deployed release.

See [staged procedure](../../platform-staging/gpu/native-group-pilot/current-group-kai/HEAD-BOOTSTRAP.md). No live object was changed. Automatic delivery migration, coordinated adoption and live qualification remain open.


The independently reviewed dynamic delivery runtime renderer passed 57 checks
with the qualified official Go CEL evaluator, zero skips. Root reran those
57 checks and the separate 48 bootstrap/observer checks. Six synthetic
admission definitions were accepted by the actual K3s server dry-run, with
empty stderr; this is API schema validation, not installed-policy evaluation
or production UID qualification.

A read-only live preflight loaded the actual v3 Node authority and four mounted
immutable approvals and generated four pointer candidates. It does not prove
fresh Source state or readiness. Actual GETs also confirmed all four old
journal approval UIDs, full-data hashes and registry revisions; all are v1,
and only the old Node reference is retained in its current component history.
This identifies the explicit historical-evidence migration requirement. No
history was rewritten, no journal reset, and no live object was mutated.
