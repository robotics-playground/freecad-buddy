# Gap list: operations with no typed tool

Read this before every `script_exec` call. Find the operation in the table. A row means no typed
tool covers it today, so `script_exec` is the route. No row: look for a typed tool in your tool
list and use it. If none exists, the list is out of date: report the missing row. State the
missing typed tool in one sentence before you send the script. When `query_capabilities` reports
`exec_enabled: false`, use the headless route in `SKILL.md`; with no shell to run `freecadcmd`,
report the operation as blocked.

## Covered: do not script

| Operation | Typed route |
|-----------|-------------|
| Read bounding box, volume, area, centre of mass, solid count of one or several objects | `query_mass_properties` (`object`, or `objects` for 1 to 50 names in one call; `com` is null for a compound such as an `App::Part`) |
| Measure overlap volume and minimum distance between objects | `query_interference` (`objects` for every pair, or `pairs`) |
| Cut a shape with a plane: wires, length, area, bbox, polyline points | `query_section` (`object`, `plane`, optional `points`) |
| Check validity, solid count, watertight, bbox, extent, volume, hole count, diameter, position and spacing, distance and angle between selectors | `verify_shape` (`checks` items `{"fn": ..., "expect": ...}`) |
| Read property values and bound expressions (`ExpressionEngine`) of one object | `query_object` |
| List every VarSet property, aliased spreadsheet cell and expression binding of the document | `query_parameters` |
| Create a VarSet, add or update typed parameters on it (length, angle, float, integer, bool, string) | `feature_parameters_define` |
| Bind or clear an expression on a numeric property path (a VarSet parameter on a feature property or a sketch constraint) | `feature_set_expression` |
| Delete whole objects, Tip features, and objects nothing else depends on, or delete them with their dependents. Read the `delete.has_dependents` list first and stop if it names a feature to keep | `document_object_delete` (`objects`, `with_dependents`) |
| Read a placement, a sketch's geometry and constraints, dependency links, failing objects | `query_placement`, `query_sketch_info`, `query_dependencies`, `verify_recompute` |
| Sketch geometry (line, circle, arc, point) and the `sketch_add_constraint` types, including a fixed point by `DistanceX` plus `DistanceY` | `sketch_*` |
| PartDesign body, pad, pocket, hole, fillet, chamfer, revolve, pattern, mirror, datum | `feature_*` |
| Write a boolean, number, quantity or enum property of any object (a feature, a VarSet, `Visibility`); lengths in mm, angles in degrees; a property driven by an expression is reset on recompute | `feature_set_parameters` |
| Write one or several objects to one STEP, 3MF or STL file; omit `objects` for all visible solids | `export_step`, `export_3mf`, `export_stl`, then `verify_export_*` |

## Gaps

| Operation | Typed tool today | `script_exec` use |
|-----------|------------------|-------------------|
| Write a placement or `AttachmentOffset` | none (`feature_set_parameters` refuses `App::PropertyPlacement`) | set `obj.Placement` or `obj.AttachmentOffset` |
| Rename a `Label` | none | set `obj.Label` |
| Remove one feature from the middle of a Body and keep the later features | none (`document_object_delete` refuses it with `delete.has_dependents`, and `with_dependents` true deletes every later feature) | `body.removeObject(feature)` relinks the next `BaseFeature`; then `doc.removeObject(feature.Name)`. Open a transaction, run `verify_*` after |
| Overlap volume of parts that touch (`query_interference` gives `boolean_failed` true, `min_distance` at most 1e-7 mm) | none | `f = a.fuse(b)`; check `f.isValid()` and `f.Solids`, else the overlap is unmeasured; then `a.Volume + b.Volume - f.Volume`. `common()` reads 0 here and proves nothing |
| Add an enumeration property to a VarSet, write a spreadsheet cell or alias | none (`feature_parameters_define` has no enumeration type) | `addProperty`, `sheet.set`, `setAlias` |
| Part primitives and booleans (`Part::Box`, `Part::Cut`, `Part::Common`) | none | `doc.addObject` |
| Loft, sweep, helix, thickness | none | `doc.addObject` or `body.newObject` |
| Groove (subtractive revolve), PartDesign primitives | none | `body.newObject("PartDesign::Groove")`, `body.newObject("PartDesign::AdditiveBox")` |
| Sketch constraint outside the `sketch_add_constraint` types (for example `InternalAlignment`, `TangentViaPoint`) | none | `sketch.addConstraint` |
| Write a string or link property of an object that is not a VarSet | none (`feature_set_parameters` refuses these; a VarSet string: `feature_parameters_define`) | `setattr` |
| Ellipse or B-spline sketch geometry | none (`sketch_add_geometry` takes line, circle, arc, point) | `sketch.addGeometry` |
| `App::Link` or clone | none | `doc.addObject("App::Link", ...)` |
| Scan faces or edges without a hole or datum query | none | iterate `shape.Faces`, `shape.Edges` |
| Import a STEP file into a document | none | `Import.insert` (script below) |
| Write measured data to a file | none | `json.dump` |
| Run a tested helper or generator file | none | `exec` the file (conversion route, `code-cad-conversion`) |

## STEP import script

```python
import Import
before = {o.Name for o in doc.Objects}
doc.openTransaction("import step")
try:
    Import.insert(r"D:/path/part.step", doc.Name)
    doc.commitTransaction()
except Exception:
    doc.abortTransaction()
    raise
doc.recompute()
result = [o.Name for o in doc.Objects if o.Name not in before]
```

`result` lists the new objects. By default a multi-body STEP creates an `App::Part` container (the Import preferences can merge
the bodies or use a link group). `result` also lists `Origin` objects, which carry no solid.
The container's shape is the sum of all leaves, so measure every leaf solid in one
`query_mass_properties` call with `objects`, and check validity with `verify_shape` `is_valid_solid` on each leaf.

## Traced outline route

A traced outline is an organic profile read from an image. No typed tool makes one, and none is
planned. The accepted route: a helper module run by `script_exec` creates the sketch geometry
inside a transaction, then `verify_sketch` and `verify_shape` check the result. Name no typed
equivalent for it.
