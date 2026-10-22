# Selected UUID CDI at cold Node startup

This optional cold-domain stage repairs the missing management UUID provider;
ordinary rotation contracts and SDK admission/CDI/driver validators are unchanged.
`startup.candidates(actual_typed_target, actual_held_node_deployment,
authority_directory=...)` returns an immutable content-addressed ConfigMap and a
prospective Deployment spec. It does not apply anything. Root stages/readbacks
and reviews the complete objects, then uses the existing full-spec UID/RV CAS
handover. It is not an independent deployment or authority mechanism.

The target must be in `cps-native-runtime`, pin
`selected_filename=cps-native-selected-147.json`, and retain reviewed hashes for
EVERY other CDI descriptor and runtime configuration. `common_edits_sha256` must
match the device-plugin source's unchanged common edits. Root must derive these
pins from actual files and the typed target configuration; do not copy an old
config or infer trust from filenames. Existing policy, qualification, epoch and
four-component ACK requirements remain independent gates.

The new init runs before `packaged-bootstrap`, using the same qualified Node
image. It has a read-only host mount for existing SDK physical inventory,
147 health and file checks; its sole writable host mount is `/run/cdi`. Its
immutable source/settings files use `subPath` file mounts so the SDK nofollow
reader sees regular protected files rather than ConfigMap symlinks. It requests
no GPU, forces `NVIDIA_VISIBLE_DEVICES=void`, makes no API calls and performs no
NVML/driver mutation or CUDA allocation. Root must separately authorize this
cold-domain hostPath addition and retained external writer/maintenance fence.

The helper verifies boot/generation, exact147 health source, live GPU UUID/minor
inventory, all existing provider/runtime pins and the complete source descriptor.
It copies only the selected UUID's device entry and unchanged common edits into
`management.nvidia.com/gpu`, then invokes the existing closed SDK one-GPU CDI
validator. No `all` alias or other GPU is emitted. It never edits the source,
management provider, runtime config or other files. Missing output (including
after reboot) is published as a fully fsynced inode with an exclusive atomic
link and directory fsync. This avoids replacing any racing writer. Existing
identical output is verified; different existing bytes/symlinks fail closed and
require explicit reviewed migration. During the final pre-publication search bracket, only this operation's exact
canonical temporary name is excluded, after matching its still-held regular
root0644/nlink1 FD to the named inode and exact intended bytes. Every foreign
provider remains denied. Temporary files are removed on handled failure; a
process crash may leave an orphan that deliberately blocks startup pending
reviewed cleanup.
Fresh health/search/inventory/CDI validation repeats after publication, before
Node startup can proceed. A post-publication failure retains the descriptor and
fails the init; it does not publish an ACK or roll back independently changed
authority. A changed boot/generation requires a freshly qualified target config.

Read-only offline check of Root's actual source `b940041d...` reproduced exactly
`93270b440c40c8b375f70c0331a44e771206b3b807133c4064f2737a3b4bcc28`.
This is byte-level rendering evidence, not live startup qualification.

Tests use the 147 SDK source/tests/Hub package on `PYTHONPATH` and:

```
python -m pytest -q platform-staging/gpu/native-selected-cdi
```

Tests cover closed UUID mapping and pin failures, atomic publication/retry,
symlink/wrong-output and pre-publication epoch failure, plus a genuinely typed
fresh-root cold Node config and exact preservation of its existing startup.
No live APIs, hardware, credentials or runtime files are modified by tests.
