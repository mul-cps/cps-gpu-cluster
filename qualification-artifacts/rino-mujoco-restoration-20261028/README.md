# CIT MuJoCo restoration, 28 October 2026

Actual user `m12113877` started the default server with `mujoco-desktop-exclusive` and a selected 24-hour maximum. The Pod became Ready on GPU1. Its original `claim-m12113877` PVC UID is retained. CUDA/PyTorch ran on exactly one physical A100; MuJoCo 3.12.0 rendered a nonblank 128x128 frame through NVIDIA EGL; the authenticated local Xpra endpoint returned HTTP 200; a temporary home-file write and removal passed. The three existing research Pod UIDs remained unchanged. The short-lived verification token was revoked.

This was an operator-run account-scoped restoration check. It does not prove a full browser desktop session or the student's training workload. It does not qualify general fractional sharing or all eight devices.

The fixed image uses the reviewed source commit and digest recorded in `result.json`. Source review and focused tests precede the live run. The sole exception is CIT username/default-server scoped; no canonical-person mapping was invented. It uses non-preempting `cps-rino-research` priority 60 and preserves the existing home volume. Runtime choices are 2, 4, 8, 12, or 24 hours, default 2 hours; this start explicitly selected 24.

Two integration failures were corrected: the Hub uses a separate immutable configuration Secret rather than the original Helm `hub` Secret, and the profile wrapper returned registered CPU-only profiles before considering this exact exception. The unused original Secret was restored. GPU1 was used only after the exact notebook image passed CUDA and rendering there. GPU2's native memory-accounting policy rejects an unenrolled ordinary exclusive workload; it was not bypassed. A verified orphan KAI reservation on the unused GPU1 card was removed with exact UID/resourceVersion checks after confirming no referencing workload.

The restoration currently uses a manual immutable configuration overlay. CIT recovery commit `fc3b01d05d72d4039ac2849e4fa2f8c66365942a` provides a bounded CAS repair and runbook; its read-only preflight passed against the actual cluster. It is not unattended Fleet durability. Consolidating the full existing native proof/policy overlay into declarative deployment remains open. Secret-bearing backups are kept outside Git; this directory intentionally records only sanitized acceptance data.

Application patch: https://github.com/mul-cps/cps-compute/pull/3 . No default branch merge or broader release qualification is implied.
