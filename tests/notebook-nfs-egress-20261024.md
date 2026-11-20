# Notebook egress source reconciliation, 2026-10-24

Base: `63cff666074810debfc878cf78896ed60f4e377e`. No live changes performed.

Pinned JupyterHub chart: 4.4.2, archive SHA256
`0ddfa517050d16f2e1b50c62b5b6377b12574f9a2b88f3b352bd211ef3173c3e`.

Run `JUPYTERHUB_CHART=/path/jupyterhub-4.4.2.tgz python3 -m unittest discover -s tests -p test_notebook_nfs_egress.py`.
Both original deployed source baselines fail for NAS193.170.30.58 TCP111;
fixed source passes. The regression checks additive IP-block destination/port
semantics, 111/2049 exclusions for TCP/UDP, allowed range boundaries, private
reachability intent, metadata exclusion, DNS, HTTPS and S3port9000.

Rendered singleuser policy SHA256: `f89d2ca02c92ef75c0237f9099bba6b846c2d464d8ebe8d48297ecdc091652d5`.
Normalized complete rendered spec equals current live spec (default TCP protocol
and unordered lists normalized). Therefore this change needs no object-only live
reconcile. Other currently matching live notebook egress policy only adds
TCP8000 to compute-gateway; it does not reopen the excluded ports.

This qualifies the canonical rendering, not runtime connectivity or NAS export
security. Future deployment must avoid rolling existing user Pods unnecessarily.

The evaluator handles omitted and empty `to`/`ports` as unrestricted. Mutation
checks demonstrate that additive broad grants reopen both excluded ports.
The test pins the chart archive SHA256, not only its version label.

CI gate: `.github/workflows/notebook-egress.yml` runs on GitHub-hosted
ubuntu-24.04 for relevant PR/push paths with contents:read only. It installs
PyYAML6.0.3 and checksum-pinned Helm3.19.0, downloads and verifies the exact
chart, then runs the focused tests. No cluster credentials, secrets, self-hosted
runners or deployment operations are used. Workflow shell steps were run
locally; GitHub Actions execution remains unverified until publication.
