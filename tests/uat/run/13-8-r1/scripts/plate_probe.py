import math
import sys
import time

import FreeCAD
import Part

V = FreeCAD.Vector
for n in (1499, 9000):
    t = time.perf_counter()
    side = int(math.ceil(math.sqrt(n)))
    size = 4 * side + 4
    outer = Part.Wire(Part.makePolygon([V(0, 0, 0), V(size, 0, 0), V(size, size, 0), V(0, size, 0), V(0, 0, 0)]))
    holes = []
    for i in range(n):
        w = Part.Wire(Part.makeCircle(1, V(4 + 4 * (i % side), 4 + 4 * (i // side), 0)))
        w.reverse()
        holes.append(w)
    face = Part.Face(Part.Plane(), [outer] + holes)
    solid = face.extrude(V(0, 0, 5))
    sys.stderr.write(
        f"n={n} faces={len(solid.Faces)} solids={len(solid.Solids)} valid={solid.isValid()} "
        f"vol={solid.Volume:.3f} expect={(size * size - n * math.pi) * 5:.3f} t={time.perf_counter() - t:.2f}s\n"
    )
