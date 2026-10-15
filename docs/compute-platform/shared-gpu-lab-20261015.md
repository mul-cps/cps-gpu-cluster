# Shared 5 GiB GPU lab: current status

The `shared-gpu-lab` pilot passed normal Source Start, Pod readiness, a current
5 GiB native GPU cap, two-browser RTC and GPU execution on 2026-10-15. The
platform remains a limited pilot without MIG; full production qualification is
unfinished.

[Open the shared GPU demo notebook](https://jupyterhub.dshl.unileoben.ac.at/user/cps-ws-27c474f74f9d41c53eac0be01fcca8a3/rtc/lab/tree/shared-gpu-demo-20261015.ipynb).
Use your ordinary CPS Hub login. The browser tests used Mikasa and Armin, who
each received HTTP 200 and retained their own visitor identity. Both connected
to the same demo kernel, synchronized edits in both directions, and saw the
live GPU output. The acceptance kernel was cleaned up afterward; only its one
demo session was deleted.

The approved profile is `interactive-shared-5`, using storage version 2. The
`mikasa-armin` Hub group contains Mikasa, Armin and Bjoern, with three verified
seven-day grants. Its Share grants access to this exact workspace server. The
neutral workspace account is not an administrator and has no default `user`
role. Browser requests retain the visitor's identity; shared kernel code uses
the workspace principal.

Source Start returned HTTP 200 and reached Ready in 26 seconds in this run. The
Pod runs the existing GPU916 notebook image on GPU2. A read-only driver check
matched the current boot and cgroup and found soft and hard limits of
5,368,709,120 bytes. The reviewed diagnostics also passed a separate 64 MiB CUDA
allocation and sum, with CUDA reporting 5 GiB. This is one bounded workspace
result; it does not establish wider packing or cross-Hub qualification.

The GPU916 notebook package still has two known failures:

- Its old Compute addon has a null PageConfig Compute URL and shows
  `TypeError: Failed to fetch`.
- The ordinary unmodified SDK fails CA trust. An explicit trusted CA and both
  SDK headers allowed the diagnostic `/v1/me` request to return HTTP 200 as the
  workspace principal. That diagnostic does not close ordinary SDK compatibility.

A replacement addon/SDK image is being prepared and is not deployed by this
acceptance. Personal C7's `/v1/workspaces` currently returns an empty list despite
verified group server access; Gateway discovery wiring remains open. A reviewed
read-only Gateway observer now confirms all three registered canonical members
have active global reservations bound to one attempt for `cps:shared-gpu-lab`.
The reservation-state API itself exposes only workspace, active binding and
attempt, not member rows. A normal Mikasa GUI CPU batch was also accepted with
HTTP 200 and succeeded in 22 seconds while this GPU workspace remained Running
and Ready on the same Pod. Its typed parameters, support import, authenticated
notebook download and logs passed; Armin could not list or inspect that personal
job or read its logs, artifacts or download. See the
[concurrent CPU batch receipt](../../platform-staging/jupyter-extensions-20261013/cpu-batch-during-shared-gpu-actual-20261015.json).

See the [public acceptance receipt](../../platform-staging/jupyter-extensions-20261013/shared-gpu-lab-native5-actual-20261015.json)
for the four private proof hashes and the distinction between the earlier
Start-only capture and the later cap, RTC and GPU execution results. No private
Pod environment, credentials, browser cookies, kernel UUID or driver identity
is included in the public receipt.
