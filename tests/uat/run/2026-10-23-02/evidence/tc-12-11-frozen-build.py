import Part, Sketcher
body = doc.addObject("PartDesign::Body", "Body")
for i in range(26):
    sk = body.newObject("Sketcher::SketchObject", f"Sketch{i:03d}")
    sk.AttachmentSupport = [(doc.getObject("XY_Plane") or body.Origin.OriginFeatures[3], "")]
    sk.MapMode = "FlatFace"
    sk.AttachmentOffset.Base.z = i * 2.0
    x = 0.0
    pts = [(x, 0), (10, 0), (10, 10), (x, 10)]
    for k in range(4):
        a, b = pts[k], pts[(k + 1) % 4]
        sk.addGeometry(Part.LineSegment(App.Vector(a[0], a[1], 0), App.Vector(b[0], b[1], 0)))
    pad = body.newObject("PartDesign::Pad", f"Pad{i:03d}")
    pad.Profile = sk
    pad.Length = 2.0
doc.recompute()
result = (len(doc.Objects), body.Shape.Volume)
