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
