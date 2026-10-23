# Profile-based notebook walltime — candidate, 23 October 2026

The current batch profile permits 259200 seconds, but the notebook submission
adapter and the Lab Submit/snippet helper separately capped all snapshots at
3600 seconds. A shorter profile limit also was not validated before snapshot
creation. The candidate removes the unrelated ceiling: the selected catalog
maxAgeSeconds bounds requests, with the same legacy 3600 default as ordinary
workflow validation when the field is absent. Invalid/nonpositive profile maxima,
non-integer request durations and durations beyond the profile fail before any
snapshot or launch. Entitlement, image/resource and snapshot-size checks remain.

196 focused submission/Gateway/artifact tests pass. 97 addon tests pass, including
long notebook snippets and over-limit rejection. The prebuilt extension and its
separate wheel build successfully. The three-wheel package verifier passes
namespace/dependency, unique destination, spawner and server-hook checks.

The immutable Gateway candidate changes only storage.py (the already-qualified
client archive identifier fix) and submissions.py versus the live Gateway;
76 Python modules and 43 other installed distributions are unchanged. The addon
candidate changes the common profile limit used by Submit and snippets. No SDK
or Hub ownership of Lab assets is introduced.

The candidate is published but NOT deployed. The live API/UI still impose the
old one-hour notebook ceiling. Gateway activation must use the authenticated
active-Node service-image handover and preserve existing authority journals and
anchors. Notebook image publication, software-preservation proof and approved
image/policy transition must then deploy the addon. Current live isolation and
lifecycle evidence remains tied to its original artifacts; this source/software
result does not prove new live image qualification or a 72-hour execution run.
