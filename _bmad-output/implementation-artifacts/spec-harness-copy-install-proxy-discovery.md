---
title: 'Built-copy addon auto-spawns the MCP proxy; live MCP suite reads the current tree key'
type: 'bugfix'
created: '2026-10-03'
status: 'done'
baseline_commit: '61443b6ec0eb172dcde7bb13e3ec285fbe4a765c'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/tests/uat/run/2026-10-03-01/report.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/integration-mcp-freecad.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** (D1) An addon installed from `scripts/build_addon.py` output (a real copy under `%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy`) never auto-spawns the MCP proxy: `_discover_external_python` only walks from the package path, and a copy in `%APPDATA%` has no path relation to the repo `.venv`. Run 2026-10-03-01 log: `MCP proxy not auto-started: no .venv/venv interpreter found next to the addon`. (F2) `_automation/live_mcp_manual.py` passes 4/22 because `sole_object` reads `tree.get("nodes")` while `query_tree_summary` returns `"tree"`.

**Approach:** `build_addon.py` writes a marker file holding the repo root into the built addon root. `_discover_external_python` reads that marker as one more discovery root, after the junction walk and before the env overrides. Fix the stale key in `live_mcp_manual.py`.

## Boundaries & Constraints

**Always:** Discovery stays zero-env-var for both junction and built-copy installs. A missing, unreadable, or stale marker (path without a venv) falls through to the existing env-var and `uv` fallbacks; it never raises inside `start_bridge`. Marker is plain UTF-8 text, one absolute path, stdlib-only read (`bootstrap.py` runs in FreeCAD's Python).

**Never:** No change to `_mcp_proxy_command` resolution order for `FREECAD_BUDDY_MCP_CMD`. No new env var. No import of `mcp` in-FreeCAD (AD-12). No change to the package copy itself (the package under `dist/addon/freecad_buddy` stays byte-equal to `src`). No edits to UAT runbooks or CLAUDE.md beyond the discovery description.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Junction install | `bootstrap.py` resolves into `<repo>/src/...`; repo has `.venv` | repo venv python (unchanged) | N/A |
| Built copy with marker | addon root has marker → `<repo>`; `<repo>/.venv` exists | `<repo>/.venv/<Scripts|bin>/<python>` | N/A |
| Built copy, marker points to path with no venv | marker → dir without `.venv`/`venv` | `None` from discovery | falls through to env/`uv` fallback |
| Built copy, no marker | no marker file | `None` from discovery | falls through |
| Marker unreadable / empty | empty file or OS error on read | ignored | no exception escapes |

</frozen-after-approval>

## Code Map

- `scripts/build_addon.py` -- `build()` assembles `dist/addon/`; `REPO_ROOT` already known. Add marker write. Stdlib only.
- `src/freecad_buddy/hosts/gui_addon/bootstrap.py:153` -- `_discover_external_python()`; `here = Path(__file__).resolve()`; probes `parents[4]` and `parents[2]`. `parents[2]` for a copy is the package dir, never a venv parent; its comment ("a vendored copy resolves the same way … the addon root") is wrong. Addon root for a copy is `here.parents[3]`.
- `src/freecad_buddy/hosts/gui_addon/bootstrap.py:197` -- `_mcp_proxy_command()`; do not reorder.
- `_automation/live_mcp_manual.py:46-49` -- `sole_object`: `nodes = tree.get("nodes")` → contract key is `"tree"` (see `query_tree_summary` envelope).
- `tests/infc/` -- stdlib `unittest`, run by `tests/run_tests.py` under FreeCAD; `bootstrap.py` imports PySide via `pump.py`, so it is importable only here (not under pytest).
- `tests/external/` -- pytest; `scripts/` imported by `sys.path.insert` (see `test_scaffold.py`).
- `_bmad-output/.../design/integration-mcp-freecad.md:136` and `CLAUDE.md` §16 -- describe discovery as "walk from the package `__file__` to the repo root"; add the marker.

## Tasks & Acceptance

**Execution:**
- [x] `scripts/build_addon.py` -- write marker `repo-root.txt` (content `str(REPO_ROOT)`) at the addon root in `build()`; name it in a module constant -- copy install gains a path back to the repo.
- [x] `src/freecad_buddy/hosts/gui_addon/bootstrap.py` -- replace the `parents[2]` probe with: read `here.parents[3] / "repo-root.txt"` when present, append its stripped path to `roots`; swallow `OSError`/empty. Give `_discover_external_python` an optional `here: Path | None = None` (default `Path(__file__).resolve()`) as the test seam. Correct the comment.
- [x] `tests/external/test_build_addon.py` -- new: build into `tmp_path`; marker exists, content equals repo root; package copied.
- [x] `tests/infc/test_bootstrap_discovery.py` -- new: hermetic temp layouts for every I/O matrix row (fake `<repo>/.venv/<Scripts|bin>/<python>` files; clear `FREECAD_BUDDY_REPO`/`FREECAD_BUDDY_SRC` for the test).
- [x] `_automation/live_mcp_manual.py` -- `tree.get("nodes")` → `tree.get("tree")`.
- [x] `integration-mcp-freecad.md` §136, `CLAUDE.md` §16 -- add one clause: a built copy finds the venv through the `repo-root.txt` marker written by `build_addon.py`.

**Acceptance Criteria:**
- Given the addon built with `build_addon.py` and copied into `Mod\FreeCADBuddy` (no junction, no env vars), when FreeCAD is launched through `cua-driver launch_app`, then `addon.log` shows `spawned MCP proxy` and `:8765` is listening.
- Given the junction install, when FreeCAD launches, then the proxy still auto-spawns (no regression).
- Given a live bridge with golden models present, when `uv run python _automation/live_mcp_manual.py` runs, then no failure is caused by an unresolved object name (`obj` is a real name for every golden model).

## Design Notes

Marker over folder walk: a copy in `%APPDATA%` shares no ancestor with the repo, so no walk can find the venv. The build script is the only actor that knows both paths. A machine that receives the built addon without the repo gets a stale marker path, and discovery falls through exactly as before.

## Verification

**Commands:**
- `uv run ruff check .` -- expected: clean
- `uv run pytest tests/external` -- expected: all pass, including `test_build_addon.py`
- `<fcb-env>\python.exe tests/run_tests.py` -- expected: `test_bootstrap_discovery` passes, no new failures
- `uv run python scripts/check_imports.py` -- expected: clean

**Manual checks:**
- Repeat run C of `tests/uat/run/2026-10-03-01` (backup kept outside `Mod\`): proxy auto-spawns from the built copy; E2E smoke 13/13; restore junction; run D smoke 13/13.
- Rerun `live_mcp_manual.py`; record pass count.

## Implementation Notes

- `bootstrap.py` read also catches `UnicodeDecodeError`: `_mcp_proxy_command` runs outside any try in `start_bridge`, so a non-UTF-8 marker would otherwise break startup.
- Infc test imports `FreeCAD` before `bootstrap`; FreeCAD init puts `Ext/PySide` on `sys.path`, which `pump.py` needs.
- Marker name lives in both `build_addon.REPO_ROOT_MARKER` and `bootstrap._REPO_ROOT_MARKER`: `bootstrap.py` runs in FreeCAD and cannot import from `scripts/`.

## Review Triage Log

| # | Layer | Finding | Verdict | Evidence | Route |
|---|-------|---------|---------|----------|-------|
| 1 | verification-gap | Build-side marker name not pinned: `test_build_addon.py` reads `build_addon.REPO_ROOT_MARKER` back, so renaming it passes all tests while `bootstrap._REPO_ROOT_MARKER` reads the old name | low | Test asserts through the constant under test; infc test writes its own literal | patch: assert literal `repo-root.txt` |
| 2 | blind | Marker name written three times, no cross-check | low | Same root cause as #1 | grouped with #1 |
| 3 | edge-case | Marker saved with UTF-8 BOM keeps U+FEFF after `strip()` | low | `read_text(encoding="utf-8")` keeps a BOM; PowerShell 5 writes one on hand edit; fix is a direct encoding change | patch: `utf-8-sig` |
| 4 | blind | `UnicodeDecodeError` branch has no test | low | Only the OSError case exists | patch: add case |
| 5 | blind | No test that a stale marker falls through to `FREECAD_BUDDY_REPO` | low | `setUp` clears both env vars; no case sets one | patch: add case |
| 6 | blind | `project-structure.md` §2.2 build tree omits `repo-root.txt` | low | Tree lists 3 entries; build writes a 4th; that doc decides layout | patch: add tree line |
| 7 | blind | `AGENTS.md:440` keeps old discovery text | low | Line unchanged | defer: agent-context file |
| 8 | blind | Docstring says returned venv has `freecad_buddy` + `mcp` importable; code checks `is_file()` only | low | Unchanged baseline line | defer: pre-existing |
| 9 | blind | "MCP proxy not auto-started" message advises `uv sync`; wrong for a copy install without marker | low | Message predates change | defer: pre-existing |
| 10 | edge-case | No log when marker points to a path without venv | low | Fix adds a branch; met only with a stale build | reject: unlikely, adds code |
| 11 | edge-case | Relative marker path resolves against FreeCAD cwd | low | `build()` always writes absolute `REPO_ROOT`; needs a hand edit | reject: unlikely, adds guard |
| 12 | blind | Builder absolute path baked into `dist/`; no `is_absolute()` check | low | Same as #11; foreign path falls through to old behavior | reject: unlikely, adds guard |
| 13 | edge-case | Stale `Mod` copy shadows `src`, infc tests hit old signature | false | Fails loudly with `TypeError`; CI has no Mod install; pre-existing known hazard | reject |
| 14 | edge-case | Byte-equal claim checked on `bootstrap.py` only | low | `copytree` call unchanged by this diff | reject: not caused, adds code |
| 15 | blind | Same as #14 plus shared build fixture | low | Same as #14 | reject |
| 16 | blind | Proxy runs repo `src` while FreeCAD runs copied package; skew if `src` edited without rebuild | low | Copy is a snapshot by design; junction is the dev path | reject: needs version check, unlikely in dev loop |
| 17 | blind + verification-gap | `_automation/live_mcp_manual.py` fix is gitignored | low | `.gitignore:32` `_automation/`; fix applied in working copy | reject: no code fix, raise at commit |
| 18 | blind | No end-to-end evidence for main AC in diff | false | Implementer launch evidence (proxy pid 3240, 13/13); lead re-verifies in step 5 | reject |
