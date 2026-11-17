# CIT JupyterHub relocation from GPU1

Root released three ordinary Evictions, one at a time: PostgreSQL moved to GPU3, Hub to GPU2, then proxy to GPU3. Each old runtime container was observed stopped before the replacement container started. Native termination grace and the PostgreSQL PDB were preserved. No direct Pod deletion, force, finalizer, PVC change, Source operation, role change or notebook stop was used.

The existing PG18.4 image was permanently pinned by digest before relocation. Temporary OnDelete prevented an automatic image-template rollout; the default RollingUpdate strategy was restored only after the replacement was Ready on the new pinned revision. The restoration changed no Pod template and caused no additional restart. Both source commits and remote SHAs were verified; Root alone pinned Fleet revisions.

Schema and 19 of 21 table hashes match. The only actual changes are the documented idle-culler service token, service-token activity timestamps and the existing Argo OAuth client salted secret hash. All 26 user records, roles, accounts, custody, groups, spawners and Shares match. Nine Secret and 13 ConfigMap identities/data fingerprints match. The initial bytea memoryview-address hashing defect and its deterministic native-backup correction are retained explicitly.

The native backup is private, 0600, and its matching-client catalog is verified. No dump, private inputs, Secret values or raw credentials are published here. Longhorn's degraded state during Root's selected-node instance-manager maintenance is recorded honestly with two current remote RW copies. This is infrastructure preservation evidence, not new GPU or human-access acceptance.
