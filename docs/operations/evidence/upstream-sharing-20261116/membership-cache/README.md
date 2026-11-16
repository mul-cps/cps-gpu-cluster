# Stock notebook authentication cache and membership-removal boundary

**Decision: no authentication cache configuration, application patch, or runtime change is justified by the observed harness gap.** Root confirmed that the authoritative Source remove-member workflow already stops affected Source workspaces and revokes/replaces Shares before deleting provider membership. The failed QA instead directly removed a Hub group member. The correct remaining acceptance test is the real Source/CourseProvider API with already-open kernel/RTC connections. Manual shutdown after a raw Hub group edit is cleanup, not that acceptance test.

This task made no node, Pod, Hub, marker, membership, token, or configuration changes. All executable checks ran offline in a local container of the exact immutable image, with network disabled, read-only root filesystem, no GPU device access and no real credentials. No local test container remains running.

## Exact installed artifact

Image: `ghcr.io/mul-cps/cps-jupyter-notebook@sha256:4a03fe381c6f32f8e056ac05aad27abc64defa2f63128c53511a24d37fb5c194`.

- JupyterHub singleuser package **5.5.2**.
- Jupyter Server **2.17.0**.
- jupyter-collaboration **4.4.2**, jupyter-server-ydoc **2.4.2**.
- Package root `/opt/conda/lib/python3.13/site-packages/jupyterhub`.

`installed-package.json` and `installed-websocket-package.json` record versions and source SHA256 values; `installed-source/` retains the exact inspected source. These are notebook package facts, not a claim about the separately deployed Hub package version.

## Cache finding

The installed `HubAuth.cache_max_age` and inherited `HubOAuth.cache_max_age` default to **300 seconds**. Both Authorization-header and signed OAuth-cookie authentication call `user_for_token`, using a key derived from the session ID and token hash. The cached Hub response includes scopes. A cache hit returns that model without contacting the Hub, so a freshly revoked Hub scope can coexist with a previously authorized notebook HTTP request until the cache expires.

Exact installed source references:

- `installed-source/services/auth.py:470`: configurable default 300 and cache construction at 484.
- `services/auth.py:556`: cache lookup precedes the Hub request; successful/denied responses are cached.
- `services/auth.py:686`: token and session cache key.
- `services/auth.py:804`: header authentication and per-request handler memoization.
- `services/auth.py:1003`: OAuth-cookie tokens use the same `user_for_token` path.
- `singleuser/extension.py:158`: identity provider checks access scopes from that returned model.

**Zero is not “disable cache.”** `_ExpiringDict` explicitly defines zero as cache forever; expiration only runs when max_age is positive (`services/auth.py:108`, `:152`). Negative values likewise do not provide a useful disabled-cache mode in this implementation. `cookie_cache_max_age` is the deprecated alias, not a separate cookie-only revocation control.

A supported small positive configuration exists, if a separate operational requirement later warrants it:

```python
c.HubOAuth.cache_max_age = 1
```

or the singleuser command-line argument `--HubOAuth.cache_max_age=1`. The inherited `c.HubAuth.cache_max_age = 1` also works. The setting must reach the **singleuser process**, not merely the Hub application. No dedicated `JUPYTERHUB_AUTH_CACHE_MAX_AGE` environment mapping exists in the installed auth/singleuser implementation; an offline test confirms that invented variable leaves the default at 300. A deliberate spawner argument or administrator-owned Jupyter config would be required. No such change was made or proposed for rollout.

`check_installed_cache.py` and `installed-cache-proof.json` demonstrate on the installed package: default-300 cached allow followed by expiration; positive-1 cached allow followed by fresh removed scopes; zero remaining cached; nested identity-provider config propagation; and actual ServerApp CLI parsing into the nested HubOAuth cache. The test uses a fake Hub response and mocked monotonic clock, so it establishes package semantics, not live revocation latency. A full offline CLI launch could not finish without a Hub; that diagnostic is retained in `full-cli-launch-offline-hub-unavailable.stderr`, and is not counted as a successful launch test.

For new HTTP requests or new WebSocket handshakes, a positive age would bound cached authorization by approximately that age after the last cached response, plus concurrent/in-flight request and network timing. It would not establish an absolute one-second guarantee for already admitted work. Cache age also does not control the browser cookie's separate lifetime.

## Existing WebSockets are a separate boundary

In the exact installed kernel handler, `pre_get` checks authorization (`jupyter_server/services/kernels/websocket.py:36`), but `on_message` forwards messages to the existing kernel connection without another Hub request (`:77`). In RTC, `jupyter_server_ydoc/handlers.py:229` authenticates/authorizes the WebSocket GET; `:352` handles subsequent document/save messages without revalidating Hub membership. The Hub identity provider also memoizes the user on the handler.

Therefore, reducing cache lifetime alone cannot guarantee removal of **active** access on an already-open kernel or RTC socket. A fresh notebook HTTP 403 is insufficient proof. WebSocket ping/idle settings do not establish membership revocation. Root's existing authoritative Source stop-before-delete lifecycle supplies the required connection teardown without modifying authentication internals.

## Token deletion and supported lifecycle

Installed `apihandlers/users.py:594` deletes the selected token in the Hub database; for OAuth tokens it deletes all of that user's tokens issued by the same OAuth client (`:600–613`). It has no notebook cache invalidation or open-socket notification. Both cookie and header callers can therefore retain a previously cached model until expiry, and existing sockets remain an independent issue. Blanket personal-token revocation would also have broader scope than removing one Source membership and is not recommended here.

The installed group-membership DELETE (`apihandlers/groups.py:177`) removes the group relation and commits; it does not stop singleuser servers. Shares deletion similarly modifies Hub DB state. These raw administrative operations are not equivalent to the application-level Source remove-member contract.

The inspected notebook package's stock `User.stop` implementation (`user.py:1093`) awaits spawner stop and, **when `will_resume` is false**, deletes the server API token and OAuth client (`:1117–1129`), then runs post-stop cleanup/clears spawner state. Spawn normally creates a new API token (`:851`) and registers the OAuth client (`:877`). A token-reuse branch exists (`:952`), so the independently deployed Hub version and actual spawner `will_resume`/reuse behavior must be checked before treating credential rotation as a deployed fact. This finding was handed to the lifecycle reviewer; it does not expand this task into another Hub implementation review.

## Required real acceptance gate

1. Through the supported Source/CourseProvider workflow, establish a shared workspace and member access. Retain exact Source/member/workspace IDs, Pod UID, route and custody binding; keep a member's existing kernel and RTC WebSocket open.
2. Remove that member through the **authoritative application API**, retaining the request outcome and timing. Do not substitute a raw Hub group edit or a later manual stop.
3. Confirm that the workflow itself completes the expected stop/route cleanup, closes existing sockets, and prevents further kernel execution/document updates through those sockets. A stopped route alone is not enough unless attributable to that API's enforced lifecycle.
4. Confirm the remaining authorized membership can restart/access the retained files, while the removed member's old header token, OAuth cookie, new connection and old socket cannot access the restarted workspace. Preserve CPU/storage behavior, canonical identity, reservation custody, and original native `9d` behavior.
5. If the lifecycle remains asynchronous, retain the exact pending/completed state and measured stop/closure bound; do not declare revocation complete merely because a request was accepted.

Root keeps GPU2 acceptance/GPU3 nomination gated on that real workflow result. The raw-Hub administrative bypass findings above are documented stock limits, not a new blocker for a correctly completed Source removal flow.

## Primary upstream references and released behavior

- [JupyterHub OAuth cache layers](https://jupyterhub.readthedocs.io/en/stable/explanation/oauth.html#token-caches-and-expiry) documents the separate singleuser response cache and browser-token cookie lifetime.
- [Installed-release auth source](https://github.com/jupyterhub/jupyterhub/blob/5.5.2/jupyterhub/services/auth.py) matches the inspected cache semantics.
- [JupyterHub changelog](https://jupyterhub.readthedocs.io/en/stable/reference/changelog.html) lists 6.2.0 and 5.5.5, both released 2026-11-05. No release change resolving this raw administrative bypass was identified; [6.2.0 auth source](https://github.com/jupyterhub/jupyterhub/blob/6.2.0/jupyterhub/services/auth.py) still has the same default cache and zero-as-forever behavior. No package upgrade is proposed as this issue's remedy.
- [Jupyter Server 2.17 kernel WebSocket](https://github.com/jupyter-server/jupyter_server/blob/v2.17.0/jupyter_server/services/kernels/websocket.py) shows handshake authorization and later message forwarding.

The GitHub Releases API returned no releases/404 during this check; current released versions above come from the official versioned documentation/changelog, not an inferred API result.


The independent lifecycle reviewer traced the deployed console image `ghcr.io/mul-cps/e2x-course-hub@sha256:b6856fa9c0ac1ddd42541c5bb629ee31ff8a5fd7420cd152548d6fdc8edde7b7`: `e2x_course_hub/cps/workspaces.py:545–589` contains the removal barrier (566), stop/release (573–576), alias removal (578), Shares replacement (580), then provider membership deletion (582). `platform_handlers.py:105–120` implements the handler; route registration at 239 is `/api/workspaces/<id>/remove-member`, with `membership_id` in the request body. These are independently supplied installed-source findings; this cache task did not re-run that review. The accompanying preparation report is `.superpowers/sdd/upstream-sharing/source-provider-authoritative-qa-preparation.md`. The 15-second Source watcher only observes already-stopped Hub state and is not a substitute for the remove-member API's stop-before-delete ordering.
