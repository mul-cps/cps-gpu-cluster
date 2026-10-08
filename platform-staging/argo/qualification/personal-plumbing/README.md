# Personal Argo live plumbing qualification

This is supporting live evidence for chart plumbing, not production activation
or human browser authorization qualification. Resources are confined to
`cps-personal-argo-qualification-20261008`; its frontend has no public ingress.
The rendered token-rotator CronJob remains suspended.

`run.py` renders only `argo-ui-reader.yaml` and `personal-argo.yaml`. It overrides
the namespace, reader ServiceAccount, and reader Secret with generated scratch
identities. OAuth/cookie secrets are generated independently and applied directly
from process memory. The only copied trust data is the public compute CA from its
ConfigMap. An operator separately provisioned the scratch image pull Secret;
the harness consumes its reference and never reads its data.

The bounded CPU runner executes the chart's rotator script, authenticates the
issued reader token against one scratch ConfigMap, verifies both updates through
the mounted Secret, and checks actual in-cluster denials for an extra reader
TokenRequest, extra Secret GET/PATCH, and target Secret GET. Limits are 1 CPU and
512 MiB, with a 300-second Job deadline. No GPUs, production databases, or
production application credentials are accessed. Reader JWTs are held only in
process memory and the scratch Secret/projection; logs and artifacts contain
only sanitized outcomes.

The original `8a05bc8` chart failed in the released image because
`kubernetes.client.V1TokenRequest` does not exist. Root corrected the chart to
send the TokenRequest API dictionary. The final run rerenders the corrected root
chart and executes its script unchanged. The observed template SHA256 is saved
in `observed.json`. Initial private-image pull failures and the corrected chart
failure are retained as history; they are not final gate failures.

The optional frontend check validates startup, compute/system CA parsing, and
unauthenticated fail-closed redirects for the page and an API path. Its generated
OAuth credential is **not registered** on a Hub. Public HTTPS Hub/native endpoints
use system CA verification; native Argo serves its `/argo/` base href. No compute
API request, Hub role/client change, ingress change, or existing namespace
NetworkPolicy change is made. This does not prove real login, ownership privacy,
callback replay defense, downloads, SSE, or browser interaction.

Fresh run (requires a fresh namespace and independently provisioned scratch pull
Secret reference):

```sh
python -B platform-staging/argo/qualification/personal-plumbing/run.py \
  --pull-secret cps-compute-image-pull
```

To qualify a corrected chart from another source worktree, recreate only this
owned runner and rerender only its reader objects:

```sh
python -B platform-staging/argo/qualification/personal-plumbing/run.py \
  --retry --pull-secret cps-compute-image-pull --chart-source-root /path/to/source
```

Observe without reading Secrets; the optional frontend probe uses this local
port-forward:

```sh
kubectl -n cps-personal-argo-qualification-20261008 port-forward svc/cps-argo-ui 18080:8080
python -B platform-staging/argo/qualification/personal-plumbing/observe.py
```

No production or dynamic-sharing flags are activated by this harness. Remove
the scratch namespace when its review is complete; no production cleanup is
required.
