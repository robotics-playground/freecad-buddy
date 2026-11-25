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
generator script for shapes typed tools cannot make, and the equality proof. It does not own feature choice for a
new design (tool-selection) or general VarSet practice (parametric-patterns).

Copy-ready helpers: `references/generator-kit.md`. Source call to FreeCAD object:
`references/build123d-mapping.md`. Check and re-export scripts:
`references/verification-kit.md`. Switches and fit decisions: `references/switches-and-fit.md`.
Known failures: `references/failure-table.md`.

All steps run through the **freecad-buddy MCP server** (`feature_*`,
`document_*`, `query_*`, `verify_*`, `export_*`, and `script_exec` for the generator route). If those tools are not in your
session, open FreeCAD with the freecad-buddy add-on and connect your MCP client
first. If `query_capabilities` reports `exec_enabled: false`, build the typed parts live and use the headless route in
`freecad-scripting-idioms` for the generator-only objects and enumeration properties.

## Decision Rules

- **Pick the route from the source shape.** Source built from primitives and
  booleans (`Box`, `Cylinder`, `Cone`, `Sphere`, `Torus`, `+=`, `-=`,
  `Pos`, `Location`) → **Part primitives and `Part::MultiFuse` / `Part::Cut` /
  `Part::MultiCommon`**, every size and placement an expression. Source built
  from sketches and `extrude` / `revolve` of profiles → PartDesign Body with
  sibling skills. Editability comes from the expressions, not the workbench; a
  PartDesign rebuild of a CSG source changes the geometry definition and loses
  the one-to-one map you need to prove equality.
- **Build each part with typed tools.** `feature_parameters_define` and
  `feature_set_expression` set up `Params` (`references/generator-kit.md`, "Run it").
  Per source primitive: `feature_part_primitive` with the default values as
  sizes (`name` is the Name and the Label: `<part>_<item>`), then one
  `feature_set_expression` call (up to 100 items) binds every size and placement
  (`Length`, `Radius`, `Placement.Base.x`, `Placement.Rotation.Angle`, a rotation
  about z). A build123d solid is centred by default and a FreeCAD box starts at its
  corner: offset the base (`references/build123d-mapping.md`). Booleans follow in
  source order with `feature_part_boolean` (`fuse`, `cut`, `common`; 1 to 20
  `tools` per call, so chain a longer cut, fuse or common); the last step takes the part name, and a
  part of one primitive names that primitive after the part.
- **Use the generator file for an object the typed tools cannot make.** A source
  `loft` of two rectangles (`Part::Wedge`, kit `taper_z`), another Part type, a
  purchased `App::Link` part, a primitive tilted off z under a frame angle: one
  generator run per object through `script_exec`, under the 30 s budget (after a
  `TIMEOUT`, run `query_tree_summary` before the next mutating call).
  `feature_part_boolean` takes the generated Wedge by its Name, so offered
  primitives and every boolean stay typed. An enumeration switch needs one
  `script_exec` call for the property (kit, "Run it" step 4).
- **A typed refusal is a stop with a repair** (`freecad-scripting-idioms`,
  `references/gap-list.md`, "A typed refusal is not a gap"). A script that repeats the call skips the guard.
- **One VarSet `Params`, source names kept.** Use the source constant names, so
  the two files compare line by line. Each float is `App::PropertyFloat`
  (unitless: mm on a length, degrees on an angle). Order the Data tab with groups.
- **Rename only what cannot parse.** Unit symbols `W`, `T`, `A`, `V`, `N`, `C`,
  `K`, `J`, `H`, `F`, `S`, `m`, `g`, `s` fail with `ParserError`: give them a
  longer name (`T` → `PLATE_T`). A tuple item becomes one variable per item
  (`RAIL_Z[1]` → `RAIL_Z_1`). Record every rename in the build notes.
- **What becomes a variable.** Every named module constant the converted parts
  reach, directly or through other constants and helpers → a `Params` variable. A function local (`slot_z`, `end_x`) → an inline expression on the
  primitive. An unnamed literal (`4`, `7.0`) → a number inside the expression.
- **Derived values are expressions, never re-typed numbers.** `BOSS_H = T + 7`
  becomes the expression `Params.PLATE_T + 7` bound to `BOSS_H`;
  `Params` shows it as `PLATE_T + 7`. Tell the user that a derived value is edited through its
  expression, not by typing a number.
- **Switches and fit decisions stay live in `Params`.** A source bool, text choice or
  `if` on parameter values becomes a variable and a ternary, never a fixed
  decision: `references/switches-and-fit.md`.
- **Mirror the source construction order.** Consecutive `+=` share one
  `MultiFuse`, consecutive `-=` share one `Cut`, named `<part>_stepN`. A nested
  expression (`body += (post + lips) - slot`) is its own boolean chain, fused into
  the body afterwards, so `slot` never cuts the body.
- **Frames.** A source `Location` becomes a frame `(tx, ty, deg)` of parameters
  (`references/build123d-mapping.md`, "Placement"). FreeCAD `cos`, `sin`, `atan2` use degrees.
- **Purchased parts.** Load each catalog STEP once into a hidden `Part::Feature`;
  place copies with `App::Link`, `LinkTransform = True`; only the placement is a
  parameter.
- **Prove equality after each part, before any new design work.** The typed
  route stays equal to the source because every part is checked against it: re-export the source at its
  defaults, in the same world frame, and also compare with any STEP the user
  gave. Per part (`verify_shape` for validity, solid count and volume; the overlap script in `references/verification-kit.md`): one valid solid, volume difference below 0.0001 %, overlap (`common`
  volume / source volume) 100.000 %. Equal volume alone is not equality; bounding
  boxes are not a test.
- **Prove the parameters, at their limits.** Edit several variables at both ends
  of a useful range, flip every switch, and pick values that change every fit
  decision and both branches of every `min()` / `max()`. Re-export the source
  with the same values (`references/verification-kit.md`: the source derives its
  own constants) and repeat the equality check. Then restore the defaults and
  repeat it against the default STEP. Budget about 8 s per case for a 100-object
  model: one case per call, restored before the next.
- **Measure; then look.** `query_screenshot` (its `include` takes object Names,
  not Labels) and a real-window screenshot confirm the look. The equality and
  limit checks decide correctness.
- **One source of numbers.** Until the user names one file as the master, a
  design change goes into both files, then both are rebuilt and re-verified.

## Worked Examples

Input: "Convert this build123d bracket to parametric FreeCAD." Source: plate
`Box(L, PLATE_W, PLATE_T, align=MIN)` and one hole
`body -= Pos(EDGE, EDGE, 0) * Cylinder(HOLE_R, PLATE_T, align=(CENTER, CENTER, MIN))`.

Reasoning: a CSG source with offered primitives, so typed calls. The plate is
aligned MIN, so it needs no offset. `feature_parameters_define` creates `Params`
(`L`, `PLATE_W`, `PLATE_T`, `HOLE_R`, `EDGE`), then:

```json
{"doc": "<fcb-doc handle>", "kind": "box", "name": "bracket_plate", "length": {"value": 60, "unit": "mm"}, "width": {"value": 40, "unit": "mm"}, "height": {"value": 5, "unit": "mm"}}
{"doc": "<fcb-doc handle>", "kind": "cylinder", "name": "bracket_hole", "radius": {"value": 2, "unit": "mm"}, "height": {"value": 5, "unit": "mm"}}
{"doc": "<fcb-doc handle>", "expressions": [{"object": "bracket_plate", "path": "Length", "expression": "Params.L"}, {"object": "bracket_plate", "path": "Width", "expression": "Params.PLATE_W"}, {"object": "bracket_plate", "path": "Height", "expression": "Params.PLATE_T"}, {"object": "bracket_hole", "path": "Radius", "expression": "Params.HOLE_R"}, {"object": "bracket_hole", "path": "Height", "expression": "Params.PLATE_T"}, {"object": "bracket_hole", "path": "Placement.Base.x", "expression": "Params.EDGE"}, {"object": "bracket_plate", "path": "Placement.Base.x", "expression": "0"}, {"object": "bracket_plate", "path": "Placement.Base.y", "expression": "0"}, {"object": "bracket_plate", "path": "Placement.Base.z", "expression": "0"}, {"object": "bracket_hole", "path": "Placement.Base.z", "expression": "0"}, {"object": "bracket_hole", "path": "Placement.Base.y", "expression": "Params.EDGE"}]}
{"doc": "<fcb-doc handle>", "operation": "cut", "base": "bracket_plate", "tools": ["bracket_hole"], "name": "bracket"}
```

The equality check passes (`verify_shape` valid, one solid, volume equal; overlap
script `overlap_pct` 100.0). The limit test sets `PLATE_T` 3 and 8 and `EDGE` 4;
each case matches its re-export. Then `document_save`. A `Wedge` part is in
`references/generator-kit.md`.

Input: "`setExpression` fails: `Failed to parse expression 'Params.T * 2'`."

Reasoning: `T` is the tesla unit symbol. Rename it to `PLATE_T` in `Params`,
record `T → PLATE_T` in the build notes, and rebuild.

## Anti-Patterns

- **PartDesign rebuild of a CSG source.** Symptom: about 20 typed calls, Hole
  and datum semantics that do not match the source, volume off by a sliver.
  Why: the agent assumed Part booleans are not editable. Fix: typed Part
  primitives and booleans with expressions, in source order.
- **Renamed parameters.** Symptom: `plate_len` in FreeCAD, `L` in the source.
  Fix: keep source names; rename only what cannot parse, with a recorded map.
- **Switch demoted to a manual edit.** Symptom: `COUNTERSINK` lives as an enum
  on one feature, outside `Params`. Fix: a `Params` bool or enumeration in a
  ternary.
- **Fit decision frozen.** Symptom: equal at the defaults, one vent too many or
  too few after an edit. Fix: a live ternary that parks the tool.
- **Baked numbers.** Symptom: a parameter edit changes nothing. Fix: every
  primitive size and placement through an expression; run the coverage script.
- **Equality by volume or bounding box.** Symptom: a shifted part "passes".
  Fix: volume difference plus `common` overlap against the source STEP.
- **Re-deriving source constants by hand.** Symptom: a re-exported reference is
  wrong and the case "fails". Fix: insert the case values into the source and
  let it derive the rest.
- **One long `script_exec`.** Symptom: `TIMEOUT`, then a suspect document. Fix:
  stages and case batches under 30 s.
- **Lookup by link Label.** Symptom: an object "disappears" after a rebuild.
  Fix: look up by `Name` or `LinkedObject.Label`.
