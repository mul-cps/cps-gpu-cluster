#!/usr/bin/env bash
# Script to set up SSH keys between VMs using Proxmox QEMU guest agent
# This bypasses SSH and uses the Proxmox API + qm guest exec
# Run this script ON THE PROXMOX HOST

set -euo pipefail

# VM IDs (adjust if different)
MAINTENANCE_VM=109  # Adjust to actual VM ID
CONTROL_PLANE_VMS=(106 107 108)
WORKER_VMS=(102 103 104 105)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "SSH Key Setup via Proxmox QEMU Guest Agent"
echo "================================================"
echo ""

# Function to check if guest agent is running
check_guest_agent() {
    local vmid=$1
    if ! qm guest cmd "$vmid" ping &>/dev/null; then
        echo -e "${RED}ERROR: QEMU guest agent not responding on VM $vmid${NC}"
        return 1
    fi
    return 0
}

# Function to execute command in VM
vm_exec() {
    local vmid=$1
    shift
    local cmd="$*"
    
    if ! check_guest_agent "$vmid"; then
        return 1
    fi
    
    # Execute command via guest agent
    qm guest exec "$vmid" -- bash -c "$cmd"
}

# Function to get command output
vm_exec_output() {
    local vmid=$1
    shift
    local cmd="$*"
    
    if ! check_guest_agent "$vmid"; then
        return 1
    fi
    
    # Execute and get output
    local exec_result
    exec_result=$(qm guest exec "$vmid" -- bash -c "$cmd" 2>&1)
    echo "$exec_result"
}

echo "Step 1: Checking QEMU guest agent on all VMs..."
echo "------------------------------------------------"
ALL_VMS=("$MAINTENANCE_VM" "${CONTROL_PLANE_VMS[@]}" "${WORKER_VMS[@]}")
for vmid in "${ALL_VMS[@]}"; do
    if check_guest_agent "$vmid"; then
        echo -e "${GREEN}✓${NC} VM $vmid: Guest agent OK"
    else
        echo -e "${RED}✗${NC} VM $vmid: Guest agent not responding"
        exit 1
    fi
done
echo ""

echo "Step 2: Generate SSH key on maintenance VM (if not exists)..."
echo "--------------------------------------------------------------"
vm_exec "$MAINTENANCE_VM" "sudo -u ubuntu bash -c 'if [ ! -f ~/.ssh/id_ed25519 ]; then ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N \"\" -C \"ubuntu@k3s-maintenance\"; echo \"Key generated\"; else echo \"Key already exists\"; fi'"
echo -e "${GREEN}✓${NC} SSH key ready on maintenance VM"
echo ""

echo "Step 3: Fetch public key from maintenance VM..."
echo "------------------------------------------------"
TEMP_PUBKEY=$(mktemp)
vm_exec_output "$MAINTENANCE_VM" "sudo -u ubuntu cat /home/ubuntu/.ssh/id_ed25519.pub" | grep "^ssh-" > "$TEMP_PUBKEY" || {
    echo -e "${RED}ERROR: Could not fetch public key${NC}"
    rm -f "$TEMP_PUBKEY"
    exit 1
}

MAINTENANCE_PUBKEY=$(cat "$TEMP_PUBKEY")
echo "Public key: ${MAINTENANCE_PUBKEY:0:80}..."
echo ""

echo "Step 4: Distribute public key to all cluster nodes..."
echo "------------------------------------------------------"
for vmid in "${CONTROL_PLANE_VMS[@]}" "${WORKER_VMS[@]}"; do
    echo "Adding key to VM $vmid..."
    
    # Create .ssh directory if not exists
    vm_exec "$vmid" "sudo -u ubuntu mkdir -p /home/ubuntu/.ssh && sudo -u ubuntu chmod 700 /home/ubuntu/.ssh"
    
    # Add key to authorized_keys if not already present
    vm_exec "$vmid" "sudo -u ubuntu bash -c 'grep -qF \"$MAINTENANCE_PUBKEY\" ~/.ssh/authorized_keys 2>/dev/null || echo \"$MAINTENANCE_PUBKEY\" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'"
    
    echo -e "${GREEN}✓${NC} VM $vmid: Key added"
done
echo ""

echo "Step 5: Fix known_hosts permissions on maintenance VM..."
echo "---------------------------------------------------------"
vm_exec "$MAINTENANCE_VM" "sudo -u ubuntu bash -c 'touch ~/.ssh/known_hosts && chmod 644 ~/.ssh/known_hosts'"
echo -e "${GREEN}✓${NC} Fixed known_hosts permissions"
echo ""

echo "Step 6: Add host keys to known_hosts on maintenance VM..."
echo "----------------------------------------------------------"
# Get IPs from running VMs
CONTROL_PLANE_IPS=(10.21.0.35 10.21.0.36 10.21.0.37)
WORKER_IPS=(10.21.0.38 10.21.0.43 10.21.0.40 10.21.0.41)

for ip in "${CONTROL_PLANE_IPS[@]}" "${WORKER_IPS[@]}"; do
    echo "Adding host key for $ip..."
    vm_exec "$MAINTENANCE_VM" "sudo -u ubuntu ssh-keyscan -H $ip >> /home/ubuntu/.ssh/known_hosts 2>/dev/null || true"
done
echo -e "${GREEN}✓${NC} Host keys added"
echo ""

echo "Step 7: Test SSH connectivity from maintenance VM..."
echo "-----------------------------------------------------"
echo "Testing connection to first control plane (${CONTROL_PLANE_IPS[0]})..."
TEST_RESULT=$(vm_exec_output "$MAINTENANCE_VM" "sudo -u ubuntu ssh -o BatchMode=yes -o ConnectTimeout=5 ubuntu@${CONTROL_PLANE_IPS[0]} 'hostname' 2>&1" || echo "FAILED")

if echo "$TEST_RESULT" | grep -q "k3s-cp1"; then
    echo -e "${GREEN}✓${NC} SSH test SUCCESSFUL!"
    echo "Result: $TEST_RESULT"
else
    echo -e "${YELLOW}⚠${NC}  SSH test returned: $TEST_RESULT"
    echo "You may need to manually accept host keys on first connection"
fi
echo ""

# Cleanup
rm -f "$TEMP_PUBKEY"

echo "================================================"
echo "SSH key setup complete!"
echo "================================================"
echo ""
echo "You can now SSH from maintenance VM to any cluster node:"
echo "  ssh ubuntu@10.21.0.35  (k3s-cp1)"
echo "  ssh ubuntu@10.21.0.38  (k3s-wk-gpu1)"
echo "  etc."
echo ""
echo "To verify manually, SSH to maintenance VM and test:"
echo "  ssh ubuntu@10.21.0.42"
echo "  ssh ubuntu@10.21.0.35"
