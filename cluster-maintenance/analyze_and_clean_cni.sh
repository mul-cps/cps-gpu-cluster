#!/bin/bash
set -e

# Configuration
CNI_PATH="/host-cni/networks/cbr0"
VALID_IPS_FILE="/tmp/valid_ips.txt"
SLEEP_INTERVAL=${SLEEP_INTERVAL:-600}

# Install kubectl if missing (for Alpine)
if ! command -v kubectl &> /dev/null; then
    echo "Installing kubectl..."
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    chmod +x kubectl
    mv kubectl /usr/local/bin/
fi

# Determine CNI Path
if [ ! -d "$CNI_PATH" ]; then
    if [ -d "/host-cni/networks/cni0" ]; then
        CNI_PATH="/host-cni/networks/cni0"
    else
        echo "CNI network directory not found at $CNI_PATH or /host-cni/networks/cni0"
        # We might be on a node that hasn't started CNI yet, or different config.
        # Don't exit, just sleep and retry, to avoid crash loops.
        echo "Sleeping..."
        sleep "$SLEEP_INTERVAL"
        exit 0 
    fi
fi

while true; do
    echo "------------------------------------------------"
    echo "Starting CNI cleanup cycle at $(date)"
    
    # Get current node name
    # NODE_NAME is passed via fieldRef in DaemonSet
    if [ -z "$NODE_NAME" ]; then
        echo "NODE_NAME environment variable not set."
        exit 1
    fi

    echo "Fetching valid IPs for node $NODE_NAME..."
    # Reset valid IPs file
    > "$VALID_IPS_FILE"
    
    # Fetch IPs
    kubectl get pods --all-namespaces --field-selector spec.nodeName="$NODE_NAME" -o jsonpath='{range .items[*]}{.status.podIP}{"\n"}{end}' > "$VALID_IPS_FILE"
    
    # Check if we got any IPs. If the node has active pods, we should have IPs.
    # If API call fails, valid_ips might be empty.
    # To be safe, if we can't talk to API, do NOT clean.
    if [ ! -s "$VALID_IPS_FILE" ]; then
         # Check if kubectl worked
         if ! kubectl get node "$NODE_NAME" &>/dev/null; then
             echo "Error: Cannot contact K8s API. Skipping cleanup."
         else
             echo "No pods with IPs found on this node. Proceeding with caution."
         fi
    fi
    
    # Valid IPs found (or empty if truly empty). Now check CNI.
    allocated_ips=$(ls -1 "$CNI_PATH" | grep -vE "lock|last_reserved_ip")
    leaked_count=0
    
    for ip in $allocated_ips; do
        if ! grep -q "^$ip$" "$VALID_IPS_FILE"; then
            echo "Removing leaked IP: $ip"
            rm -f "$CNI_PATH/$ip"
            leaked_count=$((leaked_count + 1))
        fi
    done
    
    echo "Cycle complete. Removed $leaked_count leaked IPs."
    echo "Sleeping for $SLEEP_INTERVAL seconds..."
    sleep "$SLEEP_INTERVAL"
done
