# Bidirectional legacy CUDA IPC isolation — 17 October 2026

Two distinct shared-workspace Pods with sealed 5 GiB caps passed both directions:
same-parent import succeeded; cross-Pod import returned CUDA error 800 with a
correlated kernel denial. Exporter and importer kernels continued running, and
explicit endpoint and witness cleanup completed. Independent offline replay
validated both event streams, kernel correlations and process attribution.

The per-direction inherited `awaiting-kernel-witness` state predates the separate
validated correlation files. It is retained as raw evidence, not rewritten.
Broad isolation and production qualification flags remain false. This proves the
legacy CUDA IPC path only: distinct-process VMM/POSIX-FD, other memory routes,
MPS, 10/20 GiB qualification and production concurrency remain open.

Raw IPC handle logs and credentials remain private. Both normal Stops returned
200; temporary grant expiry changes were restored and the test token revoked.
The cleanup receipt verifies all 103 native allocations released and personal
notebook Pod identities unchanged.
