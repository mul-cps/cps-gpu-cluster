# GPU1 runtime head-delivery preservation handoff

The existing `cps-compute/cps-runtime-head-delivery` controller moved from GPU1 to GPU2 with preservation checks passing at **2026-11-17 23:29:10 UTC** (November18 local time). This is a preservation receipt, not renewed legacy GPU qualification or GPU1 OS acceptance.

The Deployment still had a GPU1 hostname selector. One UID/resourceVersion/full-spec guarded patch removed that selector under its existing **Recreate, replicas1** strategy. Server dry-run and actual admitted spec matched exactly; every other spec field, main/init image, service account and security setting remained unchanged. No additional eviction, forced deletion/detach, PVC clone, ownerRef trick, head/ACK rewrite or legacy agent revival occurred. See [placement and source proof](placement-and-source.safe.json).

The old actual CRI container was observed **absent at23:27:51.654300 UTC**, before the replacement writer's reported start at **23:28:13 UTC**. This is a verified absence-before-start witness, not a claimed exact old-process exit timestamp. The old Pod was absent when the replacement became Ready. Replacement Pod UID `14e9fefe-be47-488b-aff8-3f5af56f7c05`, Deployment generation83, runs on GPU2. [Writer ordering](writer-order.safe.json) retains the exact identities.

## Preserved authority and backup

The native store consists of atomic JSON files, not SQLite. All **169 journal files**, including53 completed publications and33 historical rotations, remained byte-exact. All **four regenerated private inputs**, four head UID/data identities, eight RoleBindings and corresponding Role rules, seed Secret UID/data, and both main/init imageIDs matched. `transition` remained null. The original PVC/PV remained Bound with a sole healthy attachment on GPU2. [Preservation receipt](postmove-preservation.safe.json) and [storage identities](storage-identities.safe.json) retain these checks.

Before relocation, a bounded backup held the controller's existing nonblocking journal lock and read all169 journal files plus four inputs into RAM. Pre/post hashes were checked, with no source writes. The private0600 archive contains **174 members**, including its proof; every member hash was verified. Archive size5,242,880 bytes, SHA256 `cfc8c18925ea672defb0afbca4cc9011fad49ab66d7c859574cc7aceda3f6117`. Only [backup metadata](native-backup-verified.safe.json) is published; no archive, input content, token or journal record is included.

The first backup transport failed with nginx **HTTP414** because its metadata argument was23,126 bytes. A harmless pass-only probe reproduced the URL limit; the first archive was empty and no remote backup or placement mutation occurred. The same tested helper and metadata were then sent over stdin after fresh guards, into a new exclusive output file. There was no retry of a mutating operation. [Transport correction](transport-correction.safe.json) preserves this distinction.

## Legacy state and scope

The replacement remains in the pre-existing legacy `blocked / ready=false` application state. Kubernetes Ready had no application readiness probe and is not evidence of functional publication health. The installed module is byte-identical to the reviewed source; its existing loop checks the legacy epoch before any publication mutation.

The main Gateway's final authenticated, verified-TLS/no-proxy/no-redirect read returned `/capture` **200**, unchanged revision `992ae99b027bccef76a537ce91fd6f249f48df6f6263523652ae54fc8985b863`, and `/epoch` **503**. Historical ACK/head bytes remained exact and the retired legacy node agent remained at replicas0. Current upstream Source admission does not require those legacy ACKs. No fresh legacy acknowledgment or qualification is claimed. See [final capture read](main-capture-after.safe.json).

This receipt does not cover subsequent stateless moves, the later prerequisite package operation/reboot, full GPU1 drain, OS upgrade, worker acceptance, human SSO or full-platform acceptance. Existing controller-cutover performance limitations remain unchanged.
