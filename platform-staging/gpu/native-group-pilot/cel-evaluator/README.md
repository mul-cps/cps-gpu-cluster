# Offline CEL comparison aid

This local executable evaluates policy expressions with official cel-go v0.29.0
and `ext.Strings()`; it has no Kubernetes, network, credential or GPU client.
It is **not equivalent to K3s1.34 admission**: it uses dynamic bindings rather
than Kubernetes schema/type-checking, authorizer or Kubernetes CEL libraries.
Actual server dry-run and isolated admission tests remain required.

Go1.26.8 and the nine-module compiled closure are pinned from the cached official
KAI `bdf434e5e9201cccf4e05fad04d814363653f692` module graph (whose apiserver pin
is v0.35.4). This helper does not import apiserver. No KAI module/dependency copy
or new custom CEL functions are included. The official Go Linux AMD64 archive
SHA256 is `d0f743b33e8d8945e6b1f432edd15785c70507121d6e2a723b21285eddf8b57b`.
The small `go.sum` pins all nine compiled modules and their module metadata.

With the pinned toolchain and modules already cached, from this directory:

```sh
export GOMAXPROCS=4 GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off GOFLAGS=-mod=readonly
/absolute/pinned/go1.26.8/bin/go test -count=1 -p 2 .
CGO_ENABLED=0 /absolute/pinned/go1.26.8/bin/go build -p 2 -trimpath \
  -buildvcs=false -ldflags=-buildid= -o /private/output/cel-evaluate .
export CPS_NATIVE_PENDING_CEL_EVALUATOR=/private/output/cel-evaluate
"$CPS_NATIVE_PENDING_CEL_EVALUATOR" < /private/policy-input.json
```

Input is one JSON object:

```json
{"policy":{"spec":{"variables":[{"name":"name","expression":"object.metadata.name"}],"matchConditions":[{"name":"create","expression":"request.operation == 'CREATE'"}],"validations":[{"expression":"variables.name.startsWith('cps-')"}]}},"inputs":{"request":{"operation":"CREATE"},"object":{"metadata":{"name":"cps-example"}},"oldObject":null,"params":null}}
```

VAP metadata, messages and unrelated policy fields are ignored. Only the four
listed input bindings are accepted; omitted bindings become null. JSON integers
are converted to CEL int64 without float rounding. Variables are evaluated in
order, with earlier values exposed through `variables`. Conditions and
validations must return actual CEL bool values. Compilation/evaluation errors
remain explicit, and never become truthy strings.

Output includes `compiled`, `evaluated`, `matched`, `allExpressionsTrue`,
`decision`, and separate `variables`, `matchConditions`, `results` arrays.
Each row records its expression, compilation/evaluation status, optional error,
and nullable boolean value. Variables may return arbitrary CEL values, which
are not serialized back into the output. Variables are evaluated eagerly in
sequence, unlike Kubernetes lazy variable evaluation: even an unused variable
error stops this helper. Its error/short-circuit behavior therefore must not be
treated as exact API-server behavior. Require `matched == true`,
`compiled == true`, `evaluated == true` and `allExpressionsTrue == true` for an
offline validation pass. A false match condition returns `decision: not-matched`,
`matched: false`, `allExpressionsTrue: null` and skips validations, even when
another condition has an evaluation error. This must not be counted as a denial.
An expression error returns `decision: error`; a false validation returns `deny`.
Malformed top-level input exits2 with a JSON error; ordinary expression outcomes
exit0 and must be assessed from the explicit result fields.

Bounds:4MiB input,64variables,64conditions,1–256validations,1–32768bytes per
expression and CEL runtime cost limit1000000 per expression. No extra functions,
policy writes, retries or authority bypasses are provided. Tests cover official
substring/has/map/startsWith/regex behavior, sequential variables, integer
comparison, nonboolean and malformed expressions, matching skip/error behavior,
and input size refusal.

The admission policy CPU matrix requires this executable explicitly; no fallback
or skipped evaluator is accepted. From the cluster repository root:

```sh
CPS_NATIVE_PENDING_CEL_EVALUATOR=/private/output/cel-evaluate \
  python3 -B -m unittest discover -s platform-staging/gpu/native-group-pilot -p 'test_native_pending_admission.py'
```

The test file must be present in the reviewed admission checkout. These CPU
comparisons supplement, rather than replace, actual Kubernetes compilation and
admission qualification.
