# Bounded current-pair MPS acceptance, 2026-10-14

Two ordinary Source-managed 5 GiB workspaces reached Ready together on the
current GPU2 no-MIG pilot. The frozen trusted MPS probe held 4,096 MiB, attempted
another 4,352 MiB and received CUDA result 2. Both clients recovered; the peer
completed 363 kernel ticks. The observer recorded 479 native samples, with
maximum charges 5,195,070,848 and 900,155,776 bytes, each within its 5 GiB cap.

`mps-receipt.json` is the exact successful private receipt, SHA-256
`877d6d496e327a264f5b936a34f8a7fc20830d88ccd75b634a0b457bce3448d4`.
It confirms actual private-process and endpoint cleanup, staged-source removal
and exact native baseline restoration. Its `gpu_capacity_released: false` means
the hardware caller itself does not stop workspaces. The separate
`closure-receipt.json` records both subsequent normal Source Close results:
confirmed shutdown, reservation release, restored windows/groups, no remaining
Shares, and retained storage. The final pair executor exited zero.

The reviewed caller uses bounded, hash-verified stdin loading and SPDY exec.
A real CPU-only 120-second comparison reproduced lost EOF over WebSocket;
SPDY delivered EOF and exited normally. Seventeen focused tests and Ruff passed.
The host mapper and GPU probe remained unchanged. Their exact hashes are in the
receipt. Earlier HTTP 414 and incomplete observer-shutdown attempts remain
retained separately and are not relabelled as passes.

This qualifies this bounded pair's MPS OOM/recovery, peer continuity and cleanup.
It does not qualify KAI placement, wider 5/10/20 GiB packing, the eight-GPU fleet,
cross-Hub pooling, human OAuth, or production readiness.

Current immutable application boundary: Hub `145bfde0`, Source `8d86a5bc`,
gateway `440711b2`, node agent `5079458f`; policy `d48f6553`, Source approval
revision `832e841b`. Full hashes remain in the preceding deployment records.
