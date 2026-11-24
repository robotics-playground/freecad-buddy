import sys, hashlib, io
import FreeCAD as App, Part
V = App.Vector
def h(s):
    return hashlib.sha256(s.exportBrepToString().encode()).hexdigest()[:12]
def make():
    c = [(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)]
    return {"A": Part.makeBox(10, 10, 10), "Sep": Part.makeBox(10, 10, 10, V(20, 0, 0)), "Over": Part.makeBox(10, 10, 10, V(5, 5, 5)),
            "Cyl": Part.makeCylinder(3, 30, V(5, 5, -10)), "Bowtie": Part.Face(Part.makePolygon([V(x, y, 0) for x, y in c])).extrude(V(0, 0, 10))}
for op in ("common", "distToShape"):
    for pair in (("A", "Sep"), ("A", "Over"), ("A", "Cyl"), ("A", "Bowtie")):
        s = make(); a, b = s[pair[0]], s[pair[1]]
        ha, hb = h(a), h(b)
        getattr(a, op)(b)
        sys.stderr.write("PROBE %-11s %-10s a_changed=%s b_changed=%s\n" % (op, "/".join(pair), h(a) != ha, h(b) != hb))
# does a copy protect the original?
s = make(); a, b = s["A"], s["Over"]; ha = h(a); a.copy().common(b.copy()); sys.stderr.write("PROBE copy-common a_changed=%s\n" % (h(a) != ha))
