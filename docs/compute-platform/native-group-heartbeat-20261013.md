# Native group acquisition heartbeat fix — 2026-10-13

**Source verification passed; normal group Start acceptance is pending.**
The [source qualification record](native-group-heartbeat-20261013.json) pins
the SDK fix and candidate gateway image. It makes no new hardware,
ordinary-group availability or production qualification claim.

SDK commit `601ecb9b172d6eabcd7bd77e8200e02132d5541f` moves synchronous
native acquisition authority checks and SQLite transactions into worker
threads. Fresh Source, node-document and reservation checks keep their
existing order, including the authorizer inside the reservation transaction.
The async ledger CAS and neutral-owner checks remain in place. No
acknowledgment TTL, readiness cache, profile or GPU configuration was changed.

The preceding SDK revision `bfe20f29d73804966043de30f484d72a6cd7112d`
performed repeated synchronous four-component readiness reads on the gateway
event loop. In the two-member source fixture, initial native acquisition
performed 117 readiness observations and four node-reference observations,
equivalent to 2,420 named Kubernetes GETs with the full reader. This delayed
the acknowledgment heartbeat the acquisition checks depended on. A synthetic
2 ms observation delay and 40 ms acknowledgment lifetime reproduced native
HTTP 422 after a successful generic reservation, with no heartbeat renewal
during the native request. These timings describe the offline regression,
not cluster performance.

The repaired handler passes the same regression with heartbeat renewal and
HTTP 200. An expired proof still produces HTTP 422 without a native ledger
claim. Repeated cancellation retains acquisition ownership until the
reservation worker finishes, preventing shutdown from racing a late commit.
The existing packing race test now uses a bounded two-arrival CAS barrier to
exercise its intended same-revision conflict deterministically.

The complete SDK source suite passed **1,477 tests, with three skips**, as
reported by the release operator. Independent focused verification passed
56 native authority/reservation tests and the packing CAS race test. The
three skips remain unexecuted checks.

The gateway image under acceptance is
`ghcr.io/mul-cps/cps-compute@sha256:88dca37788b0dfda879836066e68a393e941edab18fbf4cbb9d9d970e8808516`.
Normal CPS/CIT Start, automatic finite caps, confirmed Stop and reservation
release must be recorded in a separate live receipt before this note claims
that lifecycle passed. The operator reported acquisition HTTP 200 and Pod
creation, followed by registration HTTP 422; native release and Source close
returned HTTP 409 and remain under investigation. No live receipt has been
reviewed for this attempt, and normal Start is not accepted. Existing
controlled GPU evidence and the broader
[platform acceptance gates](qualification.md) remain separate.
