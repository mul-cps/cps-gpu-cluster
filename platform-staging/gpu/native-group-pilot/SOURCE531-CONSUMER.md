# Notebook531 Source consumer and module manifest

Both consoles adopted immutable image `dbaad518` on 16 October 2026. It keeps
the Source51f application/frontend/dependencies and installs the proper Core
wheel from `de90610f`. The [adoption receipt](../../admin/qualification/compute-consumer-531-20261016/adoption-receipt.json)
records deployment, backup, capture and qualification boundaries.

The prospective proposal and Source CLI now require this image. They reject
Source51f, whose Core qualification model cannot consume notebook531. Ordinary
GPU profiles are not enabled by this change.

`source531-qualification-closure.json` is the reviewed static manifest for this
immutable image. Its exact canonical JSON bytes have SHA256
`5f68ec802212eb4c3a8dd8bf37e96354c27a4c68724e525c0ef41c87af356905`.
Copy these bytes unchanged for the Source CLI's independently pinned input;
do not reformat the file. The existing genuine-app loader still checks all 16
installed module files against this manifest before loading the configured service.

Seven application module hashes were independently cross-checked against the
actual Source51f capture in `source51f-runtime-closure-20261015.json` (raw SHA256
`de253b3f95d092b2f950c3700c0c880f04c48cdd442160380f8940d82e74a280`).
The nine compute hashes match the released wheel. All 16 were then verified
inside the immutable image with networking disabled and inside both live Pods.
The older `source-qualification-closure.json` is retained as historical legacy
input; it is not a current Source51f runtime manifest.

Fresh target snapshots must identify the new actual Source Pod UID, original
owning Deployment UID, current image and reviewed manifest. Old target captures
cannot be reused across this rollout. Source record handover/restoration and
current-image 5+20 GiB hardware qualification remain open.

Validation: the pilot suite passed **700 tests and 851 subtests**, with 14 skips.
The image/module, deployment, capture API and matching-backup checks are live
or immutable-image evidence; the CPU tests do not prove GPU isolation or a full
production release.
