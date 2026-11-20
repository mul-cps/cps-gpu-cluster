#!/bin/sh
set -eu
umask 077
backup_root=${BACKUP_DIRECTORY:-/backup}
work=$(mktemp -d "$backup_root/.partial-XXXXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
fail() { echo 'Hub backup failed; no complete bundle published' >&2; exit 1; }
# Metadata is restricted before JSON interpolation; missing versions stay null.
metadata() { case "$1" in *[!a-zA-Z0-9./:_@+-]*) fail ;; esac; }
json_value() { if [ -n "$1" ]; then printf '"%s"' "$1"; else printf null; fi; }
for value in "$BACKUP_OWNER" "$BACKUP_IMAGE" "${BACKUP_HUB_IMAGE:-}" "${BACKUP_HUB_CHART_VERSION:-}" "${BACKUP_HUB_APP_VERSION:-}"; do
    metadata "$value"
done
files='hub.pgdump'
mode=logical
snapshot=null
scope='Logical Hub database only; roles, ACLs, configuration, NFS and off-host durability require independent backups'
case "${ROLE_CAPTURE_ENABLED:-false}" in
true)
    [ -n "${ROLE_CAPTURE_PGUSER:-}" ] && [ -n "${ROLE_CAPTURE_PGPASSWORD:-}" ] || fail
    [ -n "${BACKUP_CONFIGURATION_SECRET_REF:-}" ] && [ -n "${BACKUP_CONFIGURATION_UID:-}" ] &&
        [ -n "${BACKUP_CONFIGURATION_RESOURCE_VERSION:-}" ] && [ -n "${BACKUP_CONFIGURATION_CAPTURED_AT:-}" ] || fail
    for value in "$BACKUP_CONFIGURATION_SECRET_REF" "$BACKUP_CONFIGURATION_UID" "$BACKUP_CONFIGURATION_RESOURCE_VERSION" "$BACKUP_CONFIGURATION_CAPTURED_AT"; do
        metadata "$value"
    done
    export PGUSER="$ROLE_CAPTURE_PGUSER" PGPASSWORD="$ROLE_CAPTURE_PGPASSWORD"
    # Confirm existing privilege, without creating or promoting a database role.
    if ! privileged=$(psql -X -Atc 'SELECT rolsuper FROM pg_roles WHERE rolname = current_user' 2>"$work/private-error"); then fail; fi
    [ "$privileged" = t ] || fail
    # Role hashes and all tool diagnostics remain private and never reach logs.
    pg_dumpall --roles-only --file="$work/roles.sql" > /dev/null 2>"$work/private-error" || fail
    [ -s "$work/roles.sql" ] || fail
    pg_dump --format=custom --create --file="$work/hub.pgdump" > /dev/null 2>"$work/private-error" || fail
    configuration=${PROTECTED_CONFIGURATION_DIRECTORY:-/protected-configuration}
    for name in workloads.json configmaps.json secrets.json running-images.txt; do
        [ -f "$configuration/$name" ] && [ -s "$configuration/$name" ] || fail
        cp -L "$configuration/$name" "$work/$name" > /dev/null 2>"$work/private-error" || fail
    done
    files='hub.pgdump roles.sql workloads.json configmaps.json secrets.json running-images.txt'
    mode=roles-acls-configuration
    snapshot=$(printf '{"source":"operator-supplied-secret-snapshot","observed_live":false,"secret_ref":"%s","uid":"%s","resource_version":"%s","captured_at":"%s"}' "$BACKUP_CONFIGURATION_SECRET_REF" "$BACKUP_CONFIGURATION_UID" "$BACKUP_CONFIGURATION_RESOURCE_VERSION" "$BACKUP_CONFIGURATION_CAPTURED_AT")
    scope='Roles and Hub database owners/ACLs plus operator-declared configuration snapshot; fresh API capture, coordinated capture, connected Hub/NFS restore and off-host durability remain unqualified'
    ;;
false)
    pg_dump --format=custom --no-owner --no-acl --file="$work/hub.pgdump" > /dev/null 2>"$work/private-error" || fail
    ;;
*) fail ;;
esac
[ -s "$work/hub.pgdump" ] || fail
pg_restore --list "$work/hub.pgdump" > /dev/null 2>"$work/private-error" || fail
stamp=$(date -u +%Y%m%dT%H%M%SZ)
version=$(pg_dump --version 2>"$work/private-error") || fail
case "$version" in 'pg_dump (PostgreSQL) '*) ;; *) fail ;; esac
version=${version#'pg_dump (PostgreSQL) '}
# Distro builds append packaging details after the numeric version token.
version=${version%% *}
case "$version" in ''|*[!0-9.]*) fail ;; esac
checksums=''
separator=''
for name in $files; do
    chmod 600 "$work/$name"
    checksum=$(sha256sum "$work/$name" 2>"$work/private-error") || fail
    checksum=${checksum%% *}
    [ "${#checksum}" = 64 ] || fail
    case "$checksum" in *[!a-f0-9]*) fail ;; esac
    checksums="$checksums$separator\"$name\":\"$checksum\""
    separator=,
    sync "$work/$name"
done
printf '{"owner":"%s","created_at":"%s","client_version":"%s","image":"%s","capture_mode":"%s","recovery_qualified":false,"hub":{"image":%s,"chart_version":%s,"app_version":%s},"configuration_snapshot":%s,"sha256":{%s},"scope":"%s"}\n' \
    "$BACKUP_OWNER" "$stamp" "$version" "$BACKUP_IMAGE" "$mode" \
    "$(json_value "${BACKUP_HUB_IMAGE:-}")" "$(json_value "${BACKUP_HUB_CHART_VERSION:-}")" "$(json_value "${BACKUP_HUB_APP_VERSION:-}")" \
    "$snapshot" "$checksums" "$scope" >"$work/manifest.json"
chmod 600 "$work/manifest.json"
rm -f "$work/private-error"
sync "$work/manifest.json"
# Random mktemp suffix prevents timestamp collisions; only complete bundles visible.
target="$backup_root/$stamp-$(basename "$work" | sed 's/^\.partial-//')"
mv "$work" "$target"
sync "$backup_root"
echo 'Hub PostgreSQL backup archive published and checksummed'
