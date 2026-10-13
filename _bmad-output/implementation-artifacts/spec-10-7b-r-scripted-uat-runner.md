---
title: 'Story 10.7b (part R): Scripted UAT Runner'
type: 'feature'
created: '2026-10-13'
status: 'done'
baseline_commit: '7260f09addc14bd2216714eb87fa31dfead6f189'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/implementation-artifacts/epic-10-context.md'
  - '{project-root}/_bmad-output/implementation-artifacts/spec-10-7b-freecad-probe-and-offline-reader.md'
  - '{project-root}/.knowledge-base/technical/standards/testing/freecad-gui-e2e-harness.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A UAT run needs an LLM agent to reason through every scenario (about 10 h for run 2026-10-03-04). The deterministic Thens can be measured by scripts, with the probe from part P as the independent oracle, and the agent kept for captures, re-checks and troubleshooting.

**Approach:** Add a scripted runner under `tests/uat/runner/` that executes scenario files with no LLM call: it groups scenarios by launch configuration, launches FreeCAD non-elevated with a temporary `-u` profile and `-M tests/uat/probe`, calls tools over the `:8765` MCP proxy, checks envelope fields, probe assertions, MCP/probe cross-checks and a scripted pixel check on a `cua-driver` window capture, and writes a verdict per scenario with an escalation queue for the agent.

Scope is part R of Story 10.7b (epics.md AC4–AC7). Part S (§9) and part V (replay) stay deferred.

## Decisions

- **D1 — Pilot set.** Part R encodes 10–15 pilot scenarios across 2–3 test cases, covering every check kind and at least one non-default launch configuration. Bulk encoding of TC-01..TC-14 goes with part V.
- **D2 — Golden captures.** The runner compares against a golden PNG when one exists beside a scenario; part R commits none.

## Boundaries & Constraints

**Always:**
- The test-case markdown stays the human-readable source; each scenario file names its `TC-xx-yy` id.
- Verdicts: `PASS` only when every scripted check passes **and** a capture exists; `FAIL` and every probe/MCP disagreement go to the escalation queue with the reason; a disagreement is reported, never retried.
- FreeCAD is started by the runner with `subprocess` (agent shell integrity level); the runner ends only processes it started.
- Preflight refuses to run when another FreeCAD runs or `:8765` is held.
- Runner code imports stdlib, `mcp` and the part P modules `expect`/`snapshot` only; never `freecad_buddy`.

**Never:**
- Call `invoke_menu` except for an allow-listed non-modal path (`View > Visibility > Show All Objects`, `Edit > Recompute`).
- Add a project dependency (PNG decoding uses stdlib `zlib`).
- Add a write or plant endpoint to the probe.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| All checks pass | scenario with envelope, probe and pixel checks; capture taken | `PASS`, capture path recorded | N/A |
| Missing capture | checks pass, capture failed | `ESCALATE` reason `no capture` | N/A |
| Check fails | envelope field differs | `FAIL`, queued with field, expected, observed | N/A |
| Disagreement | MCP volume 6000, probe volume 6200 | `ESCALATE` reason `probe/MCP disagreement` naming both values | not retried |
| Launch groups | 3 scenarios, 2 distinct launch configs | 2 FreeCAD launches, scenarios run inside their group | N/A |
| Invalid scenario | unknown key or missing `id` | run refused before any launch, exit 2 | message names file and key |
| Preflight | FreeCAD already running | refused, exit 2, nothing launched | message names the pid |
| Golden present | `golden.png` beside the scenario | pixel difference measured and reported | missing golden: skipped, not failed |

</frozen-after-approval>

## Code Map

- `tests/uat/probe/{probe_server,snapshot,expect}.py` -- part P oracle; extend `snapshot.read_view` (read-only) with the 3D view rectangle in global device pixels (`graphicsView().mapToGlobal` × device pixel ratio) and, per object with a shape, `screen_center` = `view.getPointOnViewport(bbox centre)` converted to global device pixels (Coin origin is bottom-left: flip Y)
- `docs/references/FreeCAD/src/Gui/View3DPy.cpp:228-233` -- `getPointOnViewport(3D vector) -> pixel coords`
- `tests/uat/probe/run_faults.py` -- precedent for launching FreeCAD with `-M`, `-u`, waiting for the discovery file, ending only its own process
- `_automation/uat/fcb.py:20-26` (gitignored) -- MCP client pattern: `ClientSession` + `mcp.client.streamable_http.streamablehttp_client("http://127.0.0.1:8765/mcp")`
- `src/freecad_buddy/hosts/gui_external/entry.py:79` -- `GET /healthz` gives `freecad_pid`: readiness = `/healthz` names the launched pid
- `cua-driver` CLI: `list_windows`, `set_window_frame {pid, window_id, x, y, width, height}`, `get_window_state {pid, window_id, include_accessibility_tree:false, screenshot_out_file}`; the capture may be downscaled — scale = capture width / window width
- `tests/uat/testcases/TC-02-*.md`, `TC-06-*.md`, `TC-11-*.md`, `TC-14-*.md` -- sources for the pilot scenarios
- `benchmarks/g0/golden-models/` -- open hidden in the GUI; scenarios show them with the allow-listed Show All step first

## Tasks & Acceptance

**Execution:**
- [x] `tests/uat/probe/snapshot.py` (+ tests) -- view rectangle and per-object `screen_center`, `null` when no 3D view -- AC5
- [x] `tests/uat/runner/scenario.py` -- JSON scenario schema and validation: `id`, `tc`, `launch` (env map), `steps` (`mcp` tool+args with `$name` bindings from earlier results; allow-listed `menu`), `expect` (envelope JSON-path checks: equals, approx, regex, absent), `probe` (an `expect.py` expectation), `cross` (MCP path vs probe path), `pixel` (extent/sample checks) -- AC4
- [x] `tests/uat/runner/launch.py` -- preflight; group by launch config; launch with env, `-M`, temp `-u`; readiness via `/healthz` pid and probe discovery; teardown ends its process and waits for `:8765` to free -- AC7
- [x] `tests/uat/runner/mcp_client.py`, `capture.py` -- tool calls returning `structuredContent`; fixed window frame then capture to the run folder -- AC4, AC5
- [x] `tests/uat/runner/png.py`, `pixel.py` -- stdlib PNG decode (8-bit RGB/RGBA, all filter types); non-background extent inside the view rectangle (background = per-row colour at the view edges); colour sample at each projected `screen_center`; golden difference when present -- AC5
- [x] `tests/uat/runner/run.py` + `README.md` -- CLI `uv run python tests/uat/runner/run.py <scenarios…> --out <run dir>`; `results.json` and `summary.md` with the escalation queue and its reasons -- AC4, AC6
- [x] `tests/uat/scenarios/*.json` -- 10–15 pilot scenarios per D1, including one disagreement-free cross-check, one pixel check, one non-default launch (`FREECAD_BUDDY_SCRIPT_EXEC=0`) -- AC4
- [x] `tests/external/test_uat_runner.py` -- every I/O matrix row with fake transport, fake probe and synthetic PNGs; static check that runner files never call `invoke_menu` outside the allow-list and never import `freecad_buddy` -- AC4–AC7

**Acceptance Criteria:**
- Given the pilot set on FreeCAD 1.1.4 with no other FreeCAD running, when `run.py` runs, then every scenario gets a verdict, each `PASS` has a capture, and `summary.md` lists the escalation queue.
- Given a scenario whose MCP value is edited to disagree with the probe, when it runs live, then it is `ESCALATE` with both values and was executed once.
- Given the run, when it ends, then no FreeCAD started by the runner remains, `:8765` is free, and the developer's `user.cfg` is unchanged.

## Implementation Notes

- Capture model measured on FreeCAD 1.1.4, ratio 1.25: a 1600 x 1000 window (`list_windows`) gives a 1568 x 979 capture; capture = (global device px - window origin) x capture/window size. The probe `rect` (`mapToGlobal(rect().topLeft())` x ratio, then `getSize()`) and `screen_center` land on the model within 1-2 px.
- The 3D view holds the navigation cube, the corner axis and the Tasks overlay (Part Design is the start workbench in a fresh `-u` profile). The extent is the connected set of solid 8 px blocks (60 % non-background) seeded at each sampled `screen_center`; the overlay's 1-2 px lines never make a block solid. Background is flat (247) on 1.1.4; the per-row edge rule also covers a gradient.
- `invoke_menu` answers `delivery: foreground, effect: unverifiable`, and a refusal (`menu_path_unavailable`) exits 0 with `"status": "refused"`, not `isError`. `capture.cua` raises on both; the runner confirms Show All through the probe (every shape object of the active document visible within 5 s), else the step raises and the scenario is `ESCALATE`.
- The runner cannot press the GUI Fit All toolbar button (not a menu path, so outside the allow-list). Added the optional scenario key `agent_check`: a scenario with one is never `PASS`; it is `ESCALATE` with that text. TC-02-15, TC-02-16 and TC-02-17 frame through Fit All and carry it.
- Product finding, not fixed here: the first `query_capabilities` in a GUI session leaves FreeCAD with no active 3D view (probe `view: null`; `View > Visibility` then refuses with `menu_path_unavailable`). `shim.capability_banner` opens probe documents without `hidden=True` (`usecases/shim.py:85,200,227`). TC-11-17 is `FAIL` on it (`pixel view: expected "a 3D view", observed null`) while its capture shows the box framed.
- Pilot: 12 scenarios (TC-02 x7, TC-11 x2, TC-14 x3), one `FREECAD_BUDDY_SCRIPT_EXEC=0` group. Live run: 8 PASS, 1 FAIL (TC-11-17, product finding above), 3 ESCALATE (`agent_check`); about 90 s. An edited TC-02-04 whose cross compares the box MCP volume with the sphere probe volume is `ESCALATE` naming 6000.0 and 4188.79, each step run once. After every run: no FreeCAD, `:8765` free, developer `user.cfg` SHA-256 unchanged. `run_faults.py` after the snapshot change: 5/5 detected, 0/2 false alarms. `tests/external`: 1582 passed, 4 skipped.

- Review patches (pass 1): findings 1-10, 12, 13, 16, 17, 19 and 21 applied. `results.json` is now `{"run": metadata, "scenarios": [...]}`; exit codes 0 (all ran, no FAIL), 1 (a FAIL), 2 (refused before launch), 3 (a group failed to launch or tear down). `test_uat_runner.py` grew from 35 to 86 tests. After the patches: `tests/external` 1633 passed, 4 skipped; ruff clean.
- Live pilot after the patches (two runs): 7 PASS, 1 FAIL (TC-11-17, product defect deferred), 4 ESCALATE, no run errors, clean teardown, `user.cfg` unchanged. Three ESCALATE are the `agent_check` Fit All scenarios. The fourth is an intermittent `cua-driver invoke_menu` refusal (`menu_path_unavailable`) on the allow-listed Show All step: TC-02-02 in one run, TC-14-02 in the other; both passed in earlier runs with the same steps. The runner reports it as ESCALATE with no retry, as designed.

## Spec Change Log

## Review Triage Log

| # | Layer | Finding | Verdict | Evidence | Route |
|---|-------|---------|---------|----------|-------|
| 1 | blind, verification, edge | `_judge`/`_golden` raise outside `try`; the group aborts and later scenarios read "launch group raised" | medium | `run.py:320-322`; `run()` catch at `:342-344` uses `setdefault` | patch |
| 2 | blind, edge | view box not clamped to the capture: negative x wraps, x past width raises | medium | `pixel.py:141`; `png.py:23-25` | patch |
| 3 | blind, verification, edge | teardown `LaunchError` (`:8765` still held) is dropped; port checked before the first group only | medium | `launch.py:137`; `run.py:344` `setdefault`; `preflight` runs once | patch |
| 4 | blind, edge | validation misses: uncompilable regex, wrong-typed `approx`/`tolerance`/`absent`, missing or non-UTF-8 file, non-string `cross` path, non-list `menu`, named menu step, empty folder, empty `agent_check` | medium | `scenario.py:135,147-169,206,211-233`; I/O row requires exit 2 before launch | patch |
| 5 | blind, edge | preflight does not check `FREECAD_EXE`, `cua-driver`; `tasklist` failure escapes as a traceback | low | `launch.py:61`; `run.py:395-399` | patch |
| 6 | edge | a run where every group failed to launch exits 0 | medium | `run.py:411` returns 1 only on `FAIL` | patch |
| 7 | blind, edge | calls after the MCP serve task died block 140 s each | low | `mcp_client.py:82-85` | patch |
| 8 | blind | `check_pixel` ignores `clipped`; hidden or clipped views get pixel checks | medium | `run.py:189`; probe reports `clipped` | patch |
| 9 | blind, edge | `tc-11-01` and `tc-02-17` call `query_capabilities` before Show All, so they pass only after earlier scenarios | low | scenario step order; product defect in Implementation Notes | patch |
| 10 | blind | bbox-centre sample is background for hollow or concave parts | low | `snapshot.py:98`; not documented | patch (README limit) |
| 11 | blind | partly encoded TCs look complete | low | scenario titles already say "(GUI proxy part)" | reject |
| 12 | verification, blind | untested: `check_expect` approx/regex/absent/`$ref`, view `None` → FAIL, cross with missing values, `launch_environment`, `main` exit codes and files, `to_result` fallback, `stop`, `wait_until_ready` pid match | medium | no hits in `test_uat_runner.py` (layer searches) | patch |
| 13 | blind | `results.json` has no run metadata (commit, addon path, FreeCAD version, times) | medium | `run.py:403` writes a bare list; a verdict cannot be tied to the code it tested | patch |
| 14 | blind, edge | spec drift (Code Map TC-06, background wording, `golden.png` name, `agent_check` narration) | low | fix edits this build's spec; `<stem>.golden.png` sits beside the scenario as the matrix says | reject |
| 15 | blind | committed pilot always exits 1 because TC-11-17 fails | medium | product defect: `shim.py:85,200,227` open probe documents without `hidden=True`; runner verdict is correct | defer (product) |
| 16 | blind | TC-02-17 regex matches the C++ `ios_base` text | low | `tc-02-17.json`; prefix is enough | patch |
| 17 | blind | `summary.md` breaks on `|` or newlines in reasons | low | `summary()` writes text unescaped | patch |
| 18 | edge | reset failure reads "step 0 raised" | low | message only | reject |
| 19 | edge | rerun into the same `--out` can judge a stale capture | low | `run.py:310-318`; direct `unlink` | patch |
| 20 | edge | readiness before the main window is on screen | maybe-false | two live runs captured the main window | reject (low if true) |
| 21 | edge | discovery `unlink` race skips the port wait | low | `launch.py:131-133`; `missing_ok` | patch |
| 22 | edge | generic runner module names in `sys.modules` | low | no collision found; churn | reject |

## Design Notes

Capture geometry: the probe reports the view rectangle and projected points in global device pixels; `list_windows` gives the window bounds in desktop pixels; the capture is the window downscaled by `capture width / window width`. One monitor only.

Pixel extent: FreeCAD's default background is a vertical gradient, so "background" is taken per row from the view's left and right edge pixels; a pixel differing by more than a set threshold counts as geometry.

## Verification

**Commands:**
- `uv run pytest tests/external/test_uat_runner.py tests/external/test_uat_probe.py` -- expected: all pass
- `uv run pytest tests/external` -- expected: no new failure
- `uv run ruff check .` -- expected: clean
- `uv run python tests/uat/runner/run.py tests/uat/scenarios --out <scratch run dir>` -- expected: a verdict per pilot scenario, captures present, exit 0 when no FAIL

**Manual checks:**
- Read each pilot capture and confirm the verdict matches the pixels; read `summary.md`.
