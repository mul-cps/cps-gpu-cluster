# Xpra Desktop Profile Design

**Status:** Approved, ready for implementation planning.
**Date:** 2026-07-24
**Repos affected:** `mul-cps/cps-jupyter-notebook` (image build), `mul-cps/cps-gpu-cluster` and `bjoernellens1/cit-teaching-platform` (JupyterHub profile wiring, both instances run the same notebook image).

## Background

This repo's JupyterHub GPU-desktop profiles (`gpu-desktop-ros2`, `gpu-desktop-5gb`, `cpu-desktop`) use TurboVNC + noVNC + websockify, with VirtualGL (`vglrun -d egl`) providing GPU-accelerated OpenGL rendering independent of the VNC transport. This stack was stabilized on 2026-07-24 after three live incidents (missing `webserver` symlink breaking `vncserver` startup entirely, Xvnc's own GLX extension segfaulting on this driver, `rviz2` not being wrapped for VirtualGL) — see `docs/troubleshooting.md` and `mul-cps/cps-jupyter-notebook` PRs #23/#24 for the full writeups.

Two usability gaps remain in the stabilized TurboVNC stack, not bugs:
1. **Clipboard**: noVNC's clipboard sync is a manual textbox in the corner of the screen (copy text into it, it syncs to the remote OS clipboard, and vice versa) — not real OS-level clipboard integration.
2. **No productivity tooling**: the desktop images have ROS 2 / dev tooling but nothing for document work (no office suite, minimal desktop utilities).

Separately, researchers using the desktop for CAD/data-review work want real multi-monitor support, which VNC does not do well regardless of clipboard.

## Decision

Build a **new, parallel** desktop image and JupyterHub profile using **Xpra** instead of TurboVNC/noVNC, rather than replacing the stabilized TurboVNC stack in place. Both profiles coexist; the TurboVNC one is not touched by this work. If Xpra proves solid in real use, retiring the TurboVNC profile is a separate, later decision — not part of this plan.

### Why Xpra over the alternatives considered

- **NICE DCV**: best raw performance (hardware encode, low latency), but proprietary and licensed off-AWS — ruled out for an on-prem cluster.
- **Moonlight/Sunshine (including the web-client forks)**: architecturally the wrong shape for this deployment. Sunshine expects a long-lived host bound to a real display with a one-time device-pairing (PIN) flow — awkward for pods KubeSpawner creates/destroys per session. Its transport is UDP/ENet RTP, which doesn't fit the existing path-routed HTTPS ingress (`jupyter-server-proxy` under JupyterHub's `/user/<name>/...` subpath) without exposing per-pod UDP ports — a real architecture change we don't want. Its core value proposition (NVENC hardware encode) is also moot on this hardware (see below).
- **Apache Guacamole**: nicer clipboard UX than raw noVNC, but it's a protocol gateway sitting in front of the same underlying VNC/Xvnc stack — doesn't remove any of the TurboVNC-specific fragility, doesn't improve encode performance, adds another component.
- **Xpra**: transport is a single WebSocket (TCP) with its own bundled HTML5 client and web server — fits the existing `jupyter-server-proxy` pattern with no ingress/networking changes, same as noVNC does today. Native bidirectional OS clipboard sync (no textbox). No device pairing. Actually **removes** a moving part versus today's stack: Xpra serves its own HTML5 client directly, so there's no separate noVNC + websockify process pair to run/monitor.

### Important correction from GPU research: no NVENC on A100

The A100 (GA100 die) has no NVENC/NVDEC hardware video encode/decode blocks at all — it's a compute-only datacenter GPU with no display/video-codec engines. This is true of H100 too. So:
- Xpra will use **software x264 encode** (its default, most common, production-grade path across real-world Xpra deployments — not a degraded fallback).
- This was also a second, independent reason Moonlight/Sunshine is a poor fit here: its whole point is NVENC-based hardware encode, which doesn't exist on this GPU.
- Software encode costs pod CPU rather than "free" GPU cycles — a real resource-planning input for the profile's `cpu_limit`/`cpu_guarantee`, to be sized during implementation based on measured encode load.

VirtualGL's GPU rendering path (`vglrun -d egl`) is unaffected by any of this — it's a rendering optimization, not a video-encode path, and continues to render real frames on the A100 exactly as it does today; only the *transport* of those rendered frames to the browser changes from VNC-tile-diffing to Xpra's own (x264-encoded) protocol.

### Session mode: full XFCE desktop

Xpra "seamless" mode (individual forwarded app windows, no desktop shell) was considered and rejected — it's a bigger UX departure from what researchers are used to today. This design uses Xpra's **desktop mode**: a full XFCE session (same window manager/desktop as the TurboVNC profile) rendered inside Xpra's own Xvfb-backed virtual display, so the day-to-day experience (taskbar, app launcher, file manager) stays familiar.

### Multi-monitor: investigate, don't commit

Xpra's multi-monitor support is well-documented and strong for its **native desktop client**, which reads the local monitor layout and matches it server-side automatically. It is markedly less mature for the **HTML5 browser client**, which is what this deployment actually uses (zero-install, browser-tab access via JupyterHub — a native client would require local installation, which defeats the point). Whether/how well multi-screen virtual layouts work through the HTML5 client specifically is not confirmed. This is **not a committed deliverable** of this design — it's investigated as part of the spike task below, and only carried into the real implementation if it works acceptably. No image/profile changes should be built around an assumption that it works until that's verified.

### Productivity tooling

Kept deliberately lean — specific packages, not meta-packages:
- `libreoffice-writer libreoffice-calc libreoffice-impress libreoffice-draw` (Base and Math explicitly excluded — confirmed with the user, not needed)
- `evince` (PDF viewer)
- `file-roller` (archive manager)
- `mousepad` (lightweight text editor — code-server remains the primary code editor, this is for quick edits)
- Existing Thunar (file manager) and xfce4-terminal are already present and reused as-is.

### Trimming (this migration also removes fat, not just avoids adding it)

Since this ships as a **new** Dockerfile variant rather than editing the existing `Dockerfile.desktop-ros2` in place, "trimming" here means: the new variant simply never installs the TurboVNC-specific packages/scripts in the first place, rather than a diff against the old file. Concretely, the new `Dockerfile.desktop-ros2-xpra` excludes, versus what `Dockerfile.desktop-ros2` installs:
- `turbovnc` (.deb download), `novnc`, `websockify` — replaced by `xpra` (+ its bundled HTML5 client)
- The custom `/usr/local/bin/vncserver`/`webserver` symlink dance and the `Xvnc` shim script (source of two of the three incidents fixed earlier today) — this entire class of bug does not exist in the Xpra architecture
- Re-evaluate `xfce4-pulseaudio-plugin` and `xubuntu-icon-theme` for slimmer equivalents or removal (audio-panel plugin and non-default icon theme are both candidates, to be confirmed during implementation by checking actual size impact)

Explicitly **not** touched by this migration (out of scope, no user request to change them): `code-server` and its extensions, the ROS 2 Jazzy desktop packages, the PyTorch/CUDA/ML pip stack, VirtualGL itself, the `_vglwrap` wrapper mechanism and its wrapped-app list.

## Implementation risk and the required first task

There is no confirmed off-the-shelf `jupyter-server-proxy` / `jupyter-remote-desktop-proxy`-equivalent package specifically for Xpra (unlike VNC, which `jupyter_remote_desktop_proxy` already handles). The integration point — a `c.ServerProxy.servers` entry in the mounted `jupyter_server_config.py` that launches `xpra start :100 --bind-tcp=0.0.0.0:{port} --html=on --daemon=no` on demand and proxies it at `/user/<name>/xpra/` through JupyterHub's existing OAuth-gated ingress — needs to be built and proven, not assumed.

**The implementation plan's first task must be a spike**: in a throwaway pod/image, get a real browser (through the actual JupyterHub ingress path, not just `kubectl port-forward`) connected to an Xpra HTML5 desktop session end-to-end, including:
1. Confirming the `ServerProxy` wiring works through JupyterHub's auth/proxy layers (cookie/token handling, path prefix rewriting — the same class of issue that made VNC's webserver-symlink bug take a while to diagnose).
2. Confirming VirtualGL (`vglrun -d egl`) still renders correctly against Xpra's Xvfb-backed display (same command, different backend display — should work, but unverified).
3. Investigating the multi-monitor question above through the HTML5 client specifically.

Only after that spike succeeds does it make sense to invest in the full Dockerfile, CI matrix entry, and JupyterHub profile wiring described above.

## Rollout plan

1. Spike (above) proves the Xpra+jupyter-server-proxy integration works.
2. New `docker/Dockerfile.desktop-ros2-xpra` in `mul-cps/cps-jupyter-notebook`, new CI matrix entry (`desktop_ros2_xpra` path filter, mirroring the existing `desktop_ros2` entry in `.github/workflows/docker-publish.yml`), publishing `ghcr.io/mul-cps/cps-jupyter-notebook:latest-desktop-ros2-xpra`.
3. New JupyterHub profile `gpu-desktop-xpra` added to `values.yaml` in **both** `cps-gpu-cluster` and `cit-teaching-platform`, alongside (not replacing) the existing desktop profiles, using the same MPS-slice pattern (`gpu-memory` annotation, `mps-pipe`/`mps-log` mounts, `kai-scheduler` queue) as `gpu-desktop-5gb`.
4. Verify live with a real user (same rigor as the Dex cutovers and the TurboVNC fixes this session): confirm connect, clipboard, LibreOffice launches, `rviz2` renders via VirtualGL, and report on the multi-monitor investigation.
5. TurboVNC profile is left running unchanged. Any future decision to retire it is out of scope here.

## Open items carried into planning (not yet decided, not blocking design approval)

- Exact CPU request/limit sizing for the new profile, given software x264 encode load — to be set based on measured behavior during implementation, not guessed upfront.
- Whether to trim `xfce4-pulseaudio-plugin`/`xubuntu-icon-theme` — confirm actual size impact first.
