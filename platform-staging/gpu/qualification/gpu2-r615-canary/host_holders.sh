#!/bin/sh
# Read-only, inside the existing GPU2 privileged hostPID driver container.
# No cmdline/environ reads, control operations, or process signals.
set -eu
printf 'module_refs\n'
sed -n '/^nvidia/p' /proc/modules
printf 'device_fd_holders\n'
for process in /proc/[0-9]*; do
    devices=''
    for fd in "$process"/fd/*; do
        target=$(readlink "$fd" 2>/dev/null) || continue
        case "$target" in /dev/nvidia*) devices="$devices $target";; esac
    done
    test -n "$devices" || continue
    comm=$(cat "$process/comm" 2>/dev/null) || continue
    uid=$(sed -n 's/^Uid:[[:space:]]*\([0-9]*\).*/\1/p' "$process/status" 2>/dev/null) || continue
    cgroup=$(tr '\n' '|' < "$process/cgroup" 2>/dev/null) || continue
    printf 'pid=%s comm=%s uid=%s cgroup=%s devices=%s\n' "${process##*/}" "$comm" "$uid" "$cgroup" "$devices"
done
