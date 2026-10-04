"""Outside oracle (FreeCAD 1.1.3 headless, fcb env): subelement names of the reference solids TC-04 builds.

query_object returns properties only, so edge/face names come from an independent FreeCAD build of
the same construction. Nothing here imports freecad_buddy.
"""
import FreeCAD as App
import Part
import Sketcher

doc = App.newDocument("oracle")


def rect_sketch(body, name, w, d, plane="XY"):
    sk = body.newObject("Sketcher::SketchObject", name)
    sk.AttachmentSupport = [(body.Origin.OriginFeatures[{"XY": 3, "XZ": 4, "YZ": 5}[plane]], "")]
    sk.MapMode = "FlatFace"
    pts = [(0, 0), (w, 0), (w, d), (0, d)]
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        sk.addGeometry(Part.LineSegment(App.Vector(*a, 0), App.Vector(*b, 0)))
    return sk


def describe(shape, label):
    print(f"== {label}: faces={len(shape.Faces)} edges={len(shape.Edges)} vol={shape.Volume:.4f}")
    for i, e in enumerate(shape.Edges, 1):
        v = [tuple(round(c, 3) for c in (x.Point.x, x.Point.y, x.Point.z)) for x in e.Vertexes]
        print(f"  Edge{i}: {type(e.Curve).__name__} {v}")
    for i, f in enumerate(shape.Faces, 1):
        c = f.CenterOfMass
        print(f"  Face{i}: {type(f.Surface).__name__} com=({c.x:.2f},{c.y:.2f},{c.z:.2f})")


for origin_fix in [True]:
    body = doc.addObject("PartDesign::Body", "PlateBody")
    sk = rect_sketch(body, "PlateProfile", 60, 40)
    pad = body.newObject("PartDesign::Pad", "PlatePad")
    pad.Profile = sk
    pad.Length = 5
    doc.recompute()
    describe(pad.Shape, "PlatePad 60x40x5")

body2 = doc.addObject("PartDesign::Body", "ShaftBody")
sk2 = body2.newObject("Sketcher::SketchObject", "ShaftProfile")
sk2.AttachmentSupport = [(body2.Origin.OriginFeatures[4], "")]
sk2.MapMode = "FlatFace"
pts = [(0, 0), (5, 0), (5, 20), (0, 20)]
for i in range(4):
    a, b = pts[i], pts[(i + 1) % 4]
    sk2.addGeometry(Part.LineSegment(App.Vector(*a, 0), App.Vector(*b, 0)))
rev = body2.newObject("PartDesign::Revolution", "ShaftRev")
rev.Profile = sk2
rev.ReferenceAxis = (sk2, ["V_Axis"])
rev.Angle = 360
doc.recompute()
describe(rev.Shape, "ShaftRev")
