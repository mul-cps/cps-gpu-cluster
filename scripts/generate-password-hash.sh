#!/usr/bin/env bash
# Script to generate a password hash for cloud-init
# Usage: ./generate-password-hash.sh

set -euo pipefail

echo "================================================"
echo "Generate Password Hash for Cloud-Init"
echo "================================================"
echo ""
echo "Enter the password for the ubuntu user:"
read -s password
echo ""
echo "Confirm password:"
read -s password_confirm
echo ""

if [ "$password" != "$password_confirm" ]; then
    echo "❌ Passwords do not match!"
    exit 1
fi

# Generate SHA-512 hash (cloud-init compatible)
# Using Python's crypt module which is available on most systems
password_hash=$(python3 -c "import crypt; print(crypt.crypt('$password', crypt.mksalt(crypt.METHOD_SHA512)))")

echo "================================================"
echo "✅ Password hash generated!"
echo "================================================"
echo ""
echo "Add this line to terraform.tfvars:"
echo ""
echo "vm_password = \"$password_hash\""
echo ""
echo "Note: This hash is compatible with cloud-init's cipassword parameter"
