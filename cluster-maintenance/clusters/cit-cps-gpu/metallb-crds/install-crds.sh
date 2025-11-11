#!/bin/bash
set -e

echo "Installing MetalLB CRDs..."

# Install MetalLB CRDs from the official repository
# Version 0.14.9
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/crd/bases/metallb.io_addresspools.yaml
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/crd/bases/metallb.io_bfdprofiles.yaml
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/crd/bases/metallb.io_bgpadvertisements.yaml
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/crd/bases/metallb.io_bgppeers.yaml
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/crd/bases/metallb.io_communities.yaml
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/crd/bases/metallb.io_ipaddresspools.yaml
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.9/config/crd/bases/metallb.io_l2advertisements.yaml

echo "MetalLB CRDs installed successfully!"
