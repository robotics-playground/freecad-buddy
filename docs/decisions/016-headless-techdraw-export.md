# 016 — Headless TechDraw Export: Page Export is GUI-Only

## Decision

**A headless FreeCAD process cannot export a TechDraw page.** Story 4.3 must compose the judge's
drawing sheet from **view-level SVG** returned by the `TechDraw` App module, and must not call a
page exporter.

The capability boundary, read from the vendored FreeCAD source:

| Entry point | Module | Registered at | Available headless |
| --- | --- | --- | --- |
| `exportPageAsPdf(DrawPageObject, FilePath)` | `TechDrawGui` | `docs/references/FreeCAD/src/Mod/TechDraw/Gui/AppTechDrawGuiPy.cpp:56` | **No** |
| `exportPageAsSvg(DrawPageObject, FilePath)` | `TechDrawGui` | `AppTechDrawGuiPy.cpp:59` | **No** |
| `export(...)` (FC Gui exporter hook) | `TechDrawGui` | `AppTechDrawGuiPy.cpp:53` | **No** |
| `viewPartAsSvg(DrawViewPart)` | `TechDraw` | `docs/references/FreeCAD/src/Mod/TechDraw/App/AppTechDrawPy.cpp:138` | Yes |
| `projectToSVG(TopoShape, direction, ...)` | `TechDraw` | `AppTechDrawPy.cpp:170` | Yes |
| `writeDXFPage(page, filename)` | `TechDraw` | `AppTechDrawPy.cpp:144` | Yes (DXF, not raster/SVG) |
| `makeExtentDim(DrawViewPart, [edges], direction)` | `TechDraw` | `AppTechDrawPy.cpp:150` | Yes |
| `makeDistanceDim(DrawViewPart, dimType, fromPoint, toPoint)` | `TechDraw` | `AppTechDrawPy.cpp:153` | Yes |

Both page-to-image exporters are `add_varargs_method` calls inside
`Py::ExtensionModule<Module>("TechDrawGui")` (`AppTechDrawGuiPy.cpp:46`). The headless module is a
separate `Py::ExtensionModule<Module>("TechDraw")` (`AppTechDrawPy.cpp:124`) and registers no
`exportPage*` name at all.

## Rationale

`verification-design.md` §7a assumes the judge input is produced by "export page to PNG/SVG". No
headless entry point provides that. The two that do live in the **Gui** module, which needs a Qt
application and a `ViewProviderPage` — `exportPageAsSvg` reaches
`TechDrawGui::PagePrinter` through the page's view provider, which a headless document does not
build.

What headless *does* give is enough to build the judge's input a different way:

- `projectToSVG(shape, direction)` returns an SVG string for a projection of a raw `TopoShape`.
  It needs no `DrawPage`, no `DrawViewPart`, and no document object — the shape and a direction
  are the whole input. Three calls at three directions give the front/top/right projections the
  gate's standard visual set asks for.
- `viewPartAsSvg(DrawViewPart)` returns the edges of a *built* `DrawViewPart` as SVG, for the
  path that does create document objects.
- `makeExtentDim` / `makeDistanceDim` create real dimension objects on a `DrawViewPart`, so
  dimension callouts remain reachable without the GUI. They return **different classes**:
  `makeExtentDim` yields a `TechDraw::DrawViewDimExtent` and `makeDistanceDim` a
  `TechDraw::DrawViewDimension` (measured under `FreeCADCmd`, FreeCAD 1.1.1, Libs
  1.1.1R20260414). 4.3 must read both classes, not assume one.

The whole headless path — `DrawPage`, `DrawSVGTemplate`, `DrawViewPart`, both dimension helpers,
and `viewPartAsSvg` over the built view — was driven end to end under `FreeCADCmd` and works. Only
the *export* of the assembled page is missing.

So the page is a composition problem, not a capability gap: 4.3 places the three view SVG strings
onto one SVG canvas itself, adds the dimension annotations, and rasterizes that canvas. This is
strictly more work than calling one exporter, and the work belongs in 4.3's design rather than
being discovered halfway through it.

## Consequences

- **Story 4.3 owns an SVG compositor.** `techdraw_for_judge` builds the sheet; it cannot delegate
  sheet layout to FreeCAD. The sheet's coordinate frame, scale, and view placement become 4.3's
  contract, not FreeCAD's.
- **An empty SVG is a real, silent outcome — 4.3 must treat it as an error.** Measured in the GUI
  during the TC-16 UAT run (`tests/uat/run/2026-09-13-07/bugs.md`, R3-01): a macro that created a
  `DrawViewPart`, called `doc.recompute()`, and read `viewPartAsSvg` in the same pass got an
  **empty string**, while a later pass over the same unchanged view got 308 bytes of real path
  geometry. `DrawViewPart` geometry is built asynchronously in the GUI, and neither `recompute()`
  returning nor `view.State == ['Up-to-date']` is a sufficient signal — the state already read
  up-to-date in the failing pass. An empty SVG raises nothing, so `techdraw_for_judge` would
  silently hand the judge a blank sheet and fail a correct part for a reason no assertion reports.
  The headless path did not show this.
- **Rasterizing the composed SVG is a separate dependency question.** The judge needs a raster at
  ≥2048 px width. FreeCAD's headless leg offers no SVG rasterizer; 4.3/4.4 must name one
  (Qt `QSvgRenderer` where Qt is importable, or an external converter) and record the choice.
- **The GUI leg is not the fallback.** The Phase-4 headless service (Epic 5) re-executes the visual
  verdict in job delivery, so a GUI-only drawing path would make the service unable to reproduce
  its own verdict. Headless composition is the only path that works on both legs.
- **`writeDXFPage` is headless but useless here.** A judge reads a raster image; DXF is a vector
  interchange format with no rendering. It is listed for completeness, not as an option.
- **The boundary is asserted, not asserted-in-prose.** `tests/infc/test_techdraw_probe.py` runs
  under `FreeCADCmd` and fails if `TechDrawGui` becomes importable in a fresh console process, if
  the headless module gains an `exportPage*` name, if `projectToSVG` / `viewPartAsSvg` stop
  returning non-empty SVG, or if the dimension helpers disappear. A FreeCAD upgrade that moves the
  boundary breaks that test rather than silently invalidating this note.
- **`TechDrawGui`'s importability is process-state dependent — do not test it in-process.**
  Measured while writing the probe: in a bare `FreeCADCmd` process `import TechDrawGui` raises
  `ImportError: Cannot load Gui module in console application`, but in a process that has already
  run the rest of `tests/infc` the same import behaves differently. The trigger is
  `adapters/render_probe.py:83-88`, which imports `FreeCADGui` and calls `setupWithoutGUI()`; any
  render test running earlier initializes the Gui layer in-process. The probe therefore runs that
  check in a fresh subprocess. The order-independent fact, and the one this decision actually
  rests on, is the second assertion: the headless `TechDraw` App module registers **no
  `exportPage*` name at all**, so there is no headless page exporter to call however the Gui
  module behaves in a given process.
- **`setupWithoutGUI()` is NOT a headless route to page export — it kills the interpreter.**
  Measured directly on FreeCAD 1.1.1 by logging to a file before and after each step, because the
  failure produces no traceback to read:

  1. bare `import TechDrawGui` → `ImportError: Cannot load Gui module in console application`
  2. `FreeCADGui.setupWithoutGUI()` → returns normally
  3. `import TechDrawGui` again → **the process terminates mid-statement**. No exception is
     raised: a `try/except BaseException` around it never runs, and the line after it never
     executes. The interpreter exits 0 on 1.1.1 (the H1 1.1.0 leg was observed exiting 127), so
     the exit code cannot be relied on to detect it either.

  So "bring the Gui layer up headless, then export a page" is not an available fallback, and a
  test that pops `TechDrawGui` out of `sys.modules` and retries the import would take the whole
  suite down rather than fail one case. Story 4.3 must not treat "the Gui module imported, so I
  can export a page" as a usable signal.

## Alternatives considered

**Run the GUI under a virtual framebuffer (Xvfb) and call `exportPageAsSvg`.** A real X display
with the full Qt GUI process, which is the smallest code change on Linux CI. Rejected as the
primary path: it needs a display server on every leg including the Phase-4 service host, it pulls
the whole Qt GUI stack into a service that otherwise needs none, and Windows has no Xvfb
equivalent — the operator's own environment is Windows. It is **not** exercised anywhere today:
`tests/uat/testcases/TC-16-techdraw-capability-boundary.md` drives the ordinary Windows GUI, not a
framebuffer, so this alternative remains untested and is recorded as rejected rather than as a
standby.

Note what this alternative is **not**: it is not `FreeCADGui.setupWithoutGUI()` inside a console
process. That path is measured above and terminates the interpreter on the subsequent
`TechDrawGui` import. Xvfb means a genuine display server hosting a genuine GUI process; there is
no measured way to reach `exportPageAsSvg` from `FreeCADCmd`.

**Skip drawings and judge the 3D renders only.** Removes the dependency entirely. Rejected because
the adopted gate criteria include the dimensioned drawing in the judge's standard input set
(epic-4-context.md, G3.7), and the wrong-dimension-callout fault case exists specifically to prove
the judge reads callouts. Dropping drawings would delete a planted fault the suite is measured on.
