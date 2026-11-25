"""CAP-1 replay of query_section against script_exec Shape.section/common, in the container."""

import asyncio
import json
import math
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = "http://127.0.0.1:18765/mcp"
OUT = sys.argv[1]

BUILD = r"""
import Part, FreeCAD
V = FreeCAD.Vector
box = doc.addObject("Part::Box", "Box"); box.Length, box.Width, box.Height = 10, 20, 30
cyl = doc.addObject("Part::Cylinder", "Cyl"); cyl.Radius, cyl.Height = 5, 20
outer = Part.Wire(Part.makePolygon([V(0,0,0), V(100,0,0), V(100,60,0), V(0,60,0), V(0,0,0)]))
holes = [Part.Wire(Part.makeCircle(3, V(x, y, 0))) for x, y in ((20,15),(80,15),(20,45),(80,45))]
plate = doc.addObject("Part::Feature", "Plate")
plate.Shape = Part.makeFace([outer] + holes, "Part::FaceMakerCheese").extrude(V(0,0,5))
rings = [Part.Wire(Part.makeCircle(r, V(0,0,0))) for r in (30, 20, 10)]
eye = doc.addObject("Part::Feature", "Bullseye")
eye.Shape = Part.makeFace(rings, "Part::FaceMakerBullseye").extrude(V(0,0,8))
shell = doc.addObject("Part::Feature", "Shell")
shell.Shape = Part.makeBox(10, 20, 30).Shells[0]
moved = doc.addObject("Part::Box", "Moved"); moved.Length, moved.Width, moved.Height = 10, 20, 30
moved.Placement.Base = V(0, 0, 100)
rev = Part.makeBox(10, 20, 30); rev.reverse()
reversed_obj = doc.addObject("Part::Feature", "Reversed"); reversed_obj.Shape = rev
doc.recompute()
result = {o.Name: [o.Shape.ShapeType, len(o.Shape.Solids), len(o.Shape.Faces), o.Shape.isValid()] for o in doc.Objects}
"""

REFERENCE = r"""
import Part, FreeCAD, json
def ref(name, n, off):
    s = doc.getObject(name).Shape.copy()
    d = FreeCAD.Vector(*n); d.normalize()
    bb = s.BoundBox; h = 3 * bb.DiagonalLength + 10
    base = bb.Center + d * (off - d.dot(bb.Center))
    pf = Part.Plane(base, d).toShape(-h, h, -h, h)
    edges = s.section(pf).Edges
    wires = [Part.Wire(g) for g in Part.sortEdges(edges)]
    try:
        area = s.common(pf).Area
    except Exception as e:
        area = repr(e)
    sl = s.slice(d, off) if len(s.Solids) else []
    return {"wires": len(wires), "closed": sum(1 for w in wires if w.isClosed()),
            "length": sum(w.Length for w in wires), "area": area, "slice_wires": len(sl)}
result = json.dumps([ref(*c) for c in CASES])
"""

FINGERPRINT = r"""
from freecad_buddy.usecases.fingerprint import fingerprint
result = fingerprint(doc, fresh=True)["digest"]
"""

AXES = {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}
P = math.pi
CASES = [
    # name, object, normal, offset, analytic {wires, closed, area, length} (None = no analytic)
    ("box mid z15", "Box", "z", 15, (1, 1, 200, 60)),
    ("box at bottom face z0", "Box", "z", 0, (1, 1, 200, 60)),
    ("box 1e-6 inside bottom", "Box", "z", 1e-6, (1, 1, 200, 60)),
    ("box at top face z30", "Box", "z", 30, (1, 1, 200, 60)),
    ("box 1e-6 inside top", "Box", "z", 30 - 1e-6, (1, 1, 200, 60)),
    ("box miss z40", "Box", "z", 40, (0, 0, 0, 0)),
    ("box x5", "Box", "x", 5, (1, 1, 600, 100)),
    ("box oblique [1,1,1] through centre", "Box", [1, 1, 1], 30 / math.sqrt(3), None),
    ("cylinder z10", "Cyl", "z", 10, (1, 1, 25 * P, 10 * P)),
    ("cylinder x0 through axis", "Cyl", "x", 0, (1, 1, 200, 60)),
    ("plate 4 holes z2.5", "Plate", "z", 2.5, (5, 5, 6000 - 4 * 9 * P, 320 + 4 * 6 * P)),
    ("bullseye z4", "Bullseye", "z", 4, (3, 3, 600 * P, 120 * P)),
    ("shell z15", "Shell", "z", 15, (1, 1, None, 60)),
    ("moved box z115 (own Placement)", "Moved", "z", 115, (1, 1, 200, 60)),
    ("moved box z15 (misses)", "Moved", "z", 15, (0, 0, 0, 0)),
]


def payload(reply):
    return reply.structuredContent or {}


async def call(session, name, args):
    start = time.perf_counter()
    reply = await session.call_tool(name, args)
    return payload(reply), time.perf_counter() - start


async def script(session, doc, code):
    body, _ = await call(session, "script_exec", {"doc": doc, "code": code})
    assert body.get("status") == "OK", body
    return body["structured_content"]


async def main():
    log = {"cases": [], "extra": {}}
    async with streamable_http_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed, _ = await call(session, "document_list", {})
            for d in listed.get("structured_content", {}).get("documents", []):
                await call(session, "document_close", {"doc": d["doc"]})
            created, _ = await call(session, "document_create", {"label": "Section1381"})
            doc = created["structured_content"]["doc"]
            log["build"] = await script(session, doc, BUILD)
            print(json.dumps(log["build"])[:600])
            ref_cases = [[o, (AXES[n] if isinstance(n, str) else n), off] for _, o, n, off, _ in CASES]
            refs_raw = await script(session, doc, f"CASES = {json.dumps(ref_cases)}\n" + REFERENCE)
            log["reference_raw"] = refs_raw
            fp_before = await script(session, doc, FINGERPRINT)
            refs = json.loads(eval(refs_raw["value_repr"]))
            for (label, obj, normal, offset, analytic), ref in zip(CASES, refs):
                args = {"doc": doc, "object": obj,
                        "plane": {"normal": normal, "offset": {"value": offset, "unit": "mm"}}}
                body, secs = await call(session, "query_section", args)
                sc = body.get("structured_content", {})
                log["cases"].append({"label": label, "args": args, "status": body.get("status"),
                                     "detail": body.get("detail"), "sc": sc, "text": body.get("text"),
                                     "reference": ref, "analytic": analytic, "elapsed_s": round(secs, 3)})
            # polylines
            for label, pts in (("cyl polylines cap 5", {"deflection": {"value": 0.01, "unit": "mm"}, "max_points": 5}),
                               ("cyl polylines default", {"deflection": {"value": 0.01, "unit": "mm"}}),
                               ("deflection below floor", {"deflection": {"value": 1e-9, "unit": "mm"}}),
                               ("deflection zero", {"deflection": {"value": 0, "unit": "mm"}})):
                args = {"doc": doc, "object": "Cyl", "plane": {"normal": "z", "offset": {"value": 10, "unit": "mm"}}, "points": pts}
                body, secs = await call(session, "query_section", args)
                log["extra"][label] = {"status": body.get("status"), "detail": body.get("detail"),
                                       "sc": body.get("structured_content"), "elapsed_s": round(secs, 3)}
            for label, args in (
                ("reversed solid", {"object": "Reversed", "plane": {"normal": "z", "offset": {"value": 15, "unit": "mm"}}}),
                ("zero normal", {"object": "Box", "plane": {"normal": [0, 0, 0], "offset": {"value": 15, "unit": "mm"}}}),
                ("unknown object", {"object": "Nope", "plane": {"normal": "z", "offset": {"value": 15, "unit": "mm"}}}),
            ):
                body, secs = await call(session, "query_section", {"doc": doc, **args})
                log["extra"][label] = {"status": body.get("status"), "detail": body.get("detail"), "text": body.get("text")}
            fp_after = await script(session, doc, FINGERPRINT)
            log["fingerprint_before"] = fp_before.get("value_repr")
            log["fingerprint_after"] = fp_after.get("value_repr")
            log["doc"] = doc
    with open(OUT, "w") as fh:
        json.dump(log, fh, indent=1)


asyncio.run(main())
