# Verification kit

Measure the converted part with the typed tools: `verify_shape` for validity, solid count,
volume against a value and cylindrical holes, `query_mass_properties` (`objects`: every part in
one call) to read the volumes, `query_interference` for overlap between parts, `verify_recompute`
for failing objects. `feature_set_parameters` sets and restores the VarSet values. Run a FreeCAD
snippet with `script_exec` only for what no typed tool measures: overlap against a reference STEP,
the reference's own volume, the expression coverage of a large model (`query_parameters` lists at
most 500 bindings per call), the overlap volume of touching parts, and a countersink probe. Every snippet
is read-only. The re-export
script runs outside FreeCAD and writes one reference STEP per case, in the same world frame as the
FreeCAD part.

## Re-export the source per case

Run with `uv run --with build123d python make_refs.py`. Each case value is inserted as a new
assignment right after the top-level statement that first assigns that name, so the source
derives every dependent constant itself. This works for tuple unpacking
(`MOS_L, MOS_W, MOS_H = ...`) and for constants defined after the functions. Never re-derive
dependent constants by hand.

```python
import ast
import sys
import types

import build123d

# Only when the source does `from cadgen import build123d as bd` and cadgen is not installed.
shim = types.ModuleType("cadgen")
shim.build123d = build123d
sys.modules["cadgen"] = shim

SRC, OUT = r"D:/path/to/parts.py", r"D:/path/to/refs"
PARTS = ("bracket",)                     # source part functions to export
CASES = {"default": {}, "T3": {"T": 3.0}, "T8": {"T": 8.0}, "nocsk": {"COUNTERSINK": False}}

def load(values):
    tree = ast.parse(open(SRC, encoding="utf-8").read())
    body, done = [], set()
    for node in tree.body:
        body.append(node)
        if isinstance(node, ast.Assign):
            names = {n.id for t in node.targets for n in ast.walk(t) if isinstance(n, ast.Name)}
            for k in sorted((names & values.keys()) - done):
                body.append(ast.parse(f"{k} = {values[k]!r}").body[0])
                done.add(k)
    assert done == values.keys(), values.keys() - done
    tree.body = body
    module = types.ModuleType("source")
    exec(compile(ast.fix_missing_locations(tree), SRC, "exec"), module.__dict__)
    return module

def overlap_pct(a, b):
    """build123d `a & b` can return a ShapeList, which has no `.volume`."""
    c = a & b
    vol = sum(s.volume for s in c) if isinstance(c, list) else c.volume
    return round(100 * vol / b.volume, 4)

for tag, values in CASES.items():
    src = load(values)
    for name in PARTS:
        build123d.export_step(getattr(src, name)(), f"{OUT}/{name}_{tag}.step")
```

Case keys use the source names; map them to `Params` names in the FreeCAD-side test
(`T` -> `PLATE_T`). An enumeration takes the same text value on both sides (on the FreeCAD side
`feature_set_parameters` `{"feature": "Params", "parameters": {"FASTEN": "tap"}}`; creating the
property is a gap); only expressions compare its index. Check the `default` re-export against any STEP the user gave first:
`build123d.import_step(given)`, equal volume and `overlap_pct` 100.

## Part equality against the source STEP

```python
import Part
ref = Part.read(r"D:/path/to/refs/bracket_default.step")
part = doc.getObjectsByLabel("bracket")[0]
common = part.Shape.common(ref)
result = {"name": part.Name, "ref_vol": ref.Volume,
          "overlap_pct": round(100 * common.Volume / ref.Volume, 4)}
```

Then one `verify_shape` with `object` set to the returned `name` (for an `App::Link`, its Name:
the placement is applied) and `ref_vol` in `expect_volume` (`expect_solid_count` takes the source
solid count; 1 for one solid):

```json
[{"fn": "is_valid_solid", "expect": true},
 {"fn": "expect_solid_count", "expect": 1},
 {"fn": "expect_volume", "expect": 1234.5678, "tol": {"rel": 1e-6}}]
```

Pass: all three checks pass and `overlap_pct` is 100.000. The `rel` tolerance is a fraction of
`ref_vol`: 1e-6 equals `diff_pct` 0.0001, and the default is 0.01 (1 %), too wide for this proof.
Equal volume alone is not equality: a part shifted or rotated keeps its volume and loses
overlap. Do not compare bounding boxes: OCC boxes around tori and cylinders are loose (several mm)
when the volumes are identical.

When a part fails, compare each `<part>_stepN` object against the same partial build in the
source to find the first step that differs.

## Expression coverage

Every primitive size and base position must carry an expression; a plain number there is a
baked value that no parameter edit reaches. A rotation about z with a non-zero angle and no
expression is a baked frame angle. A fixed `rot` about x or y (an axis cylinder, a wedge) needs
no expression. `query_parameters` lists the bindings (`truncated` says when a list is cut at
500 rows); the script below finds each primitive that lacks one.

```python
need = {"Part::Box": ("Length", "Width", "Height"),
        "Part::Cylinder": ("Radius", "Height"),
        "Part::Cone": ("Radius1", "Radius2", "Height"),
        "Part::Wedge": ("Xmin", "Xmax", "X2min", "X2max", "Ymin", "Ymax",
                        "Zmin", "Zmax", "Z2min", "Z2max")}
place = ("Placement.Base.x", "Placement.Base.y", "Placement.Base.z")
unbound = []
for o in doc.Objects:
    if o.TypeId in need:
        bound = {path.lstrip(".") for path, _ in o.ExpressionEngine}
        missing = [q for q in need[o.TypeId] + place if q not in bound]
        r = o.Placement.Rotation
        if (abs(r.Axis.z) > 0.999 and abs(r.Angle) > 1e-9
                and "Placement.Rotation.Angle" not in bound):
            missing.append("Placement.Rotation.Angle")
        if missing:
            unbound.append((o.Name, missing))
result = unbound                          # pass: []
```

## Parameter-limit test with restore

Compare each FreeCAD case with its own re-export, not only with the default STEP. Read the
defaults once with `query_parameters` and keep them. Run each case in five steps:

1. Set the case values with `feature_set_parameters`; the call recomputes the model and returns
   `post_verify`. Set a driver, not a value an expression derives.
   `feature_set_parameters` `{"feature": "Params", "parameters": {"PLATE_T": 3.0, "COUNTERSINK": false}}`
   (a float or integer is a number, a bool is `true` or `false`, an enumeration is its member
   string). A variable that a `query_parameters` binding row `{object: "Params", path: <name>}`
   derives is reset by the recompute with no error: set only variables with no such row. When
   `post_verify.passed` is false or `rolled_back` is true, the case did not apply: record it as
   failed and skip the measurement.
2. Measure the overlap with the case script below: one read-only `common()` per part.
3. Measure the part with typed calls: `verify_recompute` once, and per part the `verify_shape`
   call of the equality check above.
4. Restore the defaults with `feature_set_parameters` and the values from `query_parameters`.
5. Start the next case.

Restore after every case, also when a typed check fails, and before any `document_save`: a case
that runs on top of the previous case's values compares against the wrong re-export. Run one
case per `script_exec` call to stay under the 30 s budget: the script runs one `common()` per
part, about 8 s per case for a 100-object, two-part model.

Case script. It writes nothing:

```python
import Part
REFS = r"D:/path/to/refs"
PARTS = ("bracket",)
tag = "T3"                                                  # the case just set
parts = []
for name in PARTS:
    obj = doc.getObjectsByLabel(name)[0]
    ref = Part.read(f"{REFS}/{name}_{tag}.step")
    parts.append({"name": obj.Name, "ref_vol": ref.Volume,
                  "overlap_pct": round(100 * obj.Shape.common(ref).Volume / ref.Volume, 4)})
result = {"case": tag, "parts": parts}
```

After the last restore, run the part-equality snippet against the `default` references: a frame
or rotation that did not come back keeps its volume, so only the overlap proves the restore.
`query_parameters` must list the default values again.

Pass: every case has `verify_recompute` and `verify_shape` passing and `overlap_pct` 100.0000;
after the restore, the default equality passes again. Pick values at both ends of
the useful range, flip every switch, and choose values that change every fit decision and both
branches of every `min()` / `max()`.

## Interference between parts

`query_interference` `{"objects": ["Cut", "Cut001"]}` takes immutable Names, not Labels (the
generator sets Labels: read each Name with `query_tree_summary`). Name a Body or a Part, not a
feature inside it, and keep the objects in one container. It measures every pair;
`{"pairs": [["Cut", "Cut001"]]}` measures chosen pairs. Pass: `common_volume` at most 0.05 mm3
and `boolean_failed` false. `boolean_failed` true is unmeasured, never zero. With `min_distance` null a shape is not a valid
solid: run `verify_shape` on both parts. With `min_distance` 0 and both parts valid, the parts
touch and the overlap is unmeasured; `Shape.common()` returns the same empty result and reads 0,
so it proves nothing. Measure the overlap through the fused volume (no typed tool does):

```python
a, b = (doc.getObject(n).Shape for n in ("Cut", "Cut001"))
result = round(a.Volume + b.Volume - a.fuse(b).Volume, 3)    # pass: <= 0.05 mm3
```

The result is 0 for parts that only touch and the overlap volume for parts that overlap. For
`interference.too_complex`, measure objects with fewer faces or send fewer pairs.

## Hole checks

One `verify_shape` call covers cylindrical holes (`select` filters by `diameter` or `axis`; the
diameter is a number in mm):

```json
[{"fn": "count_cylindrical_holes", "expect": 4, "select": {"diameter": 5.5}},
 {"fn": "hole_diameter", "expect": 5.5, "select": {"axis": [0, 0, 1]}},
 {"fn": "hole_through", "expect": true, "select": {"axis": [0, 0, 1]}}]
```

`hole_position` with `expect` `[x, y]` needs a `select` that picks one hole. Pass: all checks
pass. A countersink cone is not a cylindrical hole; probe it. A hole of diameter `D` and depth
`H` at `(x, y, z0)`: a disk of diameter `D - 0.1` must not touch material, a disk of `D + 0.1`
must.

```python
def probe(shape, x, y, z, d):
    c = Part.makeCylinder(d / 2, 0.2, App.Vector(x, y, z - 0.1))
    return round(shape.common(c).Volume, 4)
```

## Mesh export

`export_stl` (deflection 0.05 mm, angular 0.2 rad), then `verify_export_stl`: watertight,
volume within its band. Compare the STL bounds with the source STL bounds (0.01 mm).

## Visual

`query_screenshot` of the converted part (`view.include` and `view.exclude` take object
Names, not Labels; leave `include` out to render the visible objects), plus a screenshot of the
real FreeCAD window. The picture confirms the look only; the checks above decide correctness.
