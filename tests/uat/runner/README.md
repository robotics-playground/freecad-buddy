# Scripted UAT runner

Runs UAT scenario files with no LLM call. It runs inside the `fcb-desktop` container
(`tests/close-loop/README.md`), starts its own FreeCAD there, calls tools over the container's
`:8765` MCP proxy, and checks the results against the UAT probe (`tests/uat/probe/`), which reads
FreeCAD directly. The agent gets the escalation queue (failed checks, probe/MCP disagreements,
missing captures and the Thens a script cannot judge) and the review set: the captures it reads
(`tests/uat/test-plan.md` §9). The scripted pixel check grades every other capture.

The test-case markdown in `tests/uat/testcases/` stays the human source. A scenario file encodes
the scripted Thens of one `TC-xx-yy` scenario.

## Run

```bash
docker exec -u cua fcb-desktop fcb-py /repo/tests/uat/runner/run.py /repo/tests/uat/scenarios \
    --out /repo/tests/uat/run/<run>/runner [--seed <n>]
```

`fcb-py` is the container's helper: the AppImage's Python with the pinned `mcp` and the desktop
session's `DISPLAY` and D-Bus address (`tests/close-loop/README.md`). The container sees the repo
read-only at `/repo` and writes `tests/uat/run/` there, so `--out` is a container path and the run
folder appears on the host. Stop the container FreeCAD first (`fcb-freecad stop`): a running
FreeCAD fails the preflight.

Arguments are scenario files or folders of `*.json`. `--seed` sets the seed of the review sample,
for debugging and replay only; a gate run omits it and the runner draws a seed. A past seed draws
the same review set again only for the same scenarios with the same verdicts. A value that is not
an integer stops the run with exit 2 before any launch.

| Exit code | Meaning |
|-----------|---------|
| 0 | every scenario ran and none is `FAIL` (`PASS` and `ESCALATE` only) |
| 1 | a scenario is `FAIL` |
| 2 | the run was refused before any launch: invalid scenario or failed preflight |
| 3 | a launch group failed: it did not launch (its scenarios are not run) or its teardown failed (FreeCAD or `:8765` may be left behind). 3 wins over 1 |

The runner tests the **installed** addon: the `Mod/FreeCADBuddy` folder of the container's
FreeCAD user data (`~/.local/share/FreeCAD/v1-1/`), which the image builds from `dist/addon/`, not
the working tree. After a change under `src/`, run the build and compose commands of
`tests/close-loop/README.md` again. `results.json` records which addon ran.

1. **Validate.** Every scenario is loaded first. An unknown key, a missing `id`, a reference to
   an unknown step or a menu path outside the allow-list stops the run with exit 2. The message
   names the file and the key.
2. **Preflight.** The run stops with exit 2 when `/opt/freecad/AppRun` is not a file,
   `/usr/local/bin/cua-driver` is not an executable file or its daemon does not answer
   `cua-driver status`, `/proc` cannot be listed, a FreeCAD process runs in the container (the
   message names its pid) or the container's `127.0.0.1:8765` is held. Each group launch repeats
   the FreeCAD and `:8765` check; a failure there is a launch failure (exit 3).
3. **Group.** Scenarios with the same `launch` map share one FreeCAD.
4. **Launch.** Per group: `/opt/freecad/AppRun -M /repo/tests/uat/probe -u <temporary user.cfg>
   -s <temporary system.cfg>`, started with `subprocess` in a new session. Inherited
   `FREECAD_BUDDY_*`, `PYTHONPATH` and `PYTHONHOME` variables are removed,
   `FREECAD_BUDDY_AUDIT_LOG` is `<run dir>/audit-group-<n>.jsonl`, then the group's `launch` map
   is applied. The temporary profile keeps the container user's `user.cfg` unchanged. `AppRun`
   starts `/opt/freecad/usr/bin/freecad` as a child, so FreeCAD is ready when `GET /healthz`
   names a pid below the runner's process and its probe discovery file exists. The main window is
   set to a fixed frame (`capture.WINDOW_FRAME`).
5. **Per scenario.** Close every open document, run the steps, take a probe snapshot, capture
   the window to `<run dir>/captures/<id>.png`, then judge the checks.
6. **Teardown.** Close every document, end the process group of the FreeCAD the runner started,
   delete its probe discovery file, and wait until `:8765` is free. The runner never ends a
   process it did not start.

FreeCAD is found by its command line under `/proc`, and the probe discovery file under
`~/.local/share/FreeCAD/*/fcb-uat-probe/`. `cua-driver` is `/usr/local/bin/cua-driver`; its
daemon is `fcb-cua-serve`, started by supervisord. The menu step resolves the allow-listed path in the element tree and presses the leaf item by
`element_token`: the driver's own menu-path tool refuses FreeCAD's Qt menu bar (`tests/close-loop/README.md`). Container
screenshots use Linux software rendering and Linux fonts: compare them with captures of the
same image only, never with Windows captures.

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
  non-modal. The runner presses the leaf item by its `element_token` (the driver's own menu-path
  tool refuses Qt's menu bar) and does not get a confirmation of the effect, so it confirms Show
  All through the probe: every shape object of the active document must read visible within 5 s.
  A delivery that is refused (`menu_path_unavailable`: the item is missing from a partial tree,
  still disabled after `capture.MENU_ENABLE_S`, or the click is refused) or that the probe does
  not confirm is delivered again, up to `run.MENU_ATTEMPTS` (3) attempts in total. After a refusal
  the runner reads the probe every `run.POLL_S` (0.25 s) for up to 4 polls (1 s) first, so a
  refused delivery that took effect late is not sent twice. The step record in `results.json`
  carries `attempts` and `attempt_log` (why each repeat happened). Three refusals, or three
  deliveries the probe does not confirm, make the scenario `ESCALATE`.
- `pixel.samples` reads the pixel at the projected centre of the object's bounding box. For a
  hollow or concave part (tube, ring, L-bracket, a part with a through-hole) that point can be
  background or another face behind the part. Such a scenario must not use a centre sample, and
  so cannot use `extent` either.
- `agent_check` names a Then the script cannot judge. The runner has no GUI **Fit All** button,
  so a test case that frames through that button (TC-02-15, TC-02-16, TC-02-17) carries an
  `agent_check`, and its capture is unframed.

**First press.** The first press of Show All Objects after the first document opens can change
nothing in the container (measured: a second press 5 s later took effect), so one repeat is normal;
read `attempt_log` before you treat a repeat as a finding.

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

The runner never retries a step or a check; the only repeat is the Show All delivery above. A
check that raises (for example an unreadable golden PNG) is an `ESCALATE` of that scenario only;
the group goes on. Every non-`PASS` scenario is in the escalation queue of `summary.md` with its
reasons; group failures are listed under `Run errors`.

## Agent review set

Paths in `summary.md` and `results.json` are container paths (`/repo/tests/uat/run/<run>/...`); the
same file is at `tests/uat/run/<run>/...` in the repository on the host, which the agent reads.

After the run, `run.mark_review` draws the review set: the captures the agent reads, each with a
complete visual comparison (`tests/uat/test-plan.md` §9). `summary.md` lists it under
`## Agent review` with the sample seed and its source, one line per scenario with its reason and
capture. Each scenario in the set has one reason, checked in this order:

| Reason | Scenarios |
|--------|-----------|
| `fail` | every `FAIL` |
| `escalate` | every `ESCALATE` |
| `no pixel check` | every other scenario whose file has no `pixel` block or no `pixel.samples` |
| `first of TC-xx` | the first `PASS` of each test case by id that is not already in |
| `sample` | `run.SAMPLE_PERCENT` (20 %) of the remaining scenarios, rounded up |

The sample ranks the remaining scenarios by SHA-256 of `"<seed>:<id>"` and takes the first ones,
so one seed draws the same set on any Python version and in any argument order. The scripted
pixel check grades every scenario outside the set on its capture.

`results.json` is `{"run": ..., "scenarios": [...]}`:

- `run`: `git_commit`, `git_dirty`, `freecad_apprun`, `freecad_version` (from the probe),
  `addon` (`path` of `Mod/FreeCADBuddy`, `exists`, `linked` when its `freecad_buddy` package
  is a symlink, and its `target`), `started`, `ended`, `groups` (per group: `launch`,
  `scenarios`, `freecad_pid`, `freecad_version`, `addon`, `error`), `errors`, `sample_seed`
  and `sample_seed_source` (`drawn`, or `given` by `--seed`).
- `scenarios`: per scenario, each step's args and result, the probe snapshot, the findings
  (`field`, `expected`, `observed`), the pixel measurement, the golden comparison, the verdict,
  its reasons and `review` (the review reason, or `null` when the scenario is out of the set).
  A scenario of a group that failed to launch has `not_run: true`.

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
- **Not seen:** a dialog, a wrong shape, a wrong colour, or anything outside the 3D view. Only the
  agent's reads of the review set catch those.

`pixel_faults.py` proves the pixel check's sensitivity (AD-13). It builds synthetic captures in
memory and runs `run.check_pixel` unchanged on each: an empty view, a part clipped at an edge, a
part moved off its sample point and a part too small must each give their finding; a flat and a
gradient background control must give none. It prints the detected and false-alarm counts and
exits 1 on a miss or a false alarm:

```bash
uv run python tests/uat/runner/pixel_faults.py
```

## Replay comparison

`compare.py` compares a runner run with the verdicts of a past agent-run report, for example the
replay of run 2026-10-03-04 (Story 10.7b AC9):

```bash
uv run python tests/uat/runner/compare.py tests/uat/run/2026-10-03-04 <replay run dir>
```

- **Old verdicts** of TC-01..TC-14: `<old run>/evidence/tc-NN-results.json` when it exists, else
  the per-test-case tables of `<old run>/report.md`. A scenario row of that table the parser
  cannot read stops the compare with exit 2; the message names the line.
- **Current ids:** the `### TC-xx-yy:` headings of `tests/uat/testcases/` (`--testcases` for
  another folder).
- **Verdict map:** old `PASS` and `PARTIAL` match runner `PASS`, or `ESCALATE` whose only reason
  is an `agent_check`; old `FAIL` matches runner `FAIL`; old `BLOCKED` and `SKIP` are not
  compared.
- **Notes:** `<replay run dir>/replay-notes.json`, written by the agent, maps an id to
  `coverage` (a not-covered reason, or `not encoded`) for an id the replay did not run, `class`
  for a verdict difference, an `explanation`, and `left_out`: the deterministic Thens a scenario
  file does not encode, each `{"then", "reason"}`, shown in the row as `Not checked: ...`, so a
  `same` row never claims more than was checked. Reasons: `H1 host`, `raw RPC or second
  client`, `process kill or relaunch`, `log or audit read`, `file check`, `GUI action`, `timing
  bound`, `comparison op`. Classes: `product fixed (F-xx, <story>)`, `test case changed (10.7
  edit)`, `runner limit`, `harness`. A value outside these sets stops the compare with exit 2.
- **Output:** `<replay run dir>/replay.md`, one row per old or current id: `same`, `differs`,
  `not covered`, `not encoded` (runner-expressible, not yet encoded), `new` (no old verdict, or
  old `BLOCKED`/`SKIP`) or `removed` (old id with no current scenario). A difference or a
  not-run id with no note is `unexplained`, and the compare exits 1; otherwise 0.

## Files

| File | Role |
|------|------|
| `run.py` | CLI, scenario execution, verdicts, review set, `results.json` and `summary.md` |
| `scenario.py` | schema, validation, `$name` references, JSON paths |
| `launch.py` | preflight, launch groups in the container, readiness, teardown, probe snapshot |
| `mcp_client.py` | synchronous MCP client for the container's `http://127.0.0.1:8765/mcp` |
| `capture.py` | container `cua-driver`: main window, fixed frame, capture, allow-listed menu |
| `png.py` | stdlib PNG decoder: 8-bit RGB or RGBA, every filter type |
| `pixel.py` | capture placement, samples, extent, golden difference |
| `pixel_faults.py` | planted-fault set for the pixel check: detected and false-alarm counts |
| `compare.py` | replay comparison with a past run's verdicts: `replay.md` |

The runner imports the standard library, `mcp` and the probe modules `expect` only; never
`freecad_buddy`.

Tests that need no FreeCAD or container: `uv run pytest tests/external/test_uat_runner.py
tests/external/test_uat_runner_container.py` (the launch logic against a fake `/proc`).
