# Source console compute consumer — candidate, not deployed

The deployed Source51f compute dependency rejects notebook531 operator
qualification. This candidate installs the exact reviewed Core wheel from
compute commit `de90610f3250a14cb5e3a33473afe547797358a0` with offline pip over
Source51f. It preserves application/frontend files, dependencies, runtime
configuration and the original image user. It does not modify the live consoles.

Published image:
`ghcr.io/mul-cps/e2x-course-hub@sha256:dbaad51899ccb634f5a07c44bd9f7022dbca71724d7cfd66e5d67abf9d569ace`.
See [receipt.json](receipt.json) for package preservation and acceptance limits.

## Reproduce the package and model checks

Build the Core wheel from the exact compute commit with its existing Hatchling
build backend. The wheel must be named `cps_compute-0.1.0-py3-none-any.whl` and
have SHA256 `85aa2fdc2aff746f563c6d91f7cedae5b2cfc8f474887301167b7e484e793503`.
Place it beside this Containerfile in a disposable build context; do not commit
the wheel or credentials. Pull the pinned Source51f base, then build with
`podman build --network=none --pull=never -t localhost/source531-candidate .`.

Run the installed model/import checks without mounting application source:

```sh
podman run --rm --network=none --user 10001 --entrypoint python \
  -v "$PWD/qualification-fixture.json:/fixture.json:ro,Z" \
  -v "$PWD/qualify.py:/qualify.py:ro,Z" \
  localhost/source531-candidate -B /qualify.py
```

The synthetic fixture is a pure model test. It supplies no credentials, starts
no workload and establishes no hardware qualification. The old Source51f image
fails this exact fixture with `Exact immutable qualification runtime images
required`; the candidate accepts it while keeping qualification profiles
disabled. Legacy916 and inert defaults remain accepted, while arbitrary images,
oversized budgets and invented passed evidence remain rejected.

Actual qualification also compared all 49 installed Core modules with the
reviewed source/wheel, all 13,959 non-Core files and their ownership/modes, all
106 dependency versions, and the image configuration/base layers. Live course
CRUD, Source capture-trust adoption and GPU hardware tests remain separate gates.
