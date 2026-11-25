"""Round 2 probes: (1) a closed loft FreeCAD builds valid, through raw FreeCAD and the tool;
(2) residual: a self-intersecting sweep from a BSpline profile through the tool."""

import json
import math
import sys
import time

sys.path.insert(0, r"D:\Work\Personal\Sources\fcb-verify-13-18\src")

import FreeCAD as App  # noqa: E402
import Part  # noqa: E402
import Sketcher  # noqa: E402

from freecad_buddy.usecases import confirm, features  # noqa: E402
from freecad_buddy.usecases.documents import DocumentRegistry  # noqa: E402

confirm.set_auto_approve(True)
out = []


def emit(**kw):
    out.append(kw)
    sys.stderr.write("\nPROBE=" + json.dumps(kw) + "\n")


def bop_ok(shape):
    try:
        shape.check(True)
        return True
    except Exception as exc:  # noqa: BLE001
        return str(exc).strip().splitlines()[-1][:120]


def ring_sections(doc, body, n, kind, radius=20.0, size=4.0):
    names = []
    for k in range(n):
        theta = 360.0 * k / n
        s = doc.addObject("Sketcher::SketchObject", f"S{k}")
        body.addObject(s)
        s.Placement = App.Placement(App.Vector(), App.Rotation(App.Vector(0, 0, 1), theta)).multiply(
            App.Placement(App.Vector(), App.Rotation(App.Vector(1, 0, 0), 90)))
        if kind == "circle":
            s.addGeometry(Part.Circle(App.Vector(radius, 0, 0), App.Vector(0, 0, 1), size), False)
        else:
            c = [(radius - size, -size), (radius + size, -size), (radius + size, size), (radius - size, size)]
            s.addGeometry([Part.LineSegment(App.Vector(*c[i], 0), App.Vector(*c[(i + 1) % 4], 0))
                           for i in range(4)], False)
        s.addConstraint([Sketcher.Constraint("Block", i) for i in range(s.GeometryCount)])
        names.append(s.Name)
    return names


# (1) raw FreeCAD closed lofts around a ring
for n in (3, 4, 6, 8, 12):
    for kind in ("circle", "square"):
        for ruled in (False, True):
            doc = App.newDocument("raw")
            body = doc.addObject("PartDesign::Body", "Body")
            names = ring_sections(doc, body, n, kind)
            loft = body.newObject("PartDesign::AdditiveLoft", "Lofted")
            loft.Profile = doc.getObject(names[0])
            loft.Sections = [(doc.getObject(x), [""]) for x in names[1:]]
            loft.Ruled = ruled
            loft.Closed = True
            doc.recompute()
            sh = loft.Shape
            ok = (not sh.isNull()) and sh.isValid() and len(sh.Solids) == 1
            emit(probe="raw_closed", n=n, kind=kind, ruled=ruled, state=list(loft.State),
                 valid=(not sh.isNull()) and sh.isValid(), solids=len(sh.Solids) if not sh.isNull() else 0,
                 volume=round(sh.Volume, 2) if not sh.isNull() else None,
                 bop=bop_ok(sh) if ok else None)
            App.closeDocument(doc.Name)

# (1b) the same through the tool, for each layout
for n in (4, 6, 8, 12):
    for kind in ("circle", "square"):
        for ruled in (False, True):
            registry = DocumentRegistry()
            handle = registry.document_create("tool")["structured_content"]["doc"]
            doc = registry.with_document(handle, lambda h, d: d)
            body = doc.addObject("PartDesign::Body", "Body")
            names = ring_sections(doc, body, n, kind)
            doc.recompute()
            start = time.perf_counter()
            env = features.feature_loft(registry, doc=handle, body="Body", profile=names[0],
                                        sections=names[1:], name="Lofted", ruled=ruled, closed=True)
            ss = ((env.get("structured_content") or {}).get("feature_state") or {}).get("shape_summary") or {}
            emit(probe="tool_closed", n=n, kind=kind, ruled=ruled, status=env["status"],
                 code=(env.get("detail") or {}).get("code"),
                 message=str((env.get("detail") or {}).get("message"))[:160],
                 volume=ss.get("volume"), elapsed=round(time.perf_counter() - start, 2))
            for name in list(App.listDocuments()):
                App.closeDocument(name)

# (2) residual: BSpline profile wider than the bend of the spine (the test's layout, profile as BSpline)
for profile_kind in ("circle", "bspline"):
    for mode in ("standard", "frenet"):
        registry = DocumentRegistry()
        handle = registry.document_create("resid")["structured_content"]["doc"]
        doc = registry.with_document(handle, lambda h, d: d)
        body = doc.addObject("PartDesign::Body", "Body")
        ring = doc.addObject("Sketcher::SketchObject", "Ring")
        body.addObject(ring)
        if profile_kind == "circle":
            ring.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 10.0), False)
        else:
            curve = Part.BSplineCurve()
            curve.interpolate([App.Vector(10 * math.cos(2 * math.pi * i / 24), 10 * math.sin(2 * math.pi * i / 24), 0)
                               for i in range(24)], PeriodicFlag=True)
            ring.addGeometry(curve, False)
        ring.addConstraint([Sketcher.Constraint("Block", 0)])
        path = doc.addObject("Sketcher::SketchObject", "Path")
        body.addObject(path)
        path.Placement = App.Placement(App.Vector(), App.Rotation(App.Vector(1, 0, 0), 90))
        path.addGeometry(Part.ArcOfCircle(Part.Circle(App.Vector(-2, 0, 0), App.Vector(0, 0, 1), 2.0), 0.0, 1.5), False)
        path.addConstraint([Sketcher.Constraint("Block", 0)])
        doc.recompute()
        env = features.feature_sweep(registry, doc=handle, body="Body", profile="Ring", spine="Path",
                                     name="Swept", mode=mode)
        sw = doc.getObject("Swept")
        sh = sw.Shape if sw is not None else None
        ss = ((env.get("structured_content") or {}).get("feature_state") or {}).get("shape_summary") or {}
        emit(probe="selfintersect", profile=profile_kind, mode=mode, status=env["status"],
             code=(env.get("detail") or {}).get("code"), is_valid=ss.get("is_valid"),
             solids=ss.get("solid_count"), volume=ss.get("volume"),
             bop=bop_ok(sh) if sh is not None and not sh.isNull() else None)
        for name in list(App.listDocuments()):
            App.closeDocument(name)

# (3) RT-4 variants: long helices accepted, time through the tool
for label in ("Part::Helix pitch1 h120", "Part::Helix pitch1 h150", "makeHelix 500 turns"):
    registry = DocumentRegistry()
    handle = registry.document_create("helix")["structured_content"]["doc"]
    doc = registry.with_document(handle, lambda h, d: d)
    body = doc.addObject("PartDesign::Body", "Body")
    prof = doc.addObject("Sketcher::SketchObject", "Prof")
    body.addObject(prof)
    r_helix = 10.0 if label.startswith("makeHelix") else 5.0
    prof.Placement = App.Placement(App.Vector(), App.Rotation(App.Vector(1, 0, 0), 90))
    prof.addGeometry(Part.Circle(App.Vector(r_helix, 0, 0), App.Vector(0, 0, 1), 0.3), False)
    prof.addConstraint([Sketcher.Constraint("Block", 0)])
    if label.startswith("makeHelix"):
        sp = doc.addObject("Part::Feature", "Spine")
        sp.Shape = Part.makeHelix(5.0, 2500.0, 10.0)
    else:
        sp = doc.addObject("Part::Helix", "Spine")
        sp.Pitch = 1.0
        sp.Height = 120.0 if "h120" in label else 150.0
        sp.Radius = 5.0
    doc.recompute()
    poles = [len(e.Curve.getPoles()) for e in sp.Shape.Edges if hasattr(e.Curve, "getPoles")]
    start = time.perf_counter()
    try:
        env = features.feature_sweep(registry, doc=handle, body="Body", profile="Prof",
                                     spine={"kind": "mapped_name", "object": "Spine"},
                                     name="Swept", mode="frenet")
        status, code = env["status"], (env.get("detail") or {}).get("code")
    except features.LoftSweepRefusal as exc:
        status, code = "REFUSED", exc.code
    emit(probe="helix", label=label, edges=len(sp.Shape.Edges), poles=poles[:3], status=status,
         code=code, elapsed=round(time.perf_counter() - start, 2))
    for name in list(App.listDocuments()):
        App.closeDocument(name)
