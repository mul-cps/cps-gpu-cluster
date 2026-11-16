# Local-path scratch configuration ownership

`fast-scratch` selects `/mnt/nvme/scratch`; local-path-provisioner also requires
that exact directory in `local-path-config.data.config.json.nodePathMap` for
the selected node. GPU1–4 are explicitly listed, preserving the default K3s
storage path for all nodes.

K3s rewrites and reapplies its packaged `local-storage.yaml` when a server
starts. That manifest contains a default-only ConfigMap and can reset the
scratch allowlist. Helm ownership labels alone do not prevent its AddOn
controller from owning the same ConfigMap; Fleet then reports "not owned by us".

Bootstrap `03-storage.yml` creates `local-storage.yaml.skip` on **every control
plane server**, preserving existing resources while preventing packaged
reapplication. It transfers only the ConfigMap's ownership metadata to Fleet;
the existing local-path StorageClass, provisioner Deployment/RBAC and all
PV/PVC data stay in place. Do not use `--disable=local-storage` for this handoff:
that actively uninstalls the packaged resources. Future local-path-provisioner
upgrades must be performed explicitly because the packaged AddOn is skipped.

The ConfigMap manifest manages `config.json` only. Preserve its existing
`helperPod.yaml`, `setup` and `teardown` keys during handoff or manual repair.
If the provisioner has given up after its retry threshold, restart only its
Deployment after correcting the ConfigMap; applications and existing volumes
do not need deletion.

Measured 2026-11-16: restored the allowlist, restarted local-path-provisioner
v0.0.36 after its retries>=15 threshold, and the exact reported
`splatograph-lwzw7-runner-gczcc-work` claim provisioned successfully on GPU4.
ARC subsequently removed its ephemeral runner/claim naturally. A separate
100Mi fast-scratch PVC plus nonroot UID1000 GPU4 Pod passed write/read and was
cleaned up. GPU4 scratch was an ext4 mount on /dev/sdb with 534GiB free before
the fixture. No user PVC/runner was force-deleted.

References:
- https://docs.k3s.io/installation/packaged-components#using-skip-files
- https://github.com/rancher/local-path-provisioner/tree/v0.0.36

After the handoff and a force-sync of only the storage-classes Bundle, Fleet
reported Ready at 2026-11-16 12:43:53 UTC. The ConfigMap retains all four data
keys and now has Fleet objectset ID `default-storage-classes-cattle-fleet-local-system`,
with no K3s AddOn owner annotations. All three skip markers were read back. A
future control-plane K3s restart was not performed as part of this repair; skip
behavior relies on K3s's documented contract.
