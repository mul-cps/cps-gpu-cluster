# Bounded archive verifier live qualification — 2026-10-07

The current 6bb6a57 source generated real verifier Jobs against the retained CPS and CIT HTTP-runtime qualification archives. Both Jobs used requests 100m/64Mi and limits 500m/256Mi. Both non-root UID 1000 containers exited zero without OOMKilled and reported real NFS EROFS with client-side readOnly unset/false. Therefore the archive check exercised NAS enforcement, rather than merely a read-only client mount.

Only the previously recorded qualification-group Retain PVs were rebound temporarily. The harness verified prior archive ownership, absent claims/writers and Released state, guarded binding changes by resource version, removed its Jobs/Pods/PVCs and restored original claimRefs. A fresh live check confirmed no group Jobs/Pods and both PVs Released with retained original paths. Archive datasets were not changed.

Two evidence-harness runs were rejected before the final success: SDK log decoding required raw bytes, and API-default false readOnly returned unset. Both failure paths cleaned up before retry. Private `storage-verifier-live/run.py`, logs and final report preserve this history. The adjacent JSON records the verified run.

This qualifies resource-bounded archive execution with the current source and existing immutable f0b96b8 verifier runtime. It used operator Kubernetes access, not an authenticated gateway/controller-SA HTTP flow, and does not qualify a new packaged artifact. Rebuilding and integrating matching artifacts remain pending; production was unchanged.
