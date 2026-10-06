#!/bin/sh
set -eu
umask 077
work=$(mktemp -d /backup/.partial-XXXXXXXX)
trap 'rm -rf "$work"' EXIT HUP INT TERM
# Do not log database diagnostics: they may include credentials or private data.
if ! pg_dump --format=custom --no-owner --no-acl --file="$work/hub.pgdump" 2>/tmp/private-pg-dump-error; then
    echo 'Hub PostgreSQL backup failed; no complete bundle published' >&2
    exit 1
fi
if ! pg_restore --list "$work/hub.pgdump" >/dev/null 2>/tmp/private-pg-restore-error; then
    echo 'Hub PostgreSQL archive validation failed' >&2
    exit 1
fi
checksum=$(sha256sum "$work/hub.pgdump" | cut -d ' ' -f 1)
stamp=$(date -u +%Y%m%dT%H%M%SZ)
version=$(pg_dump --version | sed 's/^pg_dump (PostgreSQL) //')
printf '{"owner":"%s","created_at":"%s","client_version":"%s","image":"%s","sha256":{"hub.pgdump":"%s"},"scope":"Logical Hub database only; roles, ACLs, configuration, NFS and off-host durability require independent backups"}\n' "$BACKUP_OWNER" "$stamp" "$version" "$BACKUP_IMAGE" "$checksum" >"$work/manifest.json"
sync "$work/hub.pgdump" "$work/manifest.json"
# Random mktemp suffix prevents timestamp collisions; only complete bundles visible.
target="/backup/$stamp-$(basename "$work" | sed 's/^\.partial-//')"
mv "$work" "$target"
sync /backup
echo 'Hub PostgreSQL backup archive published and checksummed'
