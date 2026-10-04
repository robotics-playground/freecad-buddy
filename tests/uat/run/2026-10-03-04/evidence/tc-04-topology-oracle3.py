"""Outside oracle (FreeCAD 1.1.3 headless): face names of a circle pad (TC-04-11 disc) and of offset rectangle pads (TC-04-12 / TC-04-15)."""
import FreeCAD as App
import Part

doc = App.newDocument("oracle3")
body = doc.addObject("PartDesign::Body", "DiscBody")
sk = body.newObject("Sketcher::SketchObject", "DiscProfile")
sk.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]
sk.MapMode = "FlatFace"
sk.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 30))
pad = body.newObject("PartDesign::Pad", "DiscPad")
pad.Profile = sk
pad.Length = 5
doc.recompute()
for i, f in enumerate(pad.Shape.Faces, 1):
    c = f.CenterOfMass
    print(f"DiscPad Face{i}: {type(f.Surface).__name__} com=({c.x:.2f},{c.y:.2f},{c.z:.2f})")


def rect_pad(name, plane_index, pts, length, midplane=False):
    b = doc.addObject("PartDesign::Body", name + "Body")
    s = b.newObject("Sketcher::SketchObject", name + "Profile")
    s.AttachmentSupport = [(b.Origin.OriginFeatures[plane_index], "")]
    s.MapMode = "FlatFace"
    for i in range(4):
        s.addGeometry(Part.LineSegment(App.Vector(*pts[i], 0), App.Vector(*pts[(i + 1) % 4], 0)))
    p = b.newObject("PartDesign::Pad", name + "Pad")
    p.Profile = s
    p.Length = length
    p.Midplane = midplane
    doc.recompute()
    for i, f in enumerate(p.Shape.Faces, 1):
        c = f.CenterOfMass
        n = f.normalAt(0, 0)
        print(f"{name}Pad Face{i}: com=({c.x:.2f},{c.y:.2f},{c.z:.2f}) n=({n.x:.0f},{n.y:.0f},{n.z:.0f})")


def rect(x0, y0, w, h):
    return [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]


rect_pad("Face", 3, rect(5, 120, 20, 30), 10)
rect_pad("Base", 4, rect(0, 20, 60, 5), 40, midplane=True)
