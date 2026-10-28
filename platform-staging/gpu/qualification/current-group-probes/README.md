# Current second-card qualification bundle wrapper

`prepare.py` is a default-inert, offline-only wrapper around the existing
`native-second-card/prepare.py` source generator. It pins that generator's exact
SHA256 (`971aff6b1eb1c266f7f96ebde34eae09d522740bcb13ab3e848921ec4169fa6d`),
checks bounded raw JSON inputs and their independently supplied hashes, and
passes private immutable input copies to the pinned producer. The producer
performs its own exact source-preimage checks and renders the two 5/10 GiB QA
Pod proposals, immutable gate source, controller and its SDK bundle, observer,
preflight, probes, and all six gate-family runners. The wrapper verifies the
result is still `offline-prepared-not-executed`, launch is unauthorized, every
family is unrun with no receipts, and the generated-source hashes match.

No command in this directory calls Kubernetes, Source, a GPU, or a hardware
runner. `--approve-qa-hostpaths` acknowledges that the *proposed source bundle*
contains narrow QA hostPath proposals; it does not authorize deployment. A
separate operator must acquire current observations, review the exact generated
bundle and runtime policy, and authorize any execution using the existing
qualification workflow. Historical receipts are never imported as current
measurements.

## Offline preparation

Inputs must be newly captured current facts in the formats documented by
[`native-second-card/README.md`](../native-second-card/README.md): observations
contain the actual Node, dedicated fresh namespace, independent device and
NativeNode guard captures, fresh cohort UUID, current reviewed QA policy hash,
and observed CDI provider bytes; the request binds the exact 5/10 pair, same
cohort/policy, namespace/UID, and immutable gate image. Observe and review those
values independently before generating these raw-byte hash pins:

```sh
sha256sum CURRENT.json REQUEST.json
```

Then prepare into a new, private output directory:

```sh
python3 -I -B platform-staging/gpu/qualification/current-group-probes/prepare.py \
  --prepare \
  --observations CURRENT.json --observations-sha256 CURRENT_RAW_SHA256 \
  --inputs REQUEST.json --inputs-sha256 REQUEST_RAW_SHA256 \
  --output NEW_PRIVATE_BUNDLE --approve-qa-hostpaths
```

The wrapper defaults to an inert JSON response. The explicit `--prepare` path
only delegates local source construction. The output must remain unqualified
and unlaunched; there is no live mode in this wrapper. For full output contract,
source closure, and separately authorized operator procedure, follow the
pinned [`native-second-card/README.md`](../native-second-card/README.md).

## Offline verification

```sh
python3 -m pytest -q platform-staging/gpu/qualification/current-group-probes/test_current_group_probes.py
python3 -m pytest -q platform-staging/gpu/qualification/native-second-card/test_prepare.py
```

The integration test uses the native-second-card unit-test fixture and its
synthetic API-object render/finalize contract. It makes no API or hardware
calls and does not assert real admission, device availability, measurement, or
qualification.

## Recovered evidence inventory

`review_actual_gpu2.py` reads retained second-card artifacts offline and reports
bounded measured assertions, their input hashes, and explicit gaps. It does not
promote hardware or production qualification. Its `measured_pass` entries are
an evidence inventory for operator review, not a substitute for inspecting raw
traces or establishing complete gate coverage. Missing cross-parent IPC must
not be inferred from same-parent IPC or cross-parent VMM results. The original
restart runner's failed postflight is retained in the report; independent
pre/post snapshots provide a separate, narrower restart comparison.

Run `python3 review_actual_gpu2.py --help` for explicit private input paths and
`python3 -m pytest -q test_review_actual_gpu2.py` for the focused reviewer tests.
