# UAT run 2026-10-05-01 — Story 10.4 targeted GUI acceptance

Purpose: verify Story 10.4 (render and framing, findings F-14, F-15, F-16, F-28) in the real
FreeCAD GUI. Expected behaviour: `_bmad-output/implementation-artifacts/spec-10-4-render-and-framing.md`,
I/O matrix and decisions D1-D9 (D9 added after the first pass; the re-run checks it).

## Environment

| Item | Value |
| --- | --- |
| `PROJECT_ROOT` | `D:/Work/Personal/Sources/freecad-buddy` |
| `RUN_DIR` | `D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-05-01` |
| Code under test | uncommitted working tree on `feat/epic-4-spec-to-part`, baseline `a1ef9ab` |
| FreeCAD | 1.1.4 GUI, `C:/Program Files/FreeCAD 1.1/bin/freecad.exe`; first pass pid `6760`, window_id `2885910`; re-run pid `3448`, window_id `1058650` |
| Addon | junction `%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy` → repo `src/freecad_buddy` |
| Bridge | RPC listener `127.0.0.1:54122`; MCP proxy on `http://127.0.0.1:8765/mcp`: pid `31740` (first pass), pid `32300` (re-run, parent `3448`) |

## How the run called and observed

- MCP: `evidence/run.py <phase>` (one MCP session per phase; every call appended to
  `evidence/mcp-<phase>.jsonl`) and `evidence/run.py call <tool> '<json>'`.
- Mutations: `preview_dry_run`, then the tool with `confirm.preview_id`. Sketches are
  fully constrained rectangles (`rect()` in `run.py`).
- GUI: `cua-driver` with JSON on stdin. The Python console was opened with
  `invoke_menu ["View","Panels","Python Console"]` (label is capital C on 1.1.4). Lines are typed with
  `type_text` (UIA) and run with a foreground pixel `return` press (`evidence/console.sh`); a background
  `return` is dropped. The console was closed again before exit.
- Window screenshots: `get_window_state` with `screenshot_out_file`, read by the agent.
- Pixel comparison: `uv run --with pillow python evidence/pixdiff.py A B`.
- The documents for S1-S3 are copies of `benchmarks/g0/golden-models/box-10-20-30.FCStd` in
  `evidence/` (the golden file was not touched). Its `Box` is a `Part::Feature`, hidden as shipped.

## Rules followed

- One FreeCAD instance. No modal dialog opened. No edit to `src/`, `tests/infc`, `tests/external`,
  `tests/uat/testcases`. No commit.
- Each scenario in its own document; `_automation/uat/close_all.py` between scenarios.
- Every visual Then judged on a window screenshot or render PNG read by the agent.
- Shutdown: `close_all.py`, console panel toggled off, `invoke_menu ["File","Exit"]`; then 0 FreeCAD
  processes and no `:8765` listener. `git status` and `git diff --stat` equal to preflight.
