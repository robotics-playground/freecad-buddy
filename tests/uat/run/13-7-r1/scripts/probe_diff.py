import sys, difflib
import FreeCAD as App, Part
V = App.Vector
a = Part.makeBox(10, 10, 10); b = Part.makeBox(10, 10, 10, V(20, 0, 0))
before = a.exportBrepToString().splitlines()
tol_before = [e.Tolerance for e in a.Edges]
a.common(b)
after = a.exportBrepToString().splitlines()
d = [l for l in difflib.unified_diff(before, after, lineterm="", n=0) if not l.startswith(("---", "+++"))]
sys.stderr.write("DIFF lines=%d\n" % len(d))
for l in d[:24]: sys.stderr.write("DIFF " + l + "\n")
sys.stderr.write("DIFF tol same=%s vol=%s valid=%s\n" % (tol_before == [e.Tolerance for e in a.Edges], a.Volume, a.isValid()))
