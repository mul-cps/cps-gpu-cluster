# Automatic Source state convergence after Hub shutdown — 23 October 2026

The real idle-expiry run stopped the Hub server and released native/member
reservations, but the Source record remained running. This prevented an ordinary
subsequent Start until a manual Stop reconciled the record.

The packaged console now starts a non-overlapping 15-second lifecycle observer
from CourseServiceApp.start (not from configuration loading or test clients).
Only running, non-archiving records are considered. Under the existing course
and workspace locks, it observes Hub absence and an explicit inactive reservation
binding. It then reuses the normal release endpoint's fresh Hub/Pod/native cleanup
checks, checks stopped/inactive state again, and conditionally persists stopped
against the original Source lifecycle snapshot. Active/unknown bindings, missing
telemetry, concurrent edits and pending cleanup retain the record. No lease age
or Pod absence alone clears capacity. Each item has a bounded observation budget;
failures do not block unrelated workspace observations or expose private errors.

The exact two-module package change preserves 105 other distributions and all
frontend assets. 79 lifecycle tests and 72 subtests pass, including real app
startup wiring, concurrent edits, new reservations and fail-closed cleanup.
Both consoles run the immutable image recorded in verification.json.

Before deployment the actual expired shared-gpu-lab record was running with no
active reservation. After deployment the server's own periodic callback changed
it to stopped and persisted a successful system:hub-lifecycle audit. Observation
used read-only clients; no manual Stop, reconciler invocation or record edit was
used to create this result. Subsequent restart/stop evidence is recorded separately
in verification.json. This is not a new claim of hard-maximum expiry or visual
browser warning acceptance. GitOps integration and production promotion remain open.
