#!/bin/bash
set -euo pipefail
# Mount isolated tagged K3s checkout at /src, stock extracted bin/etc at /stock,
# and this directory at /qualification. Source vendor must carry only the patch.
cd /src
test "$(go version)" = 'go version go1.25.11 linux/amd64'
test "$(git rev-parse HEAD)" = 5f72184f2d188f75171bbd21953b1c16268e425f
git diff --exit-code -- go.mod go.sum
cp -a /stock/bin /stock/etc .
cp -a manifests/. pkg/deploy/embed/
cp -a build/static/. pkg/static/embed/
export CGO_ENABLED=1
export CGO_CFLAGS='-DSQLITE_ENABLE_DBSTAT_VTAB=1 -DSQLITE_USE_ALLOCA=1'
export GOFLAGS='-mod=vendor -p=8'
export GOTOOLCHAIN=local
# Extract verbatim build settings from the SHA-verified official binary.
# The quoted linker value uses Go's normal quoted-string representation;
# its contents here contain no escaped quotes or backslashes.
stock_info=/qualification/evidence/stock-inner-buildinfo.txt
ldflags=$(sed -n 's/^\tbuild\t-ldflags="\(.*\)"$/\1/p' "$stock_info")
tags=$(sed -n 's/^\tbuild\t-tags=//p' "$stock_info")
test -n "$ldflags"
test -n "$tags"
go build -buildvcs=false -gcflags all= -tags "$tags" -ldflags "$ldflags" -o bin/k3s ./cmd/server
go version -m bin/k3s > /qualification/evidence/candidate-inner-buildinfo.txt
apk info -v > /qualification/evidence/builder-apk-packages.txt
export NO_DAPPER=true GIT_TAG=v1.34.9+k3s1 COMMIT=5f72184f2d188f75171bbd21953b1c16268e425f TREE_STATE=clean
# Official packaging invokes build-upload; its explicit no-credentials path
# exits without uploading. The container receives no host credentials.
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
./scripts/package-cli
sha256sum bin/k3s dist/artifacts/k3s build/data/*.tar.zst
