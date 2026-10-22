# Conversion failures: symptom, cause, fix

| Symptom | Cause | Fix |
| --- | --- | --- |
| `ParserError: Failed to parse expression 'Params.W * 3'` | variable name is a unit symbol (`W`, `T`, `A`, `V`, `N`, `C`, `K`, `J`, `H`, `F`, `S`, `m`, `g`, `s`) | rename (`PLATE_W`); keep a source-to-FreeCAD name map |
| Volume equal, overlap below 100 % | part shifted or rotated: wrong align offset, frame sign, or `cos`/`sin` given radians | FreeCAD trig takes degrees; check the align offset of each primitive against the source |
| Part becomes a fragment (only some features) after a parameter edit | a cut tool tangent to a same-radius curved face (cylinder against a torus bore); OCC returns a partial result | make the tool overlap or stop it short of the tangent face; retest the parameter limits |
| Purchased part placed at the wrong position | `App::Link` replaces the target's own placement by default | `LinkTransform = True` on every link |
| Mirrored triangle prism extrudes the wrong way | polygon winding flips with the mirror sign; extrusion follows the face normal | use a `Part::Wedge`, or set the extrusion direction explicitly |
| Object not found after a rebuild | lookup by link Label; FreeCAD makes labels unique (`fan_4021001`) | look up by `Name` or by `LinkedObject.Label` |
| `TIMEOUT`, then the document is marked suspect | one `script_exec` call ran past the 30 s budget | split the build into stages; run `query_tree_summary` before the next mutating call |
| Cylinder or cone `Invalid` at a parameter limit (`CSK_D == HOLE_D` gives a countersink cone of height 0) | a size expression reached 0 or below | the source has the same limit: record the valid range for the user; clamp with `max()` only when the source clamps too. A bool ternary on a radius stays valid (`Cone` with `Radius1 == Radius2` is a cylinder) |
| Edits to a parameter change nothing | the value was set as a plain number, not with `setExpression` | every size and placement of a primitive takes an expression; check `obj.ExpressionEngine` |
| Fillet lost after a parameter edit | `Part::Fillet` edge list is by index; the boolean re-numbered edges | fillet as the last step only; re-check its edges after each edit, or model the round as a primitive |
