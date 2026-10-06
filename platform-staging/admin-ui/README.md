# Admin UI qualification rollout

Frontend source: `mul-cps/e2x-course-hub`, branch `feat/admin-ui-redesign`,
revision `240350a4996e48239ea02229adc15e0bb1f94426`.

Immutable image is recorded in `values.yaml`. `Dockerfile.ui` overlays only
compiled frontend assets on the existing deployed backend digest. Both separate
console databases, credentials and policy settings are preserved. This is a
qualification UI update, not a complete compute-platform production release.

Validation: TypeScript/Vite production build, changed-source ESLint, 18 Chromium
fixture tests (course/member creation, grants, manual allocation, approved and
unapproved workspace configuration, member removal, confirmation, audit, errors,
external record protection, keyboard focus, desktop and mobile layouts).
The fixture tests do not prove production authorization or workspace lifecycle.

Apply only the console images over the existing reviewed deployment. Do not run
an upgrade using chart defaults: runtime secrets, policy artifacts and lifecycle
settings belong to the separate platform qualification. These image overrides
remain outside Fleet's watched paths until deliberate promotion.

Rollback both `cps-admin` and `cit-admin` in namespace `cps-compute` to:
`ghcr.io/mul-cps/e2x-course-hub:qualification-fa48334@sha256:89bd173142eb17d898efc78c46438ab474a88a3f3f700996901743f4d7b4eb7e`.
No database rollback is required for this frontend-only change.

Five refinement passes: balanced overview and text contrast; URL-backed course
tabs and full mobile navigation; sortable records and clearer status/dates;
guided forms with interactive-only workspace profiles and policy availability;
keyboard focus, inert dialog background, skip link and mobile overflow fixes.
No GPU policy is enabled by this frontend update.
