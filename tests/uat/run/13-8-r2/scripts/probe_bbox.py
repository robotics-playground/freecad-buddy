import sys

import FreeCAD as App
import Part

V = App.Vector
shapes = {
    "nurbs_cyl": Part.makeCylinder(10, 30).toNurbs(),
    "nurbs_sphere": Part.makeSphere(10).toNurbs(),
    "nurbs_torus": Part.makeTorus(20, 5).toNurbs(),
    "bspline_extrude": Part.Face(
        Part.Wire(
            Part.BSplineCurve(
                [V(-10, 0, 0), V(-5, 8, 0), V(5, 8, 0), V(10, 0, 0), V(5, -8, 0), V(-5, -8, 0), V(-10, 0, 0)],
                None, None, True, 3, None, False,
            ).toShape()
        )
    ).extrude(V(0, 0, 5)),
}
for name, shape in shapes.items():
    for normal, offset in ((V(0, 0, 1), 1e-6), (V(0, 0, 1), 2.5), (V(0, 0, 1), 15), (V(1, 0, 0), 3), (V(1, 1, 1).normalize(), 2)):
        box = shape.BoundBox
        base = box.Center + normal * (offset - normal.dot(box.Center))
        half = box.DiagonalLength + 1
        face = Part.Plane(base, normal).toShape(-half, half, -half, half)
        edges = shape.section(face).Edges
        if not edges:
            continue
        loose = Part.Compound(edges).BoundBox
        tight = Part.Compound(edges).optimalBoundingBox()
        diff = max(abs(a - b) for a, b in zip(
            (loose.XMin, loose.YMin, loose.ZMin, loose.XMax, loose.YMax, loose.ZMax),
            (tight.XMin, tight.YMin, tight.ZMin, tight.XMax, tight.YMax, tight.ZMax)))
        types = sorted({type(e.Curve).__name__ for e in edges})
        sys.stderr.write(f"BBOX {name} n={tuple(round(c, 3) for c in normal)} off={offset} types={types} max_diff={diff:.6f}\n")
