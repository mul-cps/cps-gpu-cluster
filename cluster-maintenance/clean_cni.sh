#!/bin/sh
set -e
cd /host-cni/networks/cbr0/
echo "Checking IPs on host node..."
for ip in $(ls -1 . | grep -v lock); do
  # Skip lock files
  # Check if IP is in valid list
  if ! grep -q "^$ip$" /valid_cni_ips.txt; then
    echo "Stale IP found (not in valid list): $ip"
    rm -f "/host-cni/networks/cbr0/$ip"
    # Also remove lock file? Usually it's named separately?
    # CNI plugin host-local creates lock files?
    # Often it relies on file locking the IP file itself.
    # But sometimes there are .lock files.
  else 
    echo "Valid IP kept: $ip"
  fi
done
