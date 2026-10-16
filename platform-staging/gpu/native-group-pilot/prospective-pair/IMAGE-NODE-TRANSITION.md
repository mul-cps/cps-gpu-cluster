# Actual Node8c image-backed transition

The deployed Node8c process reads `/opt/native/node_agent.py` and its flat epoch
helper from image8c. There is no pre-existing code ConfigMap volume. The older
code-volume inverse remains available for its separate synthetic/legacy shape;
it cannot be applied to this deployment.

`image_node_transition.forward_intent` verifies original image/entrypoint,
actual immutable configuration, exact original Node/epoch source bytes and the
independent Root pair contract. It validates the generated typed configuration
and retains the original physical epoch. It adds one immutable code ConfigMap
and two read-only subPath mounts for the generated Node and epoch helper. All
other source/runtime files still come from the original image. Image, privileges,
namespace, resources, host paths, service account and unrelated spec fields are
preserved. The existing configuration reference changes to the exact operator
pair. Four exact dynamic-approval bootstrap argument pairs are removed because
the temporary operator mode must not initialize the group registry. Existing
bootstrap mounts are retained unchanged for restoration. The code ConfigMap
volume explicitly sets0644, matching the API's server default.

`inverse_intent` validates exact actual created code/config objects and the
complete current Deployment spec. It invokes the existing full terminal-custody
validator for zero/one/two completed qualification lifetimes. A zero-lifetime
rollback returns the entire original spec, including image-backed code. After
one or two lifetimes the generated files remain available to interpret their
new historical references; the original group bootstrap arguments return and
the restored full-history configuration is selected. No source/config data is
silently repaired or released. All patches use actual UID/resourceVersion/full
spec compare-and-swap tests.

17 tests cover forward preservation and all three inverse phases, plus changed
image/source/epoch/command/configuration/overlapping mount/bootstrap shape,
changed actual deployment/code/configuration/UID and still-running workload.
Actual image files were read and matched the frozen pins. Both ConfigMap creates
and the full Deployment patch passed Kubernetes server dry-run, including exact
API spec readback. Server dry-run is not deployment or runtime qualification.

The generated overlay is a bounded pilot artifact. A production release still
requires a released Node source/image matrix and actual current-image GPU gates.
No live transition, driver change, MIG operation or GPU qualification is claimed.
