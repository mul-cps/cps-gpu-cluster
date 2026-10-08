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
The separate TrueNAS bridge forwards TCP8333 to its existing management-side
S3 endpoint and has no host-published ports. Existing NFS addresses stay unchanged.

Internal TCP8022 is reserved for the gateway's workspace controller. The NAS
bridge accepts that port only from the enrolled cluster peer `100.65.52.117`
and forwards to internal `10.71.1.55:22`. Cluster ingress requires namespace
`cps-compute` and Pod label `app=compute-gateway`. SSH validates the original
`truenas.local` host key end to end. The dedicated controller key uses an
authorized-keys forced command with `restrict`; arbitrary shell commands fail.
The dispatcher is `scripts/compute-platform/truenas-workspace-rpc.py`, installed
at `/home/truenas_admin/.ssh/cps-workspace-rpc.py`. Its only operations are
provision/status/archive on fixed, source-and-group-hashed retained datasets.
It never deletes datasets or turns an archived dataset writable. Keep its
private key and pinned known-hosts file in controller Secrets, never user Pods.
The existing general operator SSH identity must not be installed in Kubernetes.

The dispatcher creates separate NFS exports for new datasets using the existing
client networks `10.71.1.0/24` and `10.21.0.0/16`; it changes no existing exports.
Archives use ZFS readonly plus an independent writable client mount that must
receive `EROFS`, after the controller confirms all writers have stopped.

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
