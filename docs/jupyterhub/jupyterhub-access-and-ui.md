# JupyterHub GPU Access Control and Dynamic Profile UI

This cluster uses a combination of frontend and backend logic to provide a clean user experience while enforcing strong access control for GPU resources.

## TL;DR
- UI: Static HTML form rendered via `c.Spawner.options_form` with a JavaScript enhancement that adapts to the current user.
- Access detection: Client-side fetch to `/hub/api/user` with XSRF token to check group membership and admin status.
- Validation: `c.KubeSpawner.profile_list` is present so KubeSpawner accepts profile slugs from the form.
- Enforcement: `c.KubeSpawner.pre_spawn_hook` (`apply_profile_settings`) applies the selected profile and blocks GPU access for unauthorized users.
- Known limitation: KubeSpawner does not reliably render callable `options_form`; use a static string + JS instead.

## Why this approach
KubeSpawner 7.0.0 (with JupyterHub 5.4.1) didn’t render asynchronous or synchronous callables for `options_form` reliably, even though the base `Spawner` class supports it. To guarantee a consistent UI, we:

1. Set a static string for `c.Spawner.options_form` (always renders)
2. Use JavaScript to call `/hub/api/user` and detect whether the current user has GPU privileges
3. Hide the GPU profiles and show a CPU-only banner if the user is unauthorized
4. Keep a backend safety net (`pre_spawn_hook`) that blocks unauthorized GPU profiles regardless of the UI state

This model provides a robust UX and security:
- Everyone sees a modern, consistent form
- Authorized users see GPU options; unauthorized users see CPU-only notice
- Backend enforcement still guarantees no privilege escalation

## Implementation Notes

### Files and locations
- Config: `cluster-maintenance/clusters/<cluster>/jupyterhub/values.yaml`
- Template: Custom HTML/CSS/JS inside `c.Spawner.options_form` (static string)
- Validation: `c.KubeSpawner.profile_list` includes all CPU and GPU slugs
- Enforcement: `apply_profile_settings` attached to `c.KubeSpawner.pre_spawn_hook`

### Frontend logic
- On page load, the script fetches `/hub/api/user` with the `X-XSRFToken` header
- It normalizes `user.groups` (supports strings or objects with `name`)
- If the user is admin or in `cpsHPCAccess` / `jupyter_admin`, GPU profiles remain visible
- Otherwise, the GPU optgroup is hidden and a CPU-only info banner is shown
- On any API error, the UI leaves GPU visible; the backend still enforces security

### Backend enforcement
- `apply_profile_settings(spawner)`
  - Reads `spawner.user_options['profile']`
  - Blocks GPU profiles for users not in allowed groups (or admin)
  - Applies image, CPU, memory, and GPU resource settings from `PROFILE_CONFIGS`
  - Optional: Admins can supply a `custom_image` to override the profile’s default image

### Custom image support
- UI: An Advanced Options panel (visible to admins) includes a text input for `custom_image`
- Form: `options_from_form` reads `custom_image` when present
- Hook: Admins (or `jupyter_admin`) can override `spawner.image` with basic validation (alphanumeric, `._-:/`)

### Key decisions
- We keep the UI simple and consistent with a static HTML string
- JavaScript adds adaptation based on permissions without breaking render paths
- The backend is the source of truth for security

## Troubleshooting
- Seeing only CPU profiles as a privileged user?
  - Check the browser console; ensure `/hub/api/user` returns 200 and includes your groups
  - Verify the `X-XSRFToken` header is present; stale cookies can break this call
  - Backend still allows GPU selection if you pick a GPU profile; frontend will catch up after refresh
- Spawn fails with “No such profile”
  - Ensure `c.KubeSpawner.profile_list` contains all CPU and GPU slugs used in the form
- Callable `options_form` doesn’t render
  - Use a static string version; the Helm chart/KubeSpawner combo does not reliably render callables

## Relevant config anchors
- `c.Spawner.options_form`: static HTML form string
- `c.KubeSpawner.profile_list`: list of available profiles (slugs)
- `apply_profile_settings`: pre-spawn hook for enforcement and profile application
- `options_from_form`: extracts `profile` and optional `custom_image` from the POST

---
Maintained by: CPS GPU Cluster Team
