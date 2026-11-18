# Native JupyterHub Home discovery

JupyterHub5.5.2 has native direct/group Shares and a self-scoped
`GET /hub/api/users/<self>/shared` endpoint, but its standard Home template lists
only personal servers. The selected implementation extends `templates/home.html`
with `super()` and displays the existing native Share results. No custom Source
access API, new grant, scope, reservation store, handler or image is selected.
The unpublished Source Open API/Overview candidates remain preserved separately.

Current card template SHA256: `9ff1637259afbbad79c789e9e6a0cf6754df9b7f43cd90b41c8d258978a237d9`.
Nine functional tests and 36 responsive/theme cases passed for the card successor.
Eight local Chrome/Jinja tests passed, covering inherited personal controls,
direct/group shares, exact access scopes, ready-only Open, unsafe URLs, XSS,
duplicate readiness, empty expired pagination, errors and narrow layouts.
Group names are native labels; Source workspace titles are not in this API.

The first release mounted the template but configured its search path only in
the newly generated chart Secret. The reviewed Pod templates actually load
existing pinned runtime Secrets, so the user's screenshot correctly showed no
new section. Mounted bytes and healthy rollout did not establish active rendering.

The correction uses the standard chart `config.d` loader through a second
`hub.extraFiles` entry. Its one-line configuration has SHA256
`f430ed6a5700061a1570c77094003c81586136953197d4d302e5495d2df7ed87`.
Both actual startup logs confirm it loaded. CPS393/CIT328 are Ready with the
exact files and reviewed Pod templates; existing runtime Secrets remain pinned.
Current source owners are CPS `e8d05376cce4fc9ff7ed8857ba7134ade9f855a9`
(includes the personal CPU form/reset, permitted network-mount defaults and pinned CPU pre-puller) and CIT
`f7689464be40b42e74f501367ba04ce3305f42f7`.

[Preservation](configd-preservation.safe.json) confirms the original running
notebook Pod/container, stable access/workspace-account tables, referenced
resource identities and existing crypto keys. [Runtime proof](configd-runtime.safe.json)
binds installed files and actual configuration loading. **The user confirmed the first native shared list appeared.** The styled card
successor is deployed; its genuine Open-click acceptance remains unverified. Browser automation's
documented DOM/screenshot/CDP interfaces currently fail; no cookie fabrication,
authentication-state edit or substitute UI API token was used. Home is cookie-only.

Private execution evidence and eight-test candidate are retained under
`/home/bjoern/artifacts/cps-upstream-sharing-20261116/hub-home-native-rollout-20261118`
and `hub-home-shared-workspaces-readonly-20261118/candidate`.
