---
title: 'Story 4.3 — TechDraw Drawing Generator'
type: 'feature'
epic: 4
story: '4-3-techdraw-drawing-generator'
created: '2026-09-14'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
context:
  - '{project-root}/docs/decisions/016-headless-techdraw-export.md'
  - '{project-root}/_bmad-output/planning-artifacts/architecture/architecture-freecad-buddy-2026-07-21/design/verification-design.md'
  - '{project-root}/_bmad-output/implementation-artifacts/epic-4-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The visual judge's standard input set requires dimensioned front/top/right projections,
and no TechDraw code exists. The design assumed a page exporter; decision 016 measured that page
export is registered only in `TechDrawGui` (`AppTechDrawGuiPy.cpp:56,59`) and is unusable headless —
a second import after `setupWithoutGUI()` crashes the process outright (DW-116). So the sheet must be
composed, not exported.

**Approach:** Land `techdraw_for_judge` as a use case that builds the page on a **TempDoc copy**,
generates the three orthographic projections and their dimensions from the part's driving parameters,
composes one SVG sheet from the view-level SVG the headless `TechDraw` module does provide, and
rasterizes it at ≥2048 px. The part document is never touched — its fingerprint must be identical
across the call.

## Boundaries & Constraints

**Always:**
- The drawing is built on a **TempDoc copy** under the reserved name prefix. The part document's
  `fingerprint()` before and after the call must be **byte-identical** — this is the acceptance test,
  not a claim.
- The TempDoc is discarded whether the call succeeds or fails. A failure path that leaks a document
  or a temp file is a defect; temp files belong under the session workdir (`documents.temp_dir()`),
  never the OS temp dir, or nothing sweeps them.
- Dimensions are generated **from the part's named driving parameters and the spec's assertion set**,
  never picked from view geometry. Parameter-sourced dimensions are immune to topological-naming
  drift; geometry-picked ones are not.
- Use only the headless-reachable API measured in decision 016: `TechDraw.projectToSVG`,
  `TechDraw.viewPartAsSvg`, `TechDraw.makeExtentDim`, `TechDraw.makeDistanceDim`. `makeExtentDim`
  returns `DrawViewDimExtent` and `makeDistanceDim` returns `DrawViewDimension` — **different
  classes**; read both, never assume one.
- Never `import TechDrawGui`, and never call `FreeCADGui.setupWithoutGUI()` as a fallback to reach
  it. DW-116 measured that the retry path terminates the process with no traceback.
- The composed sheet's coordinate frame, scale, and view placement are this story's contract, since
  FreeCAD does not lay the sheet out. Record the convention where a reader will find it.
- Rasterization must produce ≥2048 px page width (AD-21). Name the rasterizer explicitly and record
  why it was chosen; if it is an optional dependency, absence must degrade to a clear
  `visual.unavailable`, never a silent smaller image.
- Ring purity: the use case lives in `usecases/`, stdlib + FreeCAD App only, version-sensitive calls
  behind `shim.py`. Qt or any GUI import in `usecases/` is a ring violation `check_imports.py` will
  catch.
- Every document handle is explicit. Never `ActiveDocument` (AD-20).

**Block If:**
- The chosen rasterizer cannot run on both the headless CI leg and the Windows operator machine.
  A sheet that rasterizes on only one leg cannot support Epic 5's headless service, which must
  re-execute the visual verdict. Stop and report rather than shipping a one-leg path.

**Never:**
- Do not implement `verify_visual` or any vision-model call — that is story 4.4.
- Do not raise `_MAX_DIM` in `usecases/screenshot.py` to serve the judge path. Judge images bypass
  the user-facing render budget; they must not widen it for ordinary callers.
- Do not write TechDraw objects into the part document under any circumstance.
- Do not pick dimension values by reading the produced geometry — that would make the drawing agree
  with the part by construction and destroy the cross-check the callouts exist to provide.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | a valid solid with named driving parameters | Three projections + dimensions on a TempDoc; one composed sheet ≥2048 px; TempDoc discarded | N/A |
| Fingerprint purity | any part document | `fingerprint(doc)` identical before and after | Any change is a hard failure |
| Failure mid-build | projection raises partway | TempDoc discarded, no temp file left, error reported | Envelope error; no leak |
| Rasterizer absent | no SVG rasterizer available | `visual.unavailable`, part not done | Clear message naming the missing dependency |
| Part with no parameters | solid without a VarSet/Spreadsheet façade | Dimensions cannot be parameter-sourced → refuse | `INVALID_INPUT`, never geometry-picked fallback |
| GUI module reachable | someone calls `setupWithoutGUI()` first | Still never imports TechDrawGui | Path does not exist in code |

</frozen-after-approval>

## Code Map

- `docs/decisions/016-headless-techdraw-export.md` -- the capability table this story is built on.
  Read it first; it names every reachable and unreachable entry point with file:line.
- `tests/infc/test_techdraw_probe.py` -- the executable proof of that boundary, including a working
  `DrawPage` + `DrawSVGTemplate` + `DrawViewPart` + dimension build under `FreeCADCmd`. This is a
  working example of the headless path, not just a test — read it before writing new code.
- `src/freecad_buddy/usecases/documents.py:36-56` -- `workdir_root()` and `temp_dir()`; every temp
  file must be placed with `dir=temp_dir()` so `sweep_temp_dir()` owns it.
- `src/freecad_buddy/usecases/fingerprint.py` -- `fingerprint(doc)`, the purity oracle for the
  acceptance test.
- `src/freecad_buddy/usecases/screenshot.py:34` -- `_MAX_DIM = 1920`; the user-facing cap this story
  must not raise. Judge images take a separate path.
- `src/freecad_buddy/usecases/shim.py` -- capability probes; the TechDraw availability probe belongs
  here rather than as a bare import in the use case.
- `src/freecad_buddy/adapters/render_probe.py:83-88` -- calls `FreeCADGui.setupWithoutGUI()`. Named
  so you know why the process state hazard exists, not as something to call.
- `benchmarks/g3/judge.py:36` -- `MIN_PAGE_WIDTH_PX = 2048`, the floor the sheet must meet.
- `benchmarks/g3/fault-injection/visual-judge/` -- includes a wrong-dimension-callout case; the
  drawing this story produces is what that fault is planted in.
- `scripts/check_imports.py` -- enforces the ring boundary; run it before claiming done.

## Tasks & Acceptance

**Execution:**
- [x] `src/freecad_buddy/usecases/shim.py` -- add a TechDraw capability probe (module importable,
      required helpers present), so absence degrades cleanly instead of raising mid-build.
- [x] `src/freecad_buddy/usecases/techdraw.py` -- new use case: TempDoc build, three projections,
      parameter-sourced dimensions, guaranteed teardown on both success and failure paths.
- [x] `src/freecad_buddy/usecases/techdraw.py` -- the SVG sheet compositor: place three view SVGs on
      one canvas with a documented frame, scale and placement convention.
- [x] `src/freecad_buddy/usecases/techdraw.py` -- rasterize the composed sheet at ≥2048 px width;
      name the rasterizer and record the choice in a decision note if it adds a dependency.
- [x] `src/freecad_buddy/contracts/` -- the wire type for the drawing result (paths, page width,
      the dimension set emitted), with a regenerated schema.
- [x] `tests/infc/test_techdraw_generator.py` -- fingerprint-purity test (identical before/after),
      teardown test on the failure path, a ≥2048 px assertion, and a test that the three projections
      differ from one another.
- [x] `tests/infc/test_techdraw_generator.py` -- assert dimensions are parameter-sourced: change a
      driving parameter and confirm the callout follows it.
- [x] `_bmad-output/implementation-artifacts/deferred-work.md` -- record the rasterizer decision and
      any limit that remains (for example, if the raster path is unavailable on one leg).

**Acceptance Criteria:**
- Given a part document, when `techdraw_for_judge` runs, then `fingerprint(doc)` is identical before
  and after, and no TechDraw object exists in the part document.
- Given a successful run, when the output is inspected, then a single composed sheet exists at
  ≥2048 px width carrying three distinct orthographic projections and their dimensions.
- Given a failure injected partway through the build, when the call returns, then the TempDoc is gone
  and no temp file remains under the session workdir.
- Given a driving parameter change, when the drawing is regenerated, then the dimension callout
  changes with it, proving the value was parameter-sourced and not read off the geometry.
- Given `check_imports.py`, when run, then no ring violation is reported (no Qt or GUI import in
  `usecases/`).
- Given the full suites, when run, then the in-FreeCAD and external baselines do not regress.

## Implementation Notes

## Spec Change Log

## Review Triage Log

## Design Notes

**The sheet is composed, not exported.** This is the whole shape of the story and it comes from a
measured fact, not a preference: `exportPageAsSvg` lives in `TechDrawGui`, which raises
`ImportError: Cannot load Gui module in console application.` under `FreeCADCmd`. Epic 5's headless
service must re-execute the visual verdict, so a GUI-only drawing path would leave the service unable
to reproduce its own result. Headless composition is the only path that works on both legs.

**Why parameter-sourced dimensions matter.** If the callouts were read from the produced geometry,
the drawing would agree with the part no matter how wrong the part was. The judge's dimension
cross-check is the only mechanism that can catch a spec→assertion mistranslation, and it only works
if the numbers come from the declared intent rather than from the result.

## Verification

**Commands:**
- `python tests/run_tests.py` (H1 `fcb` env with the `PYTHONPATH` patch) -- expected: new TechDraw
  generator tests pass; no regression below the current baseline
- `uv run pytest tests/external -q` -- expected: no regression
- `python scripts/check_imports.py` -- expected: exit 0
- `uv run ruff check src/ tests/` -- expected: clean for files this story touches
- `uv run python scripts/gen_schemas.py --check` -- expected: no schema drift
