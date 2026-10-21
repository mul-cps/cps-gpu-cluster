# Backup provenance correction, 2026-10-14

All five automatic CPS/CIT Hub, console and gateway backup jobs succeeded on
2026-10-14 at their normal schedules. The console and gateway CronJobs still
recorded earlier application images and the previous policy hash. Their three
full-spec CAS updates changed only the backup container image, `BACKUP_IMAGE`
and `BACKUP_POLICY_HASH`. Schedules, PVCs, secrets, commands and all other fields
were preserved. Existing archives were not rewritten.

The corrected console image is Source `8d86a5bc`; the gateway image is
`440711b2`. The manifest policy now matches the live `compute-policy` artifact,
`sha256:d48f6553ed036c2e7adcc97417623fe0308be93ad13b20f246047ada118511b0`.
Exact hashes and unchanged CronJob UIDs appear in `receipt.json`.

Three uniquely owned Jobs ran the actual mounted backup scripts on those exact
images. All completed successfully; new manifests, file checksums and read-only
SQLite integrity checks matched. The two scripts exactly matched Git. Eight
focused backup tests passed. The private verification receipt SHA-256 is
`72c62bfc14de68f3a91d9050bcc666a22822acc9ad19ea14784b73aec0fb3acc`.
Their temporary Jobs and Pods were removed with UID preconditions and verified
absent; the new backup archives remain on their existing backup PVCs.

The platform chart already derives backup application images and policy hashes
from the same release values as the applications. Future upgrades must promote
those CronJobs together with the applications. Applying the complete chart
requires the qualified release values and matching policy artifact; a display
overlay alone does not perform an application release.

This demonstrates corrected backup execution and archive integrity. The next
automatic schedule after the correction, connected application recovery,
coordinated Hub/console/gateway/NFS capture and encrypted off-host durability
remain separate qualification gates.

## Guarded Gateway handovers, 2026-10-21

The chart already uses the shared `gateway.image` release value for the
Deployment and backup `BACKUP_IMAGE`. Later direct Gateway rotations omitted
the CronJob update, so a successfully executed backup could still record an
older application version. `application_image` identifies the application
whose databases were backed up; it must not be inferred from the backup utility
container image.

The pure `current-group-kai/head_gateway_rotation.py::prepare` now accepts
`actual_gateway_backup` and `expected_gateway_backup_sha256` together. Root must
capture the actual `batch/v1` `compute-state-backup` CronJob and independently pin
the complete captured object. The bound proposal includes
`patches['gateway.backup-cronjob']`, a UID/resourceVersion/full-spec CAS that
changes only the single literal `BACKUP_IMAGE` to the reviewed Gateway image.
The utility image, policy hash, schedules, storage, security and other fields
remain exact. Apply this patch only after the target Gateway image has actually
become ready, and verify its readback before creating a backup Job.
Existing stagers that accept exactly five labels must explicitly admit this
optional sixth label with its pinned preimage; do not silently drop it or apply
it before readiness. The historical staged R61 renderer remains unchanged.

Omitting both optional inputs preserves previous prepared artifacts and patch
sets exactly; that compatibility path does not verify current backup provenance.
Supplying one without the other, an altered pin, a different resource identity,
or ambiguous/nonliteral provenance is rejected. The composer performs no API
calls and does not replace actual backup/restore qualification or alter existing
archives. Staged historical renderers and live objects are unchanged by this
source addition.
