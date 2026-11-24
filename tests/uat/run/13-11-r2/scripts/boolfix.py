import Sketcher
doc.openTransaction("boolean fixture")
b2 = doc.addObject("PartDesign::Body", "Body2")
sk = b2.newObject("Sketcher::SketchObject", "SkC")
sk.AttachmentSupport = [([f for f in b2.Origin.OriginFeatures if f.Role == "XY_Plane"][0], "")]
sk.MapMode = "FlatFace"
pts = [(25, -5), (35, -5), (35, 5), (25, 5)]
for i in range(4):
    a, c = pts[i], pts[(i + 1) % 4]
    sk.addGeometry(Part.LineSegment(App.Vector(a[0], a[1], 0), App.Vector(c[0], c[1], 0)), False)
for i in range(4):
    sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
pc = b2.newObject("PartDesign::Pad", "PadC"); pc.Profile = sk; pc.Length = 10
doc.recompute()
body = doc.getObject("Body")
boo = body.newObject("PartDesign::Boolean", "Bool")
boo.addObjects([b2])
doc.recompute()
doc.commitTransaction()
result = {"tip": body.Tip.Name, "body_volume": round(body.Shape.Volume, 3), "Body2_inlist": [o.Name for o in b2.InList],
          "bool_group": [o.Name for o in boo.Group], "UndoCount": doc.UndoCount, "invalid": [o.Name for o in doc.Objects if "Invalid" in o.State]}
