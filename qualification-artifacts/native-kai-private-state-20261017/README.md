# Private Coordinator state correction, 17 October 2026

Preactivation inspection found that the live Gateway PVC root is UID0/mode02775; the Gateway runs as UID10001. The previous root-level custody path and sibling-of-control.sqlite writer lock would fail the strict private-file guard, including ordinary grant and workspace mutations after Coordinator installation. The earlier API dry runs did not test filesystem operations. No activation occurred.

Application commit `7f3f6d67aa60c72bd9033f0b33df8880c88b6cab` adds optional explicit `writerLockPath`, bound consistently across both Coordinator constructors, all three execution-fence paths and the grant/workspace/native mutation guards. Conflicting bindings fail; omitted configuration preserves the legacy default. Private-file checks and SQLite transaction behavior remain unchanged.

The deployment proposal now mounts the existing complete writable data PVC in its UID10001 initializer and provisions only `/data/native-kai-private`. Directory ownership is checked through `O_DIRECTORY|O_NOFOLLOW`; mode0700 clears inherited SGID. Existing DB paths, bytes and permissions and the PVC-root permissions remain unchanged. New custody and lock files use this child.

RED-before-fix tests reproduced the old unsafe path. Verification: full SDK CPU suite3135passed/6skipped/68subtests; focused SDK70passed; cluster integration109passed/25subtests, two dependency warnings. Materializer tests exercise existing database preservation, inherited SGID clearing and symlink refusal. Two consistent Gateway database backups passed integrity checks before any proposed rollout.

This is source qualification. The installed be0 Gateway image does not support the new configuration field. Publish/adopt a compatible image and repeat actual readiness/authentication checks before activation; do not apply the earlier dry-run patch. Dynamic-head integration and GPU lifecycle/production qualification remain open.

The six CPU-suite skips are explicit remaining environment-specific checks: three JupyterLab wheel/sdist artifact inspections require `CPS_LAB_DIST`, and three root-gate CLI lifetime cases require the disposable root CPU container fixture. They are not counted as passes. These package/root-fixture checks remain separate qualification gates for the final combined release.

Subsequent environment-specific checks close all six skipped scenarios for exact source `7f3f6d6`: a fresh addon wheel built from sdist passes all three artifact inspections, and the three gate CLI cases pass in a rootless, network-none, read-only CPU container with all capabilities dropped and no GPU/CRI/host-authority mounts. See [artifact provenance](addon-artifact-result.json) and [root CPU receipt](root-cpu-result.json). The original full-suite run still reports its six skips; these are separate terminal executions, not an invented zero-skip rerun. The final combined dynamic-head release must qualify its own artifacts and fixtures.
