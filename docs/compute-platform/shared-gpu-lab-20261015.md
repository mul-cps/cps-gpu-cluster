# Shared 5 GiB GPU lab: current status

The `shared-gpu-lab` pilot has passed normal Source Start, a native 5 GiB cap,
two-browser RTC and GPU execution on 2026-10-15. The current `5c4d9d40`
handover runs Gateway511e and both Hub6bb processes. A subsequent normal Source
Start reached Running/Ready with zero restarts, a sealed current 5 GiB cap and
three member reservations. Earlier Gatewayd974 acceptance established normal
Compute discovery, persisted demo/output and renewed RTC/GPU execution. Fresh
post-handover sharing/identity checks passed for both students, and Armin's
fresh CPU9444 C7 GUI acceptance passed. Fresh SDK and CPU batch checks on
CPU9444 remain pending.
The platform remains a limited pilot without MIG; full production qualification
is unfinished.

From your personal Lab session:

1. Open **Compute**. If prompted, authorize Compute once, then refresh the panel.
2. Select **Shared Workspaces**, find `shared-gpu-lab`, and choose **Open workspace**.
3. Open `shared-gpu-demo-20261015.ipynb`. Browser requests retain your own identity;
   the shared kernel runs as the workspace principal.

[Open the shared GPU demo notebook](https://jupyterhub.dshl.unileoben.ac.at/user/cps-ws-27c474f74f9d41c53eac0be01fcca8a3/rtc/lab/tree/shared-gpu-demo-20261015.ipynb).
Use your ordinary CPS Hub login. The browser tests used Mikasa and Armin, who
each received HTTP 200 and retained their own visitor identity. Both connected
to the same demo kernel, synchronized edits in both directions, and saw the
live GPU output. The earlier Gatewayd974 post-restart test again passed two-way
edits and same-kernel GPU execution with live peer output. Only the owned test
kernel was cleaned up. Mikasa’s personal CPU server Share also has a stable
[personal workspace URL](https://jupyterhub.dshl.unileoben.ac.at/user/mikasa/lab),
which Armin opens while logged in as himself.

The approved profile is `interactive-shared-5`, using storage version 2. The
`mikasa-armin` Hub group contains Mikasa, Armin and Bjoern, with three verified
seven-day grants. Its Share grants access to this exact workspace server. The
neutral workspace account is not an administrator and has no default `user`
role. Browser requests retain the visitor's identity; shared kernel code uses
the workspace principal.

The first Source Start returned HTTP 200 and reached Ready in 26 seconds. The
earlier Gatewayd974 Stop/Start and its Pod
`79388657-dea1-4d49-b5e6-6c7d7e6a514b` remain historical evidence, including
unchanged personal Pod UIDs/restart counts and the separate 64 MiB CUDA
allocation/sum with CUDA reporting 5 GiB. Before the current software handover,
normal Source Stop confirmed that old GPU Pod absent and global reservations
zero. The latest normal Start now runs GPU916 on GPU2 in Pod
`63cb095a-153e-4ca9-8216-85df3b6944bf`, Running/Ready with zero restarts.
Its sealed driver row matches the current boot/cgroup with soft and hard limits
of 5,368,709,120 bytes (5120 MiB). Three actual member reservations share one
binding. This is one bounded workspace result; it does not establish wider
packing or cross-Hub qualification. Fresh RTC/GPU browser checks after the
latest handover are not yet claimed.

Approved CPS/Source-managed CPU paths now select CPU9444; ordinary CIT CPU paths
select CIT6acd. These configuration changes do not restart existing personal
servers. Armin subsequently completed an authorized normal empty-server
Stop/Start onto CPU9444 and passed normal Connect/OAuth plus all six C7 views.
Me/session/profiles/workspaces/workflows returned 200; optional JobSets503 was
shown as distributed workloads unavailable. Admin and Bjoern's unshared server
returned 403. See the [fresh C7 GUI receipt](../../platform-staging/jupyter-extensions-20261013/cps-c7-student-live-actual-20261015.json).
The workspace card has an Open link but no readiness/resource details, showing
“Kernel principal: Not reported” and “Profiles: None reported”. Full resource-UI
qualification, fresh CPU9444 SDK/batch checks and ordinary CIT runtime
acceptance remain open.

The GPU916 notebook package still has two known failures:

- Its old Compute addon has a null PageConfig Compute URL and shows
  `TypeError: Failed to fetch`.
- The ordinary unmodified SDK fails CA trust. An explicit trusted CA and both
  SDK headers allowed the diagnostic `/v1/me` request to return HTTP 200 as the
  workspace principal. That diagnostic does not close ordinary SDK compatibility.

GPU531 is packaged and published but has not been adopted. The prospective-only
`efa3c8ab` validator was published in Gateway511e and Hub1f8f. Gateway511e is now
deployed; current Hub6bb retains that validator from its Hub1f8f base.
Production GPU916, policyD48, Source51f, Node8c, Delivery9cd, canonical mappings
and storage remain unchanged. Fresh six-category GPU531 hardware qualification
has not run. See the [publication receipt](../../platform-staging/jupyter-extensions-20261013/prospective531-runtime-publication-actual-20261015.json).
The earlier Gatewayd974 adoption fixed the empty personal Shared Workspaces
list. Both Mikasa and Armin received HTTP 200 through normal Compute OAuth, retained their own canonical
identity, and received the authorized workspace and Open link. A reviewed
read-only Gateway observer confirms all three registered canonical members
have active global reservations bound to one attempt for `cps:shared-gpu-lab`.
The reservation-state API itself exposes only workspace, active binding and
attempt, not member rows. A normal Mikasa GUI CPU batch was also accepted with
HTTP 200 and succeeded in 22 seconds while this GPU workspace remained Running
and Ready on the same Pod. Its typed parameters, support import, authenticated
notebook download and logs passed; Armin could not list or inspect that personal
job or read its logs, artifacts or download. See the
[concurrent CPU batch receipt](../../platform-staging/jupyter-extensions-20261013/cpu-batch-during-shared-gpu-actual-20261015.json).

The current software handover completed with ready controller activation,
seed `7f08bd0b` and intent `5be320cf`. See the
[current software and consumer adoption receipt](../../platform-staging/jupyter-extensions-20261013/compute-runtime-consumer-adoption-actual-20261015.json).
Three fresh matching console/gateway backups passed integrity and checksum
checks, with owned Jobs removed. The fresh Hub6bb database/role/configuration
capture passed all 12 checksums and current image/spec checks. Both students'
fresh sharing checks returned 200 with correct identities and admin403; these
do not repeat the earlier two-way RTC/GPU execution test.

See the [earlier discovery/restart receipt](../../platform-staging/jupyter-extensions-20261013/student-discovery-adoption-actual-20261015.json)
and the [historical initial acceptance receipt](../../platform-staging/jupyter-extensions-20261013/shared-gpu-lab-native5-actual-20261015.json)
for the four private proof hashes and the distinction between the earlier
Start-only capture and the later cap, RTC and GPU execution results. No private
Pod environment, credentials, browser cookies, kernel UUID or driver identity
is included in the public receipt.

GPU batch remains disabled. Wider packing, membership-removal connection
revocation, remaining CIT runtime/workflow acceptance and full production
qualification remain open.
