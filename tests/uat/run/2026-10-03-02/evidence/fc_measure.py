# Run inside FreeCAD's own Python console. Uses only the FreeCAD API: no freecad_buddy import.
# For every open document: the Body's final shape volume, bounding box, validity, and each
# cylindrical face (diameter, axis, centre). Writes fc_measure.json next to this file.
import json, os
import FreeCAD as App
import Part

OUT = os.path.join(os.path.dirname(r"D:\Work\Personal\Sources\freecad-buddy\tests\uat\run\2026-10-03-02\evidence\fc_measure.py"), "fc_measure.json")
rows = []
for doc in App.listDocuments().values():
    bodies = [o for o in doc.Objects if o.TypeId == "PartDesign::Body"]
    shape = bodies[0].Shape
    bb = shape.BoundBox
    cyl = []
    for face in shape.Faces:
        s = face.Surface
        if isinstance(s, Part.Cylinder):
            cyl.append({"d": round(2 * s.Radius, 4), "axis": [round(v, 4) for v in s.Axis],
                        "center": [round(v, 3) for v in s.Center], "area": round(face.Area, 3)})
    rows.append({"doc": doc.Label, "tip": bodies[0].Tip.Name if bodies[0].Tip else None,
                 "volume": round(shape.Volume, 3), "valid": shape.isValid(),
                 "solids": len(shape.Solids),
                 "bbox": [round(v, 3) for v in (bb.XMin, bb.XMax, bb.YMin, bb.YMax, bb.ZMin, bb.ZMax)],
                 "cylinders": cyl})
with open(OUT, "w") as fh:
    json.dump(rows, fh, indent=1)
for r in rows:
    print(r["doc"][14:], "V=%s" % r["volume"], "valid=%s" % r["valid"], "bbox=%s" % r["bbox"], "cyl=%d" % len(r["cylinders"]))
print("FC_MEASURE_DONE %d docs" % len(rows))
