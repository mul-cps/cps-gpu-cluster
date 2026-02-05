# MetalLB Configuration

This bundle contains the MetalLB configuration resources (IPAddressPool and L2Advertisement).

## Resources

- **IPAddressPool**: Defines the IP address range (10.21.0.50-10.21.0.60) for LoadBalancer services
- **L2Advertisement**: Configures Layer 2 (ARP-based) advertisement for the IP pool

## Dependencies

- **metallb-crds**: CRDs must be installed first
- **metallb**: MetalLB controller and speaker must be running

## Deployment Order

1. **metallb-crds** - Installs CRDs
2. **metallb** - Installs MetalLB controller and speaker
3. **metallb-config** (this bundle) - Applies configuration
