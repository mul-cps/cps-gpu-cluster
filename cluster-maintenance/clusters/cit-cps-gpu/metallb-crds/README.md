# MetalLB CRDs

This bundle installs the MetalLB Custom Resource Definitions (CRDs) separately to ensure they are available before the main MetalLB installation.

## CRDs Installed

- `IPAddressPool` - Defines IP address ranges for LoadBalancer services
- `L2Advertisement` - Configures Layer 2 (ARP) advertisements
- `BGPPeer` - BGP peering configuration (not used in our L2 setup)
- `BGPAdvertisement` - BGP advertisement configuration (not used in our L2 setup)
- `BFDProfile` - BFD session configuration (not used in our L2 setup)
- `Community` - BGP community configuration (not used in our L2 setup)

## Dependencies

None - this must be deployed before the main `metallb` bundle.

## Deployment Order

1. **metallb-crds** (this bundle) - Installs CRDs
2. **metallb** - Installs MetalLB controller, speaker, and configuration
