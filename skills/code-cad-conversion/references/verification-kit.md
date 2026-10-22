# Verification kit

Run the FreeCAD snippets with `script_exec` on the converted document. Each is read-only except
the parameter-limit test, which restores every value it changes. The re-export script runs
outside FreeCAD and writes one reference STEP per case, in the same world frame as the FreeCAD
part.

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
(`T` -> `PLATE_T`). An enumeration takes the same text value on both sides:
`setattr(V, "FASTEN", "tap")`; only expressions compare its index. Check the `default` re-export against any STEP the user gave first:
`build123d.import_step(given)`, equal volume and `overlap_pct` 100.

## Part equality against the source STEP

```python
import Part
ref = Part.read(r"D:/path/to/refs/bracket_default.step")
part = doc.getObjectsByLabel("bracket")[0]
shape = part.Shape                                   # use Part.getShape(obj) for links
common = shape.common(ref)
result = {
    "valid": shape.isValid(),
    "solids": len(shape.Solids),
    "vol": round(shape.Volume, 4),
    "ref_vol": round(ref.Volume, 4),
    "diff_pct": round(100 * (shape.Volume - ref.Volume) / ref.Volume, 4),
    "overlap_pct": round(100 * common.Volume / ref.Volume, 4),
}
```

Pass: `valid` true, `solids` 1 (or the source count), `diff_pct` 0.000, `overlap_pct` 100.000.
Equal volume alone is not equality: a part shifted or rotated keeps its volume and loses
overlap. Do not compare bounding boxes: OCC boxes around tori and cylinders are loose (several mm)
when the volumes are identical.

When a part fails, compare each `<part>_stepN` object against the same partial build in the
source to find the first step that differs.

## Expression coverage

Every primitive size and base position must carry an expression; a plain number there is a
baked value that no parameter edit reaches. A rotation about z with a non-zero angle and no
expression is a baked frame angle. A fixed `rot` about x or y (an axis cylinder, a wedge) needs
no expression.

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

Compare each FreeCAD case with its own re-export, not only with the default STEP. Each case
recomputes the model and runs one `common()` per part: about 8 s per case for a 100-object,
two-part model. Run two cases per call to stay under the 30 s budget.

```python
import Part
REFS = r"D:/path/to/refs"
PARTS = ("bracket",)
V = doc.getObject("Params")
cases = {"T3": {"PLATE_T": 3.0}, "T8": {"PLATE_T": 8.0}}    # two per call
log = []
for tag, values in cases.items():
    old = {k: getattr(V, k) for k in values}
    try:
        for k, v in values.items():
            setattr(V, k, v)
        doc.recompute()
        for name in PARTS:
            s, ref = doc.getObjectsByLabel(name)[0].Shape, Part.read(f"{REFS}/{name}_{tag}.step")
            log.append({"case": tag, "part": name, "valid": s.isValid(), "solids": len(s.Solids),
                        "diff_pct": round(100 * (s.Volume - ref.Volume) / ref.Volume, 4),
                        "overlap_pct": round(100 * s.common(ref).Volume / ref.Volume, 4),
                        "invalid": [o.Name for o in doc.Objects if "Invalid" in o.State]})
    finally:
        for k, v in old.items():
            setattr(V, k, v)
        doc.recompute()
result = log
```

After the last batch, run the part-equality snippet against the `default` references: a frame
or rotation that did not come back keeps its volume, so only the overlap proves the restore.

Pass: every case valid, one solid, no `Invalid` objects, `diff_pct` 0.0000, `overlap_pct`
100.0000; after the restore, the default equality passes again. Pick values at both ends of
the useful range, flip every switch, and choose values that change every fit decision and both
branches of every `min()` / `max()`.

## Interference between parts

```python
a, b = (doc.getObjectsByLabel(n)[0].Shape for n in ("board", "box_base"))
result = round(a.common(b).Volume, 3)    # pass: <= 0.05 mm3
```

## Hole probe

A hole of diameter `D` and depth `H` at `(x, y, z0)`: a disk of diameter `D - 0.1` must not
touch material, a disk of `D + 0.1` must.

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
