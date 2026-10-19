# Hub service roles

These source-specific Helm values fragments accompany the qualified platform
chart. Merge them with existing Hub values; preserve current services, roles,
usernames and storage configuration. Dynamic service registrations persist in
the Hub database, but their role assignments must also appear in `hub.loadRoles`:
Hub initialization clears service assignments absent from configured roles.

The initial console and observer services can read identity and server metadata
only. Course group and neutral workspace mutation permissions require exact,
reviewed group/user/server scope filters before activation. Browser service
access remains subject to the Hub's existing administrator role or separately
reviewed course access grants. No human compute identity mapping is enabled.

Register each confidential OAuth client and private service credential separately;
keep credentials out of these fragments. Back up matching Hub database/config
versions before a restart. Qualify each service's actual API token after restart,
not just a database role query. The empty `cps-workspace-kernel` role is an
operator-controlled principal marker, not a resource entitlement.

Native GPU notebooks require the `native-network-metadata-values.yaml` overlay
on both Hub releases. It replaces the chart's privileged metadata iptables init
container with NetworkPolicy enforcement. Before rollout, verify the CNI enforces
egress policy and that the union of all policies selecting notebook Pods excludes
169.254.169.254 TCP/80. Keep the native compiler's caller-init rejection enabled.
