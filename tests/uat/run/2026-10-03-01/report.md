# Harness validation run 2026-10-03-01

## Build banner

| Field | Value |
|-------|-------|
| Git | `61443b6` (working tree: `AGENTS.md`, `CLAUDE.md` modified, not touched by this run) |
| FreeCAD | 1.1.1, `C:\Program Files\FreeCAD 1.1\bin\freecad.exe` |
| Driver | `cua-driver` daemon pid 16172, `\\.\pipe\cua-driver` |
| Actor | Claude Code agent, no operator input after the request |
| Launches | A0 pid 22448, A pid 11244, B pid 26444, C0 pid 28788, C pid 3632, D pid 28292 |

## Questions and verdicts

| # | Question | Verdict | Evidence |
|---|----------|---------|----------|
| Q1 | Can agent launch and control FreeCAD with `cua-driver`? | PASS | `launch_app` returns pid + window; UIA click on toolbar `New Document` gives title `Unnamed - FreeCAD 1.1.1`, MCP `document_list` = 1, pixels `a-01-new-document.png`; `invoke_menu ["File","Exit"]` exits clean 6/6 times |
| Q2 | Can agent build and install the addon into FreeCAD? | PASS with defect | `build_addon.py` exit 0; copy installed (72/72 files, hash equal); FreeCAD loads it (canary from copy in `c-launch.txt`, traceback path `c-loaded-path.txt`); 13/13 smoke. Defect D1: proxy does not auto-spawn from a copied install |
| Q3 | Can agent validate code change to real FreeCAD result with no human? | PASS (junction install) | Canary edit in `src` appears in run B log, absent in run D after revert; body + sketch + pad + measure + verify + STEP export + paired verify 13/13 in A, B, C, D; real viewport captures `*-01-viewport.png` / `a-02-viewport.png` show the 20 x 10 x 5 mm plate |

Human interventions: **0**. No modal dialog appeared in any run. No freeze.

## Runs

| Run | Install | Canary in src | Canary in log | Proxy | Smoke |
|-----|---------|---------------|---------------|-------|-------|
| A | junction to `src` | no | no | auto-spawned | 13/13 |
| B | junction to `src` | yes | **yes** | auto-spawned | 13/13 |
| C0 | built copy + backup inside `Mod\` | no | no | auto-spawned | invalid run, see F3 |
| C | built copy only | no (reverted) | **yes** (from copy) | **not spawned** (D1), manual fallback used | 13/13 |
| D | junction restored | no | **no** | auto-spawned | 13/13 |

| E-fix | built copy with `repo-root.txt` marker | no | no | **auto-spawned** (D1 fixed) | 13/13 |
| F-fix | junction restored | no | no | auto-spawned | 13/13 |

E-fix and F-fix re-check D1 after the fix in `spec-harness-copy-install-proxy-discovery.md`: the built copy now auto-spawns the proxy (`e-fix-launch.txt`), and the junction install still does. `live_mcp_manual.py` with the F2 key fix: 17/22 (`e-fix-live-mcp-manual.txt`); the 5 failures are `screenshot:<golden model>` returning an empty scene, a separate issue.

B and D are the falsification pair: the same launch path shows the marker when `src` carries it and does not show it after revert. C shows the marker while `src` is clean, so the code came from the built copy.

## Smoke definition (`evidence/e2e.py`)

Over `http://127.0.0.1:8765/mcp`, one session:
`query_capabilities` → `document_create` → `feature_body_create` → `sketch_create` (XY) →
`sketch_add_geometry` (rectangle 20 x 10, 11 constraints, fully constrained) → `feature_pad` 5 mm →
`query_mass_properties` (expect 1000 mm³, got `999.9999999999998`) → `verify_shape` →
`verify_recompute` → `export_step` → `verify_export_step` → `view_fit_viewport` → `query_screenshot`.
Every mutation goes through `preview_dry_run` and passes the returned `preview_id` as `confirm`.

## Findings

### D1 — Proxy does not auto-spawn from a built-copy install (defect)

Run C log:

```
MCP proxy not auto-started: no .venv/venv interpreter found next to the addon and no FREECAD_BUDDY_MCP_CMD override.
```

`src/freecad_buddy/hosts/gui_addon/bootstrap.py` `_discover_external_python` probes `here.parents[4]` and `here.parents[2]`.
For a copy at `Mod\FreeCADBuddy\freecad_buddy\hosts\gui_addon\bootstrap.py`, `parents[2]` is `Mod\FreeCADBuddy\freecad_buddy` and `parents[4]` is `Mod`. Neither holds the project `.venv`. The code comment says "a vendored copy resolves the same way", which is not true.
Only `FREECAD_BUDDY_REPO` / `FREECAD_BUDDY_SRC` / `FREECAD_BUDDY_MCP_CMD` rescue it. `cua-driver launch_app` cannot pass env vars, so an agent can only fix it by changing the user environment. Impact: "install addon, `uv sync`, open FreeCAD" (CLAUDE.md §16) works only for the junction install.

### F2 — `_automation/live_mcp_manual.py` is out of date (harness defect)

4/22 pass (`a-live-mcp-manual.txt`). `sole_object` reads `tree.get("nodes")`, but `query_tree_summary` now returns `"tree"`. Object name resolves to `None` and every dependent check fails. Not a product defect. This run used `evidence/e2e.py` instead.

### F3 — Any folder under `Mod\` loads as an addon (procedure trap)

Run C0 kept the backup as `Mod\FreeCADBuddy.harness-backup`. FreeCAD loaded it too, and its junction to `src` won the import (traceback path `...\Mod\FreeCADBuddy.harness-backup\.\freecad_buddy\...`). A backup or a second copy of the addon must live outside `Mod\`.

### F4 — `cua-driver` input notes for this build

- `invoke_menu ["File","New"]` is refused at segment 1. APPENDIX-B lists it as an example; the label is not `New` on this build. `["File","Exit"]` resolves.
- `hotkey ["ctrl","n"]` in background mode is dropped (`a-01-ctrl-n.png` still shows Start page).
- UIA click on toolbar `Button "New Document"` works.
- JSON args with Windows paths must go through stdin; the positional form fails to parse backslashes.

### F5 — Agent error during run

The `["File","Exit"]` path probe in A0 was meant to test label resolution only, but it fired and closed FreeCAD. No document was open, so no data was lost. It did show that a clean shutdown works.

## Not proven

- D1 path with auto-spawn: the built copy was proven only with the manual `serve --mode rpc` fallback.
- `query_screenshot` image was not compared pixel by pixel with the real viewport. The real viewport capture was judged directly and matches the expected part and camera.
- The CI path (`tests/infc` under `FreeCADCmd`, `pytest tests/external`) was not run. It is out of scope for this GUI harness question.

## Final state

- `src` diff empty (canary reverted). `dist/` is gitignored.
- `Mod\FreeCADBuddy\freecad_buddy` is a junction to `src\freecad_buddy` again.
- No FreeCAD or proxy process. No `:8765` listener.
