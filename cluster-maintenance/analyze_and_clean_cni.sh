#!/bin/bash
set -e

CNI_PATH="/host-cni/networks/cbr0" # Adjust if network name differs, usually cbr0 for K3s flannel
VALID_IPS_FILE="/tmp/valid_ips.txt"
MODE="$1" # "analyze" or "clean"

if [ ! -d "$CNI_PATH" ]; then
    echo "CNI path $CNI_PATH does not exist on this node."
    # Try cni0 just in case
    if [ -d "/host-cni/networks/cni0" ]; then
        CNI_PATH="/host-cni/networks/cni0"
        echo "Found $CNI_PATH instead."
    else
        echo "Could not find CNI network directory."
        exit 1
    fi
fi

echo "Analyzing CNI IP usage in $CNI_PATH..."

# Get all IP files (excluding locks)
allocated_ips=$(ls -1 "$CNI_PATH" | grep -vE "lock|last_reserved_ip")
count_allocated=$(echo "$allocated_ips" | wc -l)

echo "Total IPs allocated in CNI: $count_allocated"

if [ ! -f "$VALID_IPS_FILE" ]; then
    echo "No valid IPs file found at $VALID_IPS_FILE. Cannot determine leaks."
    echo "Please copy the list of valid Pod IPs for this node to $VALID_IPS_FILE."
    exit 1
fi

leaked_count=0

for ip in $allocated_ips; do
    if ! grep -q "^$ip$" "$VALID_IPS_FILE"; then
        echo "POTENTIAL LEAK: $ip"
        leaked_count=$((leaked_count + 1))
        
        if [ "$MODE" = "clean" ]; then
            echo "Removing leaked IP: $ip"
            rm -f "$CNI_PATH/$ip"
        fi
    fi
done

echo "Analysis Complete. Found $leaked_count leaked IPs."
