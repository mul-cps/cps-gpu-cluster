#!/usr/bin/env bash
# Isolated CPU-only restore exercise; no live database writes or cluster jobs.
set -euo pipefail
if [[ $# != 1 ]]; then echo 'usage: restore-hub-dumps.sh PRIVATE_EVIDENCE_DIRECTORY' >&2; exit 2; fi
evidence=$(realpath "$1")
name="cps-hub-restore-$(date +%s)-$$"
cleanup() { podman rm -f "$name" >/dev/null 2>&1 || true; }
trap cleanup EXIT
# The dump is sensitive; do not enable shell tracing or publish logs.
podman run -d --name "$name" --network none --tmpfs /var/lib/postgresql \
  -e POSTGRES_HOST_AUTH_METHOD=trust docker.io/library/postgres:18.4 >/dev/null
for attempt in $(seq 1 60); do
  if podman exec "$name" pg_isready -U postgres >/dev/null; then break; fi
  sleep 1
done
podman exec "$name" pg_isready -U postgres >/dev/null
for hub in jupyterhub cit-jhub; do
  test -s "$evidence/$hub.pgdump"
  podman exec "$name" createdb -U postgres "$hub"
  podman exec -i "$name" pg_restore -U postgres -d "$hub" --no-owner --no-acl --exit-on-error < "$evidence/$hub.pgdump"
  podman exec "$name" psql -X -U postgres -d "$hub" -Atc 'SELECT count(*) FROM users' > "$evidence/$hub-restored-user-count.txt"
  expected=$(( $(wc -l < "$evidence/$hub-identities.csv") - 1 ))
  actual=$(cat "$evidence/$hub-restored-user-count.txt")
  [[ "$actual" == "$expected" ]] || { echo "$hub identity count mismatch" >&2; exit 1; }
  echo "$hub: restore and identity count match ($actual users)"
done
printf 'This is a PostgreSQL 18 logical restore exercise, not a matching-version Hub launch or NFS restore.\n' > "$evidence/restore-limitations.txt"
chmod 600 "$evidence/"*restor*.txt
