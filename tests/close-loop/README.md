# Close-loop validation

This container is the UAT environment: every UAT run drives FreeCAD here, never on the host
(CLAUDE.md section 9, `tests/uat/test-plan.md` §6).

- Target: desktop. FreeCAD 1.1.4 GUI with the FreeCAD Buddy release addon, in a Linux container.
- Tool: `cua-driver` 0.28.1 (pinned release binary) in container `fcb-desktop`. Base image `trycua/cua-xfce` (pinned digest; Debian Bookworm, XFCE, TigerVNC, noVNC).
- Command: `uv run python tests/close-loop/journey_box.py`
- Journey: an agent builds a 30x20x10 box through MCP, and FreeCAD's own window shows it.
- Evidence: `tests/close-loop/evidence/journey-box.png` (git-ignored; written on every run).
- Proven:
  - PASS. The 3D view has a solid share of about 50%; the screenshot shows `CloseLoopBox` in the model tree and a fitted, shaded box.
  - The loop can fail. With FreeCAD started with `FREECAD_BUDDY_SCRIPT_EXEC=0`, `script_exec` is refused, the solid share is 0.0%, and the run prints FAIL.
- Not proven:
  - Element-based cua-driver actions on FreeCAD (`element_index`, `invoke_menu`). The AppImage's Qt (conda-forge `qt6-main 6.8.3`) has no AT-SPI bridge, so cua-driver sees only FreeCAD's top-level window. Pixel and keyboard routes remain.
  - Rendering parity with the Windows host. The container renders with Mesa software OpenGL and Linux fonts, so its screenshots are not comparable with Windows UAT baselines.
  - Any FreeCAD version other than 1.1.4, and any other screen size than 1600x1000.

## Start

From the repo root:

```bash
uv run python scripts/build_addon.py --release
docker compose -f tests/close-loop/docker/compose.yaml up -d --build
docker exec -u cua fcb-desktop fcb-freecad start
curl -fsS http://127.0.0.1:18765/healthz   # wait until freecad_pid is a number
```

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
| `fcb-cua-mcp` | cua-driver MCP server inside the desktop session |
| `fcb-cua-serve` | cua-driver daemon that `cua-driver call` talks to; supervisord starts it (`supervisorctl status fcb-cua-serve`) |

Run cua-driver as `/usr/local/bin/cua-driver`. A bare `cua-driver` resolves to the base image's older Python wrapper in `/opt/venv/bin`, which fails as user `cua`.

## Stop

```bash
docker compose -f tests/close-loop/docker/compose.yaml down
```
