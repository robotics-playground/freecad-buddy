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
version: 0.1.0
freecad-versions: ['1.1']
---

## Scope

Convert a build123d or CadQuery source into a FreeCAD document in which every
source number is an editable parameter and the part is provably equal to the
source. This skill owns the conversion route, the parameter layer, the generator
script, and the equality proof. It does not own feature choice for a new design
(tool-selection) or general VarSet practice (parametric-patterns).

Copy-ready helpers: `references/generator-kit.md`. Source call to FreeCAD object:
`references/build123d-mapping.md`. Check scripts: `references/verification-kit.md`.
Known failures: `references/failure-table.md`.

All steps run through the **freecad-buddy MCP server** (`script_exec`,
`document_*`, `query_*`, `verify_*`, `export_*`). If those tools are not in your
session, open FreeCAD with the freecad-buddy add-on and connect your MCP client
first. If `query_capabilities` reports `exec_enabled: false`, stop and ask the
operator to turn on `ScriptExec`: no typed tool writes a VarSet or an expression.

## Decision Rules

- **Pick the route from the source shape.** Source built from primitives and
  booleans (`Box`, `Cylinder`, `Cone`, `+=`, `-=`, `Pos`, `Location`) →
  **Part workbench primitives and `Part::MultiFuse` / `Part::Cut` /
  `Part::MultiCommon`**, every size and placement an expression. Source built
  from sketches and `extrude` / `revolve` of profiles → PartDesign Body with
  sibling skills. A CSG source rebuilt as PartDesign changes the geometry
  definition (Hole countersink depth, ThroughAll extents, datum offsets), costs
  about three calls per feature, and loses the one-to-one map you need to prove
  equality.
- **A Part CSG tree with expressions is parametric.** Editability comes from
  every size and position being an expression on `Params`, not from the
  workbench. The "prefer PartDesign" rule in tool-selection is for new designs.
- **Build with a generator file run by `script_exec`.** Write one Python file on
  disk and exec it with `doc` injected (`references/generator-kit.md`, "Run it").
  Wrap it in a transaction that aborts on error. Keep each call under the 30 s
  budget: split into stages (parameters, then one part per call). After a
  `TIMEOUT`, run `query_tree_summary` before the next mutating call.
- **One VarSet `Params`, source names kept.** Use the source constant names, so
  the two files compare line by line. Each float is `App::PropertyFloat`
  (unitless: read as mm on a length, degrees on an angle). Order the Data tab
  with groups.
- **Rename only names that are unit symbols.** `W`, `T`, `A`, `V`, `N`, `C`,
  `K`, `J`, `H`, `F`, `S`, `m`, `g`, `s` fail with `ParserError: Failed to parse
  expression`. Give those a longer name (`T` → `PLATE_T`) and record the map in
  the generator header. Keep every other name as in the source.
- **Derived values are expressions, never re-typed numbers.** `BOSS_H = T + 7`
  becomes `prm("BOSS_H", P.PLATE_T + 7, ...)`; `Params` shows it as
  `PLATE_T + 7`. Tell the user that a derived value is edited through its
  expression, not by typing a number.
- **A bool switch stays in `Params`.** Make it `App::PropertyBool` and use it in
  a ternary on a numeric size, so it flips with every other parameter:
  `COUNTERSINK ? CSK_D / 2 : HOLE_D / 2` on the countersink cone's `Radius2`.
  `Part::Cone` with `Radius1 == Radius2` is valid. Never move a source bool to a
  manual enum edit on one feature.
- **Every number carries its expression and its value.** Use the `E` class:
  sizes and positions become live expressions; `.v` lets the generator make
  structural choices (how many vents fit). Counts and fit decisions are fixed
  until the generator runs again. Write that list in the generator header.
- **Mirror the source construction order.** Consecutive `+=` share one
  `MultiFuse`, consecutive `-=` share one `Cut`, labelled `<part>_stepN`
  (`Solid` class), so a difference traces to one step.
- **Frames.** A source `Location((tx, ty, 0), (0, 0, deg)) * part` becomes a
  frame `(tx, ty, deg)`; all three may be parameters. Each primitive gets
  `Placement.Rotation.Angle = deg` and a base of `tx + x*cos(deg) - y*sin(deg)`,
  `ty + x*sin(deg) + y*cos(deg)`, all as expressions. Set a non-zero start
  rotation about the axis before the angle expression, so the axis is fixed.
  FreeCAD `cos`, `sin`, `atan2` use degrees.
- **Purchased parts.** Load each catalog STEP once into a hidden
  `Part::Feature`; place copies with `App::Link`, `LinkTransform = True`. Only
  the placement is a parameter.
- **Prove equality before any new design work.** Re-export the source to STEP
  at its defaults, in the same world frame (also compare with any STEP the user
  gave). Per part: one valid solid, volume difference 0.000 %, and
  overlap (`common` volume / source volume) 100.000 %. Equal volume alone is not
  equality. Bounding boxes are not a test: OCC boxes around curved faces are
  loose.
- **Prove the parameters, at their limits.** Edit several variables (both ends
  of a useful range) and flip every bool. Re-export the source with the same
  values and repeat the equality check. Then restore the defaults and repeat the
  equality check against the default STEP: a frame that does not come back keeps
  its volume. A model that only matches at its defaults is not parametric.
- **Measure; then look.** `query_screenshot` and a real-window screenshot
  confirm the look. The equality and limit checks decide correctness.
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
`diff_pct` 0.0, `overlap_pct` 100.0. The expression-coverage script finds no
unbound size or placement. The limit test sets `PLATE_T` 3 and 8, `COUNTERSINK`
false, and `FRAME_DEG` 0 and -120; the source is re-exported with the same
values, every case matches, and the restored part overlaps the default STEP 100 %. Then
`document_save`.

Input: "`setExpression` fails: `Failed to parse expression 'Params.T * 2'`."

Reasoning: `T` is the tesla unit symbol. Rename it to `PLATE_T` in `Params`,
record `T → PLATE_T` in the generator header, and rebuild.

## Anti-Patterns

- **PartDesign rebuild of a CSG source.** Symptom: about 20 typed calls, datum
  and Hole semantics that do not match the source cone, volume off by a sliver.
  Why: the source had no sketches; the rebuild invents a new definition. Fix:
  Part primitives and booleans with expressions, in source order.
- **"Part booleans are not editable."** Symptom: the agent picks PartDesign to
  get a parametric model. Why: editability comes from expressions on `Params`.
  Fix: put every size and placement on an expression.
- **Renamed parameters.** Symptom: `plate_len` in FreeCAD, `L` in the source;
  the two files cannot be compared line by line. Fix: keep source names; rename
  unit symbols only, with a recorded map.
- **Source bool demoted to a manual edit.** Symptom: `COUNTERSINK` lives as an
  enum on one feature, outside `Params`. Fix: `App::PropertyBool` plus a ternary
  on a numeric size.
- **Baked numbers.** Symptom: a parameter edit changes nothing. Why: the size was
  set with `setattr`, not `setExpression`. Fix: every primitive size and
  placement through `_set`; check `obj.ExpressionEngine`.
- **Equality by volume or bounding box.** Symptom: a shifted part "passes".
  Fix: volume difference plus `common` overlap against the source STEP.
- **Tests only at the defaults.** Symptom: the model breaks or drifts at another
  value. Fix: limit test against a re-exported source, then restore.
- **One long `script_exec`.** Symptom: `TIMEOUT`, then a suspect document. Fix:
  split into stages under 30 s; check the tree before the next mutation.
- **Lookup by link Label.** Symptom: an object "disappears" after a rebuild.
  Why: FreeCAD makes labels unique. Fix: look up by `Name` or
  `LinkedObject.Label`.
