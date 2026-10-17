# Distinct-process IPC positive — 17 October 2026

Actual normal console Start returned200/running. Two simultaneous processes (namespace PIDs203/213) in shared-gpu-lab Pod df3a7a8f-4e49-497a-b87e-57e9b0a4abb1 imported the same CUDA allocation successfully, read byte19, ran ordinary kernels before/after, recovered the exporter, and exited0 with explicit native cleanup. Host sealed cap remained5GiB. Exact workload image916786...ca4dc0 is recorded in the receipt and matches live policy plus immutable qualification records.

Initial wrapper rejected a stale531 image pin before GPU calls. The reviewed current wrapper pins exact916 plus policy hash; SHA256 `4cbf9caeec300754ac0b13f6fb8d461abc83cb057919028cb3af124e009ff2b8`. This test qualifies same-Pod IPC between distinct processes only. Cross-Pod denial, distinct-process VMM and full production qualification remain open. Private raw endpoint logs and host records retained locally.

Normal Stop200 confirmed Pod absent. All100ledgerclaims released; SQL reservation and binding counts0. Temporary tokena823 revoked, subsequent authentication denied and local token file removed.
