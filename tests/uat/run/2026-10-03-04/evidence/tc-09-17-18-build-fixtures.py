"""Build the two faulted fixtures under headless FreeCAD (fcb env, FreeCADCmd-style import).

tc-09-17-fixture.FCStd: Body/Sketch/Pad where the Sketch geometry was deleted after the pad -> Pad cannot rebuild.
tc-09-18-fixture.FCStd: Body/Sketch/Pad where the Sketch object itself was removed -> Pad.Profile broken reference.
"""
import FreeCAD as App
import Part
import Sketcher

EV = "D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-03-04/evidence"


def build(label):
    doc = App.newDocument(label)
    body = doc.addObject("PartDesign::Body", "Body")
    sk = body.newObject("Sketcher::SketchObject", "Sketch")
    sk.AttachmentSupport = [(doc.getObject("XY_Plane") or body.Origin.OriginFeatures[3], "")]
    sk.MapMode = "FlatFace"
    pts = [App.Vector(0, 0, 0), App.Vector(20, 0, 0), App.Vector(20, 20, 0), App.Vector(0, 20, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sk
    pad.Length = 10
    doc.recompute()
    print(label, "clean pad volume", pad.Shape.Volume, "state", pad.State)
    return doc, body, sk, pad


doc, body, sk, pad = build("TC0917Broken")
sk.deleteAllGeometry()
doc.recompute()
print("17 after emptying sketch:", "pad state", pad.State, "status", pad.getStatusString(), "valid", pad.isValid())
doc.saveAs(EV + "/tc-09-17-fixture.FCStd")

doc2, body2, sk2, pad2 = build("TC0918Broken")
body2.removeObject(sk2)
doc2.removeObject("Sketch")
doc2.recompute()
print("18 after deleting sketch:", "pad state", pad2.State, "status", pad2.getStatusString(), "profile", pad2.Profile)
doc2.saveAs(EV + "/tc-09-18-fixture.FCStd")
