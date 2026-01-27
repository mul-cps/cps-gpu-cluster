#!/bin/bash
set -e

# 1. Generate global IP mapping
echo "Generating valid IP mapping..."
kubectl get pods --all-namespaces -o jsonpath='{range .items[*]}{.status.podIP} {.spec.nodeName}{"\n"}{end}' > /tmp/all_valid_ips.txt

# 2. Get debug pods and their nodes
DEBUG_PODS=$(kubectl get pods -l app=debug-cni -o jsonpath='{range .items[*]}{.metadata.name} {.spec.nodeName}{"\n"}{end}')

echo "Starting cluster-wide analysis..."
echo "---------------------------------"

echo "$DEBUG_PODS" | while read -r pod_name node_name; do
    if [ -z "$pod_name" ]; then continue; fi
    
    echo "Analyzing Node: $node_name (Pod: $pod_name)"
    
    # Filter IPs for this node
    grep " $node_name$" /tmp/all_valid_ips.txt | awk '{print $1}' > "/tmp/valid_ips_$node_name.txt"
    
    # Copy files to pod
    kubectl cp "analyze_and_clean_cni.sh" "$pod_name:/tmp/analyze_and_clean_cni.sh"
    kubectl cp "/tmp/valid_ips_$node_name.txt" "$pod_name:/tmp/valid_ips.txt"
    
    # Make script executable
    kubectl exec "$pod_name" -- chmod +x /tmp/analyze_and_clean_cni.sh
    
    # Run analysis (clean mode)
    echo "  > Running cleanup..."
    kubectl exec "$pod_name" -- /tmp/analyze_and_clean_cni.sh clean
    
    echo "---------------------------------"
done
