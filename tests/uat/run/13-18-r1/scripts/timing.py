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


case = os.environ["FCB_CASE"]
info = {"case": case}
build_start = time.perf_counter()
if case == "loft_lines_40x200":
    names = []
    for k in range(40):
        polygon(f"S{k}", 200, 20.0 - 0.1 * k, z=2.0 * k)
        names.append(f"S{k}")
    call = lambda: features.feature_loft(registry, doc=handle, body="Body", profile=names[0],
                                         sections=names[1:], name="Lofted")
    shapes = [doc.getObject(n) for n in names]
elif case == "loft_bspline_max":
    # pick sketch count so cost <= 8000 with ~400-pole BSplines
    probe = bspline("Probe", 399, 20.0)
    doc.recompute()
    poles = len(probe.Shape.Edges[0].Curve.getPoles())
    doc.removeObject("Probe")
    count = 8000 // poles
    info["poles_each"] = poles
    names = []
    for k in range(count):
        bspline(f"S{k}", 399, 20.0 - 0.2 * k, z=3.0 * k)
        names.append(f"S{k}")
    call = lambda: features.feature_loft(registry, doc=handle, body="Body", profile=names[0],
                                         sections=names[1:], name="Lofted")
elif case == "loft_500x16":
    names = []
    for k in range(500):
        polygon(f"S{k}", 16, 20.0 + 2.0 * math.sin(k / 10.0), z=1.0 * k)
        names.append(f"S{k}")
    call = lambda: features.feature_loft(registry, doc=handle, body="Body", profile=names[0],
                                         sections=names[1:], name="Lofted")
elif case == "sweep_100x100_lines":
    polygon("Prof", 100, 1.5)
    pts = [App.Vector(3.0 * math.sin(i / 15.0), 3.0 * (1 - math.cos(i / 15.0)), 1.0 * i)
           for i in range(101)]
    part_spine("Spine", Part.makePolygon(pts))
    call = lambda: features.feature_sweep(registry, doc=handle, body="Body", profile="Prof",
                                          spine={"kind": "mapped_name", "object": "Spine"},
                                          name="Swept")
elif case == "sweep_bspline500_helix20":
    rot = App.Rotation(App.Vector(1, 0, 0), 90)
    bspline("Prof", 480, 1.5, centre=(10.0, 0.0), rotation=rot)
    part_spine("Spine", Part.makeHelix(5.0, 100.0, 10.0))
    call = lambda: features.feature_sweep(registry, doc=handle, body="Body", profile="Prof",
                                          spine={"kind": "mapped_name", "object": "Spine"},
                                          name="Swept", mode="frenet")
elif case == "sweep_250_helix25":
    rot = App.Rotation(App.Vector(1, 0, 0), 90)
    polygon("Prof", 250, 1.5, centre=(10.0, 0.0), rotation=rot)
    part_spine("Spine", Part.makeHelix(5.0, 125.0, 10.0))
    call = lambda: features.feature_sweep(registry, doc=handle, body="Body", profile="Prof",
                                          spine={"kind": "mapped_name", "object": "Spine"},
                                          name="Swept", mode="frenet")
elif case == "sweep_doubled_back":
    s0 = doc.addObject("Sketcher::SketchObject", "Prof")
    body.addObject(s0)
    s0.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 3.0), False)
    s0.addConstraint(Sketcher.Constraint("Radius", 0, 3.0))
    s0.addConstraint(Sketcher.Constraint("Coincident", 0, 3, -1, 1))
    sp = sketch("Path", 0.0, App.Rotation(App.Vector(1, 0, 0), 90))
    curve = Part.BSplineCurve()
    curve.interpolate([App.Vector(0.5 * i * math.cos(i * 0.3), 0, 0) for i in range(8)])
    sp.addGeometry(curve, False)
    call = lambda: features.feature_sweep(registry, doc=handle, body="Body", profile="Prof",
                                          spine="Path", name="Swept")
elif case == "sweep_circle_10000_lines":
    s0 = sketch("Prof")
    s0.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 1.5), False)
    block_all(s0)
    pts = [App.Vector(3.0 * math.sin(i / 150.0), 3.0 * (1 - math.cos(i / 150.0)), 0.01 * i)
           for i in range(10001)]
    part_spine("Spine", Part.makePolygon(pts))
    call = lambda: features.feature_sweep(registry, doc=handle, body="Body", profile="Prof",
                                          spine={"kind": "mapped_name", "object": "Spine"},
                                          name="Swept")
else:
    raise SystemExit("unknown case " + case)
doc.recompute()
info["fixture_s"] = round(time.perf_counter() - build_start, 2)

start = time.perf_counter()
try:
    env = call()
    info["status"] = env["status"]
    detail = env.get("detail") or {}
    info["detail"] = str(detail)[:300]
    sc = env.get("structured_content") or {}
    fs = sc.get("feature_state") or {}
    info["volume"] = (fs.get("shape_summary") or {}).get("volume")
    info["valid"] = (fs.get("shape_summary") or {}).get("is_valid")
except features.LoftSweepRefusal as exc:
    info["status"] = "REFUSED"
    info["code"] = exc.code
    info["detail"] = str(exc)[:300]
except Exception as exc:  # noqa: BLE001
    info["status"] = "EXC"
    info["detail"] = repr(exc)[:300]
info["elapsed_s"] = round(time.perf_counter() - start, 2)
sys.stderr.write("TIMING=" + json.dumps(info) + "\n")
