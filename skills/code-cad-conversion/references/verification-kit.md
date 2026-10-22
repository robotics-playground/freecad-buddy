# Verification kit

Run each snippet with `script_exec` on the converted document. Each is read-only except the
parameter-limit test, which restores every value it changes. Export the source part to STEP
first (build123d `export_step`, CadQuery `cq.exporters.export`), in the same world frame as the
FreeCAD part.

## Re-export the source per case

Run outside FreeCAD (`uv run --with build123d python make_refs.py`). Reload the module per case,
set the constants, re-derive every constant the source computes at import, then export.

```python
import importlib.util
from build123d import export_step

SRC, OUT = r"D:/path/to/part_source.py", r"D:/path/to/refs"
CASES = {"default": {}, "T3": {"T": 3.0}, "T8": {"T": 8.0}, "nocsk": {"COUNTERSINK": False}}

for tag, values in CASES.items():
    spec = importlib.util.spec_from_file_location("src", SRC)
    src = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(src)
    for k, v in values.items():
        setattr(src, k, v)
    src.BOSS_H = src.T + 7.0                 # every derived constant of the source
    export_step(src.bracket(), f"{OUT}/ref_{tag}.step")
```

Case keys use the source names; map them to `Params` names (`T` -> `PLATE_T`) in the
FreeCAD-side test.

## Part equality against the source STEP

```python
import Part
ref = Part.read(r"D:/path/to/part.step")
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
baked value that no parameter edit reaches.

```python
need = {"Part::Box": ("Length", "Width", "Height"),
        "Part::Cylinder": ("Radius", "Height"),
        "Part::Cone": ("Radius1", "Radius2", "Height")}
place = ("Placement.Base.x", "Placement.Base.y", "Placement.Base.z",
         "Placement.Rotation.Angle")      # drop the angle for a primitive with a fixed `rot`
unbound = []
for o in doc.Objects:
    if o.TypeId in need:
        bound = {path.lstrip(".") for path, _ in o.ExpressionEngine}
        missing = [q for q in need[o.TypeId] + place if q not in bound]
        if missing:
            unbound.append((o.Name, missing))
result = unbound                          # pass: []
```

## Parameter-limit test with restore

Re-export the source with each case's values first (set the constants on the imported module,
recompute its derived constants, call the part function, `export_step` to `ref_<case>.step`).
Compare each FreeCAD case with its own re-export, not only with the default STEP.

```python
import Part
V = doc.getObject("Params")
part = doc.getObjectsByLabel("bracket")[0]
before = round(part.Shape.Volume, 4)
cases = {"T3": {"PLATE_T": 3.0}, "T8": {"PLATE_T": 8.0}, "nocsk": {"COUNTERSINK": False}}
log = []
for tag, values in cases.items():
    old = {k: getattr(V, k) for k in values}
    for k, v in values.items():
        setattr(V, k, v)
    doc.recompute()
    ref, s = Part.read(rf"D:/path/to/ref_{tag}.step"), part.Shape
    log.append({"case": tag, "valid": s.isValid(), "solids": len(s.Solids),
                "diff_pct": round(100 * (s.Volume - ref.Volume) / ref.Volume, 4),
                "overlap_pct": round(100 * s.common(ref).Volume / ref.Volume, 4),
                "invalid": [o.Name for o in doc.Objects if "Invalid" in o.State]})
    for k, v in old.items():
        setattr(V, k, v)
doc.recompute()
ref = Part.read(r"D:/path/to/ref_default.step")
result = {"log": log, "restored": round(part.Shape.Volume, 4) == before,
          "restored_overlap_pct": round(100 * part.Shape.common(ref).Volume / ref.Volume, 4)}
```

Pass: every case valid, one solid, no `Invalid` objects, `diff_pct` 0.0000, `overlap_pct`
100.0000, `restored` true, `restored_overlap_pct` 100.0000. Pick values near both ends of the useful range, and flip every bool.
Each recompute counts against the 30 s budget: split a long case list over several calls.

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

`query_screenshot` of the converted part, plus a screenshot of the real FreeCAD window. The
picture confirms the look only; the checks above decide correctness.
