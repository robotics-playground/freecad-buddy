import FreeCAD
d = FreeCAD.openDocument("D:/Work/Personal/Sources/freecad-buddy/benchmarks/g0/fault-injection/non-watertight-open-shell/fixture.FCStd")
for o in d.Objects:
    s = o.Shape
    print(o.Name, o.TypeId, "ShapeType", s.ShapeType, "faces", len(s.Faces), "shells", len(s.Shells), "solids", len(s.Solids), "area", round(s.Area, 3), "bbox", [round(s.BoundBox.XLength,3), round(s.BoundBox.YLength,3), round(s.BoundBox.ZLength,3)])
