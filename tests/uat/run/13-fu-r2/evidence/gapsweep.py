import sys, os
SRC = os.environ["FCB_SRC"]; sys.path.insert(0, SRC)
import FreeCAD as App, Part
from freecad_buddy.usecases import queries
assert queries.__file__.replace("\\", "/").startswith(SRC.replace("\\", "/")), queries.__file__
print("code under test:", queries.__file__, flush=True)
V = App.Vector; box = Part.makeBox; sph = Part.makeSphere
def m(label, a, b, tol=None):
    if tol: a.fixTolerance(tol); b.fixTolerance(tol)
    true = a.distToShape(b)[0]
    print(f"{label}: distToShape={true:.4g} -> measure={queries._measure_interference(a.copy(), b.copy())}", flush=True)
for g in (1.5e-7, 2e-7):
    m(f"gap edge {g}", box(10,10,10), box(10,10,10,V(10+g,10+g,0)))
    m(f"gap sphere-sphere {g}", sph(5), sph(5,V(10+g,0,0)))
for g in (1e-3, 5e-3, 9e-3, 1.5e-2, 2e-2):
    m(f"tol1e-2 gap sphere-sphere {g}", sph(5), sph(5,V(10+g,0,0)), 1e-2)
    m(f"tol1e-2 gap vertex {g}", box(10,10,10), box(10,10,10,V(10+g,10+g,10+g)), 1e-2)
for g in (5e-4, 1e-3, 2e-3):
    m(f"tol1e-3 gap sphere-box {g}", box(10,10,10), sph(5,V(5,5,15+g)), 1e-3)
