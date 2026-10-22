---
name: code-cad-conversion
track: B
description: >-
  Use when an existing code-CAD model (build123d, CadQuery, cadgen Python)
  must become a parametric FreeCAD document that stays equal to the source.
  Trigger phrases: "convert build123d to FreeCAD", "port my CadQuery model",
  "make the build123d part parametric in FreeCAD", "build123d to FCStd",
  "cadgen to FreeCAD", "keep both models identical". Do NOT use for designing
  a new part from a written spec (see design-decomposition) or choosing which
  values become parameters in a new design (see design-intent).
version: 0.2.0
freecad-versions: ['1.1']
---

## Scope

Convert a build123d or CadQuery source into a FreeCAD document in which every
named source constant is an editable parameter and the part is provably equal
to the source. This skill owns the conversion route, the parameter layer, the
generator script, and the equality proof. It does not own feature choice for a
new design (tool-selection) or general VarSet practice (parametric-patterns).

Copy-ready helpers: `references/generator-kit.md`. Source call to FreeCAD object:
`references/build123d-mapping.md`. Check and re-export scripts:
`references/verification-kit.md`. Known failures: `references/failure-table.md`.

All steps run through the **freecad-buddy MCP server** (`script_exec`,
`document_*`, `query_*`, `verify_*`, `export_*`). If those tools are not in your
session, open FreeCAD with the freecad-buddy add-on and connect your MCP client
first. If `query_capabilities` reports `exec_enabled: false`, stop and ask the
operator to turn on `ScriptExec`: no typed tool writes a VarSet or an expression.

## Decision Rules

- **Pick the route from the source shape.** Source built from primitives and
  booleans (`Box`, `Cylinder`, `Cone`, `loft` of two rectangles, `+=`, `-=`,
  `Pos`, `Location`) → **Part primitives and `Part::MultiFuse` / `Part::Cut` /
  `Part::MultiCommon`**, every size and placement an expression. Source built
  from sketches and `extrude` / `revolve` of profiles → PartDesign Body with
  sibling skills. Editability comes from the expressions, not the workbench; a
  PartDesign rebuild of a CSG source changes the geometry definition and loses
  the one-to-one map you need to prove equality.
- **Build with a generator file run by `script_exec`.** One Python file on disk,
  run with `doc` injected (`references/generator-kit.md`, "Run it"), inside a
  transaction that aborts on error. Keep each call under the 30 s budget: split
  into stages (parameters, then one part per call); only the first stage clears
  the document. After a `TIMEOUT`, run `query_tree_summary` before the next
  mutating call.
- **One VarSet `Params`, source names kept.** Use the source constant names, so
  the two files compare line by line. Each float is `App::PropertyFloat`
  (unitless: mm on a length, degrees on an angle). Order the Data tab with groups.
- **Rename only what cannot parse.** Unit symbols `W`, `T`, `A`, `V`, `N`, `C`,
  `K`, `J`, `H`, `F`, `S`, `m`, `g`, `s` fail with `ParserError`: give them a
  longer name (`T` → `PLATE_T`). A tuple item becomes one variable per item
  (`RAIL_Z[1]` → `RAIL_Z_1`). Record every rename in the generator header.
- **What becomes a variable.** Every named module constant the converted parts
  reach, directly or through other constants and helpers → a `Params` variable. A function local (`slot_z`, `end_x`) → an inline expression on the
  primitive. An unnamed literal (`4`, `7.0`) → a number inside the expression.
- **Derived values are expressions, never re-typed numbers.** `BOSS_H = T + 7`
  becomes `prm("BOSS_H", P.PLATE_T + 7, ...)`; `Params` shows it as
  `PLATE_T + 7`. Tell the user that a derived value is edited through its
  expression, not by typing a number.
- **Switches stay in `Params`.** A bool → `App::PropertyBool` in a ternary on a
  numeric size: `COUNTERSINK ? CSK_D / 2 : HOLE_D / 2` on the cone's `Radius2`
  (`Radius1 == Radius2` is valid). A text choice (`"insert"` / `"tap"`) →
  `App::PropertyEnumeration`, compared by index: `FASTEN == 0 ? 4 : 2.5`. A
  string compare (`FASTEN == <<insert>>`) is always false, with no error.
- **Fit decisions stay live.** A Python `if` on parameter values that decides
  whether a feature exists (`if y + 1.5 < WALL + MB_IN_W - ...`) becomes a
  ternary: park the tool out of the part (`fits ? MB_FLOOR + 6 : -1000` on its
  base z) or set a size that cuts nothing. A fixed decision breaks equality as
  soon as an edit changes the count. Loop counts over literal ranges stay fixed;
  list them in the generator header.
- **Mirror the source construction order.** Consecutive `+=` share one
  `MultiFuse`, consecutive `-=` share one `Cut`, labelled `<part>_stepN`
  (`Solid` class). A nested expression (`body += (post + lips) - slot`) is its
  own `Solid`, added to the body with `add(inner.done())`, so `slot` never cuts
  the body.
- **Frames.** A source `Location((tx, ty, 0), (0, 0, deg)) * part` becomes a
  frame `(tx, ty, deg)`; all three may be parameters. Each primitive gets a
  `Placement.Rotation.Angle` expression and a base of
  `tx + x*cos(deg) - y*sin(deg)`, `ty + x*sin(deg) + y*cos(deg)`. FreeCAD `cos`,
  `sin`, `atan2` use degrees.
- **Purchased parts.** Load each catalog STEP once into a hidden `Part::Feature`;
  place copies with `App::Link`, `LinkTransform = True`; only the placement is a
  parameter.
- **Prove equality before any new design work.** Re-export the source at its
  defaults, in the same world frame, and also compare with any STEP the user
  gave. Per part: one valid solid, volume difference 0.000 %, overlap (`common`
  volume / source volume) 100.000 %. Equal volume alone is not equality; bounding
  boxes are not a test.
- **Prove the parameters, at their limits.** Edit several variables at both ends
  of a useful range, flip every switch, and pick values that change every fit
  decision and both branches of every `min()` / `max()`. Re-export the source
  with the same values (`references/verification-kit.md`: the source derives its
  own constants) and repeat the equality check. Then restore the defaults and
  repeat it against the default STEP. Budget about 8 s per case for a 100-object
  model: two cases per call.
- **Measure; then look.** `query_screenshot` (its `include` takes object Names,
  not Labels) and a real-window screenshot confirm the look. The equality and
  limit checks decide correctness.
- **One source of numbers.** Until the user names one file as the master, a
  design change goes into both files, then both are rebuilt and re-verified.

## Worked Examples

Input: "Convert this build123d bracket to parametric FreeCAD." Source: plate
`Box(L, W, T)`, `+= Cylinder(BOSS_R, BOSS_H)`, a loop of `-=` holes with
`if COUNTERSINK: -= Cone(...)`, `-= Cylinder(BORE_R, BOSS_H)`, all under
`Location((FRAME_X, FRAME_Y, 0), (0, 0, FRAME_DEG))`.

Reasoning: a CSG source, so the Part route. Generator file:

```python
prm("L", 60.0, "1 Plate"); prm("PLATE_W", 40.0, "1 Plate"); prm("PLATE_T", 5.0, "1 Plate")
prm("BOSS_H", P.PLATE_T + 7.0, "2 Boss")
prm_bool("COUNTERSINK", True, "3 Holes")
# EDGE, HOLE_D, CSK_D, BOSS_R, BORE_R, FRAME_X, FRAME_Y, FRAME_DEG: prm() the same way
F = (P.FRAME_X, P.FRAME_Y, P.FRAME_DEG)
s = Solid(box(P.L, P.PLATE_W, P.PLATE_T, align=("C", "C", "MIN"), frame=F), "bracket")
s.add(cyl(P.BOSS_R, P.BOSS_H, frame=F))
for sx in (-1, 1):
    for sy in (-1, 1):
        x, y = sx * (P.L / 2 - P.EDGE), sy * (P.PLATE_W / 2 - P.EDGE)
        csk_h = (P.CSK_D - P.HOLE_D) / 2
        s.sub(cyl(P.HOLE_D / 2, P.PLATE_T, at=(x, y, 0), frame=F),
              cone(P.HOLE_D / 2, ife(P.COUNTERSINK, P.CSK_D / 2, P.HOLE_D / 2), csk_h,
                   at=(x, y, P.PLATE_T - csk_h), frame=F))
s.sub(cyl(P.BORE_R, P.BOSS_H, frame=F))
bracket = s.done()
```

One `script_exec` runs it. The equality script reports one valid solid,
`diff_pct` 0.0, `overlap_pct` 100.0; the coverage script finds no unbound size
or placement. The limit test sets `PLATE_T` 3 and 8, `COUNTERSINK` false, and
`FRAME_DEG` 0 and -120; each case matches its re-export, and the restored part
overlaps the default STEP 100 %. Then `document_save`.

Input: "`setExpression` fails: `Failed to parse expression 'Params.T * 2'`."

Reasoning: `T` is the tesla unit symbol. Rename it to `PLATE_T` in `Params`,
record `T → PLATE_T` in the generator header, and rebuild.

## Anti-Patterns

- **PartDesign rebuild of a CSG source.** Symptom: about 20 typed calls, Hole
  and datum semantics that do not match the source, volume off by a sliver.
  Why: the agent assumed Part booleans are not editable. Fix: Part primitives
  and booleans with expressions, in source order.
- **Renamed parameters.** Symptom: `plate_len` in FreeCAD, `L` in the source.
  Fix: keep source names; rename only what cannot parse, with a recorded map.
- **Switch demoted to a manual edit.** Symptom: `COUNTERSINK` lives as an enum
  on one feature, outside `Params`. Fix: a `Params` bool or enumeration in a
  ternary.
- **Fit decision frozen.** Symptom: equal at the defaults, one vent too many or
  too few after an edit. Fix: a live ternary that parks the tool.
- **Baked numbers.** Symptom: a parameter edit changes nothing. Fix: every
  primitive size and placement through `_set`; run the coverage script.
- **Equality by volume or bounding box.** Symptom: a shifted part "passes".
  Fix: volume difference plus `common` overlap against the source STEP.
- **Re-deriving source constants by hand.** Symptom: a re-exported reference is
  wrong and the case "fails". Fix: insert the case values into the source and
  let it derive the rest.
- **One long `script_exec`.** Symptom: `TIMEOUT`, then a suspect document. Fix:
  stages and case batches under 30 s.
- **Lookup by link Label.** Symptom: an object "disappears" after a rebuild.
  Fix: look up by `Name` or `LinkedObject.Label`.
