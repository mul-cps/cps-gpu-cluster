# Profile walltime addon image

Published candidate: `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:fb9872bf71bfee402807c4f0e9adc92c49740ec30fa4a6a4261fa2ae18d32a45`. Registry readback matches the recorded manifest digest.

Installed checks preserve 30 SDK modules and 423 other distributions; 10 wheel payload files match, SDK/addon RECORD hashes and sizes verify with no overlapping ownership. The existing Python server hook is unchanged. Authenticated timer status works and polling does not change activity.

The complete before/after inventories contain 114,880 files each. SoftwarePreservation verifies the original 83 OCI base-layer descriptors and diffID prefix, runtime settings, package payloads and unchanged SDK RECORD. Full inventories and the 80.9 MB receipt remain in private release evidence.

The initial proof incorrectly compared pip-generated RECORD with wheel RECORD; this was corrected while retaining installed RECORD integrity checks. Initial publication converted base blobs to uncompressed form and was rejected. The corrected publication references the original registry base blobs after verifying identical diffIDs; the unchanged verifier passes. Rejected artifacts remain retained.

This is software preservation evidence, not new GPU hardware qualification. Policy handover, deployment and live addon acceptance remain pending.
