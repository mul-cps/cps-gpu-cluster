# Current-version backup capture, 2026-10-15

The CPS and CIT console backup CronJobs now use Source51f; the global state
backup uses Gatewayd974. Their image and provenance fields were updated with
full-spec compare-and-swap checks. Existing UIDs, schedules, PVCs, commands,
secrets and policyD48 were preserved. No notebook or application was restarted.

Three uniquely owned Jobs ran the mounted backup scripts with those images.
All completed, and the new archives passed manifest checksums and read-only
SQLite integrity checks. The scripts match the previously reviewed hashes.
The temporary Jobs and Pods were deleted with UID preconditions and verified
absent; archives remain on the existing backup PVCs.

Both Hub604 PostgreSQL database/role dumps and private Hub configuration
captures were also taken, alongside private compute application configuration.
All local bundle checksums were verified. Credentials and database contents
remain outside Git in operator-owned private directories; this repository holds
only the credential-free receipt.

These captures are sequential. They do not establish a coordinated snapshot,
connected login/spawn recovery, populated NFS/artifact recovery, encrypted
off-host durability or the next successful automatic schedule. Those production
gates remain open.
