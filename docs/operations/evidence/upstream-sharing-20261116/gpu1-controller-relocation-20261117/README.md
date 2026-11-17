# GPU1 controller and local-data relocation

Root accepted preservation of the relocated controllers and shared authority store on 2026-11-17 UTC. GPU1 remains cordoned and maintenance-tainted; this receipt does not claim a completed full drain, OS nomination, worker acceptance or full-platform acceptance. GPU2/GPU3 remain the accepted fixed-profile workers. Only sanitized receipts and archive metadata are published here; private database copies, configuration contents, tokens and archives are excluded.

| Component | Actual result | Preservation and limits |
|---|---|---|
| CPS Hub | Generation382 Ready on GPU2; original writer stopped in CRI before replacement started; health200 | Same PostgreSQL/PVC/PV, schema and19 of21 table hashes exact, all9 referenced Secret identities/data exact. The two explicitly accepted startup differences were an idle-culler **service** token/activity timestamps and salted rehash of the existing Argo OAuth client's secret. No user-token, account, role, scope, membership or custody changes. Literal all21-table equality was **false**. |
| Main + native147 Gateways | Generations442/35 Ready together on GPU2; both original writers absent from API/CRI, natural CSI detach, same authoritative RWO PVC/PV | All four database schemas and every logical row exact before unfence;13 protected files backed up,10 main private files exact afterward; all23 configuration UIDs retained and22 static hashes exact. Only the existing five-minute Argo reader TokenRequest rotation changed its token field; Root validated it against the API. Original Service specs and backup Cron restored; no clone, forced detach or custody deletion. |
| BuildKit | Desired2 replicas Ready on GPU3/GPU4 after ordinary eviction; original Service restored | Selected old cache PV retained in Released state with backend path/stat preserved. Old cache was **not** automatically reattached. This is cache preservation, not a restored-cache performance claim. |
| OpenWebUI | Source owner and actual workload stopped at replicas0; old Pod absent and no live data-PVC consumer | Same Bound PVC/PV retained. Private0600 cold-data archive:1,257,362,446 bytes, SHA256 `1246f573f919052542e51f289adba8eec27f0ad3ce001bd12cad6a2cb43b2804`, archive catalog verified. No full restore rehearsal and no VM clone/backup claim. |

Fresh controller checks are in [current-controllers-and-fences.safe.json](current-controllers-and-fences.safe.json). Both Knative availability floors are5, with5 healthy replicas and unchanged80% PDBs allowing one disruption. Activator max remains20; webhook max remains5. These current gates do not waive subsequent drain checks.

CPS source owner pin is `550a835e57c52147858f2b89a36622878b8a5ea1`; CIT remains `193747673c91a64787b6c9683020c07fc6a03f56`. Hub images remain0bbe/bf and Source console image478. Main Gateway remains6e; native147 remains270116. Placement changes introduced no runtime, authority-policy or TLS relaxation.

## Legacy behavior preserved, not repaired

Main Source read APIs returned200 after restoration. Capture returned200 with unchanged revision `992ae99b027bccef76a537ce91fd6f249f48df6f6263523652ae54fc8985b863`. Legacy `/epoch` remains503, the legacy ACK remains stale, and its retired node agent remains at replicas0. Current upstream Source admission does not depend on these legacy acknowledgments.

The native147 dedicated TLS certificate is unchanged and had already expired on October29. TLS verification correctly refuses it. Its TCP Ready state is preserved, but **no fresh native147 HTTPS qualification is claimed**. The main CA is not a substitute for its dedicated trust. No certificate renewal, TLS bypass, ACK rewrite or revival of legacy GPU machinery occurred.

## Timing and remaining gates

The CPS Hub's sampled public-health gap had a conservative upper bound of **28.644 seconds**. The main Gateway's controlled Service fence lasted **936.802 seconds**, including backup and operator diagnostics. Therefore this episode **does not meet the60-second controller cutover goal**. One measured Hub gap is not a general availability qualification.

Full GPU1 drain/OS/runtime qualification, GPU4 rollout, human/nonadministrator SSO/RTC, cross-cgroup imports/exported pools/forced numeric PID reuse, advanced/distributed modes, startup bursts and complete platform recovery remain open. Canonical quota enforcement passed previously, but Source's generic503 quota-error presentation remains an open UX defect.

The linked Root receipts record actual execution outcomes; they are not reconstructed terminal transcripts. [Manifest](manifest.safe.json) binds the copied safe receipts. No private token, Secret content, database row, archive content or raw log is included.
