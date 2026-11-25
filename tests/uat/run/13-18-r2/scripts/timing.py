"""Verifier timing of feature_loft / feature_sweep at the accepted limits (freecadcmd, host).

Case name in env FCB_CASE. Prints one JSON line TIMING=... to stderr.
"""

import json
import math
import os
import sys
import time

sys.path.insert(0, r"D:\Work\Personal\Sources\fcb-verify-13-18\src")

import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402

from freecad_buddy.usecases import confirm, features  # noqa: E402
from freecad_buddy.usecases.documents import DocumentRegistry  # noqa: E402

confirm.set_auto_approve(True)
registry = DocumentRegistry()
handle = registry.document_create("timing")["structured_content"]["doc"]
doc = registry.with_document(handle, lambda h, d: d)
body = doc.addObject("PartDesign::Body", "Body")


def sketch(name, z=0.0, rotation=None):
    s = doc.addObject("Sketcher::SketchObject", name)
    body.addObject(s)
    s.Placement = App.Placement(App.Vector(0, 0, z), rotation or App.Rotation())
    return s


def block_all(s):
    s.addConstraint([Sketcher.Constraint("Block", i) for i in range(s.GeometryCount)])


def polygon(name, n, radius, z=0.0, centre=(0.0, 0.0), rotation=None):
    s = sketch(name, z, rotation)
    pts = [
        App.Vector(centre[0] + radius * math.cos(2 * math.pi * i / n),
                   centre[1] + radius * math.sin(2 * math.pi * i / n), 0)
        for i in range(n)
    ]
    s.addGeometry([Part.LineSegment(pts[i], pts[(i + 1) % n]) for i in range(n)], False)
    block_all(s)
    return s


def bspline(name, points, radius, z=0.0, centre=(0.0, 0.0), rotation=None):
    s = sketch(name, z, rotation)
    curve = Part.BSplineCurve()
    pts = [
        App.Vector(centre[0] + radius * (1 + 0.05 * math.sin(7 * 2 * math.pi * i / points))
                   * math.cos(2 * math.pi * i / points),
                   centre[1] + radius * (1 + 0.05 * math.sin(7 * 2 * math.pi * i / points))
                   * math.sin(2 * math.pi * i / points), 0)
        for i in range(points)
    ]
    curve.interpolate(pts, PeriodicFlag=True)
    s.addGeometry(curve, False)
    block_all(s)
    return s


def part_spine(name, shape):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    return obj



def circle(name, r, z=0.0, centre=(0.0, 0.0), rotation=None):
    s = sketch(name, z, rotation)
    s.addGeometry(Part.Circle(App.Vector(centre[0], centre[1], 0), App.Vector(0, 0, 1), r), False)
    block_all(s)
    return s


def loft(profile, sections, **kw):
    return lambda: features.feature_loft(registry, doc=handle, body="Body", profile=profile,
                                         sections=sections, name="Lofted", **kw)


def sweep(spine, **kw):
    return lambda: features.feature_sweep(registry, doc=handle, body="Body", profile="Prof",
                                          spine=spine, name="Swept", **kw)


WHOLE = {"kind": "mapped_name", "object": "Spine"}
ROT = App.Rotation(App.Vector(1, 0, 0), 90)
case = os.environ["FCB_CASE"]
info = {"case": case}
if case == "loft_two_3999gons":
    polygon("A", 3999, 20.0); polygon("B", 3999, 15.0, z=20.0); call = loft("A", ["B"])
elif case == "loft_circle_to_4000gon":
    circle("A", 20.0); polygon("B", 4000, 15.0, z=20.0); call = loft("A", ["B"])
elif case == "loft_circle_to_1000gon":
    circle("A", 20.0); polygon("B", 1000, 15.0, z=20.0); call = loft("A", ["B"])
elif case == "loft_two_1000gons":
    polygon("A", 1000, 20.0); polygon("B", 1000, 15.0, z=20.0); call = loft("A", ["B"])
elif case == "loft_500x44":
    names = []
    for k in range(500):
        polygon(f"S{k}", 44, 20.0 + 2.0 * math.sin(k / 10.0), z=1.0 * k); names.append(f"S{k}")
    call = loft(names[0], names[1:])
elif case == "loft_circle_to_bspline1000":
    circle("A", 20.0); bspline("B", 998, 15.0, z=20.0)
    info["poles"] = len(doc.getObject("B").Shape.Edges[0].Curve.getPoles()) if doc.recompute() is not None or True else 0
    call = loft("A", ["B"])
elif case == "loft_two_bspline1000":
    bspline("A", 998, 20.0); bspline("B", 998, 15.0, z=20.0); call = loft("A", ["B"])
elif case == "loft_two_250gons_bopcheck":
    polygon("A", 250, 20.0); polygon("B", 250, 15.0, z=20.0); call = loft("A", ["B"])
elif case == "sweep_circle_3000_lines":
    circle("Prof", 1.5)
    pts = [App.Vector(3.0 * math.sin(i / 150.0), 3.0 * (1 - math.cos(i / 150.0)), 0.01 * i) for i in range(3001)]
    part_spine("Spine", Part.makePolygon(pts)); call = sweep(WHOLE)
elif case == "sweep_circle_10000_lines":
    circle("Prof", 1.5)
    pts = [App.Vector(3.0 * math.sin(i / 150.0), 3.0 * (1 - math.cos(i / 150.0)), 0.01 * i) for i in range(10001)]
    part_spine("Spine", Part.makePolygon(pts)); call = sweep(WHOLE)
elif case == "sweep_bspline3000_line":
    bspline("Prof", 2998, 1.5)
    part_spine("Spine", Part.makePolygon([App.Vector(0, 0, 0), App.Vector(0, 0, 30)])); call = sweep(WHOLE)
elif case == "sweep_bspline150_helix20":
    bspline("Prof", 148, 1.5, centre=(10.0, 0.0), rotation=ROT)
    part_spine("Spine", Part.makeHelix(5.0, 100.0, 10.0)); call = sweep(WHOLE, mode="frenet")
elif case == "sweep_10gon_30lines_bopcheck":
    polygon("Prof", 10, 1.5)
    pts = [App.Vector(3.0 * math.sin(i / 15.0), 3.0 * (1 - math.cos(i / 15.0)), 1.0 * i) for i in range(31)]
    part_spine("Spine", Part.makePolygon(pts)); call = sweep(WHOLE)
elif case == "sweep_helix120":
    circle("Prof", 0.5, centre=(10.0, 0.0), rotation=ROT)
    h = doc.addObject("Part::Helix", "Spine"); h.Pitch = 2.0; h.Height = 240.0; h.Radius = 10.0
    call = sweep(WHOLE, mode="frenet")
elif case == "sweep_doubled_back":
    circle("Prof", 3.0)
    sp = sketch("Path", 0.0, ROT)
    curve = Part.BSplineCurve()
    curve.interpolate([App.Vector(0.5 * i * math.cos(i * 0.3), 0, 0) for i in range(8)])
    sp.addGeometry(curve, False)
    call = sweep("Path")
else:
    raise SystemExit("unknown case " + case)
doc.recompute()
start = time.perf_counter()
try:
    env = call()
    info["status"] = env["status"]
    detail = env.get("detail") or {}
    info["code"] = detail.get("code")
    info["detail"] = str(detail.get("message"))[:200]
    sc = env.get("structured_content") or {}
    ss = (sc.get("feature_state") or {}).get("shape_summary") or {}
    info["volume"] = ss.get("volume"); info["valid"] = ss.get("is_valid"); info["faces"] = ss.get("face_count")
except features.LoftSweepRefusal as exc:
    info["status"] = "REFUSED"; info["code"] = exc.code; info["detail"] = str(exc)[:200]
except Exception as exc:  # noqa: BLE001
    info["status"] = "EXC"; info["detail"] = repr(exc)[:300]
info["elapsed_s"] = round(time.perf_counter() - start, 2)
sys.stderr.write("\nTIMING=" + json.dumps(info) + "\n")
