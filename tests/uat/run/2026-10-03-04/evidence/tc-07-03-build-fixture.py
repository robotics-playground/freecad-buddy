"""Build an under-constrained sketch fixture with the fcb-env FreeCAD (outside the bridge).
MCP sketch_add_geometry rolls back any geometry that leaves DoF > 0 (sketches.py:787-789), so an
under-constrained sketch can only reach verify_sketch from a file."""
import FreeCAD, Part, Sketcher
doc = FreeCAD.newDocument("tc07_sketch_under")
sk = doc.addObject("Sketcher::SketchObject", "Sketch")
sk.addGeometry(Part.LineSegment(FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(10, 0, 0)), False)
doc.recompute()
print("geo", sk.GeometryCount, "cons", sk.ConstraintCount, "solve", sk.solve(), "FullyConstrained", sk.FullyConstrained)
out = "D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-03-04/evidence/tc-07-03-underconstrained.FCStd"
doc.saveAs(out); print("saved", out)
