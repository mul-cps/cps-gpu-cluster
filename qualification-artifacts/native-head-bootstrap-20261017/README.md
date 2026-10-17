# Dynamic head bootstrap and mount qualification

The pure bootstrap/mount renderer and existing observer rendering passed 48 CPU checks (11 + 37). Independent review caught divergent initial v3 history and a binding path through symlinked `/var/run`; both were reproduced and corrected before publication.

The actual reviewed predecessor Gateway and Hub images were probed at UID/GID 10001:10001 and 1000:1000 using the exact released SDK protected-reader module, no network, read-only filesystems, dropped capabilities and no GPU/CRI/authority mounts. Both rejected the symlinked parent path and accepted the direct root-owned, read-only fixture at `/etc/cps-native-head-binding.json`. The required anchor mount path remains unchanged. These probes verify filesystem compatibility; they do not qualify GPU isolation or a complete deployed release.

See [staged procedure](../../platform-staging/gpu/native-group-pilot/current-group-kai/HEAD-BOOTSTRAP.md). No live object was changed. Automatic delivery migration, coordinated adoption and live qualification remain open.
