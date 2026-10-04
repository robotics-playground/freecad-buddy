# Run context — UAT 2026-10-03-04

Shared facts for every TC executor. Set up once by the main runner (uat-runner).

## Paths

| Name | Value |
| --- | --- |
| `PROJECT_ROOT` | `D:/Work/Personal/Sources/freecad-buddy` |
| `RUN_DIR` | `D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-03-04` |
| Evidence | `$RUN_DIR/evidence/` — use the `D:/...` form. A `/d/...` MSYS path breaks `cua-driver` and Windows Python. |
| `FREECAD_EXE` | `C:/Program Files/FreeCAD 1.1/bin/freecad.exe` |
| `FCB_PYTHON` | `C:/Users/thuan/micromamba/envs/fcb/python.exe` (H1 legs; needs the PYTHONPATH/PATH patch from APPENDIX-B step 3). It reports FreeCAD **1.1.3** |
| Audit log (inherited env `FREECAD_BUDDY_AUDIT_LOG`) | `D:/Work/Personal/Sources/freecad-buddy/_automation/uat/audit.jsonl` |
| Addon log / proxy log | `%APPDATA%/FreeCAD/v1-1/freecad-buddy/addon.log`, `mcp-proxy.log` |

## Build banner (query_capabilities, live GUI)

- FreeCAD GUI **1.1.4** (window title `FreeCAD 1.1.4`; `freecad_version: "1.1.4"`). The test plan says 1.1.1; that is stale. A `Then` that expects the literal `1.1.1` is a test-case defect, not a product defect — report it as such.
- `element_map_available: true`, `serializer: exportBinary`, `varset_backend: varset`, `render: gui_constructed`, `sketcher_available/partdesign_available: true`, `exec_enabled: false`.
- package `freecad-buddy 0.0.1`; RPC `_SUPPORTED_VERSIONS = ["1"]`.
- Git `fe4b8af` on `feat/epic-4-spec-to-part`, clean tree. Addon is a Junction to `src/freecad_buddy`.
- `tools/list` = 45 names (`evidence/00-tools-list.json`).
- APPENDIX-B step 6a satisfied: `preview_dry_run` + `feature_body_create` committed `OK` (`evidence/00-mutation-check.txt`).

## Live process (may change — always re-read `evidence/fc.json`)

`evidence/fc.json` holds the current `pid`, `window_id`, proxy pids. **If you relaunch FreeCAD, update `fc.json`** so the next executor and `gui.py` find the new ids.

## Calling MCP tools

The session `mcp__freecad-buddy__*` tools are NOT connected. Call the bridge over HTTP from the repo uv env:

- One call: `uv run python _automation/uat/fcb.py <tool> '<json>'` (prints the envelope; a schema reject prints `{"_raw": "Input validation error: ..."}`).
- Many calls in one session: `uv run python _automation/uat/fcb.py --batch file.json` (`[{"tool":..,"args":{..}}]`), or write a small script with `mcp.client.streamable_http.streamablehttp_client("http://127.0.0.1:8765/mcp")` (see `evidence/00-mutation-check.py`). Save scripts and their JSON/JSONL output in `$RUN_DIR/evidence/`.
- Close everything: `uv run python _automation/uat/close_all.py`.
- Mutations: `preview_dry_run {doc, operation:{tool, args}}` then the tool with `"confirm": {"preview_id": <id>, "elicitation_action": "accept"}`. `document_create` takes `label` (not `name`).
- `sketch_add_geometry` must leave the sketch fully constrained in the same call, or it rolls back.

## GUI (cua-driver)

- Pass JSON on stdin: `echo '{...}' | cua-driver <tool>`.
- Helper `evidence/gui.py` (run with `uv run python`):
  - `fitall` — clicks FreeCAD's own **Fit All** toolbar button by `element_token` from a fresh snapshot (route accessibility). Present only when a 3D view is open.
  - `shot <name.png>` — window capture to `evidence/<name.png>`.
  - `fitshot <name.png>` — Fit All then capture.
  - `buttons [substr]` — list toolbar Button labels.
- Default fit per test-plan §3 rule 5 is `view_fit_viewport {doc}`; use `gui.py fitall` when the MCP fit is under test, unavailable, or not `OK`. Known deferred defect: `view_fit_viewport` can frame a datum/sketch instead of the solid; if its framing looks wrong, record it and use Fit All for the capture.
- **Every scenario's visual `Then`:** fit, capture, then `Read` the PNG and judge the pixels yourself. A visual not read = FAIL.
- `invoke_menu` confirmed on this build: `["File","Exit"]`. `["View","Fit All"]` is refused — use the toolbar button.
- `press_key`/`hotkey` to the viewport are often dropped; verify every GUI action in a second domain.
- Do not use `Start-Process`, `SetForegroundWindow`, or `taskkill /F` unless the TC itself requires a kill (TC-01-14). Exit FreeCAD with `invoke_menu ["File","Exit"]`.

## Relaunch procedure

1. `uv run python _automation/uat/close_all.py`, then `echo '{"pid":P,"window_id":W,"path":["File","Exit"]}' | cua-driver invoke_menu`.
2. Confirm 0 FreeCAD processes and `:8765` free.
3. `bash $RUN_DIR/evidence/launch.sh <tag>` (launches through `cua-driver launch_app`, waits for `:8765`, prints pid / window id / new addon.log lines). Take `window_id` from `list_windows` (the helper does).
4. Write the new ids to `evidence/fc.json`.

Env vars for FreeCAD (e.g. `FREECAD_BUDDY_ALLOW_EXEC=1`, `FREECAD_BUDDY_NO_AUTO_MCP=1`): `launch_app` has no env field, and FreeCAD inherits the cua-driver daemon's env. A workable route is `launch_app` with `path` = a `.cmd` wrapper in the scratch area that `set`s the variable and then runs freecad.exe (`start "" "C:\Program Files\FreeCAD 1.1\bin\freecad.exe"`). If no route works, mark the scenario BLOCKED with the reason. Always relaunch a clean (no extra env) FreeCAD before you finish, unless the TC's cleanup says otherwise.

## Safety

- RPC listener runs on FreeCAD's main thread. Keep pattern occurrences ≤ 20, dimensions at model scale. If a call has not returned in ~60 s, do not retry; report it.
- Do not edit product code, tests, docs, or test cases. Do not commit. Do not delete files under `_automation/uat/`.
- NEVER open anything under `benchmarks/*/heldout`.
- A FAILED scenario: leave its state, record it, then run its cleanup before the next scenario only after you captured the evidence (you are the only investigator; the main runner needs evidence files, not live state).
- Watchdog between scenarios groups: `uv run python scripts/automation/uat_watchdog.py --pid P --window W --since "2026-10-03T23:17:00"` (pass a naive timestamp; an offset-aware `--since` crashes the script).

## Code under test moves during this run

Other agents commit to `src/` in this same working tree while the run is live, and the addon is a junction to `src`. FreeCAD loads the code at launch. **Whenever you relaunch FreeCAD, append a line to `evidence/launch-log.tsv`**: launch time, pid, `git rev-parse --short HEAD`, and `git status --short src` (empty or not). Never `git add` anything; if you see run files staged by someone else, report it.

## Lessons and known facts from earlier TCs in this run (reference them; do not re-investigate)

Harness:
- Golden `.FCStd` models may open with objects hidden → `view_fit_viewport` returns `SPEC_FAILED view_fit.unverified`. Show objects (View > Visibility > Show All Objects) before the fit, and record it.
- `view_fit_viewport` can return OK (`fits:true`, `ratio:0.0`) while framing a datum plane or sketch (known deferred defect) → use `gui.py fitall` for the capture, and record it.
- Space keypresses to the tree are dropped; foreground clicks work. TC menu labels can be stale (`Open…`); read labels from the live UIA tree.
- Env-var launches: `evidence/tc-03-fc-autoapprove.cmd` (`FREECAD_BUDDY_AUTO_APPROVE=1`) and `evidence/tc-05-fc-allowexec.cmd` (`FREECAD_BUDDY_ALLOW_EXEC=1`) work through `cua-driver launch_app`. Log the launch; relaunch clean before you finish.
- Snapshot dirs `FCB_TMP_snap_*` live under `C:/Users/thuan/freecad-buddy-workdir/tmp` on this build, not `%TEMP%`; a non-elevated shell may get "Access is denied" listing them. `%TEMP%` holds 10 old snapshot dirs dated 2026-09-22 (not from this run).
- FreeCAD 1.1.4 edge names: box vertical corners are Edge1/2/5/8; cylinder seam Edge3. Derive edge names from geometry before use.
- Direct-RPC probes need the proxy stopped (AD-26 single client), then restarted. `Stop-Process` may be denied; TC-01 used TerminateProcess.
- Infinity cannot be sent as JSON (client turns it into null): such steps are NOT RUN.

Product facts already recorded (cite the TC id, do not re-derive):
- TC-02-05: `query_tree_summary` filters prune a non-matching container before recursing, so `types:["PartDesign::Pad"]` returns `[]` (`queries.py:352-358`).
- TC-02-13: save to a new path renames the document label to the file stem (`documents.py:319`).
- TC-02-18: save to a missing folder creates it; save to a directory path writes `<dir>.FCStd`; read-only target returns `RECOMPUTE_ERROR`.
- TC-03-05: point geometry reads `center`, not `start` (`sketches.py:204`). TC-03-06: single-point DistanceX/DistanceY with `first_pos` refused (`sketches.py:442`).
- `query_object` returns properties only (no faces/edges list), and link targets become `<Type>` strings (`queries.py:407`).
- TC-04-04: `feature_pad.second_length` ignored (`features.py:483`). TC-04-21: `{Shape:1}` not refused before the transaction. TC-04-23 / TC-05-03: pad of an under-constrained sketch commits (`transaction.py:246`).
- TC-05-06: snapshot restore never reaches `rolled_back_via_snapshot` (brep_sha256 changes after reopen). TC-05-15/16/17: TNP audit reports `CLEAN` when it did not run or the reference broke.
- TC-06-03: `query_screenshot` with `include:["Body"]` returns OK but a blank PNG. TC-06-04: transparency without colour has no effect.
- TC-07-03: `verify_sketch` reports `dof=0` for an under-constrained sketch opened from file (DoF read before solve, `verify.py:331`). TC-07-05: `export_step {ap:"AP242"}` writes AP214 (`shim.py:412`).
- `view_fit_viewport` returns `SPEC_FAILED` on a document with only a sketch or only a mesh; use `gui.py fitall`.
- `document_open` opens only `.FCStd`. Careful: a "Close" Button at y≈0 is the main window's close; match task-panel buttons only below the title bar.
