# Private S3 access through NetBird

The cluster and TrueNAS currently use NetBird Cloud relays over TCP443.
Traffic is slow: approximately 31–32 Mbit/s for one stream in the pilot.
No public listeners, new firewall openings, host-network routes or NFS changes
are required. This directory remains outside Fleet until its release is qualified.

The `artifacts.cps-artifacts-relay.svc.cluster.local:8333` ClusterIP is the S3
endpoint. HAProxy accepts TLS with a certificate for that exact DNS name, then
re-encrypts to TrueNAS over NetBird. Backend validation requires both the NAS CA
and the existing `truenas.local` certificate identity. S3 bodies are visible to
this trusted cluster proxy; traffic over the external relay remains encrypted.
The separate TrueNAS bridge only forwards TCP8333 to its existing management-side
S3 endpoint and has no host-published ports. Existing NFS addresses stay unchanged.

Before `kubectl apply -k .`, provision private resources in this namespace:

- Secret `netbird-peer-identity`, key `default.json`: existing enrolled cluster
  identity, stored outside Git and backed up securely. Do not run two peers with
  the same identity concurrently.
- Secret `artifacts-relay-tls`, key `server.pem`: certificate and private key.
- ConfigMap `artifacts-relay-ca`, key `ca.crt`: NAS CA trust.

The identity is copied into a Longhorn PVC only on its first initialization.
One replica and Recreate upgrades prevent simultaneous identity use. The NetBird
client disables received LAN routes, routing-peer operation and DNS mutation.
NetworkPolicy allows S3 ingress only from the platform, workflow and Hub namespaces.
Gateway/Argo artifact credentials stay in their own Secrets; the relay has none.

Qualify authenticated PUT/GET/DELETE and byte hashes using the DNS endpoint and
normal CA/hostname verification, then restart the deployment and repeat. Back up
the PVC and TLS/identity secrets with matching image versions. Preserve the old
pilot until migration checks pass, but stop its peer before starting this one.

Failures remain fail-closed. A TCP listener readiness probe alone does not prove
NAS access; operator qualification must include the complete S3 path. This service
is not an alternative bulk-data path: datasets/checkpoints continue to use NFS.
