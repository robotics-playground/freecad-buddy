# Close-loop validation

This container is the UAT environment: every UAT run drives FreeCAD here, never on the host
(CLAUDE.md section 9, `tests/uat/test-plan.md` §6).

- Target: desktop. FreeCAD 1.1.4 GUI with the FreeCAD Buddy release addon, in a Linux container.
- Tool: `cua-driver` 0.28.1 (pinned release binary) in container `fcb-desktop`. Base image `trycua/cua-xfce` (pinned digest; Debian Bookworm, XFCE, TigerVNC, noVNC).
- Command: `uv run python tests/close-loop/journey_box.py`
- Journey: an agent builds a 30x20x10 box through MCP, and FreeCAD's own window shows it.
- Evidence: `tests/close-loop/evidence/journey-box.png` (git-ignored; written on every run).
- Proven:
  - Element-based cua-driver actions on FreeCAD. `get_window_state` returns the widget tree (346 elements on a fresh start; File, Edit and View among them), and a click by `element_token` on a menu item or a tree item changes FreeCAD (screenshots in `tests/uat/run/2026-11-17-10-9-smoke/evidence/demo-*.png`). `uv run python tests/close-loop/check_harness.py` checks that the tree is there; the press itself is shown by those screenshots. The driver's own `invoke_menu` still refuses FreeCAD's menu bar (`menu path segment 0 has no safe activation action`: Qt's top-level menu items offer only `ShowMenu`), so the runner resolves the menu path in the element tree and presses the leaf item.
  - PASS. The 3D view has a solid share of about 50%; the screenshot shows `CloseLoopBox` in the model tree and a fitted, shaded box.
  - The loop can fail. With FreeCAD started with `FREECAD_BUDDY_SCRIPT_EXEC=0`, `script_exec` is refused, the solid share is 0.0%, and the run prints FAIL.
- Not proven:
  - Parity of the rebuilt Qt libraries with the upstream AppImage beyond the guards below: the image swaps two Qt libraries (see the next section).
  - Rendering parity with the Windows host. The container renders with Mesa software OpenGL and Linux fonts, so its screenshots are not comparable with Windows UAT baselines.
  - Any FreeCAD version other than 1.1.4, and any other screen size than 1600x1000.

## The Qt accessibility bridge

The AppImage's Qt (conda-forge `qt6-main 6.8.3`) is built without the AT-SPI bridge: Qt enables it only when `libatspi` is found at build time (`qtbase` 6.8.3 `src/gui/configure.cmake:665`, `ATSPI2_FOUND`), so FreeCAD never joined the accessibility bus. The `qt-build` stage of the `Dockerfile` builds `libQt6Gui` and `libQt6XcbQpa` from the pinned `qtbase` 6.8.3 source (SHA-256 checked) with `libatspi` present and the conda-forge feature flags (`xcb`, `xcb_xlib`, `wayland`, `vulkan`, `egl`, `xkbcommon`), and swaps them into `/opt/freecad/usr/lib`. `libQt6XcbQpa` matters because `QXcbIntegration::accessibility()` creates the bridge there. `swap-qt-gui.sh` stops the build when a rebuilt library lacks an exported symbol of the original; four names are allowed to differ (`_init`, `_fini` and two FreeType 2.13 COLRv1 methods of `QFontEngineFT`), and no ELF file under `/opt/freecad` imports any of them. The originals stay in `/opt/qt-original`. The FreeCAD binary is the unmodified 1.1.4 release.

With the bridge on, Qt warns `Received text event for invalid interface` while FreeCAD builds a notification label. FreeCAD forwards that warning to `NotificationArea::pushNotification`, which locks the mutex that `showInNotificationArea` (`NotificationArea.cpp:1143`) already holds, and the main thread deadlocks (gdb: `pthread_mutex_lock` under `pushNotification` under `showInNotificationArea`). `fcb-freecad start` and the runner therefore set `QT_LOGGING_RULES=qt.accessibility.atspi.warning=false`. Start FreeCAD any other way and it can hang.

Guards on the final image: `journey_box.py` PASS at 49.7% and the same scene with the original libraries and with the rebuilt ones differs in 0 of 1,458,240 pixels.

## Start

From the repo root:

```bash
uv run python scripts/build_addon.py --release
docker compose -f tests/close-loop/docker/compose.yaml up -d --build
docker exec -u cua fcb-desktop fcb-freecad start
curl -fsS http://127.0.0.1:18765/healthz   # wait until freecad_pid is a number
```

Or start FreeCAD from the container desktop: the Applications menu holds **Graphics > FreeCAD 1.1.4**, and the desktop holds a **FreeCAD 1.1.4** launcher. Both run `fcb-freecad start`, so the session environment, the log `/tmp/freecad.log` and the single-instance check apply. Wait for `freecad_pid` in `/healthz` as above.

The first FreeCAD start in a new container provisions the addon's proxy venv from the bundled wheel, which takes about 25 s. Later starts in the same container reuse that venv.

The container sees the repo read-only at `/repo`, and `tests/uat/run/` writable at `/repo/tests/uat/run/`. Paths in MCP tool arguments are container paths: a golden model is `/repo/benchmarks/g0/golden-models/<name>.FCStd`, and exports go under `/repo/tests/uat/run/<run>/`.

After any change under `src/`, run the build and compose commands again. The image installs `dist/addon/` (the release tree `build_addon.py --release` writes), not the source tree. The build stops when `dist/addon/` holds a dev build with no `wheels/`.

## Endpoints

All ports bind the host loopback only.

| What | Where |
| --- | --- |
| freecad-buddy MCP (container proxy) | `http://127.0.0.1:18765/mcp`. A socat relay forwards it to the proxy's `127.0.0.1:8765` inside the container. |
| cua-driver MCP (stdio) | `docker exec -i -u cua fcb-desktop fcb-cua-mcp`. cua-driver serves MCP over stdio only, so no port opens. |
| Desktop view for a human | noVNC at `http://127.0.0.1:6901/vnc.html` |

To give Claude Code both as MCP servers, add these entries under `mcpServers` in your `.mcp.json` (git-ignored, so each clone adds them), then restart Claude Code after the container is up:

```json
"freecad-buddy-docker": { "type": "http", "url": "http://127.0.0.1:18765/mcp" },
"cua-driver-docker": {
  "type": "stdio",
  "command": "docker",
  "args": ["exec", "-i", "-u", "cua", "fcb-desktop", "fcb-cua-mcp"]
}
```

## Helpers in the container

| Command | Does |
| --- | --- |
| `fcb-freecad start\|stop\|status\|userdir` | Start or stop the GUI in the XFCE session, show the pids and `/healthz`, print FreeCAD's user data directory |
| `fcb-session-env` | Print `DISPLAY` and the session D-Bus address for a `docker exec` shell |
| `fcb-cua-mcp` | cua-driver MCP server inside the desktop session. It waits up to 120 s (`FCB_SESSION_WAIT_S`) for the desktop session and exits 1 with a message when none appears, so it never starts without the session's D-Bus address |
| `fcb-py` | The AppImage's Python 3.11 with the pinned `mcp`, `trimesh` and `lib3mf` (`/opt/fcb-site`, from `uv.lock` with hashes; numpy stays the AppImage's 1.26.4) and FreeCAD's own modules importable; it exports the session `DISPLAY` and D-Bus address. Runs the UAT runner, the UAT watchdog and the H1 host |
| `fcb-cua-serve` | cua-driver daemon that `cua-driver call` talks to; supervisord starts it (`supervisorctl status fcb-cua-serve`) |

## Test and UAT commands

| What | Command |
| --- | --- |
| Accessibility checks (late-session MCP address, registry, GTK and FreeCAD element counts). Needs the container and a started FreeCAD; not part of pytest or CI | `uv run python tests/close-loop/check_harness.py` |
| Scripted UAT runner. Stop FreeCAD first (`fcb-freecad stop`): the runner starts its own | `docker exec -u cua fcb-desktop fcb-py /repo/tests/uat/runner/run.py /repo/tests/uat/scenarios --out /repo/tests/uat/run/<run>/runner` |
| UAT watchdog, between test cases | `docker exec -u cua fcb-desktop fcb-py /repo/scripts/automation/uat_watchdog.py --pid <freecad pid>` |
| Headless sweeps (H1 front and FreeCAD worker run in the container, over the installed addon; reports in `_automation/`) | `uv run python scripts/automation/run_mcp_e2e.py` and `uv run python scripts/automation/run_mcp_edge_cases.py` |

Run cua-driver as `/usr/local/bin/cua-driver`. A bare `cua-driver` resolves to the base image's older Python wrapper in `/opt/venv/bin`, which fails as user `cua`.

## Stop

```bash
docker compose -f tests/close-loop/docker/compose.yaml down
```
