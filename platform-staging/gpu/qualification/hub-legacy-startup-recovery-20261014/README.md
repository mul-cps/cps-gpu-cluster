# Both-Hub legacy custody startup recovery

The `f5bff2df` qualification image failed during both Hub startups: its role
guard compared configured legacy kernel owners with registry-managed owners
only. The legacy owners remained in the Hub databases; this was a startup
configuration mismatch. The preceding custody-table migration and CPS QA
account repair had already succeeded.

The reviewed `145bfde0` replacement preserves validated legacy owners while
retaining the registry custody and revocation checks. The controlled successor
handover changed only both Hub images, their immutable publisher bindings, and
the two matching image declarations in Gateway runtime trust. Gateway code,
Source code, policy, node-agent code, driver and storage remained unchanged.

The actual successor passed both-Hub Ready checks, all four current-process
image/UID acknowledgments, seven full-preimage Role updates, mounted Gateway
runtime verification, and completion of a new delivery journal. The original
immutable delivery input and journal PVC were retained. Final protected native
readback showed zero active caps and zero charged bytes. Live checks confirmed
12 installed Hub module files per Hub match the reviewed wheel, the core
payload is unchanged, and both Hubs run as UID 1000 with JupyterHub 5.5.2 and
KubeSpawner 7.1.0.

[receipt.json](receipt.json) records immutable artifact provenance, process and
delivery UIDs, private evidence hashes, the failed and successful stages, and
the retained successful SQL migration receipt. The image handover performed no
database migration or rollback. This receipt does not claim a complete live
SQL equality comparison after startup.

This is qualification-image recovery evidence, not a production release or an
MPS qualification. Readiness and zero-allocation claims describe the recorded
handover completion; they do not describe later workloads. No notebooks or GPU
jobs were started by this recovery.
