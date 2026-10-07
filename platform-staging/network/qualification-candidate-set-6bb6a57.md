# Partial qualification candidate set — 2026-10-07

The adjacent JSON cross-checks all twelve published gateway/admin/CPU/GPU notebook candidates against compute source 6bb6a57 and wheel SHA-256 `05d82345b0f65a3a94c715c68788f52d14c545cba41a5e622249870e0e848667`. Every image index and Linux manifest is pinned and remotely verified. Package version 0.1.0 alone is insufficient to establish identical content; the wheel checksum is the common input identity.

The recorded production Deployment snapshot shows: the gateway remains on 5771df5 and both consoles on the combined 0ef266b candidate. The new images have not been deployed. The compatibility baseline remains Hub 5.5.2 / chart 4.4.2 / KubeSpawner 7.x. The central release lock is unqualified with no qualified compatibility entries.

Two remaining notebook variants, common source-tag construction, authenticated integration of the new packaged artifacts and the remaining acceptance/migration gates are incomplete. GPU sharing stays unqualified. This file is a partial inventory, not a promotion lock; productionPromotionAllowed is false. Individual evidence reports retain their exact verification scope.
