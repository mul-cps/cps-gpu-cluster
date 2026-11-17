# GPU3 Source QA pre-CREATE recovery

The first CPS shared5 GPU3 QA start failed in the temporary trusted QA routing hook: actual Hub service-account GET of GPU3 returned403 before KubeSpawner Pod CREATE. The Hub trace is correlated with the exact attempt by control audit sequence7658 and retained attempt/generation. Earlier impersonation-only permission evidence was insufficient.

One reviewed standalone operator payload (source commit6674e4bb1e7eb2955a16ad693ce185ec5324f703, payload SHA25696e293036d01e5ca9b7cb25c40edac17310752d43050505201a93c9ed9e3a3c1) was rehearsed on native SQLite copies and applied once at18:14:58Z. Root approved canonical plan SHA2561fb71bdd1d0c72f5c2138a802e55dcf36cd3a3d05276e9b426d70af6e366219e while fresh receipts remained valid.

The old creator was gone from API/CRI, its credentials closed, replacement creator fenced by actual403 and expired QA permit. Exact QA Pods/containers and GPU contexts were absent on both eligible workers. Installed code hashes and hook-before-CREATE ordering were independently verified. Native backups were retained. The release was based on this combined evidence, never Pod absence alone.

The attached-database transaction removed only the exact QA reservation and binding and appended one operator audit. Full native post-backup comparison confirms every other row and schema unchanged, including grants, workspace/storage records and native approval tables. Normal runtime modules, images and release guards were not replaced.

A temporary standard ClusterRole now grants both Hub service accounts GET of GPU3 only. Actual in-cluster clients return200 for GPU3 and403 for GPU2/list. The expired QA permit remains in place. Normal Source STOP/reconciliation and a fresh bounded QA epoch are next; no real Source GPU3 GPU acceptance is claimed. Remove the temporary role/binding after restoring original Hub configuration.

GPU2 remains accepted. GPU3 retains its maintenance taint; GPU1/GPU4 are not nominated. Full worker and rollout acceptance remain open.
