# UAT run 2026-09-14-01 — Epic 4 (TC-16 TechDraw capability boundary)

Executed by the agent against the live application, unattended, while the operator was away.

## Environment

| Item | Value |
| --- | --- |
| GUI | FreeCAD **1.1.1**, `C:\Program Files\FreeCAD 1.1\bin\freecad.exe`, pid 24072 |
| Headless (H1) | FreeCAD **1.1.0**, micromamba `fcb` env with the documented `PYTHONPATH` patch |
| Addon | junction `%APPDATA%\FreeCAD\v1-1\Mod\FreeCADBuddy\freecad_buddy` → repo `src\freecad_buddy` |
| Bridge | RPC listener `127.0.0.1:56578`; MCP proxy auto-spawned on `127.0.0.1:8765` (pid 25912) |
| cua-driver | daemon pid 20284, interactive SessionId 1 |
| Tree | working tree at baseline `273413a` + uncommitted epic-4 work |

## Preconditions

All met before the first scenario:

- No FreeCAD process running at start — the pre-existing instance (pid 1456) was shut down, and its
  orphaned MCP proxy (pid 28352) was killed because it outlived its parent and still held `:8765`.
- `:8765` free before launch, then re-occupied by the addon's own freshly spawned proxy.
- `document_list` reported `0 open document(s).` on the fresh instance.
- `$RUN_DIR/evidence/` created.

## Results

| Scenario | Verdict | Evidence |
| --- | --- | --- |
| TC-16-01 headless boundary | **PASS** | `tc-16-01-import.txt`, `tc-16-01-app-module.txt`, `tc-16-01-probe.txt` (6/6 tests OK) |
| TC-16-02 GUI exposes page export | **PASS** | `tc-16-02-gui-import.txt`, `tc-16-02-startup.png` |
| TC-16-03 GUI/headless projection agreement | **NOT RUN** | see below |
| TC-16-04 matrix vs decision 016 | **PASS** | `tc-16-04-matrix.md` |

### TC-16-01 — PASS

A fresh `FreeCADCmd` process raises `ImportError: Cannot load Gui module in console application.`
on `import TechDrawGui` (exit 1), while `import TechDraw` succeeds in the same interpreter — so the
failure is Gui-specific, not a broken environment. The App module registers **no** `exportPage*`
name (`[]`) and does expose `projectToSVG`, `viewPartAsSvg`, `makeExtentDim`, `makeDistanceDim` and
`writeDXFPage`. The `HeadlessTechDrawBoundaryTest` suite ran 6/6 OK, including the assertion that a
30 × 20 × 10 block viewed down Z projects to a 30 × 20 silhouette — a non-empty SVG alone is not
accepted as proof.

### TC-16-02 — PASS

The load-bearing other half, and the one the headless probe structurally cannot observe. Inside a
real FreeCAD 1.1.1 GUI process, `import TechDrawGui` **succeeds** from
`C:\Program Files\FreeCAD 1.1\lib\TechDrawGui.pyd` and exposes both `exportPageAsSvg` and
`exportPageAsPdf`. In that *same process* the App module still reports no `exportPage*` name. The
boundary is therefore between modules, not between processes.

The startup screenshot was read and judged: a genuine FreeCAD 1.1.1 main window with the Part Design
workbench and Start page, not a splash screen or an error dialog.

### TC-16-03 — NOT RUN

Honest gap. The scenario needs a `DrawPage` + `DrawViewPart` built inside the GUI and
`TechDraw.project(...).BoundBox` compared against the headless measurement. Driving FreeCAD's Python
console through the accessibility tree did not resolve within a reasonable attempt budget: the
`View → Panels` path is not exposed as UIA menu children until the popup renders, and the Macro menu
behaved the same way. The GUI-side import in TC-16-02 was obtained instead by launching FreeCAD with
a macro argument, which answers TC-16-02 but not the projection-agreement question.

What is **not** claimed as a result: that the GUI and headless projections agree. The headless side
is measured (probe test asserts the 30 × 20 extent); the GUI side is not.

### TC-16-04 — PASS

Every row of decision 016's capability table matches the installed builds on both legs. No
divergence, so no correction to the decision note is required and story 4.3's design premise holds.

## Defects found

None from TC-16 itself. One environment observation worth recording:

- **The MCP proxy outlived its parent FreeCAD process.** After the pre-existing FreeCAD (pid 1456)
  was terminated, `pythonw` pid 28352 still held `:8765` in LISTENING state and had to be killed
  before a clean relaunch. `CLAUDE.md` §16 states both the listener and the proxy "are torn down on
  FreeCAD quit". A force-kill is not a graceful quit, so this may be correct behaviour under
  `Stop-Process`; it is recorded rather than filed, because the graceful path was not tested.

## Scope note

Epic 4 registers **no new MCP tool** — `techdraw_for_judge`, `verify_visual` and the designer loop
are use cases and benchmark code, not entries in `tool_specs()`. UAT for this epic therefore
validates the capability boundary the epic's design rests on, not a tool surface. The four Epic 4
rows in `APPENDIX-A-deferred-coverage.md` remain correct: no tool ships.
