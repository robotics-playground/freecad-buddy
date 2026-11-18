# cua-driver — the `fcb-desktop` container (freecad-buddy)

In this repository `cua-driver` drives FreeCAD only inside the Linux container `fcb-desktop`.
The host has no `cua-driver` and no host GUI server. This file holds the container mechanics.
FreeCAD-specific actions and grading rules live in the project standards listed at the end.

Read this file first, then `LINUX.md` for the X11 backend. `WINDOWS.md` and the macOS and
Wayland material do not apply here.

## Reach the driver

- **MCP (default).** Server `cua-driver-docker`, tools `mcp__cua-driver-docker__*`. Its transport
  is stdio through `docker exec -i -u cua fcb-desktop fcb-cua-mcp`, so each connection is one
  `cua-driver mcp` process in the container. When the container restarts or is recreated, the
  connection ends: reconnect the server (`/mcp`) or restart Claude Code.
- **CLI.** Pass the JSON on stdin and run the pinned binary in the desktop session:

  ```bash
  echo '{"pid":816}' | docker exec -i -u cua fcb-desktop \
    bash -c 'eval "$(fcb-session-env)"; /usr/local/bin/cua-driver call list_windows'
  ```

  `fcb-session-env` exports the session `DISPLAY` and D-Bus address. Without it, the AT-SPI
  walk is empty for every window.
- **Binary.** Always `/usr/local/bin/cua-driver`, release 0.28.1, the version of this skill pack.
  A bare `cua-driver` resolves to the base image's 0.12.3 Python wrapper in `/opt/venv/bin`,
  which fails as user `cua`.
- **Version is pinned in the Dockerfile.** `doctor` prints an update notice. Ignore it: an
  update in the container is lost on rebuild and no longer matches this skill.
- **Daemon.** supervisord runs `cua-driver serve` as program `fcb-cua-serve`; `cua-driver call`
  talks to it. Check it with `docker exec fcb-desktop supervisorctl status fcb-cua-serve`.
  Leave `serve`, `stop` and `autostart` to supervisord.

## Platform facts

- X11 on TigerVNC display `:1`, XFCE, screen 1600 x 1000. `doctor` must show `display server:
  X11` and `AT-SPI: org.a11y.Bus reachable via session bus`.
- No `/dev/uinput`. The background MPX pixel path of `LINUX.md` is absent, so a background
  pixel click lands only through AT-SPI at the point. On a window that has no AT-SPI tree, a
  background pixel click or key can be dropped while the call reports success. Verify every
  action from fresh state; after a verified miss, retry with `delivery_mode: "foreground"`.
- Foreground in the container changes only the container desktop, never a host window. The
  UAT run practices (§6) name the actions that need it. Record any other action that needed it.
- A human watches the desktop through noVNC at `http://127.0.0.1:6901/vnc.html`.

## Check whether FreeCAD shows its widgets

The container image decides this, so check it once per container start, before you pick a route:

```json
get_window_state({"pid": PID, "window_id": WIN, "include_screenshot": false})
```

- **`degraded: true`, `element_count: 1`** (reason `x11_property_fallback_partial`): FreeCAD is
  not on the AT-SPI bus. Use the pixel route (coordinates from the window screenshot) and keys
  (`hotkey`, `press_key`, menus by Alt keys). A step written as `element_index` or `invoke_menu`
  with no pixel or key route is `NOT RUN`, with this reason.
- **More than 1 element, menu items File, Edit and View present**: element routes work. Follow
  the escalation ladder in `SKILL.md`.

When every window is degraded, a GTK window such as `xfce4-panel` included, the problem is the
driver's session bus, not FreeCAD. Run `doctor` through the CLI form above. If the CLI sees
elements and MCP does not, the MCP process started before the desktop session: reconnect the
server.

## Paths and evidence

- Every path in a tool argument is a container path. The repo is read-only at `/repo`; only
  `/repo/tests/uat/run/` is writable.
- Write captures with `screenshot_out_file` under `/repo/tests/uat/run/<run>/evidence/`. The
  file appears on the host at `tests/uat/run/<run>/evidence/`, where you `Read` it. A capture
  written elsewhere needs `docker cp fcb-desktop:<file> <host path>` first.
- The container renders with Mesa software OpenGL and Linux fonts. Compare a capture only with
  captures from the same image, never with Windows-host captures.

## FreeCAD in the container

- Start and stop FreeCAD with `docker exec -u cua fcb-desktop fcb-freecad start|stop|status`,
  not `launch_app`. The helper sets the session environment, the log and the single-instance
  check. FreeCAD is ready when `curl -fsS http://127.0.0.1:18765/healthz` shows a number in
  `freecad_pid`.
- When the container is down, start it with the commands in `tests/close-loop/README.md`. When
  it cannot start, the GUI step is `BLOCKED`. Host FreeCAD is never a fallback.
- Project rules that apply on top of this skill:
  - `.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md` — UAT environment
    table: launch, drive, measure, capture, shut down.
  - `.knowledge-base/technical/standards/testing/uat-run-practices.md` §6 — foreground actions,
    popups, stale display.
  - `.knowledge-base/technical/standards/testing/freecad-native-validation.md` — menu paths and
    UIA notes measured on the Windows host. Map each to keys or pixels in the container.
