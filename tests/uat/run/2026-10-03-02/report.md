# G3 corrupted-plan replay run 2026-10-03-02

Story 4.1 (`spec-4-1-entry-gate-g3e-spec-set-assertions-fault-suite.md`). Replays each recorded
corrupted plan through the live bridge and checks the built part in the real FreeCAD window.

## Build banner

| Field | Value |
|-------|-------|
| Git | `029a886` on `feat/epic-4-spec-to-part`, Story 4.1 working tree (uncommitted) |
| FreeCAD | 1.1.1, `C:\Program Files\FreeCAD 1.1\bin\freecad.exe`, junction install to `src` |
| Bridge | FreeCAD pid 27740 (start 15:41:59) → proxy pid 27776 → `:8765` listener pid 8912 |
| Driver | `cua-driver` daemon pid 16172 |
| Replayer | `evidence/replay_g3.py`: each mutation runs `preview_dry_run`, then the tool with the `preview_id` (AD-5) |

## Questions and verdicts

| # | Question | Verdict | Evidence |
|---|----------|---------|----------|
| Q1 | Do the 14 recorded plans replay through the MCP mutation tools? | FAIL, then PASS after fix | First run: 0/14, every plan stops at step 3, `SPEC_FAILED verify_sketch failed on PlateSketch (dof=16): sketch.fully_constrained`. Window `01-after-replay-0of14.png` shows 15 documents holding only an empty `Body`. After full sketch constraints were added: 14/14, `02-replay-after-fix.jsonl` |
| Q2 | Does each clean control build its spec's part? | PASS | Volume equals the spec `expect_volume` for all 4 controls (`control-tolerance-edge-hole` 28221.477 against 28229.801, inside its 0.1 % band); `verify_shape` OK |
| Q3 | Does each planted plan build the defect its description names? | PASS | Volume deviates as described for value and omission defects; position and frame defects build at the faithful volume (`02-replay-after-fix.jsonl`) |
| Q4 | Does the real viewport show the expected parts? | PASS | `04-wrong-hole-diameter.png` (8 mm holes) against `05-control-faithful-plate.png` (5.5 mm holes, same plate); `06-hole-on-wrong-face.png` (bore in a side face, clean top); `08-named-datum-fitall.png` (plate offset to the `PlateCornerDatum` triad) |

Human interventions: **0**. No modal dialog. All test documents closed at the end; FreeCAD left
running with 0 documents, as found.

## Native FreeCAD check (Part > Check Geometry)

Each part was checked with FreeCAD's own **Part > Check Geometry** (Run check, Shape Content
expanded), driven with `cua-driver`: activate the document, select its `Body`, run the check,
read the result through UIA, screenshot `evidence/cg-<case>.png`. No freecad-buddy code is on
this path. A FreeCAD-kernel macro (`evidence/fc_measure.py` → `fc_measure.json`, also run inside
FreeCAD) gives the same values.

| Case | Expectation | Check Geometry | Native volume | Spec volume | Verdict |
|------|-------------|----------------|---------------|-------------|---------|
| control-equivalent-step-order | PASS_CLEAN | 0 invalid, Solid, No errors | 24000.0 | 24000.0 | matches spec |
| control-faithful-mounting-plate | PASS_CLEAN | 0 invalid, Solid, No errors | 28229.8 | 28229.801 | matches spec |
| control-named-datum-honoured | PASS_CLEAN | 0 invalid, Solid, No errors | 21128.76 | 21128.761 | matches spec |
| control-tolerance-edge-hole | PASS_CLEAN | 0 invalid, Solid, No errors | 28221.48 | 28229.801 | inside 0.1 % band |
| blind-hole-made-through | DETECT | 0 invalid, Solid, No errors | 59672.57 | 60803.54 | out of band: bore runs through |
| extra-unrequested-pocket | DETECT | 0 invalid, Solid, No errors | 22800.0 | 23400.0 | out of band: extra pocket |
| missing-bolt-holes | DETECT | 0 invalid, Solid, No errors | 10053.1 | 9449.911 | out of band: 4 faces, no bolt holes |
| pocket-before-pad | DETECT | 0 invalid, Solid, No errors | 32000.0 | 24000.0 | out of band: slot lost |
| radius-for-diameter | DETECT | 0 invalid, Solid, No errors | 6785.84 | 15833.627 | out of band: 32 mm bore |
| wrong-hole-diameter | DETECT | 0 invalid, Solid, No errors | 27593.63 | 28229.801 | out of band: 8 mm holes |
| wrong-plate-thickness | DETECT | 0 invalid, Solid, No errors | 37639.73 | 28229.801 | out of band: 8 mm plate |
| datum-origin-swapped | DETECT | 0 invalid, Solid, No errors | 21128.76 | 21128.761 | volume in band; hole at datum+(50,45), control datum+(20,15) |
| hole-on-wrong-face | DETECT | 0 invalid, Solid, No errors | 60803.54 | 60803.54 | volume in band; bore axis −Y (side), spec +Z (top) |
| mirrored-hole-pattern | DETECT | 0 invalid, Solid, No errors | 13093.1 | 13093.097 | volume in band; 12 mm pivot at x=60, spec x=0 |

Positions for the three position defects come from the kernel macro (`fc_measure.json`,
cylinder axis and centre) and the viewport screenshots; Check Geometry reports no positions.

Driving notes: a Check Geometry task binds to the document active when it opens, so each part
needs close, activate, select, run. A UIA locator that matched any button named `Close` hit the
main-window Close button once; FreeCAD ignored it while the task dialog was open, and the locator
now excludes the title bar.

## Findings

| Id | Finding | Disposition |
|----|---------|-------------|
| F1 | Plans sent `sketch_add_geometry` with no `constraints`; the bridge rolls back any sketch that is not fully constrained | Fixed in all 14 plans; replay 14/14 |
| F2 | `feature_hole` adds a 118° drill point; a `g3-dev-007` build with it misses `expect_volume` by 135.9 mm³ | 007 plans use `feature_pocket`; spec decision deferred (`deferred-work.md`) |
| F3 | `view_fit_viewport` frames 1.81 mm x 0.86 mm on the named-datum document (`07-named-datum-control.png`); FreeCAD Fit all frames the plate | Product defect outside this story, deferred |

## Not verified

- Assertion grading of the built parts: the primitives and the frame resolver land in Story 4.2.
  Detection here is read from volume, `verify_shape` and the viewport, not from `evaluate`.
- The floor leg (FreeCAD 1.0.x): this run used 1.1.1 only.
