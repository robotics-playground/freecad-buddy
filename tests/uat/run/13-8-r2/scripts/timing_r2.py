"""Round 2: time the red team's shapes through the container bridge."""

import asyncio
import json
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = "http://127.0.0.1:18765/mcp"
OUT = sys.argv[1]

HELPERS = r"""
import math, Part, FreeCAD as App
def coil_spring(turns):
    helix = Part.makeHelix(6, 6 * turns, 20)
    circle = Part.Wire(Part.makeCircle(1, App.Vector(20, 0, 0), App.Vector(0, 1, 0)))
    return Part.Wire(helix).makePipeShell([circle], True, True)
def prism(sides):
    corners = [App.Vector(50 * math.cos(2 * math.pi * i / sides), 50 * math.sin(2 * math.pi * i / sides), 0) for i in range(sides)]
    return Part.Face(Part.makePolygon(corners + [corners[0]])).extrude(App.Vector(0, 0, 10))
def hex_hole_plate(holes):
    columns = 40
    plate = Part.makeBox(columns * 6 + 6, (holes // columns + 1) * 6 + 6, 10)
    prisms = []
    for index in range(holes):
        center = App.Vector(7 + 6 * (index % columns), 7 + 6 * (index // columns), 0)
        corners = [center + App.Vector(2 * math.cos(math.pi / 3 * k), 2 * math.sin(math.pi / 3 * k), 0) for k in range(6)]
        prisms.append(Part.Face(Part.makePolygon(corners + [corners[0]])).extrude(App.Vector(0, 0, 10)))
    return plate.cut(Part.makeCompound(prisms))
def pole_load(shape):
    return sum((f.Surface.NbUPoles * f.Surface.NbVPoles) ** 2 for f in shape.Faces if hasattr(f.Surface, "NbUPoles"))
"""

REFERENCE = r"""
import json
s = doc.getObject(NAME).Shape.copy()
d = App.Vector(*NORMAL); d.normalize()
bb = s.BoundBox; h = 3 * bb.DiagonalLength + 10
base = bb.Center + d * (OFFSET - d.dot(bb.Center))
pf = Part.Plane(base, d).toShape(-h, h, -h, h)
edges = s.section(pf).Edges
wires = [Part.Wire(g) for g in Part.sortEdges(edges)]
common = s.common(pf).Area
try:
    bullseye = Part.makeFace(wires, "Part::FaceMakerBullseye").Area
except Exception as e:
    bullseye = repr(e)
result = json.dumps({"wires": len(wires), "closed": sum(1 for w in wires if w.isClosed()),
    "length": sum(w.Length for w in wires), "common_area": common, "bullseye_area": bullseye})
"""

CASES = [
    # label, build expression, plane normal, offset, reference?
    ("spring 30 turns", "coil_spring(30)", "y", 0.5, False),
    ("prism 9,990 sides (9,992 faces)", "prism(9990)", "z", 5.0, False),
    ("prism 2,898 sides (2,900 faces)", "prism(2898)", "z", 5.0, True),
    ("plate 1,400 hex holes", "hex_hole_plate(1400)", "z", 5.0, False),
    ("spring 5 turns", "coil_spring(5)", "y", 0.5, True),
    ("spring 10 turns", "coil_spring(10)", "y", 0.5, True),
]


async def call(session, name, args):
    start = time.perf_counter()
    reply = await session.call_tool(name, args)
    return (reply.structuredContent or {}), time.perf_counter() - start


async def wait_ready(session):
    start = time.perf_counter()
    while time.perf_counter() - start < 900:
        body, _ = await call(session, "document_list", {})
        if body.get("status") == "OK":
            return round(time.perf_counter() - start, 1)
        await asyncio.sleep(10)
    raise RuntimeError("bridge did not answer within 900 s")


async def main():
    log = []
    async with streamable_http_client(URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            created, _ = await call(session, "document_create", {"label": "SectionR2"})
            doc = created["structured_content"]["doc"]
            for index, (label, expression, normal, offset, want_reference) in enumerate(CASES):
                name = f"Shape{index}"
                code = HELPERS + (
                    f"obj = doc.addObject('Part::Feature', {name!r})\nobj.Shape = {expression}\n"
                    "result = [len(obj.Shape.Faces), len(obj.Shape.Solids), pole_load(obj.Shape)]"
                )
                built, build_s = await call(session, "script_exec", {"doc": doc, "code": code})
                waited = None
                if built.get("status") != "OK":
                    waited = await wait_ready(session)
                info, _ = await call(session, "script_exec", {"doc": doc, "code": HELPERS + (
                    f"s = doc.getObject({name!r}).Shape\n"
                    "result = [len(s.Faces), len(s.Solids), pole_load(s), s.isValid()]")})
                body, secs = await call(session, "query_section", {
                    "doc": doc, "object": name,
                    "plane": {"normal": normal, "offset": {"value": offset, "unit": "mm"}}})
                after, after_s = await call(session, "document_list", {})
                reference = None
                if want_reference:
                    vector = {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]}[normal]
                    ref, ref_s = await call(session, "script_exec", {"doc": doc, "code": HELPERS + (
                        f"NAME = {name!r}\nNORMAL = {vector}\nOFFSET = {offset}\n") + REFERENCE})
                    reference = {"status": ref.get("status"), "elapsed_s": round(ref_s, 2),
                                 "value": (ref.get("structured_content") or {}).get("value_repr")}
                    if ref.get("status") != "OK":
                        reference["waited_for_bridge_s"] = await wait_ready(session)
                row = {"label": label, "build_status": built.get("status"), "build_s": round(build_s, 2),
                       "waited_for_bridge_s": waited,
                       "faces_solids_poleload_valid": (info.get("structured_content") or {}).get("value_repr"),
                       "status": body.get("status"), "detail": body.get("detail"),
                       "sc": body.get("structured_content"), "text": body.get("text"),
                       "elapsed_s": round(secs, 2), "bridge_after": after.get("status"),
                       "bridge_after_s": round(after_s, 2), "reference": reference}
                print(json.dumps(row)[:700], flush=True)
                log.append(row)
                with open(OUT, "w") as fh:
                    json.dump(log, fh, indent=1)
            await call(session, "document_close", {"doc": doc})


asyncio.run(main())
