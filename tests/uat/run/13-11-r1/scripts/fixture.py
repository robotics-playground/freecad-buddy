import Sketcher
doc.openTransaction("fixture")
def rect(body, name, x0, y0, w, h, z):
    sk = body.newObject("Sketcher::SketchObject", name)
    xy = [f for f in body.Origin.OriginFeatures if f.Role == "XY_Plane"][0]
    sk.AttachmentSupport = [(xy, "")]
    sk.MapMode = "FlatFace"
    sk.AttachmentOffset = App.Placement(App.Vector(0, 0, z), App.Rotation())
    pts = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        sk.addGeometry(Part.LineSegment(App.Vector(a[0], a[1], 0), App.Vector(b[0], b[1], 0)), False)
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    return sk
body = doc.addObject("PartDesign::Body", "Body")
s1 = rect(body, "Sketch1", 0, 0, 20, 20, 0)
p1 = body.newObject("PartDesign::Pad", "Pad1"); p1.Profile = s1; p1.Length = 10
doc.recompute()
s2 = rect(body, "Sketch2", 5, 5, 10, 10, 10)
p2 = body.newObject("PartDesign::Pad", "Pad2"); p2.Profile = s2; p2.Length = 5
vs = doc.addObject("App::VarSet", "VS"); vs.addProperty("App::PropertyLength", "L", "Parameters"); vs.L = 5
p2.setExpression("Length", "VS.L")
b2 = doc.addObject("PartDesign::Body", "Body001")
s3 = rect(b2, "Sketch3", 40, 0, 10, 10, 0)
p3 = b2.newObject("PartDesign::Pad", "Pad3"); p3.Profile = s3; p3.Length = 8
doc.recompute()
doc.commitTransaction()
result = {"objects": [o.Name for o in doc.Objects], "tip": body.Tip.Name, "pad2_outlist": [o.Name for o in p2.OutList],
          "UndoCount": doc.UndoCount, "RedoCount": doc.RedoCount, "pad2_zmax": p2.Shape.BoundBox.ZMax,
          "invalid": [o.Name for o in doc.Objects if "Invalid" in o.State]}
