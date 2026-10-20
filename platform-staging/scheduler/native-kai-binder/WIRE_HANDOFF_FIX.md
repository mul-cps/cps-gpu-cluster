# Kubernetes Binding handoff qualification

The normal shared-workspace attempt on 2026-10-20 passed coordinator preparation and Binding validation, but never sent the Kubernetes Binding request. A real controller-runtime HTTP regression reproduced the error: a typed Pod parent selected protobuf, which cannot encode the unstructured closed Binding body.

The patched call uses the same authenticated Pod namespace, name, UID and resource version through an unstructured Pod parent, selecting JSON. The API receives a copy of the approved Binding, preserving that exact request for the accepted callback when the response is decoded as a Kubernetes Status. No unknown result is retried.

`native_binding_http_test.go` uses the actual controller-runtime client and an HTTP server. It checks the exact request path, JSON body, successful acknowledgement, forbidden and lost responses, a single request, unchanged input Pod and retained custody on failure. The five affected Go packages and two identical static binary builds passed in the private development packet. The canonical recipe separately verifies the pinned upstream source, toolchain archive and all seventeen changed paths.

Status: offline candidate; live GPU startup and isolation qualification remain required. Earlier verification receipts in this directory describe the preceding candidate. The source manifest and recipe identify this candidate; a successful build receipt is required before OCI packaging.
