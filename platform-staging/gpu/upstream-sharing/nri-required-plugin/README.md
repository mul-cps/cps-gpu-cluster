# Required-plugin timeout backport: review candidate

This directory contains a **derived K3s v1.34.9+k3s1 review candidate**, not a
released upstream binary and not an installed runtime. No publication,
Rancher ownership change, version-target change, or cluster mutation is part
of this build.

## Source boundary

- K3s tag `v1.34.9+k3s1`: `5f72184f2d188f75171bbd21953b1c16268e425f`.
- Its existing `github.com/containerd/nri v0.12.0` dependency remains unchanged.
- The only production source change is `0001-required-plugin-presence.patch`,
  the `pkg/adaptation/adaptation.go` hunk from upstream author commit
  [`9cb8bc1fee03ebd41d90319240c2493fb03411b9`](https://github.com/containerd/nri/commit/9cb8bc1fee03ebd41d90319240c2493fb03411b9).
- Fractioning v0.1.9, its NRI dependency, and all dependency versions remain
  unchanged. No FailurePolicy dependency upgrade is included.

The validator records required-plugin presence after the callback only while
the plugin remains connected. A timeout/disconnection that drops a required
plugin therefore rejects the first request. Healthy nil adjustments and
registered plugins unsubscribed from CreateContainer retain their behavior.
CPU containers without a required-plugin annotation retain fail-open behavior.

## Retained regression evidence

`required_plugin_regression_test.go` runs inside the existing NRI v0.12.0
adaptation suite. Its mocked business callback uses real Unix sockets, real
stub registration, ttrpc deadlines/disconnects, and the built-in default
validator. It checks the first CreateContainer call, not a later retry.

Copy the fixture into `pkg/adaptation/cps_required_plugin_test.go` of the
unpatched v0.12.0 source and run:

```sh
go test -p 8 ./pkg/adaptation -run TestRuntime -ginkgo.focus='CPS required plugin' -count=1
```

`evidence/red.log`: three expected failures (required first timeout, callback
disconnect, and already-disconnected plugin); seven compatibility controls
passed. Apply the patch with `patch -p1`, then repeat the command:
`evidence/green.log` passes all ten cases. `evidence/full-suite.log` retains
`go test -p 8 -v ./... -count=1`: all packages pass, including 132 adaptation
specs. Infrastructure quota failures are retained separately and are not
counted as RED behavior.

## Packaging boundary

The official outer binary SHA256 is
`80eebb578e36a04ca460575fab419a3336b32c84205a0ae954ff16636181d9f7`.
Its embedded archive SHA256 is
`65415f7708224bbfc7865f032e84da4a5123a3acebef70c8ee40fa991aa68555`.
The former matches the installed GPU2 outer binary by a read-only SHA query.

`extract_payload.py` locates the exact SHA-matched embedded zstd frame and
extracts it without running the outer binary. All ancillary binaries/assets
come from that official payload. Both downloaded chart archives and every
source manifest were checked byte-for-byte against the official inner binary.

The isolated tagged source is vendored without changing go.mod/go.sum, then
the tested production patch is applied to its vendored NRI source. The
patched file is byte-identical to the file exercised by the regression suite.

`Containerfile` pins the official Go 1.25.11 Alpine 3.23 compiler distribution.
`build-in-container.sh` rebuilds only the inner binary using its official
tags/linker metadata, then runs the tag's unchanged `scripts/package-cli`.
The nominal version remains unchanged; this README and the artifact provenance
identify the derived build. Alpine package versions are retained separately;
the rebuilt inner is not claimed bit-identical to the official compiler run.
The container receives no host credentials, and AWS upload variables are
explicitly unset before official packaging invokes its no-upload path.

Official packaging regenerates `.sha256sums`, `.links`, the embedded archive
content hash/name, and the outer binary. This matters because K3s extraction
selects its data directory by **embedded archive basename**, not outer SHA.
`verify_payload.py` checks a fresh extraction: only `bin/k3s` and its checksum
record may differ; every ancillary asset and symlink must match stock.

Cluster qualification of the built artifact, including real NRI fault cases
and CPS/CIT lifecycles, remains a separate gate before any promotion.

## Built candidate and verification

Artifact: `/var/tmp/cps-nri-required-20261116/k3s/dist/artifacts/k3s`.

| Identity | SHA256 |
| --- | --- |
| Outer artifact | `6ce276301723a902da671058730611591c59b5f016b816f57f2d97b05c88fe2c` |
| Embedded archive / new data-directory identity | `2277a2c458beda093f8367b944c2fbb2e5f53a00f17776759721fb781b3874fa` |
| Rebuilt inner binary | `0ca3be05fd3fcdd9682e68bbff5821ea15027773404a7e47517b822bcb57387a` |

`evidence/payload-verification.json` confirms 375 inventory entries, with only
`bin/k3s` and `bin/.sha256sums` changed. Every recorded file checksum and link
target validates. `evidence/buildinfo-verification.json` confirms all 495
module-version records and every build-setting record match stock. The
vendored Go build intentionally omits upstream module checksum attestations
from its binary metadata; `evidence/provenance.json`, the unchanged go.sum, and the
retained exact source diff identify the derivative instead.

The built outer's local `--version` returns `v1.34.9+k3s1 (5f72184f)` and
`go1.25.11`. This command does not start a service. The build log confirms
official `build-upload` exited because credentials were absent.

For this prepared source/cache layout, the exact build command is retained
in `evidence/build-command.txt`. It builds a local image from `Containerfile`
and mounts only isolated source/cache, read-only stock assets, and this
qualification directory. Local Podman uses `label=disable` for this build
container to read the bind mounts; no host SELinux policy was changed, and
this setting is not a runtime deployment setting.

## Artifact distribution

`Artifact.Dockerfile` packages the approved outer binary and build provenance
in a scratch image. `SOURCE_REVISION` must be the committed repository revision
containing this policy and recipe. The immutable image labels identify that
revision, the upstream tag/commit/patch, and all three artifact hashes. It is
an artifact carrier, not a running service image. Publication does not authorize
installation or change the pending qualification status.

Published candidate:
`ghcr.io/mul-cps/cps-k3s-nri-required-plugin@sha256:1e79df5dd8d75db5407a4b3b8c62d3cce1f099fe137dfc88339f4ffdb733b456`
(tag `1.34.9-k3s1-nri-required-v1`). Its source revision is
`39c5baeb1dc6bf2c9c617d8c9e5c7102d5d0a017`. A fresh registry download verified
the manifest and layer digests, all labels, the approved outer SHA256, and the
embedded provenance record; see `evidence/publication.json`. The scratch image
contains `/k3s` and `/provenance.json`. The latter is the immutable pre-publication
build record; the publication record separately records distribution status.
No runtime installation has been performed by this artifact task.
