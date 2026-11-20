# Archive verifier resource bounds — 2026-10-07

Compute revision `6bb6a57` adds fixed CPU/memory requests and limits to the service-controlled archive verifier Job: requests 100m / 64Mi; limits 500m / 256Mi. The existing bounded deadline, UID/GID 1000, dropped capabilities, runtime-default seccomp and disabled token automount remain in place.

The original regression failed on missing resources. After the fix, all 36 storage tests and all 267 compute tests pass (22 existing dependency deprecation warnings). Generated Job and Pod specs were accepted in operator server dry runs in both jupyterhub and cit-jhub, retaining the exact resource bounds. The adjacent JSON records all four checks.

This is source and admission qualification only. Dry runs did not start a workload, mount a PVC, test controller-service-account authorization or prove NAS read-only enforcement under the new bounds. No production image was changed; a rebuilt matching compute/admin/notebook artifact set and bounded live archive test remain required before promotion. Previously published ecca902 images remain pinned to their own documented revision and do not contain this later fix.
