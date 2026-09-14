# Defects found in UAT run 2026-09-13-07 (TC-16)

Both are FreeCAD/TechDraw behaviours observed against the live application, not freecad-buddy
defects — no Phase 3 code exists to be at fault. Both are recorded because Story 4.3 will hit
them, and discovering them mid-implementation is what the 4.1 spike exists to prevent.

## R3-01 — `viewPartAsSvg` returns an empty string when read in the same pass that built the view

**Severity**: medium (silent wrong result, not an error)
**Leg**: GUI only. The headless path did not show it.
**Scenario**: TC-16-03

**Observed.** The first macro created `DrawPage` + `DrawSVGTemplate` + `DrawViewPart`, called
`doc.recompute()`, then `TechDraw.viewPartAsSvg(view)` — and got:

```
TC-16-03 viewPartAsSvg length=0 nonempty=False
```

A second macro, run afterwards against the **same unchanged view**, got a real result on its
first attempt:

```
view.State: ['Up-to-date']
attempt  1: len(svg)=308    state=['Up-to-date']
<g fill="none" stroke="#000000" ...>
<path id= "1" d=" M -15 10 L -15 -10 " />
```

**Cause.** `DrawViewPart` geometry is built asynchronously in the GUI, so the view's SVG is empty
until its own update completes. `doc.recompute()` returning and `view.State` reading
`['Up-to-date']` are both **insufficient** signals — the state already read up-to-date in the
first macro's pass.

**Why it matters to 4.3.** `techdraw_for_judge` builds views and reads their SVG in one call. An
empty string is not an exception: it would silently produce a blank judge sheet, and the visual
leg would fail a correct part for a reason no assertion reports. 4.3 must confirm the view has
produced geometry before reading its SVG, and must treat an empty SVG as an error rather than as
output.

**Repro**: run `~/AppData/Roaming/FreeCAD/v1-1/Macro/tc16_boundary.FCMacro` (it builds the view
and reads the SVG in one pass), then read the same view's SVG again from a second execution.
Evidence: `evidence/tc-16-02-03-gui.txt` (length=0) and `evidence/tc-16-03-svg-retry.txt`
(length=308 on attempt 1, same unchanged view).

## R3-02 — A DrawViewPart at Scale 1.00 on the default template overflows the sheet

**Severity**: low (cosmetic here; a layout question 4.3 must answer anyway)
**Leg**: GUI
**Scenario**: TC-16-03 visual check

**Observed.** The opened Page renders as a blank white sheet inside its border. The view is
present: clicking inside the sheet selected `tc16.View.Face0` and the entire sheet turned
selection-green, so the single projected face covers the whole page and its outline falls outside
the visible area. Properties: View X=0.00 mm, Y=0.00 mm, Scale Type Page, Scale 1.00.

**Why it matters to 4.3.** Decision 016 already assigns sheet layout to 4.3, because no headless
page exporter exists to delegate it to. This is that problem showing up concretely: page size,
view scale and view placement are 4.3's contract. A judge sheet that renders blank would be fed to
the vision model as a legitimate image.

**Evidence**: `evidence/tc-16-03-page-open.png` (blank), `evidence/tc-16-03-page-fit.png`
(same view selected, filling the sheet).
