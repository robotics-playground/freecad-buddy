# Scripted UAT runner

Runs UAT scenario files with no LLM call. It starts its own FreeCAD, calls tools over the `:8765`
MCP proxy, and checks the results against the UAT probe (`tests/uat/probe/`), which reads
FreeCAD directly. The agent gets only the escalation queue: failed checks, probe/MCP
disagreements, missing captures and the Thens a script cannot judge.

The test-case markdown in `tests/uat/testcases/` stays the human source. A scenario file encodes
the scripted Thens of one `TC-xx-yy` scenario.

## Run

```powershell
uv run python tests/uat/runner/run.py tests/uat/scenarios --out <run dir>
```

Arguments are scenario files or folders of `*.json`.

| Exit code | Meaning |
|-----------|---------|
| 0 | every scenario ran and none is `FAIL` (`PASS` and `ESCALATE` only) |
| 1 | a scenario is `FAIL` |
| 2 | the run was refused before any launch: invalid scenario or failed preflight |
| 3 | a launch group failed: it did not launch (its scenarios are not run) or its teardown failed (FreeCAD or `:8765` may be left behind). 3 wins over 1 |

The runner tests the **installed** addon: the `Mod/FreeCADBuddy` folder of the FreeCAD user
app data, not the working tree. In a dev install its `freecad_buddy` package is a junction to
`src/freecad_buddy`; with a built copy or a release zip, source edits do not reach the run.
`results.json` records which addon ran.

1. **Validate.** Every scenario is loaded first. An unknown key, a missing `id`, a reference to
   an unknown step or a menu path outside the allow-list stops the run with exit 2. The message
   names the file and the key.
2. **Preflight.** The run stops with exit 2 when `FREECAD_EXE` is not a file, `cua-driver` is
   not on `PATH` or its daemon does not answer `cua-driver status`, `tasklist` fails, a FreeCAD
   process runs (the message names its pid) or `127.0.0.1:8765` is held. Each group launch
   repeats the FreeCAD and `:8765` check; a failure there is a launch failure (exit 3).
3. **Group.** Scenarios with the same `launch` map share one FreeCAD.
4. **Launch.** Per group: `freecad.exe -M tests/uat/probe -u <temporary user.cfg>`, started
   with `subprocess` at the runner's integrity level. Inherited `FREECAD_BUDDY_*` variables are
   removed, `FREECAD_BUDDY_AUDIT_LOG` is `<run dir>/audit-group-<n>.jsonl`, then the group's
   `launch` map is applied. The temporary profile keeps the developer's `user.cfg` unchanged.
   FreeCAD is ready when `GET /healthz` names its pid and the probe discovery file exists. The
   main window is set to a fixed frame (`capture.WINDOW_FRAME`).
5. **Per scenario.** Close every open document, run the steps, take a probe snapshot, capture
   the window to `<run dir>/captures/<id>.png`, then judge the checks.
6. **Teardown.** Close every document, end the FreeCAD the runner started, delete its probe
   discovery file, and wait until `:8765` is free. The runner never ends a process it did not
   start.

Windows only: FreeCAD is found with `tasklist`, the probe discovery file under `%APPDATA%`. Set
`FREECAD_EXE` to use another `freecad.exe`. `cua-driver` must be on `PATH`, with its daemon
started from the agent shell (see the GUI harness standard).

## Scenario file

The full schema is the docstring of `scenario.py`. Example (shortened from `tc-02-02.json`):

```json
{
  "id": "TC-02-02",
  "tc": "TC-02",
  "title": "Open a golden model and read its tree",
  "steps": [
    {"name": "open", "mcp": "document_open",
     "args": {"path": "$PROJECT_ROOT/benchmarks/g0/golden-models/box-10-20-30.FCStd"}},
    {"name": "mass", "mcp": "query_mass_properties",
     "args": {"doc": "$open.structured_content.doc", "object": "Box"}},
    {"menu": ["View", "Visibility", "Show All Objects"]},
    {"name": "fit", "mcp": "view_fit_viewport", "args": {"doc": "$open.structured_content.doc"}}
  ],
  "expect": [{"step": "fit", "path": "status", "equals": "OK"}],
  "probe": {"documents": {"box_10_20_30": {"objects": {"Box": {"visibility": true}}}}},
  "cross": [{"mcp": "mass.structured_content.volume.value",
             "probe": "documents.box_10_20_30.objects.Box.shape.volume", "tolerance": 0.01}],
  "pixel": {"samples": ["box_10_20_30.Box"], "extent": {"min_fraction": 0.5, "inside": true}}
}
```

- A step result is the tool's `structuredContent`. A tool with no output schema
  (`query_tree_summary`) and an MCP schema refusal (`Input validation error: ...`) give
  `{"text": ..., "is_error": ...}`.
- `$name.<path>` reads an earlier step result; `$PROJECT_ROOT` and `$RUN_DIR` are absolute
  paths with forward slashes.
- `menu` accepts only `View > Visibility > Show All Objects` and `Edit > Recompute`. Both are
  non-modal. `invoke_menu` delivers through the foreground and does not confirm its effect, so
  the runner confirms Show All through the probe: every shape object of the active document
  must read visible within 5 s, else the step raises.
- `pixel.samples` reads the pixel at the projected centre of the object's bounding box. For a
  hollow or concave part (tube, ring, L-bracket, a part with a through-hole) that point can be
  background or another face behind the part. Such a scenario must not use a centre sample, and
  so cannot use `extent` either.
- `agent_check` names a Then the script cannot judge. The runner has no GUI **Fit All** button,
  so a test case that frames through that button (TC-02-15, TC-02-16, TC-02-17) carries an
  `agent_check`, and its capture is unframed.

## Checks and verdicts

| Check | Source | A failure is |
|-------|--------|--------------|
| `expect` | JSON path in a step result: `equals`, `approx` + `tolerance`, `regex`, `absent` | `FAIL` |
| `probe` | `tests/uat/probe/expect.py` expectation against the snapshot after the last step | `FAIL` |
| `cross` | a step value against a snapshot value | a missing value is `FAIL`; a difference is `ESCALATE` |
| `pixel` | samples and extent on the capture | `FAIL` |

| Verdict | When |
|---------|------|
| `PASS` | every check passes and a capture exists |
| `FAIL` | a check fails |
| `ESCALATE` | a probe/MCP disagreement, a step or the snapshot raised, no capture, or an `agent_check` |

The runner never retries a step or a check. A check that raises (for example an unreadable
golden PNG) is an `ESCALATE` of that scenario only; the group goes on. Every non-`PASS` scenario
is in the escalation queue of `summary.md` with its reasons; group failures are listed under
`Run errors`.

`results.json` is `{"run": ..., "scenarios": [...]}`:

- `run`: `git_commit`, `git_dirty`, `freecad_exe`, `freecad_version` (from the probe),
  `addon` (`path` of `Mod/FreeCADBuddy`, `exists`, `linked` when its `freecad_buddy` package
  is a junction or symlink, and its `target`), `started`, `ended`, `groups` (per group: `launch`,
  `scenarios`, `freecad_pid`, `freecad_version`, `addon`, `error`) and `errors`.
- `scenarios`: per scenario, each step's args and result, the probe snapshot, the findings
  (`field`, `expected`, `observed`), the pixel measurement, the golden comparison, the verdict
  and its reasons. A scenario of a group that failed to launch has `not_run: true`.

## Pixel checks

The probe gives the 3D view rectangle and each object's `screen_center` in global device
pixels. `list_windows` gives the window bounds in desktop pixels. The capture is that window,
scaled by `capture width / window width` (measured: a 1600 x 1000 window gives a 1568 x 979
capture). One monitor only.

- **Background** is taken per row from the view's left and right edge pixels, so a vertical
  gradient reads as background. A pixel is non-background when a channel differs by more than
  `pixel.GEOMETRY_THRESHOLD`.
- **View:** a `clipped` view (or one whose `clipped` is `null`: hidden or minimized) is a
  finding, and a view rectangle not wholly inside the capture is the finding
  `view rect outside capture`; in both cases nothing else is measured.
- **Sample:** the pixel at each `screen_center` must be non-background.
- **Extent:** the view also holds the navigation cube, the corner axis and the Tasks overlay.
  The view is cut into 8 px blocks; a block is solid when 60 % of its pixels are non-background.
  The extent is the connected set of solid blocks that holds a sample. Overlay text and borders
  are 1-2 px lines and never make a block solid. `min_fraction` is the larger of extent width /
  view width and extent height / view height. `inside: true` requires that the extent does not
  reach the outermost block row or column.
- **Golden:** when `<scenario file stem>.golden.png` exists beside the scenario, the fraction of
  view pixels that differ is reported in `results.json`. It is not a check. A missing golden is
  skipped.

## Files

| File | Role |
|------|------|
| `run.py` | CLI, scenario execution, verdicts, `results.json` and `summary.md` |
| `scenario.py` | schema, validation, `$name` references, JSON paths |
| `launch.py` | preflight, launch groups, readiness, teardown, probe snapshot |
| `mcp_client.py` | synchronous MCP client for `http://127.0.0.1:8765/mcp` |
| `capture.py` | `cua-driver`: main window, fixed frame, capture, allow-listed menu |
| `png.py` | stdlib PNG decoder: 8-bit RGB or RGBA, every filter type |
| `pixel.py` | capture placement, samples, extent, golden difference |

The runner imports the standard library, `mcp` and the probe modules `expect` only; never
`freecad_buddy`.

Tests that need no FreeCAD: `uv run pytest tests/external/test_uat_runner.py`.
