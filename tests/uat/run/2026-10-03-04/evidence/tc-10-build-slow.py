"""Build tc-10-slow-<delay>.FCStd outside the product (fcb python). Usage: tc-10-build-slow.py <delay>..."""
import sys
import FreeCAD
import tc10_slowfeat

for delay in sys.argv[1:]:
    doc = FreeCAD.newDocument(f"slow{delay}")
    obj = doc.addObject("Part::FeaturePython", "Slow")
    tc10_slowfeat.Slow(obj)
    doc.recompute()
    obj.Delay = float(delay)
    path = f"D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-03-04/evidence/tc-10-slow-{delay}.FCStd"
    doc.saveAs(path)
    print(path, obj.Shape.Volume, obj.Delay)
    FreeCAD.closeDocument(doc.Name)
