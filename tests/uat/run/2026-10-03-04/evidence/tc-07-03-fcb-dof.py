import FreeCAD
d = FreeCAD.openDocument("D:/Work/Personal/Sources/freecad-buddy/tests/uat/run/2026-10-03-04/evidence/tc-07-03-underconstrained.FCStd")
sk = d.getObject("Sketch")
print("after open: DoF attr", getattr(sk, "DoF", "<none>"), "FullyConstrained", sk.FullyConstrained)
d.recompute(); print("after doc.recompute: DoF", getattr(sk, "DoF", "<none>"))
sk.solve(); print("after solve(): DoF", getattr(sk, "DoF", "<none>"), "FullyConstrained", sk.FullyConstrained)
