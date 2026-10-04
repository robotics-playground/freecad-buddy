"""fcb-env FreeCAD: a document with TWO top-level shape objects, for the multi-object default branch
(two-box-compound.FCStd holds ONE Part::Feature whose shape is a 2-solid compound)."""
import FreeCAD, Part
d = FreeCAD.newDocument("tc07_two_objects")
a = d.addObject("Part::Box", "BoxA"); a.Length, a.Width, a.Height = 10, 10, 10
b = d.addObject("Part::Box", "BoxB"); b.Length, b.Width, b.Height = 10, 10, 10; b.Placement.Base = FreeCAD.Vector(20, 0, 0)
d.recompute()
out = "D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-03-04/evidence/tc-07-12-two-objects.FCStd"
d.saveAs(out); print("saved", out, [o.Name for o in d.Objects])
