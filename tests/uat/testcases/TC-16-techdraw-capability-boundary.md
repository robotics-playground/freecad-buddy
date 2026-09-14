# TC-16: Headless TechDraw Capability Boundary

Proves the spike verdict `docs/decisions/016-headless-techdraw-export.md` rests on against the
**running application**, not only against the vendored source. The verdict is a claim about what
FreeCAD exposes where — page export registered in `TechDrawGui` (`AppTechDrawGuiPy.cpp:56,59`) and
therefore unreachable headless, view-level SVG plus dimension helpers registered in the `TechDraw`
App module (`AppTechDrawPy.cpp:138,144,150,153,170`) and therefore reachable. Reading a `.cpp` file
proves what the source says; only running both processes proves what the installed build does.

Story 4.3 must compose its judge sheet from view-level SVG because of this boundary. If the
boundary is wrong, 4.3's whole design is wrong, so it is checked twice: executably under
`FreeCADCmd` (`tests/infc/test_techdraw_probe.py`) and here against the GUI.

The two processes are the point. A scenario run only under `FreeCADCmd` cannot show that
`TechDrawGui` exists *anywhere*, and one run only in the GUI cannot show it is absent headless.
The claim is a difference between them, so both legs are required and neither alone passes.

**Host**: GUI via H2 proxy for TC-16-02 and TC-16-03; `FreeCADCmd` for TC-16-01. TC-16-04 compares
the two, so it needs both.

## Preconditions
- [ ] No FreeCAD process is running at the start
      (verify: `Get-Process FreeCAD,FreeCADCmd -ErrorAction SilentlyContinue` returns nothing)
- [ ] No documents are open once the GUI is started
      (verify: `mcp document_list` reports `0 open document(s).`)
- [ ] FreeCAD 1.1.1 is the build under test
      (verify: the `FreeCAD 1.1.1, Libs: ...` banner printed by `FreeCADCmd`)
- [ ] `cua-driver` daemon is running in an interactive session (verify: `cua-driver status`)
- [ ] `$RUN_DIR` is set to this run's folder under `tests/uat/run/`
- [ ] All file paths used below are absolute — FreeCAD's working directory is not the repo root

---

### TC-16-01: `TechDrawGui` is absent under `FreeCADCmd` and the App module is present

**Priority**: Critical
**Design Ref**: decision 016; `AppTechDrawGuiPy.cpp:56,59`; `AppTechDrawPy.cpp:124,138,170`

**Given** a headless `FreeCADCmd` process with no GUI and no display

**When** `FreeCADCmd tests/run_tests.py` runs the `HeadlessTechDrawBoundaryTest` suite

**Then** `import TechDrawGui` raises `ImportError: Cannot load Gui module in console application`
**in a fresh `FreeCADCmd` subprocess** — verify: read the test output. The freshness matters and is
not a formality: measured during story 4.1, the same import **succeeds** inside a process that has
already run the rest of `tests/infc`, so an in-process check measures test ordering rather than the
build
**And** the headless `TechDraw` module registers no `exportPage*` name — verify:
`test_Should_register_no_page_exporter_...` passes. This is the order-independent assertion and the
one Story 4.3's design rests on: however the Gui module behaves in a given process, there is no
headless page exporter to call
**And** `import TechDraw` succeeds — verify: the entry-point test passes
**And** `TechDraw` exposes `projectToSVG`, `viewPartAsSvg`, `makeExtentDim` and `makeDistanceDim`
  — verify: `test_Should_expose_the_headless_entry_points_...` passes and lists nothing missing
**And** `TechDraw.projectToSVG` returns a non-empty SVG string carrying `<path` geometry for each
of the three orthographic directions — verify: `test_Should_produce_non_empty_svg_...` passes
**And** the projection of a 30 x 20 x 10 block viewed down Z measures 30 mm by 20 mm — verify:
`test_Should_project_the_expected_silhouette_...` passes; a non-empty SVG alone does not prove the
projection carries the block's real extent
**And** the full headless page path builds — `DrawPage`, `DrawSVGTemplate`, `DrawViewPart`, an
extent dimension and a distance dimension — and `viewPartAsSvg` returns non-empty output over the
built view — verify: `test_Should_build_a_view_and_dimension_...` passes

**Cleanup**: none — the test closes its own document.

---

### TC-16-02: `TechDrawGui` IS importable inside the running GUI process

**Priority**: Critical
**Design Ref**: decision 016 ("registered in the **Gui** module")

This is the half the source read cannot settle on its own. If `TechDrawGui` were unavailable in the
GUI too, the boundary would not be GUI-vs-headless at all — it would be a broken install, and the
verdict's reasoning would not hold.

**Given** FreeCAD 1.1.1 GUI is running with the bridge addon started
**And** no document is open

**When** `TechDrawGui` is imported inside the GUI process

**Then** the import succeeds — verify: run the import through the GUI's Python console driven with
`cua-driver` (View > Panels > Python console), and read the console output; an exception text in
the console is a failure
**And** `TechDrawGui` exposes `exportPageAsSvg` and `exportPageAsPdf` — verify: evaluate
`hasattr(TechDrawGui, "exportPageAsSvg"), hasattr(TechDrawGui, "exportPageAsPdf")` in the same
console and read `(True, True)`
**And** *(visual)* the Python console output is captured and read by the agent — verify:
`cua-driver call get_window_state` with
`screenshot_out_file: "$RUN_DIR/evidence/tc-16-02-console.png"`, then `Read` the PNG and confirm
the printed result visually. An MCP response is evidence, not proof; the agent states what it saw.

**Cleanup**: close the Python console panel; leave no document open.

---

### TC-16-03: The GUI produces the same projection the headless path does

**Priority**: High
**Design Ref**: decision 016 Consequences ("Headless composition is the only path that works on
both legs")

If the headless view-level SVG were a degraded or different projection from what the GUI draws,
composing a sheet from it would give the judge a picture the user never sees — and the visual leg
would be judging an artifact rather than the part.

**Given** FreeCAD 1.1.1 GUI is running
**And** a new document holding one 30 x 20 x 10 block, built through the MCP mutation tools

**When** a `DrawPage` with one `DrawViewPart` looking down Z is created in the GUI
**And** `TechDraw.viewPartAsSvg(view)` is evaluated in the GUI's Python console

**Then** the returned SVG is non-empty — verify: read the console output
**And** its projected extent is 30 mm by 20 mm, matching the headless measurement from TC-16-01 —
verify: evaluate `TechDraw.project(body.Shape, App.Vector(0,0,1))[0].BoundBox` in the console and
compare `XLength`/`YLength` against the 30/20 the headless probe asserted
**And** *(visual)* the TechDraw page rendered in the GUI shows the block's rectangular silhouette
in the orientation the numbers describe — verify:
`cua-driver call get_window_state` with
`screenshot_out_file: "$RUN_DIR/evidence/tc-16-03-page.png"`, then `Read` it and judge. The agent
confirms the drawn outline matches the measured extent; a matching number over a blank or wrongly
oriented page is a failure, and only looking catches it.

**Cleanup**: close the document without saving; verify `document_list` reports `0 open document(s).`

---

### TC-16-04: The two legs disagree exactly where the decision says they do

**Priority**: High
**Design Ref**: decision 016 Decision table

**Given** the TC-16-01 headless result and the TC-16-02 GUI result

**When** the two are compared

**Then** no headless entry point named `exportPage*` exists, while `TechDrawGui` exposes both —
verify: evaluate `[n for n in dir(TechDraw) if n.startswith("exportPage")]` in a fresh
`FreeCADCmd` and read `[]`, against TC-16-02's `(True, True)` for
`exportPageAsSvg`/`exportPageAsPdf`. **This is the load-bearing comparison**: it makes "4.3 must
compose a page" a measured conclusion rather than an inference from two separate observations, and
unlike the import check it does not depend on what else the process has loaded
**And** `TechDrawGui` is importable in the GUI and not in a fresh console — verify: TC-16-01's
subprocess check against TC-16-02's GUI import. Treat this as **supporting** evidence only: the
console import succeeds in a process that already loaded the Gui machinery, so it is a statement
about a fresh process, not an invariant of the build
**And** `TechDraw` and its four named entry points are available in **both** — verify: TC-16-01 and
TC-16-03 each exercise them

**If this scenario fails**, `docs/decisions/016-headless-techdraw-export.md` is wrong about the
installed build and Story 4.3's design premise must be reopened before any drawing code is written.
Record the finding in this run's `bugs.md`.

**Cleanup**: shut down every FreeCAD process; verify none remain.
