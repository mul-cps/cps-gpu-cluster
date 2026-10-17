# Runtime-limit deployment drift, 17 October 2026

Fresh readback confirms that the agreed catalog correction is still not deployed to the Gateway policy:

| Profile | Git catalog | Live Gateway policy |
|---|---:|---:|
| Interactive CPU |8h, idle1h|24h, idle1h|
| CPU batch |72h|4h|
| GPU batch (currently disabled)|24h|4h|
| Shared interactive GPU|4h, idle30m|4h, idle30m|
| Debug interactive GPU|1h, idle15m|1h, idle15m|

[result.json](result.json) binds the actual ConfigMap UID/resourceVersion, policy hash and all thirteen selected profile records. This readback does not prove Hub culler enforcement or update any consumer.

The current d48 policy hash remains bound into GPU qualifications, approvals and retained history. Apply the corrected catalog through a coordinated supported policy migration and verify Hub enforcement; do not patch one live document in isolation or rewrite old evidence. Preserve the four protected personal notebook Pods during that handover. No live policy changes were made.
