# GPU3 Source QA pre-CREATE recovery

The first CPS shared5 GPU3 QA start failed in the temporary trusted QA routing hook: actual Hub service-account GET of GPU3 returned403 before KubeSpawner Pod CREATE. The Hub trace is correlated with the exact attempt by control audit sequence7658 and retained attempt/generation. Earlier impersonation-only permission evidence was insufficient.

One reviewed standalone operator payload (source commit6674e4bb1e7eb2955a16ad693ce185ec5324f703, payload SHA25696e293036d01e5ca9b7cb25c40edac17310752d43050505201a93c9ed9e3a3c1) was rehearsed on native SQLite copies and applied once at18:14:58Z. Root approved canonical plan SHA2561fb71bdd1d0c72f5c2138a802e55dcf36cd3a3d05276e9b426d70af6e366219e while fresh receipts remained valid.

The old creator was gone from API/CRI, its credentials closed, replacement creator fenced by actual403 and expired QA permit. Exact QA Pods/containers and GPU contexts were absent on both eligible workers. Installed code hashes and hook-before-CREATE ordering were independently verified. Native backups were retained. The release was based on this combined evidence, never Pod absence alone.

The attached-database transaction removed only the exact QA reservation and binding and appended one operator audit. Full native post-backup comparison confirms every other row and schema unchanged, including grants, workspace/storage records and native approval tables. Normal runtime modules, images and release guards were not replaced.

A temporary standard ClusterRole now grants both Hub service accounts GET of GPU3 only. Actual in-cluster clients return200 for GPU3 and403 for GPU2/list. The expired QA permit remains in place. Normal Source STOP/reconciliation and a fresh bounded QA epoch are next; no real Source GPU3 GPU acceptance is claimed. Remove the temporary role/binding after restoring original Hub configuration.

GPU2 remains accepted. GPU3 retains its maintenance taint; GPU1/GPU4 are not nominated. Full worker and rollout acceptance remain open.

At18:22:29Z, a fresh CPS-only native operator credential completed one normal Source STOP200. Source GET reports stopped, exact Pod is absent, and strict TLS authoritative lease reports inactive/attemptnull. The token was revoked, actual authorization denied, raw handoff removed, and independent watch exited. Hub owner31/spawner72 has serverNone but retains the old attempt/generation metadata. No direct state edit or new GPU start occurred; startup handling of that historical marker is being checked.

At18:38:26Z, standard JupyterHub named-server DELETE with remove:true was verified complete (204). Installed KubeSpawner7.1/shared PVC template returns before any PVC API request; an executable positive control exercised the destructive-template path, while the actual template made zero PVC calls. The old rtc spawner72 is absent. Canonical owner31, account/custody/receipt hashes, roles and group associations remain exact; Shares/ShareCodes remain zero. PVC/PV UIDs, NFS location and Bound state remain unchanged, and authoritative lease is inactive/attemptnull. This resolved the historical marker through the upstream API, with no runtime patch or direct Hub database edit. Current filesystem content has not been reread yet; retained-file verification belongs to the next normal workspace start.

Only the existing five QA grants were renewed expiry-only for the next bounded epoch. All58 grant rows remained present, other53 raw rows and the authorized original49 guard matched. Eight verified-TLS effective responses (both Sources, four people) matched exactly, allowance1. The actual installed QA permit remains expired pending the separately reviewed next configuration. GPU3 real Source GPU acceptance is still open.
