# Full inventory reconciliation with explicit retained defaults

The selected device contains retained inventory rows without protected workflow
journals. Twelve such rows were unchanged between actual 15 October21:07 and
16 October11:13 captures in the same driver/boot epoch. Their exact observed
body is offline/pinned/default-hierarchy, used0, soft0, hardUINT64_MAX. Their
origin remains unattributed; they are not authenticated workflow cleanup.

`physical_inventory.physical_observation` reconciles every current inventory row
against typed workflow retirement or an independently raw-hash-pinned baseline.
The baseline is bounded32, binds the exact device/boot/driver/node epoch and the
original complete capture hash, and contains complete original row bodies.
Retained defaults cannot overlap any journal identity, stand in for finite
workflow caps, change, become charged/active or grow. Every finite retirement and
the existing distinct authenticated recovery still pass the original typed
history/physical validators unchanged. Any additional unknown row fails.
The complete inventory, including retained defaults, is hashed into the physical
observation. This does not change admission, cap assignment, cleanup, drivers,
Node configuration or the original strict validator.

13 tests pass, including changed pin/epoch, charged/active/unpinned defaults,
finite default substitution, unknown extra/missing rows, changed/missing finite
retirement, duplicate identities and forged retirement identity. The actual saved
pre-stop capture was rejected for its one active entry. The actual post-stop
capture reconciled65 finite retirements, one authenticated recovery and12 exact
retained defaults, with zero active entries and zero charge. No fake positive
capture was substituted for that device observation.

The normal Source Stop initially returned409 while cleanup completed; Pod removal
and native cleanup were observed independently. Readback showed Source stopping
and reservations already inactive. Only after confirming that state was Stop
retried; it returned200/stopped. Both temporary tokens were revoked. All four
personal-server Pod UIDs in the pre-operation baseline survived. The native ledger
then contained86 released claims. No direct cap reset, forced reservation release,
MIG, driver restart, filesystem deletion or handover was performed.

The Root-private observer must supply the actual device observation timestamp;
the pure reconciler cannot establish transport authenticity or freshness. The
Source callback checks freshness after full custody replay. Every subsequent
handover requires a newly collected complete custody set. The result is release
baseline evidence, not notebook531 isolation qualification or production approval.
