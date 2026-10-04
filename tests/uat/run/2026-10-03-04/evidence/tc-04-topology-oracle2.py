"""Outside oracle (FreeCAD 1.1.3 headless): edge identities through the TC-04-10 / TC-04-20 dress-up chains."""
import FreeCAD as App
import Part

doc = App.newDocument("oracle2")


def plate(prefix):
    body = doc.addObject("PartDesign::Body", prefix + "Body")
    sk = body.newObject("Sketcher::SketchObject", prefix + "Profile")
    sk.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]
    sk.MapMode = "FlatFace"
    pts = [(0, 0), (60, 0), (60, 40), (0, 40)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(App.Vector(*pts[i], 0), App.Vector(*pts[(i + 1) % 4], 0)))
    pad = body.newObject("PartDesign::Pad", prefix + "Pad")
    pad.Profile = sk
    pad.Length = 5
    doc.recompute()
    return body, pad


def edge_desc(shape, name):
    e = shape.getElement(name)
    v = [tuple(round(c, 2) for c in (x.Point.x, x.Point.y, x.Point.z)) for x in e.Vertexes]
    return f"{name}: {type(e.Curve).__name__} len={e.Length:.2f} {v}"


body, pad = plate("A")
c1 = body.newObject("PartDesign::Chamfer", "EqualChamfer")
c1.Base = (pad, ["Edge1"])
c1.Size = 1.5
doc.recompute()
print("EqualChamfer", c1.Shape.Volume, len(c1.Shape.Faces), edge_desc(c1.Shape, "Edge3"))
c2 = body.newObject("PartDesign::Chamfer", "TwoSizeChamfer")
c2.Base = (c1, ["Edge3"])
c2.ChamferType = "Two distances"
c2.Size = 2
c2.Size2 = 1
doc.recompute()
print("TwoSizeChamfer", c2.Shape.Volume, len(c2.Shape.Faces), c2.Shape.isValid(), edge_desc(c2.Shape, "Edge5"))

body, pad = plate("B")
f1 = body.newObject("PartDesign::Fillet", "DefaultFillet")
f1.Base = (pad, ["Edge1"])
doc.recompute()
print("DefaultFillet radius", f1.Radius, f1.Shape.Volume, edge_desc(f1.Shape, "Edge3"))

print("TwoSizeChamfer vertical edges:")
for i, e in enumerate(c2.Shape.Edges, 1):
    if abs(e.Length - 5) < 1e-6:
        print(" ", edge_desc(c2.Shape, f"Edge{i}"))
c3 = body.newObject("PartDesign::Chamfer", "AngleProbe")
